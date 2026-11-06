"""Checks the names shown on a dashboard."""
import unittest

from dash_app.callbacks.dashboard import parameter_label, sensor_label


class Labels(unittest.TestCase):
    def test_parameters_read_as_words(self):
        self.assertEqual(parameter_label("dissolved_oxygen"), "Dissolved oxygen")

    def test_ph_keeps_its_capital(self):
        self.assertEqual([parameter_label(n) for n in ("ph", "pH", "PH")], ["pH"] * 3)

    def test_sensor_names_lose_their_underscores(self):
        self.assertEqual(sensor_label("sim_year_sonde"), "Sim Year Sonde")


if __name__ == "__main__":
    unittest.main()
