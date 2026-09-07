"""Phase 4 done-criteria check: a zone crossing shows up as a live
alert + incident in the backend — not just a console line and a
JSONL row (that was Phase 3's bar; this one requires the backend to
actually receive it).

Requires the backend running:
    uvicorn backend.main:app --reload

Run:
    python scripts/run_phase4_demo.py --source data/sample_videos/vtest_pedestrians.avi --zones data/zones/CAM-01.json
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

from vision.event_engine.engine import EventEngine, IntrusionEvent, reference_point
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
        cv2.circle(image, (int(rx), int(ry)), 4, color, -1)
    return image


def make_backend_pusher(backend_url: str):
    """Returns an on_event callback that POSTs to the backend, but
    NEVER raises — a network blip or a dead backend must not crash
    the AI pipeline. This is the same "local intelligence keeps
    running even if the backend node is unreachable" principle behind
    the local+cloud hybrid deployment discussed earlier; here it's
    just a try/except instead of a heartbeat/failover service, since
    that's Phase 6.5+ territory, not core Phase 4.
    """
    session = requests.Session()

    def push(event: IntrusionEvent) -> None:
        payload = {k: v for k, v in asdict(event).items()}
        try:
            resp = session.post(f"{backend_url}/api/events", json=payload, timeout=2)
            resp.raise_for_status()
            print(f"  -> pushed to backend, incident {resp.json()['id'][:8]}...")
        except requests.RequestException as e:
            print(f"  -> backend push FAILED (continuing locally): {e}")

    return push


def main() -> None:
    parser = argparse.ArgumentParser(description="IBVAP Phase 4: backend integration smoke test")
    parser.add_argument("--source", default="0")
    parser.add_argument("--camera-id", default="CAM-01")
    parser.add_argument("--zones", required=True)
    parser.add_argument("--backend-url", default="http://127.0.0.1:8000")
    parser.add_argument("--output", default="output_phase4.mp4")
    parser.add_argument("--model", default=Tracker.DEFAULT_MODEL)
    parser.add_argument("--conf", type=float, default=0.4)
    parser.add_argument("--device", default="auto")
    parser.add_argument("--evidence-dir", default="data/evidence")
    parser.add_argument("--events-log", default="data/events.jsonl")
    parser.add_argument("--max-frames", type=int, default=None)
    args = parser.parse_args()

    if not Path(args.zones).exists():
        raise SystemExit(f"Zone config not found: {args.zones}")

    source = int(args.source) if args.source.isdigit() else args.source

    reader = FrameReader(source=source, camera_id=args.camera_id)
    tracker = Tracker(model_path=args.model, conf_threshold=args.conf, device=args.device)
    zones = load_zones(args.zones)
    engine = EventEngine(
        zones=zones,
        evidence_dir=args.evidence_dir,
        events_log_path=args.events_log,
        on_event=make_backend_pusher(args.backend_url),
    )

    print(f"Loaded {len(zones)} zone(s) for {args.camera_id}: {[z.name for z in zones]}")
    print(f"Pushing events to {args.backend_url}")

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
                print(f"[EVENT] {ev.type} | zone={ev.zone_name} | track={ev.track_id} ({ev.cls}) | conf={ev.confidence:.2f}")

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


if __name__ == "__main__":
    main()
