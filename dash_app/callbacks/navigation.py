from dash import callback, Input, Output, State, ALL, html
import dash_bootstrap_components as dbc
from server.models import get_sensors_grouped_by_type

@callback(
    Output("navbar-collapse", "is_open"),
    [
        Input("navbar-toggler", "n_clicks"),
        Input("home-link", "n_clicks"),
        Input("onboarding-link", "n_clicks"),
        Input("about-link", "n_clicks"),
        Input({"type": "sensor-item", "index": ALL}, "n_clicks")
    ],
    State("navbar-collapse", "is_open"),
)
def toggle_navbar(n_clicks, home_click, onboard_click, about_click, sensor_clicks, is_open):
    if any([n_clicks, home_click, onboard_click, about_click]) or any(sensor_clicks):
        return not is_open
    return is_open


@callback(
    Output("sensors-dropdown", "children"),
    Input("sensor-update", "data")
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
