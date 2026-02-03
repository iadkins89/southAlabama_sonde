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