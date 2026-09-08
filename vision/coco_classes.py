"""Shared COCO class mapping for detection/tracking.

Previously, car/motorcycle/bus/truck were all collapsed into one
generic "vehicle" label in both Detector and Tracker independently.
Now each gets its own name — the detector already sees these finer
COCO categories, collapsing them was a filtering choice, not a model
limitation. Anything that needs "is this any kind of vehicle,
regardless of which" (ANPR triggering, zone logic, etc.) should use
is_vehicle() below rather than a single string comparison, since
there's no longer one string that means "vehicle".
"""
from __future__ import annotations

COCO_PERSON_ID = 0
COCO_VEHICLE_ID_TO_NAME = {2: "car", 3: "motorcycle", 5: "bus", 7: "truck"}
VEHICLE_CLASS_NAMES = frozenset(COCO_VEHICLE_ID_TO_NAME.values())


def classify_coco_id(cls_id: int) -> str | None:
    """Returns the class name for an MVP-scoped COCO id, or None if
    it's outside scope (not person, not one of the four vehicle types)."""
    if cls_id == COCO_PERSON_ID:
        return "person"
    return COCO_VEHICLE_ID_TO_NAME.get(cls_id)


def is_vehicle(cls_name: str | None) -> bool:
    return cls_name in VEHICLE_CLASS_NAMES
