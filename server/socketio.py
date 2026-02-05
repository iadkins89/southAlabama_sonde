from flask_socketio import SocketIO
trusted_origins = [
    "https://goldfish-app-89ghz.ondigitalocean.app",
    "http://localhost:8050",
    "http://127.0.0.1:8050"
]
socketio = SocketIO(cors_allowed_origins="*", async_mode='eventlet')
#socketio = SocketIO(cors_allowed_origins=trusted_origins)
