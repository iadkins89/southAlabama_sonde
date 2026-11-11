from dash import callback, Input, Output, State, html, dcc, ALL, MATCH, ctx, no_update
from dash.exceptions import PreventUpdate
import dash_bootstrap_components as dbc
import plotly.graph_objs as go
from datetime import datetime, timedelta
from server.utils import (BATTERY_MIN_V, device_type_label, marker_icon, display_decimals, parameter_label, relative_time,
                          sensor_label)
from server.utils import save_data_to_csv, get_measurement_summary,create_map_markers, get_deployment_statistics
from server.models import (get_data,
                           get_sensor_timezone,
                           get_sensor_by_name,
                           get_most_recent,
                           get_past_deployments,
                           get_qc_counts)
import pytz
from dateutil.parser import parse as parse_date
import dash_leaflet as dl
from server.qc import FAIL, NOT_EVALUATED, PASS, SUSPECT
from urllib.parse import quote
from flask import session

# Longer than this between water levels draws as a break in the line, not a bridge.
GAUGE_GAP = timedelta(minutes=15)
LIVE_COLOR = "#dc3545"
LINE_COLOR = "#0e8f8a"
SUSPECT_COLOR = "#e8710a"
TREND_WINDOW = timedelta(hours=1)
TREND_MIN_SPAN = timedelta(minutes=30)
TREND_MIN_READINGS = 4  # A sonde reports every 15 minutes, so 5 is a full hour
TIDE_STEADY_M = 0.005  # Provisional, over the hour, until field data sets the noise floor

TYPE_ICONS = {"tide_gauge": "bi-water", "wave_gauge": "bi-tsunami", "sonde": "bi-droplet-half"}

# The 1 year view sends each block's low and high instead of every reading, until
# a zoom brings the span down to this length.
THIN_BLOCKS = 1000
SPARKLINE_BLOCKS = 60
SPARKLINE_GAP = timedelta(hours=1)  # Sondes report less often than gauges, so a break needs a longer gap
THIN_ABOVE = timedelta(days=31)
PAST_DEPLOYMENT_THIN_ABOVE = timedelta(days=180)
PLAYBACK_DEFAULT = timedelta(days=30)  # How much of a past deployment shows at first


# LoRa decodes signals far weaker than most radios, even below the noise floor (negative SNR).
RSSI_BAR_MIN = -130
RSSI_BAR_MAX = -50
RSSI_GOOD_ABOVE = -100
RSSI_POOR_BELOW = -115
SNR_GOOD_ABOVE = -5
SNR_POOR_BELOW = -15
BOARD_TEMP_BAR_MIN = -20
BOARD_TEMP_BAR_MAX = 80
BOARD_TEMP_WARM = 55
BOARD_TEMP_HOT = 70
BOARD_TEMP_COLD = -10


def can_view(sensor_name):
    """A test device is shown only to signed-in users. Callbacks can be called directly, so each checks."""
    sensor = get_sensor_by_name(sensor_name) if sensor_name else None
    return not (sensor and sensor.testing and not session.get('user_logged_in'))


def signal_color(value, good_above, poor_below):
    if value > good_above:
        return "success"
    if value >= poor_below:
        return "warning"
    return "danger"


def board_temp_bar(temperature):
    """How full the bar is, and its color. The limits are starting estimates."""
    span = BOARD_TEMP_BAR_MAX - BOARD_TEMP_BAR_MIN
    percent = max(0, min(100, int((temperature - BOARD_TEMP_BAR_MIN) * 100 / span)))
    if temperature > BOARD_TEMP_HOT or temperature < BOARD_TEMP_COLD:
        return percent, "danger"
    if temperature > BOARD_TEMP_WARM:
        return percent, "warning"
    return percent, "success"


def format_location(latitude, longitude):
    # The letter replaces the sign, since -88.0°W would read as east.
    if latitude is None or longitude is None:
        return "Location unavailable"
    north_south = "N" if latitude >= 0 else "S"
    east_west = "W" if longitude < 0 else "E"
    return f"{abs(latitude)}\u00B0{north_south}   {abs(longitude)}\u00B0{east_west}"


