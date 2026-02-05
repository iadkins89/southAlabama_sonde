import dash
from dash import html, dcc, Output, Input, State, callback
import dash_bootstrap_components as dbc
import dash_leaflet as dl
from server.utils import create_map_markers
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

def layout():

    card_content = create_instructions_card()
    markers, map_center, map_zoom = create_map_markers(selected_sensor_name=None)

    return html.Div(
        [
            dl.Map(
                [
                    dl.TileLayer(url="https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png"),
                    dl.LayerGroup(children=markers)
                ],
                center=map_center,
                zoom=map_zoom,
                style={"width": "100%", "height": "100vh"},
                zoomControl=False
            ),
            card_content
        ],
        style={"position": "relative", "height": "100vh", "overflow": "hidden"}
    )
