"""
Core End-to-End Orchestration Pipeline.
Integrates Video Stream -> YOLO Detector -> Zone Projection -> Debouncing -> Switch Control -> Energy Metrics.
"""
import time
import json
from typing import Dict, Any, List, Optional
import cv2
import numpy as np

from src.models import PersonDetection, FloorTelemetry
from src.detector import HumanDetector
from src.zone_manager import ZoneManager
from src.energy_tracker import EnergyTracker
from src.switch_controller import SwitchController
from src.video_stream import VideoStreamHandler


class FloorEnergyPipeline:
    def __init__(
        self,
        config_path: str = "config/default_zones.json",
        source: str = "synthetic",
        confidence: float = 0.40
    ):
        self.config_path = config_path
        self.zone_manager = ZoneManager(config_path)
        self.energy_tracker = EnergyTracker()
        self.switch_controller = SwitchController(mode="mock")
        self.detector = HumanDetector(confidence_threshold=confidence)
        self.stream_handler = VideoStreamHandler(source=source)

        self.latest_frame_jpeg: Optional[bytes] = None
        self.latest_telemetry: Optional[FloorTelemetry] = None
        self.is_running = True

        # Edge acceleration: decouple display FPS from AI inference frequency
        self.cached_detections: List[PersonDetection] = []
        self.last_infer_timestamp: float = 0.0
        self.infer_interval: float = 0.09  # Run YOLO at ~11 Hz, leaving CPU free for 30 FPS video display

    def process_tick(self) -> FloorTelemetry:
        """
        Executes a single end-to-end iteration of the pipeline.
        """
        success, frame, gt_detections = self.stream_handler.read_frame()
        if not success or frame is None:
            time.sleep(0.01)
            return self.latest_telemetry

        h, w = frame.shape[:2]
        now = time.time()

        # 1. Detect Humans (Threaded / Cached for High-FPS live streaming on Raspberry Pi)
        if self.stream_handler.is_synthetic:
            detections = []
            for gt in gt_detections:
                detections.append(
                    PersonDetection(
                        id=gt["id"],
                        confidence=gt.get("confidence", 0.95),
                        bbox=gt["bbox"],
                        feet_coord=gt["feet_coord"],
                        zone_id=None
                    )
                )
            self.cached_detections = detections
        elif self.detector.model is not None:
            # Run YOLO pass if interval elapsed; otherwise reuse cached detections
            if (now - self.last_infer_timestamp) >= self.infer_interval:
                self.last_infer_timestamp = now
                self.cached_detections = self.detector.detect(frame)
            detections = self.cached_detections
        else:
            detections = self.cached_detections

        # 2. Map detections to zones and apply debounce logic
        switch_events = self.zone_manager.update_occupancy(detections, frame_width=w, frame_height=h)

        # 3. Dispatch switch actions to IoT Switch Controller
        for event in switch_events:
            state_bool = (event["action"] == "ON")
            self.switch_controller.batch_update_zone(
                switches=event["switches"],
                state=state_bool,
                zone_name=event["zone_name"],
                reason=event["reason"]
            )

        # 4. Calculate Energy & Sustainability metrics
        energy_metrics = self.energy_tracker.update(self.zone_manager.zones)

        # 5. Render live visual overlays on the frame
        annotated_frame = self._render_visual_overlays(frame.copy(), detections)

        # 6. Encode to JPEG (55% quality provides 3x faster encoding and lower latency on Pi)
        ret, jpeg_buffer = cv2.imencode(".jpg", annotated_frame, [int(cv2.IMWRITE_JPEG_QUALITY), 55])
        if ret:
            self.latest_frame_jpeg = jpeg_buffer.tobytes()

        # 7. Construct telemetry package
        self.latest_telemetry = FloorTelemetry(
            timestamp=time.time(),
            floor_name=self.zone_manager.floor_name,
            total_occupancy=len(detections),
            zones=self.zone_manager.get_summary(),
            switches=dict(self.switch_controller.relay_states),
            detections=detections,
            energy=energy_metrics
        )

        return self.latest_telemetry

    def _render_visual_overlays(self, frame: np.ndarray, detections: List[PersonDetection]) -> np.ndarray:
        h, w = frame.shape[:2]
        overlay = frame.copy()

        # Draw Zone Polygons
        for zid, zone in self.zone_manager.zones.items():
            pts = []
            for pt in zone.camera_polygon:
                pts.append([int(pt[0] * w), int(pt[1] * h)])
            pts = np.array(pts, np.int32).reshape((-1, 1, 2))

            # Color styling based on occupancy
            if zone.lights_state:
                # Active/Occupied: Bright Green/Blue tint
                fill_color = (40, 180, 80) if zone.is_occupied else (220, 150, 40)
                alpha = 0.25
                border_color = (50, 240, 100) if zone.is_occupied else (255, 180, 50)
            else:
                # Vacant/Lights Off: Dim gray/dark tint
                fill_color = (40, 45, 55)
                alpha = 0.40
                border_color = (80, 90, 100)

            cv2.fillPoly(overlay, [pts], fill_color)
            cv2.polylines(frame, [pts], True, border_color, 2)

            # Zone Label Box
            lx, ly = int(zone.camera_polygon[0][0] * w) + 10, int(zone.camera_polygon[0][1] * h) + 24
            state_text = f"{zone.name} | {'LIGHTS ON' if zone.lights_state else 'OFF'}"
            cv2.putText(frame, state_text, (lx, ly), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1, cv2.LINE_AA)

        # Blend polygon fills with alpha
        cv2.addWeighted(overlay, 0.4, frame, 0.6, 0, frame)

        # Draw Detected Humans & Feet Contact Points
        for person in detections:
            x1, y1, x2, y2 = [int(v) for v in person.bbox]
            fx, fy = [int(v) for v in person.feet_coord]

            # Bounding Box
            color = (0, 255, 255) if person.zone_id else (160, 160, 160)
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)

            # Feet contact marker (small circle on floor)
            cv2.circle(frame, (fx, fy), 5, (0, 0, 255), -1)
            cv2.circle(frame, (fx, fy), 8, (0, 255, 255), 1)

            # Label
            label = f"ID:{person.id} {person.zone_id or 'corridor'}"
            cv2.putText(frame, label, (x1, max(15, y1 - 6)), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1, cv2.LINE_AA)

        return frame

    def switch_scenario(self, scenario_name: str):
        self.stream_handler.trigger_scenario(scenario_name)
