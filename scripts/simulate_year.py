"""
Fills a LOCAL database with a year of made-up data, to see how long graph ranges
look. Run it with DATABASE_URL pointing at your local database:

    python scripts/simulate_year.py

Creates sim_year_gauge (6 minute water levels) and sim_year_sonde (15 minute
water quality). Readings go straight into sensor_data, so the QC flags here are
assigned by this script, not by the real tests. To remove them, delete the two
sensors' rows or recreate the local database.
"""
import math
import os
import random
import sys
from datetime import datetime, timedelta
from urllib.parse import urlparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

GAUGE = "sim_year_gauge"
SONDE = "sim_year_sonde"
DAYS = 365
LOCAL_HOSTS = ("localhost", "127.0.0.1")
HOUR = 3600.0
SUSPECT, FAIL = 3, 4


def refuse_unless_local():
    db_host = urlparse(os.environ.get("DATABASE_URL", "")).hostname
    if db_host not in LOCAL_HOSTS:
        sys.exit(f"Refusing to run: database host is {db_host!r}.")


def water_level(when, start):
    """Mostly daily tides that strengthen and fade over two weeks, as in Mobile Bay."""
    hours = (when - start).total_seconds() / HOUR
    tide = (0.17 * math.cos(2 * math.pi * hours / 23.93)
            + 0.16 * math.cos(2 * math.pi * hours / 25.82)
            + 0.03 * math.cos(2 * math.pi * hours / 12.42))
    season = 0.10 * math.sin(2 * math.pi * (when.timetuple().tm_yday - 120) / 365)
    days_to_storm = hours / 24 - 200
    storm = 1.3 * math.exp(-(days_to_storm ** 2) / 0.5)
    return 0.05 + tide + season + storm


def gauge_rows(start, end, rng):
    outages = [(start + timedelta(days=90), timedelta(days=3)),
               (start + timedelta(days=150), timedelta(hours=6))]
    suspect_at = set(rng.sample(range(int(DAYS * 240)), 60))
    fail_at = set(rng.sample(range(int(DAYS * 240)), 20))

    when, i = start, 0
    while when <= end:
        if not any(begin <= when < begin + length for begin, length in outages):
            level = water_level(when, start) + rng.gauss(0, 0.003)
            flag = 1
            if i in suspect_at:
                level, flag = level + rng.choice((-1, 1)) * 0.12, SUSPECT
            elif i in fail_at:
                level, flag = level + rng.choice((-1, 1)) * 1.5, FAIL
            yield when, round(level, 3), flag
        when += timedelta(minutes=6)
        i += 1


def sonde_rows(start, end, rng):
    when = start
    while when <= end:
        day = when.timetuple().tm_yday
        hours = (when - start).total_seconds() / HOUR
        daily = math.sin(2 * math.pi * (when.hour + when.minute / 60 - 9) / 24)
        temperature = 22 + 8 * math.sin(2 * math.pi * (day - 110) / 365) + 0.8 * daily + rng.gauss(0, 0.05)
        conductivity = 23000 + 8000 * math.sin(2 * math.pi * hours / 24.84) + 5000 * math.sin(2 * math.pi * day / 60)
        oxygen = 11 - 0.17 * temperature + 0.7 * daily + rng.gauss(0, 0.08)
        yield when, {"temperature": round(temperature, 2), "conductivity": round(max(conductivity, 0), 1),
                     "ph": round(7.8 + 0.15 * daily + rng.gauss(0, 0.01), 2),
                     "dissolved_oxygen": round(oxygen, 2)}
        when += timedelta(minutes=15)


def main():
    refuse_unless_local()

    from server import create_server
    from server.database import db, run_migrations
    from server.models import (LocationHistory, SensorData, create_or_update_sensor,
                               get_or_create_parameter, get_sensor_by_name)

    rng = random.Random(42)
    end = datetime.utcnow().replace(second=0, microsecond=0)
    end -= timedelta(minutes=end.minute % 6)
    start = end - timedelta(days=DAYS)

    with create_server().app_context():
        run_migrations()
        if get_sensor_by_name(GAUGE) or get_sensor_by_name(SONDE):
            sys.exit("The simulated year is already there, so nothing was added.")

        print(create_or_update_sensor(GAUGE, 30.25, -88.08, "tide_gauge", navd88_elevation=3.25))
        print(create_or_update_sensor(SONDE, 30.35, -87.98, "sonde"))
        gauge, sonde = get_sensor_by_name(GAUGE), get_sensor_by_name(SONDE)

        # The dashboard only graphs the current deployment.
        for sensor in (gauge, sonde):
            LocationHistory.query.filter_by(sensor_id=sensor.id).one().deployed_at = start - timedelta(days=1)

        level_id = get_or_create_parameter("water_level").id
        rows = [{"sensor_id": gauge.id, "parameter_id": level_id, "timestamp": when, "value": level, "qc_flag": flag}
                for when, level, flag in gauge_rows(start, end, rng)]

        parameter_ids = {name: get_or_create_parameter(name).id
                         for name in ("temperature", "conductivity", "ph", "dissolved_oxygen",
                                      "board_temperature", "rssi", "snr")}
        for when, readings in sonde_rows(start, end, rng):
            for name, value in readings.items():
                rows.append({"sensor_id": sonde.id, "parameter_id": parameter_ids[name],
                             "timestamp": when, "value": value, "qc_flag": None})

        # Fills the gauge's Sensor Health panel.
        for name, value in (("board_temperature", 24.5), ("rssi", -95), ("snr", 7.5)):
            rows.append({"sensor_id": gauge.id, "parameter_id": parameter_ids[name],
                         "timestamp": end, "value": value, "qc_flag": None})

        db.session.bulk_insert_mappings(SensorData, rows)
        db.session.commit()
        print(f"Added {len(rows):,} readings from {start:%Y-%m-%d} to {end:%Y-%m-%d}.")


if __name__ == "__main__":
    main()
