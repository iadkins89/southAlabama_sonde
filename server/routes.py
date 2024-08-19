from flask import request, jsonify, Response
from datetime import datetime, timedelta
from .models import SensorData, LoraData
from .database import db
import json
import time

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
        timestamp = datetime.fromtimestamp(unix_time_data).strftime('%Y-%m-%dT%H:%M:%S')

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
        
    @server.route('/eventsource')
    def eventsource():
        def generate():
            with server.app_context():
                while True:
                    data = db.session.query(SensorData).filter(
                                SensorData.timestamp >= datetime.utcnow() - timedelta(days=2)
                            ).all()
                    data_json = [
                        {
                            "name":d.name,
                            "timestamp": d.timestamp.strftime('%Y-%m-%dT%H:%M:%S'),
                            "dissolved_oxygen": d.dissolved_oxygen,
                            "conductivity": d.conductivity,
                            "turbidity": d.turbidity,
                            "ph": d.ph,
                            "temperature": d.temperature
                        } for d in data
                    ]
                    time.sleep(1)
                    yield f"data: {json.dumps(data_json)}\n\n"
        return Response(generate(), mimetype='text/event-stream')