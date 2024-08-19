from dash_app import create_app
from server import create_server

server = create_server()
app = create_app(server)
