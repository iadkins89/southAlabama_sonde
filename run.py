from dash_app import create_app
from server import create_server

server = create_server()
app = create_app(server)

if __name__ == '__main__':
    server.run(host='0.0.0.0', port=8080, debug=False, threaded=True)