from dash import dcc, html, register_page
import dash_bootstrap_components as dbc
from flask import session

register_page(
    __name__,
    top_nav=True,
    path='/onboarding/test-devices',
    title="Test Devices | South Alabama Telemetry"
)


def layout():
    if not session.get('user_logged_in'):
        return dcc.Location(pathname='/onboarding', id='redirect-login')

    return dbc.Container([
        dcc.Store(id="go-live-sensor"),
        dcc.Store(id="test-devices-refresh"),
        html.H1("Test devices", className="form-title mt-2"),
        html.P("Only signed-in users can see these. Their readings stay off the public site until they go live.",
               className="form-subtitle"),
        dbc.Button("← Back", href="/onboarding", color="secondary", outline=True, size="sm", className="mb-4"),
        html.Div(id="go-live-response"),
        html.Div(id="test-devices-list"),

        dbc.Modal([
            dbc.ModalHeader(dbc.ModalTitle(id="go-live-title")),
            dbc.ModalBody([
                html.P("Enter where it is deployed. It then appears on the map and its first deployment starts now."),
                dbc.Row([
                    dbc.Col(dbc.Label("Latitude"), width=12, sm=4),
                    dbc.Col(dbc.Input(type="number", id="go-live-latitude", placeholder="e.g. 30.25"), width=12, sm=8),
                ], className="mb-3"),
                dbc.Row([
                    dbc.Col(dbc.Label("Longitude"), width=12, sm=4),
                    dbc.Col(dbc.Input(type="number", id="go-live-longitude", placeholder="e.g. -88.08"), width=12, sm=8),
                ], className="mb-3"),
                html.Div(dbc.Row([
                    dbc.Col(dbc.Label("NAVD88 Elevation (m)"), width=12, sm=4),
                    dbc.Col(dbc.Input(type="number", id="go-live-elevation",
                                      placeholder="Gauge elevation in NAVD88"), width=12, sm=8),
                ], className="mb-3"), id="go-live-elevation-row", style={"display": "none"}),
                dbc.Alert(id="go-live-warning", color="warning", className="small mb-0"),
                html.Div(id="go-live-error", className="text-danger mt-2"),
            ]),
            dbc.ModalFooter([
                dbc.Button("Cancel", id="go-live-cancel-btn", color="secondary", outline=True),
                dbc.Button("Go live", id="go-live-confirm-btn", color="success"),
            ]),
        ], id="go-live-modal", is_open=False, centered=True),
    ], className="form-page px-3 py-3")
