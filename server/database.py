from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

def init_db(server):
    db.init_app(server)
    with server.app_context():
        db.create_all()
        
    