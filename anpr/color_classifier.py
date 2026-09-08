"""Vehicle color classification — classical CV, no model download needed.

Same reasoning as anpr/plate_localizer.py: no pretrained color
classifier was reachable from this build environment, and for a
bounded set of common vehicle colors under (comparatively) controlled
camera conditions, a classical HSV-threshold approach is a legitimate
choice here, not a placeholder for "real" ML. It also stays fast
enough to run on every vehicle without a trigger-zone gate.

Buckets are deliberately coarse: white, black, gray, red, orange,
yellow, green, blue, purple. No separate "silver" (indistinguishable
from white/gray with simple HSV thresholds — a silver car will land
in one of those two depending on lighting) and no "brown" (falls into
red/orange, usually at lower confidence). Stated here rather than
discovered later.
"""
from __future__ import annotations

from typing import Optional, Tuple

import cv2
import numpy as np

# OpenCV's hue range is [0, 180], not [0, 360]. Red wraps around 0/180.
_HUE_BUCKETS = {
    "orange": [(10, 22)],
    "yellow": [(22, 35)],
    "green": [(35, 85)],
    "blue": [(85, 130)],
    "purple": [(130, 155)],
    "red": [(155, 180), (0, 10)],  # covers both ends of the hue wrap
}

_SAT_ACHROMATIC_MAX = 40   # below this, treat as white/gray/black regardless of hue
_VAL_BLACK_MAX = 60
_VAL_WHITE_MIN = 180
_VAL_DARK_IGNORE_MAX = 35  # near-black shadow/glass pixels — excluded from chromatic voting


def classify_vehicle_color(vehicle_crop: Optional[np.ndarray]) -> Tuple[str, float]:
    """Returns (color_name, confidence). confidence is the fraction of
    sampled pixels that voted for the winning bucket — a measure of
    how uniform the crop's color was, not a calibrated probability.
    A low value (rule of thumb: under ~0.3) usually means a small or
    low-quality crop, strong shadowing, or a multi-tone vehicle —
    treat the label as best-effort, not certain, same spirit as ANPR's
    confidence score.
    """
    if vehicle_crop is None or vehicle_crop.size == 0:
        return "unknown", 0.0

    h, w = vehicle_crop.shape[:2]
    # Center-crop: bounding boxes aren't tight to the vehicle silhouette,
    # and the top/bottom edges are the likeliest places to catch
    # background, ground shadow, or dark window glass rather than body
    # paint — this narrows to the region most likely to BE body paint.
    y1, y2 = int(h * 0.25), int(h * 0.75)
    x1, x2 = int(w * 0.1), int(w * 0.9)
    crop = vehicle_crop[y1:y2, x1:x2]
    if crop.size == 0:
        crop = vehicle_crop

    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    h_ch = hsv[:, :, 0].astype(np.int32)
    s_ch = hsv[:, :, 1].astype(np.int32)
    v_ch = hsv[:, :, 2].astype(np.int32)
    total = h_ch.size
    if total == 0:
        return "unknown", 0.0

    achromatic = s_ch < _SAT_ACHROMATIC_MAX
    black_mask = achromatic & (v_ch < _VAL_BLACK_MAX)
    white_mask = achromatic & (v_ch >= _VAL_WHITE_MIN)
    gray_mask = achromatic & ~black_mask & ~white_mask

    votes = {
        "black": int(black_mask.sum()),
        "white": int(white_mask.sum()),
        "gray": int(gray_mask.sum()),
    }

    chromatic = ~achromatic & (v_ch >= _VAL_DARK_IGNORE_MAX)
    for name, ranges in _HUE_BUCKETS.items():
        count = 0
        for lo, hi in ranges:
            count += int(((h_ch >= lo) & (h_ch < hi) & chromatic).sum())
        votes[name] = count

    best_color = max(votes, key=votes.get)
    confidence = votes[best_color] / total
    return best_color, float(confidence)
