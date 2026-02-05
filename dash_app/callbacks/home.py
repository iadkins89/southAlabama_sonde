from dash import callback, Input, Output, State
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