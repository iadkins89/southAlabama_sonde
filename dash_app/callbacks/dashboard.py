from dash import callback, Input, Output, State, html, dcc, ALL, MATCH, ctx, no_update
from dash.exceptions import PreventUpdate
import dash_bootstrap_components as dbc
import plotly.graph_objs as go
from datetime import datetime, timedelta
from server.utils import BATTERY_MIN_V, save_data_to_csv, get_measurement_summary,create_map_markers, get_deployment_statistics
from server.models import (get_data,
                           get_sensor_timezone,
                           get_sensor_by_name,
                           get_most_recent,
                           get_past_deployments)
import pytz
from dateutil.parser import parse as parse_date
import dash_leaflet as dl
from server.qc import SUSPECT

# Longer than this between water levels draws as a break in the line, not a bridge.
GAUGE_GAP = timedelta(minutes=15)

# The 1 year view sends each block's low and high instead of every reading, until
# a zoom brings the span down to this length.
THIN_BLOCKS = 1000
THIN_ABOVE = timedelta(days=31)


def display_decimals(parameter):
    # Tides here are a few tenths of a metre, which 1 decimal would flatten.
    return 3 if parameter.startswith("water_level") else 1


def break_line_at_gaps(timestamps, values, max_gap):
    x, y = [], []
    for i, (timestamp, value) in enumerate(zip(timestamps, values)):
        if i > 0 and timestamp - timestamps[i - 1] > max_gap:
            x.append(timestamp)
            y.append(None)
        x.append(timestamp)
        y.append(value)
    return x, y


def thin_stretch(timestamps, values, first, last, origin, block_width):
    """The positions of one unbroken stretch that are worth keeping, in time order."""
    lows, highs = {}, {}
    for i in range(first, last + 1):
        block = int((timestamps[i] - origin) / block_width)
        if block not in lows or values[i] < values[lows[block]]:
            lows[block] = i
        if block not in highs or values[i] > values[highs[block]]:
            highs[block] = i
    return sorted({first, last, *lows.values(), *highs.values()})


def thin_line(timestamps, values, max_gap=None, blocks=THIN_BLOCKS):
    """
    Reduces a line to each time block's low and high, so peaks survive. Gaps are
    found first, because the kept points are far apart even with no gap.
    """
    origin = timestamps[0]
    block_width = (timestamps[-1] - origin) / blocks

    x, y = [], []
    first = 0
    for i in range(1, len(timestamps) + 1):
        if i < len(timestamps) and not (max_gap and timestamps[i] - timestamps[i - 1] > max_gap):
            continue
        if x:
            x.append(timestamps[first])
            y.append(None)
        for kept in thin_stretch(timestamps, values, first, i - 1, origin, block_width):
            x.append(timestamps[kept])
            y.append(values[kept])
        first = i
    return x, y


# ----------------------------
# Time series graphs
# ----------------------------
def is_year_view(radio, deploy_data):
    # A past deployment hides the range buttons and uses the slider instead.
    return radio == "1-year" and not (deploy_data and not deploy_data.get('is_current', False))


def graph_window(radio, slider, deploy_data):
    if deploy_data and not deploy_data.get('is_current', False):
        return datetime.fromtimestamp(slider[0]), datetime.fromtimestamp(slider[1])

    end = datetime.utcnow()
    days = {"2-days": 2, "1-week": 7, "1-month": 30, "1-year": 365}.get(radio, 2)
    start = end - timedelta(days=days)

    if deploy_data and deploy_data.get('is_current', False):
        # Parse the actual start date of the CURRENT deployment
        deploy_start = parse_date(deploy_data['start_iso'])

        # If the calculated start date is older than the deployment, clamp it
        if start < deploy_start:
            start = deploy_start

    return start, end


