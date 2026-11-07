"""
Sends a week of simulated tide gauge packets for four Little Lagoon gauges to a
LOCAL copy of the site, so they go through the real ingest and QC. Run the site
first, then:

    python scripts/simulate_little_lagoon.py

Add --live to keep sending one reading per gauge every 6 minutes until stopped,
so the gauges stay online. Running it again only adds readings that are missing.

The tides are made up. Each gauge gets a share of a Gulf-style tide and a delay,
to look like a tide that shrinks and arrives later away from the pass. These are
not measured values. It refuses to run against anything but localhost.
"""
import math
import os
import random
import sys
import time
from datetime import datetime, timedelta
from urllib.parse import urlparse

import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

SITE_URL = os.environ.get("SIM_URL", "http://localhost:8050")
LOCAL_HOSTS = ("localhost", "127.0.0.1")
ELEVATION_M = 3.25
CYCLE = timedelta(minutes=6)
DAYS = 7
EPOCH = datetime(1970, 1, 1)

# name: latitude, longitude, share of the tide, delay in hours
GAUGES = {
    "little_lagoon_1": (30.256987, -87.700198, 0.70, 1.5),
    "little_lagoon_2": (30.241472, -87.737979, 0.90, 0.5),
    "little_lagoon_3": (30.245115, -87.781427, 0.60, 2.5),
    "little_lagoon_4": (30.245351, -87.666686, 0.50, 3.0),
}


def refuse_unless_local():
    db_host = urlparse(os.environ.get("DATABASE_URL", "")).hostname
    site_host = urlparse(SITE_URL).hostname
    if db_host not in LOCAL_HOSTS or site_host not in LOCAL_HOSTS:
        sys.exit(f"Refusing to run: database host is {db_host!r} and site host is {site_host!r}.")


def create_sensors(start):
    from server import create_server
    from server.database import db
    from server.models import LocationHistory, create_or_update_sensor, get_sensor_by_name

    with create_server().app_context():
        for name, (latitude, longitude, _, _) in GAUGES.items():
            if get_sensor_by_name(name):
                continue
            print(create_or_update_sensor(name, latitude, longitude, "tide_gauge", navd88_elevation=ELEVATION_M))

            # The dashboard only graphs the current deployment.
            LocationHistory.query.filter_by(sensor_id=get_sensor_by_name(name).id).one().deployed_at = \
                start - timedelta(days=1)
        db.session.commit()


def water_level(when, share, delay_hours):
    """Mostly daily tides that strengthen and fade over two weeks."""
    hours = (when - EPOCH).total_seconds() / 3600 - delay_hours
    tide = (0.17 * math.cos(2 * math.pi * hours / 23.93)
            + 0.16 * math.cos(2 * math.pi * hours / 25.82)
            + 0.03 * math.cos(2 * math.pi * hours / 12.42))
    return 0.05 + share * tide


def send(session, name, when, count, noise):
    share, delay_hours = GAUGES[name][2:]
    distance_mm = round((ELEVATION_M - water_level(when, share, delay_hours)) * 1000) + noise.randint(-3, 3)
    body = {
        "deviceInfo": {"deviceName": name},
        "fCnt": count,
        "rxInfo": [{"rssi": noise.randint(-104, -92), "snr": round(noise.uniform(5, 9), 1)}],
        "object": {"timestamp": int((when - EPOCH).total_seconds()), "time_source": "device",
                   "distance_mm": distance_mm, "sd_mm": noise.randint(30, 50), "n_used": 1208, "n_rejected": 3,
                   "n_no_target": 0, "n_floor": 0, "battery": 3.0, "battery_valid": False,
                   "board_temp_c": round(noise.uniform(22, 27), 1), "queue_depth": 0, "status_raw": 0},
    }
    response = session.post(f"{SITE_URL}/receive_data", json=body, timeout=10)
    if response.status_code != 200:
        sys.exit(f"Site returned {response.status_code}: {response.text}")


def latest_mark():
    now = datetime.utcnow()
    return now.replace(minute=now.minute - now.minute % 6, second=0, microsecond=0) - CYCLE


def main():
    refuse_unless_local()

    end = latest_mark()
    start = end - timedelta(days=DAYS)
    create_sensors(start)

    noise = random.Random(7)
    session = requests.Session()
    when, count = start, 0
    while when <= end:
        count += 1
        for name in GAUGES:
            send(session, name, when, count, noise)
        when += CYCLE
    print(f"Sent {count} readings to each of {len(GAUGES)} gauges.")

    if "--live" not in sys.argv:
        return

    print("Sending live readings. Press Ctrl+C to stop.")
    while True:
        while latest_mark() < when:
            time.sleep(5)
        count += 1
        for name in GAUGES:
            send(session, name, when, count, noise)
        when += CYCLE


if __name__ == "__main__":
    main()
