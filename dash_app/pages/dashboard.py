from dash import dcc, html, register_page
import dash_bootstrap_components as dbc
from datetime import datetime
from dash_extensions import EventSource
from server.models import get_unique_sensor_names
import pytz

register_page(
	__name__,
	top_nav=True,
	path='/dashboard'
)


def layout():
    cst = pytz.timezone('America/Chicago')
    cst_today = datetime.now(cst).replace(hour=0, minute=0, second=0, microsecond=0)
    sensor_options = [name for name in get_unique_sensor_names()]

    layout = dbc.Container([
        dbc.Row([
            dbc.Col(dbc.Form([
                dbc.Input(id="csv-filename", placeholder="Enter CSV filename"),
                dbc.Button("Download CSV", id="set-filename-btn", color="primary", className="mt-2"),
                dcc.DatePickerRange(
                    id='date-picker-range',
                    minimum_nights=0,
                    start_date=cst_today,
                    end_date=cst_today,
                    stay_open_on_select=True,
                    style={"margin-left": "15px",
                           'padding': '10px'}
                ),
                dcc.ConfirmDialog(
                    id='confirm-dialog',
                    message=''
                ),
                dcc.Download(id="download-dataframe-csv")
            ]), width=5),
            dbc.Col(),
            dbc.Col(
                html.Div(
                    dcc.Dropdown(
                        id='table-dropdown',
                        options=sensor_options if len(sensor_options) !=0  else [],
                        value=sensor_options[0] if len(sensor_options) !=0 else [],
                        #placeholder="Select a sensor",
                        style={'width': '100%'},
                    ),
                    style={'display': 'flex', 'justifyContent': 'flex-end', 'width': '90%'}
                ),
                width=5
            )
        ]),
        dbc.Row([
            dbc.Col(dcc.Graph(id='multi-sensor-graph', config={
                'modeBarButtonsToRemove': [
                    'pan2d', 'select2d', 'lasso2d',
                    'zoomIn2d', 'zoomOut2d', 'autoScale2d',
                    'hoverClosestCartesian', 'hoverCompareCartesian',
                    'toggleSpikelines'
                ],
                'displaylogo': False,  # Optional: remove Plotly logo
                'modeBarStyle': {
                    'bgcolor': 'white',  # Set the background to transparent
                    'border': 'none',  # Remove border
                    'border-color': 'rgba(0,0,0,0)',
                    'color': 'rgba(0,0,0,0)'}
            }), xs=12, sm=8, md=12, lg=12 ),
        ]),
        EventSource(id='eventsource', url='/eventsource')
    ])
	
    return layout