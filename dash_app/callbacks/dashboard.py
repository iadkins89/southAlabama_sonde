from dash import callback, Input, Output, State, html, dcc
from dash.exceptions import PreventUpdate
import dash_bootstrap_components as dbc
import plotly.graph_objs as go
from datetime import datetime, timedelta
from server.utils import save_data_to_csv, get_measurement_summary
from server.models import (get_data,
                           get_sensor_timezone,
                           get_sensor_by_name,
                           get_most_recent)
import pytz
from dateutil.parser import parse as parse_date
# ----------------------------
# Time series graphs
# ----------------------------
@callback(
    Output('multi-sensor-graph', 'children'),
    [
        Input("date-range-radio", "value"),
        Input("sensor-name-store", "data"),
        Input("live-sensor-data", "data")
    ]
)
def update_multi_sensor_graph(date_range_value, sensor_name, live_data):

    if not sensor_name:
        return html.Div("No sensor selected.")

    now = datetime.utcnow()
    if date_range_value == "2-days":
        start = now - timedelta(days=2)
    elif date_range_value == "1-week":
        start = now - timedelta(weeks=1)
    elif date_range_value == "1-month":
        start = now - timedelta(weeks=4)
    elif date_range_value == "1-year":
        start = now - timedelta(days=365)
    else:
        start = now - timedelta(days=2)

    # Query data with units
    data = get_data(sensor_name, start, now, lora=False)

    if not data:
        return html.Div(f"No data available for sensor '{sensor_name}' in the selected date range.")

    # Prepare Timezone for Display
    tz_str = get_sensor_timezone(sensor_name)
    try:
        target_tz = pytz.timezone(tz_str)
    except:
        target_tz = pytz.utc

    # Process data
    parameter_data = {}
    parameter_units = {}

    for row in data:
        timestamp, value, parameter_name, unit = row.timestamp, row.value, row.name, row.unit
        local_ts = timestamp.replace(tzinfo=pytz.utc).astimezone(target_tz)
        if parameter_name not in parameter_data:
            if parameter_name == "longitude" or parameter_name == "latitude":
                continue
            parameter_data[parameter_name] = {"timestamps": [], "values": []}
            parameter_units[parameter_name] = unit
        parameter_data[parameter_name]["timestamps"].append(local_ts)
        parameter_data[parameter_name]["values"].append(value)

    # Sort data by timestamps for each parameter
    for parameter, values in parameter_data.items():
        sorted_data = sorted(
            zip(values["timestamps"], values["values"]),
            key=lambda x: x[0]
        )
        parameter_data[parameter]["timestamps"], parameter_data[parameter]["values"] = zip(*sorted_data)

    # Generate graphs dynamically
    graphs = []
    for parameter, values in parameter_data.items():
        min_y = min(values["values"])
        max_y = max(values["values"])
        y_padding = (max_y - min_y) * 0.2
        unit = parameter_units[parameter]

        # Get the very last point for the "Live" indicator
        last_time = values["timestamps"][-1]
        last_val = values["values"][-1]

        # Check if the last point is older than 24 hours
        now_aware = datetime.utcnow().replace(tzinfo=pytz.utc).astimezone(target_tz)
        is_active = (now_aware - last_time) < timedelta(days=1)

        trace_data = []

        trace_data.append(go.Scatter(
            x=values["timestamps"],
            y=values["values"],
            mode="lines",
            name="History",
            line={"color": "#1f77b4", "width": 2, "shape": "spline", "smoothing": 0.3},
            fill='tozeroy',  # Uncomment for "Area Chart" style
            fillcolor='rgba(0, 123, 255, 0.1)',
            # %{y:.2f} = value with 2 decimals
            # <extra></extra> = removes the side box (name/icon)
            hovertemplate=f'%{{y:.2f}} {unit}<extra></extra>'
        ))

        # Live Indicators (Only if active)
        if is_active:
            # Halo (Glow)
            trace_data.append(go.Scatter(
                x=[last_time], y=[last_val], mode="markers",
                marker={"color": "rgba(220, 53, 69, 0.3)", "size": 25, "line": {"width": 0}},
                hoverinfo="skip"  # Never show tooltip for the glow
            ))
            # Red Dot
            trace_data.append(go.Scatter(
                x=[last_time], y=[last_val],
                mode="markers+text",
                marker={"color": "#dc3545", "size": 12, "line": {"width": 2, "color": "white"}},
                hoverinfo="skip",  # Skip this too! The Line tooltip already covers this point.
                text=["Live"],
                textposition="middle right",
                textfont=dict(
                    color="#dc3545",
                    size=12,
                    family="Arial Black, sans-serif"
                ),
            ))

        graph = dcc.Graph(
            figure={
                "data": trace_data,
                "layout": go.Layout(
                    uirevision=sensor_name,
                    template="plotly_white",
                    xaxis={
                        "tickangle": -45, "showgrid": True, "gridcolor": "#f0f0f0",
                        "linecolor": "#dcdcdc", "showline": True
                    },
                    yaxis={
                        "title": f"{parameter.replace('_', ' ').capitalize()}{f' ({unit})' if unit else ''}",
                        "range": [min_y - y_padding, max_y + y_padding],
                        "showgrid": True, "gridcolor": "#f0f0f0",
                    },
                    margin={"l": 60, "r": 40, "t": 40, "b": 80},
                    height=300,
                    showlegend=False,
                    hovermode="x unified"  # Professional vertical line hover
                )
            },
            config={
                "responsive": True,
                'displayModeBar': False,
                'displaylogo': False
            },
        )
        graphs.append(dbc.Col(graph, xs=12, sm=12, md=12, lg=12))
    return graphs

