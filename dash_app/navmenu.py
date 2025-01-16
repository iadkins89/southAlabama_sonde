from dash import html
import dash_bootstrap_components as dbc
from dash import dcc

def create_menu():
    navmenu = dbc.Navbar(
        dbc.Container(
            [
                dcc.Store(id="navbar-state", data={"is_open": False}),
                # Navbar header: logo and title
                dbc.Row(
                    [
                        dbc.Col(
                            html.Img(src='/assets/usa_blue.png', style={'height': '100px'}),
                            width='auto',
                        ),
                        dbc.Col(
                            html.H1(
                                "South Alabama Telemetry",
                                className="text-left",
                                style={'color': '#154360'},
                            ),
                            width='auto',
                        ),
                    ],
                    align='center',
                ),

                # Toggler for hamburger menu (mobile view)
                dbc.NavbarToggler(id="navbar-toggler", n_clicks=0),

                # Collapsible navigation menu
                dbc.Collapse(
                    dbc.Nav(
                        [
                            dbc.NavLink("Home", active="exact", href="/", className="nav-pill", id = "home-link"),
                            dbc.DropdownMenu(
                                label="Sensors",
                                nav=True,
                                id="sensors-dropdown",  # Dropdown ID for dynamic population
                                children=[],  # Placeholder - will be updated dynamically
                                className="nav-pill-dropdown",
                            ),
                            dbc.NavLink(
                                "Onboard Sensor", active="exact", href="/onboarding", className="nav-pill", id="onboarding-link"
                            ),
                            dbc.NavLink("About", active="exact", href="/about", className="nav-pill", id="about-link"),
                        ],
                        pills=True,
                        className="nav-menu",
						style={"margin-left": "auto"},  # Ensures right alignment
					),
                    id="navbar-collapse",
                    is_open=False,  # Initially collapsed
                    navbar=True,
                ),
            ]
        ),
        class_name="custom-navbar",
    )

    return navmenu