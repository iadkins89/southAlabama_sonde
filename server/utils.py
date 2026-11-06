import os
import pandas as pd
import io
import base64
from PIL import Image, ImageOps
from collections import defaultdict
import dash_bootstrap_components as dbc
from dash import dcc, html
import dash_leaflet as dl
from dateutil.parser import parse as parse_date

BATTERY_MIN_V = 3.4  # Where the health panel's battery bar starts


def parameter_label(parameter):
    if parameter.lower() == "ph":
        return "pH"
    return parameter.replace("_", " ").capitalize()


def sensor_label(sensor_name):
    return sensor_name.replace("_", " ").title()


def device_type_label(device_type):
    return device_type.replace("_", " ").title() if device_type else "Sensor"


def display_decimals(parameter):
    # Tides here are a few tenths of a metre, which 1 decimal would flatten.
    return 3 if parameter.startswith("water_level") else 1


def sensor_state(sensor):
    if not sensor.get('active', False):
        return "deactivated"
    return "online" if sensor.get('is_online', False) else "offline"


def upload_preview(image_data):
    """What a photo upload box shows: the chosen image, or the prompt if there is none."""
    box = {"width": "100%", "borderWidth": "1px", "borderRadius": "5px", "textAlign": "center", "margin": "10px 0"}

    if not image_data:
        return (html.Div(["Drag and Drop or ", html.A("Select an Image File")]),
                {**box, "height": "80px", "lineHeight": "80px", "borderStyle": "dashed"})

    return (html.Img(src=image_data, alt="Sensor photo preview", style={"maxHeight": "100%", "maxWidth": "100%"}),
            {**box, "height": "300px", "borderStyle": "solid", "display": "flex", "alignItems": "center",
             "justifyContent": "center", "overflow": "hidden"})


def relative_time(moment):
    """A time that assets/app.js keeps up to date, such as "5 min ago"."""
    return html.Span(moment.strftime("%b %d, %H:%M UTC"), **{"data-time": moment.isoformat() + "Z"})

CARTO_API_KEY = os.environ.get("CARTO_API_KEY")


def get_carto_tile_url():
    """
    Returns the CARTO Voyager raster tile URL, appending the API key
    (required as of CARTO's raster basemap changes) when one is configured.
    """
    base_url = "https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png"
    return f"{base_url}?key={CARTO_API_KEY}" if CARTO_API_KEY else base_url

# from server.models import get_sensor_timezone, get_sensor_by_name, get_most_recent, get_all_sensors
# TO DO: Refactor so function's here are "pure" and do not rely on DB import. This will avoid inline
# imports and circular imports

def save_data_to_csv(data, sensor_name):
    from server.models import get_sensor_by_name, get_sensor_timezone, get_locations_for_range
    organized_data = defaultdict(dict)

    timezone_str = get_sensor_timezone(sensor_name)

    for row in data:
        organized_data[row.timestamp][f"{row.name} {f'({row.unit})' if row.unit else ''}"] = row.value
        if row.qc_flag is not None:
            organized_data[row.timestamp][f"{row.name} QARTOD flag"] = row.qc_flag

    # Create a DataFrame from the organized data
    df = pd.DataFrame.from_dict(organized_data, orient='index').reset_index()

    # Timestamps are stored in UTC. Show them in the sensor's own timezone.
    df['index'] = (pd.to_datetime(df['index'], utc=True).dt.tz_convert(timezone_str)
                   .dt.strftime('%Y-%m-%d %H:%M:%S'))

    # Rename the first column to 'timestamp (timezone)'
    formatted_time = f"timestamp ({timezone_str})"
    df.rename(columns={'index': formatted_time}, inplace=True)

    # Convert the DataFrame to a CSV string
    csv_data = df.to_csv(index=False)
    header = f"Sensor Name: {sensor_name}\n"

    # Use where the sensor was during this data, which may not be where it is now
    sensor = get_sensor_by_name(sensor_name)
    times = [row.timestamp for row in data]
    locations = get_locations_for_range(sensor, min(times), max(times))

    if len(locations) > 1:
        for number, loc in enumerate(locations, start=1):
            end = loc.removed_at.strftime('%Y-%m-%d') if loc.removed_at else 'present'
            header += (f"Location {number}: {loc.latitude}, {loc.longitude} "
                       f"({loc.deployed_at.strftime('%Y-%m-%d')} to {end})\n")
    else:
        latitude = locations[0].latitude if locations else sensor.latitude
        longitude = locations[0].longitude if locations else sensor.longitude
        header += f"Latitude: {latitude}\nLongitude: {longitude}\n"

    return header + csv_data

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
            "name": p_name,
            "unit": p_unit,
            "parameter": f"{p_name} {f'({p_unit})' if p_unit else ''}",
            "value": data_obj.value,
            "timestamp": data_obj.timestamp
        })

    response["most_recent_measurements"] = summary_list
    response["status"] = "online"

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

