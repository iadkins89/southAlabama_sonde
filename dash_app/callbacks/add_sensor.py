from dash import callback, Input, Output, State, html, no_update
import dash_bootstrap_components as dbc
from server.models import create_or_update_sensor, get_sensor_by_name
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
    ],
)
def submit_onboarding_form(n_clicks, device_name, latitude, longitude, timezone, device_type, image_data):
    if n_clicks:
        # Validate required fields
        if not all([device_name, latitude, longitude, device_type]):
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
            user_id = current_user_id
        )

        # Check if the operation was successful
        if "successfully" in message.lower():
            return dbc.Alert(message, color="success"), {"timestamp": time.time()}
            # Output time of sensor-update to make sure other components triggered correctly
        else:
            return dbc.Alert(message, color="danger"), no_update

    return "", no_update

@callback(
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
