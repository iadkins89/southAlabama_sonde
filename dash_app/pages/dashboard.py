from dash import dcc, html, register_page
import dash_bootstrap_components as dbc
from datetime import datetime
import pytz
import dash_leaflet as dl
from server.utils import BATTERY_MIN_V, create_map_markers, get_carto_tile_url

register_page(
    __name__,
    top_nav=False,
    path='/dashboard'
)

def bar_with_value(bar, value_id):
    # The value is centered on the whole bar, because a weak reading's fill is too short to hold it.
    return html.Div(
        [bar, html.Span(id=value_id, style={
            "position": "absolute", "inset": 0, "display": "flex", "alignItems": "center",
            "justifyContent": "center", "fontSize": "0.8rem", "fontWeight": 600,
            "color": "#212529", "pointerEvents": "none"
        })],
        style={"position": "relative"}
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
                            dl.TileLayer(url=get_carto_tile_url()),
                            dl.LayerGroup(children=markers, id="map-markers")
                        ],
                        id="dashboard-map",
                        center=map_center,
                        zoom=map_zoom,
                        style={"width": "100%", "height": "55vh"},
                        zoomControl=True
                    ),
                    className="shadow-sm border-0"
                ),
                xs=12, sm=12, md=12, lg=6,
                className="h-100"
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
                                                        style={
                                                            "display": "block", "width": "100%", "height": "100%",
                                                            "objectFit": "cover", "borderRadius": "8px"
                                                        }
                                                    )
                                                ],
                                                # Every sensor's image fills the same square, whatever its shape
                                                style={"width": "220px", "height": "220px", "margin": "0 auto"},
                                            ),
                                        ], xs=12, md="auto"),
                                    ], className="align-items-center"
                                ),
                            ],
                            className="sensor-summary-container",
                           style = {"overflowY": "auto"},
                        ),

                        dbc.CardFooter([
                            dbc.Button("Download Data", id="download-button", size="sm", color="light"),
                            dbc.Button("Sensor Health", id="sensor-health-button", size="sm", color="light",
                                       className="ms-2"),
                            dbc.Button("Deployment History", id="history-button", size="sm", color="light",),
                        ], className="d-flex justify-content-center py-2 bg-white border-top"),

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
                                bar_with_value(
                                    dbc.Progress(id="battery-gauge", value=75, animated=True, striped=True, color="success",
                                                 min=BATTERY_MIN_V, max=4.2, className="progress-bar"),
                                    "battery-value"
                                ),
                                html.H5("RSSI", className="rssi-label"),
                                bar_with_value(
                                    dbc.Progress(id="rssi-progress", value=50, color="warning", className="progress-bar"),
                                    "rssi-value"
                                ),
                                html.H5("SNR", className="snr-label"),
                                bar_with_value(
                                    dbc.Progress(id="snr-progress", value=30, color="danger", className="progress-bar"),
                                    "snr-value"
                                ),
                                html.Div([
                                    html.H5("Board Temperature", className="snr-label"),
                                    html.P(id="board-temp-value"),
                                ], id="board-temp-container", style={"display": "none"}),
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
                            #placement="end",
                            is_open=False,
                        ),
                    ],
                    className="sensor-card shadow-sm border-0",
                    style = {"height": "55vh"}
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
                            html.Span(id="slider-date-label", className="badge bg-light")
                        ], className="d-flex justify-content-between align-items-center mb-3"),

                        html.Div(
                            dcc.RangeSlider(
                                id="historic-date-slider",
                                min=0, max=100, value=[0, 100],
                                tooltip={"always_visible": False}
                            ),
                            style={"padding": "0 10px"}
                        )
                    ], id="historic-controls-container", style={"display": "none"})
                ],
                className="radio-group mt-3"
            )
        ),
        dbc.Row(
            id="multi-sensor-graph",
            className="g-4",
        )
    ], fluid=False, className="dash-container pt-3")

    return layout
