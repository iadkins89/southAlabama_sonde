import hmac
import os

from flask import request, jsonify
from .models import (SensorData,
                     get_all_sensors,
                     get_sensor_by_name,
                     HEALTH_PARAMS,
                     get_or_create_parameter)
from .database import db
from .realtime import emit_event
from .tide_gauge import begin_reading, finish_reading
from server.parser import parse_lora_message, parse_iridium_message


def ingest_token_ok():
    """
    Checks the shared secret on an incoming packet. Senders that can set headers
    use X-Ingest-Token; the others can use ?token= in the URL. With INGEST_TOKEN
    unset every packet is accepted, so the token can be added to the senders first.
    """
    expected = os.environ.get("INGEST_TOKEN")
    if not expected:
        return True

    supplied = request.headers.get("X-Ingest-Token") or request.args.get("token") or ""
    return hmac.compare_digest(supplied.encode(), expected.encode())


def setup_routes(server):
    if not os.environ.get("INGEST_TOKEN"):
        print("WARNING: INGEST_TOKEN is not set, so /receive_data accepts packets from anyone")

    @server.route('/api/sensors')
    def list_sensors():
        """Sensor names and status, for the search in the navigation bar."""
        return jsonify([
            {key: sensor[key] for key in ('name', 'device_type', 'active', 'is_online')}
            for sensor in get_all_sensors()
        ])

    @server.route('/receive_data', methods=['POST'])
    def receive_data():
        if not ingest_token_ok():
            return jsonify({'error': 'Invalid or missing token'}), 401

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

        #Tide gauges: keep the raw packet, then pass on only what should be stored as data
        gauge = None
        if sensor.device_type == "tide_gauge":
            gauge = begin_reading(sensor, payload)
            if gauge is None:
                return jsonify({'error': 'Invalid tide gauge payload'}), 400
            if gauge.stop_reason:
                db.session.commit()
                return jsonify({'message': gauge.stop_reason}), 200
            measurements = gauge.measurements

        timestamp = measurements.get('timestamp')
        lat = payload.get('lat') #handle missing data gracefully
        lon = payload.get('lon')

        #Update Sensor table (map pin updates from this). A test device's position
        #is wherever it is being tested, so only its readings keep it.
        if lat is not None and lon is not None and not sensor.testing:
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
            parameter = get_or_create_parameter(param_name)

            #Create new SensorData entry
            new_entry = SensorData(
                sensor_id = sensor.id,
                parameter_id = parameter.id,
                timestamp = timestamp,
                value = param_value
            )
            db.session.add(new_entry)

            if gauge and param_name == 'water_level':
                new_entry.qc_flag = gauge.flag
                gauge.water_level_entry = new_entry

            new_data.append({
                'name': param_name,
                'value': param_value,
                'is_health': param_name in HEALTH_PARAMS
            })

        try:
            if gauge:
                db.session.flush()
                finish_reading(gauge)

            db.session.commit()

            #Real time data. Every browser receives these, so test devices are left
            #out; their page checks for new readings itself.
            if not sensor.testing:
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
