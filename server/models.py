from sqlalchemy import distinct, ForeignKey, Table
from sqlalchemy.orm import relationship
from sqlalchemy.exc import SQLAlchemyError
import os
import base64
from datetime import datetime
from server import db
import pandas as pd
from dateutil.parser import parse as parse_date
from collections import defaultdict


# Association table for many-to-many relationship between Sensor and Parameter
sensor_parameter = Table(
    'sensor_parameter',
    db.Model.metadata,
    db.Column('sensor_id', db.Integer, ForeignKey('sensor.id'), primary_key=True),
    db.Column('parameter_id', db.Integer, ForeignKey('parameter.id'), primary_key=True),
)

# Sensor table
class Sensor(db.Model):
    __tablename__ = 'sensor'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String, unique=True, nullable=False)
    latitude = db.Column(db.Float, nullable=False)
    longitude = db.Column(db.Float, nullable=False)
    device_type = db.Column(db.String, nullable=False)
    image = db.Column(db.String, nullable=True)

    # Relationship with sensor_data
    sensor_data = relationship('SensorData', back_populates='sensor')
    lora_data = relationship('LoraData', back_populates='sensor')  # Added relationship for LoraData

    # Many-to-many relationship with Parameter
    parameters = relationship('Parameter', secondary=sensor_parameter, back_populates='sensors')

    def __repr__(self):
        return f"<Sensor {self.name}>"

# Parameter table
class Parameter(db.Model):
    __tablename__ = 'parameter'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String, unique=True, nullable=False)

    # Many-to-many relationship with Sensor
    sensors = relationship('Sensor', secondary=sensor_parameter, back_populates='parameters')
    def __repr__(self):
        return f"<Parameter {self.name}>"

# SensorData table
class SensorData(db.Model):
    __tablename__ = 'sensor_data'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    sensor_id = db.Column(db.Integer, ForeignKey('sensor.id'), nullable=False)
    timestamp = db.Column(db.DateTime, index=True, nullable=False)
    parameter_id = db.Column(db.Integer, ForeignKey('parameter.id'), nullable=False)
    value = db.Column(db.Float, nullable=False)

    # Relationships
    sensor = relationship('Sensor', back_populates='sensor_data')

    def __repr__(self):
        return f"<SensorData {self.sensor_id} {self.timestamp} {self.parameter_id} {self.value}>"

# LoraData table
class LoraData(db.Model):
    __tablename__ = 'lora_data'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    sensor_id = db.Column(db.Integer, ForeignKey('sensor.id'), nullable=False)
    timestamp = db.Column(db.DateTime, index=True, nullable=False)
    rssi = db.Column(db.Integer, nullable=False)
    snr = db.Column(db.Float, nullable=False)
    battery = db.Column(db.Float, nullable=True)

    # Relationships
    sensor = relationship('Sensor', back_populates='lora_data')

    def __repr__(self):
        return f"<LoraData {self.sensor_id} {self.timestamp} {self.rssi} {self.snr}>"


def query_most_recent_lora(sensor_name):
    result = (
        db.session.query(LoraData.rssi, LoraData.snr)
        .join(Sensor)
        .filter(Sensor.name == sensor_name)
        .order_by(desc(LoraData.timestamp))
        .first()
    )

    return result
# Query function
def query_data(start_date, end_date, sensor_name):
    start_dt = parse_date(start_date).replace(hour=0, minute=0, second=0)
    end_dt = parse_date(end_date).replace(hour=23, minute=59, second=59)

    result = (
        db.session.query(Parameter.name, SensorData.timestamp, SensorData.value)
        .join(Sensor)
        .join(Parameter)
        .filter(Sensor.name == sensor_name, SensorData.parameter_id == Parameter.id, SensorData.timestamp >= start_dt, SensorData.timestamp <= end_dt)
        .all()
    )

    return result

def query_lora_data(start_date, end_date, sensor_name):
    start_dt = parse_date(start_date).replace(hour=0, minute=0, second=0)
    end_dt = parse_date(end_date).replace(hour=23, minute=59, second=59)

    result = (
        db.session.query(LoraData.rssi, LoraData.snr, LoraData.timestamp)
        .join(Sensor)
        .filter(Sensor.name == sensor_name, LoraData.timestamp >= start_dt, LoraData.timestamp <= end_dt)
        .all()
    )

    return result

