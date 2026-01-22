from flask import Flask, redirect, url_for, request, session
from .database import db, init_db
from .routes import setup_routes
import os
from datetime import timedelta
from .socketio import socketio

def create_server():

    server = Flask(__name__)
    server.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get("DATABASE_URL")
    server.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    # Add session configuration
    server.config["SECRET_KEY"] = os.environ.get("SECRET_KEY")
    server.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=30)

    socketio.init_app(server)

    @server.before_request
    def before_request():
        if 'user_logged_in' not in session:
            session['user_logged_in'] = False  # Initialize to False when first visiting the site
        session.permanent = True  # Enable session permanence

    init_db(server)
    
    with server.app_context():
        setup_routes(server)

    return server
