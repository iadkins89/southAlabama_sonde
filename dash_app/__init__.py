from dash import Dash
import dash_bootstrap_components as dbc
from .layout import get_layout

FONTS = "https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Sora:wght@500;600;700&display=swap"

# The script runs before the page draws, so a dark theme never flashes white.
INDEX_STRING = """<!DOCTYPE html>
<html lang="en">
    <head>
        {%metas%}
        <title>{%title%}</title>
        <link rel="icon" type="image/svg+xml" href="/assets/favicon.svg">
        <script>
            var savedTheme = null;
            try { savedTheme = localStorage.getItem("sat-theme"); } catch (e) {}
            if (savedTheme !== "light") {
                document.documentElement.setAttribute("data-bs-theme", "dark");
            }
        </script>
        {%css%}
    </head>
    <body>
        {%app_entry%}
        <footer>
            {%config%}
            {%scripts%}
            {%renderer%}
        </footer>
    </body>
</html>"""


def create_app(server):
	socketio_cdn = "https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.6.0/socket.io.min.js"

	app = Dash(
		__name__,
		server=server,
		use_pages=True,
		suppress_callback_exceptions=True,
		external_stylesheets=[dbc.themes.MINTY, dbc.icons.BOOTSTRAP, FONTS],
		external_scripts=[socketio_cdn],
		title="South Alabama Telemetry",
		update_title=None,
		meta_tags=[
			{"name": "viewport", "content": "width=device-width, initial-scale=1"},
			{"name": "description", "content": "Live coastal water level and water quality data "
			                                   "from the University of South Alabama."},
			{"name": "theme-color", "content": "#0b3d63"},
		],
	)
	app.index_string = INDEX_STRING

	from . import callbacks
	app.layout = get_layout()

	return app
