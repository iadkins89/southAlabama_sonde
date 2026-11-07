from dash import html
import dash_bootstrap_components as dbc
from dash import dcc

def create_menu():
    navmenu = dbc.Navbar(
        dbc.Container(
            [
                dcc.Store(id="navbar-state", data={"is_open": False}),

                # Header
                dbc.Row(
                    [
                        # Logo
                        dbc.Col(
                            html.A(html.Img(src='/assets/usa_blue.png', className="navbar-logo",
                                            alt="University of South Alabama"), href="/"),
                            width="auto",
                            className="nav-logo-col"
                        ),
                        # Title
                        dbc.Col(
                            html.H1("South Alabama Telemetry", className="navbar-title"),
                            width=True,
                            className="nav-title-col d-flex align-items-center"
                        ),
                        # Sensor search and theme
                        dbc.Col(
                            [
                                html.Button(
                                    [html.I(className="bi bi-search"),
                                     html.Span("Find a sensor", className="nav-search-label"),
                                     html.Kbd("\u2318K", className="nav-search-key")],
                                    id="sensor-search-open", className="nav-search", type="button",
                                    **{"aria-label": "Find a sensor"}
                                ),
                                html.Button(
                                    html.I(className="bi bi-sun"),
                                    id="theme-toggle", className="theme-toggle", type="button",
                                    **{"aria-label": "Switch between light and dark"}
                                ),
                            ],
                            width="auto",
                            className="nav-tools d-flex align-items-center"
                        ),
                        # Hamburger Button
                        dbc.Col(
                            dbc.NavbarToggler(id="navbar-toggler", n_clicks=0),
                            width="auto",
                            className="nav-toggler-col d-flex justify-content-end"
                        ),
                    ],
                    align='center',
                    className="w-100 g-0 flex-nowrap"
                ),

                # Collapse menu
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
        expand="lg",
    )
    return navmenu