def sparkline_src(timestamps, values, max_gap, width=120, height=30):
    """
    A small trend line, as an image so that a tile stays light. Points sit by their
    real time, and thin_line keeps each block's low and high, the newest reading
    and a break at every outage.
    """
    span = (timestamps[-1] - timestamps[0]).total_seconds() if len(timestamps) > 1 else 0
    if not span:
        return None

    low, high = min(values), max(values)
    range_of_values = (high - low) or 1

    path = []
    start_new_stretch = True
    for moment, value in zip(*thin_line(timestamps, values, max_gap, blocks=SPARKLINE_BLOCKS)):
        if value is None:
            start_new_stretch = True
            continue
        x = (moment - timestamps[0]).total_seconds() / span * width
        y = height - 2 - (value - low) / range_of_values * (height - 4)
        path.append(f"{'M' if start_new_stretch else 'L'}{x:.1f} {y:.1f}")
        start_new_stretch = False

    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" preserveAspectRatio="none">'
           f'<path d="{" ".join(path)}" fill="none" stroke="{LINE_COLOR}" stroke-width="2" '
           'stroke-linejoin="round" stroke-linecap="round" vector-effect="non-scaling-stroke"/></svg>')
    return "data:image/svg+xml," + quote(svg)


def trend_start(latest, deploy_data):
    """A tile's trend covers the last 24 hours, but never reaches past the current deployment."""
    start = latest - timedelta(hours=24)
    if deploy_data and deploy_data.get('is_current', False):
        start = max(start, parse_date(deploy_data['start_iso']))
    return start


def hourly_change(timestamps, values):
    """
    How much a reading changed over the last hour, and the minutes that covers.
    It comes from a line through every reading, so one noisy reading can't decide
    it. None if the hour holds too little data to fit a line.
    """
    window_start = timestamps[-1] - TREND_WINDOW
    recent = [(t, v) for t, v in zip(timestamps, values) if t >= window_start]
    if len(recent) < TREND_MIN_READINGS:
        return None

    seconds = [(t - recent[0][0]).total_seconds() for t, _ in recent]
    if seconds[-1] < TREND_MIN_SPAN.total_seconds():
        return None

    levels = [v for _, v in recent]
    mean_seconds = sum(seconds) / len(seconds)
    mean_level = sum(levels) / len(levels)
    slope = (sum((x - mean_seconds) * (y - mean_level) for x, y in zip(seconds, levels))
             / sum((x - mean_seconds) ** 2 for x in seconds))

    return slope * seconds[-1], seconds[-1] / 60


def tide_trend(change):
    """Just after high or low water this lags, because the hour still holds the tide before the turn."""
    if abs(change) < TIDE_STEADY_M:
        return "Steady"
    return "Rising" if change > 0 else "Falling"


def change_line(change, minutes, decimals, unit):
    # Readings 6 minutes apart span 54 to 60 minutes, which is still the last hour
    period = "last hour" if minutes >= 50 else f"last {round(minutes)} min"
    if round(change, decimals) == 0:
        return html.Div([html.I(className="bi bi-arrow-right"), f"No net change in {period}"],
                        className="reading-change")
    arrow = "bi-arrow-up-right" if change > 0 else "bi-arrow-down-right"
    amount = f"{change:+.{decimals}f} {unit or ''}".strip()
    return html.Div([html.I(className=f"bi {arrow}"), f"{amount} in {period}"], className="reading-change")


def reading_tile(label, value, unit, values=None, timestamps=None, is_water_level=False):
    sparkline = None
    hourly = None
    if values and len(values) > 1:
        sparkline = sparkline_src(timestamps, values, GAUGE_GAP if is_water_level else SPARKLINE_GAP)
        hourly = hourly_change(timestamps, values)

    trend = tide_trend(hourly[0]) if is_water_level and hourly else None

    return html.Div(
        [
            html.Div([html.Span(label),
                      html.Span(f"{trend}, last hour", className="reading-direction") if trend else None],
                     className="reading-label"),
            html.Div([value, html.Span(f" {unit}" if unit else "", className="reading-unit")],
                     className="reading-value"),
            html.Img(src=sparkline, className="reading-sparkline", alt="") if sparkline else None,
            change_line(*hourly, 3 if is_water_level else 1, unit) if hourly else None,
        ],
        className="reading-tile"
    )


def quality_panel(sensor_name):
    """The QC results behind the graph, in plain words. Empty until a sensor has QC."""
    counts = get_qc_counts(sensor_name)
    total = sum(counts.values())
    if not total:
        return None

    groups = [
        (PASS, "Passed", "pass", "bi-check-circle-fill"),
        (NOT_EVALUATED, "Not evaluated", "unknown", "bi-dash-circle-fill"),
        (SUSPECT, "Suspect", "suspect", "bi-exclamation-diamond-fill"),
        (FAIL, "Failed", "fail", "bi-x-circle-fill"),
    ]
    shown = [(counts.get(flag, 0), label, key, icon) for flag, label, key, icon in groups if counts.get(flag)]

    return html.Div(
        [
            html.Div([html.Span("Data quality"), html.Span("Last 7 days of QARTOD checks", className="quality-note")],
                     className="quality-title"),
            html.Div(
                [html.Div(className=f"quality-segment quality-{key}", style={"flexGrow": count})
                 for count, _, key, _ in shown],
                className="quality-bar"
            ),
            html.Div(
                [html.Div([html.I(className=f"bi {icon} quality-icon-{key}"), f"{label} {count / total:.1%}"],
                          className="quality-item", title=f"{count:,} readings")
                 for count, label, key, icon in shown],
                className="quality-legend"
            ),
            html.Div("Failed readings stay out of the graphs but remain in CSV downloads.", className="quality-foot")
            if counts.get(FAIL) else None,
            html.Div("Using initial QC limits.", className="quality-foot"),
        ],
        className="quality-panel"
    )


