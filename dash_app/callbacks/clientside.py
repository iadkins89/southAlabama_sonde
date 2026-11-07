from dash import clientside_callback, ClientsideFunction, Input, Output

# Update Store from WebSocket trigger
clientside_callback(
    ClientsideFunction(
        namespace="clientside",
        function_name="update_store"
    ),
    Output("live-sensor-data", "data"),
    Input("ws-trigger", "children")
)

# The sensor list starts closed, so that it doesn't cover the map on a phone
clientside_callback(
    """
    function () {
        return window.innerWidth > 768 ? ["active-item"] : window.dash_clientside.no_update;
    }
    """,
    Output("sensor-accordion", "active_item"),
    Input("sensor-accordion", "id")
)

# The network card starts closed for the same reason
clientside_callback(
    """
    function () {
        return window.innerWidth > 768 ? [true, "\u25BC"] : window.dash_clientside.no_update;
    }
    """,
    [Output("instructions-body", "is_open", allow_duplicate=True),
     Output("toggle-instructions", "children", allow_duplicate=True)],
    Input("instructions-card", "id"),
    prevent_initial_call="initial_duplicate"
)
