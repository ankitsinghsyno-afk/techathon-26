"""
Plug-and-play Smart Switch & Relay Controller Interface.
Supports:
1. Virtual/Mock Relay (for hackathon testing & dashboard demonstration)
2. MQTT Publisher (for Shelly, Sonoff, Tasmota, ESP32, Zigbee2MQTT)
3. HTTP Webhook Relay (for Shelly REST API / IoT gateways)
"""
import time
import json
from typing import Dict, Any, List, Optional


class SwitchController:
    def __init__(self, mode: str = "mock", mqtt_broker: Optional[str] = None):
        self.mode = mode
        self.mqtt_broker = mqtt_broker
        # Tracks current physical/virtual state of each relay switch
        self.relay_states: Dict[str, bool] = {}
        # Audit log of switch toggles
        self.audit_log: List[Dict[str, Any]] = []

    def set_switch(self, switch_id: str, state: bool, reason: str = "") -> bool:
        """
        Sets a specific switch relay to ON (True) or OFF (False).
        """
        prev = self.relay_states.get(switch_id, False)
        self.relay_states[switch_id] = state

        record = {
            "timestamp": time.time(),
            "switch_id": switch_id,
            "state": "ON" if state else "OFF",
            "previous_state": "ON" if prev else "OFF",
            "reason": reason
        }
        self.audit_log.append(record)
        if len(self.audit_log) > 100:
            self.audit_log.pop(0)

        # Trigger hardware dispatch depending on mode
        if self.mode == "mqtt" and self.mqtt_broker:
            self._dispatch_mqtt(switch_id, state)
        elif self.mode == "http":
            self._dispatch_http(switch_id, state)

        return True

    def batch_update_zone(self, switches: List[str], state: bool, zone_name: str, reason: str = ""):
        for sw in switches:
            self.set_switch(sw, state, reason=f"[{zone_name}] {reason}")

    def _dispatch_mqtt(self, switch_id: str, state: bool):
        # Placeholder for paho-mqtt publish: topic=f"office/switches/{switch_id}/set" payload="ON"|"OFF"
        pass

    def _dispatch_http(self, switch_id: str, state: bool):
        # Placeholder for HTTP webhook: POST http://device-ip/relay/0
        pass

    def get_status(self) -> Dict[str, Any]:
        return {
            "mode": self.mode,
            "relays": self.relay_states,
            "recent_events": self.audit_log[-10:]
        }
