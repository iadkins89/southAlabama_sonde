from flask import request, jsonify, Response
from datetime import datetime, timedelta
from .models import SensorData, LoraData
from .database import db
import json
import time
import pytz

def setup_routes(server):
    @server.route('/receive_data', methods=['POST'])
    def receive_data():
        sensor_data = request.json
        name = sensor_data["name"]
        rssi_data = sensor_data['hotspots'][0]['rssi']
        snr_data = sensor_data['hotspots'][0]['snr']

        do_data = sensor_data['decoded']['payload']['dissolved_oxygen']
        cond_data = sensor_data['decoded']['payload']['conductivity']
        turb_data = sensor_data['decoded']['payload']['turbidity']
        ph_data = sensor_data['decoded']['payload']['ph']
        temp_data = sensor_data['decoded']['payload']['temperature']
        unix_time_data = sensor_data['decoded']['payload']['timestamp']

        # Convert the timestamp to Central Time
        utc_time = datetime.fromtimestamp(unix_time_data, pytz.utc)
        central = pytz.timezone('America/Chicago')
        central_time = utc_time.astimezone(central)
        timestamp = central_time.strftime('%Y-%m-%dT%H:%M:%S')

        new_sensor_data = SensorData(
            name = name,
            timestamp=timestamp,
            dissolved_oxygen=do_data,
            conductivity=cond_data,
            turbidity=turb_data,
            ph=ph_data,
            temperature=temp_data
        )

        new_lora_data = LoraData(
            name = name,
            timestamp = timestamp,
            rssi = rssi_data,
            snr=snr_data
        )
        db.session.add(new_sensor_data)
        db.session.add(new_lora_data)
        db.session.commit()

        return jsonify({'message': 'Data received and broadcasted.'}), 200
