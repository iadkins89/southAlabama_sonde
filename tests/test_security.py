"""
Checks that packets need the token and that sensor changes need a login, using
the real routes. Needs a throwaway Postgres database in TEST_DATABASE_URL.
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


def sonde_packet():
    return {
        "deviceInfo": {"deviceName": "sonde"},
        "rxInfo": [{"rssi": -95, "snr": 7.5}],
        "object": {"timestamp": int(datetime(2026, 11, 5, 12, 0).timestamp()), "temperature": 21.5},
    }


def dash_call(output, outputs, button, state):
    return {
        "output": output,
        "outputs": outputs,
        "inputs": [{"id": button, "property": "n_clicks", "value": 1}],
        "changedPropIds": [f"{button}.n_clicks"],
        "state": [{"id": k, "property": p, "value": v} for k, p, v in state],
    }


def add_sensor_call(name):
    return dash_call(
        "..submission-response.children...sensor-update.data..",
        [{"id": "submission-response", "property": "children"},
         {"id": "sensor-update", "property": "data"}],
        "submit-btn",
        [("device-name", "value", name), ("latitude", "value", 30.5), ("longitude", "value", -87.9),
         ("timezone", "value", "America/Chicago"), ("device-type", "value", "sonde"),
         ("device-image", "contents", None), ("gauge-elevation", "value", None)],
    )


def update_sensor_call(button):
    return {
        **dash_call(
            "update-submission-response.children",
            {"id": "update-submission-response", "property": "children"},
            button,
            [("select-device-dropdown", "value", "sonde"), ("update-device-name", "value", "renamed"),
             ("update-latitude", "value", 1.0), ("update-longitude", "value", 2.0),
             ("update-device-type", "value", "sonde"), ("update-device-image", "contents", None),
             ("update-gauge-elevation", "value", None), ("sensor-active-status-store", "data", True)],
        ),
        "inputs": [{"id": "update-submit-btn", "property": "n_clicks", "value": 1},
                   {"id": "toggle-active-btn", "property": "n_clicks", "value": 1}],
    }


@unittest.skipUnless(TEST_DB, "TEST_DATABASE_URL not set")
class Security(unittest.TestCase):
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
        create_or_update_sensor("sonde", 30.5, -87.9, "sonde")
        self.client = self.server.test_client()

    def tearDown(self):
        from server.database import db
        db.session.remove()
        self.ctx.pop()

    def stored_rows(self):
        from server.models import SensorData
        return SensorData.query.count()

    def log_in(self):
        with self.client.session_transaction() as session:
            session["user_logged_in"] = True

    def sensor(self, name):
        from server.database import db
        from server.models import get_sensor_by_name
        db.session.expire_all()
        return get_sensor_by_name(name)

    def test_without_a_configured_token_packets_are_accepted(self):
        with mock.patch.dict(os.environ):
            os.environ.pop("INGEST_TOKEN", None)
            self.assertEqual(self.client.post("/receive_data", json=sonde_packet()).status_code, 200)
        self.assertGreater(self.stored_rows(), 0)

    def test_a_missing_or_wrong_token_stores_nothing(self):
        with mock.patch.dict(os.environ, {"INGEST_TOKEN": "right"}):
            responses = [
                self.client.post("/receive_data", json=sonde_packet()),
                self.client.post("/receive_data", json=sonde_packet(), headers={"X-Ingest-Token": "wrong"}),
                self.client.post("/receive_data?token=wrong", json=sonde_packet()),
                self.client.post("/receive_data", json=sonde_packet(), headers={"X-Ingest-Token": "é"}),
            ]
        self.assertEqual([r.status_code for r in responses], [401] * 4)
        self.assertEqual(self.stored_rows(), 0)

    def test_the_right_token_is_accepted_by_header_or_url(self):
        with mock.patch.dict(os.environ, {"INGEST_TOKEN": "right"}):
            header = self.client.post("/receive_data", json=sonde_packet(), headers={"X-Ingest-Token": "right"})
            url = self.client.post("/receive_data?token=right", json=sonde_packet())
        self.assertEqual((header.status_code, url.status_code), (200, 200))

    def test_adding_a_sensor_needs_a_login(self):
        response = self.client.post("/_dash-update-component", json=add_sensor_call("intruder"))
        self.assertIn("log in", response.get_data(as_text=True))
        self.assertIsNone(self.sensor("intruder"))

    def test_a_logged_in_user_can_add_a_sensor(self):
        self.log_in()
        self.client.post("/_dash-update-component", json=add_sensor_call("new_sonde"))
        self.assertIsNotNone(self.sensor("new_sonde"))

    def test_updating_or_deactivating_a_sensor_needs_a_login(self):
        for button in ("update-submit-btn", "toggle-active-btn"):
            response = self.client.post("/_dash-update-component", json=update_sensor_call(button))
            self.assertIn("log in", response.get_data(as_text=True))
        sensor = self.sensor("sonde")
        self.assertEqual((sensor.latitude, sensor.active), (30.5, True))
        self.assertIsNone(self.sensor("renamed"))

    def test_a_logged_in_user_can_update_a_sensor(self):
        self.log_in()
        self.client.post("/_dash-update-component", json=update_sensor_call("update-submit-btn"))
        self.assertIsNotNone(self.sensor("renamed"))

    def try_delete(self, password, logged_in=True):
        from flask import session
        from dash_app.callbacks.update_sensor import delete_error
        from server.database import db
        from server.models import User

        user = User(username="tester")
        user.set_password("right")
        db.session.add(user)
        db.session.commit()
        with self.server.test_request_context():
            session.update(user_logged_in=logged_in, user_id=user.id)
            return delete_error("sonde", password)

    def test_deleting_a_sensor_needs_a_login(self):
        self.assertEqual(self.try_delete("right", logged_in=False), "Please log in again.")
        self.assertIsNotNone(self.sensor("sonde"))

    def test_deleting_a_sensor_needs_the_right_password(self):
        self.assertEqual(self.try_delete("wrong"), "Incorrect password.")
        self.assertIsNotNone(self.sensor("sonde"))

    def test_an_empty_password_deletes_nothing(self):
        self.assertEqual(self.try_delete(None), "Incorrect password.")
        self.assertIsNotNone(self.sensor("sonde"))

    def test_the_right_password_deletes_the_sensor(self):
        self.assertIsNone(self.try_delete("right"))
        self.assertIsNone(self.sensor("sonde"))


if __name__ == "__main__":
    unittest.main()
