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
    Output("map-markers", "children"),
    Input("show-inactive-switch", "value"),
    prevent_initial_call=True
)
def toggle_inactive_sensors(show_inactive):
    # Re-generate markers with the new switch value
    # We ignore center/zoom (using _) so the map doesn't jump when you toggle
    markers, _, _ = create_map_markers(show_inactive=show_inactive)
    return markers