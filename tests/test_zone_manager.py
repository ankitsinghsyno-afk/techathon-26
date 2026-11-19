import pytest
import time
from src.zone_manager import is_point_in_polygon, ZoneManager
from src.models import PersonDetection


def test_is_point_in_polygon():
    # Square polygon from (0.1, 0.1) to (0.5, 0.5)
    polygon = [[0.1, 0.1], [0.5, 0.1], [0.5, 0.5], [0.1, 0.5]]

    # Point clearly inside
    assert is_point_in_polygon((0.3, 0.3), polygon) is True

    # Point clearly outside
    assert is_point_in_polygon((0.6, 0.3), polygon) is False
    assert is_point_in_polygon((0.0, 0.0), polygon) is False
    assert is_point_in_polygon((0.3, 0.7), polygon) is False


def test_zone_occupancy_and_debouncing():
    zm = ZoneManager("config/default_zones.json")
    assert "zone_alpha" in zm.zones
    assert "zone_beta" in zm.zones

    # Initially, all zones should be vacant and lights OFF
    summary = zm.get_summary()
    assert summary["zone_alpha"]["is_occupied"] is False
    assert summary["zone_alpha"]["lights_state"] is False

    # Simulate detecting a person inside zone_alpha
    # zone_alpha camera polygon is [0.05, 0.10] to [0.45, 0.48]
    person1 = PersonDetection(
        id=1,
        confidence=0.92,
        bbox=[100, 100, 200, 250],
        feet_coord=(0.20, 0.30)  # normalized coords inside zone_alpha
    )

    events = zm.update_occupancy([person1], frame_width=1, frame_height=1)
    assert len(events) > 0
    # Zone alpha should switch ON
    alpha_events = [e for e in events if e["zone_id"] == "zone_alpha"]
    assert len(alpha_events) == 1
    assert alpha_events[0]["action"] == "ON"
    assert zm.zones["zone_alpha"].lights_state is True
    assert zm.zones["zone_alpha"].current_occupancy == 1

    # In the next frame, person leaves (0 detections)
    # Since debounce is 8s, lights should STAY ON
    events_empty = zm.update_occupancy([], frame_width=1, frame_height=1)
    assert zm.zones["zone_alpha"].current_occupancy == 0
    assert zm.zones["zone_alpha"].lights_state is True  # still held ON due to debounce

    # Now artificially advance timestamp past debounce threshold (e.g. 10s)
    zm.zones["zone_alpha"].last_occupied_timestamp -= 10.0
    events_timeout = zm.update_occupancy([], frame_width=1, frame_height=1)

    alpha_off = [e for e in events_timeout if e["zone_id"] == "zone_alpha"]
    assert len(alpha_off) == 1
    assert alpha_off[0]["action"] == "OFF"
    assert zm.zones["zone_alpha"].lights_state is False
