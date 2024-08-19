from dash import dcc, html, register_page
import plotly.graph_objs as go
import dash_bootstrap_components as dbc

register_page(
    __name__,
    top_nav=True,
    path='/'
)

# Map graph configuration
map_graph = dcc.Graph(
    id='map-graph',
    figure={
        'data': [
            go.Scattermapbox(
                lat=[30.685075],
                lon=[-88.074669],
                mode='markers',
                marker=dict(size=14, color='red'),
                text=['Sensor Location']
            )
        ],
        'layout': go.Layout(
            title={
                'text': 'Sensor Network',
                'font': {
                    'size': 24  
                }
            },
            autosize=True,
            hovermode='closest',
            #margin=dict(l=20, r=20, t=50, b=10),
            mapbox=dict(
                accesstoken='pk.eyJ1IjoiaWVhMjAyMSIsImEiOiJjbHh6ZXp4OWgwYXdrMmxxMTYwcmtrNGdiIn0.kchUpTpboU3YMlrUkx8HuA',
                bearing=0,
                center=dict(
                    lat=30.685075,
                    lon=-88.074669
                ),
                pitch=0,
                zoom=8,
                style='outdoors'
            )
        )
    },
    style={'height': '700px'}  
)

def layout():
    layout = dbc.Container(
        [
            dbc.Row(
                dbc.Col(
                    map_graph,
                    width=0
                ),
            style={"margin-left": "100px", "margin-right": "100px", "margin-bottom": "0px"} 
            ),
            dbc.Row(
                dbc.Col(
                    html.P(
                        "This map shows the location of the sensor of activately deployed sensors in our network. "
                        "You can use this map to visualize the sensor's position and explore the surrounding area.",
                        "Collected sensor measurements can be viewed at the Dashboard tab of this webpage.",
                        className="lead",
                        style={"margin-left": "190px", "margin-right": "190px"} 
                    ),
                    width='auto'
                ),
                style={"margin-top": "0px"}
            ),
        ],
        fluid=True,
        style={"padding": "0px"} 
    )

    return layout