def load_series(sensor_name, start, end, only_parameter=None, localize_input=False):
    """Returns the graphed values per parameter, in time order and in the sensor's timezone."""
    data = get_data(sensor_name, start, end, lora=False, localize_input=localize_input)

    tz_str = get_sensor_timezone(sensor_name)
    try:
        target_tz = pytz.timezone(tz_str)
    except:
        target_tz = pytz.utc

    series = {}
    for row in data:
        parameter = row.name
        if parameter in ("longitude", "latitude"):
            continue
        if only_parameter and parameter != only_parameter:
            continue
        if parameter not in series:
            series[parameter] = {"timestamps": [], "values": [], "flags": [], "unit": row.unit}
        series[parameter]["timestamps"].append(row.timestamp.replace(tzinfo=pytz.utc).astimezone(target_tz))
        series[parameter]["values"].append(row.value)
        series[parameter]["flags"].append(row.qc_flag)

    for values in series.values():
        sorted_data = sorted(zip(values["timestamps"], values["values"], values["flags"]), key=lambda x: x[0])
        values["timestamps"], values["values"], values["flags"] = zip(*sorted_data)

    return series


def build_figure(sensor_name, parameter, values, radio, thin, show_live):
    timestamps, readings, unit = values["timestamps"], values["values"], values["unit"]
    min_y = min(readings)
    max_y = max(readings)
    y_padding = (max_y - min_y) * 0.2

    trace_data = []
    is_water_level = parameter == "water_level"
    hover_format = ".3f" if is_water_level else ".2f"
    max_gap = GAUGE_GAP if is_water_level else None
    thin = thin and timestamps[-1] - timestamps[0] > THIN_ABOVE

    if thin:
        line_x, line_y = thin_line(timestamps, readings, max_gap)
    elif is_water_level:
        line_x, line_y = break_line_at_gaps(timestamps, readings, max_gap)
    else:
        line_x, line_y = timestamps, readings

    # NAVD88 levels can cross zero, so filling down to zero would mislead.
    area_style = {} if is_water_level else {"fill": "tozeroy", "fillcolor": "rgba(0, 123, 255, 0.1)"}  # Area chart style

    trace_data.append(go.Scatter(
        x=line_x,
        y=line_y,
        mode="lines",
        name="History",
        # A curve through alternating lows and highs would overshoot both.
        line={"color": "#1f77b4", "width": 1 if thin else 2,
              **({} if thin else {"shape": "spline", "smoothing": 0.3})},
        # <extra></extra> = removes the side box (name/icon)
        hovertemplate=f'%{{y:{hover_format}}} {unit}<extra></extra>',
        **area_style
    ))

    suspect_points = [(t, v) for t, v, flag in zip(timestamps, readings, values["flags"]) if flag == SUSPECT]
    if suspect_points:
        suspect_x, suspect_y = zip(*suspect_points)
        trace_data.append(go.Scatter(
            x=suspect_x,
            y=suspect_y,
            mode="markers",
            name="Suspect",
            marker={"color": "#fd7e14", "size": 8, "symbol": "diamond",
                    "line": {"width": 1, "color": "white"}},
            hovertemplate=f'%{{y:{hover_format}}} {unit} (suspect)<extra></extra>'
        ))

    # Live Indicators (Only if active)
    if show_live:
        last_time = timestamps[-1]
        last_val = readings[-1]
        # Halo (Glow)
        trace_data.append(go.Scatter(
            x=[last_time], y=[last_val], mode="markers",
            marker={"color": "rgba(220, 53, 69, 0.3)", "size": 25, "line": {"width": 0}},
            hoverinfo="skip"
        ))
        # Red Dot
        trace_data.append(go.Scatter(
            x=[last_time], y=[last_val],
            mode="markers+text",
            marker={"color": "#dc3545", "size": 12, "line": {"width": 2, "color": "white"}},
            hoverinfo="skip",  # The Line tooltip already covers this point.
            text=["Live"],
            textposition="middle right",
            textfont=dict(
                color="#dc3545",
                size=12,
                family="Arial Black, sans-serif"
            ),
        ))

    return {
        "data": trace_data,
        "layout": go.Layout(
            uirevision=f"{sensor_name}-{radio}",  # Keeps a zoom until the range changes
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
            hovermode="x unified"  # vertical line hover
        )
    }


