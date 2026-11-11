"""
Checks that test devices stay off the public site, have no location until they go
live, and that going live clears the readings taken while testing. Needs a
throwaway Postgres database in TEST_DATABASE_URL.
"""
import os
import unittest
from datetime import datetime
from unittest import mock

from tests.shared_app import get_server

TEST_DB = os.environ.get("TEST_DATABASE_URL")
if TEST_DB:
    os.environ["DATABASE_URL"] = TEST_DB
    os.environ.setdefault("SECRET_KEY", "test")


def packet(device, hour=12):
    return {
        "deviceInfo": {"deviceName": device},
        "rxInfo": [{"rssi": -95, "snr": 7.5}],
        "object": {"timestamp": int(datetime(2026, 11, 5, hour, 0).timestamp()), "temperature": 21.5},
    }


@unittest.skipUnless(TEST_DB, "TEST_DATABASE_URL not set")
class TestDevices(unittest.TestCase):
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
        create_or_update_sensor("live_sonde", 30.5, -87.9, "sonde")
        # Coordinates given to a test device (say, a house) must not be kept
        create_or_update_sensor("bench_sonde", 30.1, -88.1, "sonde", testing=True)
        self.client = self.server.test_client()

    def tearDown(self):
        from server.database import db
        db.session.remove()
        self.ctx.pop()

    def sensor(self, name):
        from server.database import db
        from server.models import get_sensor_by_name
        db.session.expire_all()
        return get_sensor_by_name(name)

    def history(self, name):
        from server.models import LocationHistory
        return LocationHistory.query.filter_by(sensor_id=self.sensor(name).id).all()

    def test_a_test_device_has_no_location_or_deployment(self):
        bench = self.sensor("bench_sonde")
        self.assertTrue(bench.testing)
        self.assertEqual((bench.latitude, bench.longitude), (None, None))
        self.assertEqual(self.history("bench_sonde"), [])
        self.assertEqual(len(self.history("live_sonde")), 1)

    def test_updating_a_test_device_stores_no_location(self):
        from server.models import create_or_update_sensor
        message = create_or_update_sensor("bench_sonde", 30.2, -88.2, "sonde",
                                          sensor_id=self.sensor("bench_sonde").id)
        self.assertIn("successfully", message)
        self.assertIsNone(self.sensor("bench_sonde").latitude)
        self.assertEqual(self.history("bench_sonde"), [])

    def test_public_lists_leave_out_test_devices(self):
        from server.models import get_all_sensors, get_network_summary
        self.assertEqual([s["name"] for s in get_all_sensors()], ["live_sonde"])
        self.assertEqual([s["name"] for s in get_all_sensors(testing=True)], ["bench_sonde"])
        names = [s["name"] for s in self.client.get("/api/sensors").get_json()]
        self.assertEqual(names, ["live_sonde"])

        self.client.post("/receive_data", json=packet("bench_sonde"))
        self.assertEqual(get_network_summary()["reports_24h"], 0)

    def test_test_device_packets_are_stored_but_not_broadcast(self):
        from server.models import SensorData
        with mock.patch("server.routes.emit_event") as emit:
            self.assertEqual(self.client.post("/receive_data", json=packet("bench_sonde")).status_code, 200)
            emit.assert_not_called()
            self.client.post("/receive_data", json=packet("live_sonde"))
            emit.assert_called_once()
        self.assertGreater(SensorData.query.filter_by(sensor_id=self.sensor("bench_sonde").id).count(), 0)

    def admin_id(self):
        from server.database import db
        from server.models import User
        admin = User.query.filter_by(username="admin").first()
        if not admin:
            admin = User(username="admin", is_admin=True)
            admin.set_password("x")
            db.session.add(admin)
            db.session.commit()
        return admin.id

    def dashboard(self, sensor, logged_in):
        import dash
        from flask import session
        page = next(p for p in dash.page_registry.values() if p["path"] == "/dashboard")
        user_id = self.admin_id()
        with self.server.test_request_context():
            session.update(user_logged_in=logged_in, user_id=user_id)
            return str(page["layout"](sensor=sensor))

    def test_a_test_device_dashboard_needs_a_login(self):
        self.assertIn("couldn't find that page", self.dashboard("bench_sonde", logged_in=False))
        signed_in = self.dashboard("bench_sonde", logged_in=True)
        self.assertNotIn("couldn't find that page", signed_in)
        self.assertNotIn("couldn't find that page", self.dashboard("live_sonde", logged_in=False))

    def test_dashboard_data_needs_a_login_for_test_devices(self):
        from flask import session
        from dash_app.callbacks.dashboard import can_view
        user_id = self.admin_id()
        with self.server.test_request_context():
            session.update(user_logged_in=False, user_id=user_id)
            self.assertFalse(can_view("bench_sonde"))
            self.assertTrue(can_view("live_sonde"))
            session["user_logged_in"] = True
            self.assertTrue(can_view("bench_sonde"))

    def test_going_live_clears_test_readings_and_starts_a_deployment(self):
        from server.models import SensorData, count_test_readings, get_all_sensors, go_live
        self.client.post("/receive_data", json=packet("bench_sonde"))
        bench_id = self.sensor("bench_sonde").id
        self.assertGreater(count_test_readings(bench_id), 0)

        self.assertIsNone(go_live(bench_id, 30.25, -88.08))

        bench = self.sensor("bench_sonde")
        self.assertFalse(bench.testing)
        self.assertEqual((bench.latitude, bench.longitude), (30.25, -88.08))
        self.assertEqual(SensorData.query.filter_by(sensor_id=bench_id).count(), 0)
        history = self.history("bench_sonde")
        self.assertEqual([(h.latitude, h.longitude, h.removed_at) for h in history], [(30.25, -88.08, None)])
        self.assertIn("bench_sonde", [s["name"] for s in get_all_sensors()])

        # Readings after going live are kept
        self.client.post("/receive_data", json=packet("bench_sonde", hour=13))
        self.assertGreater(SensorData.query.filter_by(sensor_id=bench_id).count(), 0)

    def test_going_live_checks_its_input(self):
        from server.models import go_live
        bench_id = self.sensor("bench_sonde").id
        self.assertIn("numbers", go_live(bench_id, None, -88.08))
        self.assertIn("out of range", go_live(bench_id, 95, -88.08))
        self.assertTrue(self.sensor("bench_sonde").testing)
        self.assertIn("already live", go_live(self.sensor("live_sonde").id, 30.0, -88.0))

    def test_a_test_gauge_gets_a_fresh_datum_when_it_goes_live(self):
        from server.models import GaugeDatum, create_or_update_sensor, go_live
        create_or_update_sensor("bench_gauge", None, None, "tide_gauge", navd88_elevation=0, testing=True)
        gauge_id = self.sensor("bench_gauge").id

        self.assertIsNone(go_live(gauge_id, 30.25, -88.08, 1.234))

        datums = GaugeDatum.query.filter_by(sensor_id=gauge_id).all()
        self.assertEqual([(d.elevation_m, d.valid_to) for d in datums], [(1.234, None)])
        self.assertEqual(self.sensor("bench_gauge").navd88_elevation, 1.234)


if __name__ == "__main__":
    unittest.main()
