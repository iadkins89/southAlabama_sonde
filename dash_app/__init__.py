from dash import Dash
import dash_bootstrap_components as dbc
from .layout import get_layout

def create_app(server):
	socketio_cdn = "https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.6.0/socket.io.min.js"

	app = Dash(
		__name__,
		server=server,
		use_pages=True,
		suppress_callback_exceptions=True,
		external_stylesheets=[dbc.themes.MINTY, dbc.icons.BOOTSTRAP],
		external_scripts=[socketio_cdn]
	)

	from . import callbacks
	app.layout = get_layout()

	return app