@callback(
    Output('multi-sensor-graph', 'children'),
    [
        Input("date-range-radio", "value"),
        Input("historic-date-slider", "value"),
        Input("sensor-name-store", "data"),
        Input("selected-deployment-store", "data"),
        Input("live-sensor-data", "data")
    ]
)
def update_multi_sensor_graph(radio, slider, sensor_name, deploy_data, live_data):

    if not sensor_name:
        return html.Div("No sensor selected.")

    # One new reading can't be seen at this scale, and redrawing would undo a zoom.
    year_view = is_year_view(radio, deploy_data)
    if year_view and ctx.triggered_id == "live-sensor-data":
        raise PreventUpdate

    start, end = graph_window(radio, slider, deploy_data)
    series = load_series(sensor_name, start, end)

    if not series:
        return html.Div(f"No data available for sensor '{sensor_name}' in the selected date range.")

    is_active = get_sensor_by_name(sensor_name).is_online

    graphs = []
    for parameter, values in series.items():
        graph = dcc.Graph(
            id={"type": "sensor-graph", "parameter": parameter},
            figure=build_figure(sensor_name, parameter, values, radio, thin=year_view, show_live=is_active),
            config={
                "responsive": True,
                'displayModeBar': False,
                'displaylogo': False
            },
        )
        graphs.append(dbc.Col(graph, xs=12, sm=12, md=12, lg=12))
    return graphs


@callback(
    Output({"type": "sensor-graph", "parameter": MATCH}, "figure"),
    Input({"type": "sensor-graph", "parameter": MATCH}, "relayoutData"),
    [State("date-range-radio", "value"),
     State("historic-date-slider", "value"),
     State("sensor-name-store", "data"),
     State("selected-deployment-store", "data")],
    prevent_initial_call=True
)
def reload_year_graph_on_zoom(relayout, radio, slider, sensor_name, deploy_data):
    if not relayout or not is_year_view(radio, deploy_data):
        raise PreventUpdate

    parameter = ctx.triggered_id["parameter"]

    if relayout.get("xaxis.autorange"):  # Double click: back to the whole year
        start, end = graph_window(radio, slider, deploy_data)
        series = load_series(sensor_name, start, end, parameter)
        show_live = get_sensor_by_name(sensor_name).is_online
    elif "xaxis.range[0]" in relayout:
        # The axis shows the sensor's local time
        start = parse_date(relayout["xaxis.range[0]"])
        end = parse_date(relayout["xaxis.range[1]"])
        series = load_series(sensor_name, start, end, parameter, localize_input=True)
        show_live = False  # The last point on screen may be months old
    else:
        raise PreventUpdate

    if parameter not in series:
        raise PreventUpdate

    return build_figure(sensor_name, parameter, series[parameter], radio, thin=True, show_live=show_live)

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
            data = get_data(sensor_name, start_date, end_date, lora=False, localize_input=True,
                            include_failed=True)
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
     Output("battery-value", "children"),
     Output("battery-gauge", "color"),
     Output("rssi-progress", "value"),
     Output("rssi-value", "children"),
     Output("rssi-progress", "color"),
     Output("snr-progress", "value"),
     Output("snr-value", "children"),
     Output("snr-progress", "color"),
     Output("board-temp-value", "children"),
     Output("board-temp-container", "style")],
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
    board_temperature = readings.get('board_temperature')

    # Handle missing data
    if battery is None:
        battery_label = "No battery data available"
        battery_color = "secondary"
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

    # Not every device reports this, so the row only appears when there is a value
    if board_temperature is None:
        board_temp_label = ""
        board_temp_style = {"display": "none"}
    else:
        board_temp_label = f"{board_temperature:.1f} \u00B0C"
        board_temp_style = {"display": "block"}

    # Return updated values, labels, and colors
    return (
        battery if battery is not None else BATTERY_MIN_V, battery_label, battery_color,
        rssi_transformed if rssi is not None else 0, rssi_label, rssi_color,
        snr_transformed if snr is not None else 0, snr_label, snr_color,
        board_temp_label, board_temp_style,
    )

