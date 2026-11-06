"""
Pretends to be a sonde reporting live to your LOCAL site, so you can watch a
dashboard update. Run the site first, then open the sensor's dashboard and run:

    python scripts/simulate_live_sonde.py
    python scripts/simulate_live_sonde.py my_sensor --every 10

The sensor must already exist on the site. Press Ctrl+C to stop. Every reading
is stored in your local database. It refuses to run against anything but localhost.
"""
import argparse
import os
import random
import sys
import time
from urllib.parse import urlparse

import requests

LOCAL_HOSTS = ("localhost", "127.0.0.1")

# name: (starting value, largest step per reading, lowest, highest)
PARAMETERS = {
    "temperature": (19.5, 0.1, 5, 35),
    "conductivity": (21000, 150, 0, 60000),
    "ph": (7.8, 0.02, 6.5, 9),
    "dissolved_oxygen": (7.2, 0.1, 2, 12),
}


def next_values(values):
    """Each reading drifts a little from the last, as real water does."""
    updated = {}
    for name, value in values.items():
        _, step, low, high = PARAMETERS[name]
        updated[name] = round(min(high, max(low, value + random.uniform(-step, step))), 2)
    return updated


def packet(sensor, values):
    return {
        "deviceInfo": {"deviceName": sensor},
        "rxInfo": [{"rssi": random.randint(-105, -85), "snr": round(random.uniform(-2, 9), 1)}],
        "object": {"timestamp": int(time.time()), "battery": 3.9, **values},
    }


def main():
    parser = argparse.ArgumentParser(description="Send fake live sonde readings to your local site.")
    parser.add_argument("sensor", nargs="?", default="sim_year_sonde", help="sensor name (default: sim_year_sonde)")
    parser.add_argument("--every", type=float, default=5, help="seconds between readings (default: 5)")
    parser.add_argument("--url", default="http://localhost:8050", help="your local site")
    args = parser.parse_args()

    if urlparse(args.url).hostname not in LOCAL_HOSTS:
        sys.exit(f"Refusing to run: {args.url} is not a local address.")

    headers = {"X-Ingest-Token": os.environ.get("INGEST_TOKEN", "")}
    values = {name: settings[0] for name, settings in PARAMETERS.items()}
    print(f"Sending a reading for {args.sensor} every {args.every:g} seconds. Press Ctrl+C to stop.")
    print(f"Watch it at {args.url}/dashboard?sensor={args.sensor}\n")

    try:
        while True:
            values = next_values(values)
            try:
                response = requests.post(f"{args.url}/receive_data", json=packet(args.sensor, values),
                                         headers=headers, timeout=10)
            except requests.ConnectionError:
                sys.exit(f"Could not reach {args.url}. Is the site running?")

            if response.status_code != 200:
                sys.exit(f"The site said {response.status_code}: {' '.join(response.text.split())}")

            print(f"{time.strftime('%H:%M:%S')}  " + "  ".join(f"{k}={v}" for k, v in values.items()), flush=True)
            time.sleep(args.every)
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
