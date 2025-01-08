from dash.dependencies import Input, Output, State
from dash.exceptions import PreventUpdate
import dash_bootstrap_components as dbc
import plotly.graph_objs as go
from server.models import query_data, save_data_to_csv, get_measurement_summary, query_most_recent_lora, query_lora_data, create_or_update_sensor
from dash import no_update, dcc, html
from urllib.parse import urlparse, parse_qs
import os
import base64

USERNAME = 'admin'
PASSWORD = 'admin'
def register_callbacks(app):
    @app.callback(
        Output('multi-sensor-graph', 'children'),
        [Input('temp-date-picker-range', 'start_date'),
         Input('temp-date-picker-range', 'end_date'),
        Input("sensor-name-store", "data"),]
    )
    def update_multi_sensor_graph(start_date, end_date, sensor_name):

        # Query data
        data = query_data(start_date, end_date, sensor_name)
        if not data:
            return html.Div(f"No data available for sensor '{sensor_name}' in the selected date range.")

        # Process data into a dictionary grouped by parameter
        parameter_data = {}
        for row in data:
            timestamp = row.timestamp
            value = row.value
            parameter_name = row.name

            if parameter_name not in parameter_data:
                parameter_data[parameter_name] = {"timestamps": [], "values": []}
            parameter_data[parameter_name]["timestamps"].append(timestamp)
            parameter_data[parameter_name]["values"].append(value)

        # Generate graphs dynamically
        graphs = []
        for parameter, values in parameter_data.items():
            min_y = min(values["values"])
            max_y = max(values["values"])
            y_padding = (max_y - min_y) * 0.2

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
                        #title=f"{parameter} vs Time",
                        xaxis={"title": "Time", "tickangle": -45},
                        yaxis={
                            "title": parameter,
                            "range": [min_y - y_padding, max_y + y_padding]  # Apply padding to y-axis
                        },
                        margin={"l": 40, "r": 40, "t": 40, "b": 80},
                        font={"size": 12},
                        height=200
                    )
                }
            )
            graphs.append(graph)

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
            if not start_date or not end_date:
                return True, 'Please provide a valid date range and filename.', None
            if not filename:
                return True, 'Please provide a valid filename.', None

            if data_type == "   Sensor Data":
                data = query_data(start_date, end_date, sensor_name)
            else:
                data = query_lora_data(start_date, end_date, sensor_name)

            if not data:
                return True, 'No data found for the given date range.', None

            saved_csv_file = save_data_to_csv(data, sensor_name)
            return False, '', dict(content=saved_csv_file, filename=f"{filename}.csv")
        return False, '', None

    # Callback to handle marker click and redirect
    @app.callback(
        Output('url', 'href'),
        Input('map-graph', 'clickData')
    )
    def redirect_on_click(clickData):
        if clickData:
            sensor_name = clickData['points'][0]['text']

            # Generate the URL with query string
            return f"/dashboard?name={sensor_name}"
        return no_update

    @app.callback(
        [Output("card-title", "children"), Output("summary-content", "children")],
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

        # Format the content with parameters and values
        parameter_list = html.Div(
            [
                dbc.Row(
                    [
                        dbc.Col(html.Div(measurement['parameter']), width=6),
                        dbc.Col(html.Div(f"{round(measurement['value'], 1)}"), width=6),
                    ]
                )
                for measurement in recent_measurements
            ],
            style={"list-style-type": "none", "padding": "0", "margin": "0"}  # Remove bullet points and extra spacing
        )

        # Combine the timestamp and parameters
        content = html.Div(
            [
                html.Div(
                    timestamp,
                    style={
                        "text-align": "center",
                        "font-weight": "bold",
                        "margin-bottom": "10px",
                    },
                ),
                parameter_list,
            ]
        )

        return f"{sensor_name} Information", content
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
        [Output("rssi-progress", "value"),
        Output("rssi-progress", "label"),
        Output("rssi-progress", "color"),
        Output("snr-progress", "value"),
        Output("snr-progress", "label"),
        Output("snr-progress", "color"),],
        [Input("sensor-name-store", "data")]
    )
    def update_sensor_health(sensor_name):

        # Query data
        data = query_most_recent_lora(sensor_name)
        if not data:
            return html.Div(f"No data available for sensor '{sensor_name}' in the selected date range.")

        rssi = data.rssi
        snr = data.snr

        # RSSI transformation and thresholds
        rssi_transformed = max(0, min(100, int((rssi + 120) * 100 / 120)))  # Map -120 to 0 dBm -> 0 to 100
        if rssi >= -50:
            rssi_color = "success"  # Good
        elif -80 <= rssi < -50:
            rssi_color = "warning"  # Moderate
        else:
            rssi_color = "danger"  # Poor

        # SNR thresholds
        snr_transformed = max(0, min(100, int((snr + 20) * 100 / 40)))  # Map -20 to 20 dB -> 0 to 100
        if snr > 10:
            snr_color = "success"  # Good
        elif 0 <= snr <= 10:
            snr_color = "warning"  # Moderate
        else:
            snr_color = "danger"  # Poor

        # Return updated values, labels, and colors
        return (
            rssi_transformed, f"{rssi} dBm", rssi_color,
            snr_transformed, f"{snr} dB", snr_color,
        )

    @app.callback(
        [Output("login-error", "children"),
         Output("login-form", "style"), Output("onboarding-form", "style")],
        Input("login-btn", "n_clicks"),
        [State("username", "value"), State("password", "value")],
    )
    def login_user(n_clicks, username, password):
        if n_clicks:
            if username == USERNAME and password == PASSWORD:
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
            upload_directory = os.path.join(os.getcwd(), "assets")  # Replace with your desired directory

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
