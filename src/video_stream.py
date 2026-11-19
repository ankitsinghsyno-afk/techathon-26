"""
Video stream capture and realistic 6th Floor IT office simulation engine.
Matches user floor plan:
- 4 Main Workstation Bays (Bay 1, 2, 3, 4 with 10 seats P1-P10 each + HVAC)
- Top: Cabin 1, Cabin 2, Cabin 3
- Right: Server Room, Manager Cabin (No Camera / IoT Sensor), Entry Gate
- Bottom: Conference Room (TV, Split AC, No Camera / IoT Sensor)
- Camera Position: Bottom-Right looking diagonally across the bays
"""
import os
import time
import math
import random
from typing import Optional, Tuple, List, Dict, Any

# Ensure macOS AVFoundation authorization warning does not freeze secondary threads
os.environ.setdefault("OPENCV_AVFOUNDATION_SKIP_AUTH", "1")

import numpy as np
import cv2


class SyntheticPerson:
    def __init__(self, pid: int, start_x: float, start_y: float, target_zone: str):
        self.pid = pid
        self.x = start_x
        self.y = start_y
        self.target_x = start_x
        self.target_y = start_y
        self.target_zone = target_zone
        self.speed = random.uniform(1.2, 2.5)
        self.state = "working"  # "working", "walking"
        self.last_decision = time.time()

    def update(self, bounds: Tuple[int, int], waypoints: Dict[str, Tuple[float, float]]):
        now = time.time()
        # Periodically shift slightly around their desk or walk to conference/corridor
        if now - self.last_decision > random.uniform(10.0, 25.0):
            self.last_decision = now
            if random.random() < 0.25:
                # Visit conference room or wander
                dest_key = random.choice(list(waypoints.keys()))
                tx, ty = waypoints[dest_key]
                self.target_x = max(60, min(bounds[0] - 60, tx + random.uniform(-40, 40)))
                self.target_y = max(60, min(bounds[1] - 60, ty + random.uniform(-25, 25)))
                self.target_zone = dest_key
                self.state = "walking"
            else:
                # Small movement at desk
                tx, ty = waypoints.get(self.target_zone, (self.x, self.y))
                self.target_x = tx + random.uniform(-30, 30)
                self.target_y = ty + random.uniform(-15, 15)
                self.state = "working"

        dx = self.target_x - self.x
        dy = self.target_y - self.y
        dist = math.hypot(dx, dy)
        if dist > 3.0:
            self.x += (dx / dist) * self.speed
            self.y += (dy / dist) * self.speed
        else:
            self.state = "working"


