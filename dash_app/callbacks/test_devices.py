import time

from dash import callback, Input, Output, State, ALL, ctx, dcc, html, no_update
import dash_bootstrap_components as dbc
from dash.exceptions import PreventUpdate
from flask import session

from server.models import count_test_readings, go_live
from dash_app.access import managed_sensor, managed_sensors
from server.utils import device_type_label, relative_time, sensor_label


def test_device_row(sensor, readings):
    last_report = sensor.get('last_report')
    return html.Div([
        html.Div([
            html.Div(sensor_label(sensor['name']), className="test-device-name"),
            html.Div([device_type_label(sensor.get('device_type')), " · ",
                      # A Span, not a list: Dash can't draw a list nested inside children
                      html.Span(["Last report ", relative_time(last_report)]) if last_report else "No data yet",
                      f" · {readings:,} stored values"],
                     className="test-device-meta"),
        ], className="test-device-text"),
        html.Div([
            dbc.Button([html.I(className="bi bi-graph-up me-2"), "Readings"],
                       href=f"/dashboard?sensor={sensor['name']}", color="primary", outline=True, size="sm"),
            dbc.Button([html.I(className="bi bi-broadcast me-2"), "Go live"],
                       id={"type": "go-live-btn", "index": sensor['name']}, color="success", size="sm"),
        ], className="test-device-actions"),
    ], className="test-device")


@callback(
    Output("test-devices-list", "children"),
    [Input("main-url", "pathname"),
     Input("test-devices-refresh", "data")]
)
def list_test_devices(pathname, refresh):
    if not session.get('user_logged_in'):
        return no_update

    # Only this user's test devices, or every one for an admin
    sensors = managed_sensors(testing=True)
    if not sensors:
        return html.Div(
            [html.Div(html.I(className="bi bi-tools"), className="empty-icon"),
             html.Div("No devices in test", className="empty-title"),
             html.Div(["New sensors start here. ",
                       dcc.Link("Add a sensor", href="/onboarding/add-sensor"), " to begin testing."],
                      className="empty-text")],
            className="empty-state"
        )

    return [test_device_row(s, count_test_readings(s['id'])) for s in sensors]


@callback(
    [Output("go-live-modal", "is_open"),
     Output("go-live-sensor", "data"),
     Output("go-live-title", "children"),
     Output("go-live-warning", "children"),
     Output("go-live-elevation-row", "style"),
     Output("go-live-latitude", "value"),
     Output("go-live-longitude", "value"),
     Output("go-live-elevation", "value"),
     Output("go-live-error", "children")],
    [Input({"type": "go-live-btn", "index": ALL}, "n_clicks"),
     Input("go-live-cancel-btn", "n_clicks")],
    prevent_initial_call=True
)
def open_go_live_dialog(go_live_clicks, cancel_clicks):
    # Redrawing the list fires this with no clicks, which must not open the dialog
    trigger = ctx.triggered_id
    if not isinstance(trigger, dict) or not ctx.triggered[0]['value']:
        return False, None, no_update, no_update, no_update, None, None, None, ""

    sensor = managed_sensor(trigger['index'])
    if not sensor or not sensor.testing:
        return False, None, no_update, no_update, no_update, None, None, None, ""

    readings = count_test_readings(sensor.id)
    if readings:
        warning = (f"Going live deletes the {readings:,} values stored during testing, so desk readings never "
                   "reach the public graphs or QC work. To keep a copy, download them from its Readings page first.")
    else:
        warning = "Nothing was stored during testing, so nothing will be deleted."

    is_gauge = sensor.device_type == "tide_gauge"
    return (True, sensor.name, f"Take {sensor_label(sensor.name)} live?", warning,
            {} if is_gauge else {"display": "none"}, None, None, None, "")


@callback(
    [Output("go-live-error", "children", allow_duplicate=True),
     Output("go-live-modal", "is_open", allow_duplicate=True),
     Output("go-live-response", "children"),
     Output("test-devices-refresh", "data"),
     Output("sensor-update", "data", allow_duplicate=True)],
    Input("go-live-confirm-btn", "n_clicks"),
    [State("go-live-sensor", "data"),
     State("go-live-latitude", "value"),
     State("go-live-longitude", "value"),
     State("go-live-elevation", "value")],
    prevent_initial_call=True
)
def confirm_go_live(n_clicks, sensor_name, latitude, longitude, elevation):
    # The dialog's button is drawn with the page, which fires this once unclicked
    if not n_clicks:
        raise PreventUpdate
    # The page checks the login too, but this callback can be called directly
    if not session.get('user_logged_in'):
        return "Please log in again.", no_update, no_update, no_update, no_update

    sensor = managed_sensor(sensor_name)
    if not sensor:
        return f"Could not find sensor '{sensor_name}'.", no_update, no_update, no_update, no_update
    if latitude is None or longitude is None:
        return "Enter both latitude and longitude.", no_update, no_update, no_update, no_update
    if sensor.device_type == "tide_gauge" and elevation is None:
        return "A tide gauge needs its NAVD88 elevation.", no_update, no_update, no_update, no_update

    error = go_live(sensor.id, latitude, longitude, elevation)
    if error:
        return error, no_update, no_update, no_update, no_update

    done = dbc.Alert([f"{sensor_label(sensor_name)} is live. ",
                      dcc.Link("View its dashboard", href=f"/dashboard?sensor={sensor_name}"), "."],
                     color="success", dismissable=True)
    now = {"timestamp": time.time()}
    return "", False, done, now, now