# ----------------------------
# History Offcanvas
# ----------------------------
@callback(
    Output("history-offcanvas", "is_open"),
    Input("history-button", "n_clicks"),
    [State("history-offcanvas", "is_open")],
)
def toggle_history_offcanvas(n_clicks, is_open):
    if n_clicks:
        return not is_open
    return is_open

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
    Input("live-sensor-data", "data"),
     Input("selected-deployment-store", "data")]
)
def update_summary_from_url(sensor_name, live_data, deploy_data):
    # Format Title
    title_name = sensor_name + " " + "Information"
    title_name = title_name.title()

    title = html.Div(
        title_name,
        style={
            "text-align": "center",
            "font-weight": "bold"
        },
    )

    if not sensor_name:
        return "No Sensor Found", html.P("No sensor data was found.", className="text-warning")

    # Past Deployment
    if deploy_data and not deploy_data.get('is_current', False):

        stats = get_deployment_statistics(sensor_name, deploy_data)

        if "error" in stats:
            return title, html.P(stats["error"], className="text-danger text-center small")

        location = f"{stats['latitude']}\u00B0N   {stats['longitude']}\u00B0W"
        stat_rows = []

        if stats["averages"]:
            for avg in stats["averages"]:
                formatted_unit = f"({avg['unit']})" if avg.get('unit') else ""
                display_name = f"Avg {avg['parameter'].replace('_', ' ').title()} {formatted_unit}"

                # Matches the Live View format exactly could refactor this later
                stat_rows.append(
                    dbc.Row(
                        [
                            dbc.Col(html.Div(display_name, style={'text-align': 'left', 'font-size': '14px'}), width=9),
                            dbc.Col(html.Div(f"{round(avg['value'], display_decimals(avg['parameter']))}",
                                             style={'text-align': 'right', 'font-size': '14px'}), width=3),
                        ]
                    )
                )
        else:
            stat_rows = [html.P("No data available for this period.", className="text-warning text-center small")]

        parameter_list = html.Div(
            stat_rows,
            style={"list-style-type": "none", "padding": "0", "margin": "0"}
        )

        content = html.Div(
            [
                html.Div("Archived View", className="badge bg-warning text-dark mb-2 d-table mx-auto"),
                html.Div(
                    f"{stats['range']} ({stats['duration']})",
                    style={"text-align": "center", "font-weight": "bold"},
                ),
                html.Div(
                    location,
                    style={"text-align": "center", "font-size": "14px", "margin-bottom": "10px"}
                ),
                parameter_list,
            ]
        )
        return title, content

    summary = get_measurement_summary(sensor_name)

    if "error" in summary:
        return sensor_name, html.P(summary["error"], className="text-danger")

    # Format location
    latitude = str(summary['latitude']) + u'\N{DEGREE SIGN}' + 'N'
    longitude = str(summary['longitude']) + u'\N{DEGREE SIGN}' + 'W'
    location = latitude + "   " + longitude

    if "message" in summary:
        content = html.Div(
            [
                html.Div(
                    location,
                    style={
                        "text-align": "center",
                        "font-size": "14px",
                        "margin-bottom": "10px",
                    }
                ),
                html.P(summary["message"], className="text-info")
            ]
        )
        return title, content

    # Prepare content dynamically based on the most recent measurements
    recent_measurements = summary.get("most_recent_measurements", [])

    if not recent_measurements:
        html.Div(
            location,
            style={
                "text-align": "center",
                "font-size": "14px",
                "margin-bottom": "10px",
            }
        ),
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


    # Format the content with parameters and values
    parameter_list = html.Div(
        [
            dbc.Row(
                [
                    dbc.Col(html.Div(measurement['parameter'].replace("_", " "), style={'text-align': 'left', 'font-size': '14px'}), width=9),
                    dbc.Col(html.Div(f"{round(measurement['value'], display_decimals(measurement['parameter']))}", style={'text-align': 'right', 'font-size': '14px'}), width=3),
                ]
            )
            for measurement in recent_measurements
        ],
        style={"list-style-type": "none", "padding": "0", "margin": "0"}
    )

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

# ----------------------------
# Past Locations
# ----------------------------
@callback(
    [Output("date-range-radio", "style"),
     Output("historic-controls-container", "style"),
     Output("historic-date-slider", "min"),
     Output("historic-date-slider", "max"),
     Output("historic-date-slider", "marks"),
     Output("historic-date-slider", "value"),
     Output("historic-date-slider", "tooltip")],
    Input("selected-deployment-store", "data")
)
def toggle_controls(deploy_data):
    # Default Tooltip Config (Hidden)
    hidden_tooltip = {"always_visible": False}

    if not deploy_data or deploy_data.get('is_current', False):
        return {"display": "inline-flex"}, {"display": "none"}, 0, 100, {}, [0, 100], hidden_tooltip

    start = parse_date(deploy_data['start_iso'])
    end = parse_date(deploy_data['end_iso']) if deploy_data.get('end_iso') else datetime.utcnow()

    min_ts, max_ts = int(start.timestamp()), int(end.timestamp())

    marks = {
        min_ts: {"label": start.strftime("%b %d"), "style": {"transform": "translate(0, 5px)", "whiteSpace": "nowrap"}},
        max_ts: {"label": end.strftime("%b %d"),
                 "style": {"transform": "translate(-100%, 5px)", "whiteSpace": "nowrap"}}
    }

    # Return everything, ensuring tooltip remains hidden
    return {"display": "none"}, {"display": "block"}, min_ts, max_ts, marks, [min_ts, max_ts], hidden_tooltip

