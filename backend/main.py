"""IBVAP backend — Phase 4.

FastAPI service: receives events from the AI node, persists
events/incidents, and pushes live updates to connected dashboards over
WebSocket. Implements the guide's section 7 realtime flow:

    AI pipeline -> event created -> FastAPI event service -> WebSocket -> dashboard

Run from the project root:
    uvicorn backend.main:app --reload
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import List, Optional
import queue
import sys
import threading

import cv2
from fastapi import Depends, FastAPI, HTTPException, Response, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from . import models, schemas
from .db import get_db, init_db
from .pipeline_manager import PipelineManager
from .ws_manager import manager

PROJECT_ROOT = Path(__file__).resolve().parent.parent
pipeline_manager = PipelineManager(project_root=PROJECT_ROOT)

app = FastAPI(title="IBVAP Backend", version="0.1.0")

# Wide open for hackathon dev convenience — the frontend dev server runs
# on a different port than this backend, and without this every request
# gets silently blocked by the browser's CORS policy, not by anything
# visible in the network tab that explains why. Tighten allow_origins to
# your actual frontend URL before this is anything but a local demo.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def _startup() -> None:
    init_db()


@app.on_event("shutdown")
def _shutdown() -> None:
    # Without this, stopping the backend (Ctrl+C, --reload restart) would
    # orphan every running AI-node subprocess — they'd keep processing
    # video and trying to POST to a backend that's no longer there.
    pipeline_manager.stop_all()


# Evidence images are saved to disk with paths like "data/evidence/<id>.jpg"
# (see vision.event_engine.engine and anpr.engine) — that's exactly the
# path shape this mount serves, so evidence_path values returned by the
# API can be fetched directly as `${BACKEND_URL}/{evidence_path}`, no
# transformation needed. Note this exposes everything under data/ (zone
# configs, sample videos too), which is fine for a local demo but worth
# narrowing before any real deployment.
# Directory must exist before StaticFiles() is constructed (this runs at
# import time, not at the startup event above) — the repo ships data/
# with .gitkeep files, but mkdir here anyway so a fresh/pruned checkout
# doesn't fail to even start.
Path("data").mkdir(exist_ok=True)
app.mount("/data", StaticFiles(directory="data"), name="data")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/api/events", response_model=schemas.IncidentOut)
async def create_event(event_in: schemas.EventIn, db: Session = Depends(get_db)):
    # Idempotent on purpose: if the AI node retries a POST (e.g. after
    # a network blip to a cloud backend), don't create a duplicate
    # event/incident for the same event_id.
    existing = db.get(models.Event, event_in.event_id)
    if existing is not None:
        return existing.incident

    camera = db.get(models.Camera, event_in.camera_id)
    if camera is None:
        camera = models.Camera(id=event_in.camera_id, status="ONLINE", last_seen_at=datetime.utcnow())
        db.add(camera)
    else:
        camera.status = "ONLINE"
        camera.last_seen_at = datetime.utcnow()

    event = models.Event(
        id=event_in.event_id,
        camera_id=event_in.camera_id,
        zone_id=event_in.zone_id,
        zone_name=event_in.zone_name,
        track_id=event_in.track_id,
        type=event_in.type,
        cls=event_in.cls,
        confidence=event_in.confidence,
        timestamp=event_in.timestamp,
        evidence_path=event_in.evidence_path,
    )
    db.add(event)

    # Severity heuristic — deliberately simple for the MVP; a real
    # version would fold in zone criticality, time-of-day, and (if
    # built later) the behavior-engine score discussed separately.
    severity = "HIGH" if (event_in.confidence or 0) >= 0.7 else "MEDIUM"
    incident = models.Incident(event_id=event.id, severity=severity, status="ACTIVE")
    db.add(incident)

    db.commit()
    db.refresh(incident)

    await manager.broadcast({
        "type": "incident_created",
        "data": schemas.IncidentOut.model_validate(incident).model_dump(mode="json"),
    })
    return incident


@app.get("/api/events", response_model=List[schemas.EventOut])
def list_events(camera_id: Optional[str] = None, limit: int = 100, db: Session = Depends(get_db)):
    q = db.query(models.Event)
    if camera_id:
        q = q.filter(models.Event.camera_id == camera_id)
    return q.order_by(models.Event.created_at.desc()).limit(limit).all()


@app.get("/api/incidents", response_model=List[schemas.IncidentOut])
def list_incidents(status: Optional[str] = None, limit: int = 100, db: Session = Depends(get_db)):
    q = db.query(models.Incident)
    if status:
        q = q.filter(models.Incident.status == status)
    return q.order_by(models.Incident.created_at.desc()).limit(limit).all()


@app.patch("/api/incidents/{incident_id}", response_model=schemas.IncidentOut)
async def update_incident(incident_id: str, update: schemas.IncidentStatusUpdate, db: Session = Depends(get_db)):
    incident = db.get(models.Incident, incident_id)
    if incident is None:
        raise HTTPException(status_code=404, detail="Incident not found")

    if update.status not in {"ACTIVE", "ACKNOWLEDGED", "RESOLVED"}:
        raise HTTPException(status_code=400, detail="status must be ACTIVE, ACKNOWLEDGED, or RESOLVED")

    incident.status = update.status
    incident.resolved_at = datetime.utcnow() if update.status == "RESOLVED" else None
    db.commit()
    db.refresh(incident)

    await manager.broadcast({
        "type": "incident_updated",
        "data": schemas.IncidentOut.model_validate(incident).model_dump(mode="json"),
    })
    return incident


@app.get("/api/cameras", response_model=List[schemas.CameraOut])
def list_cameras(db: Session = Depends(get_db)):
    return db.query(models.Camera).all()


@app.post("/api/anpr", response_model=schemas.ANPRResultOut)
async def create_anpr_result(result_in: schemas.ANPRResultIn, db: Session = Depends(get_db)):
    existing = db.get(models.ANPRResult, result_in.result_id)
    if existing is not None:
        return existing

    camera = db.get(models.Camera, result_in.camera_id)
    if camera is None:
        camera = models.Camera(id=result_in.camera_id, status="ONLINE", last_seen_at=datetime.utcnow())
        db.add(camera)

    result = models.ANPRResult(
        id=result_in.result_id,
        camera_id=result_in.camera_id,
        track_id=result_in.track_id,
        plate_text=result_in.plate_text,
        confidence=result_in.confidence,
        plausible=result_in.plausible,
        timestamp=result_in.timestamp,
        evidence_path=result_in.evidence_path,
    )
    db.add(result)
    db.commit()
    db.refresh(result)

    await manager.broadcast({
        "type": "anpr_result",
        "data": schemas.ANPRResultOut.model_validate(result).model_dump(mode="json"),
    })
    return result


@app.get("/api/anpr", response_model=List[schemas.ANPRResultOut])
def list_anpr_results(camera_id: Optional[str] = None, limit: int = 100, db: Session = Depends(get_db)):
    q = db.query(models.ANPRResult)
    if camera_id:
        q = q.filter(models.ANPRResult.camera_id == camera_id)
    return q.order_by(models.ANPRResult.created_at.desc()).limit(limit).all()


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await manager.connect(ws)
    try:
        while True:
            await ws.receive_text()  # dashboard has nothing to send; just keeps the connection open
    except WebSocketDisconnect:
        manager.disconnect(ws)


# ---------------------------------------------------------------------
# Camera/pipeline management — the "no terminal" layer. Everything below
# lets the UI add a camera, draw its zones, and start/stop its AI-node
# process, none of which existed before this was all typed by hand per
# camera in separate terminal windows.
# ---------------------------------------------------------------------

@app.get("/api/sample-videos")
def list_sample_videos():
    """Files the UI's camera-source picker can offer without the user
    typing a path — anything already staged in data/sample_videos/."""
    d = PROJECT_ROOT / "data" / "sample_videos"
    if not d.exists():
        return []
    exts = {".mp4", ".avi", ".mov", ".mkv"}
    return sorted(f"data/sample_videos/{p.name}" for p in d.iterdir() if p.suffix.lower() in exts)


@app.get("/api/preview-frame")
def preview_frame(source: str):
    """Returns the first frame of `source` as a JPEG — what the web
    zone editor draws on top of. Runs on the backend machine (same
    physical machine as any attached camera, per this project's
    single-machine setup), so a webcam index works here the same way
    it works for the pipeline itself.

    Bounded with a hard timeout on purpose: cv2.VideoCapture has no
    built-in timeout and is known to hang indefinitely on Windows for
    a bad/busy webcam index (a real issue hit while testing this, not
    a hypothetical) — without this, a bad source would leave the
    browser's "Loading preview..." spinning forever with no error and
    no way to tell what went wrong. This guarantees the HTTP request
    itself always returns within ~6s; if the underlying OS call is
    still stuck after that, the background thread is abandoned
    (harmless — it's a daemon thread) rather than blocking the response.
    """
    src = int(source) if source.isdigit() else source
    result: "queue.Queue" = queue.Queue()

    def _grab():
        # CAP_DSHOW avoids a known slow/hanging default-backend
        # (MSMF) behavior on Windows when opening webcam indices.
        # For file/RTSP sources, force CAP_FFMPEG explicitly rather
        # than a platform default — Windows' default backend has much
        # weaker legacy-codec support, which can hang or fail on an
        # old/unusual codec (see vision/video_ingest/reader.py for the
        # fuller reasoning; same fix applied in both places), falling
        # back to the platform default if FFMPEG itself isn't available.
        if isinstance(src, int) and sys.platform == "win32":
            cap = cv2.VideoCapture(src, cv2.CAP_DSHOW)
        elif isinstance(src, str):
            cap = cv2.VideoCapture(src, cv2.CAP_FFMPEG)
            if not cap.isOpened():
                cap.release()
                cap = cv2.VideoCapture(src)
        else:
            cap = cv2.VideoCapture(src)
        try:
            if not cap.isOpened():
                result.put(("error", f"Could not open source: {source}"))
                return
            ok, frame = cap.read()
            if not ok:
                result.put(("error", f"Could not read a frame from source: {source}"))
                return
            result.put(("ok", frame))
        finally:
            cap.release()

    threading.Thread(target=_grab, daemon=True).start()
    try:
        status, payload = result.get(timeout=6.0)
    except queue.Empty:
        raise HTTPException(
            status_code=504,
            detail=f"Timed out (6s) opening source: {source!r}. If this is a webcam index, "
                   f"check it's not in use by another app; if it's a file path, check it's correct.",
        )

    if status == "error":
        raise HTTPException(status_code=400, detail=payload)

    ok, buf = cv2.imencode(".jpg", payload)
    if not ok:
        raise HTTPException(status_code=500, detail="Failed to encode preview frame")
    return Response(content=buf.tobytes(), media_type="image/jpeg")


@app.post("/api/zones")
def create_zone(req: schemas.ZoneCreateRequest):
    if req.kind not in ("intrusion", "anpr"):
        raise HTTPException(status_code=400, detail="kind must be 'intrusion' or 'anpr'")
    if len(req.polygon) < 3:
        raise HTTPException(status_code=400, detail="polygon needs at least 3 points")

    from vision.event_engine.zone_config import save_zone  # local import: vision/ isn't needed unless this endpoint is hit

    suffix = "" if req.kind == "intrusion" else "-anpr"
    rel_path = f"data/zones/{req.camera_id}{suffix}.json"
    save_zone(
        path=str(PROJECT_ROOT / rel_path),
        camera_id=req.camera_id,
        zone_id=req.zone_id,
        name=req.name,
        polygon=[tuple(p) for p in req.polygon],
    )
    return {"path": rel_path}


@app.post("/api/pipelines", response_model=schemas.PipelineOut)
def start_pipeline(req: schemas.PipelineStartRequest, db: Session = Depends(get_db)):
    try:
        handle = pipeline_manager.start(
            camera_id=req.camera_id,
            source=req.source,
            zones_path=req.zones_path,
            anpr_zones_path=req.anpr_zones_path,
            device=req.device,
            ocr_gpu=req.ocr_gpu,
        )
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))

    # Register the camera immediately, not on its first event — a
    # camera with no zones configured (a valid, skippable choice in
    # the Add Camera flow) would otherwise never appear anywhere in
    # the UI despite genuinely running, since it would never fire a
    # zone event to trigger the auto-registration in create_event().
    camera = db.get(models.Camera, req.camera_id)
    if camera is None:
        db.add(models.Camera(id=req.camera_id, status="ONLINE", last_seen_at=datetime.utcnow()))
        db.commit()

    return {
        "camera_id": handle.camera_id, "source": handle.source,
        "running": handle.is_running(), "pid": handle.proc.pid, "started_at": handle.started_at,
    }


@app.get("/api/pipelines", response_model=List[schemas.PipelineOut])
def list_pipelines():
    return pipeline_manager.list()


@app.delete("/api/pipelines/{camera_id}")
def stop_pipeline(camera_id: str):
    try:
        pipeline_manager.stop(camera_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="No running pipeline for that camera_id")
    return {"stopped": camera_id}


@app.get("/api/pipelines/{camera_id}/log")
def get_pipeline_log(camera_id: str, lines: int = 50):
    return {"log": pipeline_manager.get_log_tail(camera_id, lines=lines)}


# ---------------------------------------------------------------------
# Serve the built frontend so `uvicorn backend.main:app` is the ONLY
# command needed for backend + UI together. Must be mounted LAST — a
# mount at "/" registered before the API routes above would shadow all
# of them. Guarded on the directory existing so a backend-only checkout
# (frontend not yet built) still starts instead of crashing at import
# time — see run_demo.py, which builds it first if missing.
# ---------------------------------------------------------------------
_frontend_dist = PROJECT_ROOT / "frontend" / "dist"
if _frontend_dist.exists():
    app.mount("/", StaticFiles(directory=str(_frontend_dist), html=True), name="frontend")
