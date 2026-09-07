"""Phase 2 done-criteria check: same person/vehicle keeps the same
track_id across the clip. Each ID gets a stable color so you can
visually confirm persistence (a flickering color on the same person =
the tracker is losing and re-acquiring them, not doing its job).

Run:
    python scripts/run_phase2_demo.py --source data/sample_videos/demo.mp4

With no --source, falls back to webcam index 0.
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import cv2

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from vision.tracking.tracker import Tracker
from vision.video_ingest.reader import FrameReader

_PALETTE = [
    (66, 135, 245), (245, 66, 90), (66, 245, 141), (245, 188, 66),
    (197, 66, 245), (66, 245, 233), (245, 66, 194), (152, 245, 66),
]


def color_for_id(track_id: int) -> tuple[int, int, int]:
    return _PALETTE[track_id % len(_PALETTE)]


def draw_tracks(image, tracked):
    for t in tracked:
        x1, y1, x2, y2 = (int(v) for v in t.bbox)
        color = color_for_id(t.track_id)
        cv2.rectangle(image, (x1, y1), (x2, y2), color, 2)
        label = f"ID {t.track_id} {t.cls} {t.confidence:.2f}"
        cv2.putText(image, label, (x1, max(y1 - 8, 0)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
    return image


def main() -> None:
    parser = argparse.ArgumentParser(description="IBVAP Phase 2: tracking smoke test")
    parser.add_argument("--source", default="0", help="Video file path, or webcam index (default: 0)")
    parser.add_argument("--camera-id", default="CAM-01")
    parser.add_argument("--output", default="output_phase2.mp4")
    parser.add_argument("--model", default=Tracker.DEFAULT_MODEL)
    parser.add_argument("--conf", type=float, default=0.4)
    parser.add_argument("--tracker-config", default="bytetrack.yaml", choices=["bytetrack.yaml", "botsort.yaml"])
    parser.add_argument("--device", default="auto")
    parser.add_argument("--max-frames", type=int, default=None)
    args = parser.parse_args()

    source = int(args.source) if args.source.isdigit() else args.source

    reader = FrameReader(source=source, camera_id=args.camera_id)
    tracker = Tracker(
        model_path=args.model,
        conf_threshold=args.conf,
        tracker_config=args.tracker_config,
        device=args.device,
    )

    writer = None
    frame_count = 0
    seen_ids: set[int] = set()
    start_time = time.time()

    try:
        for frame in reader:
            tracked = tracker.track(frame)
            seen_ids.update(t.track_id for t in tracked)
            annotated = draw_tracks(frame.image.copy(), tracked)

            if writer is None:
                h, w = annotated.shape[:2]
                fourcc = cv2.VideoWriter_fourcc(*"mp4v")
                writer = cv2.VideoWriter(args.output, fourcc, 20.0, (w, h))
            writer.write(annotated)

            frame_count += 1
            if frame_count % 30 == 0:
                elapsed = time.time() - start_time
                fps = frame_count / elapsed if elapsed > 0 else 0.0
                print(f"[{args.camera_id}] frame {frame_count} | {fps:.1f} FPS | "
                      f"{len(tracked)} tracked now | {len(seen_ids)} unique IDs so far")

            if args.max_frames and frame_count >= args.max_frames:
                break
    finally:
        if writer is not None:
            writer.release()
        reader.release()

    print(f"Done. {frame_count} frames processed -> {args.output}")
    print(f"Unique track IDs seen: {sorted(seen_ids)}")
    print("Sanity check: watch how IDs behave on STATIC or slow objects (parked "
          "vehicles, a loitering person) vs a busy scene with people constantly "
          "entering/exiting frame. A parked vehicle or the same person changing "
          "ID while clearly still in frame = the tracker losing and re-acquiring "
          "them (real bug — try lowering --conf, or check source FPS isn't choppy). "
          "A rising unique-ID count in a busy scene where people keep walking in "
          "and out is expected and correct, not a failure.")


if __name__ == "__main__":
    main()
