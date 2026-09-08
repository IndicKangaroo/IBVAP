"""ANPR + vehicle identification trigger engine — Phase 5 (extended).

Runs plate localization + OCR, plus vehicle type/color classification,
only when a vehicle track crosses into a designated trigger zone — and
only once per track per zone, using the same crossing-detection idiom
as vision.event_engine.engine.EventEngine. This directly implements
the guide's performance strategy: "Do not run OCR ... on every frame;
trigger expensive modules only when needed." Color classification is
cheap enough to not need its own gate, so it rides along on the same
trigger as OCR rather than getting a separate one.

A trigger zone is just a Zone (same class, same JSON config format as
restricted zones) — reused here for a different purpose: not "alert on
entry" but "identify a vehicle once per pass-through."
"""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

import cv2

from vision.coco_classes import is_vehicle
from vision.event_engine.engine import reference_point
from vision.event_engine.zone import Zone
from vision.tracking.tracker import TrackedObject

from .color_classifier import classify_vehicle_color
from .normalizer import is_plausible, normalize
from .ocr_reader import PlateOCR
from .plate_localizer import localize_plate


@dataclass
class ANPRResult:
    result_id: str
    camera_id: str
    track_id: int
    vehicle_type: str                    # "car" | "motorcycle" | "bus" | "truck"
    vehicle_color: Optional[str]         # e.g. "white", "blue" — None if the crop was empty
    vehicle_color_confidence: float
    plate_text: Optional[str]
    confidence: float
    plausible: bool
    timestamp: float
    evidence_path: Optional[str] = None


class ANPREngine:
    def __init__(
        self,
        trigger_zones: List[Zone],
        ocr: PlateOCR,
        evidence_dir: Optional[str] = None,
        results_log_path: Optional[str] = None,
        on_result: Optional[Callable[[ANPRResult], None]] = None,
    ) -> None:
        self.trigger_zones = trigger_zones
        self.ocr = ocr
        self.evidence_dir = Path(evidence_dir) if evidence_dir else None
        if self.evidence_dir:
            self.evidence_dir.mkdir(parents=True, exist_ok=True)
        self.results_log_path = Path(results_log_path) if results_log_path else None
        self.on_result = on_result

        self._triggered: Dict[Tuple[int, str], bool] = {}     # (track_id, zone_id) -> already read?
        self._inside_state: Dict[Tuple[int, str], bool] = {}  # (track_id, zone_id) -> currently inside?

    def process(self, tracked: List[TrackedObject], frame_image) -> List[ANPRResult]:
        results: List[ANPRResult] = []
        for obj in tracked:
            if not is_vehicle(obj.cls):
                continue
            point = reference_point(obj.bbox)
            for zone in self.trigger_zones:
                if zone.camera_id != obj.camera_id:
                    continue

                key = (obj.track_id, zone.zone_id)
                was_inside = self._inside_state.get(key, False)
                is_inside = zone.contains(point)
                self._inside_state[key] = is_inside

                if is_inside and not was_inside and not self._triggered.get(key, False):
                    self._triggered[key] = True  # once per vehicle per zone, even if it lingers
                    results.append(self._run_anpr(obj, frame_image))
        return results

    def _run_anpr(self, obj: TrackedObject, frame_image) -> ANPRResult:
        x1, y1, x2, y2 = (int(v) for v in obj.bbox)
        h, w = frame_image.shape[:2]
        x1, y1, x2, y2 = max(0, x1), max(0, y1), min(w, x2), min(h, y2)
        vehicle_crop = frame_image[y1:y2, x1:x2]

        result_id = str(uuid.uuid4())
        plate_text, confidence, plausible, evidence_path = None, 0.0, False, None

        # Runs on every triggered vehicle regardless of whether OCR
        # finds a plate — color is independent of plate legibility,
        # and unlike OCR it's cheap enough not to need its own gate.
        vehicle_color, vehicle_color_confidence = classify_vehicle_color(vehicle_crop)

        if vehicle_crop.size > 0:
            px1, py1, px2, py2 = localize_plate(vehicle_crop)
            plate_crop = vehicle_crop[py1:py2, px1:px2]

            if plate_crop.size > 0:
                raw_text, confidence = self.ocr.read(plate_crop)
                if raw_text:
                    plate_text = normalize(raw_text)
                    plausible = is_plausible(plate_text)

                if self.evidence_dir is not None:
                    evidence_path = str(self.evidence_dir / f"{result_id}.jpg")
                    cv2.imwrite(evidence_path, plate_crop)

        result = ANPRResult(
            result_id=result_id,
            camera_id=obj.camera_id,
            track_id=obj.track_id,
            vehicle_type=obj.cls,
            vehicle_color=vehicle_color if vehicle_color != "unknown" else None,
            vehicle_color_confidence=vehicle_color_confidence,
            plate_text=plate_text,
            confidence=confidence,
            plausible=plausible,
            timestamp=obj.timestamp,
            evidence_path=evidence_path,
        )

        if self.results_log_path is not None:
            self.results_log_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.results_log_path, "a") as f:
                f.write(json.dumps(asdict(result)) + "\n")

        if self.on_result is not None:
            self.on_result(result)

        return result
