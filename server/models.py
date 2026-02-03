from server import db
from sqlalchemy import Index, func
from datetime import datetime
import pytz
from werkzeug.security import generate_password_hash, check_password_hash
from server.utils import compress_image

HEALTH_PARAMS = ['Battery', 'RSSI', 'SNR', 'battery', 'rssi', 'snr']
class User(db.Model):
    __tablename__ = 'user'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password, method='pbkdf2:sha256')
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @classmethod
    def authenticate(cls, username, password):
        user = cls.query.filter_by(username=username).first()
        if user and user.check_password(password):
            return user
        return None

    def __repr__(self):
        return f"<User {self.username}>"

# Sensor table
class Sensor(db.Model):
    __tablename__ = 'sensors'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    device_type = db.Column(db.String(50))  # 'sonde', 'tide_gauge', etc.
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)
    image_data = db.Column(db.Text, nullable=True)
    timezone = db.Column(db.String(50), default='America/Chicago', nullable=False)
    active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationship to data (Cascades delete: if sensor is deleted, data is deleted)
    data = db.relationship("SensorData", back_populates="sensor", cascade="all, delete-orphan")

# Parameter table
class Parameter(db.Model):
    __tablename__ = 'parameters'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)  # e.g. "Temperature"
    canonical_unit = db.Column(db.String(20))  # e.g. "degC"

    data = db.relationship("SensorData", back_populates="parameter")

# SensorData table
class SensorData(db.Model):
    __tablename__ = 'sensor_data'
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, index=True, nullable=False)
    value = db.Column(db.Float, nullable=False)

    sensor_id = db.Column(db.Integer, db.ForeignKey('sensors.id'), nullable=False)
    parameter_id = db.Column(db.Integer, db.ForeignKey('parameters.id'), nullable=False)

    sensor = db.relationship("Sensor", back_populates="data")
    parameter = db.relationship("Parameter", back_populates="data")

    # composite index for speed.
    __table_args__ = (
        Index('idx_sensor_param_time', 'sensor_id', 'parameter_id', 'timestamp'),
    )

# ----------------
# Query functions
#-----------------
def get_sensor_by_name(name):
    return db.session.query(Sensor).filter(Sensor.name == name).first()

def get_param_by_name(name):
    return db.session.query(Parameter).filter(Parameter.name == name).first()

def get_sensor_timezone(sensor_name):
    sensor = get_sensor_by_name(sensor_name)
    if sensor and sensor.timezone:
        return sensor.timezone
    return 'UTC'

def get_all_sensors():
    """Returns a list of all sensors as dictionaries."""
    sensors = db.session.query(Sensor).all()
    return [{
        "name": s.name,
        "latitude": s.latitude,
        "longitude": s.longitude,
        "device_type": s.device_type,
        "image_data": s.image_data
    } for s in sensors]

def get_sensors_grouped_by_type():
    sensors = get_all_sensors()
    grouped = {}
    for s in sensors:
        d_type = s['device_type']
        if d_type not in grouped:
            grouped[d_type] = []
        grouped[d_type].append(s['name'])
    return grouped

def get_data(sensor_name, start_date, end_date, lora=False, localize_input=False):
    """
        Retrieves sensor data.

        Args:
            lora (bool): If True, LoRaWAN data (rssi, snr, and battery) are returned.
                         False, all other data is retrieved
            localize_input (bool): If True, assumes start_date/end_date are in the
                                   SENSOR'S timezone. Converts them to UTC before querying.
        """
    sensor = get_sensor_by_name(sensor_name)
    if not sensor:
        return []

    if localize_input and sensor.timezone:
        try:
            local_tz = pytz.timezone(sensor.timezone)
            if start_date.tzinfo is None:
                start_date = local_tz.localize(start_date).astimezone(pytz.utc).replace(tzinfo=None)
            if end_date.tzinfo is None:
                end_date = local_tz.localize(end_date).astimezone(pytz.utc).replace(tzinfo=None)
        except:
            pass

    query = (
        db.session.query(
            SensorData.timestamp.label('timestamp'),
            SensorData.value.label('value'),
            Parameter.name.label('name'),
            Parameter.canonical_unit.label('unit')
        )
        .join(Parameter, SensorData.parameter_id == Parameter.id)
        .filter(SensorData.sensor_id == sensor.id)
        .filter(SensorData.timestamp >= start_date)
        .filter(SensorData.timestamp <= end_date)
    )

    if lora:
        query = query.filter(Parameter.name.in_(HEALTH_PARAMS))
    else:
        query = query.filter(Parameter.name.notin_(HEALTH_PARAMS))

    results = query.order_by(SensorData.timestamp).all()

    return results


def get_parameters(sensor_name):
    """
    Adapter
    Used to populate the 'Update Sensor' form.
    New logic: Query distinct parameters from the data table.
    """
    sensor = get_sensor_by_name(sensor_name)
    if not sensor:
        return []

    # Find all parameter IDs this sensor has data for
    param_ids = (
        db.session.query(SensorData.parameter_id)
        .filter(SensorData.sensor_id == sensor.id)
        .distinct()
    )

    params = (
        db.session.query(Parameter.name, Parameter.canonical_unit)
        .filter(Parameter.id.in_(param_ids))
        .all()
    )
    return params

def get_most_recent(sensor_name, Lora = False):

    sensor = get_sensor_by_name(sensor_name)
    if not sensor:
        return []

    latest_ts = db.session.query(func.max(SensorData.timestamp)) \
        .filter_by(sensor_id=sensor.id).scalar()

    if not latest_ts:
        return []

    query = (
        db.session.query(SensorData, Parameter.name, Parameter.canonical_unit) \
        .join(Parameter, SensorData.parameter_id == Parameter.id) \
        .filter(SensorData.sensor_id == sensor.id) \
        .filter(SensorData.timestamp == latest_ts) \
        )

    if Lora:
        recent_data = query.filter(Parameter.name.in_(HEALTH_PARAMS)).all()
    else:
        recent_data = query.filter(~Parameter.name.in_(HEALTH_PARAMS)).all()

    return recent_data

def create_or_update_sensor(name, latitude, longitude, device_type, image_data=None, timezone='America/Chicago', active = True):
    """Creates a new sensor. DEPRECIATED Does NOT handle parameters (dynamic)."""
    try:
        sensor = get_sensor_by_name(name)
        action = None
        if not sensor:
            sensor = Sensor(name = name)
            db.session.add(sensor)
            action = 'created'

        sensor.latitude = latitude
        sensor.longitude = longitude
        sensor.device_type = device_type
        sensor.timezone = timezone
        sensor.active = active

        if image_data:
            sensor.image_data = compress_image(image_data)

        if not action:
            action = 'updated'

        db.session.commit()
        return f"Sensor '{name}' {action} successfully."
    except Exception as e:
        db.session.rollback()
        return f"Database Error: {str(e)}"
