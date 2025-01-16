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
                dbc.Label("Device Name", width=2, className="text-end"),
                dbc.Col(dbc.Input(type="text", id="device-name", placeholder="Enter device name"), width=10, lg=8, md=9,
                        sm=12),
            ], className="mb-3"),
            dbc.Row([
                dbc.Label("Latitude", width=2, className="text-end"),
                dbc.Col(dbc.Input(type="number", id="latitude", placeholder="Enter latitude"), width=10, lg=8, md=9,
                        sm=12),
            ], className="mb-3"),
            dbc.Row([
                dbc.Label("Longitude", width=2, className="text-end"),
                dbc.Col(dbc.Input(type="number", id="longitude", placeholder="Enter longitude"), width=10, lg=8, md=9,
                        sm=12),
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
                        inline=False,
                        className="mb-3",
                    ), width=10, lg=8, md=9, sm=12
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
                        multiple=False,
                    ), width=10, lg=8, md=9, sm=12
                ),
            ], className="mb-3"),
            dbc.Row([
                dbc.Col(dbc.Button("Submit", id="submit-btn", color="success", className="mt-3"),
                        width={"size": 4, "offset": 2}),
            ]),
            html.Div(id="submission-response", className="mt-3"),
        ]),
    ])

    return layout