def create_map_markers(selected_sensor_name=None, show_inactive=False, hide_selected=False):
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

        if is_selected and hide_selected:
            continue

        if not is_active and not show_inactive and not is_selected:
            continue

        if lat is None or lon is None:
            continue

        if not is_active:
            status_text = "Deactivated"
            marker_class = "inactive-marker"
        elif is_online:
            status_text = "Online"
            marker_class = "online-marker"
        else:
            status_text = "Offline"
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

        last_report = s.get('last_report')
        popup_content = html.Div([
            html.Div([html.Span(className=f"status-dot status-{sensor_state(s)}"), sensor_label(name)],
                     className="map-popup-title"),
            html.Div(f"{display_type} \u00B7 {status_text}", className="map-popup-meta"),
            html.Div(["Last report ", relative_time(last_report)] if last_report else "No data yet",
                     className="map-popup-meta"),
            # Set here because Leaflet recolors every link inside a popup
            dcc.Link("View Dashboard", href=f"/dashboard?sensor={name}", className="map-popup-link",
                     style={"color": "#ffffff", "backgroundColor": "#0b3d63"}),
        ], className="map-popup")

        markers.append(
            dl.Marker(
                # A new id per selected sensor closes any popup left open by the last one
                id={"type": "sensor-marker", "selected": selected_sensor_name or "", "name": name},
                position=[lat, lon],
                title=name,
                children=[
                    dl.Popup(popup_content, closeButton=False),
                ],
                icon=icon_opts
            )
        )

    return markers, map_center, map_zoom


def sensor_row(sensor):
    """One sensor in the home page list, with its status and newest reading."""
    from server.models import get_most_recent

    name = sensor['name']
    type_label = device_type_label(sensor.get('device_type'))
    state = sensor_state(sensor)
    last_report = sensor.get('last_report')

    # Deactivated sensors have no current readings to show. assets/app.js cycles through these.
    readings = []
    if sensor.get('active'):
        rows = [row for row in get_most_recent(name) if row[1] not in ("latitude", "longitude")]
        for i, (data, parameter, unit) in enumerate(sorted(rows, key=lambda row: row[1].lower())):
            value = round(data.value, display_decimals(parameter))
            text = f"{parameter_label(parameter)} {value} {unit or ''}".strip()
            # Hidden here, not in the stylesheet, so that a stale stylesheet can't show them all
            readings.append(html.Div(text, className="sensor-row-reading",
                                     style={} if i == 0 else {"display": "none"}))

    row = dcc.Link(
        [
            html.Span(className=f"status-dot status-{state}"),
            html.Div(
                [
                    html.Div(sensor_label(name), className="sensor-row-name"),
                    html.Div(
                        [f"{type_label} \u00B7 ",
                         relative_time(last_report) if last_report else "No data yet"],
                        className="sensor-row-meta"
                    ),
                ],
                className="sensor-row-text"
            ),
            html.Div(readings, className="sensor-row-value") if readings else None,
        ],
        href=f"/dashboard?sensor={name}",
        className="sensor-row",
    )
    return html.Div(row, **{"data-search": f"{name} {type_label}".replace("_", " ").lower()})


def create_instructions_card():
    from server.models import get_network_summary
    network = get_network_summary()
    sensors = network['sensors']

    # Filter sensors based on explicit user intent (Active vs Deactivated)
    active_sensors = [s for s in sensors if s.get('active', False)]
    deactivated_sensors = [s for s in sensors if not s.get('active', False)]
    active_sensors.sort(key=lambda s: (not s.get('is_online', False), s['name']))

    def make_sensor_list(sensor_list):
        if not sensor_list:
            return html.Div("No sensors here yet.", className="sensor-list-empty")
        return html.Div([sensor_row(s) for s in sensor_list], className="sensor-list")

    def stat(value, label):
        return html.Div([html.Div(value, className="network-stat-value"),
                         html.Div(label, className="network-stat-label")], className="network-stat")

    latest = network['latest_report']

    return dbc.Card(
        [
            dbc.CardHeader(
                html.Div([
                    html.Div([
                        html.Div("Sensor network", className="network-title"),
                        html.Div("Live coastal monitoring", className="network-subtitle"),
                    ]),

                    # Toggle Button
                    dbc.Button(
                        "\u25B2",
                        id="toggle-instructions",
                        color="link",
                        size="sm",
                        className="network-toggle",
                    )
                ], className="d-flex justify-content-between align-items-center"),
            ),

            # Collapsible Body
            dbc.Collapse(
                dbc.CardBody(
                    [
                        html.Div(
                            [
                                stat(f"{network['online']} of {network['active']}", "Reporting"),
                                stat(f"{network['reports_24h']:,}", "Reports, last 24 h"),
                                stat(relative_time(latest) if latest else "\u2014", "Latest report"),
                            ],
                            className="network-stats"
                        ),
                        html.Div(
                            [html.I(className="bi bi-search"),
                             dcc.Input(id="sensor-filter", type="text", placeholder="Filter sensors",
                                       className="sensor-filter-input", debounce=False)],
                            className="sensor-filter"
                        ),
                        dbc.Accordion(
                            [
                                dbc.AccordionItem(
                                    make_sensor_list(active_sensors),
                                    title=f"Active ({len(active_sensors)})",
                                    item_id="active-item"
                                ),
                                dbc.AccordionItem(
                                    [
                                        html.Div(
                                            [
                                                html.Span("Show on map"),
                                                dbc.Switch(id="show-inactive-switch", value=False,
                                                           className="m-0")
                                            ],
                                            className="inactive-switch-row"
                                        ),
                                        # The list of deactivated sensors follows the toggle
                                        make_sensor_list(deactivated_sensors)
                                    ],
                                    title=f"Deactivated ({len(deactivated_sensors)})",
                                    item_id="offline-item"
                                ),
                            ],
                            id="sensor-accordion",
                            flush=True,
                            always_open=True,
                            start_collapsed=True,  # Desktop opens Active, see callbacks/clientside.py
                            className="sensor-accordion"
                        ),
                    ],
                    className="p-0"
                ),
                id="instructions-body",
                is_open=False,  # Desktop opens it, see callbacks/clientside.py
            ),
        ],
        id="instructions-card",
        className="network-card",
    )
