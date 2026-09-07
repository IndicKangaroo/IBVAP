"""Phase 5 done-criteria check: a vehicle crossing an ANPR trigger zone
gets a plate read attempt — once per vehicle, not every frame — with
the result (text + confidence, or an honest "nothing legible") pushed
to the backend.

Requires an ANPR trigger zone config (same format/tool as restricted
zones — see scripts/draw_zone.py) and the backend running:
    uvicorn backend.main:app --reload

Run:
    python scripts/run_phase5_demo.py --source data/sample_videos/vtest_pedestrians.avi --anpr-zones data/zones/CAM-01-anpr.json
"""
from __future__ import annotations

import argparse
import sys
import time
from dataclasses import asdict
from pathlib import Path

import cv2
import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from anpr.engine import ANPREngine, ANPRResult
from anpr.ocr_reader import PlateOCR
from vision.event_engine.engine import reference_point
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
        zone.draw(image, color=(255, 200, 0))  # distinct color from intrusion zones
    for t in tracked:
        x1, y1, x2, y2 = (int(v) for v in t.bbox)
        color = color_for_id(t.track_id)
        cv2.rectangle(image, (x1, y1), (x2, y2), color, 2)
        cv2.putText(image, f"ID {t.track_id} {t.cls} {t.confidence:.2f}", (x1, max(y1 - 8, 0)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
        rx, ry = reference_point(t.bbox)
        cv2.circle(image, (int(rx), int(ry)), 4, color, -1)
    return image


def make_backend_pusher(backend_url: str):
    session = requests.Session()

    def push(result: ANPRResult) -> None:
        payload = asdict(result)  # field names already match ANPRResultIn
        try:
            resp = session.post(f"{backend_url}/api/anpr", json=payload, timeout=2)
            resp.raise_for_status()
            print(f"  -> pushed to backend, anpr result {resp.json()['id'][:8]}...")
        except requests.RequestException as e:
            print(f"  -> backend push FAILED (continuing locally): {e}")

    return push


def main() -> None:
    parser = argparse.ArgumentParser(description="IBVAP Phase 5: ANPR smoke test")
    parser.add_argument("--source", default="0")
    parser.add_argument("--camera-id", default="CAM-01")
    parser.add_argument("--anpr-zones", required=True, help="Path to an ANPR trigger zone config JSON")
    parser.add_argument("--backend-url", default="http://127.0.0.1:8000")
    parser.add_argument("--output", default="output_phase5.mp4")
    parser.add_argument("--model", default=Tracker.DEFAULT_MODEL)
    parser.add_argument("--conf", type=float, default=0.4)
    parser.add_argument("--device", default="auto")
    parser.add_argument("--ocr-gpu", default="auto")
    parser.add_argument("--evidence-dir", default="data/anpr_evidence")
    parser.add_argument("--results-log", default="data/anpr_results.jsonl")
    parser.add_argument("--max-frames", type=int, default=None)
    args = parser.parse_args()

    if not Path(args.anpr_zones).exists():
        raise SystemExit(
            f"ANPR zone config not found: {args.anpr_zones}\n"
            f"Create one first: python scripts/draw_zone.py --source {args.source} --camera-id {args.camera_id} "
            f"--zone-id checkpoint-1 --name \"ANPR Checkpoint\" --config-dir <dir for this file>"
        )

    source = int(args.source) if args.source.isdigit() else args.source

    reader = FrameReader(source=source, camera_id=args.camera_id)
    tracker = Tracker(model_path=args.model, conf_threshold=args.conf, device=args.device)
    zones = load_zones(args.anpr_zones)
    ocr = PlateOCR(gpu=args.ocr_gpu)
    engine = ANPREngine(
        trigger_zones=zones,
        ocr=ocr,
        evidence_dir=args.evidence_dir,
        results_log_path=args.results_log,
        on_result=make_backend_pusher(args.backend_url),
    )

    print(f"Loaded {len(zones)} ANPR trigger zone(s) for {args.camera_id}: {[z.name for z in zones]}")

    writer = None
    frame_count = 0
    total_triggers = 0
    start_time = time.time()

    try:
        for frame in reader:
            tracked = tracker.track(frame)
            results = engine.process(tracked, frame.image)

            for r in results:
                total_triggers += 1
                label = r.plate_text if r.plate_text else "(nothing legible)"
                print(f"[ANPR] track={r.track_id} | plate={label!r} | conf={r.confidence:.2f} | plausible={r.plausible}")

            annotated = draw_frame(frame.image.copy(), tracked, zones)
            if writer is None:
                h, w = annotated.shape[:2]
                fourcc = cv2.VideoWriter_fourcc(*"mp4v")
                writer = cv2.VideoWriter(args.output, fourcc, 20.0, (w, h))
            writer.write(annotated)

            frame_count += 1
            if frame_count % 30 == 0:
                elapsed = time.time() - start_time
                fps = frame_count / elapsed if elapsed > 0 else 0.0
                print(f"[{args.camera_id}] frame {frame_count} | {fps:.1f} FPS | {total_triggers} ANPR triggers so far")

            if args.max_frames and frame_count >= args.max_frames:
                break
    finally:
        if writer is not None:
            writer.release()
        reader.release()

    print(f"Done. {frame_count} frames processed -> {args.output}")
    print(f"Total ANPR triggers: {total_triggers}")


if __name__ == "__main__":
    main()
