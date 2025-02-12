from sqlalchemy import distinct, ForeignKey, Table
from sqlalchemy.orm import relationship
from sqlalchemy.exc import SQLAlchemyError
import os
import base64
from werkzeug.security import generate_password_hash, check_password_hash  # For hashing passwords
from server import db
import pandas as pd
from dateutil.parser import parse as parse_date
from collections import defaultdict
from sqlalchemy import desc

class User(db.Model):
    __tablename__ = 'user'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, password):
        """Hashes the password for storage."""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        """Checks if the provided password matches the stored hash."""
        return check_password_hash(self.password_hash, password)

    @classmethod
    def authenticate(cls, username, password):
        """Authenticate a user based on username and password."""
        user = cls.query.filter_by(username=username).first()
        if user and user.check_password(password):
            return user
        return None

    def __repr__(self):
        return f"<User {self.username}>"

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
    is_active = db.Column(db.Boolean, nullable=False, default=True)

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
    name = db.Column(db.String, nullable=False)
    unit =db.Column(db.String, nullable=True)

    __table_args__ = (db.UniqueConstraint('name', 'unit', name='uix_name_unit'),) #composite unique constraint between name and unit

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
    parameter_id = db.Column(db.Integer, ForeignKey('parameter.id'), nullable=False)
    value = db.Column(db.Float, nullable=False)

    # Relationships
    sensor = relationship('Sensor', back_populates='lora_data')

    def __repr__(self):
        return f"<LoraData {self.sensor_id} {self.timestamp} {self.rssi} {self.snr}>"


def query_most_recent_lora(sensor_name):
    result = (
        db.session.query(Parameter.name, LoraData.timestamp, LoraData.value)
        .join(Sensor)
        .join(Parameter)
        .filter(Sensor.name == sensor_name, LoraData.parameter_id == Parameter.id)
        .order_by(desc(LoraData.timestamp))
        .limit(3)  # Fetch one record per parameter
        .all()
    )
    return result
# Query function
def query_data(start_date, end_date, sensor_name, include_units=False):

    # Query database
    query = (
        db.session.query(Parameter.name, SensorData.timestamp, SensorData.value)
        .join(Sensor)
        .join(Parameter)
        .filter(Sensor.name == sensor_name, SensorData.parameter_id == Parameter.id, SensorData.timestamp >= start_date, SensorData.timestamp <= end_date)
    )

    if include_units:
        query = query.add_columns(Parameter.unit)

    result = query.all()

    return result


def query_lora_data(start_date, end_date, sensor_name, include_units=False):

    query = (
        db.session.query(Parameter.name, LoraData.timestamp, LoraData.value)
        .join(Sensor)
        .join(Parameter)
        .filter(Sensor.name == sensor_name, LoraData.parameter_id == Parameter.id, LoraData.timestamp >= start_date, LoraData.timestamp <= end_date)
    )

    if include_units:
        query = query.add_columns(Parameter.unit)

    result = query.all()

    return result

# Save data to CSV
def save_data_to_csv(data, sensor_name):
    organized_data = defaultdict(dict)
    for parameter, timestamp, value, unit in data:
        organized_data[timestamp][f"{parameter} ({unit})"] = value

    # Create a DataFrame from the organized data
    df = pd.DataFrame.from_dict(organized_data, orient='index').reset_index()

    # Rename the first column to 'timestamp'
    df.rename(columns={'index': 'timestamp'}, inplace=True)

    # Convert the DataFrame to a CSV string
    csv_data = df.to_csv(index=False)
    sensor_name_line = f"Sensor Name: {sensor_name}\n"
    csv_data = sensor_name_line + csv_data

    return csv_data


def get_all_sensors():
    """
    Retrieves all sensors from the database with their names, latitude, longitude, and device types.

    Returns:
        list: A list of dictionaries, each containing sensor details.
    """
    try:
        sensors = Sensor.query.all()
        return [
            {
                "name": sensor.name,
                "latitude": sensor.latitude,
                "longitude": sensor.longitude,
                "device_type": sensor.device_type,
            }
            for sensor in sensors
        ]
    except Exception as e:
        print(f"Error retrieving sensors: {e}")
        return []

def get_sensors_grouped_by_type():
    """
    Retrieve all sensors from the database and group them by type.

    Returns:
        dict: A dictionary where keys are sensor types, and values are lists of sensors of that type.
    """
    sensors = get_all_sensors()  # Retrieve sensors from your database
    grouped_sensors = {}

    for sensor in sensors:
        device_type = sensor["device_type"]
        if device_type not in grouped_sensors:
            grouped_sensors[device_type] = []
        grouped_sensors[device_type].append(sensor["name"])

    return grouped_sensors

