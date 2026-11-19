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
    assert "bay_1" in zm.zones
    assert "bay_2" in zm.zones

    # Initially, all zones should be vacant and lights OFF
    summary = zm.get_summary()
    assert summary["bay_1"]["is_occupied"] is False
    assert summary["bay_1"]["lights_state"] is False

    # Simulate detecting a person inside bay_1
    # bay_1 camera polygon is [0.05, 0.16] to [0.72, 0.28]
    person1 = PersonDetection(
        id=1,
        confidence=0.92,
        bbox=[100, 100, 200, 250],
        feet_coord=(0.20, 0.20)  # normalized coords inside bay_1
    )

    events = zm.update_occupancy([person1], frame_width=1, frame_height=1)
    assert len(events) > 0
    # Bay 1 should switch ON
    b1_events = [e for e in events if e["zone_id"] == "bay_1"]
    assert len(b1_events) == 1
    assert b1_events[0]["action"] == "ON"
    assert zm.zones["bay_1"].lights_state is True
    assert zm.zones["bay_1"].current_occupancy == 1

    # In the next frame, person leaves (0 detections)
    # Since debounce is 8s, lights should STAY ON
    events_empty = zm.update_occupancy([], frame_width=1, frame_height=1)
    assert zm.zones["bay_1"].current_occupancy == 0
    assert zm.zones["bay_1"].lights_state is True  # still held ON due to debounce

    # Now artificially advance timestamp past debounce threshold (e.g. 10s)
    zm.zones["bay_1"].last_occupied_timestamp -= 10.0
    events_timeout = zm.update_occupancy([], frame_width=1, frame_height=1)

    b1_off = [e for e in events_timeout if e["zone_id"] == "bay_1"]
    assert len(b1_off) == 1
    assert b1_off[0]["action"] == "OFF"
    assert zm.zones["bay_1"].lights_state is False
