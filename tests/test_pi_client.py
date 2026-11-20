import unittest
from scripts.pi_relay_client import PiRelayClient, DEFAULT_RELAY_PINS


class TestPiRelayClient(unittest.TestCase):
    def setUp(self):
        self.client = PiRelayClient("http://127.0.0.1:8000", use_mock=True)

    def tearDown(self):
        self.client.cleanup()

    def test_initial_relay_states(self):
        for sw_id in self.client.relay_pins:
            self.assertFalse(self.client.current_relay_states[sw_id])

    def test_set_relay(self):
        self.client.set_relay("RELAY_LGT_BAY_1", True)
        self.assertTrue(self.client.current_relay_states["RELAY_LGT_BAY_1"])

        self.client.set_relay("RELAY_LGT_BAY_1", False)
        self.assertFalse(self.client.current_relay_states["RELAY_LGT_BAY_1"])

    def test_handle_telemetry_switches(self):
        payload = {
            "switches": {
                "RELAY_LGT_BAY_1": True,
                "RELAY_AC_BAY_1": True,
                "RELAY_LGT_BAY_2": False
            }
        }
        self.client.handle_telemetry(payload)
        self.assertTrue(self.client.current_relay_states["RELAY_LGT_BAY_1"])
        self.assertTrue(self.client.current_relay_states["RELAY_AC_BAY_1"])
        self.assertFalse(self.client.current_relay_states["RELAY_LGT_BAY_2"])

    def test_handle_telemetry_zones(self):
        payload = {
            "zones": {
                "bay_3": {
                    "lights_state": True,
                    "ac_state": False,
                    "appliances": [
                        {"switch_id": "RELAY_LGT_BAY_3", "type": "light"},
                        {"switch_id": "RELAY_AC_BAY_3", "type": "ac"}
                    ]
                }
            }
        }
        self.client.handle_telemetry(payload)
        self.assertTrue(self.client.current_relay_states["RELAY_LGT_BAY_3"])
        self.assertFalse(self.client.current_relay_states["RELAY_AC_BAY_3"])


if __name__ == "__main__":
    unittest.main()
