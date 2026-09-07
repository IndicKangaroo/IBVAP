"""Restricted-zone definitions — Phase 3.

A Zone is a named polygon on one camera's frame. Point-in-polygon
testing uses OpenCV's own cv2.pointPolygonTest rather than adding a
shapely dependency — for a handful of zones per camera this is more
than fast enough, and keeps requirements.txt to libraries you already
depend on for video I/O.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple

import cv2
import numpy as np


@dataclass
class Zone:
    zone_id: str
    name: str
    camera_id: str
    polygon: List[Tuple[float, float]]  # ordered points, in pixel coords

    def __post_init__(self) -> None:
        if len(self.polygon) < 3:
            raise ValueError(f"Zone {self.zone_id!r} needs at least 3 points, got {len(self.polygon)}")
        self._contour = np.array(self.polygon, dtype=np.float32).reshape((-1, 1, 2))

    def contains(self, point: Tuple[float, float]) -> bool:
        """True if `point` is inside (or exactly on the edge of) the polygon."""
        result = cv2.pointPolygonTest(self._contour, (float(point[0]), float(point[1])), measureDist=False)
        return result >= 0

    def draw(self, image, color: Tuple[int, int, int] = (0, 0, 255), thickness: int = 2):
        pts = np.array(self.polygon, dtype=np.int32).reshape((-1, 1, 2))
        cv2.polylines(image, [pts], isClosed=True, color=color, thickness=thickness)
        label_pt = (int(self.polygon[0][0]), max(int(self.polygon[0][1]) - 10, 0))
        cv2.putText(image, self.name, label_pt, cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
        return image
