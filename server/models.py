from sqlalchemy import distinct
from datetime import datetime
from server import db
import pandas as pd

class SensorData(db.Model):
    __tablename__ = 'sonde_data'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String, nullable=True)
    timestamp = db.Column(db.DateTime, index=True, nullable=False)
    dissolved_oxygen = db.Column(db.Float, nullable=False)
    conductivity = db.Column(db.Float, nullable=False)
    turbidity = db.Column(db.Float, nullable=False)
    ph = db.Column(db.Float, nullable=False)
    temperature = db.Column(db.Float, nullable=False)

    def __repr__(self):
        return f"<SensorData {self.name} {self.timestamp} {self.dissolved_oxygen} {self.conductivity} {self.conductivity} {self.turbidity} {self.ph} {self.temperature}>"

class LoraData(db.Model):
    __tablename__ = 'lora_data'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String, nullable=True)
    timestamp = db.Column(db.DateTime, index=True, nullable=False)
    rssi = db.Column(db.Float, nullable=False)
    snr = db.Column(db.Float, nullable=False)

    def __repr__(self):
        return f"<LoraData {self.name} {self.timestamp} {self.rssi} {self.snr}>"

def query_data(start_date, end_date, name):
    # Convert strings to datetime objects including microseconds
    start_dt = datetime.strptime(start_date, '%Y-%m-%dT%H:%M:%S.%f').replace(hour=0, minute=0, second=0, microsecond=0)
    end_dt = datetime.strptime(end_date, '%Y-%m-%dT%H:%M:%S.%f').replace(hour=23, minute=59, second=59, microsecond=999999)

    result = db.session.query(SensorData).filter(SensorData.name == name, SensorData.timestamp >= start_dt, SensorData.timestamp <= end_dt).all()
    return result

def save_data_to_csv(data, filename='output.csv'):
    sensor_name = data[0].name

    data_dict = {
        'id': [d.id for d in data],
        'timestamp': [d.timestamp for d in data],
        'dissolved_oxygen': [d.dissolved_oxygen for d in data],
        'conductivity': [d.conductivity for d in data],
        'turbidity': [d.turbidity for d in data],
        'ph': [d.ph for d in data],
        'temperature': [d.temperature for d in data]
    }
    df = pd.DataFrame(data_dict)
    csv_data = df.to_csv(index=False)

    # Add the sensor name at the beginning
    sensor_name_line = f"Sensor Name: {sensor_name}\n"
    csv_data = sensor_name_line + csv_data

    return csv_data

def get_unique_sensor_names():
    unique_names = db.session.query(distinct(SensorData.name)).all()
    return [name[0] for name in unique_names] #result is a tuple with only the first entry filled. Hence name[0] is used to extract each unique name.
