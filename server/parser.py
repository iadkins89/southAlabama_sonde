from datetime import datetime
import pytz
import base64
import struct

def parse_lora_message(sensor_data):
    """
    Parses Helium JSON payloads.
    """
    try:
        sensor_name = sensor_data['deviceInfo']["deviceName"]

        rssi = sensor_data['rxInfo'][0].get('rssi')
        snr = sensor_data['rxInfo'][0].get('snr')

        # Decode the payload and timestamp
        payload = sensor_data.get("object", {})
        payload['rssi'] = rssi
        payload['snr'] = snr

        # Convert timestamp to Central Time
        unix_timestamp = payload.get("timestamp")
        utc_time = datetime.utcfromtimestamp(unix_timestamp)
        central_time = utc_time.replace(tzinfo=pytz.utc).astimezone(pytz.timezone('America/Chicago'))
        payload['timestamp'] = central_time

        # Iterate over payload parameters
        for param, value in payload.items():
            # Skip the timestamp key
            if param == "timestamp":
                continue

        return{
            "sensor_name": sensor_name,
            "timestamp": central_time,
            "measurement": payload,
            "lat": None,
            "lon": None
        }
    except Exception as e:
        print(f"Lora parsing error: {e}")
        return None

def parse_iridium_message(sensor_data):
    """
    Parses Iridium JSON payloads.
    """
    try:
        # Indentify sensor
        imei = sensor_data.get('identity', {}).get('hardware', {}).get('imei')
        if not imei: return None

        sensor_name = f"iridium_{imei}"

        # Get timestamp
        time = sensor_data.get('receivedAt', {})
        if time:
            timestamp = datetime(
                year=time.get('year'), month=time.get('month'), day=time.get('day'),
                hour=time.get('hour'), minute=time.get('minute'), second=time.get('second'),
                tzinfo=pytz.utc
            )
        else:
            timestamp = datetime.utcnow().replace(tzinfo=pytz.utc)

        # Grab lat/long
        location = sensor_data.get('imt', {})
        lat = location.get('lat')
        lon = location.get('lon')

        #Decode payload
        b64_string = sensor_data.get('data') or sensor_data.get('message')

        payload = {}

        if b64_string:
            try:
                raw = base64.b64decode(b64_string)

                do, ec, ph, temp = struct.unpack('<4f', raw)

                payload['dissolved oxygen'] = do
                payload['conductivity'] = ec
                payload['pH'] = ph
                payload['temperature'] = temp

            except Exception as e:
                print(f"Binary Decoding Failed: {e}")

        return {
            "sensor_name": sensor_name,
            "timestamp": timestamp,
            "measurements": payload,
            "lat": lat,
            "lon": lon
        }

    except Exception as e:
        print(f"Iridium Parsing Error: {e}")
        return None