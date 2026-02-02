from flask import request, jsonify
from datetime import datetime
from .models import (Sensor,
                     Parameter,
                     SensorData,
                     get_sensor_by_name,
                     HEALTH_PARAMS,
                     get_param_by_name)
from .database import db
import pytz
from .realtime import emit_event
from server.parser import parse_lora_message, parse_iridium_message


# Helper function to guess unit
def guess_unit(param_name):
    param = param_name.lower()
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
    return PARAMETER_UNITS.get(param, "")

def setup_routes(server):
    @server.route('/receive_data', methods=['POST'])
    def receive_data():
        sensor_data = request.json
        if not sensor_data:
            return jsonify({'error': 'No JSON payload received'}), 400

        payload = None

        #LoRaWAN message
        if 'deviceInfo' in sensor_data:
            payload = parse_lora_message(sensor_data)
        #Iridium message
        elif 'id' in sensor_data:
            payload = parse_iridium_message(sensor_data)
        else:
            return jsonify({'error': 'Unknown payload format'}), 400

        if not payload:
            return jsonify({'error': 'Parsing failed or empty data'}), 400

        #Reject messages from devices that have not been onboarded
        sensor_name = payload['sensor_name']
        sensor = get_sensor_by_name(sensor_name)

        if not sensor:
            return jsonify({'error': f"Device '{sensor_name}' not onboarded."}), 403

        #Data prep. Handle lat and long (not reported by LoRaWAN sensors)
        measurements = payload['measurements']
        timestamp = measurements.get('timestamp')
        lat = payload.get('lat') #handle missing data gracefully
        lon = payload.get('lon')

        #Update Sensor table (map pin updates from this)
        if lat is not None and lon is not None:
            sensor.latitude = float(lat)
            sensor.longitude = float(lon)

        #Add lat/lon to measurements to store in SensorData and track over time
        if lat is not None:
            measurements['latitude'] = float(lat)
            measurements['longitude'] = float(lon)

        #Data Ingestion
        new_data = [] #dictionary to emit

        for param_name, param_value in measurements.items():
            if param_name.lower() == 'timestamp':
                continue

            if param_value is None:
                continue

            #Find the parameter or create it if it is new
            parameter = get_param_by_name(param_name)
            if not parameter:
                parameter = Parameter(name=param_name, canonical_unit=guess_unit(param_name))
                db.session.add(parameter)
                db.session.commit()

            #Create new SensorData entry
            new_entry = SensorData(
                sensor_id = sensor.id,
                parameter_id = parameter.id,
                timestamp = timestamp,
                value = param_value
            )
            db.session.add(new_entry)

            new_data.append({
                'name': param_name,
                'value': param_value,
                'is_health': param_name in HEALTH_PARAMS
            })

        try:
            db.session.commit()

            #Real time data
            emit_event("sensor_update", {
                "sensor": sensor.name,
                "timestamp": timestamp.isoformat(),
                "measurements": new_data
            })

            return jsonify({'message': 'Data received and stored successfully'}), 200

        except Exception as e:
            db.session.rollback()
            print(f"Database insert error: {e}")
            return jsonify({"error": str(e)}), 500





