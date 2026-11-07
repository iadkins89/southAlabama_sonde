"""Checks that each onboarding timezone maps to one offset all year."""
import unittest
from datetime import timedelta

from server.models import standard_time


class StandardTime(unittest.TestCase):
    def check(self, name, label, hours):
        zone = standard_time(name)
        self.assertEqual((str(zone), zone.utcoffset(None)), (label, timedelta(hours=hours)))

    def test_onboarding_choices(self):
        self.check("America/Chicago", "CST", -6)
        self.check("America/New_York", "EST", -5)
        self.check("UTC", "UTC", 0)

    def test_southern_hemisphere_uses_its_winter_offset(self):
        self.check("Australia/Sydney", "AEST", 10)

    def test_unknown_timezone_falls_back_to_utc(self):
        self.check("Not/AZone", "UTC", 0)


if __name__ == "__main__":
    unittest.main()
