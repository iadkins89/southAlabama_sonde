from dash import dcc, html, register_page
import dash_bootstrap_components as dbc
from datetime import datetime
from dash_extensions import EventSource
from server.models import get_unique_sensor_names
import pytz
import plotly.graph_objs as go
import os


register_page(
    __name__,
    top_nav=False,
    path='/dashboard'
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
                text=['sensor1234'],
                hoverinfo='text',
            ),
            go.Scattermapbox(
                lat=[30.433475],
                lon=[-88.005984],
                mode='markers',
                marker=dict(size=14, color='red'),
                text=['multi_sensored_sonde1'],
                hoverinfo='text',
            ),
            go.Scattermapbox(
                lat=[30.54294824],
                lon=[-87.90090477],
                mode='markers',
                marker=dict(size=14, color='blue'),
                text=['tide_gauge'],
                hoverinfo='text'
            ),
            go.Scattermapbox(
                lat=[30.259100],
                lon=[-87.999108],
                mode='markers',
                marker=dict(size=14, color='purple'),
                text=['wave_gauge'],
                hoverinfo='text'
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
            showlegend=False  # Remove the trace side bar (legend)
        )
    },
    style={'height': '50vh'},
    config={
        'displayModeBar': False  # Hide the mode bar completely
    }
)

def layout(name=None, **other_unknown_query_strings):
    cst = pytz.timezone('America/Chicago')
    cst_today = datetime.now(cst).replace(hour=0, minute=0, second=0, microsecond=0)

    layout = dbc.Container([
        dcc.Location(id='url', refresh=True),
        dcc.Store(id="sensor-name-store", data=name),

        # First Row (Map and Info Box)
        dbc.Row([
            dbc.Col(
                dbc.Card(map_graph)
                # map_graph,
                # xs=12, sm=12, md=6, lg=6, className="mb-3"
            ),
            dbc.Col(
                dbc.Card(
                    [
                        #dbc.CardHeader(name),
                        dbc.CardBody(
                            [
                                html.H5(id="card-title", className="card-title"),  # Dynamically set title
                                html.Div(
                                    id="summary-content",
                                    children=html.P("Loading summary information...", className="summary-text"),
                                    style={"textAlign": "left"}
                                ),
                            ]
                        ),
                        dbc.CardFooter([dbc.Button("Download Data", id="download-button", size="sm", color="light"),
                                       dbc.Button("Sensor Health", id="sensor-health-button", size="sm", color="info", className="ms-2")]),
                        dbc.Offcanvas(
                            html.Div([
                                html.P("Data Type"),
                                dcc.RadioItems(
                                    ['   Sensor Data', '   LoRaWAN Data'],
                                    '   Sensor Data',
                                    id="radio-data-item",
                                    style={'margin-bottom': '12px'}
                                ),
                                html.P("Date Range"),
                                dcc.DatePickerRange(
                                    id='date-picker-range',
                                    minimum_nights=0,
                                    start_date=cst_today,
                                    end_date=cst_today,
                                    stay_open_on_select=True,
                                ),
                                html.P("File Name", style={'margin-top': '14px'}),
                                dbc.Input(id="csv-filename", placeholder="Enter CSV filename", style={'margin-bottom': '12px'}),
                                dbc.Button("Download CSV", id="set-filename-btn", size = "sm", color="primary", className="mt-2"),
                                dcc.Download(id="download-dataframe-csv"),
                                dcc.ConfirmDialog(
                                    id='confirm-dialog',
                                    message=''
                                )]
                            ),
                            id="download-data-offcanvas",
                            title="Download Options",
                            is_open=False,
                        ),
                        dbc.Offcanvas(
                            html.Div([
                                html.H5("Battery Level", className="mt-3"),
                                dbc.Progress(id="battery-gauge", value=75, animated=True, striped=True, color="success",
                                             style={"height": "20px"}),
                                html.H5("RSSI", className="mt-4"),
                                dbc.Progress(id="rssi-progress", value=50, color="warning", style={"height": "20px"}),
                                html.H5("SNR", className="mt-4"),
                                dbc.Progress(id="snr-progress", value=30, color="danger", style={"height": "20px"}),
                            ]),
                            id="sensor-health-offcanvas",
                            title="Sensor Health",
                            is_open=False,
                        ),
                    ], style={"height":"100%"}
                ), xs=12, sm=12, md=12, lg=6
            ),
        ], className="g-3", justify="center"),

        # Second Row (Graph)
        dbc.Row([
            dbc.Col(
                dcc.DatePickerRange(
                    id='temp-date-picker-range',
                    minimum_nights=0,
                    start_date=cst_today,
                    end_date=cst_today,
                    stay_open_on_select=True,
                )
            ),
            dbc.Col(
                id="multi-sensor-graph",  # Graphs will be dynamically added here
                className="g-4",  # Space between rows
                #dcc.Graph(
                #    id='multi-sensor-graph',
                #    config={
                #        'displayModeBar': False,
                #        'displaylogo': False
                #    },
                #),
                xs=12, sm=12, md=12, lg=12  # Full width for all screens
            ),
        ]),

        # EventSource Component
        EventSource(id='eventsource', url='/eventsource')
    ], fluid=True)  # Use `fluid=True` for a full-width container

    return layout


