"""Restricted-zone event engine — Phase 3.

Turns tracked-object positions into intrusion events: one event per
zone *crossing* — the transition from outside to inside — not one
event per frame the object happens to be sitting inside a zone.
That distinction is the entire point of this module. "Person detected
inside zone" repeated 20-30 times a second while someone just stands
there is noise, not an event; the guide's own performance-strategy
section calls this out explicitly ("make zone events stateful to
avoid duplicate alerts every frame").
"""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

import cv2

from vision.tracking.tracker import TrackedObject

from .zone import Zone


@dataclass
class IntrusionEvent:
    event_id: str
    type: str
    camera_id: str
    zone_id: str
    zone_name: str
    track_id: int
    cls: str
    confidence: float
    timestamp: float
    entry_point: Tuple[float, float]
    evidence_path: Optional[str] = None


def reference_point(bbox: Tuple[float, float, float, float]) -> Tuple[float, float]:
    """Bottom-center of the bounding box — an approximation of the
    object's ground-plane position, not the box centroid. A tall
    bounding box's center can sit well above where a person is
    actually standing, which would trigger zone entry inconsistently
    depending on how tall the box is / how the camera is angled.
    """
    x1, y1, x2, y2 = bbox
    return ((x1 + x2) / 2.0, y2)


# Same colors the frontend dashboard already uses for these two
# concepts (frontend/src/lib/palette.js) — the intruder's box uses
# the "critical/active" red-orange, the zone boundary uses the
# "caution/checkpoint" amber the web zone editor draws with. Keeping
# the evidence image's colors consistent with the UI it's displayed
# in, not just picking OpenCV's default red for both.
_COLOR_INTRUDER_BOX = (62, 89, 232)   # BGR for #E8593E
_COLOR_ZONE_BORDER = (62, 167, 227)   # BGR for #E3A73E


def _draw_evidence_annotation(frame_image, obj: TrackedObject, zone: Zone):
    """Draws the triggering object's bounding box and the zone
    boundary onto a COPY of the frame, so the saved evidence image
    itself shows what was detected and where. This is what the
    dashboard actually displays (CameraPanel's snapshot, the incident
    detail modal) — the annotation has to be baked into the saved
    image at capture time, not something the UI draws later, since
    the frontend never receives raw detection coordinates, only the
    finished JPEG referenced by evidence_path.
    """
    annotated = frame_image.copy()

    zone.draw(annotated, color=_COLOR_ZONE_BORDER, thickness=2)

    x1, y1, x2, y2 = (int(v) for v in obj.bbox)
    cv2.rectangle(annotated, (x1, y1), (x2, y2), _COLOR_INTRUDER_BOX, 3)

    label = f"{obj.cls} ID {obj.track_id} {obj.confidence:.0%}"
    font, scale, thickness = cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2
    (text_w, _), _ = cv2.getTextSize(label, font, scale, thickness)
    frame_h, frame_w = annotated.shape[:2]
    # Clamp so the label never runs off the right edge — visible and
    # cut off in the very first real test image this produced, near a
    # box close to the frame boundary. Left edge can't go negative either.
    label_x = min(x1, frame_w - text_w - 5)
    label_x = max(label_x, 5)
    label_y = max(y1 - 10, 20)
    cv2.putText(annotated, label, (label_x, label_y), font, scale, _COLOR_INTRUDER_BOX, thickness)

    cv2.putText(annotated, "INTRUSION DETECTED", (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 1.0, _COLOR_INTRUDER_BOX, 3)

    return annotated


class EventEngine:
    def __init__(
        self,
        zones: List[Zone],
        evidence_dir: Optional[str] = None,
        events_log_path: Optional[str] = None,
        on_event: Optional[Callable[["IntrusionEvent"], None]] = None,
    ) -> None:
        """
        Args:
            on_event: optional callback invoked with each IntrusionEvent
                right after it's created (evidence saved, JSONL logged).
                This is the extension point Phase 4 uses to push events
                to the backend over HTTP — kept as a plain callback so
                this module has zero networking code / no dependency on
                `requests`. See scripts/run_phase4_demo.py.
        """
        self.zones = zones
        self.evidence_dir = Path(evidence_dir) if evidence_dir else None
        if self.evidence_dir:
            self.evidence_dir.mkdir(parents=True, exist_ok=True)
        self.events_log_path = Path(events_log_path) if events_log_path else None
        self.on_event = on_event

        # (track_id, zone_id) -> currently inside? This state is what
        # makes crossings — not raw containment — the actual trigger.
        self._inside_state: Dict[Tuple[int, str], bool] = {}

    def process(self, tracked: List[TrackedObject], frame_image=None) -> List[IntrusionEvent]:
        """Call once per frame with that frame's tracked objects.
        Returns only the events newly triggered THIS frame (usually empty)."""
        events: List[IntrusionEvent] = []
        for obj in tracked:
            point = reference_point(obj.bbox)
            for zone in self.zones:
                if zone.camera_id != obj.camera_id:
                    continue

                key = (obj.track_id, zone.zone_id)
                was_inside = self._inside_state.get(key, False)
                is_inside = zone.contains(point)

                if is_inside and not was_inside:
                    events.append(self._create_event(obj, zone, point, frame_image))

                self._inside_state[key] = is_inside

        return events

    def _create_event(self, obj: TrackedObject, zone: Zone, point, frame_image) -> IntrusionEvent:
        event_id = str(uuid.uuid4())
        evidence_path = None

        if self.evidence_dir is not None and frame_image is not None:
            annotated = _draw_evidence_annotation(frame_image, obj, zone)
            evidence_path = str(self.evidence_dir / f"{event_id}.jpg")
            cv2.imwrite(evidence_path, annotated)

        event = IntrusionEvent(
            event_id=event_id,
            type="INTRUSION",
            camera_id=obj.camera_id,
            zone_id=zone.zone_id,
            zone_name=zone.name,
            track_id=obj.track_id,
            cls=obj.cls,
            confidence=obj.confidence,
            timestamp=obj.timestamp,
            entry_point=point,
            evidence_path=evidence_path,
        )

        if self.events_log_path is not None:
            self.events_log_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.events_log_path, "a") as f:
                f.write(json.dumps(asdict(event)) + "\n")

        if self.on_event is not None:
            self.on_event(event)

        return event

    def forget_track(self, track_id: int) -> None:
        """Optional cleanup — call once a track is confirmed gone (not
        seen for N frames) so its zone state doesn't sit around
        forever. Not needed for a short demo clip; cheap insurance for
        anything longer-running."""
        self._inside_state = {k: v for k, v in self._inside_state.items() if k[0] != track_id}
