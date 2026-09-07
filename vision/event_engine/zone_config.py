"""Load/save Zone definitions to/from a per-camera JSON config file.

Kept separate from the interactive polygon editor (scripts/draw_zone.py)
on purpose: this file I/O and validation logic needs to be testable
without a display, since the editor itself can't run headless.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import List, Tuple

from .zone import Zone


def load_zones(path: str) -> List[Zone]:
    data = json.loads(Path(path).read_text())
    camera_id = data["camera_id"]
    zones = []
    for z in data.get("zones", []):
        zones.append(Zone(
            zone_id=z["zone_id"],
            name=z["name"],
            camera_id=camera_id,
            polygon=[tuple(p) for p in z["polygon"]],
        ))
    return zones


def save_zone(path: str, camera_id: str, zone_id: str, name: str, polygon: List[Tuple[float, float]]) -> None:
    """Add or replace one zone in a camera's zone config file, creating the file if it doesn't exist yet."""
    p = Path(path)
    if p.exists():
        data = json.loads(p.read_text())
    else:
        data = {"camera_id": camera_id, "zones": []}

    data["camera_id"] = camera_id
    data["zones"] = [z for z in data["zones"] if z["zone_id"] != zone_id]
    data["zones"].append({"zone_id": zone_id, "name": name, "polygon": [list(pt) for pt in polygon]})

    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=2))
