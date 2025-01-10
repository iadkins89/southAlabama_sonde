from dash import dcc, html, register_page
import dash_bootstrap_components as dbc
from datetime import datetime
import pytz
from .home import get_map_graph

register_page(
    __name__,
    top_nav=False,
    path='/dashboard'
)

def layout(name=None, **other_unknown_query_strings):
    cst = pytz.timezone('America/Chicago')
    cst_today = datetime.now(cst).replace(hour=0, minute=0, second=0, microsecond=0)

    layout = dbc.Container([
        dcc.Location(id='url', refresh=False),
        dcc.Store(id="sensor-name-store", data=name),

        # First Row (Map and Info Box)
        dbc.Row([
            # Column for the map (unchanged)
            dbc.Col(
                dbc.Card(get_map_graph("50vh", 0, 0, 0, 0)),
                xs=12, sm=12, md=12, lg=6, className="mb-3"
            ),

            # Column for the sensor card
            dbc.Col(
                dbc.Card(
                    [
                        dbc.CardBody(
                            [
                                # Create a row for the summary content and image
                                dbc.Row(
                                    [
                                        # Column for the title and summary content
                                        dbc.Col(
                                            [
                                                html.H5(id="card-title", className="card-title"),
                                                        # Dynamically set title
                                                        html.Div(
                                                            id="summary-content",
                                                            children=html.P("Loading summary information...",
                                                                            className="summary-text"),
                                                            style={"text-align": "left"}
                                                        )
                                                     ],
                                                        width=True,  # Takes remaining space
                                                    ),

                                        # Column for the sensor image
                                        dbc.Col([
                                            html.H5(),
                                            html.Div(
                                                id="sensor-image-container",
                                                children=[
                                                    html.Img(
                                                        id="sensor-image",  # ID to dynamically update the image
                                                        src=f"/assets/{name}.png",  # Default image path
                                                        alt="Sensor Image",
                                                        style={"width": "250px", "height": "auto",
                                                               "borderRadius": "8px"}  # Adjust style as needed
                                                    )
                                                ],
                                                style={
                                                    "display": "flex",
                                                    "alignItems": "center",  # Vertically centers the image
                                                    "justifyContent": "center",
                                                    # Horizontally centers the image (if needed)
                                                    "height": "100%",  # Ensure the container takes up full height
                                                }
                                            ),
                                           ], width="auto",  # Adjust width based on image size
                                        ),
                                    ]
                                ),
                            ]
                        ),

                        # Footer for the card (unchanged)
                        dbc.CardFooter([
                            dbc.Button("Download Data", id="download-button", size="sm", color="light"),
                            dbc.Button("Sensor Health", id="sensor-health-button", size="sm", color="info",
                                       className="ms-2")
                        ]),

                        # Offcanvas for download options (unchanged)
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
                                dbc.Input(id="csv-filename", placeholder="Enter CSV filename",
                                          style={'margin-bottom': '12px'}),
                                dbc.Button("Download CSV", id="set-filename-btn", size="sm", color="primary",
                                           className="mt-2"),
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

                        # Offcanvas for sensor health (unchanged)
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
                    ], style={"height": "100%"}
                ),
                xs=12, sm=12, md=12, lg=6
            ),
        ], className="g-3", justify="center"),

        # Second Row (Date Picker)
        dbc.Row(
            dbc.Col(
                dbc.ButtonGroup(
                    [
                        dbc.Button("2 Days", id="range-2-days", color="primary", outline=False, active=True),
                        dbc.Button("1 Week", id="range-1-week", color="primary", outline=True),
                        dbc.Button("1 Month", id="range-1-month", color="primary", outline=True),
                        dbc.Button("1 Year", id="range-1-year", color="primary", outline=True),
                    ],
                    size="sm",  # Adjust size of the buttons
                    className="mb-3",
                )
            ),
        ),

        # Third Row (Graph)
        dcc.Loading(
            id='graph-loader',
             children=dbc.Row(
                id="multi-sensor-graph",  # Graphs will be dynamically added here
                className="g-4",  # Space between rows
            ),
        )
    ], fluid=False)  # Use `fluid=True` for a full-width container

    return layout


