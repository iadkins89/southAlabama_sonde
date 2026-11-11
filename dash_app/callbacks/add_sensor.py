from dash import callback, Input, Output, State, dcc, html, no_update
import dash_bootstrap_components as dbc
from server.models import create_or_update_sensor, get_sensor_by_name
from server.utils import upload_preview
import time
from flask import session

@callback(
    [
        Output("submission-response", "children"),
        Output("sensor-update", "data")
     ],
    Input("submit-btn", "n_clicks"),
    [
        State("device-name", "value"),
        State("latitude", "value"),
        State("longitude", "value"),
        State("timezone", "value"),
        State("device-type", "value"),
        State("device-image", "contents"),
        State("gauge-elevation", "value"),
        State("add-testing-switch", "value"),
    ],
)
def submit_onboarding_form(n_clicks, device_name, latitude, longitude, timezone, device_type, image_data,
                           gauge_elevation, testing):
    if n_clicks:
        # The page checks the login too, but this callback can be called directly
        if not session.get('user_logged_in'):
            return dbc.Alert("Please log in again.", color="danger"), no_update

        # Validate required fields
        if testing:
            if not all([device_name, device_type]):
                return dbc.Alert("Device name and device type are required!", color="danger"), no_update
        elif not all([device_name, latitude is not None, longitude is not None, device_type]):
            return dbc.Alert("Device name, latitude, longitude, and device type fields are required!", color="danger"), no_update

        existing_sensor = get_sensor_by_name(device_name)
        if existing_sensor:
            return dbc.Alert(
                f"Sensor with name '{device_name}' already exists. Please use another name or update the existing sensor.",
                color="warning"), no_update

        current_user_id = session.get('user_id')

        message = create_or_update_sensor(
            name=device_name,
            latitude=latitude,
            longitude=longitude,
            device_type=device_type,
            image_data=image_data,
            timezone=timezone,
            active=True,
            user_id = current_user_id,
            navd88_elevation=gauge_elevation if device_type == "tide_gauge" else None,
            testing=bool(testing)
        )

        if "successfully" in message.lower():
            if testing:
                message = [message + " It is in test mode, under ",
                           dcc.Link("Test Devices", href="/onboarding/test-devices"), "."]
            return dbc.Alert(message, color="success"), {"timestamp": time.time()}
            # Output time of sensor-update to make sure other components triggered correctly
        else:
            return dbc.Alert(message, color="danger"), no_update

    return "", no_update

@callback(
    [Output("add-location-rows", "style"),
     Output("gauge-elevation-test-hint", "style")],
    Input("add-testing-switch", "value")
)
def toggle_location_fields(testing):
    return ({"display": "none"} if testing else {}), ({} if testing else {"display": "none"})


@callback(
    Output("gauge-elevation-row", "style"),
    Input("device-type", "value")
)
def toggle_gauge_elevation_field(device_type):
    if device_type == "tide_gauge":
        return {"display": "block"}
    return {"display": "none"}

@callback(
    [Output("device-image", "children"),
     Output("device-image", "style")],
    [Input("device-image", "contents")]
)
def show_add_sensor_preview(image_data):
    return upload_preview(image_data)
