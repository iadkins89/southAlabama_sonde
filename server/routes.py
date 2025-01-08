from flask import request, jsonify
from datetime import datetime
from .models import Sensor, Parameter, SensorData, LoraData
from .database import db
import pytz

def setup_routes(server):
    @server.route('/receive_data', methods=['POST'])
    def receive_data():
        sensor_data = request.json

        # Extract general sensor information
        sensor_name = sensor_data.get("name")
        rssi = sensor_data['hotspots'][0].get('rssi')
        snr = sensor_data['hotspots'][0].get('snr')

        # Retrieve or create the sensor
        sensor = Sensor.query.filter_by(name=sensor_name).first()
        if not sensor:
            sensor = Sensor(name=sensor_name)
            db.session.add(sensor)
            db.session.commit()

        # Decode the payload and timestamp
        payload = sensor_data.get("decoded", {}).get("payload", {})
        unix_timestamp = payload.get("timestamp")
        if not unix_timestamp:
            return jsonify({"error": "Timestamp is missing in the payload"}), 400

        # Convert timestamp to Central Time
        utc_time = datetime.utcfromtimestamp(unix_timestamp)
        central_time = utc_time.replace(tzinfo=pytz.utc).astimezone(pytz.timezone('America/Chicago'))

        # Iterate over payload parameters
        for param, value in payload.items():
            # Skip the timestamp key
            if param == "timestamp":
                continue

            # Check if the parameter exists in the database
            parameter = Parameter.query.filter_by(name=param).first()
            if not parameter:
                parameter = Parameter(name=param)
                db.session.add(parameter)
                db.session.commit()

            if parameter not in sensor.parameters:
                sensor.parameters.append(parameter)

            # Add the sensor data entry
            sensor_data_entry = SensorData(
                sensor_id=sensor.id,
                timestamp=central_time,
                parameter_id=parameter.id,
                value=value
            )
            db.session.add(sensor_data_entry)

        # Add LoRa data for the transmission
        lora_data_entry = LoraData(
            sensor_id=sensor.id,
            timestamp=central_time,
            rssi=rssi,
            snr=snr
        )
        db.session.add(lora_data_entry)

        # Commit all changes
        db.session.commit()

        return jsonify({'message': 'Data received and stored successfully.'}), 200

