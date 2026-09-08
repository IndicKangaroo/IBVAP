"""Detection — Phase 1.

Wraps a lightweight YOLO model (Ultralytics) and filters its output down
to the classes the IBVAP MVP cares about: person and vehicle sub-types
(car, motorcycle, bus, truck — see vision/coco_classes.py).

Swap `model_path` for a bigger checkpoint later if accuracy needs
outweigh speed on your hardware — nothing downstream (tracking, zone
logic) needs to know which YOLO variant produced the boxes.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar, List, Tuple

from ultralytics import YOLO

from vision.coco_classes import classify_coco_id
from vision.video_ingest.reader import Frame


@dataclass
class Detection:
    camera_id: str
    frame_id: int
    timestamp: float
    cls: str                              # "person" | "car" | "motorcycle" | "bus" | "truck"
    confidence: float
    bbox: Tuple[float, float, float, float]  # x1, y1, x2, y2 in pixels


class Detector:
    """Runs YOLO on a single Frame and returns MVP-scoped Detections."""

    DEFAULT_MODEL: ClassVar[str] = "yolov8n.pt"  # smallest/fastest COCO checkpoint

    def __init__(self, model_path: str = DEFAULT_MODEL, conf_threshold: float = 0.4) -> None:
        self.model = YOLO(model_path)
        self.conf_threshold = conf_threshold

    def detect(self, frame: Frame) -> List[Detection]:
        """Run detection on one ingested Frame, return filtered detections."""
        results = self.model.predict(
            source=frame.image,
            conf=self.conf_threshold,
            verbose=False,
        )[0]

        detections: List[Detection] = []
        for box in results.boxes:
            cls_name = classify_coco_id(int(box.cls[0]))
            if cls_name is None:
                continue  # outside MVP scope — ignore

            x1, y1, x2, y2 = (float(v) for v in box.xyxy[0])
            detections.append(
                Detection(
                    camera_id=frame.camera_id,
                    frame_id=frame.frame_id,
                    timestamp=frame.timestamp,
                    cls=cls_name,
                    confidence=float(box.conf[0]),
                    bbox=(x1, y1, x2, y2),
                )
            )
        return detections
