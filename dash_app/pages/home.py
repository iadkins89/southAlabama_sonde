from dash import dcc, html, register_page
from server.models import get_all_sensors
import plotly.graph_objs as go
import dash_bootstrap_components as dbc
import os

register_page(
    __name__,
    top_nav=True,
    path='/'
)

def get_map_graph(height, l=10, r=10, t=0, b=0):
    """
    Generates a Scattermapbox graph with markers based on sensors' data.

    Returns:
        dcc.Graph: A Dash graph component.
    """
    # Retrieve sensor data
    sensors = get_all_sensors()

    # Define color mapping for device types
    device_type_colors = {
        "sonde": "red",
        "tide_gauge": "blue",
        "wave_gauge": "purple",
        "other": "green"  # Default color if no matching type
    }

    # Extract data for markers
    latitudes = [sensor["latitude"] for sensor in sensors]
    longitudes = [sensor["longitude"] for sensor in sensors]
    texts = [sensor["name"] for sensor in sensors]
    colors = [device_type_colors.get(sensor["device_type"], "gray") for sensor in sensors]

    # Create the graph
    map_graph = dcc.Graph(
        id="map-graph",
        figure={
            "data": [
                go.Scattermapbox(
                    lat=latitudes,
                    lon=longitudes,
                    mode="markers",
                    marker=dict(size=14, color=colors),
                    text=texts,
                    hoverinfo="text",
                )
            ],
            "layout": go.Layout(
                autosize=True,
                hovermode="closest",
                mapbox=dict(
                    accesstoken=os.environ.get("MAP_ACCESS_TOKEN"),
                    bearing=0,
                    center=dict(lat=30.5, lon=-88.0),  # Default center
                    pitch=0,
                    zoom=8,
                    style="outdoors"
                ),
                margin=dict(l=l, r=r, t=t, b=b),
                showlegend=False
            )
        },
        style={"height": height},
        config={
            "displayModeBar": False
        }
    )

    return map_graph

def layout():
    layout = dbc.Container(
        [
            dcc.Location(id='home-url', refresh=True),
            dcc.Store(id='click-store'),  # Store to reset clickData
            dbc.Row(
                [
                    dbc.Col(
                        dbc.Card(get_map_graph("75vh",0,0,0,0)),
                        xs=12, sm=12, md=12, lg=9
                    ),
                    dbc.Col(
                        dbc.Card([
                            html.H5("Exploring Our Network ",
                                    style={
                                        "text-align": "center",
                                        "margin-top": "20px"
                                    }
                                ),
                            html.P(
                                "This map shows the location of actively deployed sensors in our network. "
                                "Real-time sensor measurements can be viewed by selecting a sensor on the map "
                                "or by selecting a sensor in the Dashboard tab.",
                                className="lead",
                                style={"margin-left": "5%"}
                            ),
                        ]),
                    xs=12, sm=12, md=12, lg=3),
                ]
            ),
        ],
        fluid=False,
        style={"padding": "0px"}
    )

    return layout



