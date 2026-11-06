from server import db
from sqlalchemy import Index, func, or_, text
from sqlalchemy.orm import defer
from sqlalchemy.dialects.postgresql import JSONB
from datetime import datetime, timedelta
import pytz
from werkzeug.security import generate_password_hash, check_password_hash
from server.qc import FAIL
from server.utils import compress_image

HEALTH_PARAMS = ['Battery', 'RSSI', 'SNR', 'battery', 'rssi', 'snr', 'board_temperature']

PARAMETER_UNITS = {
    "temperature": "°C",
    "board_temperature": "°C",
    "pressure": "Pa",
    "humidity": "%",
    "velocity": "m/s",
    "acceleration": "m/s\u00B2",
    "water_level": "m",
    "wave_height": "m",
    "depth": "m",
    "dissolved_oxygen": "mg/L",
    "conductivity": "µS/cm",
    "turbidity": "NTU",
    "ph": "",
    "rssi": "dBm",
    "snr": "dB",
    "battery": "V",
}

user_sensor_association = db.Table('user_sensor',
    db.Column('user_id', db.Integer, db.ForeignKey('user.id'), primary_key=True),
    db.Column('sensor_id', db.Integer, db.ForeignKey('sensors.id'), primary_key=True)
)
class User(db.Model):
    __tablename__ = 'user'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=True)
    is_admin = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    sensors = db.relationship('Sensor', secondary=user_sensor_association, backref='users')

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

class LocationHistory(db.Model):
    __tablename__ = 'location_history'

    id = db.Column(db.Integer, primary_key=True)
    sensor_id = db.Column(db.Integer, db.ForeignKey('sensors.id'), nullable=False)
    latitude = db.Column(db.Float, nullable=False)
    longitude = db.Column(db.Float, nullable=False)

    # The span of time this sensor was at this location
    deployed_at = db.Column(db.DateTime, default=datetime.utcnow)
    removed_at = db.Column(db.DateTime, nullable=True)  # NULL means "Currently Here"

    def __repr__(self):
        return f"<LocationHistory {self.sensor_id}: {self.deployed_at} to {self.removed_at}>"

# Sensor table
class Sensor(db.Model):
    __tablename__ = 'sensors'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    device_type = db.Column(db.String(50))  # 'sonde', 'tide_gauge', etc.
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)
    navd88_elevation = db.Column(db.Float, nullable=True)  # Tide gauges: gauge height in NAVD88
    image_data = db.Column(db.Text, nullable=True)
    timezone = db.Column(db.String(50), default='America/Chicago', nullable=False)
    active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationship to data (Cascades delete: if sensor is deleted, data is deleted)
    data = db.relationship("SensorData", back_populates="sensor", cascade="all, delete-orphan")

    @property
    def is_online(self):
        """
        Dynamically calculates if the sensor is online based on
        whether it has transmitted data in the last 2 hours.
        """
        # If the sensor is manually deactivated, it's considered offline
        if not self.active:
            return False

        # Get the most recent data point for this sensor
        latest_ping = SensorData.query.filter_by(sensor_id=self.id) \
            .order_by(SensorData.timestamp.desc()) \
            .first()

        # If it has never sent data, it's offline
        if not latest_ping:
            return False

        # Check if the latest ping was within the last 2 hours
        two_hours_ago = datetime.utcnow() - timedelta(hours=2)
        return latest_ping.timestamp >= two_hours_ago

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

    # Display copy of the current QARTOD-scale flag. NULL means not evaluated.
    # The full record is in qc_assessments.
    qc_flag = db.Column(db.SmallInteger, nullable=True)

    sensor_id = db.Column(db.Integer, db.ForeignKey('sensors.id'), nullable=False)
    parameter_id = db.Column(db.Integer, db.ForeignKey('parameters.id'), nullable=False)

    sensor = db.relationship("Sensor", back_populates="data")
    parameter = db.relationship("Parameter", back_populates="data")

    # composite index for speed.
    __table_args__ = (
        Index('idx_sensor_param_time', 'sensor_id', 'parameter_id', 'timestamp'),
    )

