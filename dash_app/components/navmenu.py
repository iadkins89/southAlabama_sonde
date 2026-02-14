from dash import html
import dash_bootstrap_components as dbc
from dash import dcc

def create_menu():
    navmenu = dbc.Navbar(
        dbc.Container(
            [
                dcc.Store(id="navbar-state", data={"is_open": False}),

                # HEADER ROW
                dbc.Row(
                    [
                        # Logo
                        dbc.Col(
                            html.Img(src='/assets/usa_blue.png', className="navbar-logo"),
                            width="auto",
                        ),
                        # Title
                        dbc.Col(
                            html.H1("South Alabama Telemetry", className="navbar-title"),
                            width=True,
                            className="d-flex align-items-center"
                        ),
                        # Hamburger Button (Visible Always)
                        dbc.Col(
                            dbc.NavbarToggler(id="navbar-toggler", n_clicks=0),
                            width="auto",
                            className="d-flex justify-content-end"
                        ),
                    ],
                    align='center',
                    className="w-100 g-0 flex-nowrap"
                ),

                # COLLAPSIBLE MENU
                dbc.Collapse(
                    dbc.Nav(
                        [
                            dbc.NavLink("Home", active="exact", href="/", className="nav-pill", id="home-link"),
                            dbc.DropdownMenu(
                                label="Sensors",
                                nav=True,
                                id="sensors-dropdown",
                                children=[],
                                className="nav-pill-dropdown",
                            ),
                            dbc.NavLink("Onboard Sensor", active="exact", href="/onboarding", className="nav-pill",
                                        id="onboarding-link"),
                            dbc.NavLink("About", active="exact", href="/about", className="nav-pill", id="about-link"),
                        ],
                        pills=True,
                        className="nav-menu ms-auto",
                    ),
                    id="navbar-collapse",
                    is_open=False,
                    navbar=True,
                ),
            ],
            fluid=True
        ),
        class_name="custom-navbar",
        # CRITICAL CHANGE: expand=False forces the hamburger on ALL screen sizes
        expand=False,
    )
    return navmenu
