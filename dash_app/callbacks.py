from dash.dependencies import ClientsideFunction, Input, Output, State
from dash.exceptions import PreventUpdate
import dash
import dash_bootstrap_components as dbc
import plotly.graph_objs as go
from server.models import (query_data,
                           save_data_to_csv,
                           get_measurement_summary,
                           query_most_recent_lora,
                           create_or_update_sensor,
                           get_sensors_grouped_by_type,
                           get_all_sensors,
                           get_sensor_by_name,
                           get_sensor_timezone,
                           get_parameters,
                    # These are deprecated but kept for import safety
                           update_sensor_parameters,
                           update_sensor_data,
                           delete_unused_parameters,
                           )
from dash import no_update, dcc, html, callback_context, ALL
from dateutil.parser import parse as parse_date
from urllib.parse import urlencode
import os
import time
from datetime import datetime, timedelta
import pytz
import base64
from flask import session

USERNAME = 'admin'
PASSWORD = 'admin'

def get_sensors_grouped_by_type():
    sensors = get_all_sensors()
    grouped = {}
    for s in sensors:
        d_type = s.get('device_type', 'Unknown')
        if d_type not in grouped:
            grouped[d_type] = []
        grouped[d_type].append(s['name'])
    return grouped

def register_callbacks(app):

    app.clientside_callback(
        ClientsideFunction(
            namespace="clientside",
            function_name="update_store"
        ),
        Output("live-sensor-data", "data"),
        Input("ws-trigger", "children")
    )
    @app.callback(
        Output("navbar-collapse", "is_open"),
        [
            Input("navbar-toggler", "n_clicks"),
             Input("home-link", "n_clicks"),
             Input("onboarding-link", "n_clicks"),
             Input("about-link", "n_clicks"),
             Input({"type": "sensor-item", "index": dash.ALL}, "n_clicks")
         ],
        State("navbar-collapse", "is_open"),
    )
    def toggle_navbar(n_clicks, home_click, onboard_click, about_click, sensor_clicks, is_open):
        if any([n_clicks, home_click, onboard_click, about_click]) or any(sensor_clicks):
            return not is_open
        return is_open

    @app.callback(
        Output("sensors-dropdown", "children"),
        Input("navbar-state", "data")
    )
    def populate_sensors_dropdown(data):
        """
        Populate the sensors dropdown dynamically by querying the database.
        """
        # Retrieve sensors grouped by type
        sensors_grouped = get_sensors_grouped_by_type()

        dropdown_items = []
        for device_type, sensors in sensors_grouped.items():
            # Add section header for each device type
            dropdown_items.append(
                html.H6(
                    device_type.replace("_", " ").capitalize(),
                    style={"fontWeight": "bold", "padding": "5px 10px"}  # Add bold styling and padding
                )
            )

            # Add each sensor under the device type
            for sensor_name in sensors:
                dropdown_items.append(
                    dbc.DropdownMenuItem(
                        sensor_name,
                        href=f"/dashboard?name={sensor_name}",
                        id={"type": "sensor-item", "index": sensor_name}
                    )
                )

            # Add a divider between sections
            dropdown_items.append(dbc.DropdownMenuItem(divider=True))

        # Remove the last divider if present
        if dropdown_items and isinstance(dropdown_items[-1], dbc.DropdownMenuItem) and dropdown_items[-1].divider:
           dropdown_items.pop()

        # Fallback if no sensors are found
        if not dropdown_items:
            dropdown_items = [dbc.DropdownMenuItem("No sensors available", disabled=True)]

        return dropdown_items

    @app.callback(
    Output('home-url', 'href'),
    Input('map-graph', 'clickData')
    )
    def home_redirect_on_click(clickData):
        if clickData:
            sensor_name = clickData['points'][0]['text']

            # Generate the URL with query string
            return f"/dashboard?name={sensor_name}"
        return no_update

    # Callback to handle marker click and redirect
    @app.callback(
        [Output('url', 'href'), Output('sensor-name-store', 'data')],
        Input('map-graph', 'clickData'),
        prevent_initial_call=True
    )
    def redirect_on_click(clickData):
        if clickData:
            sensor_name = clickData['points'][0]['text']

            # Generate the URL with query string
            return f"/dashboard?name={sensor_name}", sensor_name
        return no_update, no_update

    @app.callback(
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
        data = query_data(sensor_name, start, now, lora=False)

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
                    x=[last_time], y=[last_val], mode="markers",
                    marker={"color": "#dc3545", "size": 12, "line": {"width": 2, "color": "white"}},
                    hoverinfo="skip"  # Skip this too! The Line tooltip already covers this point.
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

    @app.callback(
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
    def update_output(n_clicks, sensor_name, start_date, end_date, filename, data_type):
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
                data = query_data(sensor_name, start_date, end_date, lora=False, localize_input=True)
            else:
                data = query_data(sensor_name,start_date, end_date, lora=True, localize_input=True)

            if not data:
                return True, 'No data found for the given date range.', None

            saved_csv_file = save_data_to_csv(data, sensor_name)
            return False, '', dict(content=saved_csv_file, filename=f"{filename}.csv")
        return False, '', None

    @app.callback(
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
    @app.callback(
        Output("download-data-offcanvas", "is_open"),
        Input("download-button", "n_clicks"),
        [State("download-data-offcanvas", "is_open")],
    )
    def toggle_download_data_offcanvas(n_clicks, is_open):
        if n_clicks:
            return not is_open
        return is_open

    @app.callback(
        Output("sensor-health-offcanvas", "is_open"),
        Input("sensor-health-button", "n_clicks"),
        [State("sensor-health-offcanvas", "is_open")],
    )
    def toggle_sensor_health_offcanvas(n_clicks, is_open):
        if n_clicks:
            return not is_open
        return is_open

    @app.callback(
        Output("sensor-image", "src"),
        Input("sensor-name-store", "data"),
    )
    def get_sensor_pic(sensor_name):
        if not sensor_name:
            return "/assets/default_sensor.png"

        sensor = get_sensor_by_name(sensor_name)

        # Logic: If DB has image_data, use it. Else, default.
        if sensor and sensor.image_data:
            image_src = sensor.image_data
        else:
            image_src = "/assets/default_sensor.png"

        return image_src

    @app.callback(
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

        # Query data
        data = query_most_recent_lora(sensor_name)

        # Initialize values
        battery = None
        rssi = None
        snr = None

        for entry in data:
            if entry[0] == 'battery':
                battery = entry[2]
            if entry[0] == 'rssi':
                rssi = entry[2]
            if entry[0] == 'snr':
                snr = entry[2]

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

    @app.callback(
        [Output("login-error", "children"),
         Output("login-form", "style"),
         Output("menu", "style")],
        Input("login-btn", "n_clicks"),
        [State("username", "value"), State("password", "value")],
    )
    def login_user(n_clicks, username, password):
        if session['user_logged_in']:
            return "", {"display": "none"}, {"display": "block"}
        if n_clicks:
            if username == USERNAME and password == PASSWORD:
                session['user_logged_in'] = True
                return "", {"display": "none"}, {"display": "block"}
            return "Invalid credentials. Please try again.", {}, {"display": "none"}
        return "", {}, {"display": "none"}


    @app.callback(
        Output("submission-response", "children"),
        Input("submit-btn", "n_clicks"),
        [
            State("device-name", "value"),
            State("latitude", "value"),
            State("longitude", "value"),
            State("timezone", "value"),
            State("device-type", "value"),
            State("device-image", "contents"),
        ],
    )
    def submit_onboarding_form(n_clicks, device_name, latitude, longitude, timezone, device_type, image_data):
        if n_clicks:
            # Validate required fields
            if not all([device_name, latitude, longitude, device_type]):
                return dbc.Alert("Device name, latitude, longitude, and device type fields are required!", color="danger")

            message = create_or_update_sensor(
                name=device_name,
                latitude=latitude,
                longitude=longitude,
                device_type=device_type,
                image_data=image_data,
                timezone = timezone,
                active = True
            )

            # Check if the operation was successful
            if "successfully" in message.lower():
                return dbc.Alert(message, color="success")
            else:
                return dbc.Alert(message, color="danger")

        return ""

    @app.callback(
        [Output("device-image", "children"),
         Output("device-image", "style")],
        [Input("device-image", "contents")]
    )
    def show_add_sensor_preview(image_data):
        # Default Style (Small box with text)
        default_style = {
            "width": "100%", "height": "80px", "lineHeight": "80px",
            "borderWidth": "1px", "borderStyle": "dashed",
            "borderRadius": "5px", "textAlign": "center", "margin": "10px",
        }

        if not image_data:
            # Show default text
            default_content = html.Div(["Drag and Drop or ", html.A("Select an Image File")])
            return default_content, default_style

        # Image Style (Bigger box containing the image)
        image_style = {
            "width": "100%", "height": "300px",  # Made taller to fit image
            "borderWidth": "1px", "borderStyle": "solid",
            "borderRadius": "5px", "textAlign": "center", "margin": "10px",
            "display": "flex", "alignItems": "center", "justifyContent": "center",
            "overflow": "hidden"
        }

        # Return the actual image tag inside the upload box
        image_content = html.Img(src=image_data, style={"maxHeight": "100%", "maxWidth": "100%"})

        return image_content, image_style

    @app.callback(
        Output("form-container", "style"),
        [Input("select-device-dropdown", "value")]
    )
    def show_form_on_device_select(selected_device):
        if selected_device:
            return {"display": "block"}  # Show the form
        return {"display": "none"}  # Hide the form if no device is selected

    @app.callback(
        [Output("update-device-name", "value"),
         Output("update-latitude", "value"),
         Output("update-longitude", "value"),
         Output("update-device-type", "value")],
        [Input("select-device-dropdown", "value")]
    )
    def populate_form_with_device_info(selected_device):
        if selected_device:
            # Get the sensor details from the database
            sensor = get_sensor_by_name(selected_device)

            return sensor.name, sensor.latitude, sensor.longitude, sensor.device_type
        return "", "", "", ""

    @app.callback(
        Output("parameters-container", "children"),
        Input("select-device-dropdown", "value")
    )
    def populate_form_with_parameters_info(selected_device):
        if not selected_device:
            return []

        parameters = get_parameters(selected_device)
        if "error" in parameters:
            return html.P(parameters["error"], className="text-danger")

        remove = ['battery', 'rssi', 'snr']
        filtered_parameters = [param for param in parameters if param[0] not in remove]

        rows = [
            dbc.Row([
                # Adjusting the label's width for different screen sizes
                dbc.Col(html.Label(param[0], className="text-start"), width=12, sm=4, md=3),
                # Full width on mobile, smaller width on larger screens
                dbc.Col(
                    dbc.Input(
                        id={"type": "parameter-input", "index": param[0]},  # Assign unique ID
                        placeholder=param[1],
                        size="sm",
                        style={"maxWidth": "13%"}  # Ensure the input takes full width on mobile
                    ), width=12, sm=8, md=9, lg=8  # Full width on small screens, adjusted for larger screens
                ),
            ], className="mb-2") for param in filtered_parameters
        ]

        return rows

    @app.callback(
        Output("update-submission-response", "children"),
        [Input("update-submit-btn", "n_clicks"),
         Input("deactivate-btn", "n_clicks")],  # Matches id in update-sensor.py
        [State("select-device-dropdown", "value"),
         State("update-device-name", "value"),
         State("update-latitude", "value"),
         State("update-longitude", "value"),
         State("update-device-type", "value"),
         State("update-device-image", "contents")]  # Matches id in update-sensor.py
    )
    def update_sensor_information(submit_clicks, deactivate_clicks, original_name, new_name, lat, lon, dtype,
                                  image_data):
        # Determine which button was clicked
        ctx = callback_context
        if not ctx.triggered: return ""

        button_id = ctx.triggered[0]['prop_id'].split('.')[0]

        if button_id == "deactivate-btn":
            # Soft Delete: Set active=False, ignore image data
            msg = create_or_update_sensor(original_name, lat, lon, dtype, image_data=None, active=False)
            return dbc.Alert(f"Sensor '{original_name}' deactivated.", color="warning")

        elif button_id == "update-submit-btn":
            # Normal Update: Set active=True
            msg = create_or_update_sensor(new_name, lat, lon, dtype, image_data, active=True)
            return dbc.Alert(msg, color="success")

        return ""


