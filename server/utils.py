import pandas as pd
import io
import base64
from PIL import Image, ImageOps
from collections import defaultdict
import dash_bootstrap_components as dbc
from dash import html
import dash_leaflet as dl
from dateutil.parser import parse as parse_date

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

    response = {
        "sensor_name": sensor.name,
        "latitude": sensor.latitude,
        "longitude": sensor.longitude,
        "timezone": sensor.timezone,
        "most_recent_measurements": [],
        "status": "offline"  # Default to offline
    }

    recent_data = get_most_recent(sensor_name)

    if not recent_data:
        response["message"] = f"No recent data for '{sensor_name}'"
        return response

    summary_list = []

    for data_obj, p_name, p_unit in recent_data:
        if p_name == "latitude" or p_name == "longitude":
            continue
        summary_list.append({
            "parameter": f"{p_name} {f'({p_unit})' if p_unit else ''}",
            "value": data_obj.value,
            "timestamp": data_obj.timestamp
        })

    response["most_recent_measurements"] = summary_list
    response["status"] = "online"  # Could add logic here to check if timestamp is < time (e.g. 2hours)

    return response


def get_deployment_statistics(sensor_name, deploy_data):
    """
    Takes a deployment dictionary, fetches the historical data,
    and returns duration, dates, and the mean of each parameter.
    """
    from server.models import get_data

    if not deploy_data:
        return {"error": "No deployment data provided."}

    stats = {
        "duration": deploy_data.get('duration', 'Unknown'),
        "range": deploy_data.get('range', ''),
        "latitude": deploy_data.get('latitude', 0),
        "longitude": deploy_data.get('longitude', 0),
        "averages": []
    }

    try:
        start_date = parse_date(deploy_data['start_iso'])
        end_date = parse_date(deploy_data['end_iso']) if deploy_data.get('end_iso') else None

        historic_data = get_data(sensor_name, start_date, end_date, lora=False)

        if not historic_data:
            return stats  # Averages list will just remain empty

        # 3. Calculate sums and counts for the means
        param_totals = {}
        param_counts = {}
        param_units = {}

        for row in historic_data:
            if row.name in ["latitude", "longitude"]:
                continue  # Skip coordinates

            param_totals[row.name] = param_totals.get(row.name, 0) + row.value
            param_counts[row.name] = param_counts.get(row.name, 0) + 1
            param_units[row.name] = row.unit

        for param, total in param_totals.items():
            avg_val = total / param_counts[param]
            stats["averages"].append({
                "parameter": param,
                "value": avg_val,
                "unit": param_units[param]
            })

    except Exception as e:
        print(f"Error calculating deployment statistics: {e}")
        stats["error"] = "Failed to calculate statistics."

    return stats

def create_map_markers(selected_sensor_name=None, show_inactive=False):
    """
    Generates map markers.
    If selected_sensor_name is provided, it zooms in on that sensor and makes it bigger.
    """
    from server.models import get_all_sensors
    sensors = get_all_sensors()
    markers = []

    # Default View (Whole Bay)
    map_center = [30.4, -87.95]
    map_zoom = 9.5

    for s in sensors:
        name = s.get('name', 'Unknown')
        lat = s.get('latitude')
        lon = s.get('longitude')
        s_type = s.get('device_type')
        is_active = s.get('active', False)
        is_online = s.get("is_online", False)

        # Highlight Logic
        is_selected = (name == selected_sensor_name)

        if not is_active and not show_inactive and not is_selected:
            continue

        if lat is None or lon is None:
            continue

        header_style = {}
        button_style = {"color": "white", "width": "100%"}

        if not is_active:
            status_text = "Deactivated"
            header_class = "text-white p-2"
            header_style = {"backgroundColor": "#b5b3b3"}
            button_color = "light"
            button_style.update({"backgroundColor": "#b5b3b3", "borderColor": "#b5b3b3"})
            marker_class = "inactive-marker"
        elif is_online:
            status_text = "Online"
            header_class = "text-white bg-primary p-2"
            button_color = "primary"
            marker_class = "online-marker"
        else:
            status_text = "Offline"
            header_class = "text-white bg-secondary p-2"
            button_color = "primary"
            marker_class = "offline-marker"

        if s_type == "tide_gauge":
            icon_file = "/assets/tide_gauge.svg"
        elif s_type == "wave_gauge":
            icon_file = "/assets/wave_gauge.svg"
        else:
            icon_file = "/assets/buoy.svg"

        #Set icon size
        if is_selected:
            map_center = [lat, lon]
            map_zoom = 12
            icon_size = [60, 60]
            icon_anchor = [30, 30]
            popup_anchor = [0, -30]
        else:
            icon_size = [30, 30]
            icon_anchor = [15, 15]
            popup_anchor = [0, -20]

        icon_opts = {
            "iconUrl": icon_file,
            "iconSize": icon_size,
            "iconAnchor": icon_anchor,
            "popupAnchor": popup_anchor,
            "className": marker_class
        }

        display_type = s_type.replace('_', ' ').title() if s_type else 'Unknown'

        popup_content = dbc.Card([
            dbc.CardHeader(name, className=header_class, style=header_style),
            dbc.CardBody([
                html.P(f"Type: {display_type}", className="small mb-1"),
                html.P(f"Status: {status_text}", className="small mb-2 fw-bold"),

                dbc.Button(
                    "View Dashboard",
                    href=f"/dashboard?sensor={name}",  # Standardized Query String
                    size="sm",
                    color=button_color,
                    className="w-100",
                    style=button_style
                )
            ], className="p-2")
        ], className="border-0", style={"minWidth": "200px"})

        markers.append(
            dl.Marker(
                position=[lat, lon],
                title=name,
                children=[
                    dl.Popup(popup_content, closeButton=False),
                ],
                icon=icon_opts
            )
        )

    return markers, map_center, map_zoom


