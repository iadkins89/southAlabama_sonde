"""
Who is signed in, and which sensors they may manage. Dash callbacks can be called
directly, so every onboarding action checks here rather than trusting the page.
"""
from flask import session

from server.database import db
from server.models import User, get_all_sensors, get_sensor_by_name, user_can_manage


def current_user():
    if not session.get('user_logged_in'):
        return None
    user_id = session.get('user_id')
    return db.session.get(User, user_id) if user_id else None


def managed_sensor(name):
    """The named sensor if the signed-in user may manage it, otherwise None."""
    sensor = get_sensor_by_name(name) if name else None
    return sensor if user_can_manage(current_user(), sensor) else None


def managed_sensors(testing=None):
    user = current_user()
    return get_all_sensors(testing=testing, user=user) if user else []
