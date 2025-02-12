from dash import dcc, html, register_page, Input, Output, State
import dash_bootstrap_components as dbc

register_page(
    __name__,
    top_nav=True,
    path='/onboarding'
)

def layout():
    layout = dbc.Container([
        html.Div(id="onboarding-page", children=[
            dcc.Location(id="url", refresh=True),
            html.Div(id="login-form", children=[
                html.H2("Login to Access Onboarding", className="text-center mt-4 fs-5"),
                dbc.Form([
                    dbc.Row([
                        dbc.Label("Username", width=2, className="text-end"),
                        dbc.Col(dbc.Input(type="text", id="username", placeholder="Enter username"), width=12, lg=8, md=9),
                    ], className="mb-3"),
                    dbc.Row([
                        dbc.Label("Password", width=2, className="text-end"),
                        dbc.Col(dbc.Input(type="password", id="password", placeholder="Enter password"), width=12, lg=8, md=9),
                    ], className="mb-3"),
                    dbc.Row([
                        dbc.Col(dbc.Button("Login", id="login-btn", color="primary", className="mt-2 w-100"), width=12, sm={"size": 6, "offset": 3}),
                    ]),
                    html.Div(id="login-error", className="text-danger mt-2 text-center"),
                ]),
            ]),
            html.Div(id="menu", style={"display": "none"}, children=[
                html.H2("Onboarding Portal", className="text-center mt-4 fs-5"),
                dbc.Row([
                    dbc.Col(dbc.Button("Add New Sensor", size='lg', href="/onboarding/add-sensor",
                                       color="success", className="mt-2 w-100"), width=12, lg=6, className="text-center"),
                    dbc.Col(dbc.Button("Update Sensor", size='lg', href="/onboarding/update-sensor",
                                       color="success", className="mt-2 w-100"), width=12, lg=6, className="text-center"),
                ], className="justify-content-center flex-column flex-lg-row"),
            ]),
        ])
    ], className="px-3 py-3")
    return layout



