import unittest
from datetime import datetime, timedelta
from types import SimpleNamespace

from server.qc import (DEFAULT_WATER_LEVEL_CONFIG as CFG, FAIL, NOT_EVALUATED, PASS, SUSPECT,
                       attenuated_signal_test, evaluate_reading, flat_line_test, gross_range_test,
                       is_consecutive, overall_flag, rate_of_change_test, spike_test, window_checks)

STATS = {"n_used": 1200, "n_rejected": 5, "n_no_target": 0, "n_floor": 0, "sd_mm": 40, "dropped": False}


class GrossRange(unittest.TestCase):
    def test_sensor_limits(self):
        self.assertEqual(gross_range_test(2000, 1.0, CFG), PASS)
        self.assertEqual(gross_range_test(4999, 1.0, CFG), PASS)
        self.assertEqual(gross_range_test(311, 1.0, CFG), PASS)
        self.assertEqual(gross_range_test(310, 1.0, CFG), FAIL)
        self.assertEqual(gross_range_test(5000, 1.0, CFG), FAIL)

    def test_user_limits_only_reach_suspect(self):
        cfg = {**CFG, "user_min_m": -1.0, "user_max_m": 2.0}
        self.assertEqual(gross_range_test(2000, 2.5, cfg), SUSPECT)
        self.assertEqual(gross_range_test(2000, -1.5, cfg), SUSPECT)
        self.assertEqual(gross_range_test(2000, 1.0, cfg), PASS)


class Spike(unittest.TestCase):
    def test_thresholds(self):
        self.assertEqual(spike_test(1.0, 1.05, 1.0, CFG), PASS)
        self.assertEqual(spike_test(1.0, 1.15, 1.0, CFG), SUSPECT)
        self.assertEqual(spike_test(1.0, 1.25, 1.0, CFG), FAIL)
        self.assertEqual(spike_test(1.0, 0.75, 1.0, CFG), FAIL)

    def test_steady_tide_is_not_a_spike(self):
        self.assertEqual(spike_test(1.00, 1.03, 1.06, CFG), PASS)

    def test_a_step_is_not_a_spike(self):
        self.assertEqual(spike_test(1.0, 1.0, 1.5, CFG), PASS)

    def test_good_readings_beside_a_spike_are_not_flagged(self):
        self.assertEqual(spike_test(1.0, 1.0, 1.4, CFG), PASS)
        self.assertEqual(spike_test(1.4, 1.0, 1.0, CFG), PASS)


class RateOfChange(unittest.TestCase):
    window = [0.0, 0.1] * 100

    def test_needs_enough_history(self):
        self.assertEqual(rate_of_change_test(1.0, 0.9, [0.0, 0.1], CFG), NOT_EVALUATED)
        self.assertEqual(rate_of_change_test(1.0, None, self.window, CFG), NOT_EVALUATED)

    def test_never_fails(self):
        self.assertEqual(rate_of_change_test(5.0, 0.0, self.window, CFG), SUSPECT)
        self.assertEqual(rate_of_change_test(0.11, 0.1, self.window, CFG), PASS)


class FlatLine(unittest.TestCase):
    def test_counts_include_the_current_reading(self):
        self.assertEqual(flat_line_test(1.0, [], CFG), NOT_EVALUATED)
        self.assertEqual(flat_line_test(1.0, [1.0], CFG), NOT_EVALUATED)
        self.assertEqual(flat_line_test(1.0, [1.0, 1.0], CFG), SUSPECT)

    def test_stops_at_suspect_by_default(self):
        self.assertEqual(flat_line_test(1.0, [1.0] * 20, CFG), SUSPECT)

    def test_fails_once_a_fail_count_is_set(self):
        cfg = {**CFG, "flat_fail_count": 5}
        self.assertEqual(flat_line_test(1.0, [1.0, 1.0, 1.0], cfg), SUSPECT)
        self.assertEqual(flat_line_test(1.0, [1.0, 1.0, 1.0, 1.0], cfg), FAIL)

    def test_one_millimetre_is_movement(self):
        # Water levels near 1.235 m don't subtract to exactly 0.001 in floats.
        self.assertEqual(flat_line_test(1.234, [1.235, 1.234], CFG), PASS)


