"""
Sends two days of simulated tide gauge packets to a LOCAL copy of the site, in
the format the stage 5 codec produces. Run the site first, then:

    python scripts/simulate_tide_gauge.py

Creates a sensor called sim_gauge and includes one of each case worth seeing:
a spike, suspect readings, an outage, a blind sensor, a lost clock, a late
reading and a compact packet. It refuses to run against anything but localhost.
"""
import math
import os
import random
import sys
from datetime import datetime, timedelta
from urllib.parse import urlparse

import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

SITE_URL = os.environ.get("SIM_URL", "http://localhost:8050")
SENSOR = "sim_gauge"
ELEVATION_M = 3.25
CYCLE = timedelta(minutes=6)
READINGS = 480
LOCAL_HOSTS = ("localhost", "127.0.0.1")


def refuse_unless_local():
    db_host = urlparse(os.environ.get("DATABASE_URL", "")).hostname
    site_host = urlparse(SITE_URL).hostname
    if db_host not in LOCAL_HOSTS or site_host not in LOCAL_HOSTS:
        sys.exit(f"Refusing to run: database host is {db_host!r} and site host is {site_host!r}.")


def create_sensor():
    from server import create_server
    from server.database import db
    from server.models import LocationHistory, create_or_update_sensor, get_sensor_by_name

    with create_server().app_context():
        if get_sensor_by_name(SENSOR):
            return
        print(create_or_update_sensor(SENSOR, 30.45, -88.0, "tide_gauge", navd88_elevation=ELEVATION_M))

        # The dashboard only graphs the current deployment, so it has to start
        # before the simulated readings do.
        LocationHistory.query.filter_by(sensor_id=get_sensor_by_name(SENSOR).id).one().deployed_at = \
            datetime.utcnow() - timedelta(days=3)
        db.session.commit()


def send(fields, when=None):
    body = {
        "deviceInfo": {"deviceName": SENSOR},
        "fCnt": 1,
        "rxInfo": [{"rssi": -96, "snr": 7.5}],
        "object": {"sd_mm": 40, "n_used": 1208, "n_rejected": 3, "n_no_target": 0, "n_floor": 0,
                   "battery": 3.0, "battery_valid": False, "board_temp_c": 24.5, "queue_depth": 0,
                   "status_raw": 0, "time_source": "device", **fields},
    }
    if when:
        body["object"]["timestamp"] = int((when - datetime(1970, 1, 1)).total_seconds())
    response = requests.post(f"{SITE_URL}/receive_data", json=body, timeout=10)
    if response.status_code != 200:
        sys.exit(f"Site returned {response.status_code}: {response.text}")


def main():
    refuse_unless_local()
    create_sensor()

    now = datetime.utcnow()
    last_mark = now.replace(minute=now.minute - now.minute % 6, second=0, microsecond=0) - CYCLE

    noise = random.Random(1)

    for i in range(READINGS):
        when = last_mark - CYCLE * (READINGS - i - 1)
        distance = 2500 + round(180 * math.sin(i * 2 * math.pi / 240))  # One tide a day
        distance += noise.randint(-3, 3)

        if 300 <= i < 320:                       # Outage: 2 hours of nothing
            continue
        if i == 100:
            distance -= 500                      # Spike: fails, and is hidden
        elif 150 <= i < 154:
            send({"distance_mm": distance, "n_used": 300, "n_no_target": 900}, when)  # Suspect
            continue
        elif i == 200:
            send({"distance_mm": 0, "n_used": 0, "n_no_target": 1210, "sd_mm": 0}, when)  # Blind sensor
            continue
        elif i == 250:
            send({"distance_mm": distance, "status_raw": 0x01}, when)  # Lost clock: quarantined
            continue

        send({"distance_mm": distance}, when)

    send({"distance_mm": 2600, "status_raw": 0x08}, last_mark - CYCLE * 170)  # Late reading, inside the outage
    send({"distance_mm": 2500, "time_source": "server", "cycles_back": 0, "degraded": True,
          "n_floor": None, "rssi": -118})        # Compact packet at the current mark

    print(f"Done. Open {SITE_URL}/dashboard?sensor={SENSOR}")


if __name__ == "__main__":
    main()
