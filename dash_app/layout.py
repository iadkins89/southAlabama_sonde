import dash
from dash import dcc, html
from .navmenu import create_menu
from .footer import create_footer

def get_layout():
    layout = html.Div(
        children=[
            dcc.Store(id="sensor-update"),
            html.Div(id="ws-trigger", style={"display": "none"}),
            create_menu(),
            dash.page_container,
            create_footer()

        ],
        className='app'
    )

    return layout
