from .socketio import socketio

def emit_event(event_name, payload):
    """
    Emit arbitrary payloads over WebSocket.
    Payload is assumed to already be JSON-serializable.
    """
    socketio.emit(event_name, payload, namespace='/')
