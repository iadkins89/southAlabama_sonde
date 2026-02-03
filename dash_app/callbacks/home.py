from dash import callback, Input, Output, no_update
@callback(
    Output('home-url', 'href'),
    Input('map-graph', 'clickData')
)
def home_redirect_on_click(clickData):
    if clickData:
        sensor_name = clickData['points'][0]['text']

        # Generate the URL with query string
        return f"/dashboard?name={sensor_name}"
    return no_update