def break_line_at_gaps(timestamps, values, max_gap):
    x, y = [], []
    for i, (timestamp, value) in enumerate(zip(timestamps, values)):
        if i > 0 and timestamp - timestamps[i - 1] > max_gap:
            x.append(timestamp)
            y.append(None)
        x.append(timestamp)
        y.append(value)
    return x, y


def thin_stretch(timestamps, values, first, last, origin, block_width):
    """The positions of one unbroken stretch that are worth keeping, in time order."""
    lows, highs = {}, {}
    for i in range(first, last + 1):
        block = int((timestamps[i] - origin) / block_width)
        if block not in lows or values[i] < values[lows[block]]:
            lows[block] = i
        if block not in highs or values[i] > values[highs[block]]:
            highs[block] = i
    return sorted({first, last, *lows.values(), *highs.values()})


def thin_line(timestamps, values, max_gap=None, blocks=THIN_BLOCKS):
    """
    Reduces a line to each time block's low and high, so peaks survive. Gaps are
    found first, because the kept points are far apart even with no gap.
    """
    origin = timestamps[0]
    block_width = (timestamps[-1] - origin) / blocks

    x, y = [], []
    first = 0
    for i in range(1, len(timestamps) + 1):
        if i < len(timestamps) and not (max_gap and timestamps[i] - timestamps[i - 1] > max_gap):
            continue
        if x:
            x.append(timestamps[first])
            y.append(None)
        for kept in thin_stretch(timestamps, values, first, i - 1, origin, block_width):
            x.append(timestamps[kept])
            y.append(values[kept])
        first = i
    return x, y


# ----------------------------
# Time series graphs
# ----------------------------
def is_year_view(radio, deploy_data):
    # A past deployment hides the range buttons and uses the slider instead.
    return radio == "1-year" and not (deploy_data and not deploy_data.get('is_current', False))


def uses_thinning(radio, slider, deploy_data):
    if is_year_view(radio, deploy_data):
        return True
    if deploy_data and not deploy_data.get('is_current', False):
        start, end = graph_window(radio, slider, deploy_data)
        return end - start > PAST_DEPLOYMENT_THIN_ABOVE
    return False


def graph_window(radio, slider, deploy_data):
    if deploy_data and not deploy_data.get('is_current', False):
        return datetime.fromtimestamp(slider[0]), datetime.fromtimestamp(slider[1])

    end = datetime.utcnow()
    days = {"2-days": 2, "1-week": 7, "1-month": 30, "1-year": 365}.get(radio, 2)
    start = end - timedelta(days=days)

    if deploy_data and deploy_data.get('is_current', False):
        # Parse the actual start date of the CURRENT deployment
        deploy_start = parse_date(deploy_data['start_iso'])

        # If the calculated start date is older than the deployment, clamp it
        if start < deploy_start:
            start = deploy_start

    return start, end


def load_series(sensor_name, start, end, only_parameter=None, localize_input=False):
    """Returns the graphed values per parameter, in time order and in the sensor's standard time."""
    data = get_data(sensor_name, start, end, lora=False, localize_input=localize_input)

    target_tz = get_sensor_timezone(sensor_name)

    series = {}
    for row in data:
        parameter = row.name
        if parameter in ("longitude", "latitude"):
            continue
        if only_parameter and parameter != only_parameter:
            continue
        if parameter not in series:
            series[parameter] = {"timestamps": [], "values": [], "flags": [], "unit": row.unit}
        series[parameter]["timestamps"].append(row.timestamp.replace(tzinfo=pytz.utc).astimezone(target_tz))
        series[parameter]["values"].append(row.value)
        series[parameter]["flags"].append(row.qc_flag)

    for values in series.values():
        sorted_data = sorted(zip(values["timestamps"], values["values"], values["flags"]), key=lambda x: x[0])
        values["timestamps"], values["values"], values["flags"] = zip(*sorted_data)

    return series


