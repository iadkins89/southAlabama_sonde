from dash import callback, Input, Output, State
from server.utils import create_map_markers
@callback(
    [Output("instructions-body", "is_open"), Output("toggle-instructions", "children")],
    Input("toggle-instructions", "n_clicks"),
    State("instructions-body", "is_open"),
    prevent_initial_call=True
)
def toggle_card(n, is_open):
    if is_open:
        return False, "▲"
    else:
        return True, "▼"

@callback(
    Output("show-inactive-switch", "value"),
    Input("show-inactive-switch", "id"),  # Runs when the home page appears
    State("show-inactive-store", "data")
)
def restore_inactive_switch(_, show_inactive):
    return bool(show_inactive)

@callback(
    [Output("map-markers", "children"),
     Output("show-inactive-store", "data")],
    Input("show-inactive-switch", "value"),
    prevent_initial_call=True
)
def toggle_inactive_sensors(show_inactive):
    markers, _, _ = create_map_markers(show_inactive=show_inactive)
    return markers, show_inactive