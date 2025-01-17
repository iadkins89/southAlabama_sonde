import dash
from dash import dcc, html, register_page
import dash_html_components as html
import dash_bootstrap_components as dbc
from dash.dependencies import Input, Output, State
from flask import session
from server.models import get_all_sensors, get_sensor_by_name, get_measurement_summary

register_page(
    __name__,
    top_nav=True,
    path='/onboarding/update-sensor'
)

def layout():
    if not session['user_logged_in']:
        return dcc.Location(pathname='/onboarding', id='redirect-login')

    layout = dbc.Container([
        dcc.Location(id="url", refresh=True),
        html.H2("Update Existing Sensor", className="text-center mt-4"),
        dbc.Button("Back", href="/onboarding", color="secondary", className="mb-4"),
        dbc.Form([
            dbc.Row([
                dbc.Label("Select Device", width=2, className="text-end"),
                dbc.Col(dcc.Dropdown(
                    id="select-device-dropdown",
                    options=[{'label': device['name'], 'value': device['name']} for device in get_all_sensors()],
                    placeholder="Select a sensor"
                ), width=10, lg=8, md=9, sm=12),
            ], className="mb-3"),

            # Form fields initially hidden
            html.Div(id="form-container", children=[
                dbc.Row([
                    dbc.Label("Device Name", width=2, className="text-end"),
                    dbc.Col(dbc.Input(type="text", id="update-device-name", placeholder="Enter device name"), width=10,
                            lg=8, md=9, sm=12),
                ], className="mb-3"),
                dbc.Row([
                    dbc.Label("Latitude", width=2, className="text-end"),
                    dbc.Col(dbc.Input(type="number", id="update-latitude", placeholder="Enter latitude"), width=10,
                            lg=8, md=9, sm=12),
                ], className="mb-3"),
                dbc.Row([
                    dbc.Label("Longitude", width=2, className="text-end"),
                    dbc.Col(dbc.Input(type="number", id="update-longitude", placeholder="Enter longitude"), width=10,
                            lg=8, md=9, sm=12),
                ], className="mb-3"),
                dbc.Row([
                    dbc.Label("Parameter Units", width=2, className="text-end"),
                    dbc.Col([
                        # Parameters section
                        html.Div([
                            html.Div(id="parameters-container")  # Dynamically populated with parameters
                        ], className="mb-4"),
                    ])
                ]),
                dbc.Row([
                    dbc.Label("Device Type", width=2, className="text-end align-self-center"),
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
                        ), width=6, lg=4, md=6, sm=12
                    )
                ], className="mb-3"),
                dbc.Row([
                    dbc.Label("Device Image", width=2, className="text-end"),
                    dbc.Col(
                        dcc.Upload(
                            id="update-device-image",
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
                    dbc.Col(dbc.Button("Submit", id="update-submit-btn", color="success", className="mt-3"),
                            width={"size": 4, "offset": 2}),
                ]),
                html.Div(id="submission-response", className="mt-3"),
            ])
        ])
    ])

    return layout