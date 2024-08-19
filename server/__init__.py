from flask import Flask
from .database import db, init_db
from .routes import setup_routes
import os

def create_server():

    server = Flask(__name__)
    server.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get("DATABASE_URL")
    server.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    init_db(server)
    
    with server.app_context():
        setup_routes(server)

    return server
