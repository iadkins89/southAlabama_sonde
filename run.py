from dash_app import create_app
from server import create_server

server = create_server()
app = create_app(server)

#if __name__ == '__main__':
#    server.run(port=8080, debug=True, threaded=True)
