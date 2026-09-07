"""Interactive polygon editor for defining a restricted zone on a
camera's frame — Phase 3's "polygon editor" piece.

Opens the FIRST frame of --source in a window. Controls:
    left click   - add a point
    z            - undo last point
    c            - clear all points
    s / enter    - save zone (needs >= 3 points) and exit
    q / esc      - quit without saving

Requires a display — this won't run over SSH without X forwarding, or
in a headless/CI environment (this repo was built and tested in one,
which is why this file only wraps the mouse/window loop around
zone_config.save_zone(), the part that's already unit-tested without a
display). On the 4060 laptop with a screen attached, this just works.

Run:
    python scripts/draw_zone.py --source data/sample_videos/vtest_pedestrians.avi --camera-id CAM-01 --zone-id restricted-1 --name "Fence Line"
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import cv2

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from vision.event_engine.zone_config import save_zone

_points: list[tuple[int, int]] = []


def _on_mouse(event, x, y, flags, param) -> None:
    if event == cv2.EVENT_LBUTTONDOWN:
        _points.append((x, y))


def _draw(frame):
    display = frame.copy()
    for i, pt in enumerate(_points):
        cv2.circle(display, pt, 5, (0, 0, 255), -1)
        if i > 0:
            cv2.line(display, _points[i - 1], pt, (0, 0, 255), 2)
    if len(_points) >= 3:
        cv2.line(display, _points[-1], _points[0], (0, 0, 255), 1)  # preview the closing edge
    cv2.putText(display, f"{len(_points)} points | left-click add, z undo, c clear, s save, q quit",
                (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 2)
    return display


def main() -> None:
    parser = argparse.ArgumentParser(description="Draw a restricted zone polygon on a video frame")
    parser.add_argument("--source", required=True, help="Video file path, or webcam index")
    parser.add_argument("--camera-id", required=True)
    parser.add_argument("--zone-id", default="restricted-1")
    parser.add_argument("--name", default="Restricted Zone")
    parser.add_argument("--config-dir", default="data/zones")
    args = parser.parse_args()

    source = int(args.source) if args.source.isdigit() else args.source
    cap = cv2.VideoCapture(source)
    if not cap.isOpened():
        raise SystemExit(f"Could not open source: {args.source}")
    ok, frame = cap.read()
    cap.release()
    if not ok:
        raise SystemExit("Could not read a frame from source")

    window = "Draw zone (left-click add, z undo, c clear, s save, q quit)"
    cv2.namedWindow(window)
    cv2.setMouseCallback(window, _on_mouse)

    while True:
        cv2.imshow(window, _draw(frame))
        key = cv2.waitKey(20) & 0xFF

        if key in (ord("q"), 27):
            print("Cancelled — nothing saved.")
            break
        elif key == ord("z") and _points:
            _points.pop()
        elif key == ord("c"):
            _points.clear()
        elif key in (ord("s"), 13):
            if len(_points) < 3:
                print("Need at least 3 points before saving.")
                continue
            out_path = Path(args.config_dir) / f"{args.camera_id}.json"
            save_zone(
                path=str(out_path),
                camera_id=args.camera_id,
                zone_id=args.zone_id,
                name=args.name,
                polygon=_points,
            )
            print(f"Saved zone {args.zone_id!r} ({len(_points)} points) -> {out_path}")
            break

    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