def build_figure(sensor_name, parameter, values, radio, thin, show_live):
    timestamps, readings, unit = values["timestamps"], values["values"], values["unit"]
    min_y = min(readings)
    max_y = max(readings)
    y_padding = (max_y - min_y) * 0.2

    trace_data = []
    is_water_level = parameter == "water_level"
    hover_format = ".3f" if is_water_level else ".2f"
    max_gap = GAUGE_GAP if is_water_level else None
    thin = thin and timestamps[-1] - timestamps[0] > THIN_ABOVE

    if thin:
        line_x, line_y = thin_line(timestamps, readings, max_gap)
    elif is_water_level:
        line_x, line_y = break_line_at_gaps(timestamps, readings, max_gap)
    else:
        line_x, line_y = timestamps, readings

    # NAVD88 levels can cross zero, so filling down to zero would mislead.
    area_style = {} if is_water_level else {"fill": "tozeroy", "fillcolor": "rgba(14, 143, 138, 0.10)"}  # Area chart style

    # Hover shows the nearest point of every trace, so a tooltip on the markers
    # would also appear on the readings beside them. The line reports it instead.
    suspect_points = [(t, v) for t, v, flag in zip(timestamps, readings, values["flags"]) if flag == SUSPECT]
    suspect_times = {t for t, _ in suspect_points}

    trace_data.append(go.Scatter(
        x=line_x,
        y=line_y,
        customdata=[" (suspect)" if t in suspect_times else "" for t in line_x],
        mode="lines",
        name="History",
        # A curve through alternating lows and highs would overshoot both.
        line={"color": LINE_COLOR, "width": 1 if thin else 2,
              **({} if thin else {"shape": "spline", "smoothing": 0.3})},
        # <extra></extra> = removes the side box (name/icon)
        hovertemplate=f'%{{y:{hover_format}}} {unit}%{{customdata}}<extra></extra>',
        **area_style
    ))

    if suspect_points:
        suspect_x, suspect_y = zip(*suspect_points)
        trace_data.append(go.Scatter(
            x=suspect_x,
            y=suspect_y,
            mode="markers",
            name="Suspect",
            marker={"color": SUSPECT_COLOR, "size": 9, "symbol": "diamond",
                    "line": {"width": 1, "color": "white"}},
            hoverinfo="skip"
        ))

    # Live Indicator (Only if active). dashboard_styles.css blinks points in LIVE_COLOR,
    # and the halo must share that color to blink with the dot.
    if show_live:
        last_time = timestamps[-1]
        last_val = readings[-1]
        trace_data.append(go.Scatter(
            x=[last_time], y=[last_val], mode="markers",
            marker={"color": LIVE_COLOR, "opacity": 0.3, "size": 25, "line": {"width": 0}},
            hoverinfo="skip"
        ))
        trace_data.append(go.Scatter(
            x=[last_time], y=[last_val], mode="markers",
            marker={"color": LIVE_COLOR, "size": 12, "line": {"width": 2, "color": "white"}},
            hoverinfo="skip"  # The Line tooltip already covers this point.
        ))

    return {
        "data": trace_data,
        "layout": go.Layout(
            uirevision=f"{sensor_name}-{radio}",  # Keeps a zoom until the range changes
            template="plotly_white",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font={"family": "Inter, sans-serif", "size": 12, "color": "#5b6b7a"},
            xaxis={"showgrid": False, "linecolor": "#dbe2e9", "showline": True, "automargin": True},
            yaxis={
                "range": [min_y - y_padding, max_y + y_padding],
                "showgrid": True, "gridcolor": "#edf1f5", "zeroline": False, "automargin": True,
            },
            margin={"l": 8, "r": 16, "t": 8, "b": 8},
            height=260,
            showlegend=False,
            hovermode="x unified"  # vertical line hover
        )
    }


