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
        payload['timestamp'] = utc_time

        return{
            "sensor_name": sensor_name,
            "measurements": payload,
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
        lat = location.get('latitude')
        lon = location.get('longitude')

        #Decode payload
        b64_string = sensor_data.get('data') or sensor_data.get('message')
        print(f"Raw Payload: {b64_string}")

        payload = {}
        payload['timestamp'] = timestamp
        if b64_string:
            try:
                raw = base64.b64decode(b64_string)

                # Check if there is more than a header
                if len(raw) >= 2:

                    # Start at index 2 to skip the header bytes
                    i = 2

                    # Loop while we have at least 5 bytes remaining (1 tag + 4 float)
                    while i <= len(raw) - 5:
                        tag = raw[i]

                        value = struct.unpack('<f', raw[i + 1: i + 5])[0]

                        # Tags
                        if tag == 1:
                            payload['dissolved_oxygen'] = value
                        elif tag == 2:
                            payload['conductivity'] = value
                        elif tag == 3:
                            payload['pH'] = value
                        elif tag == 4:
                            payload['temperature'] = value
                        elif tag == 5:
                            payload['humidity'] = value

                        # Move to next block (1 byte tag + 4 bytes float = 5 bytes)
                        i += 5
                else:
                    print("Payload too short for header")

            except Exception as e:
                print(f"Binary Decoding Failed: {e}")

        return {
            "sensor_name": sensor_name,
            "measurements": payload,
            "lat": lat,
            "lon": lon
        }

    except Exception as e:
        print(f"Iridium Parsing Error: {e}")
        return None