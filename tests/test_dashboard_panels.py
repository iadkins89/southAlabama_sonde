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

from dash_app.callbacks.dashboard import (GAUGE_GAP, change_line, hourly_change, reading_tile,  # noqa: E402
                                          sparkline_src, tide_trend, trend_start)

NOW = datetime(2026, 11, 5, 12, 0)


class HourlyChange(unittest.TestCase):
    def series(self, values, step_minutes=6):
        return [NOW + timedelta(minutes=step_minutes * i) for i in range(len(values))], values

    def test_it_measures_the_rise_over_the_hour(self):
        change, minutes = hourly_change(*self.series([0.1 + i * 0.01 for i in range(11)]))
        self.assertAlmostEqual(change, 0.10)
        self.assertEqual(minutes, 60)

    def test_one_noisy_last_reading_cannot_flip_it(self):
        values = [0.5 - i * 0.01 for i in range(11)]
        values[-1] = 0.45
        self.assertLess(hourly_change(*self.series(values))[0], 0)

    def test_only_the_last_hour_counts(self):
        falling = [9.0 - i * 0.1 for i in range(60)]
        rising = [3.0 + i * 0.01 for i in range(11)]
        self.assertGreater(hourly_change(*self.series(falling + rising))[0], 0)

    def test_a_full_hour_of_15_minute_sonde_readings_is_enough(self):
        self.assertIsNotNone(hourly_change(*self.series([1, 2, 3, 4, 5], step_minutes=15)))

    def test_too_few_readings_gives_nothing(self):
        self.assertIsNone(hourly_change(*self.series([0.1, 0.2, 0.3], step_minutes=15)))

    def test_too_short_a_stretch_gives_nothing(self):
        self.assertIsNone(hourly_change(*self.series([0.1, 0.2, 0.3, 0.4, 0.5, 0.6], step_minutes=1)))


class TideTrend(unittest.TestCase):
    def test_the_word_follows_the_change_over_the_hour(self):
        self.assertEqual([tide_trend(c) for c in (0.1, -0.1, 0.002)], ["Rising", "Falling", "Steady"])


class ChangeLine(unittest.TestCase):
    def test_it_gives_the_amount_with_its_unit(self):
        self.assertIn("-0.067 m in last hour", str(change_line(-0.067, 60, 3, "m")))
        self.assertIn("bi-arrow-down-right", str(change_line(-0.067, 60, 3, "m")))

    def test_rising_points_up(self):
        self.assertIn("bi-arrow-up-right", str(change_line(0.4, 60, 1, "\u00B0C")))

    def test_a_reading_with_no_unit_still_reads_cleanly(self):
        self.assertIn("+0.1 in last hour", str(change_line(0.1, 60, 1, "")))

    def test_a_short_stretch_says_how_short(self):
        self.assertIn("in last 35 min", str(change_line(0.5, 35, 1, "m")))

    def test_a_change_that_rounds_to_zero_never_shows_minus_zero(self):
        self.assertIn("No net change in last hour", str(change_line(-0.01, 60, 1, "m")))


class ReadingTile(unittest.TestCase):
    timestamps = [NOW + timedelta(minutes=6 * i) for i in range(11)]
    values = [0.1 + i * 0.01 for i in range(11)]

    def text(self, **options):
        return str(reading_tile("Level", 0.3, "m", values=self.values, timestamps=self.timestamps, **options))

    def test_a_gauge_shows_its_trend_and_amount(self):
        text = self.text(is_water_level=True)
        self.assertIn("Rising, last hour", text)
        self.assertIn("+0.100 m in last hour", text)

    def test_a_sonde_shows_the_amount_but_no_trend_word(self):
        text = self.text()
        self.assertNotIn("Rising", text)
        self.assertIn("+0.1 m in last hour", text)

    def test_no_tile_shows_a_24_hour_change_or_range(self):
        for text in (self.text(), self.text(is_water_level=True)):
            self.assertNotIn("24 h", text)
            self.assertNotIn("range", text)


