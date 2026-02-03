import dash
from dash import dcc, html
from dash_app.components.navmenu import create_menu
from dash_app.components.footer import create_footer

def get_layout():
    layout = html.Div(
        children=[
            dcc.Location(id="main-url", refresh=False),
            dcc.Store(id="sensor-update"),
            html.Div(id="ws-trigger", style={"display": "none"}),
            create_menu(),
            dash.page_container,
            create_footer()

        ],
        className='app'
    )

    return layout
