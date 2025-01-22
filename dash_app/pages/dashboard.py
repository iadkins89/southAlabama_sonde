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
                xs=12, sm=12, md=12, lg=6,
            ),

            # Column for the sensor card
            dbc.Col(
                dbc.Card(
                    [
                        dbc.CardBody(
                            [
                                dbc.Row(
                                    [
                                        # Column for the title and summary content
                                        dbc.Col(
                                            [
                                                html.H5(id="card-title", className="card-title"),
                                                html.Div(
                                                    id="summary-content",
                                                    children=html.P(
                                                        "Loading summary information...",
                                                        className="summary-text"
                                                    ),
                                                    className="summary-container"
                                                )
                                            ],
                                            width=True,
                                        ),

                                        # Column for the sensor image
                                        dbc.Col([
                                            html.H5(),
                                            html.Div(
                                                id="sensor-image-container",
                                                children=[
                                                    html.Img(
                                                        id="sensor-image",
                                                        src=f"/assets/{name}.png",
                                                        alt="Sensor Image",
                                                        className="sensor-image"
                                                    )
                                                ],
                                                className="image-container"
                                            ),
                                        ], width='auto'),
                                    ]
                                ),
                            ]
                        ),

                        dbc.CardFooter([
                            dbc.Button("Download Data", id="download-button", size="sm", color="light"),
                            dbc.Button("Sensor Health", id="sensor-health-button", size="sm", color="light",
                                       className="ms-2")
                        ]),

                        dbc.Offcanvas(
                            html.Div([
                                html.P("Data Type"),
                                dcc.RadioItems(
                                    ['   Sensor Data', '   LoRaWAN Data'],
                                    '   Sensor Data',
                                    id="radio-data-item",
                                    className="radio-items"
                                ),
                                html.P("Date Range"),
                                dcc.DatePickerRange(
                                    id='date-picker-range',
                                    minimum_nights=0,
                                    start_date=cst_today,
                                    end_date=cst_today,
                                    stay_open_on_select=True,
                                ),
                                html.P("File Name", className="file-name-label"),
                                dbc.Input(
                                    id="csv-filename",
                                    placeholder="Enter CSV filename",
                                    className="filename-input"
                                ),
                                dbc.Button(
                                    "Download CSV", id="set-filename-btn", size="sm", color="primary",
                                    className="download-csv-btn"
                                ),
                                dcc.Download(id="download-dataframe-csv"),
                                dcc.ConfirmDialog(
                                    id='confirm-dialog',
                                    message=''
                                )
                            ]),
                            id="download-data-offcanvas",
                            title="Download Options",
                            is_open=False,
                        ),

                        dbc.Offcanvas(
                            html.Div([
                                html.H5("Battery Level", className="battery-label"),
                                dbc.Progress(id="battery-gauge", value=75, animated=True, striped=True, color="success",
                                             className="progress-bar"),
                                html.H5("RSSI", className="rssi-label"),
                                dbc.Progress(id="rssi-progress", value=50, color="warning", className="progress-bar"),
                                html.H5("SNR", className="snr-label"),
                                dbc.Progress(id="snr-progress", value=30, color="danger", className="progress-bar"),
                            ]),
                            id="sensor-health-offcanvas",
                            title="Sensor Health",
                            is_open=False,
                        ),
                    ],
                    className="sensor-card"
                ),
                xs=12, sm=12, md=12, lg=6
            ),
        ], className="g-3", justify="center"),

        dbc.Row(
            dbc.Col(
                dbc.RadioItems(
                    id="date-range-radio",
                    className="btn-group",  # Group styling
                    inputClassName="btn-check",  # Hidden input style
                    labelClassName="btn btn-outline-primary",  # Button styling
                    labelCheckedClassName="active",  # Active button styling
                    options=[
                        {"label": "2 Days", "value": "2-days"},
                        {"label": "1 Week", "value": "1-week"},
                        {"label": "1 Month", "value": "1-month"},
                        {"label": "1 Year", "value": "1-year"},
                    ],
                    value="2-days",  # Default value
                ),
                className="radio-group mt-3",  # Add margin-top for spacing
            ),
        ),

        dbc.Spinner(
            id='graph-loader',
             children=dbc.Row(
                id="multi-sensor-graph",
                className="g-4",
            ), color='primary'
        )
    ], fluid=False, className="dash-container")

    return layout



