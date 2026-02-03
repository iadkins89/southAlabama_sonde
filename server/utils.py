import pandas as pd
import io
import base64
from PIL import Image, ImageOps
from collections import defaultdict
from server.models import get_sensor_timezone, get_sensor_by_name, get_most_recent
def save_data_to_csv(data, sensor_name):
    organized_data = defaultdict(dict)

    timezone_str = get_sensor_timezone(sensor_name)

    for timestamp, value, parameter, unit in data:
        organized_data[timestamp][f"{parameter} ({unit})"] = value

    # Create a DataFrame from the organized data
    df = pd.DataFrame.from_dict(organized_data, orient='index').reset_index()

    # Rename the first column to 'timestamp (timezone)'
    formatted_time = f"timestamp ({timezone_str})"
    df.rename(columns={'index': formatted_time}, inplace=True)

    # Convert the DataFrame to a CSV string
    csv_data = df.to_csv(index=False)
    sensor_name_line = f"Sensor Name: {sensor_name}\n"
    csv_data = sensor_name_line + csv_data

    return csv_data

def compress_image(base64_string, max_size=(800, 800), quality=70):
    """
    Accepts a base64 string, resizes/compresses it, and returns a new base64 string.
    """
    try:
        # Split header (e.g. "data:image/png;base64,") from data
        if ',' in base64_string:
            header, data = base64_string.split(',', 1)
        else:
            header = "data:image/jpeg;base64"  # Default assumption
            data = base64_string

        # Decode to bytes
        image_bytes = base64.b64decode(data)
        img = Image.open(io.BytesIO(image_bytes))

        #Fix orientation
        img = ImageOps.exif_transpose(img)

        # Convert to RGB (if PNG has transparency, this avoids errors saving as JPEG)
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")

        # Resize and save
        img.thumbnail(max_size)
        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", quality=quality)

        # Re-encode to Base64
        new_data = base64.b64encode(buffer.getvalue()).decode('utf-8')

        return f"data:image/jpeg;base64,{new_data}"

    except Exception as e:
        print(f"Image compression error: {e}")
        return base64_string  # Return original if compression fails

def get_measurement_summary(sensor_name, include_health=False):
    """
    Fetches the single most recent data this sensor has reported.
    Excludes sensor health related data
    """
    sensor = get_sensor_by_name(sensor_name)
    if not sensor:
        return {"error": f"Sensor '{sensor_name}' not found"}

    recent_data = get_most_recent(sensor_name)

    if not recent_data:
        return {"message": f"No data available for sensor '{sensor_name}'"}

    summary_list = []

    for data_obj, p_name, p_unit in recent_data:
        if p_name == "latitude" or p_name == "longitude":
            continue
        summary_list.append({
            "parameter": f"{p_name} {f'({p_unit})' if p_unit else ''}",
            "value": data_obj.value,
            "timestamp": data_obj.timestamp
        })

    return {
        "sensor_name": sensor.name,
        "latitude": sensor.latitude,
        "longitude": sensor.longitude,
        "timezone": sensor.timezone,
        "most_recent_measurements": summary_list
    }