class GaugeDatum(db.Model):
    """The gauge's NAVD88 elevation over time, so a re-survey or moved mount
    only applies to readings taken after that change."""
    __tablename__ = 'gauge_datums'

    id = db.Column(db.Integer, primary_key=True)
    sensor_id = db.Column(db.Integer, db.ForeignKey('sensors.id', ondelete='CASCADE'),
                          nullable=False, index=True)
    elevation_m = db.Column(db.Float, nullable=False)
    valid_from = db.Column(db.DateTime, nullable=False)
    valid_to = db.Column(db.DateTime, nullable=True)  # NULL means current


class GaugeReading(db.Model):
    """One row per tide gauge packet, holding what the device sent, unchanged."""
    __tablename__ = 'gauge_readings'

    id = db.Column(db.Integer, primary_key=True)
    sensor_id = db.Column(db.Integer, db.ForeignKey('sensors.id', ondelete='CASCADE'), nullable=False)
    mark_time = db.Column(db.DateTime, nullable=False)
    received_at = db.Column(db.DateTime, nullable=False)
    fcnt = db.Column(db.Integer)

    distance_mm = db.Column(db.Integer)  # NULL when the window had no valid readings
    sd_mm = db.Column(db.Integer)
    n_used = db.Column(db.Integer)
    n_rejected = db.Column(db.Integer)
    n_no_target = db.Column(db.Integer)
    n_floor = db.Column(db.Integer)

    battery_v = db.Column(db.Float)
    board_temp_c = db.Column(db.Float)
    rssi = db.Column(db.Float)
    snr = db.Column(db.Float)

    status = db.Column(db.SmallInteger, nullable=False)
    queue_depth = db.Column(db.SmallInteger)
    backfill = db.Column(db.Boolean, nullable=False, default=False)
    time_source = db.Column(db.String(10), nullable=False)  # 'device', or 'server' for compact packets
    degraded = db.Column(db.Boolean, nullable=False, default=False)  # Compact packet, coarser statistics
    time_ok = db.Column(db.Boolean, nullable=False, default=True)
    datum_id = db.Column(db.Integer, db.ForeignKey('gauge_datums.id'))

    # A device with a lost clock can repeat mark times, so only trusted times
    # have to be unique. This is also what makes redelivered packets harmless.
    __table_args__ = (
        Index('uq_gauge_reading_mark', 'sensor_id', 'mark_time', unique=True,
              postgresql_where=text('time_ok')),
    )


class QcConfig(db.Model):
    """The thresholds in force over time, so every flag can be explained later."""
    __tablename__ = 'qc_configs'

    id = db.Column(db.Integer, primary_key=True)
    sensor_id = db.Column(db.Integer, db.ForeignKey('sensors.id', ondelete='CASCADE'),
                          nullable=False, index=True)
    parameter_id = db.Column(db.Integer, db.ForeignKey('parameters.id'), nullable=False)
    thresholds = db.Column(JSONB, nullable=False)
    manual_version = db.Column(db.String(100))
    valid_from = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    valid_to = db.Column(db.DateTime, nullable=True)  # NULL means current


class QcAssessment(db.Model):
    """
    A judgement on one value. A reading can have several: a real-time QARTOD
    verdict, a model's predicted NERRS label and a reviewer's NERRS label.
    Later reviews add rows rather than changing the real-time verdict.
    """
    __tablename__ = 'qc_assessments'

    id = db.Column(db.Integer, primary_key=True)
    sensor_data_id = db.Column(db.Integer, db.ForeignKey('sensor_data.id', ondelete='CASCADE'),
                               nullable=False, index=True)
    scheme = db.Column(db.String(20), nullable=False)  # 'qartod' or 'nerrs'
    source = db.Column(db.String(20), nullable=False)  # 'realtime', 'model' or 'reviewer'
    flag = db.Column(db.SmallInteger, nullable=False)  # Read only together with scheme
    error_code = db.Column(db.String(10))              # NERRS, e.g. 'SSD'
    comment_code = db.Column(db.String(10))            # NERRS, e.g. 'CRE'
    tests = db.Column(JSONB)                           # QARTOD result per test
    score = db.Column(db.Float)                        # Model output
    corrected_value = db.Column(db.Float)              # NERRS flag 5
    config_id = db.Column(db.Integer, db.ForeignKey('qc_configs.id'))
    model_version = db.Column(db.String(50))
    assessed_by = db.Column(db.String(150))
    assessed_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        Index('uq_qc_realtime', 'sensor_data_id', 'scheme', unique=True,
              postgresql_where=text("source = 'realtime'")),
    )