@callback(
    Output("slider-date-label", "children"),
    [Input("historic-date-slider", "value"),
     Input("historic-date-slider", "drag_value")]
)
def update_slider_label(value, drag_value):
    current = drag_value if drag_value else value

    if not current or len(current) < 2: return "Loading..."

    start = datetime.fromtimestamp(current[0])
    end = datetime.fromtimestamp(current[1])

    return f"{start.strftime('%b %d, %Y')} — {end.strftime('%b %d, %Y')}"

@callback(
    [Output("selected-deployment-store", "data"),
     Output("history-offcanvas", "is_open", allow_duplicate=True)],
    Input({"type": "deployment-item", "index": ALL}, "n_clicks"),
    State("sensor-name-store", "data"),
    prevent_initial_call=True
)
def select_deployment(clicks, sensor_name):
    trigger = ctx.triggered_id
    if not trigger or not isinstance(trigger, dict):
        raise PreventUpdate

    index = trigger['index']
    deployments = get_past_deployments(sensor_name)
    if index < len(deployments):
        return deployments[index], False
    return no_update, no_update

@callback(
    Output("history-list-content", "children"),
    Input("sensor-name-store", "data")
)
def update_history_list(sensor_name):
    if not sensor_name: return []
    deployments = get_past_deployments(sensor_name)

    return [
        dbc.ListGroupItem([
            html.Div([
                html.Strong("Current Deployment" if d['is_current'] else d['range'], className="small"),
                html.Span(d['duration'],
                          className=f"badge {'bg-success' if d['is_current'] else 'bg-light text-dark'} ms-2")
            ], className="d-flex justify-content-between"),
            html.Small(f"Lat: {d['latitude']:.4f}, Lon: {d['longitude']:.4f}", className="text-muted d-block")
        ], action=True, id={"type": "deployment-item", "index": i})
        for i, d in enumerate(deployments)
    ]

#-----------------
# MAP UPDATE
#-----------------
def map_viewport(center, zoom):
    # The map only reads its center and zoom props once, when it is first created.
    return {"center": center, "zoom": zoom, "transition": "flyTo"}


@callback(
    [Output("map-markers", "children", allow_duplicate=True),
     Output("dashboard-map", "viewport")],
    [Input("selected-deployment-store", "data"),
     Input("sensor-name-store", "data")],
    prevent_initial_call=True
)
def update_map_view(deploy_data, sensor_name):

    if not sensor_name:
        raise PreventUpdate

    if not deploy_data or deploy_data.get('is_current', True):
        markers, map_center, map_zoom = create_map_markers(sensor_name)
        return markers, map_viewport(map_center, map_zoom)

    # Historic mode
    lat = deploy_data.get('latitude')
    lon = deploy_data.get('longitude')

    if lat is None or lon is None:
        return no_update, no_update

    sensor = get_sensor_by_name(sensor_name)
    s_type = sensor.device_type if sensor else None

    if s_type == "tide_gauge":
        icon_file = "/assets/tide_gauge.svg"
    elif s_type == "wave_gauge":
        icon_file = "/assets/wave_gauge.svg"
    else:
        icon_file = "/assets/buoy.svg"

    icon_opts = {
        "iconUrl": icon_file,
        "iconSize": [60, 60],
        "iconAnchor": [30, 30],
        "popupAnchor": [0, -30],
        "className": "inactive-marker"
    }

    historic_marker = [dl.Marker(
        position=[lat, lon],
        title=f"Historic: {sensor_name}",
        icon=icon_opts
    )]

    return historic_marker, map_viewport([lat, lon], 12)