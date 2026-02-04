import dash
from dash import html, dcc, Output, Input, State, callback
import dash_bootstrap_components as dbc
import dash_leaflet as dl
from server.models import get_all_sensors

dash.register_page(__name__, path='/')


# Helper to Build the Card
def create_instructions_card():
    # Fetch fresh data every time the page loads
    sensors = get_all_sensors()

    # Filter sensors
    active_sensors = [s for s in sensors if s.get('active', False)]
    offline_sensors = [s for s in sensors if not s.get('active', False)]

    # Helper function to create a clean list of links
    def make_sensor_list(sensor_list):
        if not sensor_list:
            return html.Div("No sensors found.", className="text-muted small p-2")

        return dbc.ListGroup(
            [
                dbc.ListGroupItem(
                    html.A(
                        [
                            html.I(className="bi bi-circle-fill text-success me-2" if s.get(
                                'active') else "bi bi-circle-fill text-secondary me-2", style={"fontSize": "0.7rem"}),
                            s.get('name', 'Unknown')
                        ],
                        # Link to the dashboard for this specific sensor
                        href=f"/dashboard?sensor={s.get('name')}",
                        className="text-decoration-none text-dark d-flex align-items-center"
                    ),
                    className="p-1 border-0 small action-item"
                )
                for s in sensor_list
            ],
            flush=True
        )

        # Helper function to create a stylish "Title + Subtitle" list
    def make_sensor_list(sensor_list):
        if not sensor_list:
            return html.Div("No sensors found.", className="text-muted small p-2")

        list_items = []
        for s in sensor_list:
            # 1. Get the Device Type logic (matching your map markers logic)
            s_type = s.get('type') or s.get('device_type') or 'Buoy'

            # 2. Determine Dot Color
            dot_class = "bi bi-circle-fill text-success" if s.get('active') else "bi bi-circle-fill text-secondary"

            item = dbc.ListGroupItem(
                html.A(
                    [
                        # COLUMN 1: The Status Dot (Centered vertically)
                        html.Div(
                            html.I(className=dot_class, style={"fontSize": "0.6rem"}),
                            className="me-3 d-flex align-items-center"
                        ),

                        # COLUMN 2: The Text Stack (Name + Type)
                        html.Div(
                            [
                                html.Span(s.get('name', 'Unknown'), className="fw-bold text-dark me-2",
                                          style={"fontSize": "0.9rem"}),
                                # We wrap the type in parentheses or just keep it small/muted next to the name
                                html.Span(f"({s_type})", className="text-muted small",
                                          style={"fontSize": "0.75rem", "paddingTop": "2px"})
                            ],
                            # 'align-items-center' keeps them level
                            # 'flex-wrap' allows the type to drop down if the name is too long
                            className="d-flex align-items-center flex-wrap"
                        )
                    ],
                    # Link setup
                    href=f"/dashboard?sensor={s.get('name')}",
                    className="text-decoration-none d-flex align-items-center w-100"
                ),
                className="p-2 border-0 border-bottom sensor-list-item",  # Added custom class for hover
                action=True  # Makes the whole row clickable/hoverable
            )
            list_items.append(item)

        return dbc.ListGroup(list_items, flush=True)

    return dbc.Card(
        [
            dbc.CardHeader(
                html.Div([
                    html.Span([
                        html.I(className="bi bi-hdd-network me-2"),
                        "Sensor Network"
                    ], className="fw-bold"),

                    # Toggle Button
                    dbc.Button(
                        "▼",
                        id="toggle-instructions",
                        color="link",
                        size="sm",
                        className="p-0 text-white text-decoration-none",
                        style={"fontSize": "1.2rem", "lineHeight": "1"}
                    )
                ], className="d-flex justify-content-between align-items-center"),
                className="bg-primary text-white",
                # Add cursor style here to hint it is draggable
                style={"cursor": "move"}
            ),

            # Collapsible Body
            dbc.Collapse(
                dbc.CardBody(
                    [
                        # UPDATED ACCORDION WITH NEW CLASS
                        dbc.Accordion(
                            [
                                dbc.AccordionItem(
                                    make_sensor_list(active_sensors),
                                    title=f"Active ({len(active_sensors)})",
                                    item_id="active-item"
                                ),
                                dbc.AccordionItem(
                                    make_sensor_list(offline_sensors),
                                    title=f"Offline ({len(offline_sensors)})",
                                    item_id="offline-item"
                                ),
                            ],
                            flush=True,
                            start_collapsed=False,
                            always_open=True,
                            # THIS CLASS connects to the new CSS
                            className="sensor-accordion"
                        )
                    ],
                    className="p-0"  # Remove padding so the list hits the edges
                ),
                id="instructions-body",
                is_open=True
            )
        ],
        id="instructions-card",
        style={
            "position": "absolute",
            "top": "20px",
            "left": "20px",
            "width": "300px",  # Slightly wider to fit names
            "zIndex": "1000",
            "boxShadow": "0 4px 12px rgba(0,0,0,0.15)",
            "maxHeight": "80vh",  # Prevent it from being taller than screen
            "overflowY": "auto"  # Scroll if too many sensors
        },
    )


# --- 2. Helper to Create Markers (Unchanged) ---
def create_map_markers():
    sensors = get_all_sensors()
    markers = []

    for s in sensors:
        s_type = s.get('type') or s.get('device_type') or 'Buoy'
        lat = s.get('latitude')
        lon = s.get('longitude')

        if lat is None or lon is None:
            continue

        name = s.get('name', 'Unknown')
        is_active = s.get('active', False)

        status_color = "success" if is_active else "secondary"
        status_text = "Online" if is_active else "Offline"

        popup_content = dbc.Card([
            dbc.CardHeader(name, className=f"text-white bg-{status_color} p-2"),
            dbc.CardBody([
                html.P(f"Type: {s_type}", className="small mb-1"),
                html.P(f"Status: {status_text}", className="small mb-2 fw-bold"),
                dbc.Button(
                    "View Dashboard",
                    href=f"/dashboard?sensor={name}",
                    size="sm",
                    color="primary",
                    className="w-100"
                )
            ], className="p-2")
        ], className="border-0", style={"minWidth": "200px"})

        markers.append(
            dl.Marker(
                position=[lat, lon],
                children=[
                    dl.Tooltip(name),
                    dl.Popup(popup_content, closeButton=False)
                ],
                icon={
                    "iconUrl": "/assets/buoy.svg",
                    "iconSize": [25, 25],
                    "iconAnchor": [20, 20],
                    "popupAnchor": [0, -20]
                }
            )
        )
    return markers


# --- 3. The Layout Function ---
def layout():
    # We call the function here so the list is fresh every time the page loads
    card_content = create_instructions_card()

    return html.Div(
        [
            dl.Map(
                [
                    dl.TileLayer(url="https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png"),
                    dl.LayerGroup(children=create_map_markers())
                ],
                center=[30.4, -87.8],
                zoom=9,
                style={"width": "100%", "height": "100vh"},
                zoomControl=False
            ),
            card_content
        ],
        style={"position": "relative", "height": "100vh", "overflow": "hidden"}
    )


# --- 4. Callbacks ---
@callback(
    [Output("instructions-body", "is_open"), Output("toggle-instructions", "children")],
    Input("toggle-instructions", "n_clicks"),
    State("instructions-body", "is_open"),
    prevent_initial_call=True
)
def toggle_card(n, is_open):
    if is_open:
        return False, "▲"
    else:
        return True, "▼"