def get_parameters(sensor_name):
    sensor = db.session.query(Sensor).filter(Sensor.name == sensor_name).first()
    if not sensor:
        return {"error": f"Sensor '{sensor_name}' not found"}

    # Fetch parameters for this sensor from the parameters table
    sensor_parameters = (
        db.session.query(Parameter.name, Parameter.unit)
        .join(sensor_parameter, sensor_parameter.c.parameter_id == Parameter.id)
        .filter(sensor_parameter.c.sensor_id == sensor.id)
        .all()
    )

    return sensor_parameters

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

    # Fetch parameters for this sensor
    sensor_parameters = (
        db.session.query(Parameter.name, Parameter.unit)
        .join(sensor_parameter, sensor_parameter.c.parameter_id == Parameter.id)
        .filter(sensor_parameter.c.sensor_id == sensor.id)
        .all()
    )
    parameter_names = [
        f"{param.name} ({param.unit})" if param.unit else param.name for param in sensor_parameters
    ]

    # If no parameters are associated with the sensor, return an error
    if not parameter_names:
        return {"error": f"No parameters found for sensor '{sensor_name}'"}

    remove = ['battery', 'rssi', 'snr']

    # Fetch the most recent data for each parameter
    recent_data = (
        db.session.query(SensorData.parameter_id, SensorData.value, SensorData.timestamp)
        .join(Sensor)
        .filter(Sensor.name == sensor_name)
        .filter(Parameter.name not in remove)
        .order_by(desc(SensorData.timestamp))
        .limit(len(parameter_names)-3)
        .all()
    )

    if not recent_data:
        return {"message": f"No data available for sensor '{sensor_name}'"}

    # Format the output
    summary = {
        "sensor_name": sensor_name,
        "latitude": sensor.latitude,
        "longitude": sensor.longitude,
        "most_recent_measurements": [
            {
                "parameter": f"{db.session.query(Parameter.name).filter(Parameter.id == record.parameter_id).scalar()} ({db.session.query(Parameter.unit).filter(Parameter.id == record.parameter_id).scalar()})",
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


def decode_base64(image_data):
    if "," in image_data:
        # Split off the metadata prefix
        _, base64_data = image_data.split(",", 1)
    else:
        base64_data = image_data

    # Decode the Base64 string
    return base64.b64decode(base64_data)

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
                decoded_image = decode_base64(image_data)
                with open(save_path, "wb") as f:
                    f.write(decoded_image)
                sensor.image_path = save_path
        else:  # Create a new sensor
            new_sensor = Sensor(
                name=device_name,
                latitude=latitude,
                longitude=longitude,
                device_type=device_type,
                image=None
            )

            if image_data and base_path:
                save_path = os.path.join(base_path, f"{device_name}.png")
                decoded_image = decode_base64(image_data)
                with open(save_path, "wb") as f:
                    f.write(decoded_image)
                new_sensor.image_path = save_path

            db.session.add(new_sensor)

        db.session.commit()
        return f"Sensor '{device_name}' successfully created/updated!"
    except SQLAlchemyError as e:
        db.session.rollback()
        return f"Database error: {str(e)}"
    except Exception as e:
        return f"An error occurred: {str(e)}"

def add_parameter_if_not_exists(parameter_name, unit):
    """
    Check if a parameter with the given name and unit exists. If not, create it.
    """
    existing_parameter = db.session.query(Parameter).filter_by(name=parameter_name, unit=unit).first()

    if not existing_parameter:
        new_parameter = Parameter(name=parameter_name, unit=unit)
        db.session.add(new_parameter)
        db.session.commit()

        return new_parameter  # Return the new parameter
    return existing_parameter  # Return the existing parameter

def update_sensor_parameters(sensor, updated_parameters):
    """
    Update the parameters for a given sensor, while keeping the ones that aren't changed and
    only updating specific parameters (name and/or unit).
    """
    # Map existing parameters for the sensor (name, unit) -> Parameter object
    existing_parameters = {(param.name, param.unit): param for param in sensor.parameters}
    print(f"Existing parameters for sensor '{sensor.name}': {list(existing_parameters.keys())}")
    print(f"Updated parameters to process: {updated_parameters}")

    # Set to track parameters to retain (those that aren't being updated)
    parameters_to_retain = set(existing_parameters.keys())

    # Loop through updated parameters to update them
    for param_name, param_unit in updated_parameters:
        # Add or fetch the parameter
        param = add_parameter_if_not_exists(param_name, param_unit)

        # If the parameter is not already associated with the sensor, associate it
        if (param_name, param_unit) not in existing_parameters:
            sensor.parameters.append(param)
            parameters_to_retain.add((param_name, param_unit))
            print(f"Added parameter '{param_name} ({param_unit})' to sensor '{sensor.name}'")

        # If the parameter already exists but has a different unit
        for (name, unit) in existing_parameters:
            if name == param_name and unit != param_unit:
                parameters_to_retain.remove((name, unit))

        print(f"parameters_to_retain: {parameters_to_retain}")

    # Remove any parameters from the sensor that are no longer in the updated list
    for param in sensor.parameters[:]:  # Copy the list to safely modify it
        if (param.name, param.unit) not in parameters_to_retain:
            print(f"Removing outdated parameter '{param.name} ({param.unit})' from sensor '{sensor.name}'")
            sensor.parameters.remove(param)

    db.session.commit()
    print(f"Final parameters for sensor '{sensor.name}': {[f'{p.name} ({p.unit})' for p in sensor.parameters]}")


def update_sensor_data(sensor, updated_parameters):
    """
    Update the `sensor_data` table to reflect updated parameter associations for the given sensor.

    Parameters:
        sensor (Sensor): The sensor object being updated.
        updated_parameters (list of tuples): List of updated parameters as (name, unit).
    """
    # Create a mapping of existing parameters for the sensor
    parameter_mapping = {f"{param.name}|{param.unit}": param for param in sensor.parameters}
    print(f"Parameter mapping for sensor '{sensor.name}': {parameter_mapping}")

    # Query existing `sensor_data` for the sensor
    sensor_data_entries = db.session.query(SensorData).filter_by(sensor_id=sensor.id).all()
    print(f"Sensor data entries before update: {[(d.id, d.parameter_id, d.value) for d in sensor_data_entries]}")

    # Create a lookup for updated parameters
    updated_mapping = {f"{name}|{unit}": (name, unit) for name, unit in updated_parameters}

    for data in sensor_data_entries:
        # Fetch the current parameter associated with this `sensor_data` entry
        current_param = db.session.query(Parameter).filter_by(id=data.parameter_id).first()

        if not current_param:
            print(f"Warning: Parameter ID {data.parameter_id} not found for SensorData ID {data.id}")
            continue

        current_key = f"{current_param.name}|{current_param.unit}"

        # Check if the current parameter exists in the updated parameters
        if current_key in updated_mapping:
            # If it matches, retain the parameter association
            continue

        # If the current parameter doesn't match, find the new parameter
        new_key = next(
            (key for key in updated_mapping if current_param.name in key),
            None,
        )

        if new_key:
            new_param = parameter_mapping[new_key]
            if data.parameter_id != new_param.id:
                print(
                    f"Updating SensorData entry (ID: {data.id}) "
                    f"from parameter_id {data.parameter_id} ({current_param.name}, {current_param.unit}) "
                    f"to {new_param.id} ({new_param.name}, {new_param.unit})"
                )
                data.parameter_id = new_param.id  # Update `parameter_id`
                db.session.add(data)  # Mark for commit

    # Commit all changes to the database
    db.session.commit()
    print(f"Sensor data entries after update: {[(d.id, d.parameter_id, d.value) for d in sensor_data_entries]}")


def delete_unused_parameters():
    """
    Delete parameters that are not associated with any sensors.
    """
    unused_parameters = db.session.query(Parameter).filter(~Parameter.sensors.any()).all()

    print(f"Unused parameters: {[f'{p.name} ({p.unit})' for p in unused_parameters]}")

    for param in unused_parameters:
        print(f"Deleting unused parameter: {param.name} ({param.unit})")
        db.session.delete(param)

    db.session.commit()
    print("Unused parameters deleted successfully.")

"""
def update_sensor_parameters(sensor, updated_parameters):
  
    Update the parameters for a given sensor.
    Ensures that `sensor_parameter` is updated correctly.

    # Fetch existing parameters for the sensor
    existing_parameters = {(param.name, param.unit): param for param in sensor.parameters}

    print(f"Existing parameters for sensor '{sensor.name}': {list(existing_parameters.keys())}")
    print(f"Updated parameters to process: {updated_parameters}")

    for param_name, param_unit in updated_parameters:
        # Add or fetch the parameter
        param = add_parameter_if_not_exists(param_name, param_unit)

        # Check if the parameter is already associated with the sensor
        if (param_name, param_unit) not in existing_parameters:
            sensor.parameters.append(param)  # Add association to `sensor_parameter`
            print(f"Added parameter '{param_name} ({param_unit})' to sensor '{sensor.name}'")
        else:
            print(f"Parameter '{param_name} ({param_unit})' already associated with sensor '{sensor.name}'")

    db.session.commit()
    print(f"Final parameters for sensor '{sensor.name}': {[f'{p.name} ({p.unit})' for p in sensor.parameters]}")
"""

