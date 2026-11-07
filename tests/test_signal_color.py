"""Checks the Sensor Health colors against what is normal for LoRa."""
import unittest

from dash_app.callbacks.dashboard import (RSSI_GOOD_ABOVE, RSSI_POOR_BELOW, SNR_GOOD_ABOVE,
                                          SNR_POOR_BELOW, board_temp_bar, signal_color)


class SignalColor(unittest.TestCase):
    def rssi(self, value):
        return signal_color(value, RSSI_GOOD_ABOVE, RSSI_POOR_BELOW)

    def snr(self, value):
        return signal_color(value, SNR_GOOD_ABOVE, SNR_POOR_BELOW)

    def test_rssi(self):
        self.assertEqual([self.rssi(v) for v in (-95, -100, -115, -118)],
                         ["success", "warning", "warning", "danger"])

    def test_snr(self):
        self.assertEqual([self.snr(v) for v in (7.5, -5, -14.5, -15, -16)],
                         ["success", "warning", "warning", "warning", "danger"])

    def test_board_temperature(self):
        self.assertEqual([board_temp_bar(t) for t in (24.5, 60, 75, -15)],
                         [(44, "success"), (80, "warning"), (95, "danger"), (5, "danger")])

    def test_board_temperature_bar_stays_within_its_ends(self):
        self.assertEqual((board_temp_bar(200)[0], board_temp_bar(-60)[0]), (100, 0))


if __name__ == "__main__":
    unittest.main()