# ----------------
# Query functions
#-----------------
def not_failed():
    # A plain != FAIL would also drop NULL rows, which is all unevaluated data.
    return or_(SensorData.qc_flag.is_(None), SensorData.qc_flag != FAIL)

def get_sensor_by_name(name):
    return db.session.query(Sensor).filter(Sensor.name == name).first()

def get_param_by_name(name):
    return db.session.query(Parameter).filter(Parameter.name == name).first()

def get_or_create_parameter(name):
    parameter = get_param_by_name(name)
    if not parameter:
        parameter = Parameter(name=name, canonical_unit=PARAMETER_UNITS.get(name.lower(), ""))
        db.session.add(parameter)
        db.session.flush()
    return parameter

def get_sensor_timezone(sensor_name):
    sensor = get_sensor_by_name(sensor_name)
    if sensor and sensor.timezone:
        return sensor.timezone
    return 'UTC'


def get_all_sensors():
    """Returns a list of all sensors as dictionaries.
       Doesn't use is_online for efficiency.
    """
    sensors = db.session.query(Sensor).options(defer(Sensor.image_data)).all()

    #Get the latest timestamp for ALL sensors in ONE query
    latest_data = db.session.query(
        SensorData.sensor_id,
        func.max(SensorData.timestamp).label('latest_ts')
    ).group_by(SensorData.sensor_id).all()

    latest_pings = {row.sensor_id: row.latest_ts for row in latest_data}

    two_hours_ago = datetime.utcnow() - timedelta(hours=2)

    results = []
    for s in sensors:
        is_online = False
        if s.active:
            latest_ts = latest_pings.get(s.id)
            if latest_ts and latest_ts >= two_hours_ago:
                is_online = True

        results.append({
            "name": s.name,
            "latitude": s.latitude,
            "longitude": s.longitude,
            "device_type": s.device_type,
            "active": s.active,
            "is_online": is_online,
            "last_report": latest_pings.get(s.id)
        })

    return results

def get_network_summary():
    """Sensor counts and the last day's reading count, for the home page."""
    sensors = get_all_sensors()
    active = [s for s in sensors if s['active']]
    reports = [s['last_report'] for s in active if s['last_report']]
    since = datetime.utcnow() - timedelta(hours=24)
    return {
        "sensors": sensors,
        "active": len(active),
        "online": sum(s['is_online'] for s in active),
        # One packet stores many values, so a report is one sensor at one time
        "reports_24h": db.session.query(SensorData.sensor_id, SensorData.timestamp).filter(
            SensorData.timestamp >= since).distinct().count(),
        "latest_report": max(reports) if reports else None,
    }

def get_qc_counts(sensor_name, days=7):
    """How many readings got each QC flag, over the sensor's latest few days."""
    sensor = get_sensor_by_name(sensor_name)
    if not sensor:
        return {}
    latest = db.session.query(func.max(SensorData.timestamp)).filter(
        SensorData.sensor_id == sensor.id, SensorData.qc_flag.isnot(None)).scalar()
    if not latest:
        return {}
    rows = db.session.query(SensorData.qc_flag, func.count(SensorData.id)).filter(
        SensorData.sensor_id == sensor.id,
        SensorData.qc_flag.isnot(None),
        SensorData.timestamp >= latest - timedelta(days=days)
    ).group_by(SensorData.qc_flag).all()
    return dict(rows)

