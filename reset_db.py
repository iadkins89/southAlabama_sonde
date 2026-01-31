# reset_db.py
from server import create_server, db
from server.models import User

app = create_server()

with app.app_context():
    print("1. Creating new tables...")
    db.create_all()
    print("   - Tables created (Sensors, Parameters, SensorData, User)")

    print("2. Creating Admin User...")
    # Check if admin exists just in case
    if not User.query.filter_by(username='admin').first():
        admin = User(username='admin', email='admin@example.com')
        admin.set_password('admin') # Or your preferred password
        db.session.add(admin)
        db.session.commit()
        print("   - Admin user created (User: admin / Pass: admin)")
    else:
        print("   - Admin user already exists.")

    print("---------------------------------------")
    print("SUCCESS: Database is ready for the new code.")