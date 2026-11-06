"""Checks the coordinates shown on a dashboard's summary card."""
import unittest

from dash_app.callbacks.dashboard import format_location


class FormatLocation(unittest.TestCase):
    def test_mobile_bay_reads_west_without_a_minus_sign(self):
        self.assertEqual(format_location(30.45, -88.0), "30.45°N   88.0°W")

    def test_other_hemispheres_get_their_own_letters(self):
        self.assertEqual(format_location(-12.5, 45.0), "12.5°S   45.0°E")

    def test_a_missing_location_does_not_crash(self):
        self.assertEqual(format_location(None, -88.0), "Location unavailable")


if __name__ == "__main__":
    unittest.main()
