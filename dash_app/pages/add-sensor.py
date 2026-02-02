from dash import dcc, html, register_page, Input, Output, State
import dash_bootstrap_components as dbc
from flask import session
from dash.exceptions import PreventUpdate

register_page(
    __name__,
    top_nav=True,
    path='/onboarding/add-sensor'
)

def layout():
    if not session['user_logged_in']:
        return dcc.Location(pathname='/onboarding', id='redirect-login')

    layout = dbc.Container([
        dcc.Location(id="url", refresh=True),
        html.H2("Add New Sensor", className="text-center mt-4"),
        dbc.Button("Back", href="/onboarding", color="secondary", className="mb-4"),
        dbc.Form([
            dbc.Row([
                dbc.Col(dbc.Label("Device Name", className="text-start text-md-end"), width=12, md=2),
                dbc.Col(dbc.Input(type="text", id="device-name", placeholder="Enter device name"), width=12, md=10),
            ], className="mb-3"),
            dbc.Row([
                dbc.Col(dbc.Label("Latitude", className="text-start text-md-end"), width=12, md=2),
                dbc.Col(dbc.Input(type="number", id="latitude", placeholder="Enter latitude"), width=12, md=10),
            ], className="mb-3"),
            dbc.Row([
                dbc.Col(dbc.Label("Longitude", className="text-start text-md-end"), width=12, md=2),
                dbc.Col(dbc.Input(type="number", id="longitude", placeholder="Enter longitude"), width=12, md=10),
            ], className="mb-3"),
            dbc.Row([
                dbc.Col(dbc.Label("Timezone", className="text-start text-md-end"), width=12, md=2),
                dbc.Col(
                    dcc.Dropdown(
                        id="timezone",
                        options=[
                            {'label': 'Central Time (Mobile, AL, Gulf)', 'value': 'America/Chicago'},
                            {'label': 'Eastern Time (Florida, Atlantic)', 'value': 'America/New_York'},
                            {'label': 'UTC (Universal Standard)', 'value': 'UTC'}
                        ],
                        value='America/Chicago',  # Default to Mobile time
                        clearable=False,
                        style={'color': 'black'}  # Fixes dark mode visibility issues if present
                    ),
                    width=12, md=10
                ),
            ], className="mb-3"),
            dbc.Row([
                dbc.Col(dbc.Label("Device Type", className="text-start text-md-end"), width=12, md=2),
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
                    ), width=12, md=10
                ),
            ], className="mb-3"),
            dbc.Row([
                dbc.Col(dbc.Label("Device Image", className="text-start text-md-end"), width=12, md=2),
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
                            "margin": "10px",
                        },
                        multiple=False,
                        accept="image/*"
                    ),
                ], width=12, md=10),
            ], className="mb-3"),
            dbc.Row([
                dbc.Col(
                    dbc.Button("Submit", id="submit-btn", color="success", className="mt-3 w-100"),
                    width=12, md={"size": 4, "offset": 2},
                ),
            ]),
            html.Div(id="submission-response", className="mt-3"),
        ]),
    ], className="px-3 py-3")
    return layout

