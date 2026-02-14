import pandas as pd
import os
import io
import base64
from PIL import Image, ImageOps
from collections import defaultdict
import dash_bootstrap_components as dbc
from dash import html
import dash_leaflet as dl
import plotly.graph_objs as go
from dash import dcc
# from server.models import get_sensor_timezone, get_sensor_by_name, get_most_recent, get_all_sensors
# TO DO: Refactor so function's here are "pure" and do not rely on DB import. This will avoid inline
# imports and circular imports

def save_data_to_csv(data, sensor_name):
    from server.models import get_sensor_timezone
    organized_data = defaultdict(dict)

    timezone_str = get_sensor_timezone(sensor_name)

    for timestamp, value, parameter, unit in data:
        organized_data[timestamp][f"{parameter} {f'({unit})' if unit else ''}"] = value

    # Create a DataFrame from the organized data
    df = pd.DataFrame.from_dict(organized_data, orient='index').reset_index()

    # Rename the first column to 'timestamp (timezone)'
    formatted_time = f"timestamp ({timezone_str})"
    df.rename(columns={'index': formatted_time}, inplace=True)

    # Convert the DataFrame to a CSV string
    csv_data = df.to_csv(index=False)
    sensor_name_line = f"Sensor Name: {sensor_name}\n"
    csv_data = sensor_name_line + csv_data

    return csv_data

def compress_image(base64_string, max_size=(800, 800), quality=70):
    """
    Accepts a base64 string, resizes/compresses it, and returns a new base64 string.
    """
    try:
        # Split header (e.g. "data:image/png;base64,") from data
        if ',' in base64_string:
            header, data = base64_string.split(',', 1)
        else:
            header = "data:image/jpeg;base64"  # Default assumption
            data = base64_string

        # Decode to bytes
        image_bytes = base64.b64decode(data)
        img = Image.open(io.BytesIO(image_bytes))

        #Fix orientation
        img = ImageOps.exif_transpose(img)

        # Convert to RGB (if PNG has transparency, this avoids errors saving as JPEG)
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")

        # Resize and save
        img.thumbnail(max_size)
        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", quality=quality)

        # Re-encode to Base64
        new_data = base64.b64encode(buffer.getvalue()).decode('utf-8')

        return f"data:image/jpeg;base64,{new_data}"

    except Exception as e:
        print(f"Image compression error: {e}")
        return base64_string  # Return original if compression fails

def get_measurement_summary(sensor_name, include_health=False):
    """
    Fetches the single most recent data this sensor has reported.
    Excludes sensor health related data
    """
    from server.models import get_sensor_by_name, get_most_recent
    sensor = get_sensor_by_name(sensor_name)
    if not sensor:
        return {"error": f"Sensor '{sensor_name}' not found"}

    recent_data = get_most_recent(sensor_name)

    if not recent_data:
        return {"message": f"No data available for sensor '{sensor_name}'"}

    summary_list = []

    for data_obj, p_name, p_unit in recent_data:
        if p_name == "latitude" or p_name == "longitude":
            continue
        summary_list.append({
            "parameter": f"{p_name} {f'({p_unit})' if p_unit else ''}",
            "value": data_obj.value,
            "timestamp": data_obj.timestamp
        })

    return {
        "sensor_name": sensor.name,
        "latitude": sensor.latitude,
        "longitude": sensor.longitude,
        "timezone": sensor.timezone,
        "most_recent_measurements": summary_list
    }


def create_map_markers(selected_sensor_name=None):
    """
    Generates map markers.
    If selected_sensor_name is provided, it zooms in on that sensor and makes it bigger.
    """
    from server.models import get_all_sensors
    sensors = get_all_sensors()
    markers = []

    # Default View (Whole Bay)
    map_center = [30.4, -87.8]
    map_zoom = 9

    for s in sensors:
        name = s.get('name', 'Unknown')
        lat = s.get('latitude')
        lon = s.get('longitude')
        s_type = s.get('device_type')
        is_active = s.get('active', False)

        if lat is None or lon is None:
            continue

        # Highlight Logic
        is_selected = (name == selected_sensor_name)

        if is_selected:
            map_center = [lat, lon]
            map_zoom = 12
            icon_opts = {
                "iconUrl": "/assets/buoy.svg",
                "iconSize": [60, 60],  # Highlighted = Big
                "iconAnchor": [30, 30],
                "popupAnchor": [0, -30]
            }
        else:
            icon_opts = {
                "iconUrl": "/assets/buoy.svg",
                "iconSize": [30, 30],  # Standard = Normal
                "iconAnchor": [15, 15],
                "popupAnchor": [0, -20]
            }

        # Popup Content
        status_color = "success" if is_active else "secondary"
        status_text = "Online" if is_active else "Offline"

        popup_content = dbc.Card([
            dbc.CardHeader(name, className=f"text-white bg-{status_color} p-2"),
            dbc.CardBody([
                html.P(f"Type: {s_type}", className="small mb-1"),
                html.P(f"Status: {status_text}", className="small mb-2 fw-bold"),

                dbc.Button(
                    "View Dashboard",
                    href=f"/dashboard?sensor={name}",  # Standardized Query String
                    size="sm",
                    color="primary",
                    className="w-100"
                )
            ], className="p-2")
        ], className="border-0", style={"minWidth": "200px"})

        markers.append(
            dl.Marker(
                position=[lat, lon],
                title=name,
                children=[
                    dl.Popup(popup_content, closeButton=False)
                ],
                icon=icon_opts
            )
        )

    return markers, map_center, map_zoom

def create_instructions_card():
    # Fetch fresh data every time the page loads
    from server.models import get_all_sensors
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

            s_type = s.get('device_type')

            # Determine Dot Color
            dot_class = "bi bi-circle-fill text-success" if s.get('active') else "bi bi-circle-fill text-secondary"

            item = dbc.ListGroupItem(
                html.A(
                    [
                        # The Status Dot
                        html.Div(
                            html.I(className=dot_class, style={"fontSize": "0.6rem"}),
                            className="me-3 d-flex align-items-center"
                        ),

                        # COLUMN 2: The Text Stack (Name + Type)
                        html.Div(
                            [
                                html.Span(s.get('name', 'Unknown'), className="fw-bold text-dark me-2",
                                          style={"fontSize": "0.9rem"}),
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
                                    title=f"Past Deployments ({len(offline_sensors)})",
                                    item_id="offline-item"
                                ),
                            ],
                            flush=True,
                            start_collapsed=True,
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
