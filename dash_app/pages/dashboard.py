from dash import dcc, html, register_page
from flask import session
import dash_bootstrap_components as dbc
from datetime import datetime
import pytz
import dash_leaflet as dl
from server.models import get_past_deployments, get_sensor_by_name, get_sensor_timezone
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
            "color": "var(--ink)", "pointerEvents": "none"
        })],
        style={"position": "relative"}
    )


def skeleton_graphs():
    return [dbc.Col(html.Div(className="skeleton skeleton-graph"), xs=12) for _ in range(2)]


def skeleton_tiles():
    return html.Div([html.Div(className="skeleton skeleton-tile") for _ in range(4)], className="reading-tiles")


def layout(sensor=None, **other_unknown_query_strings):
    # A test device doesn't exist as far as the public is concerned
    sensor_row = get_sensor_by_name(sensor) if sensor else None
    testing = bool(sensor_row and sensor_row.testing)
    if testing and not session.get('user_logged_in'):
        from dash_app.pages.not_found_404 import layout as not_found
        return not_found()

    cst = pytz.timezone('America/Chicago')
    cst_today = datetime.now(cst).replace(hour=0, minute=0, second=0, microsecond=0)

    markers, map_center, map_zoom = create_map_markers(sensor)

    # Starting on the newest deployment stops a deactivated sensor flashing its live view
    deployments = get_past_deployments(sensor) if sensor else []

    layout = dbc.Container([
        dcc.Store(id="sensor-name-store", data=sensor),
        dcc.Store(id="live-sensor-data"),
        # Test devices are left out of live broadcasts, so their page checks for new readings itself
        dcc.Interval(id="test-device-refresh", interval=60 * 1000, disabled=not testing),
        dcc.Store(id="selected-deployment-store", data=deployments[0] if deployments else None),

        # Sensor name and actions
        html.Div([
            html.Div([
                dcc.Link([html.I(className="bi bi-arrow-left"), "Test devices" if testing else "All sensors"],
                         href="/onboarding/test-devices" if testing else "/", className="hero-back"),
                html.H1(id="card-title", className="hero-title"),
                html.Div(id="hero-meta", className="hero-meta"),
            ]),
            html.Div([
                dbc.Button([html.I(className="bi bi-download me-2"), "Download Data"], id="download-button",
                           color="primary", size="sm"),
                dbc.Button([html.I(className="bi bi-activity me-2"), "Sensor Health"], id="sensor-health-button",
                           color="secondary", outline=True, size="sm"),
                dbc.Button([html.I(className="bi bi-clock-history me-2"), "Deployment History"], id="history-button",
                           color="secondary", outline=True, size="sm"),
            ], className="hero-actions"),
        ], className="dash-hero"),

        # Map and latest readings
        dbc.Row([
            dbc.Col(
                html.Div(
                    dl.Map(
                        [
                            dl.TileLayer(url=get_carto_tile_url()),
                            dl.LayerGroup(children=markers, id="map-markers")
                        ],
                        id="dashboard-map",
                        center=map_center,
                        zoom=map_zoom,
                        style={"width": "100%", "height": "100%"},
                        zoomControl=True
                    ),
                    className="surface-card dash-map"
                ),
                xs=12, lg=5,
            ),
            dbc.Col(
                html.Div(
                    html.Div([
                        html.Div(skeleton_tiles(), id="summary-content", className="summary-main"),
                        # Phones only: the photo stays tucked away until asked for
                        html.Button(
                            [html.I(className="bi bi-image"), html.Span("Show sensor photo", id="photo-toggle-label"),
                             html.I(className="bi bi-chevron-down photo-toggle-arrow")],
                            id="photo-toggle", className="photo-toggle", type="button",
                            **{"aria-expanded": "false", "aria-controls": "sensor-image-container"}
                        ),
                        html.Div(
                            html.Img(
                                id="sensor-image",
                                src="/assets/no_image_available.png",  # Default placeholder
                                alt="Sensor photo",
                                style={"display": "block", "width": "100%", "height": "100%",
                                       "objectFit": "cover", "borderRadius": "10px"}
                            ),
                            id="sensor-image-container",
                            # Every sensor's image fills the same square, whatever its shape
                            style={"width": "220px", "height": "220px", "flex": "0 0 220px"},
                        ),
                    ], className="summary-layout"),
                    className="surface-card summary-card"
                ),
                xs=12, lg=7,
            ),
        ], className="g-3"),

        # Graph range
        html.Div([
            html.Div([
                # --- LIVE CONTROLS (Radio Buttons) ---
                dbc.RadioItems(
                    id="date-range-radio",
                    className="btn-group range-group",
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
                html.Div(f"Drag across a graph to zoom in. Double-click to zoom back out. "
                         f"Times are {get_sensor_timezone(sensor)} all year.", className="range-hint"),
            ], className="range-row"),

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
        ], className="range-bar"),

        dbc.Row(skeleton_graphs(), id="multi-sensor-graph", className="g-3"),

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
                                    bar_with_value(
                                        dbc.Progress(id="board-temp-progress", value=0, className="progress-bar"),
                                        "board-temp-value"
                                    ),
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
    ], fluid=False, className="dash-container page")

    return layout
