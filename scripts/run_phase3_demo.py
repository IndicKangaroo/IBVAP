"""Phase 3 done-criteria check: one zone crossing creates exactly one
intrusion event (not one event per frame the object stays inside).

Requires a zone config for the camera — create one interactively with:
    python scripts/draw_zone.py --source data/sample_videos/your_clip.mp4 --camera-id CAM-01

Run:
    python scripts/run_phase3_demo.py --source data/sample_videos/vtest_pedestrians.avi --zones data/zones/CAM-01.json
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import cv2

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from vision.event_engine.engine import EventEngine, reference_point
from vision.event_engine.zone_config import load_zones
from vision.tracking.tracker import Tracker
from vision.video_ingest.reader import FrameReader

_PALETTE = [
    (66, 135, 245), (245, 66, 90), (66, 245, 141), (245, 188, 66),
    (197, 66, 245), (66, 245, 233), (245, 66, 194), (152, 245, 66),
]


def color_for_id(track_id: int) -> tuple[int, int, int]:
    return _PALETTE[track_id % len(_PALETTE)]


def draw_frame(image, tracked, zones):
    for zone in zones:
        zone.draw(image)
    for t in tracked:
        x1, y1, x2, y2 = (int(v) for v in t.bbox)
        color = color_for_id(t.track_id)
        cv2.rectangle(image, (x1, y1), (x2, y2), color, 2)
        label = f"ID {t.track_id} {t.cls} {t.confidence:.2f}"
        cv2.putText(image, label, (x1, max(y1 - 8, 0)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
        rx, ry = reference_point(t.bbox)
        cv2.circle(image, (int(rx), int(ry)), 4, color, -1)  # ground-plane reference point used for zone tests
    return image


def main() -> None:
    parser = argparse.ArgumentParser(description="IBVAP Phase 3: zone/event smoke test")
    parser.add_argument("--source", default="0", help="Video file path, or webcam index (default: 0)")
    parser.add_argument("--camera-id", default="CAM-01")
    parser.add_argument("--zones", required=True, help="Path to a zone config JSON (see scripts/draw_zone.py)")
    parser.add_argument("--output", default="output_phase3.mp4")
    parser.add_argument("--model", default=Tracker.DEFAULT_MODEL)
    parser.add_argument("--conf", type=float, default=0.4)
    parser.add_argument("--device", default="auto")
    parser.add_argument("--evidence-dir", default="data/evidence")
    parser.add_argument("--events-log", default="data/events.jsonl")
    parser.add_argument("--max-frames", type=int, default=None)
    args = parser.parse_args()

    if not Path(args.zones).exists():
        raise SystemExit(
            f"Zone config not found: {args.zones}\n"
            f"Create one first: python scripts/draw_zone.py --source {args.source} --camera-id {args.camera_id}"
        )

    source = int(args.source) if args.source.isdigit() else args.source

    reader = FrameReader(source=source, camera_id=args.camera_id)
    tracker = Tracker(model_path=args.model, conf_threshold=args.conf, device=args.device)
    zones = load_zones(args.zones)
    engine = EventEngine(zones=zones, evidence_dir=args.evidence_dir, events_log_path=args.events_log)

    print(f"Loaded {len(zones)} zone(s) for {args.camera_id}: {[z.name for z in zones]}")

    writer = None
    frame_count = 0
    total_events = 0
    start_time = time.time()

    try:
        for frame in reader:
            tracked = tracker.track(frame)
            events = engine.process(tracked, frame_image=frame.image)

            for ev in events:
                total_events += 1
                print(f"[EVENT] {ev.type} | zone={ev.zone_name} | track={ev.track_id} ({ev.cls}) "
                      f"| conf={ev.confidence:.2f} | evidence={ev.evidence_path}")

            annotated = draw_frame(frame.image.copy(), tracked, zones)
            if events:
                cv2.putText(annotated, "INTRUSION DETECTED", (20, 40),
                            cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 255), 3)

            if writer is None:
                h, w = annotated.shape[:2]
                fourcc = cv2.VideoWriter_fourcc(*"mp4v")
                writer = cv2.VideoWriter(args.output, fourcc, 20.0, (w, h))
            writer.write(annotated)

            frame_count += 1
            if frame_count % 30 == 0:
                elapsed = time.time() - start_time
                fps = frame_count / elapsed if elapsed > 0 else 0.0
                print(f"[{args.camera_id}] frame {frame_count} | {fps:.1f} FPS | {total_events} events so far")

            if args.max_frames and frame_count >= args.max_frames:
                break
    finally:
        if writer is not None:
            writer.release()
        reader.release()

    print(f"Done. {frame_count} frames processed -> {args.output}")
    print(f"Total intrusion events: {total_events}")
    print(f"Events log: {args.events_log}")


if __name__ == "__main__":
    main()