# ----------------------------
# File download
# ----------------------------
@callback(
    Output("download-data-offcanvas", "is_open"),
    Input("download-button", "n_clicks"),
    [State("download-data-offcanvas", "is_open")],
)
def toggle_download_data_offcanvas(n_clicks, is_open):
    if n_clicks:
        return not is_open
    return is_open

@callback(
    [Output('confirm-dialog', 'displayed'),
    Output('confirm-dialog', 'message'),
    Output('download-dataframe-csv', 'data'),],
    [Input("set-filename-btn", 'n_clicks'),
     Input('sensor-name-store', 'data')],
    [State('date-picker-range', 'start_date'),
     State('date-picker-range', 'end_date'),
     State('csv-filename', 'value'),
     State('radio-data-item', 'value')]
)
def file_download(n_clicks, sensor_name, start_date, end_date, filename, data_type):
    if n_clicks is None:
        raise PreventUpdate
    else:
        #Convert dates from string to date_time object and set hr/min/sec to get full days
        start_date = parse_date(start_date).replace(hour=0, minute=0, second=0)
        end_date = parse_date(end_date).replace(hour=23, minute=59, second=59)

        if not start_date or not end_date:
            return True, 'Please provide a valid date range and filename.', None
        if not filename:
            return True, 'Please provide a valid filename.', None

        if data_type == "   Sensor Data":
            data = get_data(sensor_name, start_date, end_date, lora=False, localize_input=True)
        else:
            data = get_data(sensor_name, start_date, end_date, lora=True, localize_input=True)

        if not data:
            return True, 'No data found for the given date range.', None

        saved_csv_file = save_data_to_csv(data, sensor_name)
        return False, '', dict(content=saved_csv_file, filename=f"{filename}.csv")
    return False, '', None

# ----------------------------
# Sensor health
# ----------------------------
@callback(
    Output("sensor-health-offcanvas", "is_open"),
    Input("sensor-health-button", "n_clicks"),
    [State("sensor-health-offcanvas", "is_open")],
)
def toggle_sensor_health_offcanvas(n_clicks, is_open):
    if n_clicks:
        return not is_open
    return is_open

@callback(
    [Output("battery-gauge", "value"),
     Output("battery-gauge", "label"),
     Output("battery-gauge", "color"),
     Output("rssi-progress", "value"),
     Output("rssi-progress", "label"),
     Output("rssi-progress", "color"),
     Output("snr-progress", "value"),
     Output("snr-progress", "label"),
     Output("snr-progress", "color")],
    [Input("sensor-name-store", "data"),
     Input("live-sensor-data", "data")]
)
def update_sensor_health(sensor_name, live_data):

    raw_data = get_most_recent(sensor_name, Lora=True)

    # Structure from query is: (SensorDataObj, param_name, unit)
    readings = {row[1].lower(): row[0].value for row in raw_data}

    battery = readings.get('battery')
    rssi = readings.get('rssi')
    snr = readings.get('snr')

    # Handle missing data
    if battery is None:
        battery_label = "No battery data available"
        battery_color = "secondary"  # You can use a different color like gray for unavailable data
    else:
        if battery >= 3.7:
            battery_color = "success"
        elif 3.5 <= battery < 3.7:
            battery_color = 'warning'
        else:
            battery_color = 'danger'
        battery_label = f"{battery} V"

    if rssi is None:
        rssi_label = "No RSSI data available"
        rssi_color = "secondary"
    else:
        rssi_transformed = max(0, min(100, int((rssi + 120) * 100 / 120)))  # Map -120 to 0 dBm -> 0 to 100
        if rssi >= -50:
            rssi_color = "success"  # Good
        elif -80 <= rssi < -50:
            rssi_color = "warning"  # Moderate
        else:
            rssi_color = "danger"  # Poor
        rssi_label = f"{rssi} dBm"

    if snr is None:
        snr_label = "No SNR data available"
        snr_color = "secondary"
    else:
        snr_transformed = max(0, min(100, int((snr + 20) * 100 / 40)))  # Map -20 to 20 dB -> 0 to 100
        if snr > 10:
            snr_color = "success"  # Good
        elif 0 <= snr <= 10:
            snr_color = "warning"  # Moderate
        else:
            snr_color = "danger"  # Poor
        snr_label = f"{snr} dB"

    # Return updated values, labels, and colors
    return (
        battery if battery is not None else 0, battery_label, battery_color,
        rssi_transformed if rssi is not None else 0, rssi_label, rssi_color,
        snr_transformed if snr is not None else 0, snr_label, snr_color,
    )