# Save data to CSV
def save_data_to_csv(data, sensor_name):
    organized_data = defaultdict(dict)
    for parameter, timestamp, value in data:
        organized_data[timestamp][parameter] = value

    # Create a DataFrame from the organized data
    df = pd.DataFrame.from_dict(organized_data, orient='index').reset_index()

    # Rename the first column to 'timestamp'
    df.rename(columns={'index': 'timestamp'}, inplace=True)

    # Convert the DataFrame to a CSV string
    csv_data = df.to_csv(index=False)
    sensor_name_line = f"Sensor Name: {sensor_name}\n"
    csv_data = sensor_name_line + csv_data

    return csv_data

# Get unique sensor names
def get_unique_sensor_names():
    unique_names = db.session.query(distinct(Sensor.name)).all()
    return [name[0] for name in unique_names]

from sqlalchemy import func, desc
from datetime import datetime, timedelta

from sqlalchemy import desc
from datetime import datetime

def get_measurement_summary(sensor_name):
    """
    Returns the most recent measurement data for a specific sensor.

    Parameters:
        sensor_name (str): The name of the sensor.

    Returns:
        dict: A dictionary containing the most recent measurement information.
    """
    # Check if the sensor exists
    sensor = db.session.query(Sensor).filter(Sensor.name == sensor_name).first()
    if not sensor:
        return {"error": f"Sensor '{sensor_name}' not found"}

    # Fetch parameters for this sensor from the parameters table
    sensor_parameters = (
        db.session.query(Parameter.name)
        .join(sensor_parameter, sensor_parameter.c.parameter_id == Parameter.id)
        .filter(sensor_parameter.c.sensor_id == sensor.id)
        .all()
    )
    parameter_names = [param.name for param in sensor_parameters]

    # If no parameters are associated with the sensor, return an error
    if not parameter_names:
        return {"error": f"No parameters found for sensor '{sensor_name}'"}

    # Fetch the most recent data for each parameter
    recent_data = (
        db.session.query(SensorData.parameter_id, SensorData.value, SensorData.timestamp)
        .join(Sensor)
        .filter(Sensor.name == sensor_name)
        .order_by(desc(SensorData.timestamp))
        .limit(len(parameter_names))  # Fetch one record per parameter
        .all()
    )

    if not recent_data:
        return {"message": f"No data available for sensor '{sensor_name}'"}

    # Format the output
    summary = {
        "sensor_name": sensor_name,
        "most_recent_measurements": [
            {
                "parameter": db.session.query(Parameter.name)
                .filter(Parameter.id == record.parameter_id)
                .scalar(),
                "value": record.value,
                "timestamp": record.timestamp,
            }
            for record in recent_data
        ],
    }

    return summary

def get_sensor_by_name(device_name):
    """Retrieve a sensor by its name."""
    return db.session.query(Sensor).filter_by(name=device_name).first()

def create_or_update_sensor(device_name, latitude, longitude, device_type, image_data=None, base_path=None):
    """
    Create or update a sensor in the database.

    Args:
        device_name (str): Name of the sensor.
        latitude (float): Latitude of the sensor.
        longitude (float): Longitude of the sensor.
        device_type (str): Type of the sensor.
        image_data (str, optional): Base64-encoded image data.
        base_path (str, optional): Base path to save images. Defaults to None.

    Returns:
        str: Success or error message.
    """
    try:
        # Check if the sensor exists
        sensor = get_sensor_by_name(device_name)

        if sensor:  # Update existing sensor
            sensor.latitude = latitude
            sensor.longitude = longitude
            sensor.device_type = device_type

            if image_data and base_path:
                save_path = os.path.join(base_path, f"{device_name}.png")
                with open(save_path, "wb") as f:
                    f.write(base64.b64decode(image_data))
                sensor.image_path = save_path
        else:  # Create a new sensor
            new_sensor = Sensor(
                name=device_name,
                latitude=latitude,
                longitude=longitude,
                device_type=device_type,
                image_path=None
            )

            if image_data and base_path:
                save_path = os.path.join(base_path, f"{device_name}.png")
                with open(save_path, "wb") as f:
                    f.write(base64.b64decode(image_data))
                new_sensor.image_path = save_path

            db.session.add(new_sensor)

        db.session.commit()
        return f"Sensor '{device_name}' successfully created/updated!"
    except SQLAlchemyError as e:
        db.session.rollback()
        return f"Database error: {str(e)}"
    except Exception as e:
        return f"An error occurred: {str(e)}"


