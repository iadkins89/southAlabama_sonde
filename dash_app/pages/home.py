import dash
from dash import html
import dash_leaflet as dl
from server.utils import create_instructions_card, create_map_markers, get_carto_tile_url

dash.register_page(__name__, path='/')


def legend_item(state, label):
    return html.Div([html.Span(className=f"status-dot status-{state}"), label], className="map-legend-item")


def layout():

    card_content = create_instructions_card()
    markers, map_center, map_zoom = create_map_markers(selected_sensor_name=None)

    return html.Div(
        [
            dl.Map(
                [
                    dl.TileLayer(url=get_carto_tile_url()),
                    dl.LayerGroup(children=markers, id="map-markers")
                ],
                center=map_center,
                zoom=map_zoom,
                style={"width": "100%", "height": "100%"},
                zoomControl=False
            ),
            card_content,
            html.Div(
                [legend_item("online", "Online"), legend_item("offline", "Offline"),
                 legend_item("deactivated", "Deactivated")],
                className="map-legend"
            ),
        ],
        className="home-map"
    )
