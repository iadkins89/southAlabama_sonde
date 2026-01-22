from dash_app import create_app
from server import create_server
from server.socketio import socketio

server = create_server()
app = create_app(server)

if __name__ == "__main__":
    socketio.run(server, debug=True, host="0.0.0.0", port=8050)
