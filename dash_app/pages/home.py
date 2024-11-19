from dash import dcc, html, register_page
import plotly.graph_objs as go
import dash_bootstrap_components as dbc
import os

register_page(
    __name__,
    top_nav=True,
    path='/'
)

# Map graph configuration
map_graph = dcc.Graph(
    id='map-graph',
    figure={
        'data': [
            go.Scattermapbox(
                lat=[30.685075],
                lon=[-88.074669],
                mode='markers',
                marker=dict(size=14, color='red'),
                text=['Sensor Location']
            )
        ],
        'layout': go.Layout(
            autosize=True,
            hovermode='closest',
            mapbox=dict(
                accesstoken=os.environ.get("MAP_ACCESS_TOKEN"),
                bearing=0,
                center=dict(
                    lat=30.685075,
                    lon=-88.074669
                ),
                pitch=0,
                zoom=8,
                style='outdoors'
            ),
            margin=dict(l=0, r=0, t=0, b=0),  # Remove padding around the map
        )
    },
    style={'height': '75vh', 'width': '100%'},
    config={
        'displayModeBar': False  # Hide the mode bar completely
    }
)

def layout():
    layout = dbc.Container(
        [
            dcc.Location(id='url', refresh=True),
            dcc.Store(id='click-store'),  # Store to reset clickData
            dbc.Row(
                dbc.Col(
                    map_graph,
                    width=12
                ),
            style={"margin": "0"}
            ),
            dbc.Row(
                dbc.Col(
                    html.P(
                        "This map shows the location of actively deployed sensors in our network. "
                        "You can use this map to visualize the sensor's position and explore the surrounding area."
                        "Collected sensor measurements can be viewed by clicking a sensor marker on the map"
                        "or by clicking Dashboard tab of this webpage.",
                        className="lead",
                        style={"margin-left": "5%", "margin-right": "5%"}
                    ),
                    width='12'
                ),
                style={"margin-top": "0px"}
            ),
        ],
        fluid=True,
        style={"padding": "0px"} 
    )

    return layout