def create_instructions_card():
    # Fetch fresh data every time the page loads
    from server.models import get_all_sensors
    sensors = get_all_sensors()

    # Filter sensors based on explicit user intent (Active vs Deactivated)
    active_sensors = [s for s in sensors if s.get('active', False)]
    deactivated_sensors = [s for s in sensors if not s.get('active', False)]

    # Helper function to create a stylish "Title + Subtitle" list
    def make_sensor_list(sensor_list):
        if not sensor_list:
            return html.Div("No sensors found.", className="text-muted small p-2")

        list_items = []
        for s in sensor_list:
            s_type = s.get('device_type')
            display_type = s_type.replace('_', ' ').title() if s_type else 'Unknown'
            name = s.get('name', 'Unknown')

            is_active = s.get('active', False)
            is_online = s.get('is_online', False)

            if not is_active:
                dot_class = "bi bi-circle-fill text-secondary"  # Gray for deactivated
            elif is_online:
                dot_class = "bi bi-circle-fill text-success"  # Green for online
            else:
                dot_class = "bi bi-circle-fill text-secondary"

            item = dbc.ListGroupItem(
                html.A(
                    [
                        # The Status Dot
                        html.Div(
                            html.I(className=dot_class, style={"fontSize": "0.6rem"}),
                            className="me-3 d-flex align-items-center"
                        ),

                        # COLUMN 2: The Text Stack (Name + Type) - Reverted to your original style!
                        html.Div(
                            [
                                html.Span(name, className="fw-bold text-dark me-2",
                                          style={"fontSize": "0.9rem"}),
                                html.Span(f"({display_type})", className="text-muted small",
                                          style={"fontSize": "0.75rem", "paddingTop": "2px"})
                            ],
                            className="d-flex align-items-center flex-wrap"
                        )
                    ],
                    # Link setup
                    href=f"/dashboard?sensor={name}",
                    className="text-decoration-none d-flex align-items-center w-100"
                ),
                className="p-2 border-0 border-bottom sensor-list-item",
                action=True
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
                style={"cursor": "move"}
            ),

            # Collapsible Body
            dbc.Collapse(
                dbc.CardBody(
                    [
                        dbc.Accordion(
                            [
                                dbc.AccordionItem(
                                    make_sensor_list(active_sensors),
                                    title=f"Active ({len(active_sensors)})",
                                    item_id="active-item"
                                ),
                                dbc.AccordionItem(
                                    [
                                        dbc.Row(
                                            [
                                                dbc.Col(html.Span("Show on Map",
                                                                  className="small text-muted fw-bold",
                                                                  style={"fontSize": "10px"}),
                                                        className="p-0"
                                                        ),
                                                dbc.Col(
                                                    dbc.Switch(
                                                        id="show-inactive-switch",
                                                        value=False,
                                                        className="d-flex justify-content-end",
                                                        style={"minHeight": "unset"}
                                                    )
                                                )
                                            ],
                                            className="mb-2 g-0 border-bottom pb-2 align-items-center mx-1",
                                            style={"marginTop": "-15px", "paddingTop": "0px"}
                                        ),
                                        # The list of deactivated sensors follows the toggle
                                        make_sensor_list(deactivated_sensors)
                                    ],
                                    title=f"Deactivated ({len(deactivated_sensors)})",
                                    item_id="offline-item"
                                ),
                            ],
                            flush=True,
                            start_collapsed=True,
                            always_open=True,
                            className="sensor-accordion"
                        )
                    ],
                    className="p-0"
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
            "width": "300px",
            "zIndex": "1050",
            "boxShadow": "0 4px 12px rgba(0,0,0,0.15)",
            "maxHeight": "80vh",
            "overflowY": "auto"
        },
    )