class VideoStreamHandler:
    def __init__(self, source: str = "synthetic", width: int = 800, height: int = 900):
        self.source = source
        self.width = width
        self.height = height
        self.cap = None
        self.is_synthetic = (source.lower() == "synthetic")

        # Floor Plan Waypoints matching the 6th floor layout
        self.waypoints = {
            "bay_1": (300.0, 210.0),
            "bay_2": (300.0, 350.0),
            "bay_3": (300.0, 490.0),
            "bay_4": (300.0, 630.0),
            "conf_room": (340.0, 800.0),
            "manager_cabin": (675.0, 335.0),
            "cabin_1": (150.0, 85.0),
            "cabin_2": (400.0, 85.0),
            "cabin_3": (650.0, 85.0)
        }
        self.synthetic_people: List[SyntheticPerson] = []
        self._init_source()

    def _init_source(self):
        if self.is_synthetic:
            # Default: Team 1 working in Bay 1 (solving user's single team working statement)
            self.synthetic_people = [
                SyntheticPerson(1, 150, 190, "bay_1"),  # P1
                SyntheticPerson(2, 230, 190, "bay_1"),  # P2
                SyntheticPerson(3, 310, 190, "bay_1"),  # P3
                SyntheticPerson(4, 230, 240, "bay_1"),  # P7
                SyntheticPerson(5, 390, 240, "bay_1"),  # P9
            ]
        else:
            # Try opening camera (webcam index or RTSP / iPhone HTTP stream)
            try:
                if self.source.isdigit():
                    src_val = int(self.source)
                    self.cap = cv2.VideoCapture(src_val, cv2.CAP_AVFOUNDATION)
                    if not self.cap.isOpened():
                        self.cap = cv2.VideoCapture(src_val)
                else:
                    self.cap = cv2.VideoCapture(self.source)

                if self.cap is None or not self.cap.isOpened():
                    print(f"⚠️ Notice: Camera source '{self.source}' could not be accessed. Reverting to 6th Floor simulation.")
                    self.is_synthetic = True
                    self.cap = None
                    self._init_source()
                    return

                self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
                self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
                self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

                ret, _ = self.cap.read()
                if not ret:
                    print(f"⚠️ Notice: Camera '{self.source}' opened but read failed. Reverting to simulation.")
                    self.cap.release()
                    self.cap = None
                    self.is_synthetic = True
                    self._init_source()
            except Exception as e:
                print(f"Error opening camera source '{self.source}': {e}. Reverting to simulation.")
                self.is_synthetic = True
                self.cap = None
                self._init_source()

    def read_frame(self) -> Tuple[bool, Optional[np.ndarray], List[Dict[str, Any]]]:
        if self.is_synthetic or self.cap is None or not self.cap.isOpened():
            frame, gt_boxes = self._generate_synthetic_frame()
            return True, frame, gt_boxes

        ret, frame = self.cap.read()
        if not ret:
            if isinstance(self.source, str) and not self.source.isdigit():
                self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                ret, frame = self.cap.read()
            if not ret:
                frame, gt_boxes = self._generate_synthetic_frame()
                return True, frame, gt_boxes

        frame = cv2.resize(frame, (self.width, self.height))
        return True, frame, []

    def _generate_synthetic_frame(self) -> Tuple[np.ndarray, List[Dict[str, Any]]]:
        """
        Renders the architectural layout matching the user's hand-drawn 6th Floor Map.
        """
        frame = np.full((self.height, self.width, 3), (18, 24, 33), dtype=np.uint8)

        # Draw grid
        for x in range(0, self.width, 40):
            cv2.line(frame, (x, 0), (x, self.height), (26, 34, 46), 1)
        for y in range(0, self.height, 40):
            cv2.line(frame, (0, y), (self.width, y), (26, 34, 46), 1)

        # 1. Top Cabins (Cabin 1, Cabin 2, Cabin 3)
        cabins = [
            (40, 30, 220, 105, "Cabin 1"),
            (280, 30, 240, 105, "Cabin 2"),
            (540, 30, 220, 105, "Cabin 3")
        ]
        for cx, cy, cw, ch, cname in cabins:
            cv2.rectangle(frame, (cx, cy), (cx + cw, cy + ch), (33, 44, 58), -1)
            cv2.rectangle(frame, (cx, cy), (cx + cw, cy + ch), (70, 85, 105), 1)
            cv2.putText(frame, cname, (cx + 15, cy + 30), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (180, 200, 220), 1)

        # 2. Right Side Rooms: Server Room & Manager Cabin
        # Server Room
        cv2.rectangle(frame, (590, 160), (760, 255), (38, 48, 64), -1)
        cv2.rectangle(frame, (590, 160), (760, 255), (100, 115, 135), 1)
        cv2.putText(frame, "Server Room", (610, 200), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (140, 165, 190), 1)
        cv2.putText(frame, "[24/7 Precision AC]", (605, 220), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (100, 130, 160), 1)

        # Manager Cabin
        cv2.rectangle(frame, (590, 280), (760, 390), (33, 44, 58), -1)
        cv2.rectangle(frame, (590, 280), (760, 390), (70, 85, 105), 1)
        cv2.putText(frame, "Manager Cabin", (615, 325), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (180, 200, 220), 1)
        cv2.putText(frame, "(No Cam - IoT PIR)", (610, 345), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (120, 180, 220), 1)

        # Entry Gate & Camera
        cv2.rectangle(frame, (620, 640), (760, 710), (45, 55, 72), -1)
        cv2.rectangle(frame, (620, 640), (760, 710), (16, 185, 129), 2)
        cv2.putText(frame, "ENTRY GATE", (640, 675), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (52, 211, 153), 1)

        # Camera Marker at Bottom-Right
        cam_x, cam_y = 700, 750
        cv2.circle(frame, (cam_x, cam_y), 16, (14, 165, 233), -1)
        cv2.circle(frame, (cam_x, cam_y), 20, (56, 189, 248), 2)
        cv2.putText(frame, "CAMERA", (cam_x - 22, cam_y + 35), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (56, 189, 248), 1)
        # FOV cone lines
        cv2.line(frame, (cam_x, cam_y), (40, 160), (56, 189, 248), 1)
        cv2.line(frame, (cam_x, cam_y), (40, 680), (56, 189, 248), 1)

        # 3. Workstation Bays 1, 2, 3, 4 with 10 Desks each (P1-P5 & P6-P10)
        bays_info = [
            (40, 155, 530, 115, "Bay 1 (Team 1)", 200),
            (40, 295, 530, 115, "Bay 2 (Team 2)", 340),
            (40, 435, 530, 115, "Bay 3 (Product)", 480),
            (40, 575, 530, 115, "Bay 4 (QA & Ops)", 620)
        ]
        for bx, by, bw, bh, btitle, hvac_y in bays_info:
            # Bay perimeter outline
            cv2.rectangle(frame, (bx, by), (bx + bw, by + bh), (40, 52, 68), 1)
            cv2.putText(frame, btitle, (bx + 15, by + 20), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (160, 185, 210), 1)

            # Central HVAC Duct label box
            cv2.rectangle(frame, (bx + 200, by + 8), (bx + 330, by + 32), (30, 41, 59), -1)
            cv2.rectangle(frame, (bx + 200, by + 8), (bx + 330, by + 32), (6, 182, 212), 1)
            cv2.putText(frame, "HVAC AC", (bx + 235, by + 25), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (6, 182, 212), 1)

            # Row 1 Desks: P1 to P5
            desk_w, desk_h = 75, 28
            for i in range(5):
                dx = bx + 35 + i * 95
                dy = by + 40
                cv2.rectangle(frame, (dx, dy), (dx + desk_w, dy + desk_h), (50, 65, 85), -1)
                cv2.rectangle(frame, (dx, dy), (dx + desk_w, dy + desk_h), (80, 100, 125), 1)
                cv2.putText(frame, f"P{i+1}", (dx + 28, dy + 18), cv2.FONT_HERSHEY_SIMPLEX, 0.32, (200, 215, 230), 1)

            # Row 2 Desks: P6 to P10
            for i in range(5):
                dx = bx + 35 + i * 95
                dy = by + 75
                cv2.rectangle(frame, (dx, dy), (dx + desk_w, dy + desk_h), (50, 65, 85), -1)
                cv2.rectangle(frame, (dx, dy), (dx + desk_w, dy + desk_h), (80, 100, 125), 1)
                cv2.putText(frame, f"P{i+6}", (dx + 28, dy + 18), cv2.FONT_HERSHEY_SIMPLEX, 0.32, (200, 215, 230), 1)

        # 4. Conference Room at bottom
        cv2.rectangle(frame, (40, 720), (640, 870), (33, 44, 58), -1)
        cv2.rectangle(frame, (40, 720), (640, 870), (70, 85, 105), 1)
        cv2.putText(frame, "Conference Room (TV, Split AC, No Camera)", (60, 755), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (220, 230, 242), 1)
        # Conference table
        cv2.ellipse(frame, (340, 805), (140, 35), 0, 0, 360, (50, 65, 85), -1)
        cv2.ellipse(frame, (340, 805), (140, 35), 0, 0, 360, (100, 120, 145), 1)
        # TV Wall display
        cv2.rectangle(frame, (50, 785), (65, 835), (245, 158, 11), -1)
        cv2.putText(frame, "TV", (70, 815), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (245, 158, 11), 1)

        # Draw Synthetic Occupants
        gt_detections = []
        for person in self.synthetic_people:
            person.update((self.width, self.height), self.waypoints)
            px = int(person.x)
            py = int(person.y)

            w_person = 28
            h_person = 56
            x1 = px - w_person // 2
            y1 = py - h_person
            x2 = px + w_person // 2
            y2 = py

            # Shadow + Torso + Head
            cv2.ellipse(frame, (px, py), (14, 7), 0, 0, 360, (10, 12, 16), -1)
            cv2.rectangle(frame, (x1 + 3, y1 + 16), (x2 - 3, y2 - 4), (59, 130, 246), -1)
            cv2.circle(frame, (px, y1 + 9), 9, (230, 190, 155), -1)

            gt_detections.append({
                "id": person.pid,
                "bbox": [x1, y1, x2, y2],
                "feet_coord": (float(px), float(y2)),
                "confidence": 0.94
            })

        return frame, gt_detections

    def trigger_scenario(self, scenario_name: str):
        """
        Scenarios customized for user's 6th Floor Map:
        - 'only_bay_1': Only Team 1 in Bay 1 (Solves user's exact problem statement!)
        - 'only_bay_2': Only Team 2 in Bay 2
        - 'bays_1_and_3': Bay 1 & Bay 3 occupied
        - 'conference_meeting': Conference Room in use (TV & Split AC on)
        - 'all_occupied': All bays occupied
        - 'all_empty': Floor vacant after hours (100% savings)
        """
        if scenario_name in ("only_team_a", "only_bay_1"):
            self.synthetic_people = [
                SyntheticPerson(1, 150, 210, "bay_1"),
                SyntheticPerson(2, 240, 210, "bay_1"),
                SyntheticPerson(3, 330, 210, "bay_1"),
                SyntheticPerson(4, 420, 240, "bay_1"),
            ]
        elif scenario_name in ("only_team_b", "only_bay_2"):
            self.synthetic_people = [
                SyntheticPerson(1, 150, 350, "bay_2"),
                SyntheticPerson(2, 240, 350, "bay_2"),
                SyntheticPerson(3, 330, 350, "bay_2"),
            ]
        elif scenario_name == "bays_1_and_3":
            self.synthetic_people = [
                SyntheticPerson(1, 150, 210, "bay_1"),
                SyntheticPerson(2, 240, 210, "bay_1"),
                SyntheticPerson(3, 150, 490, "bay_3"),
                SyntheticPerson(4, 240, 490, "bay_3"),
            ]
        elif scenario_name in ("meeting_in_session", "conference_meeting"):
            self.synthetic_people = [
                SyntheticPerson(1, 260, 800, "conf_room"),
                SyntheticPerson(2, 340, 810, "conf_room"),
                SyntheticPerson(3, 420, 800, "conf_room"),
                SyntheticPerson(4, 150, 210, "bay_1"),
            ]
        elif scenario_name == "all_occupied":
            self.synthetic_people = [
                SyntheticPerson(1, 180, 210, "bay_1"),
                SyntheticPerson(2, 260, 350, "bay_2"),
                SyntheticPerson(3, 200, 490, "bay_3"),
                SyntheticPerson(4, 300, 630, "bay_4"),
                SyntheticPerson(5, 675, 335, "manager_cabin"),
                SyntheticPerson(6, 340, 800, "conf_room")
            ]
        elif scenario_name == "all_empty":
            self.synthetic_people = []

    def release(self):
        if self.cap is not None and self.cap.isOpened():
            self.cap.release()