@callback(
    Output('multi-sensor-graph', 'children'),
    [
        Input("date-range-radio", "value"),
        Input("historic-date-slider", "value"),
        Input("sensor-name-store", "data"),
        Input("selected-deployment-store", "data"),
        Input("live-sensor-data", "data")
    ]
)
def update_multi_sensor_graph(radio, slider, sensor_name, deploy_data, live_data):
    if not can_view(sensor_name):
        raise PreventUpdate

    if not sensor_name:
        return html.Div("No sensor selected.")

    # One new reading can't be seen at this scale, and redrawing would undo a zoom.
    year_view = is_year_view(radio, deploy_data)
    if year_view and ctx.triggered_id == "live-sensor-data":
        raise PreventUpdate

    start, end = graph_window(radio, slider, deploy_data)
    series = load_series(sensor_name, start, end)

    if not series:
        return dbc.Col(html.Div(
            [html.Div(html.I(className="bi bi-calendar-x"), className="empty-icon"),
             html.Div("No readings in this range", className="empty-title"),
             html.Div("Try a longer range, or check back after the sensor's next report.", className="empty-text")],
            className="surface-card empty-state"
        ), xs=12)

    is_active = get_sensor_by_name(sensor_name).is_online
    thin = uses_thinning(radio, slider, deploy_data)

    graphs = []
    for parameter, values in series.items():
        suspect_count = sum(flag == SUSPECT for flag in values["flags"])
        unit = values["unit"]
        heading = html.Div(
            [
                html.Div([parameter_label(parameter), html.Span(f" {unit}" if unit else "", className="graph-unit")],
                         className="graph-title"),
                html.Div([html.I(className="bi bi-diamond-fill"), f"{suspect_count} suspect"], className="graph-chip")
                if suspect_count else None,
            ],
            className="graph-head"
        )
        graph = dcc.Graph(
            id={"type": "sensor-graph", "parameter": parameter},
            figure=build_figure(sensor_name, parameter, values, radio, thin=thin, show_live=is_active),
            config={
                "responsive": True,
                'displayModeBar': False,
                'displaylogo': False
            },
        )
        graphs.append(dbc.Col(html.Div([heading, graph], className="surface-card graph-card"),
                              xs=12, lg=6 if len(series) > 1 else 12))
    return graphs


@callback(
    Output({"type": "sensor-graph", "parameter": MATCH}, "figure"),
    Input({"type": "sensor-graph", "parameter": MATCH}, "relayoutData"),
    [State("date-range-radio", "value"),
     State("historic-date-slider", "value"),
     State("sensor-name-store", "data"),
     State("selected-deployment-store", "data")],
    prevent_initial_call=True
)
def reload_year_graph_on_zoom(relayout, radio, slider, sensor_name, deploy_data):
    if not can_view(sensor_name):
        raise PreventUpdate
    if not relayout or not uses_thinning(radio, slider, deploy_data):
        raise PreventUpdate

    parameter = ctx.triggered_id["parameter"]

    if relayout.get("xaxis.autorange"):  # Double click: back to the whole year
        start, end = graph_window(radio, slider, deploy_data)
        series = load_series(sensor_name, start, end, parameter)
        show_live = get_sensor_by_name(sensor_name).is_online
    elif "xaxis.range[0]" in relayout:
        # The axis shows the sensor's standard time
        start = parse_date(relayout["xaxis.range[0]"])
        end = parse_date(relayout["xaxis.range[1]"])
        series = load_series(sensor_name, start, end, parameter, localize_input=True)
        show_live = False  # The last point on screen may be months old
    else:
        raise PreventUpdate

    if parameter not in series:
        raise PreventUpdate

    return build_figure(sensor_name, parameter, series[parameter], radio, thin=True, show_live=show_live)

# ----------------------------
# File download
# ----------------------------
@callback(
    Output("download-data-offcanvas", "is_open"),
    Input("download-button", "n_clicks"),
    [State("download-data-offcanvas", "is_open")],
)
def toggle_download_data_offcanvas(n_clicks, is_open):
    if n_clicks:
        return not is_open
    return is_open

@callback(
    [Output('confirm-dialog', 'displayed'),
    Output('confirm-dialog', 'message'),
    Output('download-dataframe-csv', 'data'),],
    [Input("set-filename-btn", 'n_clicks'),
     Input('sensor-name-store', 'data')],
    [State('date-picker-range', 'start_date'),
     State('date-picker-range', 'end_date'),
     State('csv-filename', 'value'),
     State('radio-data-item', 'value')]
)
def file_download(n_clicks, sensor_name, start_date, end_date, filename, data_type):
    if not can_view(sensor_name):
        raise PreventUpdate
    if n_clicks is None:
        raise PreventUpdate
    else:
        #Convert dates from string to date_time object and set hr/min/sec to get full days
        start_date = parse_date(start_date).replace(hour=0, minute=0, second=0)
        end_date = parse_date(end_date).replace(hour=23, minute=59, second=59)

        if not start_date or not end_date:
            return True, 'Please provide a valid date range and filename.', None
        if not filename:
            return True, 'Please provide a valid filename.', None

        if data_type == "   Sensor Data":
            data = get_data(sensor_name, start_date, end_date, lora=False, localize_input=True,
                            include_failed=True)
        else:
            data = get_data(sensor_name, start_date, end_date, lora=True, localize_input=True)

        if not data:
            return True, 'No data found for the given date range.', None

        saved_csv_file = save_data_to_csv(data, sensor_name)
        return False, '', dict(content=saved_csv_file, filename=f"{filename}.csv")
    return False, '', None

