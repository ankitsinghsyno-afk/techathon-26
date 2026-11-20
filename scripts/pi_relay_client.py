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


# BCM GPIO Pin Configuration calibrated for Breadboard LED Grid + 2-Channel Relay + Magnetic Door
# 1. Breadboard Floor Light LEDs (Active HIGH: HIGH = ON, LOW = OFF)
DEFAULT_BREADBOARD_LEDS = {
    "bay_1": 17,          # Physical Pin 11 -> Bay 1 LED
    "bay_2": 22,          # Physical Pin 15 -> Bay 2 LED
    "bay_3": 24,          # Physical Pin 18 -> Bay 3 LED
    "bay_4": 5,           # Physical Pin 29 -> Bay 4 LED
    "conf_room": 12,      # Physical Pin 32 -> Conference Room LED
    "cabin_1": 27,        # Physical Pin 13 -> Executive Cabin 1 LED
    "manager_cabin": 16,  # Physical Pin 36 -> Manager Cabin LED
    "server_room": 20,    # Physical Pin 38 -> Server Room LED (Always ON)
}

# 2. 2-Channel Relay Module (Active LOW: LOW = ON, HIGH = OFF)
# Mapped to Bay 1 & Bay 2 for audible relay click demo
DEFAULT_RELAY_PINS = {
    "RELAY_LGT_BAY_1": 23,  # Physical Pin 16 (IN1 on 2-ch relay)
    "RELAY_LGT_BAY_2": 25,  # Physical Pin 22 (IN2 on 2-ch relay)
}

# 3. Sensors: Magnetic Door Switch (White contact sensor) & PIR Motion
DEFAULT_SENSOR_PINS = {
    "conf_room": 21,        # Physical Pin 40 -> White Magnetic Door Switch (or PIR)
    "manager_cabin": 4,     # Physical Pin 7  -> PIR / Motion Sensor
}


