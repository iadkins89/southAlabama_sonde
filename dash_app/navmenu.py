from dash import html
import dash_bootstrap_components as dbc
from dash import dcc

def create_menu():

	navmenu = dbc.Navbar(
	    dbc.Container(
	        [
	        	dbc.Row([
	            	dbc.Col(html.Img(src='/assets/usa_blue.png', style={'height': '100px'}), width='auto'),
	            	dbc.Col(html.H1("South Alabama Telemetry", className="text-left", style={'color': '#154360'}), width='auto')
	        	], align='center'),
	            dbc.Nav(
	                [
				        dbc.NavLink("Home", active="exact", href="/"),
						dbc.DropdownMenu(
							label="Sensors",
							nav=True,
							id="sensors-dropdown",  # Dropdown ID for dynamic population
							children=[],  # Placeholder - will be updated dynamically
						),
				        dbc.NavLink("Onboard Sensor", active="exact", href="/onboarding"),
				        dbc.NavLink("About", active="exact", href="/about"),				      
	                ],
	                pills=True,
	            ),
	        ]
	    ),
	    class_name = "custom-navbar"
	)

	return navmenu