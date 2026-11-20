"""
Human Detection module using Ultralytics YOLOv8.
Extracts person bounding boxes and calculates floor contact points (feet coordinates).
"""
import time
from typing import List, Tuple, Optional
import numpy as np
from src.models import PersonDetection


class HumanDetector:
    def __init__(self, model_name: str = "yolov8n.pt", confidence_threshold: float = 0.40, imgsz: int = 384):
        self.model_name = model_name
        self.confidence_threshold = confidence_threshold
        self.imgsz = imgsz
        self.model = None
        self._load_model()

    def _load_model(self):
        try:
            import os
            from ultralytics import YOLO
            model_target = self.model_name
            # If NCNN model directory exists on Raspberry Pi, use it automatically for 3x speed
            if os.path.exists("yolov8n_ncnn_model"):
                model_target = "yolov8n_ncnn_model"
                print(f"🚀 Detected & loading accelerated NCNN model: {model_target}")
            else:
                print(f"Loading YOLO model: {model_target}...")
            self.model = YOLO(model_target)
            print("YOLO model loaded successfully.")
        except Exception as e:
            print(f"Notice: Could not initialize YOLO directly ({e}). Fallback detector will be used if needed.")
            self.model = None

    def detect(self, frame: np.ndarray) -> List[PersonDetection]:
        """
        Runs person detection on an image frame (BGR format from OpenCV).
        Returns a list of PersonDetection objects with feet coordinates.
        """
        detections: List[PersonDetection] = []
        if self.model is None or frame is None:
            return detections

        h, w = frame.shape[:2]
        # Class 0 in COCO is 'person'. imgsz=384 optimizes speed on Raspberry Pi / ARM CPU
        results = self.model(
            frame,
            classes=[0],
            conf=self.confidence_threshold,
            imgsz=self.imgsz,
            verbose=False
        )

        person_idx = 1
        for result in results:
            boxes = result.boxes
            if boxes is None:
                continue

            for box in boxes:
                xyxy = box.xyxy[0].cpu().numpy()
                x1, y1, x2, y2 = float(xyxy[0]), float(xyxy[1]), float(xyxy[2]), float(xyxy[3])
                conf = float(box.conf[0].cpu().numpy())

                # Ground contact point: center-bottom of bounding box
                feet_x = (x1 + x2) / 2.0
                feet_y = y2

                detections.append(
                    PersonDetection(
                        id=person_idx,
                        confidence=round(conf, 2),
                        bbox=[round(x1, 1), round(y1, 1), round(x2, 1), round(y2, 1)],
                        feet_coord=(round(feet_x, 1), round(feet_y, 1)),
                        zone_id=None
                    )
                )
                person_idx += 1

        return detections
