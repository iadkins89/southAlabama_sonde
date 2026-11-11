from dash import dcc, html, register_page
import dash_bootstrap_components as dbc
from flask import session

register_page(
    __name__,
    top_nav=True,
    path='/onboarding',
    title="Onboarding | South Alabama Telemetry"
)

def layout():
    # Drawing the right view first stops a signed-in visitor seeing the form flash
    signed_in = session.get('user_logged_in', False)

    layout = dbc.Container([
        html.Div(id="onboarding-page", children=[
            html.Div(id="login-form", style={"display": "none"} if signed_in else {}, children=[
                html.Div(html.I(className="bi bi-shield-lock"), className="form-icon"),
                html.H1("Sign in", className="form-title"),
                html.P("Sign in to add or update sensors.", className="form-subtitle"),
                dbc.Form([
                    dbc.Row([
                        dbc.Label("Username", width=12, md=3),
                        dbc.Col(dbc.Input(type="text", id="username", placeholder="Enter username"), width=12, md=9),
                    ], className="mb-3"),
                    dbc.Row([
                        dbc.Label("Password", width=12, md=3),
                        dbc.Col(dbc.Input(type="password", id="password", placeholder="Enter password"), width=12, md=9),
                    ], className="mb-3"),
                    dbc.Row([
                        dbc.Col(dbc.Button("Sign in", id="login-btn", color="primary", className="mt-2 w-100"), width=12),
                    ]),
                    html.Div(id="login-error", className="text-danger mt-2 text-center"),
                ]),
            ]),
            html.Div(id="menu", style={"display": "block" if signed_in else "none"}, children=[
                html.H1("Onboarding portal", className="form-title"),
                html.P("Manage the sensors shown on this site.", className="form-subtitle"),
                html.Div([
                    dcc.Link([html.I(className="bi bi-plus-circle"),
                              html.Div("Add New Sensor", className="action-card-title"),
                              html.Div("Register a device so that its packets are accepted.", className="action-card-text")],
                             href="/onboarding/add-sensor", className="action-card"),
                    dcc.Link([html.I(className="bi bi-pencil-square"),
                              html.Div("Update Sensor", className="action-card-title"),
                              html.Div("Edit details, move a deployment or deactivate a device.", className="action-card-text")],
                             href="/onboarding/update-sensor", className="action-card"),
                    dcc.Link([html.I(className="bi bi-tools"),
                              html.Div("Test Devices", className="action-card-title"),
                              html.Div("Check devices before they go public, then take them live.",
                                       className="action-card-text")],
                             href="/onboarding/test-devices", className="action-card"),
                ], className="action-cards"),
            ]),
        ])
    ], className="form-page px-3 py-3")
    return layout



