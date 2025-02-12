from dash.dependencies import Input, Output, State
from dash.exceptions import PreventUpdate
import dash
import dash_bootstrap_components as dbc
import plotly.graph_objs as go
from server.models import (query_data,
                           save_data_to_csv,
                           get_measurement_summary,
                           query_most_recent_lora,
                           query_lora_data,
                           create_or_update_sensor,
                           get_sensors_grouped_by_type,
                           get_all_sensors,
                           get_sensor_by_name,
                           get_parameters,
                           update_sensor_parameters,
                           update_sensor_data,
                           delete_unused_parameters,
                           User
                           )
from dash import no_update, dcc, html, callback_context, ALL
from dateutil.parser import parse as parse_date
from urllib.parse import urlparse, parse_qs
import os
import time
from datetime import datetime, timedelta
import pytz
import base64
from flask import session

def register_callbacks(app):
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
        Output('multi-sensor-graph', 'children'),
        [
            Input("date-range-radio", "value"),
            Input("sensor-name-store", "data")
        ]
    )
    def update_multi_sensor_graph(date_range_value, sensor_name):
        cst = pytz.timezone('America/Chicago')
        cst_today = datetime.now(cst).replace(tzinfo=None)
        start_date = cst_today - timedelta(days=2)

        # Determine start date based on selected radio option
        if date_range_value == "2-days":
            start_date = cst_today - timedelta(days=2)
        elif date_range_value == "1-week":
            start_date = cst_today - timedelta(weeks=1)
        elif date_range_value == "1-month":
            start_date = cst_today - timedelta(weeks=4)
        elif date_range_value == "1-year":
            start_date = cst_today - timedelta(days=365)

        # Query data with units
        data = query_data(start_date, cst_today, sensor_name, include_units=True)

        if not data:
            return html.Div(f"No data available for sensor '{sensor_name}' in the selected date range.")

        # Process data
        parameter_data = {}
        parameter_units = {}
        for row in data:
            timestamp, value, parameter_name, unit = row.timestamp, row.value, row.name, row.unit

            if parameter_name not in parameter_data:
                parameter_data[parameter_name] = {"timestamps": [], "values": []}
                parameter_units[parameter_name] = unit
            parameter_data[parameter_name]["timestamps"].append(timestamp)
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

            graph = dcc.Graph(
                figure={
                    "data": [
                        go.Scatter(
                            x=values["timestamps"],
                            y=values["values"],
                            mode="lines+markers",
                            name=parameter
                        )
                    ],
                    "layout": go.Layout(
                        xaxis={"tickangle": -45},
                        yaxis={
                            "title": f"{parameter.replace('_', ' ').capitalize()} ({unit})",
                            "range": [min_y - y_padding, max_y + y_padding]
                        },
                        margin={"l": 50, "r": 40, "t": 40, "b": 80},
                        font={"size": 12},
                        height=300
                    )
                },
                config={
                    "responsive": True,
                    'displayModeBar': False,
                    'displaylogo': False
                },
            )
            graphs.append(dbc.Col(graph, xs=12, sm=12, md=12, lg=12))
        time.sleep(2)
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
            #Convert dates from string to date_time object and set hr/min/sec to get the full days
            start_date = parse_date(start_date).replace(hour=0, minute=0, second=0)
            end_date = parse_date(end_date).replace(hour=23, minute=59, second=59)

            if not start_date or not end_date:
                return True, 'Please provide a valid date range and filename.', None
            if not filename:
                return True, 'Please provide a valid filename.', None

            if data_type == "   Sensor Data":
                data = query_data(start_date, end_date, sensor_name, include_units=True)
            else:
                data = query_lora_data(start_date, end_date, sensor_name, include_units=True)

            if not data:
                return True, 'No data found for the given date range.', None

            saved_csv_file = save_data_to_csv(data, sensor_name)
            return False, '', dict(content=saved_csv_file, filename=f"{filename}.csv")
        return False, '', None

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
        [Output("card-title", "children"),
         Output("summary-content", "children")],
        Input("sensor-name-store", "data"),
    )
    def update_summary_from_url(sensor_name):
        if not sensor_name:
            return "No Sensor Found", html.P("No sensor data was found.", className="text-warning")

        # Fetch summary information for the sensor
        summary = get_measurement_summary(sensor_name)

        if "error" in summary:
            return sensor_name, html.P(summary["error"], className="text-danger")

        # Prepare content dynamically based on the most recent measurements
        recent_measurements = summary.get("most_recent_measurements", [])

        timestamp = recent_measurements[0]["timestamp"].strftime("%a %b %d, %H:%M")

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
                    timestamp,
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
        image_path = f"dash_app/assets/{sensor_name}.png"
        if os.path.exists(os.path.join(os.getcwd(), image_path)):
            return f"/assets/{sensor_name}.png"  # Return the relative path for Dash to render
        else:
            return "/assets/no_image_available.png"

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
        [Input("sensor-name-store", "data")]
    )
    def update_sensor_health(sensor_name):

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
        if session.get('user_logged_in'): #Check if the user is already logged in
            return "", {"display": "none"}, {"display": "block"}
        if n_clicks:
            user = User.authenticate(username, password)

            if user:  # If the user is authenticated
                session['user_logged_in'] = True
                return "", {"display": "none"}, {"display": "block"}

            return "Invalid credentials. Please try again.", {}, {"display": "none"}

        return "", {}, {"display": "none"}  # Initial state if no clicks

    @app.callback(
        Output("submission-response", "children"),
        Input("submit-btn", "n_clicks"),
        [
            State("device-name", "value"),
            State("latitude", "value"),
            State("longitude", "value"),
            State("device-type", "value"),
            State("device-image", "contents"),
        ],
    )
    def submit_onboarding_form(n_clicks, device_name, latitude, longitude, device_type, image_data):
        if n_clicks:
            # Validate required fields
            if not all([device_name, latitude, longitude, device_type]):
                return dbc.Alert("Device name, latitude, longitude, and device type fields are required!", color="danger")

            # Define the base path for uploads
            upload_directory = os.path.join(os.getcwd(), "dash_app/assets")

            message = create_or_update_sensor(
                device_name=device_name,
                latitude=latitude,
                longitude=longitude,
                device_type=device_type,
                image_data=image_data,
                base_path=upload_directory
            )

            # Check if the operation was successful
            if "successfully" in message.lower():
                return dbc.Alert(message, color="success")
            else:
                return dbc.Alert(message, color="danger")

        return ""

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
        Input("update-submit-btn", "n_clicks"),
        [
            State("select-device-dropdown", "value"),
            State("update-device-name", "value"),
            State("update-latitude", "value"),
            State("update-longitude", "value"),
            State("update-device-type", "value"),
            State("update-device-image", "contents"),
            State({"type": "parameter-input", "index": ALL}, "value"),  # Capture all dynamic inputs
            State({"type": "parameter-input", "index": ALL}, "id"),  # Capture all IDs of inputs
        ]
    )
    def update_sensor_information(n_clicks, selected_device, device_name, latitude, longitude, device_type, image_data,
                                  param_units, param_ids):
        if not n_clicks:
            return ""

        if not all([device_name, latitude, longitude, device_type]):
            return dbc.Alert("Device name, latitude, longitude, and device type fields are required!", color="danger")

        # Debugging: Inspect captured IDs and values
        print("Captured IDs:", param_ids)
        print("Captured Values:", param_units)

        # Pair parameter names with their corresponding units
        updated_parameters = [
            (param_id["index"], param_unit)
            for param_id, param_unit in zip(param_ids, param_units)
            if param_unit is not None
        ]

        # Debugging: Inspect updated parameters
        print("Updated Parameters:", updated_parameters)

        if not updated_parameters:
            return dbc.Alert("No parameter units provided!", color="danger")

        # Get the existing sensor by name
        sensor = get_sensor_by_name(selected_device)
        if not sensor:
            return dbc.Alert(f"Sensor '{selected_device}' not found.", color="danger")

        # Update sensor parameters
        try:
            update_sensor_parameters(sensor, updated_parameters)
            update_sensor_data(sensor, updated_parameters)
        except Exception as e:
            return dbc.Alert(f"Error updating sensor parameters: {str(e)}", color="danger")

        #delete_unused_parameters()

        return dbc.Alert("Sensor information updated successfully!", color="success")