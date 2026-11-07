from dash import html, register_page
import dash_bootstrap_components as dbc

register_page(__name__, path="/404", title="Page not found | South Alabama Telemetry")


def layout(**_):
    return html.Div(
        html.Div(
            [
                html.Div(html.I(className="bi bi-compass"), className="empty-icon"),
                html.H1("We couldn't find that page", className="empty-title"),
                html.P("The link may be old, or the page may have moved.", className="empty-text"),
                dbc.Button("Back to the sensor map", href="/", color="primary"),
            ],
            className="empty-state",
        ),
        className="page-narrow",
    )
