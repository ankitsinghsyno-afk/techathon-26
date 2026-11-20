#!/usr/bin/env python3
"""
Raspberry Pi Edge Actuator & Sensor Client for Smart Office Energy Management.

Connects to the central Mac Vision/AI Server over WebSocket / REST.
- Actuator: Receives real-time zone switch commands and toggles physical Relays (Active-Low/High).
- Sensor Hub: Reads PIR Motion Sensors for non-camera zones (Conference Room & Manager Cabin)
  and pushes triggers back to the central server.
"""

import sys
import time
import json
import argparse
import threading
from typing import Dict, Any, Optional

try:
    import websocket
except ImportError:
    websocket = None

try:
    import requests
except ImportError:
    requests = None

# Try importing Raspberry Pi GPIO
try:
    import RPi.GPIO as GPIO
    HAS_GPIO = True
except (ImportError, RuntimeError):
    HAS_GPIO = False


# BCM GPIO Pin Configuration (Calibrated for standard 8-channel / 4-channel relay boards)
DEFAULT_RELAY_PINS = {
    # Workstation Bays (6th Floor Map)
    "RELAY_LGT_BAY_1": 17,  # Physical Pin 11
    "RELAY_AC_BAY_1": 27,   # Physical Pin 13
    "RELAY_LGT_BAY_2": 22,  # Physical Pin 15
    "RELAY_AC_BAY_2": 23,   # Physical Pin 16
    "RELAY_LGT_BAY_3": 24,  # Physical Pin 18
    "RELAY_AC_BAY_3": 25,   # Physical Pin 22
    "RELAY_LGT_BAY_4": 5,    # Physical Pin 29
    "RELAY_AC_BAY_4": 6,    # Physical Pin 31

    # Shared & Private Facilities
    "RELAY_LGT_CONF": 12,   # Physical Pin 32 (Conference Downlights)
    "RELAY_AC_CONF": 13,    # Physical Pin 33 (Conference AC)
    "RELAY_LGT_MGR": 16,    # Physical Pin 36 (Manager Cabin Light)
    "RELAY_AC_MGR": 26,     # Physical Pin 37 (Manager Cabin AC)
    "RELAY_LGT_SRV": 19,    # Physical Pin 35 (Server Room Light)
    "RELAY_AC_SRV": 20,     # Physical Pin 38 (Server Precision Cooling)
}

# Digital PIR Motion Sensors for privacy/no-camera zones
DEFAULT_PIR_PINS = {
    "conf_room": 21,        # Physical Pin 40 (Conference Room PIR Input)
    "manager_cabin": 4,     # Physical Pin 7  (Manager Cabin PIR Input)
}


