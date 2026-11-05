"""Checks that thinning a long graph keeps what a reader needs to see."""
import math
import unittest
from datetime import datetime, timedelta

from dash_app.callbacks.dashboard import GAUGE_GAP, THIN_BLOCKS, thin_line

START = datetime(2026, 1, 1)
STEP = timedelta(minutes=6)


def year_of_tides(skip=lambda i: False):
    timestamps, values = [], []
    for i in range(87600):
        if not skip(i):
            timestamps.append(START + i * STEP)
            values.append(math.sin(i / 40))
    return timestamps, values


class ThinLine(unittest.TestCase):
    def test_a_year_becomes_about_two_points_per_block(self):
        x, y = thin_line(*year_of_tides())
        self.assertLessEqual(len(x), 2 * THIN_BLOCKS + 3)
        self.assertEqual(x, sorted(x))

    def test_a_one_reading_peak_survives(self):
        timestamps, values = year_of_tides()
        values[43210] = 9.0
        values[50000] = -9.0
        x, y = thin_line(timestamps, values)
        self.assertEqual((max(y), min(y)), (9.0, -9.0))
        self.assertIn(timestamps[43210], x)

    def test_the_first_and_last_readings_are_kept(self):
        timestamps, values = year_of_tides()
        x, _ = thin_line(timestamps, values)
        self.assertEqual((x[0], x[-1]), (timestamps[0], timestamps[-1]))

    def test_no_data_gap_means_no_break_in_the_line(self):
        _, y = thin_line(*year_of_tides(), max_gap=GAUGE_GAP)
        self.assertNotIn(None, y)

    def test_an_outage_shorter_than_a_block_still_breaks_the_line(self):
        timestamps, values = year_of_tides(skip=lambda i: 20000 <= i < 20010)
        x, y = thin_line(timestamps, values, GAUGE_GAP)
        self.assertEqual(y.count(None), 1)
        break_at = y.index(None)
        self.assertEqual(x[break_at - 1], START + 19999 * STEP)
        self.assertEqual(x[break_at + 1], START + 20010 * STEP)


if __name__ == "__main__":
    unittest.main()
