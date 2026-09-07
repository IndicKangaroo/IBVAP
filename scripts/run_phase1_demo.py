"""Phase 1 done-criteria check: read one video, detect person/vehicle,
draw stable boxes + confidence, save the annotated result.

Run:
    python scripts/run_phase1_demo.py --source data/sample_videos/demo.mp4

With no --source, falls back to webcam index 0. Run this from the
ibvap/ project root so the `vision` package resolves.
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import cv2

# Allow running this script directly (python scripts/run_phase1_demo.py)
# without needing PYTHONPATH set or the package installed.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from vision.detection.detector import Detector
from vision.video_ingest.reader import FrameReader

_BOX_COLORS = {"person": (0, 200, 0), "vehicle": (0, 140, 255)}  # BGR


def draw_detections(image, detections):
    for d in detections:
        x1, y1, x2, y2 = (int(v) for v in d.bbox)
        color = _BOX_COLORS.get(d.cls, (255, 255, 255))
        cv2.rectangle(image, (x1, y1), (x2, y2), color, 2)
        label = f"{d.cls} {d.confidence:.2f}"
        cv2.putText(image, label, (x1, max(y1 - 8, 0)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
    return image


def main() -> None:
    parser = argparse.ArgumentParser(description="IBVAP Phase 1: detection smoke test")
    parser.add_argument("--source", default="0", help="Video file path, or webcam index (default: 0)")
    parser.add_argument("--camera-id", default="CAM-01")
    parser.add_argument("--output", default="output_phase1.mp4")
    parser.add_argument("--model", default=Detector.DEFAULT_MODEL)
    parser.add_argument("--conf", type=float, default=0.4)
    parser.add_argument("--max-frames", type=int, default=None, help="Stop after N frames (useful for quick tests)")
    args = parser.parse_args()

    source = int(args.source) if args.source.isdigit() else args.source

    reader = FrameReader(source=source, camera_id=args.camera_id)
    detector = Detector(model_path=args.model, conf_threshold=args.conf)

    writer = None
    frame_count = 0
    start_time = time.time()

    try:
        for frame in reader:
            detections = detector.detect(frame)
            annotated = draw_detections(frame.image.copy(), detections)

            if writer is None:
                h, w = annotated.shape[:2]
                fourcc = cv2.VideoWriter_fourcc(*"mp4v")
                writer = cv2.VideoWriter(args.output, fourcc, 20.0, (w, h))
            writer.write(annotated)

            frame_count += 1
            if frame_count % 30 == 0:
                elapsed = time.time() - start_time
                fps = frame_count / elapsed if elapsed > 0 else 0.0
                print(f"[{args.camera_id}] frame {frame_count} | {fps:.1f} FPS | {len(detections)} detections")

            if args.max_frames and frame_count >= args.max_frames:
                break
    finally:
        if writer is not None:
            writer.release()
        reader.release()

    print(f"Done. {frame_count} frames processed -> {args.output}")


if __name__ == "__main__":
    main()