# ----------------------------
# Sensor health
# ----------------------------
@callback(
    Output("sensor-health-offcanvas", "is_open"),
    Input("sensor-health-button", "n_clicks"),
    [State("sensor-health-offcanvas", "is_open")],
)
def toggle_sensor_health_offcanvas(n_clicks, is_open):
    if n_clicks:
        return not is_open
    return is_open

@callback(
    [Output("battery-gauge", "value"),
     Output("battery-value", "children"),
     Output("battery-gauge", "color"),
     Output("rssi-progress", "value"),
     Output("rssi-value", "children"),
     Output("rssi-progress", "color"),
     Output("snr-progress", "value"),
     Output("snr-value", "children"),
     Output("snr-progress", "color"),
     Output("board-temp-progress", "value"),
     Output("board-temp-progress", "color"),
     Output("board-temp-value", "children"),
     Output("board-temp-container", "style")],
    [Input("sensor-name-store", "data"),
     Input("live-sensor-data", "data")]
)
def update_sensor_health(sensor_name, live_data):
    if not can_view(sensor_name):
        raise PreventUpdate

    raw_data = get_most_recent(sensor_name, Lora=True)

    # Structure from query is: (SensorDataObj, param_name, unit)
    readings = {row[1].lower(): row[0].value for row in raw_data}

    battery = readings.get('battery')
    rssi = readings.get('rssi')
    snr = readings.get('snr')
    board_temperature = readings.get('board_temperature')

    # Handle missing data
    if battery is None:
        battery_label = "No battery data available"
        battery_color = "secondary"
    else:
        if battery >= 3.7:
            battery_color = "success"
        elif 3.5 <= battery < 3.7:
            battery_color = 'warning'
        else:
            battery_color = 'danger'
        battery_label = f"{battery} V"

    if rssi is None:
        rssi_label = "No RSSI data available"
        rssi_color = "secondary"
    else:
        rssi_transformed = max(0, min(100, int((rssi - RSSI_BAR_MIN) * 100 / (RSSI_BAR_MAX - RSSI_BAR_MIN))))
        rssi_color = signal_color(rssi, RSSI_GOOD_ABOVE, RSSI_POOR_BELOW)
        rssi_label = f"{rssi} dBm"

    if snr is None:
        snr_label = "No SNR data available"
        snr_color = "secondary"
    else:
        snr_transformed = max(0, min(100, int((snr + 20) * 100 / 40)))  # Map -20 to 20 dB -> 0 to 100
        snr_color = signal_color(snr, SNR_GOOD_ABOVE, SNR_POOR_BELOW)
        snr_label = f"{snr} dB"

    # Not every device reports this, so the row only appears when there is a value
    if board_temperature is None:
        board_temp_percent, board_temp_color = 0, "secondary"
        board_temp_label = ""
        board_temp_style = {"display": "none"}
    else:
        board_temp_percent, board_temp_color = board_temp_bar(board_temperature)
        board_temp_label = f"{board_temperature:.1f} \u00B0C"
        board_temp_style = {"display": "block"}

    # Return updated values, labels, and colors
    return (
        battery if battery is not None else BATTERY_MIN_V, battery_label, battery_color,
        rssi_transformed if rssi is not None else 0, rssi_label, rssi_color,
        snr_transformed if snr is not None else 0, snr_label, snr_color,
        board_temp_percent, board_temp_color, board_temp_label, board_temp_style,
    )

# ----------------------------
# History Offcanvas
# ----------------------------
@callback(
    Output("history-offcanvas", "is_open"),
    Input("history-button", "n_clicks"),
    [State("history-offcanvas", "is_open")],
)
def toggle_history_offcanvas(n_clicks, is_open):
    if n_clicks:
        return not is_open
    return is_open

@callback(
    Output("sensor-image", "src"),
    Input("sensor-name-store", "data"),
)
def get_sensor_pic(sensor_name):
    if not can_view(sensor_name):
        raise PreventUpdate
    if not sensor_name:
        return "/assets/no_image_available.png"

    sensor = get_sensor_by_name(sensor_name)

    # If DB has image_data, use it. Else, default.
    if sensor and sensor.image_data:
        image_src = sensor.image_data
    else:
        image_src = "/assets/no_image_available.png"

    return image_src
def avg_label(parameter):
    label = parameter_label(parameter)
    return label if label == "pH" else label.lower()


