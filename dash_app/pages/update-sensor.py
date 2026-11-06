from dash import dcc, html, register_page
import dash_bootstrap_components as dbc
from flask import session

register_page(
    __name__,
    top_nav=True,
    path='/onboarding/update-sensor'
)

def layout():
    if not session['user_logged_in']:
        return dcc.Location(pathname='/onboarding', id='redirect-login')

    layout = dbc.Container([
        dcc.Store(id="sensor-active-status-store"),
        html.H2("Update Existing Sensor", className="text-center mt-4"),
        dbc.Button("\u2190 Back", href="/onboarding", color="secondary", outline=True, size="sm", className="mb-4"),
        dbc.Form([
            dbc.Row([
                dbc.Col(dbc.Label("Select Device", className="text-start"), width=12, sm=4),
                dbc.Col(dcc.Dropdown(
                    id="select-device-dropdown",
                    options=[],
                    placeholder="Select a sensor"
                ), width=12, sm=8),
            ], className="mb-3"),

            html.Div(id="form-container", children=[
                dbc.Row([
                    dbc.Col(dbc.Label("Device Name", className="text-start"), width=12, sm=4),
                    dbc.Col(dbc.Input(type="text", id="update-device-name", placeholder="Enter device name"), width=12, sm=8),
                ], className="mb-3"),
                dbc.Row([
                    dbc.Col(dbc.Label("Latitude", className="text-start"), width=12, sm=4),
                    dbc.Col(dbc.Input(type="number", id="update-latitude", placeholder="Enter latitude"), width=12, sm=8),
                ], className="mb-3"),
                dbc.Row([
                    dbc.Col(dbc.Label("Longitude", className="text-start"), width=12, sm=4),
                    dbc.Col(dbc.Input(type="number", id="update-longitude", placeholder="Enter longitude"), width=12, sm=8),
                ], className="mb-3"),
                dbc.Row([
                    dbc.Col(dbc.Label("Device Type", className="text-start align-self-center"), width=12, sm=4),
                    dbc.Col(
                        dbc.RadioItems(
                            id="update-device-type",
                            options=[
                                {"label": "Sonde", "value": "sonde"},
                                {"label": "Tide Gauge", "value": "tide_gauge"},
                                {"label": "Wave Gauge", "value": "wave_gauge"},
                                {"label": "Other", "value": "other"},
                            ],
                            inline=False,
                            className="custom-radio",
                        ), width=12, sm=8
                    ),
                ], className="mb-3"),
                html.Div(
                    dbc.Row([
                        dbc.Col(dbc.Label("NAVD88 Elevation (m)", className="text-start"), width=12, sm=4),
                        dbc.Col(
                            dbc.Input(type="number", id="update-gauge-elevation",
                                      placeholder="Enter gauge elevation in NAVD88"),
                            width=12, sm=8
                        ),
                    ], className="mb-3"),
                    id="update-gauge-elevation-row",
                    style={"display": "none"}
                ),
                dbc.Row([
                    dbc.Col(dbc.Label("Device Image", className="text-start"), width=12, sm=4),
                    dbc.Col([
                        dcc.Upload(
                            id="update-device-image",
                            children=html.Div([
                                "Drag and Drop or ",
                                html.A("Select an Image File")
                            ]),
                            style={
                                "width": "100%",
                                "height": "80px",
                                "lineHeight": "80px",
                                "borderWidth": "1px",
                                "borderStyle": "dashed",
                                "borderRadius": "5px",
                                "textAlign": "center",
                                "margin": "10px 0",
                            },
                            multiple=False,
                            accept="image/*"
                        ),
                        html.Div(html.Img(id="update-image-preview",style={"width": "100%", "max-width": "300px", "marginTop": "10px"}), className="text-center"),
                        ], width=12, sm=8
                    ),
                ], className="mb-3"),
                dbc.Row([
                    dbc.Col(dbc.Button("Submit", id="update-submit-btn", color="primary", className="mt-3 w-100"),
                            width=12, sm=6),
                    dbc.Col(dbc.Button("Deactivate", id="toggle-active-btn", color="danger", className="mt-3 w-100"),
                            width=12, sm=6),
                ], className="d-flex justify-content-between mb-3"),
                html.Div(id="update-submission-response", className="mt-3"),
            ])
        ], className="px-3 py-3")
    ], className="form-page")

    return layout
