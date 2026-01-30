from datetime import datetime
import pytz

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

def parse_iridium_message(payload):
    """
    Parses Iridium (Certus/RockBLOCK) JSON payloads.
    """
    try:
        # 1. Identity
        imei = payload.get('identity', {}).get('hardware', {}).get('imei')
        if not imei: return None

        sensor_name = f"iridium_{imei}"

        # 2. Timestamp
        t = payload.get('receivedAt', {})
        if t:
            timestamp = datetime(
                year=t.get('year'), month=t.get('month'), day=t.get('day'),
                hour=t.get('hour'), minute=t.get('minute'), second=t.get('second'),
                tzinfo=pytz.utc
            )
        else:
            timestamp = datetime.utcnow().replace(tzinfo=pytz.utc)

        # 3. Location
        # Check 'location' wrapper first (common in Iridium JSONs)
        location = payload.get('location', {})
        lat = location.get('lat')
        lon = location.get('lon')

        # 4. Measurements (The payload data)
        # Assuming 'data' contains the dictionary of values
        measurements = payload.get('data', {})

        # If Lat/Lon came inside the hex payload (not the wrapper), extract it here
        if not lat and 'latitude' in measurements:
            lat = measurements['latitude']
        if not lon and 'longitude' in measurements:
            lon = measurements['longitude']

        return {
            "sensor_name": sensor_name,
            "timestamp": timestamp,
            "measurements": measurements,
            "lat": lat,
            "lon": lon
        }

    except Exception as e:
        print(f"Iridium Parsing Error: {e}")
        return None