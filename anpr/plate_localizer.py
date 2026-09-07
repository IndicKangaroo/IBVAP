"""Plate region localization — Phase 5.

No learned plate-detector model here on purpose — a pretrained one
wasn't reachable from this environment's allowed network domains, and
more importantly, the guide's own ANPR scope doesn't need one: "Demo:
controlled sample footage with fictional/sample plates; do not depend
on live road traffic." For that scope, classical CV — edge detection +
contour geometry, restricted to a vehicle's own bounding box — is a
legitimate, explainable approach, not a placeholder for a "real"
model. A learned plate-detector would be the natural upgrade path if
this ever needs to handle uncontrolled real-world traffic footage.
"""
from __future__ import annotations

from typing import Tuple

import cv2
import numpy as np

# A plate is noticeably wider than tall; loosen/tighten if your sample
# footage's plates look visually different from a typical rectangular plate.
_MIN_ASPECT = 1.5
_MAX_ASPECT = 6.0
_MIN_AREA_FRACTION = 0.01   # plate must be at least 1% of the vehicle crop's area
_MAX_AREA_FRACTION = 0.35


def _heuristic_crop(vehicle_crop: np.ndarray) -> Tuple[int, int, int, int]:
    """Fixed fallback region: plates usually sit in the lower-middle
    portion of a vehicle's bounding box — not the roofline/windshield,
    not the very edges (mirrors, background)."""
    h, w = vehicle_crop.shape[:2]
    x1, x2 = int(w * 0.20), int(w * 0.80)
    y1, y2 = int(h * 0.55), int(h * 0.90)
    return x1, y1, x2, y2


def localize_plate(vehicle_crop: np.ndarray) -> Tuple[int, int, int, int]:
    """Returns (x1, y1, x2, y2) of the candidate plate region, in the
    vehicle_crop's own coordinate space (caller offsets back to the
    full frame). Always returns SOME region rather than None — the
    caller (ANPREngine) already decided a plate read is worth
    attempting; OCR confidence is what signals whether it paid off.
    """
    h, w = vehicle_crop.shape[:2]
    if h == 0 or w == 0:
        return _heuristic_crop(vehicle_crop)

    gray = cv2.cvtColor(vehicle_crop, cv2.COLOR_BGR2GRAY)
    blurred = cv2.bilateralFilter(gray, 11, 17, 17)
    edges = cv2.Canny(blurred, 30, 200)
    edges = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, np.ones((3, 9), np.uint8))

    contours, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)

    vehicle_area = h * w
    best = None
    best_area = 0
    for c in contours:
        x, y, cw, ch = cv2.boundingRect(c)
        if ch == 0:
            continue
        aspect = cw / ch
        area_fraction = (cw * ch) / vehicle_area
        if not (_MIN_ASPECT <= aspect <= _MAX_ASPECT and _MIN_AREA_FRACTION <= area_fraction <= _MAX_AREA_FRACTION):
            continue
        if y < h * 0.4:
            continue  # plates aren't on the roof — skip upper-half contours
        area = cw * ch
        if area > best_area:
            best_area = area
            best = (x, y, x + cw, y + ch)

    return best if best is not None else _heuristic_crop(vehicle_crop)
