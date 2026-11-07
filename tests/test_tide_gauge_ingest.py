"""
Sends simulated ChirpStack packets through the real route. Needs a throwaway
Postgres database in TEST_DATABASE_URL, because every table in it is dropped.
"""
import os
import unittest
from datetime import datetime, timedelta

from tests.shared_app import get_server

TEST_DB = os.environ.get("TEST_DATABASE_URL")
if TEST_DB:
    os.environ["DATABASE_URL"] = TEST_DB
    os.environ.setdefault("SECRET_KEY", "test")

EPOCH = datetime(1970, 1, 1)


def to_unix(when):
    return int((when - EPOCH).total_seconds())


def packet(name, when, distance_mm=2000, status=0, **fields):
    """A full fPort 1 packet, as decoded by the stage 5 codec."""
    return {
        "deviceInfo": {"deviceName": name},
        "fCnt": 7,
        "rxInfo": [{"rssi": -95, "snr": 7.5}],
        "object": {
            "timestamp": to_unix(when), "time_source": "device", "distance_mm": distance_mm,
            "sd_mm": 41, "n_used": 1208, "n_rejected": 3, "n_no_target": 0, "n_floor": 0,
            "battery": 3.0, "battery_valid": False, "board_temp_c": 24.5, "queue_depth": 0,
            "status_raw": status, "lost_power": bool(status & 1), "backfill": bool(status & 8),
            **fields,
        },
    }


def compact_packet(name, cycles_back=0, distance_mm=2000, status=0):
    """A compact fPort 3 packet, as decoded by the stage 5 codec."""
    return {
        "deviceInfo": {"deviceName": name},
        "fCnt": 8,
        "rxInfo": [{"rssi": -118, "snr": -9.5}],
        "object": {
            "cycles_back": cycles_back, "time_source": "server", "distance_mm": distance_mm,
            "sd_mm": 41, "n_used": 1208, "n_no_target": 0, "n_rejected": 3, "battery": 3.0,
            "battery_valid": False, "board_temp_c": 24.5, "queue_depth": 0, "degraded": True,
            "status_raw": status,
        },
    }


