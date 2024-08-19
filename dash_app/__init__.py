from dash import Dash
import dash_bootstrap_components as dbc
from .layout import get_layout
from .callbacks import register_callbacks

def create_app(server):
	app = Dash(__name__, server=server, use_pages=True, external_stylesheets=[dbc.themes.MINTY])

	app.layout = get_layout()
	register_callbacks(app)

	return app