class AttenuatedSignal(unittest.TestCase):
    def test_off_until_configured(self):
        self.assertEqual(attenuated_signal_test([1.0, 1.0], CFG), NOT_EVALUATED)

    def test_thresholds(self):
        cfg = {**CFG, "attenuated_warn_m": 0.05, "attenuated_fail_m": 0.01}
        self.assertEqual(attenuated_signal_test([1.0, 1.2], cfg), PASS)
        self.assertEqual(attenuated_signal_test([1.0, 1.02], cfg), SUSPECT)
        self.assertEqual(attenuated_signal_test([1.0, 1.005], cfg), FAIL)


class WindowChecks(unittest.TestCase):
    def test_healthy_window_passes(self):
        self.assertTrue(all(flag == PASS for flag in window_checks(STATS, CFG).values()))

    def test_each_problem_is_suspect(self):
        self.assertEqual(window_checks({**STATS, "n_used": 300}, CFG)["few_readings"], SUSPECT)
        self.assertEqual(window_checks({**STATS, "n_rejected": 300}, CFG)["high_rejection"], SUSPECT)
        self.assertEqual(window_checks({**STATS, "n_no_target": 300}, CFG)["no_target_readings"], SUSPECT)
        self.assertEqual(window_checks({**STATS, "n_floor": 1}, CFG)["at_minimum_range"], SUSPECT)
        self.assertEqual(window_checks({**STATS, "sd_mm": 0}, CFG)["sd_zero"], SUSPECT)
        self.assertEqual(window_checks({**STATS, "dropped": True}, CFG)["samples_dropped"], SUSPECT)

    def test_compact_packets_have_no_floor_count(self):
        self.assertEqual(window_checks({**STATS, "n_floor": None}, CFG)["at_minimum_range"], NOT_EVALUATED)


class OverallFlag(unittest.TestCase):
    def test_worst_result_wins(self):
        self.assertEqual(overall_flag({"a": PASS, "b": SUSPECT, "c": FAIL}), FAIL)
        self.assertEqual(overall_flag({"a": PASS, "b": SUSPECT}), SUSPECT)

    def test_pending_tests_do_not_hide_a_pass(self):
        self.assertEqual(overall_flag({"a": PASS, "b": NOT_EVALUATED}), PASS)
        self.assertEqual(overall_flag({"a": NOT_EVALUATED}), NOT_EVALUATED)


class EvaluateReading(unittest.TestCase):
    now = datetime(2027, 1, 1, 12, 0)

    def row(self, minutes_ago, value, flag=PASS):
        return SimpleNamespace(timestamp=self.now - timedelta(minutes=minutes_ago), value=value, qc_flag=flag)

    def evaluate(self, history, backfill=False):
        stats = {**STATS, "timestamp": self.now}
        return evaluate_reading(1.0, 2000, stats, history, CFG, backfill)

    def test_backfill_only_gets_single_reading_checks(self):
        tests = self.evaluate([], backfill=True)
        self.assertIn("gross_range", tests)
        for name in ("spike", "rate_of_change", "flat_line", "attenuated_signal"):
            self.assertNotIn(name, tests)

    def test_spike_starts_pending(self):
        self.assertEqual(self.evaluate([])["spike"], NOT_EVALUATED)

    def test_failed_readings_still_count_towards_flat_line(self):
        history = [self.row(m, 1.0, FAIL) for m in (24, 18, 12, 6)]
        self.assertEqual(self.evaluate(history)["flat_line"], SUSPECT)

    def test_a_gap_resets_flat_line(self):
        self.assertEqual(self.evaluate([self.row(m, 1.0) for m in (48, 42, 36, 30)])["flat_line"], NOT_EVALUATED)

    def test_is_consecutive(self):
        self.assertTrue(is_consecutive(self.now, self.now + timedelta(minutes=6), 360))
        self.assertFalse(is_consecutive(self.now, self.now + timedelta(minutes=12), 360))
        self.assertFalse(is_consecutive(self.now, self.now, 360))


if __name__ == "__main__":
    unittest.main()
