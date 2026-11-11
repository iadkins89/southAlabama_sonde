import time

from dash import callback, Input, Output, State, callback_context, no_update
from server.database import db
from server.models import (User, count_sensor_readings, delete_sensor,
                           create_or_update_sensor)
from dash_app.access import managed_sensor, managed_sensors
from server.utils import upload_preview
import dash_bootstrap_components as dbc
from flask import session


def option_label(sensor):
    if sensor['testing']:
        return f"{sensor['name']} (Testing)"
    if not sensor.get('active', True):
        return f"{sensor['name']} (Inactive)"
    return sensor['name']


def sensor_options():
    # Only the sensors this user owns, or every sensor for an admin
    return [{'label': option_label(s), 'value': s['name']} for s in managed_sensors(testing=None)]


@callback(
    Output("select-device-dropdown", "options"),
    Input("main-url", "pathname")
)
def populate_sensor_dropdown(pathname):
    # This fires when the page loads
    return sensor_options()

@callback(
    Output("form-container", "style"),
    [Input("select-device-dropdown", "value")]
)
def show_form_on_device_select(selected_device):
    if selected_device:
        return {"display": "block"}  # Show the form
    return {"display": "none"}  # Hide the form if no device is selected

@callback(
    [Output("update-location-rows", "style"),
     Output("update-testing-note", "style"),
     Output("toggle-active-col", "style")],
    Input("select-device-dropdown", "value")
)
def hide_location_for_test_devices(selected_device):
    sensor = managed_sensor(selected_device)
    if sensor and sensor.testing:
        return {"display": "none"}, {}, {"display": "none"}
    return {}, {"display": "none"}, {}


@callback(
    Output("update-gauge-elevation-row", "style"),
    Input("update-device-type", "value")
)
def toggle_update_gauge_elevation_field(device_type):
    if device_type == "tide_gauge":
        return {"display": "block"}
    return {"display": "none"}

@callback(
    [Output("update-device-image", "children"),
     Output("update-device-image", "style")],
    [Input("update-device-image", "contents"),
     Input("select-device-dropdown", "value")]
)
def show_update_sensor_preview(image_data, selected_device):
    # With no new upload, show the photo the sensor already has
    if not image_data and selected_device:
        sensor = managed_sensor(selected_device)
        image_data = sensor.image_data if sensor else None
    return upload_preview(image_data)

@callback(
    [Output("update-device-name", "value"),
     Output("update-latitude", "value"),
     Output("update-longitude", "value"),
     Output("update-device-type", "value"),
     Output("update-gauge-elevation", "value"),
     Output("sensor-active-status-store", "data"),  # Store the status
     Output("toggle-active-btn", "children"),  # Change button text
     Output("toggle-active-btn", "color"),
     Output("update-device-image", "contents")],  # A photo chosen for one sensor must not carry to the next
    [Input("select-device-dropdown", "value")]
)
def populate_form_with_device_info(selected_device):
    # Get the sensor details from the database
    sensor = managed_sensor(selected_device)
    if sensor:

        btn_text = "Deactivate" if sensor.active else "Reactivate"
        btn_color = "danger" if sensor.active else "success"

        return (sensor.name, sensor.latitude, sensor.longitude, sensor.device_type, sensor.navd88_elevation,
                sensor.active, btn_text, btn_color, None)
    return "", "", "", "", "", "", "", "", None

