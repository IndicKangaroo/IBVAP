"""Object tracking — Phase 2.

Adds persistent track IDs on top of Phase 1 detection using
Ultralytics' built-in ByteTrack integration (the guide's first-choice
tracker). This intentionally runs detection + tracking in one pass via
`model.track()` rather than tracking Phase 1's `Detection` objects
after the fact — Ultralytics' tracker is tightly coupled to its own
detection loop internally, so re-detecting separately would mean
running the model twice per frame for no benefit. `Tracker` owns its
own model instance for this reason; use Detector (Phase 1) OR Tracker
(Phase 2) per camera stream, not both on the same frame.

If ByteTrack struggles with occlusion-heavy footage (people crossing
paths, briefly hidden behind a vehicle), swap `tracker_config` to
"botsort.yaml" — Ultralytics ships both, no other code changes needed.
That maps to the guide's "DeepSORT if needed" fallback (BoT-SORT adds
the same appearance-matching idea DeepSORT does).
"""
from __future__ import annotations

import torch
from dataclasses import dataclass
from typing import ClassVar, List, Tuple

from ultralytics import YOLO

from vision.video_ingest.reader import Frame

# Same MVP scope as Phase 1: person + the four COCO vehicle classes.
_COCO_VEHICLE_IDS = {2, 3, 5, 7}
_COCO_PERSON_ID = 0


@dataclass
class TrackedObject:
    camera_id: str
    frame_id: int
    timestamp: float
    track_id: int
    cls: str                              # "person" | "vehicle"
    confidence: float
    bbox: Tuple[float, float, float, float]  # x1, y1, x2, y2 in pixels


class Tracker:
    """Runs YOLO detection + ByteTrack association, scoped to person/vehicle."""

    DEFAULT_MODEL: ClassVar[str] = "yolov8n.pt"

    def __init__(
        self,
        model_path: str = DEFAULT_MODEL,
        conf_threshold: float = 0.4,
        tracker_config: str = "bytetrack.yaml",
        device: str = "auto",
    ) -> None:
        """
        Args:
            device: "auto" picks CUDA if available, else CPU. Pass "cpu"
                or "cuda:0" explicitly to override. Printed on load so
                you can confirm the GPU is actually being used.
        """
        resolved_device = ("cuda:0" if torch.cuda.is_available() else "cpu") if device == "auto" else device
        self.device = resolved_device
        self.model = YOLO(model_path)
        self.model.to(resolved_device)
        self.conf_threshold = conf_threshold
        self.tracker_config = tracker_config
        print(f"[Tracker] model={model_path} device={resolved_device} tracker={tracker_config}")

    def track(self, frame: Frame) -> List[TrackedObject]:
        """Run tracking on one ingested Frame, return filtered TrackedObjects.

        `persist=True` keeps ByteTrack's internal state between calls
        so IDs carry across frames of the same stream instead of
        resetting every call.
        """
        results = self.model.track(
            source=frame.image,
            conf=self.conf_threshold,
            tracker=self.tracker_config,
            persist=True,
            verbose=False,
        )[0]

        tracked: List[TrackedObject] = []
        if results.boxes is None or results.boxes.id is None:
            # Nothing tracked yet this frame — e.g. no detections, or
            # ByteTrack hasn't confirmed a new track as stable yet.
            return tracked

        for box in results.boxes:
            cls_id = int(box.cls[0])
            if cls_id == _COCO_PERSON_ID:
                cls_name = "person"
            elif cls_id in _COCO_VEHICLE_IDS:
                cls_name = "vehicle"
            else:
                continue  # outside MVP scope

            x1, y1, x2, y2 = (float(v) for v in box.xyxy[0])
            tracked.append(
                TrackedObject(
                    camera_id=frame.camera_id,
                    frame_id=frame.frame_id,
                    timestamp=frame.timestamp,
                    track_id=int(box.id[0]),
                    cls=cls_name,
                    confidence=float(box.conf[0]),
                    bbox=(x1, y1, x2, y2),
                )
            )
        return tracked