def hero_meta(sensor, location, moment=None, archived_range=None):
    device_type = sensor.device_type if sensor else None
    testing = bool(sensor and sensor.testing)
    items = [html.Span([html.I(className=f"bi {TYPE_ICONS.get(device_type, 'bi-broadcast')}"),
                        device_type_label(device_type)]),
             html.Span([html.I(className="bi bi-geo-alt"), "Not deployed" if testing else location])]
    if testing:
        items.insert(0, html.Span("Test Device", className="hero-archived"))
    if archived_range:
        items.insert(0, html.Span("Archived View", className="hero-archived"))
        # If the line is too narrow, the duration moves down whole instead of splitting
        items.append(html.Span([html.I(className="bi bi-calendar3"), archived_range]))
    elif moment:
        items.append(html.Span([html.I(className="bi bi-clock"), "Last report ", relative_time(moment)]))
    return items


@callback(
    [Output("card-title", "children"),
     Output("hero-meta", "children"),
     Output("summary-content", "children")],
    [Input("sensor-name-store", "data"),
     Input("live-sensor-data", "data"),
     Input("selected-deployment-store", "data")]
)
def update_summary_from_url(sensor_name, live_data, deploy_data):
    if not can_view(sensor_name):
        raise PreventUpdate
    if not sensor_name:
        return "No Sensor Found", None, html.P("No sensor data was found.", className="text-warning")

    title = sensor_label(sensor_name)
    sensor = get_sensor_by_name(sensor_name)

    # Past Deployment
    if deploy_data and not deploy_data.get('is_current', False):

        stats = get_deployment_statistics(sensor_name, deploy_data)

        if "error" in stats:
            return title, None, html.P(stats["error"], className="text-danger text-center small")

        location = format_location(stats['latitude'], stats['longitude'])
        meta = hero_meta(sensor, location, archived_range=f"{stats['range']} ({stats['duration']})")

        if not stats["averages"]:
            return title, meta, html.P("No data available for this period.", className="empty-text")

        return title, meta, html.Div(
            [reading_tile(f"Avg {avg_label(avg['parameter'])}",
                          round(avg['value'], display_decimals(avg['parameter'])), avg.get('unit'))
             for avg in stats["averages"]],
            className="reading-tiles"
        )

    summary = get_measurement_summary(sensor_name)

    if "error" in summary:
        return title, None, html.P(summary["error"], className="text-danger")

    location = format_location(summary['latitude'], summary['longitude'])

    if "message" in summary:
        return title, hero_meta(sensor, location), html.Div(
            "No readings yet. This sensor's data will appear here after its first report.", className="empty-text"
        )

    # Prepare content dynamically based on the most recent measurements
    recent_measurements = summary.get("most_recent_measurements", [])

    if not recent_measurements:
        return title, hero_meta(sensor, location), html.P("No data received yet.", className="empty-text")

    latest = recent_measurements[0]["timestamp"]
    day = load_series(sensor_name, trend_start(latest, deploy_data), latest)

    tiles = []
    for measurement in recent_measurements:
        name = measurement['name']
        history = day.get(name, {})
        tiles.append(reading_tile(
            parameter_label(name), round(measurement['value'], display_decimals(name)), measurement['unit'],
            values=history.get("values"), timestamps=history.get("timestamps"),
            is_water_level=name == "water_level"
        ))

    return title, hero_meta(sensor, location, latest), html.Div(
        [html.Div(tiles, className="reading-tiles"), quality_panel(sensor_name)]
    )

@callback(
    [Output("date-range-radio", "style"),
     Output("historic-controls-container", "style"),
     Output("historic-date-slider", "min"),
     Output("historic-date-slider", "max"),
     Output("historic-date-slider", "marks"),
     Output("historic-date-slider", "value"),
     Output("historic-date-slider", "tooltip")],
    Input("selected-deployment-store", "data")
)
def toggle_controls(deploy_data):
    # Default Tooltip Config (Hidden)
    hidden_tooltip = {"always_visible": False}

    if not deploy_data or deploy_data.get('is_current', False):
        return {"display": "inline-flex"}, {"display": "none"}, 0, 100, {}, [0, 100], hidden_tooltip

    start = parse_date(deploy_data['start_iso'])
    end = parse_date(deploy_data['end_iso']) if deploy_data.get('end_iso') else datetime.utcnow()

    min_ts, max_ts = int(start.timestamp()), int(end.timestamp())
    first_shown = max(min_ts, max_ts - int(PLAYBACK_DEFAULT.total_seconds()))

    marks = {
        min_ts: {"label": start.strftime("%b %d"), "style": {"transform": "translate(0, 5px)", "whiteSpace": "nowrap"}},
        max_ts: {"label": end.strftime("%b %d"),
                 "style": {"transform": "translate(-100%, 5px)", "whiteSpace": "nowrap"}}
    }

    # Return everything, ensuring tooltip remains hidden
    return {"display": "none"}, {"display": "block"}, min_ts, max_ts, marks, [first_shown, max_ts], hidden_tooltip

