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
"""
def get_map_graph(height, l=10, r=10, t=0, b=0):
   
    Generates a Scattermapbox graph with markers based on sensors' data.

    Returns:
        dcc.Graph: A Dash graph component.
  
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
    device_type = [sensor["device_type"] for sensor in sensors]

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
                showlegend=True,
                legend=dict(
                    title="Device Types",
                    font=dict(size=12),
                    bgcolor="rgba(255, 255, 255, 0.7)",  # Semi-transparent background
                    bordercolor="lightgray",
                    borderwidth=1,
                    x=0.02,  # Horizontal position within the map
                    y=0.98,  # Vertical position within the map
                ),
            )
        },
        style={"height": height},
        config={
            "displayModeBar": False
        }
    )

    return map_graph
"""
def get_map_graph(height, l=10, r=10, t=0, b=0):
    """
    Generates a Scattermapbox graph with markers based on sensors' data, including a legend for device types.

    Returns:
        dcc.Graph: A Dash graph component.
    """
    # Retrieve sensor data
    sensors = get_all_sensors()

    # Define color mapping for device types
    device_type_colors = {
        "sonde": "darkblue",
        "tide_gauge": "seagreen",
        "wave_gauge": "blue",
        "other": "goldenrod"  # Default color if no matching type
    }

    # Create Scattermapbox traces grouped by device type
    traces = []
    for device_type, color in device_type_colors.items():
        # Filter sensors for this device type
        filtered_sensors = [sensor for sensor in sensors if sensor["device_type"] == device_type]

        # Add a trace if there are sensors of this type
        if filtered_sensors:
            traces.append(
                go.Scattermapbox(
                    lat=[sensor["latitude"] for sensor in filtered_sensors],
                    lon=[sensor["longitude"] for sensor in filtered_sensors],
                    mode="markers",
                    marker=dict(
                        size=16,
                        color=color,
                    ),
                    text=[sensor["name"] for sensor in filtered_sensors],
                    hoverinfo="text",
                    name=device_type.replace("_", " ").capitalize(),  # Legend label
                    legendgroup=device_type  # Grouping for consistent coloring
                )
            )

    # Create the map graph
    map_graph = dcc.Graph(
        id="map-graph",
        figure={
            "data": traces,
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
                showlegend=True,
                legend=dict(
                    title="Device Types",
                    font=dict(size=12),
                    bgcolor="rgba(255, 255, 255, 0.7)",  # Semi-transparent background
                    bordercolor="lightgray",
                    borderwidth=1,
                    x=0.02,  # Horizontal position within the map
                    y=0.98,  # Vertical position within the map
                ),
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
                                "or by selecting a sensor in the Sensors tab.",
                                className="lead",
                                style={"margin-left": "5%"}
                            ),
                        ]),
                    xs=12, sm=12, md=12, lg=3),
                ], className="g-3", justify="center"
            ),
        ],
        fluid=False,
        #style={"padding": "0px"}
    )

    return layout



