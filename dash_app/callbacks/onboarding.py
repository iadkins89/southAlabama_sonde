from dash import callback, Input, Output, State
from flask import session

USERNAME = 'admin'
PASSWORD = 'admin'
@callback(
    [Output("login-error", "children"),
     Output("login-form", "style"),
     Output("menu", "style")],
    Input("login-btn", "n_clicks"),
    [State("username", "value"), State("password", "value")],
)
def login_user(n_clicks, username, password):
    if session['user_logged_in']:
        return "", {"display": "none"}, {"display": "block"}
    if n_clicks:
        if username == USERNAME and password == PASSWORD:
            session['user_logged_in'] = True
            return "", {"display": "none"}, {"display": "block"}
        return "Invalid credentials. Please try again.", {}, {"display": "none"}
    return "", {}, {"display": "none"}