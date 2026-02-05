import dash
from dash import html
import dash_leaflet as dl
from server.utils import create_instructions_card,create_map_markers

dash.register_page(__name__, path='/')

def layout():

    card_content = create_instructions_card()
    markers, map_center, map_zoom = create_map_markers(selected_sensor_name=None)

    return html.Div(
        [
            dl.Map(
                [
                    dl.TileLayer(url="https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png"),
                    dl.LayerGroup(children=markers)
                ],
                center=map_center,
                zoom=map_zoom,
                style={"width": "100%", "height": "100vh"},
                zoomControl=False
            ),
            card_content
        ],
        style={"position": "relative", "height": "100vh", "overflow": "hidden"}
    )
