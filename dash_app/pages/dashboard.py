from dash import dcc, html, register_page
import dash_bootstrap_components as dbc
from datetime import datetime
import pytz
import dash_leaflet as dl
from server.utils import create_map_markers

register_page(
    __name__,
    top_nav=False,
    path='/dashboard'
)

def layout(sensor=None, **other_unknown_query_strings):
    cst = pytz.timezone('America/Chicago')
    cst_today = datetime.now(cst).replace(hour=0, minute=0, second=0, microsecond=0)

    markers, map_center, map_zoom = create_map_markers(sensor)

    layout = dbc.Container([
        dcc.Store(id="sensor-name-store", data=sensor),
        dcc.Store(id="live-sensor-data"),
        dcc.Store(id="selected-deployment-store", data=None),

        # First Row (Map and Info Box)
        dbc.Row([
            # Map
            dbc.Col(
                dbc.Card(
                    dl.Map(
                        [
                            dl.TileLayer(
                                url="https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png"),
                            dl.LayerGroup(children=markers, id="map-markers")
                        ],
                        id="dashboard-map",
                        center=map_center,
                        zoom=map_zoom,
                        style={"width": "100%", "height": "50vh"},
                        zoomControl=True
                    ),
                    className="shadow-sm border-0"
                ),
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
                                                        src="/assets/no_image_available.png",  # Default placeholder
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
                                       className="ms-2"),
                            dbc.Button("Deployment History", id="history-button", size="sm", color="light", className="border"),
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
                                             min=3.4, max=4.2, className="progress-bar"),
                                html.H5("RSSI", className="rssi-label"),
                                dbc.Progress(id="rssi-progress", value=50, color="warning", className="progress-bar"),
                                html.H5("SNR", className="snr-label"),
                                dbc.Progress(id="snr-progress", value=30, color="danger", className="progress-bar"),
                            ]),
                            id="sensor-health-offcanvas",
                            title="Sensor Health",
                            is_open=False,
                        ),

                        dbc.Offcanvas(
                            html.Div(
                                dbc.ListGroup(id="history-list-content", flush=True)
                            ),
                            id="history-offcanvas",
                            title="Deployment History",
                            placement="end",
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
                [
                    # --- LIVE CONTROLS (Radio Buttons) ---
                    dbc.RadioItems(
                        id="date-range-radio",
                        className="btn-group",
                        inputClassName="btn-check",
                        labelClassName="btn btn-outline-primary",
                        labelCheckedClassName="active",
                        options=[
                            {"label": "2 Days", "value": "2-days"},
                            {"label": "1 Week", "value": "1-week"},
                            {"label": "1 Month", "value": "1-month"},
                            {"label": "1 Year", "value": "1-year"},
                        ],
                        value="2-days",
                        style={"display": "inline-flex"}
                    ),

                    # --- HISTORY CONTROLS (Slider) ---
                    html.Div([
                        html.Div([
                            html.Span("Playback History", className="fw-bold small me-2"),
                            html.Span(id="slider-date-label", className="badge bg-secondary")
                        ], className="d-flex justify-content-between align-items-center mb-3"),

                        html.Div(
                            dcc.RangeSlider(
                                id="historic-date-slider",
                                min=0, max=100, value=[0, 100],
                                # Disable built-in tooltip (it shows raw numbers)
                                tooltip={"always_visible": False}
                            ),
                            style={"padding": "0 10px"}
                        )
                    ], id="historic-controls-container", style={"display": "none"})
                ],
                className="radio-group mt-3"  # Keep your original class
            )
        ),
        dbc.Row(
            id="multi-sensor-graph",
            className="g-4",
        )
    ], fluid=False, className="dash-container")

    return layout