def get_sensors_grouped_by_type():
    sensors = get_all_sensors()
    grouped = {}
    for s in sensors:
        d_type = s['device_type']
        if d_type not in grouped:
            grouped[d_type] = []
        grouped[d_type].append(s['name'])
    return grouped

def get_data(sensor_name, start_date, end_date, lora=False, localize_input=False, include_failed=False):
    """
        Retrieves sensor data.

        Args:
            lora (bool): If True, LoRaWAN data (rssi, snr, and battery) are returned.
                         False, all other data is retrieved
            localize_input (bool): If True, assumes start_date/end_date are in the
                                   SENSOR'S timezone. Converts them to UTC before querying.
            include_failed (bool): If True, readings that failed QC are returned too.
                                   Exports use this so that nothing is silently lost.
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
            SensorData.qc_flag.label('qc_flag'),
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

    if not include_failed:
        query = query.filter(not_failed())

    results = query.order_by(SensorData.timestamp).all()

    return results


def get_parameters(sensor_name):
    """
    Used to populate the 'Update Sensor' form.
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

    # Search only the wanted parameters, so that a health-only packet or a failed
    # reading doesn't leave the summary card empty.
    if Lora:
        wanted = [Parameter.name.in_(HEALTH_PARAMS)]
    else:
        wanted = [~Parameter.name.in_(HEALTH_PARAMS), not_failed()]

    latest_ts = db.session.query(func.max(SensorData.timestamp)) \
        .join(Parameter, SensorData.parameter_id == Parameter.id) \
        .filter(SensorData.sensor_id == sensor.id, *wanted).scalar()

    if not latest_ts:
        return []

    recent_data = (
        db.session.query(SensorData, Parameter.name, Parameter.canonical_unit) \
        .join(Parameter, SensorData.parameter_id == Parameter.id) \
        .filter(SensorData.sensor_id == sensor.id) \
        .filter(SensorData.timestamp == latest_ts) \
        .filter(*wanted) \
        .all()
    )

    return recent_data

def update_gauge_datum(sensor_id, elevation, now):
    """Starts a new datum if the elevation changed. Past readings keep their old one."""
    current = GaugeDatum.query.filter_by(sensor_id=sensor_id, valid_to=None).first()

    if current and elevation is not None and abs(current.elevation_m - elevation) < 1e-6:
        return

    if current:
        current.valid_to = now

    if elevation is not None:
        # A first datum covers everything, including any backfilled readings.
        valid_from = now if current else datetime(1970, 1, 1)
        db.session.add(GaugeDatum(sensor_id=sensor_id, elevation_m=elevation, valid_from=valid_from))


