from dash import callback, Input, Output, State
from flask import session
from server.models import User

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
    # If already logged in show menu
    if session['user_logged_in']:
        return "", {"display": "none"}, {"display": "block"}
    if n_clicks:
        user = User.authenticate(username, password)
        if user:
            session['user_logged_in'] = True
            return "", {"display": "none"}, {"display": "block"}
        return "Invalid credentials. Please try again.", {}, {"display": "none"}
    return "", {}, {"display": "none"}