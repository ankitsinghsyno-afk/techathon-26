"""
Video stream capture and synthetic office simulation engine.
Provides frames from webcam, RTSP, video file, or a simulated office environment.
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
        self.speed = random.uniform(1.5, 3.5)
        self.state = "working"  # "working", "walking"
        self.last_decision = time.time()

    def update(self, bounds: Tuple[int, int], waypoints: Dict[str, Tuple[float, float]]):
        now = time.time()
        # Randomly decide to wander or visit pantry/conf room
        if now - self.last_decision > random.uniform(8.0, 20.0):
            self.last_decision = now
            dest_key = random.choice(list(waypoints.keys()))
            tx, ty = waypoints[dest_key]
            # Add small random jitter inside the zone
            self.target_x = max(40, min(bounds[0] - 40, tx + random.uniform(-40, 40)))
            self.target_y = max(40, min(bounds[1] - 40, ty + random.uniform(-40, 40)))
            self.target_zone = dest_key
            self.state = "walking"

        # Move towards target
        dx = self.target_x - self.x
        dy = self.target_y - self.y
        dist = math.hypot(dx, dy)
        if dist > 3.0:
            self.x += (dx / dist) * self.speed
            self.y += (dy / dist) * self.speed
        else:
            self.state = "working"


class VideoStreamHandler:
    def __init__(self, source: str = "synthetic", width: int = 800, height: int = 600):
        self.source = source
        self.width = width
        self.height = height
        self.cap = None
        self.is_synthetic = (source.lower() == "synthetic")

        # Synthetic simulation entities
        self.synthetic_people: List[SyntheticPerson] = []
        self.waypoints = {
            "zone_alpha": (200.0, 160.0),
            "zone_beta": (600.0, 160.0),
            "zone_qa": (200.0, 430.0),
            "zone_conf": (520.0, 430.0),
            "zone_lounge": (690.0, 430.0),
        }
        self._init_source()

    def _init_source(self):
        if self.is_synthetic:
            # Seed with 3-5 office team members
            self.synthetic_people = [
                SyntheticPerson(1, 180, 150, "zone_alpha"),
                SyntheticPerson(2, 220, 180, "zone_alpha"),
                SyntheticPerson(3, 580, 140, "zone_beta"),
                SyntheticPerson(4, 690, 430, "zone_lounge")
            ]
        else:
            # Try to open webcam or video file / RTSP
            try:
                if self.source.isdigit():
                    src_val = int(self.source)
                    # On macOS prefer AVFOUNDATION backend explicitly
                    self.cap = cv2.VideoCapture(src_val, cv2.CAP_AVFOUNDATION)
                    if not self.cap.isOpened():
                        self.cap = cv2.VideoCapture(src_val)
                else:
                    self.cap = cv2.VideoCapture(self.source)

                if self.cap is None or not self.cap.isOpened():
                    print(f"⚠️ Notice: Camera source '{self.source}' could not be accessed.")
                    print("   If on macOS, ensure Camera permissions are granted to your Terminal/IDE.")
                    print("   Falling back safely to Synthetic Simulation Mode.")
                    self.is_synthetic = True
                    self.cap = None
                    self._init_source()
                    return

                self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
                self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
                # Minimize network stream latency buffer (crucial for wireless iPhone / RTSP streams)
                self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                # Test read a frame to confirm authorization
                ret, _ = self.cap.read()
                if not ret:
                    print(f"⚠️ Notice: Camera '{self.source}' opened but failed to capture frame (permission denied).")
                    print("   Reverting to Synthetic Simulation Mode.")
                    self.cap.release()
                    self.cap = None
                    self.is_synthetic = True
                    self._init_source()
            except Exception as e:
                print(f"Error opening camera source '{self.source}': {e}. Falling back to synthetic mode.")
                self.is_synthetic = True
                self.cap = None
                self._init_source()

    def read_frame(self) -> Tuple[bool, Optional[np.ndarray], List[Dict[str, Any]]]:
        """
        Returns (success, frame, synthetic_ground_truth_if_any)
        """
        if self.is_synthetic or self.cap is None or not self.cap.isOpened():
            frame, gt_boxes = self._generate_synthetic_frame()
            return True, frame, gt_boxes

        ret, frame = self.cap.read()
        if not ret:
            # If looped video file, rewind
            if isinstance(self.source, str) and not self.source.isdigit():
                self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                ret, frame = self.cap.read()
            if not ret:
                # If camera fails during read, gracefully fall back to synthetic
                frame, gt_boxes = self._generate_synthetic_frame()
                return True, frame, gt_boxes

        frame = cv2.resize(frame, (self.width, self.height))
        return True, frame, []

    def _generate_synthetic_frame(self) -> Tuple[np.ndarray, List[Dict[str, Any]]]:
        """
        Draws a top-down / angled office view with desks, partitions, and moving team members.
        Generates realistic visuals that can either be fed to YOLO or ground-truth extracted.
        """
        # Dark modern office background
        frame = np.full((self.height, self.width, 3), (28, 32, 38), dtype=np.uint8)

        # Draw grid flooring lines
        grid_size = 40
        for x in range(0, self.width, grid_size):
            cv2.line(frame, (x, 0), (x, self.height), (38, 44, 52), 1)
        for y in range(0, self.height, grid_size):
            cv2.line(frame, (0, y), (self.width, y), (38, 44, 52), 1)

        # Draw office bays & desks
        desks = [
            (80, 110, 140, 50), (220, 110, 140, 50),
            (480, 110, 140, 50), (620, 110, 140, 50),
            (80, 380, 140, 50), (220, 380, 140, 50),
            (470, 380, 100, 60), (650, 380, 80, 40)
        ]
        for dx, dy, dw, dh in desks:
            cv2.rectangle(frame, (dx, dy), (dx + dw, dy + dh), (55, 65, 81), -1)
            cv2.rectangle(frame, (dx, dy), (dx + dw, dy + dh), (90, 105, 120), 1)
            # Desk monitor
            cv2.rectangle(frame, (dx + dw//2 - 15, dy + dh - 10), (dx + dw//2 + 15, dy + dh - 4), (160, 175, 190), -1)

        # Update synthetic humans
        gt_detections = []
        for person in self.synthetic_people:
            person.update((self.width, self.height), self.waypoints)
            px = int(person.x)
            py = int(person.y)

            # Draw person representation (circle body, head, shoulder)
            # Person height ~ 60px, width ~ 30px
            w_person = 32
            h_person = 64
            x1 = px - w_person // 2
            y1 = py - h_person
            x2 = px + w_person // 2
            y2 = py  # feet coordinate

            # Draw avatar with shadow
            cv2.ellipse(frame, (px, py), (16, 8), 0, 0, 360, (15, 18, 22), -1)  # shadow
            cv2.rectangle(frame, (x1 + 4, y1 + 18), (x2 - 4, y2 - 4), (59, 130, 246), -1)  # torso
            cv2.circle(frame, (px, y1 + 10), 10, (230, 185, 150), -1)  # head

            gt_detections.append({
                "id": person.pid,
                "bbox": [x1, y1, x2, y2],
                "feet_coord": (float(px), float(y2)),
                "confidence": 0.94
            })

        return frame, gt_detections

    def trigger_scenario(self, scenario_name: str):
        """
        Allows interactive manipulation of people in synthetic mode for presentations.
        e.g. 'only_team_a', 'all_empty', 'all_occupied', 'meeting_in_session'
        """
        if scenario_name == "only_team_a":
            self.synthetic_people = [
                SyntheticPerson(1, 180, 170, "zone_alpha"),
                SyntheticPerson(2, 240, 190, "zone_alpha"),
                SyntheticPerson(3, 150, 220, "zone_alpha")
            ]
        elif scenario_name == "only_team_b":
            self.synthetic_people = [
                SyntheticPerson(1, 580, 170, "zone_beta"),
                SyntheticPerson(2, 640, 190, "zone_beta")
            ]
        elif scenario_name == "all_empty":
            self.synthetic_people = []
        elif scenario_name == "meeting_in_session":
            self.synthetic_people = [
                SyntheticPerson(1, 500, 420, "zone_conf"),
                SyntheticPerson(2, 530, 440, "zone_conf"),
                SyntheticPerson(3, 550, 410, "zone_conf"),
                SyntheticPerson(4, 180, 170, "zone_alpha")
            ]
        elif scenario_name == "all_occupied":
            self.synthetic_people = [
                SyntheticPerson(1, 180, 170, "zone_alpha"),
                SyntheticPerson(2, 580, 170, "zone_beta"),
                SyntheticPerson(3, 200, 420, "zone_qa"),
                SyntheticPerson(4, 520, 420, "zone_conf"),
                SyntheticPerson(5, 680, 420, "zone_lounge")
            ]

    def release(self):
        if self.cap is not None and self.cap.isOpened():
            self.cap.release()
