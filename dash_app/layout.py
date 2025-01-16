import dash
from dash import dcc, html
from .navmenu import create_menu
from .footer import create_footer

def get_layout():
    layout = html.Div(
        children=[
            create_menu(),
            dash.page_container,
            create_footer()

        ],
        className='app'
    )

    return layout