def create_or_update_sensor(name,
                            latitude,
                            longitude,
                            device_type,
                            image_data=None,
                            timezone='America/Chicago',
                            active = True,
                            user_id = None,
                            sensor_id=None,
                            navd88_elevation=None):
    try:
        now = datetime.utcnow()
        action = None

        # Prevent invalid lat/lon
        # This might should go into the callbacks that use this function
        try:
            lat_float, lon_float = float(latitude), float(longitude)
        except (ValueError, TypeError):
            return "Error: Latitude and Longitude must be numbers."

        if not (-90 <= lat_float <= 90) or not (-180 <= lon_float <= 180):
            return "Error: Coordinates out of range (Lat: -90 to 90, Lon: -180 to 180)"

        # NAVD88 elevation is optional (only meaningful for tide gauges)
        if navd88_elevation is not None and navd88_elevation != "":
            try:
                navd88_elevation = float(navd88_elevation)
            except (ValueError, TypeError):
                return "Error: NAVD88 Elevation must be a number."
        else:
            navd88_elevation = None

        sensor = None
        if sensor_id:
            sensor = Sensor.query.get(sensor_id)
        elif name:
            sensor = get_sensor_by_name(name)

        # New sensor
        if not sensor:
            sensor = Sensor(name = name)
            db.session.add(sensor)

            # Create the first history record
            new_history = LocationHistory(
                latitude=lat_float,
                longitude=lon_float,
                deployed_at=now
            )

            # Link sensor with user
            if user_id:
                user = User.query.get(user_id)
                if user:
                    user.sensors.append(sensor)

            # Link new sensor with admin accounts
            admins = User.query.filter_by(is_admin=True).all()
            for admin in admins:
                # Avoid adding twice if the creator IS the admin
                if sensor not in admin.sensors:
                    admin.sensors.append(sensor)

            # We add sensor first to generate ID
            db.session.flush()
            new_history.sensor_id = sensor.id
            db.session.add(new_history)

            action = 'created'

        # Updating sensor, address location history
        else:
            # Check if location changed significantly
            loc_changed = (abs(sensor.latitude - lat_float) > 0.0001 or
                           abs(sensor.longitude - lon_float) > 0.0001)

            status_changed_to_active = (not sensor.active and active)
            status_changed_to_inactive = (sensor.active and not active)

            # If moving, reactivating, or deactivating then close the location history record
            if loc_changed or status_changed_to_active or status_changed_to_inactive:

                # Find the currently open record (removed_at is NULL)
                current_history = LocationHistory.query.filter_by(
                    sensor_id=sensor.id,
                    removed_at=None
                ).first()

                if current_history:
                    current_history.removed_at = now

                # If we are moving or reactivating then open a new location record
                # If we are strictly deactivating, we do NOT open a new record
                if active:
                    new_history = LocationHistory(
                        sensor_id=sensor.id,
                        latitude=lat_float,
                        longitude=lon_float,
                        deployed_at=now
                    )
                    db.session.add(new_history)

        sensor.name = name
        sensor.latitude = lat_float
        sensor.longitude = lon_float
        sensor.device_type = device_type
        sensor.timezone = timezone
        sensor.active = active
        sensor.navd88_elevation = navd88_elevation
        update_gauge_datum(sensor.id, navd88_elevation, now)

        if image_data:
            sensor.image_data = compress_image(image_data)

        if not action:
            action = 'updated'

        db.session.commit()
        return f"Sensor '{name}' {action} successfully."
    except Exception as e:
        db.session.rollback()
        return f"Database Error: {str(e)}"

def get_locations_for_range(sensor, start, end):
    """The deployments that overlap a time range, oldest first."""
    return LocationHistory.query.filter(
        LocationHistory.sensor_id == sensor.id,
        LocationHistory.deployed_at <= end,
        (LocationHistory.removed_at.is_(None)) | (LocationHistory.removed_at >= start)
    ).order_by(LocationHistory.deployed_at).all()


def get_past_deployments(sensor_name):
    """
    Fetches location history for a specific sensor.
    Returns a list of dicts with formatted dates and coordinates.
    """

    sensor = get_sensor_by_name(sensor_name)
    if not sensor:
        return []

    # Query the LocationHistory table
    try:
        history_records = LocationHistory.query.filter_by(sensor_id=sensor.id)\
            .order_by(LocationHistory.deployed_at.desc()).all()
    except Exception as e:
        print(f"Error fetching history: {e}")
        return []

    deployments = []
    for record in history_records:
        # Format the dates nicely
        start_fmt = record.deployed_at.strftime("%b %d, %Y")
        if record.removed_at:
            end_fmt = record.removed_at.strftime("%b %d, %Y")
            # Calculate duration roughly
            days = (record.removed_at - record.deployed_at).days
            duration = f"{days} days"
            is_current = False
            end_iso = record.removed_at.isoformat()
        else:
            end_fmt = "Active"
            duration = "Current"
            is_current = True
            end_iso = None

        deployments.append({
            "site_name": f"Deployment: {start_fmt}",
            "range": f"{start_fmt} - {end_fmt}",
            "duration": duration,
            "latitude": record.latitude,
            "longitude": record.longitude,
            "is_current": is_current,
            "start_iso": record.deployed_at.isoformat(),
            "end_iso": end_iso
        })

    return deployments
