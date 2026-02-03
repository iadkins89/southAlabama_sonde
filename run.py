import os
from dash_app import create_app
from server import create_server
from server.socketio import socketio

server = create_server()
app = create_app(server)

if __name__ == "__main__":
    is_production = os.environ.get('FLASK_ENV') == 'production'
    debug_mode = not is_production

    print(f"Starting server... (Debug Mode: {debug_mode})")

    socketio.run(server, debug=debug_mode, host="0.0.0.0", port=8050)
