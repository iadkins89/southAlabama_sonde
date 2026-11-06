"""Checks the trend, status and quality figures shown on the home page and dashboards."""
import os
import unittest
from datetime import datetime, timedelta
from urllib.parse import unquote

from tests.shared_app import get_server

TEST_DB = os.environ.get("TEST_DATABASE_URL")
if TEST_DB:
    os.environ["DATABASE_URL"] = TEST_DB
    os.environ.setdefault("SECRET_KEY", "test")

from dash_app.callbacks.dashboard import change_line, sparkline_src, tide_direction  # noqa: E402

NOW = datetime(2026, 11, 5, 12, 0)


class Trends(unittest.TestCase):
    def series(self, values, step_minutes=6):
        return [NOW + timedelta(minutes=step_minutes * i) for i in range(len(values))], values

    def test_water_going_up_over_the_last_hour_is_rising(self):
        self.assertEqual(tide_direction(*self.series([0.1 + i * 0.01 for i in range(11)])), "Rising")

    def test_water_going_down_over_the_last_hour_is_falling(self):
        self.assertEqual(tide_direction(*self.series([0.5 - i * 0.01 for i in range(11)])), "Falling")

    def test_a_tiny_change_is_steady(self):
        self.assertEqual(tide_direction(*self.series([0.100, 0.101, 0.102])), "Steady")

    def test_direction_only_uses_the_last_hour(self):
        timestamps, values = self.series([9.0] + [0.1 + i * 0.01 for i in range(11)], step_minutes=6)
        timestamps[0] -= timedelta(hours=5)
        self.assertEqual(tide_direction(timestamps, values), "Rising")

    def test_one_reading_gives_no_direction(self):
        self.assertIsNone(tide_direction(*self.series([0.1])))

    def test_a_change_that_rounds_to_zero_never_shows_minus_zero(self):
        self.assertIn("No change in 24 h", str(change_line(-0.01, 1)))

    def test_a_flat_series_still_draws_a_sparkline(self):
        self.assertIn("polyline", unquote(sparkline_src([0.5, 0.5, 0.5])))

    def test_one_point_cannot_draw_a_sparkline(self):
        self.assertIsNone(sparkline_src([0.5]))


@unittest.skipUnless(TEST_DB, "TEST_DATABASE_URL not set")
class Summaries(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = get_server()

    def setUp(self):
        from server.database import db, run_migrations
        from server.models import SensorData, create_or_update_sensor, get_or_create_parameter, get_sensor_by_name
        self.ctx = self.server.app_context()
        self.ctx.push()
        db.drop_all()
        db.create_all()
        run_migrations()
        create_or_update_sensor("gauge", 30.5, -87.9, "tide_gauge", image_data=None)
        create_or_update_sensor("old", 30.6, -87.8, "sonde", active=False)
        gauge = get_sensor_by_name("gauge")
        level = get_or_create_parameter("water_level")
        now = datetime.utcnow()
        for age_days, flag in ((0, 1), (1, 1), (2, 3), (3, 4), (30, 4)):
            db.session.add(SensorData(sensor_id=gauge.id, parameter_id=level.id, value=0.2, qc_flag=flag,
                                      timestamp=now - timedelta(days=age_days)))
        db.session.commit()

    def tearDown(self):
        from server.database import db
        db.session.remove()
        self.ctx.pop()

    def test_quality_counts_only_cover_the_latest_seven_days(self):
        from server.models import get_qc_counts
        self.assertEqual(get_qc_counts("gauge"), {1: 2, 3: 1, 4: 1})

    def test_a_sensor_without_qc_has_no_quality_counts(self):
        from server.models import get_qc_counts
        self.assertEqual(get_qc_counts("old"), {})

    def test_the_network_summary_leaves_out_deactivated_sensors(self):
        from server.models import get_network_summary
        summary = get_network_summary()
        self.assertEqual((summary["active"], summary["online"], summary["reports_24h"]), (1, 1, 1))

    def test_the_sensor_list_is_public_but_small(self):
        response = self.server.test_client().get("/api/sensors")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(sorted(response.get_json()[0]), ["active", "device_type", "is_online", "name"])


if __name__ == "__main__":
    unittest.main()