@unittest.skipUnless(TEST_DB, "TEST_DATABASE_URL not set")
class Ingest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = get_server()

    def setUp(self):
        from server.database import db, run_migrations
        from server.models import create_or_update_sensor
        self.ctx = self.server.app_context()
        self.ctx.push()
        db.drop_all()
        db.create_all()
        run_migrations()
        self.assertIn("successfully", create_or_update_sensor(
            "gauge", 30.5, -87.9, "tide_gauge", navd88_elevation=3.25))
        self.client = self.server.test_client()
        self.t0 = datetime(2027, 3, 1, 12, 0)

    def tearDown(self):
        from server.database import db
        db.session.remove()
        self.ctx.pop()

    def send(self, minutes=0, **kwargs):
        when = self.t0 + timedelta(minutes=minutes)
        return self.client.post("/receive_data", json=packet("gauge", when, **kwargs))

    def rows(self, name="water_level"):
        from server.models import Parameter, SensorData
        return (SensorData.query.join(Parameter).filter(Parameter.name == name)
                .order_by(SensorData.timestamp).all())

    def test_only_expected_parameters_are_stored(self):
        from server.models import Parameter
        self.assertEqual(self.send().status_code, 200)
        self.assertEqual({p.name for p in Parameter.query.all()},
                         {"water_level", "board_temperature", "rssi", "snr"})

    def test_water_level_is_elevation_minus_distance_in_metres(self):
        self.send(distance_mm=2000)
        self.assertAlmostEqual(self.rows()[0].value, 1.25)

    def test_raw_packet_is_kept(self):
        from server.models import GaugeReading
        self.send(distance_mm=2000, sd_mm=55)
        reading = GaugeReading.query.one()
        self.assertEqual((reading.distance_mm, reading.sd_mm, reading.fcnt), (2000, 55, 7))

    def test_redelivered_packet_is_ignored(self):
        from server.models import GaugeReading
        self.send()
        self.assertEqual(self.send().status_code, 200)
        self.assertEqual(GaugeReading.query.count(), 1)
        self.assertEqual(len(self.rows()), 1)

    def test_lost_power_is_quarantined(self):
        from server.models import GaugeReading, SensorData
        self.assertEqual(self.send(status=0x01).status_code, 200)
        self.assertFalse(GaugeReading.query.one().time_ok)
        self.assertEqual(SensorData.query.count(), 0)

    def test_quarantined_rows_can_share_a_mark_time(self):
        from server.models import GaugeReading
        self.send(status=0x01)
        self.send(status=0x01)
        self.send()
        self.assertEqual(GaugeReading.query.count(), 3)

    def test_no_target_keeps_health_without_a_water_level(self):
        self.assertEqual(self.send(distance_mm=0, n_used=0, n_no_target=1200).status_code, 200)
        self.assertEqual(self.rows(), [])
        self.assertEqual(len(self.rows("board_temperature")), 1)

    def test_failed_reading_is_stored_but_hidden(self):
        from server.models import get_data, get_most_recent
        self.send(0, distance_mm=2000)
        self.send(6, distance_mm=305, n_floor=1000)
        self.assertEqual(self.rows()[1].qc_flag, 4)

        span = (self.t0 - timedelta(hours=1), self.t0 + timedelta(hours=1))
        self.assertEqual(len(get_data("gauge", *span)), 1)
        self.assertEqual(len(get_data("gauge", *span, include_failed=True)), 2)

        recent = get_most_recent("gauge")
        self.assertEqual(recent[0][0].timestamp, self.t0)

    def test_spike_flags_previous_reading_when_next_arrives(self):
        from server.models import QcAssessment
        self.send(0, distance_mm=2000)
        self.send(6, distance_mm=1700)
        before = self.rows()[1]
        self.assertEqual(before.qc_flag, 1)

        self.send(12, distance_mm=2000)
        spiked = self.rows()[1]
        self.assertEqual(spiked.qc_flag, 4)
        assessment = QcAssessment.query.filter_by(sensor_data_id=spiked.id).one()
        self.assertEqual((assessment.flag, assessment.tests["spike"]), (4, 4))
        self.assertEqual(self.rows()[2].qc_flag, 1)

    def test_backfill_gets_no_series_tests_and_no_link_stats(self):
        from server.models import QcAssessment
        self.send(0)
        self.send(-6, status=0x08)
        late = self.rows()[0]
        self.assertNotIn("spike", QcAssessment.query.filter_by(sensor_data_id=late.id).one().tests)
        self.assertEqual(len(self.rows("rssi")), 1)
        self.assertEqual(len(self.rows("board_temperature")), 2)

    def test_backfill_uses_the_datum_valid_at_its_mark_time(self):
        from server.models import GaugeDatum, create_or_update_sensor, get_sensor_by_name
        from server.database import db
        sensor = get_sensor_by_name("gauge")
        create_or_update_sensor("gauge", 30.5, -87.9, "tide_gauge", sensor_id=sensor.id,
                                timezone=sensor.timezone, navd88_elevation=3.5)
        change = GaugeDatum.query.filter_by(valid_to=None).one()
        boundary = self.t0 + timedelta(hours=1)
        change.valid_from = boundary
        GaugeDatum.query.filter(GaugeDatum.id != change.id).one().valid_to = boundary
        db.session.commit()

        self.send(0, status=0x08, distance_mm=2000)
        self.send(120, distance_mm=2000)
        rows = self.rows()
        self.assertAlmostEqual(rows[0].value, 1.25)
        self.assertAlmostEqual(rows[1].value, 1.50)

    def add_gauge_without_elevation(self):
        from server.models import create_or_update_sensor
        self.assertIn("successfully", create_or_update_sensor("no_datum", 30.5, -87.9, "tide_gauge"))

    def assert_nothing_stored(self):
        from server.models import GaugeReading, SensorData
        self.assertEqual((GaugeReading.query.count(), SensorData.query.count()), (0, 0))

    def test_gauge_without_elevation_stores_nothing(self):
        self.add_gauge_without_elevation()
        when = self.t0
        for body in (packet("no_datum", when), packet("no_datum", when + timedelta(minutes=6), status=0x01),
                     packet("no_datum", when + timedelta(minutes=12), status=0x08), compact_packet("no_datum")):
            response = self.client.post("/receive_data", json=body)
            self.assertEqual(response.status_code, 200)
            self.assertIn("no NAVD88 elevation", response.json["message"])
        self.assert_nothing_stored()

    def test_gauge_stores_readings_once_elevation_is_set(self):
        from server.models import create_or_update_sensor, get_sensor_by_name
        self.add_gauge_without_elevation()
        self.client.post("/receive_data", json=packet("no_datum", self.t0))
        self.assert_nothing_stored()

        sensor = get_sensor_by_name("no_datum")
        create_or_update_sensor(sensor.name, sensor.latitude, sensor.longitude, sensor.device_type,
                                timezone=sensor.timezone, navd88_elevation=3.25)
        self.client.post("/receive_data", json=packet("no_datum", self.t0 + timedelta(minutes=6), status=0x08))
        self.assertEqual([round(row.value, 3) for row in self.rows()], [1.25])

    def test_unchanged_elevation_keeps_one_datum(self):
        from server.models import GaugeDatum, create_or_update_sensor, get_sensor_by_name
        sensor = get_sensor_by_name("gauge")
        create_or_update_sensor("gauge", 30.5, -87.9, "tide_gauge", sensor_id=sensor.id,
                                timezone=sensor.timezone, navd88_elevation=3.25)
        self.assertEqual(GaugeDatum.query.count(), 1)

    def test_invalid_payload_is_rejected(self):
        body = packet("gauge", self.t0)
        del body["object"]["sd_mm"]
        self.assertEqual(self.client.post("/receive_data", json=body).status_code, 400)

    def test_placeholder_battery_stays_out_of_the_health_panel(self):
        from server.models import GaugeReading
        self.send(battery=3.0, battery_valid=False)
        self.assertEqual(self.rows("battery"), [])
        self.assertEqual(GaugeReading.query.one().battery_v, 3.0)

    def test_real_battery_reaches_the_health_panel(self):
        self.send(battery=3.9, battery_valid=True)
        self.assertEqual(self.rows("battery")[0].value, 3.9)

    def test_compact_packet_gets_a_server_time_on_a_mark(self):
        from server.models import GaugeReading
        response = self.client.post("/receive_data", json=compact_packet("gauge"))
        self.assertEqual(response.status_code, 200)
        reading = GaugeReading.query.one()
        self.assertEqual(reading.time_source, "server")
        self.assertTrue(reading.degraded)
        self.assertIsNone(reading.n_floor)
        self.assertEqual(to_unix(reading.mark_time) % 360, 0)
        self.assertLess(0, (reading.received_at - reading.mark_time).total_seconds() + 1)
        self.assertLessEqual((reading.received_at - reading.mark_time).total_seconds(), 360)
        self.assertAlmostEqual(self.rows()[0].value, 1.25)

    def test_lost_clock_compact_packet_is_kept_as_suspect(self):
        from server.models import GaugeReading, QcAssessment
        response = self.client.post("/receive_data", json=compact_packet("gauge", status=0x01))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(GaugeReading.query.one().time_ok)
        entry = self.rows()[0]
        self.assertEqual(entry.qc_flag, 3)
        self.assertEqual(QcAssessment.query.one().tests["time_estimated"], 3)

    def test_lost_clock_compact_packets_do_not_collide(self):
        from server.models import GaugeReading
        self.client.post("/receive_data", json=compact_packet("gauge", status=0x01))
        self.client.post("/receive_data", json=compact_packet("gauge", status=0x01))
        self.assertEqual(GaugeReading.query.count(), 2)

    def test_estimated_time_allows_for_delivery_delay_and_cycles_back(self):
        from server.tide_gauge import estimate_mark_time
        received = datetime(2027, 3, 1, 12, 10, 15)
        self.assertEqual(estimate_mark_time(received, 2, 360), datetime(2027, 3, 1, 11, 56))

    def test_slow_send_stays_on_its_own_mark(self):
        from server.tide_gauge import rebuild_mark_time
        mark = datetime(2027, 3, 1, 12, 6)
        for delay in (90, 179, 180, 181, 264):
            self.assertEqual(rebuild_mark_time(mark + timedelta(seconds=delay), 0, 360), mark)

    def test_cycles_back_moves_a_compact_packet_earlier(self):
        from server.tide_gauge import rebuild_mark_time
        received = datetime(2027, 3, 1, 12, 7, 35)
        self.assertEqual(rebuild_mark_time(received, 5, 360), datetime(2027, 3, 1, 11, 36))

    def test_csv_times_are_in_the_sensor_timezone(self):
        from server.models import get_data
        from server.utils import save_data_to_csv
        self.send(0)                              # 2027-03-01 12:00 UTC, in winter
        self.t0 = datetime(2027, 7, 1, 12, 0)     # In summer, still standard time
        self.send(0)

        rows = save_data_to_csv(get_data("gauge", datetime(2027, 1, 1), datetime(2028, 1, 1)),
                                "gauge").splitlines()
        self.assertTrue(rows[3].startswith("timestamp (CST)"))
        self.assertTrue(rows[4].startswith("2027-03-01 06:00:00,"))
        self.assertTrue(rows[5].startswith("2027-07-01 06:00:00,"))

    def test_graph_times_do_not_repeat_when_the_clocks_go_back(self):
        from dash_app.callbacks.dashboard import load_series
        self.t0 = datetime(2026, 11, 1, 6, 54)    # 01:54 CDT, then the clock returns to 01:00
        for minutes in (0, 6, 12):
            self.send(minutes)

        series = load_series("gauge", datetime(2026, 11, 1), datetime(2026, 11, 2))
        self.assertEqual([t.strftime("%H:%M") for t in series["water_level"]["timestamps"]],
                         ["00:54", "01:00", "01:06"])

    def test_date_ranges_are_read_as_standard_time(self):
        from server.models import get_data
        self.t0 = datetime(2027, 7, 1, 12, 0)     # 06:00 CST
        self.send(0)

        def rows(hour):
            return get_data("gauge", datetime(2027, 7, 1, hour), datetime(2027, 7, 1, hour, 59), localize_input=True)
        self.assertTrue(rows(6))
        self.assertFalse(rows(7))

    def test_deleting_a_gauge_removes_only_its_own_rows(self):
        from server.models import (GaugeDatum, GaugeReading, LocationHistory, QcAssessment, QcConfig, SensorData,
                                   create_or_update_sensor, delete_sensor, get_sensor_by_name)
        create_or_update_sensor("other", 30.5, -87.9, "tide_gauge", navd88_elevation=3.0)
        self.client.post("/receive_data", json=packet("other", self.t0))
        self.send(0)
        self.send(6)
        models = (GaugeDatum, GaugeReading, LocationHistory, QcAssessment, QcConfig, SensorData)
        other_rows = {"datum": 1, "reading": 1, "location": 1, "qc": 1, "config": 1, "data": 4}

        delete_sensor(get_sensor_by_name("gauge").id)

        self.assertIsNone(get_sensor_by_name("gauge"))
        self.assertEqual([model.query.count() for model in models], list(other_rows.values()))
        self.assertEqual(self.client.post("/receive_data", json=packet("gauge", self.t0)).status_code, 403)

    def test_csv_header_has_location_above_the_data(self):
        from server.models import get_data
        from server.utils import save_data_to_csv
        self.send()
        span = (self.t0 - timedelta(hours=1), self.t0 + timedelta(hours=1))
        lines = save_data_to_csv(get_data("gauge", *span), "gauge").splitlines()
        self.assertEqual(lines[:3], ["Sensor Name: gauge", "Latitude: 30.5", "Longitude: -87.9"])
        self.assertTrue(lines[3].startswith("timestamp"))

    def test_csv_header_uses_the_deployment_of_the_data_not_the_current_one(self):
        from server.database import db
        from server.models import LocationHistory, get_data, get_sensor_by_name
        from server.utils import save_data_to_csv
        self.send()
        sensor = get_sensor_by_name("gauge")
        first = LocationHistory.query.one()
        first.deployed_at, first.removed_at = datetime(2027, 1, 1), datetime(2027, 6, 1)
        sensor.latitude, sensor.longitude = 31.0, -88.0
        db.session.add(LocationHistory(sensor_id=sensor.id, latitude=31.0, longitude=-88.0,
                                       deployed_at=datetime(2027, 6, 1)))
        db.session.commit()

        span = (self.t0 - timedelta(hours=1), self.t0 + timedelta(hours=1))
        lines = save_data_to_csv(get_data("gauge", *span), "gauge").splitlines()
        self.assertEqual(lines[1:3], ["Latitude: 30.5", "Longitude: -87.9"])

    def test_csv_header_lists_each_deployment_in_range(self):
        from server.database import db
        from server.models import LocationHistory, get_data, get_sensor_by_name
        from server.utils import save_data_to_csv
        self.send(0)
        self.send(60 * 24 * 200)
        first = LocationHistory.query.one()
        first.deployed_at, first.removed_at = datetime(2027, 1, 1), datetime(2027, 6, 1)
        db.session.add(LocationHistory(sensor_id=get_sensor_by_name("gauge").id, latitude=31.0,
                                       longitude=-88.0, deployed_at=datetime(2027, 6, 1)))
        db.session.commit()

        lines = save_data_to_csv(get_data("gauge", datetime(2027, 1, 1), datetime(2028, 1, 1)),
                                 "gauge").splitlines()
        self.assertEqual(lines[1], "Location 1: 30.5, -87.9 (2027-01-01 to 2027-06-01)")
        self.assertEqual(lines[2], "Location 2: 31.0, -88.0 (2027-06-01 to present)")

    def test_nerrs_and_qartod_can_sit_on_one_reading(self):
        from server.database import db
        from server.models import QcAssessment
        self.send()
        entry = self.rows()[0]
        db.session.add(QcAssessment(sensor_data_id=entry.id, scheme="nerrs", source="reviewer",
                                    flag=-3, error_code="SSD", comment_code="CRE"))
        db.session.add(QcAssessment(sensor_data_id=entry.id, scheme="nerrs", source="model",
                                    flag=1, error_code="SSD", score=0.8, model_version="v1"))
        db.session.commit()
        self.assertEqual(QcAssessment.query.filter_by(sensor_data_id=entry.id).count(), 3)

    def test_sensor_with_qc_data_can_be_deleted(self):
        from server.database import db
        from server.models import GaugeReading, LocationHistory, QcAssessment, get_sensor_by_name
        self.send()
        LocationHistory.query.delete()
        db.session.delete(get_sensor_by_name("gauge"))
        db.session.commit()
        self.assertEqual(GaugeReading.query.count(), 0)
        self.assertEqual(QcAssessment.query.count(), 0)


if __name__ == "__main__":
    unittest.main()
