"""
One app for the whole test run. Dash attaches its callbacks to the first app
created, so any later app would answer callbacks with an error.
"""
_server = None


def get_server():
    global _server
    if _server is None:
        from dash_app import create_app
        from server import create_server
        _server = create_server()
        create_app(_server)
    return _server