class PiRelayClient:
    def __init__(
        self,
        server_url: str,
        active_low: bool = True,
        use_mock: bool = False,
        relay_pins: Optional[Dict[str, int]] = None,
        pir_pins: Optional[Dict[str, int]] = None,
    ):
        self.server_url = server_url.rstrip("/")
        self.active_low = active_low
        self.is_mock = use_mock or not HAS_GPIO
        self.relay_pins = relay_pins or DEFAULT_RELAY_PINS
        self.pir_pins = pir_pins or DEFAULT_PIR_PINS

        # Tracks current hardware pin output states
        self.current_relay_states: Dict[str, bool] = {}
        self.ws: Optional[Any] = None
        self.is_running = True

        self._setup_hardware()

    def _setup_hardware(self):
        """Initializes GPIO pins or prints mock status."""
        if self.is_mock:
            print("[INFO] Running in MOCK/SIMULATION Mode (No physical GPIO calls).")
            for sw_id in self.relay_pins:
                self.current_relay_states[sw_id] = False
            return

        print("[INFO] Initializing Raspberry Pi GPIO (BCM Mode)...")
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)

        # Setup Relay Outputs
        for sw_id, pin in self.relay_pins.items():
            GPIO.setup(pin, GPIO.OUT)
            # Default OFF: For Active-Low relay, OFF = HIGH. For Active-High, OFF = LOW.
            initial_val = GPIO.HIGH if self.active_low else GPIO.LOW
            GPIO.output(pin, initial_val)
            self.current_relay_states[sw_id] = False
            print(f"  -> Relay Output Configured: {sw_id} on BCM GPIO {pin}")

        # Setup PIR Sensor Inputs
        for zone_id, pin in self.pir_pins.items():
            GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
            print(f"  -> PIR Sensor Input Configured: {zone_id} on BCM GPIO {pin}")

    def set_relay(self, switch_id: str, state: bool):
        """Sets relay hardware pin to ON (True) or OFF (False)."""
        prev = self.current_relay_states.get(switch_id, None)
        if prev == state:
            return

        self.current_relay_states[switch_id] = state
        pin = self.relay_pins.get(switch_id)

        symbol = "💡 [ON] " if state else "⚫ [OFF]"
        print(f"[{time.strftime('%H:%M:%S')}] {symbol} Relay '{switch_id}' (GPIO {pin}) -> {'ON' if state else 'OFF'}")

        if not self.is_mock and pin is not None:
            # Active-low: ON = LOW, OFF = HIGH
            # Active-high: ON = HIGH, OFF = LOW
            if self.active_low:
                gpio_val = GPIO.LOW if state else GPIO.HIGH
            else:
                gpio_val = GPIO.HIGH if state else GPIO.LOW
            GPIO.output(pin, gpio_val)

    def handle_telemetry(self, data: Dict[str, Any]):
        """Processes telemetry payload from central Mac server."""
        # 1. Update from direct switch states if provided
        switches = data.get("switches", {})
        if switches:
            for sw_id, state in switches.items():
                if sw_id in self.relay_pins:
                    self.set_relay(sw_id, bool(state))
            return

        # 2. Or derive from zone appliances
        zones = data.get("zones", {})
        for zid, zdata in zones.items():
            lights_on = zdata.get("lights_state", False)
            ac_on = zdata.get("ac_state", False)
            for app in zdata.get("appliances", []):
                sw_id = app.get("switch_id")
                app_type = app.get("type")
                if not sw_id or sw_id not in self.relay_pins:
                    continue
                if app_type in ("light", "display", "socket"):
                    self.set_relay(sw_id, lights_on)
                elif app_type == "ac":
                    self.set_relay(sw_id, ac_on)

    def start_pir_monitor(self):
        """Background thread monitoring PIR motion sensor pins."""
        if self.is_mock:
            return

        def monitor_loop():
            last_states = {z: False for z in self.pir_pins}
            while self.is_running:
                for zone_id, pin in self.pir_pins.items():
                    current = bool(GPIO.input(pin))
                    if current != last_states[zone_id]:
                        last_states[zone_id] = current
                        if current:
                            print(f"[PIR MOTION] Sensor triggered in {zone_id}! Reporting to server...")
                            self.send_sensor_trigger(zone_id, motion=True)
                time.sleep(0.1)

        t = threading.Thread(target=monitor_loop, daemon=True)
        t.start()

    def send_sensor_trigger(self, zone_id: str, motion: bool = True):
        """Sends motion trigger event back to central Mac server."""
        payload = json.dumps({"action": "sensor_trigger", "zone_id": zone_id, "motion": motion})
        if self.ws and getattr(self.ws, "sock", None) and self.ws.sock.connected:
            try:
                self.ws.send(payload)
                return
            except Exception as e:
                print(f"[WARN] Failed to send over WebSocket: {e}")

        # Fallback to HTTP POST
        if requests:
            try:
                http_url = self.server_url.replace("ws://", "http://").replace("wss://", "https://")
                requests.post(f"{http_url}/api/sensor_trigger", json={"zone_id": zone_id, "motion": motion}, timeout=1.0)
            except Exception as e:
                print(f"[WARN] Failed to send HTTP sensor trigger: {e}")

    def run(self):
        """Main client loop connecting to Mac server over WebSocket with auto-reconnect."""
        ws_url = self.server_url.replace("http://", "ws://").replace("https://", "wss://")
        if not ws_url.endswith("/ws"):
            ws_url = f"{ws_url}/ws"

        print(f"=======================================================")
        print(f"  Smart Office Edge Actuator - Raspberry Pi Client")
        print(f"  Target Central Server: {ws_url}")
        print(f"  Hardware Relay Mode:  {'ACTIVE-LOW' if self.active_low else 'ACTIVE-HIGH'}")
        print(f"  Active GPIO Backend:  {'MOCK' if self.is_mock else 'RPi.GPIO (Physical)'}")
        print(f"=======================================================")

        self.start_pir_monitor()

        while self.is_running:
            try:
                if websocket is None:
                    print("[ERROR] 'websocket-client' package not found. Run: pip install websocket-client")
                    time.sleep(5)
                    continue

                print(f"[CONNECT] Attempting connection to central Mac: {ws_url} ...")

                def on_message(ws, message):
                    try:
                        data = json.loads(message)
                        self.handle_telemetry(data)
                    except Exception as err:
                        pass

                def on_error(ws, error):
                    print(f"[ERROR] Connection error: {error}")

                def on_close(ws, close_status_code, close_msg):
                    print(f"[CLOSED] Disconnected from server. Reconnecting in 3s...")

                def on_open(ws):
                    print(f"[CONNECTED] Successfully connected to central server! Listening for relay commands...")

                self.ws = websocket.WebSocketApp(
                    ws_url,
                    on_open=on_open,
                    on_message=on_message,
                    on_error=on_error,
                    on_close=on_close
                )
                self.ws.run_forever()

            except KeyboardInterrupt:
                print("\n[STOP] Shutting down client...")
                self.is_running = False
                break
            except Exception as e:
                print(f"[EXCEPTION] Loop error: {e}")

            time.sleep(3)

        self.cleanup()

    def cleanup(self):
        """Safely turns off all relays and cleans up GPIO pins."""
        print("[CLEANUP] Turning off all physical relays...")
        for sw_id in self.relay_pins:
            self.set_relay(sw_id, False)
        if not self.is_mock and HAS_GPIO:
            GPIO.cleanup()
        print("[CLEANUP] GPIO cleanup complete.")


def main():
    parser = argparse.ArgumentParser(description="Raspberry Pi Edge Actuator for Smart Office Energy")
    parser.add_argument("--server", type=str, default="http://localhost:8000", help="Central Mac server URL (e.g. http://192.168.1.100:8000)")
    parser.add_argument("--active-high", action="store_true", help="Set if relay board is Active-High (default is Active-Low)")
    parser.add_argument("--mock", action="store_true", help="Force mock/simulation mode without GPIO")
    args = parser.parse_args()

    client = PiRelayClient(
        server_url=args.server,
        active_low=not args.active_high,
        use_mock=args.mock
    )
    client.run()


if __name__ == "__main__":
    main()