class PiRelayClient:
    def __init__(
        self,
        server_url: str,
        active_low_relay: bool = True,
        use_mock: bool = False,
        no_resistor_pwm: bool = False,
        pwm_duty: int = 15,
        led_pins: Optional[Dict[str, int]] = None,
        relay_pins: Optional[Dict[str, int]] = None,
        sensor_pins: Optional[Dict[str, int]] = None,
    ):
        self.server_url = server_url.rstrip("/")
        self.active_low_relay = active_low_relay
        self.is_mock = use_mock or not HAS_GPIO
        self.no_resistor_pwm = no_resistor_pwm
        self.pwm_duty = max(1, min(pwm_duty, 25))  # Safe duty cycle cap (max 25%)
        self.led_pins = led_pins or DEFAULT_BREADBOARD_LEDS
        self.relay_pins = relay_pins or DEFAULT_RELAY_PINS
        self.sensor_pins = sensor_pins or DEFAULT_SENSOR_PINS

        # Tracks current hardware output states
        self.current_led_states: Dict[str, bool] = {}
        self.current_relay_states: Dict[str, bool] = {}
        self.pwm_instances: Dict[str, Any] = {}
        self.ws: Optional[Any] = None
        self.is_running = True

        self._setup_hardware()

    def _setup_hardware(self):
        """Initializes GPIO pins or prints mock status."""
        if self.is_mock:
            print("[INFO] Running in MOCK/SIMULATION Mode (No physical GPIO calls).")
            for zid in self.led_pins:
                self.current_led_states[zid] = False
            for sw_id in self.relay_pins:
                self.current_relay_states[sw_id] = False
            return

        print("[INFO] Initializing Raspberry Pi GPIO (BCM Mode)...")
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)

        # 1. Setup Breadboard LEDs (Active HIGH)
        for zid, pin in self.led_pins.items():
            GPIO.setup(pin, GPIO.OUT)
            if self.no_resistor_pwm:
                # 1000 Hz PWM restricts average current safely to ~1-2 mA without resistors
                pwm = GPIO.PWM(pin, 1000)
                pwm.start(0)
                self.pwm_instances[zid] = pwm
            else:
                GPIO.output(pin, GPIO.LOW)  # OFF
            self.current_led_states[zid] = False
            mode_str = f"PWM {self.pwm_duty}% Current-Limited" if self.no_resistor_pwm else "Standard 3.3V"
            print(f"  -> Breadboard LED: {zid:14s} on BCM GPIO {pin} (Pin {self._get_phys_pin(pin)}) [{mode_str}]")

        # 2. Setup 2-Channel Relay Module (Active LOW)
        for sw_id, pin in self.relay_pins.items():
            GPIO.setup(pin, GPIO.OUT)
            initial_val = GPIO.HIGH if self.active_low_relay else GPIO.LOW
            GPIO.output(pin, initial_val)  # OFF
            self.current_relay_states[sw_id] = False
            print(f"  -> Physical Relay: {sw_id:14s} on BCM GPIO {pin} (Pin {self._get_phys_pin(pin)})")

        # 3. Setup Sensors (Pull-up for door reed switch, pull-down for PIR)
        for zone_id, pin in self.sensor_pins.items():
            # Pull-up for magnetic door contact switch (Pin pulls LOW when magnet closes switch)
            GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
            print(f"  -> Sensor Input:  {zone_id:14s} on BCM GPIO {pin} (Pin {self._get_phys_pin(pin)})")

    def _get_phys_pin(self, bcm: int) -> str:
        bcm_to_phys = {
            2: "3", 3: "5", 4: "7", 14: "8", 15: "10", 17: "11", 18: "12",
            27: "13", 22: "15", 23: "16", 24: "18", 10: "19", 9: "21", 25: "22",
            11: "23", 8: "24", 7: "26", 5: "29", 6: "31", 12: "32", 13: "33",
            19: "35", 16: "36", 26: "37", 20: "38", 21: "40"
        }
        return bcm_to_phys.get(bcm, "?")

    def set_led(self, zone_id: str, state: bool):
        """Sets breadboard LED pin to ON (True) or OFF (False)."""
        prev = self.current_led_states.get(zone_id, None)
        if prev == state:
            return

        self.current_led_states[zone_id] = state
        pin = self.led_pins.get(zone_id)
        symbol = "💡 [LED ON] " if state else "⚫ [LED OFF]"
        print(f"[{time.strftime('%H:%M:%S')}] {symbol} Zone '{zone_id}' (GPIO {pin}) -> {'ON' if state else 'OFF'}")

        if not self.is_mock and pin is not None:
            if self.no_resistor_pwm and zone_id in self.pwm_instances:
                duty = self.pwm_duty if state else 0
                self.pwm_instances[zone_id].ChangeDutyCycle(duty)
            else:
                GPIO.output(pin, GPIO.HIGH if state else GPIO.LOW)

    def set_relay(self, switch_id: str, state: bool):
        """Sets relay hardware pin to ON (True) or OFF (False)."""
        prev = self.current_relay_states.get(switch_id, None)
        if prev == state:
            return

        self.current_relay_states[switch_id] = state
        pin = self.relay_pins.get(switch_id)
        symbol = "⚡ [RELAY ON] " if state else "🔌 [RELAY OFF]"
        print(f"[{time.strftime('%H:%M:%S')}] {symbol} Relay '{switch_id}' (GPIO {pin}) -> {'ON' if state else 'OFF'}")

        if not self.is_mock and pin is not None:
            if self.active_low_relay:
                gpio_val = GPIO.LOW if state else GPIO.HIGH
            else:
                gpio_val = GPIO.HIGH if state else GPIO.LOW
            GPIO.output(pin, gpio_val)

    def handle_telemetry(self, data: Dict[str, Any]):
        """Processes telemetry payload from central Mac server."""
        zones = data.get("zones", {})
        for zid, zdata in zones.items():
            lights_on = bool(zdata.get("lights_state", False))

            # 1. Update breadboard LED for this zone
            if zid in self.led_pins:
                self.set_led(zid, lights_on)

            # 2. Update paired physical relay for Bay 1 & Bay 2
            if zid == "bay_1" and "RELAY_LGT_BAY_1" in self.relay_pins:
                self.set_relay("RELAY_LGT_BAY_1", lights_on)
            elif zid == "bay_2" and "RELAY_LGT_BAY_2" in self.relay_pins:
                self.set_relay("RELAY_LGT_BAY_2", lights_on)

        # Also support direct switches payload
        switches = data.get("switches", {})
        for sw_id, state in switches.items():
            if sw_id in self.relay_pins:
                self.set_relay(sw_id, bool(state))

    def start_sensor_monitor(self):
        """Background thread monitoring magnetic door switch and PIR motion sensor pins."""
        if self.is_mock:
            return

        def monitor_loop():
            last_states = {z: None for z in self.sensor_pins}
            while self.is_running:
                for zone_id, pin in self.sensor_pins.items():
                    # For pull-up door switch: 1 = Open/Triggered, 0 = Closed/Idle
                    raw_val = GPIO.input(pin)
                    # Trigger condition:
                    # Door sensor: High (1) means door opened
                    # PIR sensor: High (1) means motion detected
                    is_triggered = (raw_val == GPIO.HIGH)

                    if last_states[zone_id] != is_triggered:
                        last_states[zone_id] = is_triggered
                        if is_triggered:
                            print(f"[SENSOR EVENT] Presence/Door triggered in '{zone_id}'! Notifying central Mac...")
                            self.send_sensor_trigger(zone_id, motion=True)
                time.sleep(0.15)

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
        print(f"  Hardware Relay Mode:  {'ACTIVE-LOW' if self.active_low_relay else 'ACTIVE-HIGH'}")
        print(f"  Active GPIO Backend:  {'MOCK' if self.is_mock else 'RPi.GPIO (Physical)'}")
        print(f"=======================================================")

        self.start_sensor_monitor()

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
        """Safely turns off all relays, LEDs, and cleans up GPIO pins."""
        print("[CLEANUP] Turning off all physical LEDs and relays...")
        for zid in self.led_pins:
            self.set_led(zid, False)
        for pwm in self.pwm_instances.values():
            try:
                pwm.stop()
            except Exception:
                pass
        for sw_id in self.relay_pins:
            self.set_relay(sw_id, False)
        if not self.is_mock and HAS_GPIO:
            GPIO.cleanup()
        print("[CLEANUP] GPIO cleanup complete.")


def main():
    parser = argparse.ArgumentParser(description="Raspberry Pi Edge Actuator for Smart Office Energy")
    parser.add_argument("--server", type=str, default="http://localhost:8000", help="Central Mac server URL (e.g. http://192.168.1.100:8000)")
    parser.add_argument("--active-high-relay", action="store_true", help="Set if relay board is Active-High (default is Active-Low)")
    parser.add_argument("--mock", action="store_true", help="Force mock/simulation mode without GPIO")
    parser.add_argument("--no-resistor-pwm", action="store_true", help="Enables 1000Hz PWM current limiting (15%% duty cycle) for bare LEDs without resistors")
    parser.add_argument("--pwm-duty", type=int, default=15, help="PWM duty cycle percentage (1-25) when --no-resistor-pwm is enabled")
    args = parser.parse_args()

    client = PiRelayClient(
        server_url=args.server,
        active_low_relay=not args.active_high_relay,
        use_mock=args.mock,
        no_resistor_pwm=args.no_resistor_pwm,
        pwm_duty=args.pwm_duty
    )
    client.run()


if __name__ == "__main__":
    main()