@callback(
    Output("slider-date-label", "children"),
    [Input("historic-date-slider", "value"),
     Input("historic-date-slider", "drag_value")]
)
def update_slider_label(value, drag_value):
    current = drag_value if drag_value else value

    if not current or len(current) < 2: return "Loading..."

    start = datetime.fromtimestamp(current[0])
    end = datetime.fromtimestamp(current[1])

    return f"{start.strftime('%b %d, %Y')} — {end.strftime('%b %d, %Y')}"

@callback(
    [Output("selected-deployment-store", "data"),
     Output("history-offcanvas", "is_open", allow_duplicate=True)],
    Input({"type": "deployment-item", "index": ALL}, "n_clicks"),
    State("sensor-name-store", "data"),
    prevent_initial_call=True
)
def select_deployment(clicks, sensor_name):
    trigger = ctx.triggered_id
    # The list being drawn also fires this, so only a real click counts
    if not trigger or not isinstance(trigger, dict) or not any(clicks):
        raise PreventUpdate

    index = trigger['index']
    deployments = get_past_deployments(sensor_name)
    if index < len(deployments):
        return deployments[index], False
    return no_update, no_update

@callback(
    Output("history-list-content", "children"),
    Input("sensor-name-store", "data")
)
def update_history_list(sensor_name):
    if not sensor_name: return []
    deployments = get_past_deployments(sensor_name)

    return [
        dbc.ListGroupItem([
            html.Div([
                html.Strong("Current Deployment" if d['is_current'] else d['range'], className="small"),
                html.Span(d['duration'],
                          className=f"badge {'bg-success' if d['is_current'] else 'bg-light text-dark'} ms-2")
            ], className="d-flex justify-content-between"),
            html.Small(f"Lat: {d['latitude']:.4f}, Lon: {d['longitude']:.4f}", className="text-muted d-block")
        ], action=True, id={"type": "deployment-item", "index": i})
        for i, d in enumerate(deployments)
    ]

#-----------------
# MAP UPDATE
#-----------------
def map_viewport(center, zoom, current):
    # A page change updates this callback twice, and a second flight would restart the
    # first one partway through, so the map wobbles.
    if current and current.get("center") == center and current.get("zoom") == zoom:
        return no_update
    # The map only reads its center and zoom props once, when it is first created.
    return {"center": center, "zoom": zoom, "transition": "flyTo"}


@callback(
    [Output("map-markers", "children", allow_duplicate=True),
     Output("dashboard-map", "viewport")],
    [Input("selected-deployment-store", "data"),
     Input("sensor-name-store", "data")],
    [State("show-inactive-store", "data"),  # Global, so as an Input it would fire on other pages
     State("dashboard-map", "viewport")],
    prevent_initial_call="initial_duplicate"
)
def update_map_view(deploy_data, sensor_name, show_inactive, current_viewport):

    if not sensor_name:
        raise PreventUpdate

    if not deploy_data or deploy_data.get('is_current', True):
        markers, map_center, map_zoom = create_map_markers(sensor_name, show_inactive=bool(show_inactive))
        return markers, map_viewport(map_center, map_zoom, current_viewport)

    # Historic mode
    lat = deploy_data.get('latitude')
    lon = deploy_data.get('longitude')

    if lat is None or lon is None:
        return no_update, no_update

    sensor = get_sensor_by_name(sensor_name)
    s_type = sensor.device_type if sensor else None

    # The other sensors stay on the map, and this deployment's marker replaces the sensor's own
    other_markers, _, _ = create_map_markers(sensor_name, show_inactive=bool(show_inactive), hide_selected=True)

    historic_marker = [dl.Marker(
        position=[lat, lon],
        title=f"Historic: {sensor_name}",
        icon=marker_icon(s_type, "deactivated", "inactive-marker", selected=True)
    )]

    return other_markers + historic_marker, map_viewport([lat, lon], 12, current_viewport)

@callback(
    Output("live-sensor-data", "data", allow_duplicate=True),
    Input("test-device-refresh", "n_intervals"),
    prevent_initial_call=True
)
def refresh_test_device(n_intervals):
    # Any new value redraws the graphs, tiles and health, as a broadcast packet would
    return {"refresh": n_intervals}
