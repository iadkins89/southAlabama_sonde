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
            dcc.Store(id="auth-fail", data=False),  # Tracks failed authentication
            html.Div(id="login-form", children=[
                html.H2("Login to Access Onboarding", className="text-center mt-4"),
                dbc.Form([
                    dbc.Row([
                        dbc.Label("Username", width=2, className="text-end"),
                        dbc.Col(dbc.Input(type="text", id="username", placeholder="Enter username"), width=10),
                    ], className="mb-3"),
                    dbc.Row([
                        dbc.Label("Password", width=2, className="text-end"),
                        dbc.Col(dbc.Input(type="password", id="password", placeholder="Enter password"), width=10),
                    ], className="mb-3"),
                    dbc.Row([
                        dbc.Col(dbc.Button("Login", id="login-btn", color="primary", className="mt-2"), width={"size": 4, "offset": 2}),
                    ]),
                    html.Div(id="login-error", className="text-danger mt-2")
                ]),
            ]),
            html.Div(id="onboarding-form", style={"display": "none"}, children=[
                html.H2("Device Onboarding Form", className="text-center mt-4"),
                dbc.Form([
                    dbc.Row([
                        dbc.Label("Device Name", width=2, className="text-end"),
                        dbc.Col(dbc.Input(type="text", id="device-name", placeholder="Enter device name"), width=10),
                    ], className="mb-3"),
                    dbc.Row([
                        dbc.Label("Latitude", width=2, className="text-end"),
                        dbc.Col(dbc.Input(type="number", id="latitude", placeholder="Enter latitude"), width=10),
                    ], className="mb-3"),
                    dbc.Row([
                        dbc.Label("Longitude", width=2, className="text-end"),
                        dbc.Col(dbc.Input(type="number", id="longitude", placeholder="Enter longitude"), width=10),
                    ], className="mb-3"),
                    dbc.Row([
                        dbc.Label("Device Type", width=2, className="text-end"),
                        dbc.Col(
                            dbc.RadioItems(
                                id="device-type",
                                options=[
                                    {"label": "Sonde", "value": "sonde"},
                                    {"label": "Tide Gauge", "value": "tide_gauge"},
                                    {"label": "Wave Gauge", "value": "wave_gauge"},
                                    {"label": "Other", "value": "other"},
                                ],
                                inline=False,  # Vertical layout for better clarity
                            ), width=10
                        ),
                    ], className="mb-3"),
                    dbc.Row([
                        dbc.Label("Device Image", width=2, className="text-end"),
                        dbc.Col(
                            dcc.Upload(
                                id="device-image",
                                children=html.Div([
                                    "Drag and Drop or ",
                                    html.A("Select an Image File")
                                ]),
                                style={
                                    "width": "100%",
                                    "height": "60px",
                                    "lineHeight": "60px",
                                    "borderWidth": "1px",
                                    "borderStyle": "dashed",
                                    "borderRadius": "5px",
                                    "textAlign": "center",
                                    "margin": "10px",
                                },
                                multiple=False,  # Single file upload
                            ), width=10
                        ),
                    ], className="mb-3"),
                    dbc.Row([
                        dbc.Col(dbc.Button("Submit", id="submit-btn", color="success", className="mt-3"), width={"size": 4, "offset": 2}),
                    ]),
                    html.Div(id="submission-response", className="mt-3"),
                ]),
            ]),
        ])
    ])
    return layout