from flask import request, jsonify
from datetime import datetime
from .models import Sensor, Parameter, SensorData, LoraData, sensor_parameter
from .database import db
import pytz


# Helper function to guess unit
def guess_unit(param, value):
    PARAMETER_UNITS = {
        "temperature": "°C",
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
    # Check if the parameter name matches a known unit
    if param in PARAMETER_UNITS:
        return PARAMETER_UNITS[param]

    # Fallback logic based on value
    if isinstance(value, int):
        return "units"  # Generic count
    elif isinstance(value, float):
        if 0 <= value <= 1:
            return ""  # Probabilities or fractions
        elif value > 1 and value < 1000:
            return "m"  # Assume distance in meters
        else:
            return "unknown"
    return "unknown"

def setup_routes(server):
    @server.route('/receive_data', methods=['POST'])
    def receive_data():
        sensor_data = request.json
        print(sensor_data)

        # Extract general sensor information
        sensor_name = sensor_data['deviceInfo']["deviceName"]
        if not sensor_name:
            return jsonify({"error": "Sensor name is missing in the payload"}), 400

        rssi = snr = None
        if 'rxInfo' in sensor_data and len(sensor_data['rxInfo']) > 0:
            rssi = sensor_data['rxInfo'][0]['rssi']
            snr = sensor_data['rxInfo'][0]['snr']

        # Retrieve or create the sensor
        sensor = Sensor.query.filter_by(name=sensor_name).first()
        if not sensor:
            sensor = Sensor(name=sensor_name)
            db.session.add(sensor)
            db.session.commit()

        # Decode the payload and timestamp
        payload = sensor_data.get("object", {})
        payload['rssi'] = rssi
        payload['snr'] = snr
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
            parameter = (
                db.session.query(Parameter)
                .join(sensor_parameter)
                .filter(sensor_parameter.c.sensor_id == sensor.id, Parameter.name == param)
                .first()
            )

            if not parameter:
                guessed_unit = guess_unit(param, value)
                parameter = Parameter(name=param, unit=guessed_unit)
                db.session.add(parameter)
                db.session.commit()

            if parameter not in sensor.parameters:
                sensor.parameters.append(parameter)
                db.session.commit()

            if param not in ['rssi', 'snr', 'battery']:
                # Add the sensor data entry
                sensor_data_entry = SensorData(
                    sensor_id=sensor.id,
                    timestamp=central_time,
                    parameter_id=parameter.id,
                    value=value
                )
                db.session.add(sensor_data_entry)
            else:
                # Add LoRa data for the transmission
                lora_data_entry = LoraData(
                    sensor_id=sensor.id,
                    timestamp=central_time,
                    parameter_id=parameter.id,
                    value=value
                )
                db.session.add(lora_data_entry)

        # Commit all changes
        db.session.commit()

        return jsonify({'message': 'Data received and stored successfully.'}), 200

