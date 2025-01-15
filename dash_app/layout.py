import dash
from dash import dcc, html
from .navmenu import create_menu
from .footer import create_footer

def get_layout():
    layout = html.Div(
        id='app',
        children=[
            create_menu(),
            dash.page_container,
            create_footer()

        ],
    )

    return layout
