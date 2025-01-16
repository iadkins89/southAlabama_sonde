from flask import Flask, redirect, url_for, request, session
from flask_session import Session
from .database import db, init_db
from .routes import setup_routes
import os
from datetime import timedelta

def create_server():

    server = Flask(__name__)
    server.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get("DATABASE_URL")
    server.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    # Add session configuration
    server.config["SECRET_KEY"] = "982d1a997ecb712756e836c0a022fd301a04f5bd18debd3e016d53b168a4c0c9"
    #server.config['PERMANENT_SESSION_LIFETIME'] = timedelta(seconds=30)
    server.config["SESSION_TYPE"] = "filesystem"  # Use server-side session storage
    Session(server)  # Initialize Flask-Session

    @server.before_request
    def before_request():
        if 'user_logged_in' not in session:
            session['user_logged_in'] = False  # Initialize to False when first visiting the site
        session.permanent = False  # Enable session permanence

    init_db(server)
    
    with server.app_context():
        setup_routes(server)

    return server