def path_of(timestamps, values, max_gap=timedelta(hours=1)):
    svg = unquote(sparkline_src(timestamps, values, max_gap))
    return svg.split('d="')[1].split('"')[0].split()


def xs(path):
    return [float(word[1:]) for word in path[0::2]]


class Sparkline(unittest.TestCase):
    def hours(self, *offsets):
        return [NOW + timedelta(hours=h) for h in offsets]

    def test_points_sit_at_their_real_time_not_evenly(self):
        path = path_of(self.hours(0, 1, 23, 24), [1, 2, 3, 4], max_gap=timedelta(hours=30))
        self.assertEqual(xs(path), [0.0, 5.0, 115.0, 120.0])

    def test_a_burst_of_readings_stays_in_its_share_of_the_time(self):
        burst = [NOW + timedelta(hours=23, seconds=5 * i) for i in range(200)]
        timestamps = self.hours(0, 6, 12, 18) + burst
        path = path_of(timestamps, [1.0, 2.0, 3.0, 4.0] + [5.0] * 200, max_gap=timedelta(hours=30))
        span_hours = (timestamps[-1] - timestamps[0]).total_seconds() / 3600
        self.assertEqual(xs(path)[:4], [round(hour / span_hours * 120, 1) for hour in (0, 6, 12, 18)])
        self.assertTrue(all(x >= 118 for x in xs(path)[4:]))

    def test_the_newest_reading_always_ends_the_line(self):
        timestamps = [NOW + timedelta(minutes=15 * i) for i in range(301)]
        values = [float(i % 7) for i in range(301)]
        values[-1] = 3.5
        path = path_of(timestamps, values, max_gap=timedelta(hours=1))
        self.assertEqual(xs(path)[-1], 120.0)
        expected_y = 30 - 2 - 3.5 / 6 * 26
        self.assertAlmostEqual(float(path[-1]), expected_y, places=1)

    def test_an_outage_breaks_the_line(self):
        timestamps = [NOW + timedelta(minutes=6 * i) for i in range(20)]
        timestamps += [timestamps[-1] + timedelta(hours=4, minutes=6 * i) for i in range(20)]
        path = path_of(timestamps, [float(i) for i in range(40)], max_gap=GAUGE_GAP)
        self.assertEqual(sum(word.startswith("M") for word in path), 2)

    def test_a_one_reading_peak_survives(self):
        timestamps = [NOW + timedelta(minutes=15 * i) for i in range(400)]
        values = [1.0] * 400
        values[123] = 9.0
        ys = [float(word) for word in path_of(timestamps, values)[1::2]]
        self.assertEqual(min(ys), 2.0)  # The top of the sparkline

    def test_a_flat_series_still_draws_a_line(self):
        self.assertTrue(path_of(self.hours(0, 1, 2), [0.5, 0.5, 0.5]))

    def test_one_reading_cannot_draw_a_line(self):
        self.assertIsNone(sparkline_src([NOW], [0.5], timedelta(hours=1)))

    def test_readings_at_one_moment_cannot_draw_a_line(self):
        self.assertIsNone(sparkline_src([NOW, NOW], [0.5, 0.6], timedelta(hours=1)))


class TrendWindow(unittest.TestCase):
    latest = datetime(2026, 11, 6, 12, 0)

    def test_it_covers_24_hours(self):
        self.assertEqual(trend_start(self.latest, None), self.latest - timedelta(hours=24))

    def test_it_stops_at_the_start_of_a_new_deployment(self):
        deployed = {"is_current": True, "start_iso": "2026-11-06T09:00:00"}
        self.assertEqual(trend_start(self.latest, deployed), datetime(2026, 11, 6, 9, 0))

    def test_an_old_deployment_does_not_shorten_it(self):
        deployed = {"is_current": True, "start_iso": "2025-01-01T00:00:00"}
        self.assertEqual(trend_start(self.latest, deployed), self.latest - timedelta(hours=24))


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
