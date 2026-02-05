from dash import callback, Input, Output, State, callback_context
from server.models import get_sensor_by_name, create_or_update_sensor, get_all_sensors
import dash_bootstrap_components as dbc

@callback(
    Output("select-device-dropdown", "options"),
    Input("main-url", "pathname")
)
def populate_sensor_dropdown(pathname):
    # This fires when the page loads
    sensors = get_all_sensors()
    return [{'label': f"{s['name']} (Inactive)" if not s.get('active', True) else s['name'],
             'value': s['name']} for s in sensors]

@callback(
    Output("form-container", "style"),
    [Input("select-device-dropdown", "value")]
)
def show_form_on_device_select(selected_device):
    if selected_device:
        return {"display": "block"}  # Show the form
    return {"display": "none"}  # Hide the form if no device is selected

@callback(
    [Output("update-device-name", "value"),
     Output("update-latitude", "value"),
     Output("update-longitude", "value"),
     Output("update-device-type", "value"),
     Output("sensor-active-status-store", "data"),  # Store the status
     Output("toggle-active-btn", "children"),  # Change button text
     Output("toggle-active-btn", "color")],
    [Input("select-device-dropdown", "value")]
)
def populate_form_with_device_info(selected_device):
    if selected_device:
        # Get the sensor details from the database
        sensor = get_sensor_by_name(selected_device)

        btn_text = "Deactivate" if sensor.active else "Reactivate"
        btn_color = "danger" if sensor.active else "success"

        return sensor.name, sensor.latitude, sensor.longitude, sensor.device_type, sensor.active, btn_text, btn_color
    return "", "", "", "", "", "", ""

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
     State("sensor-active-status-store", "data")]
)
def update_sensor_information(submit_clicks, deactivate_clicks, original_name, new_name, lat, lon, dtype,
                              image_data, is_active):
    # Determine which button was clicked
    ctx = callback_context
    if not ctx.triggered: return ""

    button_id = ctx.triggered[0]['prop_id'].split('.')[0]

    if button_id == "toggle-active-btn":
        new_status = not is_active
        msg = create_or_update_sensor(original_name, lat, lon, dtype, image_data=None, active=new_status)

        status_word = "Activated" if new_status else "Deactivated"
        color = "success" if new_status else "warning"
        return dbc.Alert(f"Sensor '{original_name}' {status_word}. (Please refresh page to see button update)",
                         color=color)

    elif button_id == "update-submit-btn":
        # Normal Update: Set active=True
        msg = create_or_update_sensor(new_name, lat, lon, dtype, image_data, active=True)
        return dbc.Alert(msg, color="success")

    return ""
