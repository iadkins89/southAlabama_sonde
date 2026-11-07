from dash import dcc, html, register_page
import dash_bootstrap_components as dbc
from flask import session

register_page(
    __name__,
    top_nav=True,
    path='/onboarding/add-sensor'
)

def layout():
    if not session['user_logged_in']:
        return dcc.Location(pathname='/onboarding', id='redirect-login')

    layout = dbc.Container([
        html.H1("Add a new sensor", className="form-title mt-2"),
        dbc.Button("\u2190 Back", href="/onboarding", color="secondary", outline=True, size="sm", className="mb-4"),
        dbc.Form([
            dbc.Row([
                dbc.Col(dbc.Label("Device Name", className="text-start text-md-end"), width=12, md=3),
                dbc.Col(dbc.Input(type="text", id="device-name", placeholder="Enter device name"), width=12, md=9),
            ], className="mb-3"),
            dbc.Row([
                dbc.Col(dbc.Label("Latitude", className="text-start text-md-end"), width=12, md=3),
                dbc.Col(dbc.Input(type="number", id="latitude", placeholder="Enter latitude"), width=12, md=9),
            ], className="mb-3"),
            dbc.Row([
                dbc.Col(dbc.Label("Longitude", className="text-start text-md-end"), width=12, md=3),
                dbc.Col(dbc.Input(type="number", id="longitude", placeholder="Enter longitude"), width=12, md=9),
            ], className="mb-3"),
            dbc.Row([
                dbc.Col(dbc.Label("Timezone", className="text-start text-md-end"), width=12, md=3),
                dbc.Col(
                    dcc.Dropdown(
                        id="timezone",
                        options=[
                            {'label': 'Central Time', 'value': 'America/Chicago'},
                            {'label': 'Eastern Time', 'value': 'America/New_York'},
                            {'label': 'UTC (Universal Standard)', 'value': 'UTC'}
                        ],
                        value='America/Chicago',  # Default to CST
                        clearable=False,
                        style={'color': 'black'}
                    ),
                    width=12, md=9
                ),
            ], className="mb-3"),
            dbc.Row([
                dbc.Col(dbc.Label("Device Type", className="text-start text-md-end"), width=12, md=3),
                dbc.Col(
                    dbc.RadioItems(
                        id="device-type",
                        options=[
                            {"label": "Sonde", "value": "sonde"},
                            {"label": "Tide Gauge", "value": "tide_gauge"},
                            {"label": "Wave Gauge", "value": "wave_gauge"},
                            {"label": "Other", "value": "other"},
                        ],
                        inline=False,
                        className="custom-radio mt-2",
                    ), width=12, md=9
                ),
            ], className="mb-3"),
            html.Div(
                dbc.Row([
                    dbc.Col(dbc.Label("NAVD88 Elevation (m)", className="text-start text-md-end"), width=12, md=3),
                    dbc.Col(
                        dbc.Input(type="number", id="gauge-elevation",
                                  placeholder="Enter gauge elevation in NAVD88"),
                        width=12, md=9
                    ),
                ], className="mb-3"),
                id="gauge-elevation-row",
                style={"display": "none"}
            ),
            dbc.Row([
                dbc.Col(dbc.Label("Device Image", className="text-start text-md-end"), width=12, md=3),
                dbc.Col([
                    dcc.Upload(
                        id="device-image",
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
                ], width=12, md=9),
            ], className="mb-3"),
            dbc.Row([
                dbc.Col(
                    dbc.Button("Submit", id="submit-btn", color="primary", className="mt-3 w-100"),
                    width=12,
                ),
            ]),
            html.Div(id="submission-response", className="mt-3"),
        ]),
    ], className="form-page px-3 py-3")
    return layout