# ----------------------------
# Summary Info
# ----------------------------

@callback(
    Output("sensor-image", "src"),
    Input("sensor-name-store", "data"),
)
def get_sensor_pic(sensor_name):
    if not sensor_name:
        return "/assets/no_image_available.png"

    sensor = get_sensor_by_name(sensor_name)

    # If DB has image_data, use it. Else, default.
    if sensor and sensor.image_data:
        image_src = sensor.image_data
    else:
        image_src = "/assets/no_image_available.png"

    return image_src
@callback(
    [Output("card-title", "children"),
     Output("summary-content", "children")],
    [Input("sensor-name-store", "data"),
    Input("live-sensor-data", "data")]
)
def update_summary_from_url(sensor_name, live_data):
    if not sensor_name:
        return "No Sensor Found", html.P("No sensor data was found.", className="text-warning")

    # Fetch summary information for the sensor
    summary = get_measurement_summary(sensor_name)

    if "error" in summary:
        return sensor_name, html.P(summary["error"], className="text-danger")

    if "message" in summary:
        return sensor_name, html.P(summary["message"], className="text-info")

    # Prepare content dynamically based on the most recent measurements
    recent_measurements = summary.get("most_recent_measurements", [])

    if not recent_measurements:
        return sensor_name, html.P("No data received yet.", className="text-warning")

    tz_str = summary.get("timezone", "UTC")
    try:
        target_tz = pytz.timezone(tz_str)
        utc_ts = recent_measurements[0]["timestamp"].replace(tzinfo=pytz.utc)
        local_ts = utc_ts.astimezone(target_tz)
        timestamp_str = local_ts.strftime("%a %b %d, %H:%M")
        timestamp_str = f"{timestamp_str} ({tz_str})"
    except:
        timestamp_str = str(recent_measurements[0]["timestamp"])
        timestamp_str = f"{timestamp_str} ({tz_str})"

    #Format title
    title_name = sensor_name + " " + "Information"
    title_name = title_name.title()

    title = html.Div(
        title_name,
        style={
            "text-align": "center",
            "font-weight": "bold"
        },
    )
    # Format the content with parameters and values
    parameter_list = html.Div(
        [
            dbc.Row(
                [
                    dbc.Col(html.Div(measurement['parameter'].replace("_", " "), style={'text-align': 'left', 'font-size': '14px'}), width=9),
                    dbc.Col(html.Div(f"{round(measurement['value'], 1)}", style={'text-align': 'right', 'font-size': '14px'}), width=3),
                ]
            )
            for measurement in recent_measurements
        ],
        style={"list-style-type": "none", "padding": "0", "margin": "0"}  # Remove bullet points and extra spacing
    )

    latitude = str(summary['latitude']) + u'\N{DEGREE SIGN}' + 'N'
    longitude = str(summary['longitude']) + u'\N{DEGREE SIGN}' + 'W'
    location = latitude + "   " + longitude

    # Combine the timestamp and parameters
    content = html.Div(
        [
            html.Div(
                timestamp_str,
                style={
                    "text-align": "center",
                    "font-weight": "bold"
                },
            ),
            html.Div(
                location,
                style={
                    "text-align": "center",
                    "font-size": "14px",
                    "margin-bottom": "10px",
                }
            ),
            parameter_list,
        ]
    )

    return title, content
