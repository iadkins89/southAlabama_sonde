"""Checks the Sensor Health colors against what is normal for LoRa."""
import unittest

from dash_app.callbacks.dashboard import (RSSI_GOOD_ABOVE, RSSI_POOR_BELOW, SNR_GOOD_ABOVE,
                                          SNR_POOR_BELOW, signal_color)


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


if __name__ == "__main__":
    unittest.main()