@callback(
    Output("update-submission-response", "children"),
    [Input("update-submit-btn", "n_clicks"),
     Input("toggle-active-btn", "n_clicks")],
    [State("select-device-dropdown", "value"),
     State("update-device-name", "value"),
     State("update-latitude", "value"),
     State("update-longitude", "value"),
     State("update-device-type", "value"),
     State("update-device-image", "contents"),
     State("update-gauge-elevation", "value"),
     State("sensor-active-status-store", "data")]
)
def update_sensor_information(submit_clicks, deactivate_clicks, original_name, new_name, lat, lon, dtype,
                              image_data, gauge_elevation, is_active):
    # Determine which button was clicked
    ctx = callback_context
    if not ctx.triggered: return ""

    # The page checks the login too, but this callback can be called directly
    if not session.get('user_logged_in'):
        return dbc.Alert("Please log in again.", color="danger")

    button_id = ctx.triggered[0]['prop_id'].split('.')[0]

    sensor_to_update = managed_sensor(original_name)

    if not sensor_to_update:
        return dbc.Alert(f"Error: Could not find sensor '{original_name}' in the database.", color="danger")

    target_id = sensor_to_update.id

    if button_id == "toggle-active-btn":
        new_status = not is_active
        # Pass the current database values to prevent saving unsaved form edits.
        # Decouple this later to not use the create_or_update_sensor function
        # instead create a dedicated function that changes the status and updates
        # history.
        msg = create_or_update_sensor(
            name=sensor_to_update.name,
            latitude=sensor_to_update.latitude,
            longitude=sensor_to_update.longitude,
            device_type=sensor_to_update.device_type,
            image_data=None,
            active=new_status,
            sensor_id=target_id,
            navd88_elevation=sensor_to_update.navd88_elevation
        )

        status_word = "Activated" if new_status else "Deactivated"
        color = "success" if new_status else "warning"
        return dbc.Alert(f"Sensor '{original_name}' {status_word}. (Please refresh page to see update)",
                         color=color)

    elif button_id == "update-submit-btn":
        # Normal Update: Set active=True
        msg = create_or_update_sensor(
            new_name,
            lat,
            lon,
            dtype,
            image_data,
            active=is_active,
            sensor_id=target_id,
            navd88_elevation=gauge_elevation if dtype == "tide_gauge" else None
        )
        return dbc.Alert(msg, color="success")

    return ""


@callback(
    [Output("delete-sensor-modal", "is_open"),
     Output("delete-sensor-warning", "children"),
     Output("delete-sensor-password", "value"),
     Output("delete-sensor-error", "children")],
    [Input("delete-sensor-btn", "n_clicks"),
     Input("delete-cancel-btn", "n_clicks")],
    State("select-device-dropdown", "value"),
    prevent_initial_call=True
)
def open_delete_dialog(open_clicks, cancel_clicks, selected_device):
    sensor = managed_sensor(selected_device)
    if callback_context.triggered_id != "delete-sensor-btn" or not sensor:
        return False, no_update, "", ""

    readings = count_sensor_readings(sensor.id)
    return (True,
            f"This permanently deletes {sensor.name} and its {readings:,} stored values. This can't be undone.",
            "", "")


def delete_error(selected_device, password):
    """Returns why the sensor can't be deleted, or None after deleting it."""
    # The page checks the login too, but this callback can be called directly
    if not session.get('user_logged_in'):
        return "Please log in again."

    user = db.session.get(User, session.get('user_id'))
    if not user:
        return "Please log in again."
    if not password or not user.check_password(password):
        return "Incorrect password."

    # Someone else's sensor reads as missing, so its existence isn't confirmed
    sensor = managed_sensor(selected_device)
    if not sensor:
        return f"Could not find sensor '{selected_device}'."

    delete_sensor(sensor.id)
    return None


@callback(
    [Output("delete-sensor-error", "children", allow_duplicate=True),
     Output("delete-sensor-password", "value", allow_duplicate=True),
     Output("delete-sensor-modal", "is_open", allow_duplicate=True),
     Output("update-submission-response", "children", allow_duplicate=True),
     Output("select-device-dropdown", "value"),
     Output("select-device-dropdown", "options", allow_duplicate=True),
     Output("sensor-update", "data", allow_duplicate=True)],
    [Input("delete-confirm-btn", "n_clicks"),
     Input("delete-sensor-password", "n_submit")],
    [State("select-device-dropdown", "value"),
     State("delete-sensor-password", "value")],
    prevent_initial_call=True
)
def confirm_delete(n_clicks, n_submit, selected_device, password):
    error = delete_error(selected_device, password)
    if error:
        return error, "", no_update, no_update, no_update, no_update, no_update

    return ("", "", False, dbc.Alert(f"Sensor '{selected_device}' deleted.", color="success"), None,
            sensor_options(), {"timestamp": time.time()})
