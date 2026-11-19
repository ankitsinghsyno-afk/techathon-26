"""
Zone management and point-in-polygon mapping for floor occupancy.
"""
import json
import time
from typing import List, Dict, Any, Tuple, Optional
from src.models import Zone, Appliance, PersonDetection


def is_point_in_polygon(point: Tuple[float, float], polygon: List[List[float]]) -> bool:
    """
    Ray-casting algorithm to test whether a 2D point is inside a polygon.
    Works with both normalized (0.0 - 1.0) and pixel coordinates.
    """
    x, y = point
    inside = False
    n = len(polygon)
    if n < 3:
        return False

    p1x, p1y = polygon[0]
    for i in range(1, n + 1):
        p2x, p2y = polygon[i % n]
        if min(p1y, p2y) < y <= max(p1y, p2y):
            if x <= max(p1x, p2x):
                if p1y != p2y:
                    xinters = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                if p1x == p2x or x <= xinters:
                    inside = not inside
        p1x, p1y = p2x, p2y

    return inside


class ZoneManager:
    def __init__(self, config_path: str):
        self.config_path = config_path
        self.floor_name = "Smart Office Floor"
        self.canvas_size = {"width": 800, "height": 600}
        self.zones: Dict[str, Zone] = {}
        self.load_config(config_path)

    def load_config(self, config_path: str):
        with open(config_path, "r") as f:
            data = json.load(f)

        self.floor_name = data.get("floor_name", "Smart Office Floor")
        self.canvas_size = data.get("canvas_size", {"width": 800, "height": 600})
        self.zones = {}

        now = time.time()
        for zd in data.get("zones", []):
            appliances = [
                Appliance(
                    name=a["name"],
                    type=a["type"],
                    wattage=float(a["wattage"]),
                    switch_id=a["switch_id"],
                    is_active=False
                )
                for a in zd.get("appliances", [])
            ]
            zone = Zone(
                id=zd["id"],
                name=zd["name"],
                department=zd.get("department", "General"),
                camera_polygon=zd["camera_polygon"],
                floor_polygon=zd["floor_polygon"],
                appliances=appliances,
                debounce_seconds=float(zd.get("debounce_seconds", 8.0)),
                color=zd.get("color", "#3B82F6"),
                last_occupied_timestamp=0.0
            )
            self.zones[zone.id] = zone

    def update_occupancy(
        self,
        detections: List[PersonDetection],
        frame_width: int = 1,
        frame_height: int = 1
    ) -> List[Dict[str, Any]]:
        """
        Maps detections to zones using feet contact coordinates.
        Applies debounce policy and triggers switch events on transition.
        Returns list of switch action events.
        """
        now = time.time()
        # Reset current occupancy count for this frame
        zone_counts = {zid: 0 for zid in self.zones}

        # Check each person's ground coordinate against zone camera polygons
        for person in detections:
            fx, fy = person.feet_coord
            # Normalize feet coordinates if received in pixel coordinates
            norm_x = fx / frame_width if frame_width > 1 else fx
            norm_y = fy / frame_height if frame_height > 1 else fy

            assigned_zone = None
            for zid, zone in self.zones.items():
                if is_point_in_polygon((norm_x, norm_y), zone.camera_polygon):
                    assigned_zone = zid
                    zone_counts[zid] += 1
                    break
            person.zone_id = assigned_zone

        events = []

        # Update zone state machines
        for zid, zone in self.zones.items():
            occupancy = zone_counts[zid]
            zone.current_occupancy = occupancy
            prev_lights_state = zone.lights_state

            if occupancy > 0:
                zone.last_occupied_timestamp = now
                zone.is_occupied = True
                zone.lights_state = True
                zone.ac_state = True
            else:
                # No one detected in this frame
                time_since_last_seen = now - zone.last_occupied_timestamp
                if time_since_last_seen >= zone.debounce_seconds:
                    zone.is_occupied = False
                    zone.lights_state = False
                    zone.ac_state = False
                else:
                    # Still within debounce hold period - keep lights active
                    zone.is_occupied = False  # current occupancy is 0
                    zone.lights_state = True  # but hold light active

            # Update appliances state
            for app in zone.appliances:
                if app.type in ("light", "display", "socket"):
                    app.is_active = zone.lights_state
                elif app.type == "ac":
                    app.is_active = zone.ac_state

            # Detect state transition
            if prev_lights_state != zone.lights_state:
                new_state = "ON" if zone.lights_state else "OFF"
                events.append({
                    "timestamp": now,
                    "zone_id": zid,
                    "zone_name": zone.name,
                    "action": new_state,
                    "reason": f"Occupancy={occupancy}, Debounce={zone.debounce_seconds}s",
                    "switches": [app.switch_id for app in zone.appliances]
                })

        return events

    def get_summary(self) -> Dict[str, Any]:
        return {
            zid: {
                "id": z.id,
                "name": z.name,
                "department": z.department,
                "occupancy": z.current_occupancy,
                "is_occupied": z.is_occupied,
                "lights_state": z.lights_state,
                "ac_state": z.ac_state,
                "appliances": [a.model_dump() for a in z.appliances],
                "color": z.color,
                "camera_polygon": z.camera_polygon,
                "floor_polygon": z.floor_polygon,
                "debounce_seconds": z.debounce_seconds
            }
            for zid, z in self.zones.items()
        }
