from dash import dcc, html, register_page
from server.utils import get_map_graph
import dash_bootstrap_components as dbc

register_page(
    __name__,
    top_nav=True,
    path='/'
)

def layout():
    layout = dbc.Container(
        [
            dcc.Location(id='home-url', refresh=True),
            dcc.Store(id='click-store'),  # Store to reset clickData
            dbc.Row(
                [
                    dbc.Col(
                        dbc.Card(get_map_graph("75vh",0,0,0,0)),
                        xs=12, sm=12, md=12, lg=9
                    ),
                    dbc.Col(
                        dbc.Card([
                            html.H5("Exploring Our Network ",
                                    style={
                                        "text-align": "center",
                                        "margin-top": "20px"
                                    }
                                ),
                            html.P(
                                "This map shows the location of actively deployed sensors in our network. "
                                "Real-time sensor measurements can be viewed by selecting a sensor on the map "
                                "or by selecting a sensor in the Sensors tab.",
                                className="lead",
                                style={"margin-left": "5%"}
                            ),
                        ]),
                    xs=12, sm=12, md=12, lg=3),
                ], className="g-3", justify="center"
            ),
        ],
        fluid=False,
        className="dash-container"
    )

    return layout



