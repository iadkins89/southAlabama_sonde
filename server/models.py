from server import db
from sqlalchemy import Index, desc, func
from datetime import datetime
import pytz
from collections import defaultdict
import pandas as pd
from werkzeug.security import generate_password_hash, check_password_hash

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
    image_url = db.Column(db.String(500), nullable=True)
    timezone = db.Column(db.String(50), default='America/Chicago', nullable=False)

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
        "image_url": s.image_url
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

def query_data(sensor_name, start_date, end_date, lora=False, localize_input=False):
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

def query_most_recent_lora(sensor_name):
    """
        Fetches the most recent Battery, RSSI, and SNR for a sensor.
        Queries SensorData (since LoraData table is gone).
        """
    sensor = get_sensor_by_name(sensor_name)

    if not sensor:
        return []

    # The parameters we consider "Health" stats
    health_params = ['battery', 'rssi', 'snr']
    results = []

    for param_name in health_params:
        # Find the parameter ID
        param = Parameter.query.filter_by(name=param_name).first()
        if not param:
            continue

        # Get latest reading for this specific parameter
        latest = db.session.query(SensorData) \
            .filter_by(sensor_id=sensor.id, parameter_id=param.id) \
            .order_by(SensorData.timestamp.desc()) \
            .first()

        if latest:
            results.append((param_name, latest.timestamp, latest.value))

    return results

def create_or_update_sensor(name, latitude, longitude, device_type, image_url=None, timezone='America/Chicago'):
    """Creates a new sensor. Does NOT handle parameters (dynamic)."""
    try:
        sensor = get_sensor_by_name(name)
        if sensor:
            sensor.latitude = latitude
            sensor.longitude = longitude
            sensor.device_type = device_type
            sensor.timezone = timezone

            if image_url:
                sensor.image_url = image_url

            action = 'updated'
        else:
            sensor = Sensor(
                name=name,
                latitude=latitude,
                longitude=longitude,
                device_type=device_type,
                image_url=image_url,
                timezone = timezone
            )
            db.session.add(sensor)
            action = "created"

            db.session.commit()
        return f"Sensor '{name}' {action} successfully."
    except Exception as e:
        db.session.rollback()
        return f"Database Error: {str(e)}"

def get_measurement_summary(sensor_name, include_health=False):
    """
    Fetches the single most recent data this sensor has reported.
    Excludes sensor health related data
    """
    sensor = get_sensor_by_name(sensor_name)
    if not sensor:
        return {"error": f"Sensor '{sensor_name}' not found"}

    # Get the most recent timestamp for this sensor
    latest_ts = db.session.query(func.max(SensorData.timestamp)) \
        .filter_by(sensor_id=sensor.id).scalar()

    if not latest_ts:
        return {"message": f"No data available for sensor '{sensor_name}'"}

    # Fetch all parameters for the latest timestamp not including health params
    recent_data = db.session.query(SensorData, Parameter.name, Parameter.canonical_unit) \
        .join(Parameter, SensorData.parameter_id == Parameter.id) \
        .filter(SensorData.sensor_id == sensor.id) \
        .filter(SensorData.timestamp == latest_ts) \
        .filter(~Parameter.name.in_(HEALTH_PARAMS))\
        .all()

    summary_list = []

    for data_obj, p_name, p_unit in recent_data:
        summary_list.append({
            "parameter": f"{p_name} ({p_unit})",
            "value": data_obj.value,
            "timestamp": data_obj.timestamp
        })

    return {
        "sensor_name": sensor.name,
        "latitude": sensor.latitude,
        "longitude": sensor.longitude,
        "timezone": sensor.timezone,
        "most_recent_measurements": summary_list
    }

def save_data_to_csv(data, sensor_name):
    organized_data = defaultdict(dict)

    timezone_str = get_sensor_timezone(sensor_name)

    for timestamp, value, parameter, unit in data:
        organized_data[timestamp][f"{parameter} ({unit})"] = value

    # Create a DataFrame from the organized data
    df = pd.DataFrame.from_dict(organized_data, orient='index').reset_index()

    # Rename the first column to 'timestamp (timezone)'
    formatted_time = f"timestamp ({timezone_str})"
    df.rename(columns={'index': formatted_time}, inplace=True)

    # Convert the DataFrame to a CSV string
    csv_data = df.to_csv(index=False)
    sensor_name_line = f"Sensor Name: {sensor_name}\n"
    csv_data = sensor_name_line + csv_data

    return csv_data

#----------- OLD -------------------------------

def update_sensor_parameters(*args, **kwargs):
    print("WARNING: update_sensor_parameters is deprecated in the new schema.")
    pass

def update_sensor_data(*args, **kwargs):
    print("WARNING: update_sensor_data is deprecated in the new schema.")
    pass

def delete_unused_parameters(*args, **kwargs):
    pass

