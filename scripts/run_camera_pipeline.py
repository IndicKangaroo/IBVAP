"""Unified per-camera pipeline — the process the backend's
PipelineManager launches when you click "Add Camera" in the UI,
instead of you running run_phase4_demo.py and run_phase5_demo.py by
hand in separate terminals.

Combines what were previously two separate demo scripts:
tracking + intrusion zone events (Phase 3/4) AND ANPR (Phase 5) run
together in one process per camera, both pushing to the backend. Zone
configs are optional — a camera can run detection/tracking with no
intrusion zone or ANPR checkpoint configured yet (e.g. right after
being added via the UI, before a zone is drawn); it just won't
generate zone-based events until one exists.

Long-running by design (no --max-frames limit by default, and file
sources loop by default) — this is meant to run for the duration of a
demo, not exit after a fixed frame count like the earlier phase-N demo
scripts did.

Not meant to be run by hand under normal use — see
backend/pipeline_manager.py, which launches this as a subprocess. It's
still a plain CLI script for direct use / debugging if you need it.
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from anpr.engine import ANPREngine
from anpr.ocr_reader import PlateOCR
from vision.event_engine.engine import EventEngine
from vision.event_engine.zone_config import load_zones
from vision.tracking.tracker import Tracker
from vision.video_ingest.reader import FrameReader

try:
    import cv2
    import requests
except ImportError as e:
    print(f"Missing dependency: {e}. Run `pip install -r requirements.txt` first.", file=sys.stderr)
    raise


def load_zones_if_exists(path: str | None):
    if not path or not Path(path).exists():
        return []
    return load_zones(path)


def make_backend_pusher(backend_url: str, endpoint: str, payload_fn):
    session = requests.Session()

    def push(obj) -> None:
        try:
            resp = session.post(f"{backend_url}{endpoint}", json=payload_fn(obj), timeout=2)
            resp.raise_for_status()
        except requests.RequestException as e:
            print(f"  -> backend push to {endpoint} FAILED (continuing locally): {e}", flush=True)

    return push


def main() -> None:
    parser = argparse.ArgumentParser(description="IBVAP unified per-camera pipeline")
    parser.add_argument("--source", required=True, help="Video file path, or webcam index")
    parser.add_argument("--camera-id", required=True)
    parser.add_argument("--zones", default=None, help="Restricted-zone config JSON (optional)")
    parser.add_argument("--anpr-zones", default=None, help="ANPR trigger-zone config JSON (optional)")
    parser.add_argument("--backend-url", default="http://127.0.0.1:8000")
    parser.add_argument("--model", default=Tracker.DEFAULT_MODEL)
    parser.add_argument("--conf", type=float, default=0.4)
    parser.add_argument("--device", default="auto")
    parser.add_argument("--ocr-gpu", default="auto")
    parser.add_argument("--evidence-dir", default="data/evidence")
    parser.add_argument("--anpr-evidence-dir", default="data/anpr_evidence")
    parser.add_argument("--events-log", default=None, help="Per-camera event log path (default: data/events_<camera_id>.jsonl)")
    parser.add_argument("--anpr-results-log", default=None)
    parser.add_argument("--max-frames", type=int, default=None, help="Stop after N frames (default: run indefinitely)")
    parser.add_argument("--no-loop", action="store_true", help="Don't restart a file source from frame 0 when it ends")
    args = parser.parse_args()

    events_log = args.events_log or f"data/events_{args.camera_id}.jsonl"
    anpr_log = args.anpr_results_log or f"data/anpr_results_{args.camera_id}.jsonl"

    source = int(args.source) if str(args.source).isdigit() else args.source
    is_file_source = not isinstance(source, int)

    print(f"[{args.camera_id}] starting pipeline: source={args.source} device={args.device}", flush=True)

    reader = FrameReader(source=source, camera_id=args.camera_id, loop=is_file_source and not args.no_loop)
    tracker = Tracker(model_path=args.model, conf_threshold=args.conf, device=args.device)

    intrusion_zones = load_zones_if_exists(args.zones)
    anpr_zones = load_zones_if_exists(args.anpr_zones)
    print(f"[{args.camera_id}] intrusion zones: {[z.name for z in intrusion_zones]}", flush=True)
    print(f"[{args.camera_id}] ANPR zones: {[z.name for z in anpr_zones]}", flush=True)

    from dataclasses import asdict

    event_engine = EventEngine(
        zones=intrusion_zones,
        evidence_dir=args.evidence_dir,
        events_log_path=events_log,
        on_event=make_backend_pusher(args.backend_url, "/api/events", lambda e: asdict(e)),
    )

    anpr_engine = None
    if anpr_zones:
        ocr = PlateOCR(gpu=args.ocr_gpu)
        anpr_engine = ANPREngine(
            trigger_zones=anpr_zones,
            ocr=ocr,
            evidence_dir=args.anpr_evidence_dir,
            results_log_path=anpr_log,
            on_result=make_backend_pusher(args.backend_url, "/api/anpr", lambda r: asdict(r)),
        )

    frame_count = 0
    start_time = time.time()

    try:
        for frame in reader:
            tracked = tracker.track(frame)
            events = event_engine.process(tracked, frame_image=frame.image)
            for ev in events:
                print(f"[{args.camera_id}][EVENT] {ev.type} | zone={ev.zone_name} | track={ev.track_id} ({ev.cls}) | conf={ev.confidence:.2f}", flush=True)

            if anpr_engine is not None:
                results = anpr_engine.process(tracked, frame.image)
                for r in results:
                    label = r.plate_text if r.plate_text else "(nothing legible)"
                    print(f"[{args.camera_id}][ANPR] track={r.track_id} | plate={label!r} | conf={r.confidence:.2f}", flush=True)

            frame_count += 1
            if frame_count % 60 == 0:
                elapsed = time.time() - start_time
                fps = frame_count / elapsed if elapsed > 0 else 0.0
                print(f"[{args.camera_id}] frame {frame_count} | {fps:.1f} FPS", flush=True)

            if args.max_frames and frame_count >= args.max_frames:
                break
    except KeyboardInterrupt:
        pass
    finally:
        reader.release()

    print(f"[{args.camera_id}] pipeline stopped after {frame_count} frames", flush=True)


if __name__ == "__main__":
    main()
