import unittest
from scripts.pi_relay_client import PiRelayClient


class TestPiRelayClient(unittest.TestCase):
    def setUp(self):
        self.client = PiRelayClient("http://127.0.0.1:8000", use_mock=True)

    def tearDown(self):
        self.client.cleanup()

    def test_initial_states(self):
        for zid in self.client.led_pins:
            self.assertFalse(self.client.current_led_states[zid])
        for sw_id in self.client.relay_pins:
            self.assertFalse(self.client.current_relay_states[sw_id])

    def test_set_led_and_relay(self):
        self.client.set_led("bay_1", True)
        self.assertTrue(self.client.current_led_states["bay_1"])
        self.client.set_led("bay_1", False)
        self.assertFalse(self.client.current_led_states["bay_1"])

        self.client.set_relay("RELAY_LGT_BAY_1", True)
        self.assertTrue(self.client.current_relay_states["RELAY_LGT_BAY_1"])
        self.client.set_relay("RELAY_LGT_BAY_1", False)
        self.assertFalse(self.client.current_relay_states["RELAY_LGT_BAY_1"])

    def test_handle_telemetry_zones(self):
        payload = {
            "zones": {
                "bay_1": {
                    "lights_state": True,
                    "ac_state": True
                },
                "bay_2": {
                    "lights_state": False,
                    "ac_state": False
                }
            }
        }
        self.client.handle_telemetry(payload)
        # Bay 1 LED and Relay should be ON
        self.assertTrue(self.client.current_led_states["bay_1"])
        self.assertTrue(self.client.current_relay_states["RELAY_LGT_BAY_1"])

        # Bay 2 LED and Relay should be OFF
        self.assertFalse(self.client.current_led_states["bay_2"])
        self.assertFalse(self.client.current_relay_states["RELAY_LGT_BAY_2"])


if __name__ == "__main__":
    unittest.main()
