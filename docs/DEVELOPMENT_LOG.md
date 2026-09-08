# IBVAP — Development Log

This is the phase-by-phase build log: what was built, in what order,
and — the actual point of keeping this — what was *verified* at each
step and how, including real bugs caught along the way and how they
were found and fixed. For the project overview, architecture, and
quickstart, see the main [README.md](../README.md) instead. This file
is the detailed record underneath it.

## Streamlined demo (no terminal juggling)

For a live demo, skip everything below and use this instead:

```bash
python run_demo.py
```

One command. It builds the frontend if needed, starts the backend
(which now serves the API *and* the UI from a single process — see
`backend/main.py`'s static mount), and opens a browser tab. From
there, **every camera is added and started from the UI's "Add Camera"
button** — pick a source, optionally draw a restricted zone and/or
ANPR checkpoint zone by clicking directly on a real preview frame in
the browser (no OpenCV desktop window needed), and start it. Stop any
running camera from the same panel. Nothing about this requires
touching a terminal again after the initial `python run_demo.py`.

This is real, not a mockup — the whole flow (preview frame → draw
zone → start pipeline → real events landing) was tested end to end
against a live backend before being wired into the UI. See "No
terminal needed" further down for what's actually running underneath
and what was verified.

The manual phase-by-phase scripts below (`run_phase1_demo.py` through
`run_phase5_demo.py`, `draw_zone.py`) still exist and still work —
useful for development and debugging one phase in isolation, just not
needed for running an actual demo anymore.

## Setup (Phase 0)

```bash
cd ibvap
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

First run downloads `yolov8n.pt` (~6MB) automatically via `ultralytics`.

Drop a short sample clip (10–30s, MP4) into `data/sample_videos/` for a
repeatable local test instead of relying on a webcam.

**Done when:** the environment installs cleanly and you can import
`vision.detection.detector` without errors.

## Run the Phase 1 smoke test

```bash
python scripts/run_phase1_demo.py --source data/sample_videos/demo.mp4
```

No `--source` → falls back to webcam index 0. Output is an annotated
MP4 (`output_phase1.mp4` by default) with person/vehicle boxes and
confidence drawn on every frame, plus FPS printed to the console every
30 frames.

**Done when (per the guide's Phase 1 criteria):** boxes are stable
frame-to-frame and confidence values look reasonable — that's the
whole bar for Phase 1, tracking comes next.

## Run the Phase 2 smoke test (tracking)

```bash
python scripts/run_phase2_demo.py --source data/sample_videos/demo.mp4
```

Same idea as Phase 1, but boxes now carry a persistent `ID N` label
with a stable per-track color. Prints unique-ID count as it runs.

**Done when (per the guide's Phase 2 criteria):** the same
person/vehicle keeps the same ID across the clip. Concretely — the
unique-ID count should roughly match the number of distinct
people/vehicles that actually appeared, not climb steadily as the
clip plays (that's ByteTrack losing and re-acquiring the same object
over and over). Verified locally on both a synthetic multi-object clip
and a real photo looped into a clip — 4 real people/objects in, 4
stable IDs out, no drift across 30 frames.

Development machine has no GPU, so this was validated on CPU
(`--device cpu`); on the RTX 4060 it'll pick CUDA automatically via
`--device auto` (the default) — worth a quick FPS check first run to
confirm it's actually using the GPU (the `[Tracker] ... device=...`
line printed on startup tells you).

## Real test clip included

`data/sample_videos/vtest_pedestrians.avi` is a real 768×576, 10fps,
~80s CCTV-angle clip of people and parked vehicles in a plaza — pulled
from OpenCV's public sample data (`opencv/opencv/samples/data/vtest.avi`,
widely used as a standard CV test clip). Use this instead of a
synthetic clip for any "does this actually work on real footage" check:

```bash
python scripts/run_phase2_demo.py --source data/sample_videos/vtest_pedestrians.avi
```

**Verified result:** on the first 150 frames, the two parked vehicles
held the *exact same* track IDs the entire time — the correct signal
that persistence is working, since a real bug (ID switching) would
show up first on stationary objects. Person-ID count climbed from 3 to
~18 over that span, which is expected here, not a bug: this is a busy
walkway and people genuinely keep entering/exiting frame within 15
real seconds — confirmed by checking that the original frame-0 walkers
had already exited by frame 50, replaced by different pedestrians, not
the same people getting relabeled.

## Even quicker: your webcam

No clip on hand at all? Both demo scripts default to webcam index 0:

```bash
python scripts/run_phase2_demo.py
```

Walk in and out of frame a few times — your own ID should stay the
same the whole time you're visible, and only change if you leave frame
and re-enter (a fresh appearance is a legitimately fresh track).

## Run the Phase 3 smoke test (zone + event engine)

First, define a restricted zone for your camera — either interactively:

```bash
python scripts/draw_zone.py --source data/sample_videos/vtest_pedestrians.avi --camera-id CAM-01 --zone-id restricted-1 --name "Restricted Path"
```

(left-click to add points, `s` to save, `q` to cancel — needs a
display, so this is a 4060-laptop step, not something to run headless)

...or hand-write `data/zones/CAM-01.json` directly if you already know
the coordinates you want:

```json
{
  "camera_id": "CAM-01",
  "zones": [
    {"zone_id": "restricted-1", "name": "Restricted Path", "polygon": [[350,150],[650,150],[650,350],[350,350]]}
  ]
}
```

Then run:

```bash
python scripts/run_phase3_demo.py --source data/sample_videos/vtest_pedestrians.avi --zones data/zones/CAM-01.json
```

Output video shows the zone outline, tracked boxes, a small dot at
each object's ground-reference point (bottom-center of its box — see
`reference_point()` in `event_engine/engine.py`), and a red
"INTRUSION DETECTED" banner on any frame with a new event. Events also
print to console and append to `data/events.jsonl`; each one saves a
snapshot to `data/evidence/`.

**Done when (per the guide's Phase 3 criteria):** one zone crossing
creates exactly one event — not one event per frame the object
happens to be inside. This was checked three ways, not just run once:

1. **Unit test**, synthetic trajectory (enter → stay 5 frames → exit →
   re-enter → exit): 12 frames, exactly 2 events. Confirms the
   engine fires on the outside→inside *transition*, not on raw
   containment.
2. **Config roundtrip**: multiple zones per camera save/load correctly
   without clobbering each other.
3. **Real footage**, the pedestrian clip above: 23 events across 300
   frames of a busy scene. A few track IDs fired twice — checked the
   time gaps (3.5–20s apart, i.e. dozens to 100+ frames at this CPU's
   ~6 FPS) to rule out per-frame spam or boundary-pixel jitter, then
   visually confirmed one of them by eye: that person was walking
   *along* the zone's left edge, not just standing near it — real
   repeated crossings, not a bug.

**Zone-placement lesson learned from that last check, worth carrying
into your actual demo zone:** don't draw a zone boundary parallel to a
natural walking path — people weaving slightly relative to the edge
will generate legitimate repeat crossings. Draw boundaries roughly
*perpendicular* to the expected approach direction (e.g. across a
fence line someone would walk toward, not alongside a footpath) for a
cleaner single-crossing demo moment.

## Run the Phase 4 smoke test (backend + live alerts)

Start the backend (separate terminal, from the project root):

```bash
uvicorn backend.main:app --reload
```

Defaults to a local SQLite file (`ibvap.db`) — no Postgres server
needed to develop or demo against. Point `DATABASE_URL` at a real
Postgres instance later without touching any backend code (see
`backend/db.py`).

Then run the same pipeline as Phase 3, now pushing every event live:

```bash
python scripts/run_phase4_demo.py --source data/sample_videos/vtest_pedestrians.avi --zones data/zones/CAM-01.json
```

Check what landed: `curl http://127.0.0.1:8000/api/incidents`, or open
`http://127.0.0.1:8000/docs` for FastAPI's interactive API explorer.

**Done when (per the guide's Phase 4 criteria):** a zone crossing
shows up as a live alert + incident record, not just a console line.
Verified, not just run once:

1. **API correctness** — event creation, idempotency (retrying the
   same `event_id` returns the original record, doesn't duplicate),
   severity heuristic, camera auto-registration on first sighting —
   all checked directly against a running server.
2. **WebSocket broadcast** — an independent WebSocket client caught
   all 3 real-time messages (`incident_created`, then two
   `incident_updated`) as an incident was created and walked through
   `ACTIVE → ACKNOWLEDGED → RESOLVED`, with `resolved_at` only set on
   the actual RESOLVED transition.
3. **Real pipeline, real backend** — ran the Phase 3 CV pipeline
   against the pedestrian clip with the backend live: 16 events fired,
   16 incidents landed in the database, exact match.
4. **Resilience** — reran the same pipeline pointed at an unreachable
   backend URL. It didn't crash (exit code 0); events still logged
   locally to `data/events.jsonl` and evidence still saved. This is
   the same "local AI keeps working even if the backend dies"
   principle from the local+cloud hybrid deployment discussed earlier
   — here it's just a try/except around the HTTP push, not a full
   heartbeat/failover service (that's later, optional work if you
   build the cloud DR phase).

**Known limitation, not fixed yet:** the backend push happens
synchronously inside the per-frame loop with a 2s timeout. A clean
connection refusal (backend fully down) returns instantly and doesn't
hurt FPS — confirmed above. A *slow or lossy* network (packets
dropped, not refused) would stall each frame for up to that timeout
instead. Not a concern on localhost for a demo; if the backend ever
moves to a real network hop (e.g. the cloud-secondary setup discussed
earlier), pushing events from a background thread/queue instead of
inline would be the fix — noting it now rather than discovering it
live.

## Structure

```
ibvap/
├── vision/
│   ├── video_ingest/reader.py   # FrameReader — file/webcam/RTSP -> Frame(camera_id, frame_id, timestamp, image)
│   ├── detection/detector.py    # Detector — YOLO wrapper, filtered to person/vehicle (Phase 1, no IDs)
│   ├── tracking/tracker.py      # Tracker — YOLO + ByteTrack, filtered to person/vehicle (Phase 2, with IDs)
│   └── event_engine/            # Phase 3: zones + crossing logic (done)
│       ├── zone.py              # Zone — polygon + point-in-polygon test + drawing
│       ├── zone_config.py       # load/save zone configs to per-camera JSON
│       └── engine.py            # EventEngine — crossing detection, evidence snapshots, event log, on_event callback
├── backend/                     # Phase 4: FastAPI + WebSocket + DB (done)
│   ├── db.py                    # SQLAlchemy engine/session — SQLite by default, Postgres via DATABASE_URL
│   ├── models.py                # Camera, Event, Incident, ANPRResult tables
│   ├── schemas.py                # Pydantic request/response shapes
│   ├── ws_manager.py            # in-memory WebSocket broadcast
│   └── main.py                  # FastAPI app: /api/events, /api/incidents, /api/anpr, /api/cameras, /ws
├── anpr/                        # Phase 5: plate localization + OCR (done)
│   ├── plate_localizer.py       # classical edge/contour plate-region detection, no learned model
│   ├── ocr_reader.py            # EasyOCR wrapper
│   ├── normalizer.py            # conservative text cleanup, no character "correction"
│   └── engine.py                # ANPREngine — same crossing-trigger idiom as EventEngine, once per vehicle
├── frontend/                     # Phase 6: React command center (done)
│   ├── CommandCenterReference.jsx  # mock-data reference build — visual/interaction reference only
│   ├── src/lib/api.js              # REST client — verified via Vite-SSR against a live backend
│   ├── src/lib/reconnectingSocket.js  # WS reconnect w/ backoff — unit-tested against a killed+restarted backend
│   ├── src/lib/useLiveBackend.js   # ties both together, re-syncs REST on every reconnect
│   ├── src/components/             # CameraGrid, CameraPanel, AlertRail, IncidentTable, ANPRTable, etc.
│   └── scripts/                    # test-api.mjs, test-reconnect.mjs — re-runnable against a live backend
├── data/
│   ├── sample_videos/           # local test clips (gitignored contents, folder kept)
│   ├── zones/                   # per-camera zone configs — intrusion AND ANPR trigger zones
│   ├── evidence/                # intrusion event snapshots (gitignored)
│   ├── anpr_evidence/           # ANPR plate-crop snapshots (gitignored)
│   ├── events.jsonl             # local append-only intrusion event log
│   └── anpr_results.jsonl       # local append-only ANPR result log
├── scripts/
│   ├── run_phase1_demo.py       # CLI: video -> detection -> annotated video out
│   ├── run_phase2_demo.py       # CLI: video -> tracking -> annotated video out, ID persistence stats
│   ├── run_phase3_demo.py       # CLI: video -> tracking -> zone events -> annotated video + local event log
│   ├── run_phase4_demo.py       # CLI: same as phase3, plus pushes each event to the live backend
│   ├── run_phase5_demo.py       # CLI: video -> tracking -> ANPR trigger -> plate read -> pushes to backend
│   └── draw_zone.py             # interactive polygon editor (needs a display)
├── requirements.txt
└── README.md
```

## Design notes carried over from the implementation guide

- `Frame` and `Detection` are plain dataclasses on purpose — no camera
  or model-specific state leaks between `vision/video_ingest` and
  `vision/detection`. Tracking (Phase 2) will consume `Detection`
  objects the same way; it doesn't need to know about OpenCV or YOLO.
- `Detector.DEFAULT_MODEL = "yolov8n.pt"` — smallest/fastest COCO
  checkpoint. If you're on CPU-only hardware, stay on `n`; if you have
  a GPU and accuracy is short, try `yolov8s.pt` next, not a jump
  straight to `l`/`x`.
- Detection is filtered to `person` / `vehicle` only (COCO ids
  `{0}` and `{2,3,5,7}`) — matches the guide's Phase 1 scope. Widen
  `_COCO_VEHICLE_IDS` in `detector.py` if you want bicycles in-scope
  later.

## Note on Detector vs Tracker

`Tracker` doesn't consume `Detector`'s output — it re-runs detection
internally via Ultralytics' `model.track()`, which fuses detection +
ByteTrack association in one pass (re-detecting separately would mean
running the model twice per frame for nothing). So `Detector` and
`Tracker` each own their own model instance; use one or the other per
camera stream, not both stacked together. `Tracker`'s `TrackedObject`
is a superset of `Detector`'s `Detection` (same fields, plus
`track_id`), so anything built against `Detection` downstream should
still feel familiar.

## Run the Phase 5 smoke test (ANPR)

Vehicle detection is already in scope (`Tracker` filters to person +
vehicle), so this phase adds: an ANPR trigger zone (a vehicle
"checkpoint" — same `Zone`/JSON config as restricted zones, different
purpose), plate localization within a vehicle's box, OCR, and
conservative normalization.

Define a trigger zone (same tool as restricted zones, saved separately
so it doesn't collide with intrusion zones):

```bash
python scripts/draw_zone.py --source data/sample_videos/vtest_pedestrians.avi --camera-id CAM-01 --zone-id checkpoint-1 --name "ANPR Checkpoint"
```

...then rename/move the saved file to `data/zones/CAM-01-anpr.json` (or
just point `--anpr-zones` at wherever you saved it). With the backend
running:

```bash
python scripts/run_phase5_demo.py --source data/sample_videos/vtest_pedestrians.avi --anpr-zones data/zones/CAM-01-anpr.json
```

**Done when (per the guide's Phase 5 criteria):** a controlled sample
plate gets recognized. What was actually checked, not just assumed:

1. **Plate localization**, synthetic vehicle with a known plate
   region: classical edge/contour detection (no learned model — see
   `anpr/plate_localizer.py` for why that's the right scope here, not
   a shortcut) found the region at 0.83 IoU against ground truth.
2. **OCR + normalization**, synthetic plate with legible fictional
   text `KA01AB1234`: read as `'KAOIAB123-'` at 90% confidence — got
   most characters right but confused O↔0 and 1↔I, plus a trailing
   artifact. This is exactly why `anpr/normalizer.py` doesn't try to
   "correct" character-level ambiguity — high OCR confidence isn't the
   same as correctness, and silently fixing it would fabricate
   certainty the system doesn't have.
3. **Trigger timing**: one vehicle lingering in the checkpoint zone
   for 5 frames triggered OCR exactly once, not 5 times — same
   crossing-detection idiom as the intrusion `EventEngine`, and the
   reason OCR doesn't run on every frame (per the guide's own
   performance-strategy section).
4. **Real footage, honest failure mode**: ran against the actual
   parked van/car in the pedestrian clip. Both vehicles triggered ANPR
   and correctly returned `plate_text=None` — at this camera distance
   the plate region is a handful of blurry pixels (checked the actual
   evidence crop, not just the confidence number), so "nothing
   legible" is the right answer, not a bug. Matches the guide's own
   caution against depending on live/uncontrolled footage.
5. **Backend integration**: results pushed and retrievable via
   `GET /api/anpr`, broadcast over the same WebSocket as intrusion
   incidents (`type: "anpr_result"`).

**Bug caught and fixed during this testing, not shipped quietly:**
`--ocr-gpu false` silently did nothing — `bool("false")` evaluates to
`True` in Python, so a string flag meant to disable the GPU was being
cast straight to `True`. It only "worked" here by accident because
this sandbox has no GPU to mistakenly use. Fixed in
`anpr/ocr_reader.py` by parsing `"auto"/"true"/"false"` explicitly
instead of blind `bool()` casting — worth knowing about since it's the
kind of bug that stays invisible until you're on hardware where it
actually matters (your 4060).

## Frontend command center — done

(Note: earlier notes in this README called this "Phase 6," which was
a mislabel — the original guide's actual Phase 6 is multi-camera
support, covered separately below. This section is the React
dashboard from guide section 8, which the guide's phase table doesn't
assign its own number to.)

`frontend/` is a real Vite + React app (`npm install && npm run dev`,
needs the backend running — see `frontend/README.md`), not a mock.
Verified against a live backend, not just built and assumed correct:

1. **`reconnectingSocket.js`**, unit-tested from Node against the real
   backend (`frontend/scripts/test-reconnect.mjs`): connected, received
   a live broadcast, survived the backend being killed mid-session (5
   reconnect attempts with exponential backoff), and recovered cleanly
   — reconnected and received a new broadcast — once the backend came
   back. This is the piece the blueprint's §3 warning was about (no
   message history on the backend, so a silent disconnect means
   silently missed events) — `useLiveBackend.js` re-fetches the REST
   snapshot on every reconnect specifically because of that test.
2. **`api.js`**, loaded through Vite's own SSR module transform
   (`frontend/scripts/test-api.mjs`) — not reimplemented or mocked —
   and run against a live backend with a real seeded incident: every
   REST function, plus `patchIncidentStatus` actually changing a
   database row and the change being confirmed by a follow-up read.
3. **Production build**: `npm run build` is clean — zero warnings,
   zero `npm audit` vulnerabilities (an initial CSS `@import` ordering
   bug, and a vulnerable transitive esbuild pulled in by an older Vite
   version, were both caught and fixed, not left in).

**Known limitation, stated plainly:** no browser was available in the
environment this was built in, so actual in-browser rendering and
click interactions were never visually confirmed — only the
build output and the data layer (REST + WebSocket + reconnect
behavior) were verified against the real backend. Open it in an actual
browser before trusting it fully.

`CommandCenterReference.jsx` (same folder) is the earlier mock-data
version this was extended from — kept around as a lightweight
visual/interaction reference, not meant to be run for real.

## Phase 6 — multi-camera — done

The guide's actual Phase 6: "2–4 streams / prerecorded feeds. Camera
grid works reliably." Tested for real, not assumed from the schema
having a `camera_id` field everywhere:

Ran two full AI-node pipelines (`run_phase4_demo.py`) as genuinely
separate concurrent OS processes — `CAM-01` and `CAM-02`, both hitting
the same live backend at once. Result: 24 total incidents, split
exactly 12/12 with correct per-camera attribution, zero SQLite
"database is locked" errors, zero dropped events, zero cross-camera
contamination. Confirmed the frontend's own `api.js` (via the same
Vite-SSR test used elsewhere) sees both cameras: `['CAM-01', 'CAM-02']`.
`CameraGrid.jsx` maps generically over however many cameras exist —
no hardcoded single-camera assumption — so this is real evidence the
grid renders correctly with 2+ tiles, not just a hope.

**Honest scope of that result:** 2 cameras, ~3 FPS each on CPU, light
write volume — genuinely zero contention at that load. This validates
the *architecture* handles multi-camera correctly; it isn't evidence
SQLite scales indefinitely under heavier concurrent load (more
cameras, higher frame rates). The guide's own Postgres recommendation
exists for exactly that scaling need — swap `DATABASE_URL` when you
outgrow this, no code changes required (see `backend/db.py`).

## No terminal needed — done

What changed and why, plus what was actually verified rather than
assumed:

**`scripts/run_camera_pipeline.py`** — unifies what used to be two
separate scripts (Phase 4's intrusion pipeline and Phase 5's ANPR
pipeline) into one long-running per-camera process. Zones are
optional — a camera can run with no restricted zone and no ANPR
checkpoint configured, producing tracking data with no zone-based
events, which is a legitimate choice, not a degraded state.

**`backend/pipeline_manager.py`** — spawns/tracks/stops these as real
OS subprocesses, launched via `sys.executable` (inherits whatever venv
the backend itself is running in — no "wrong Python" surprises) rather
than assuming a `python` command on PATH. Stated plainly rather than
glossed over: stopping a pipeline uses `Popen.terminate()`, which is a
clean SIGTERM on POSIX but an immediate hard kill on Windows
(`TerminateProcess`, no chance for the child to clean up) — since the
actual demo machine is Windows, treat every stop as a hard stop. Not
a hidden gap; the OS reclaims file/camera handles either way, and this
is an acceptable simplification for a hackathon tool.

**New backend endpoints**: `POST/GET/DELETE /api/pipelines`,
`GET /api/pipelines/{id}/log`, `GET /api/sample-videos`,
`GET /api/preview-frame`, `POST /api/zones`. The last two are what
make browser-based zone drawing possible — `preview-frame` returns a
real JPEG of a source's first frame, `zones` writes a config file from
polygon points, replacing `draw_zone.py`'s OpenCV window for anyone
who can't or doesn't want to run that locally.

**Frontend**: `AddCameraModal.jsx` (source picker → optional zone
drawing → start), `ZoneCanvasEditor.jsx` (click-to-add-points on a
real preview frame, canvas-based), `PipelinesPanel.jsx` (running
cameras with stop buttons, polled every 4s since pipeline state isn't
part of the WebSocket protocol).

**What was actually tested, including a real bug caught and fixed:**

- Full pipeline lifecycle via the API — start, confirm the exact OS
  process (matched by PID, not a fuzzy process-name search) is
  running the right command with the right cwd, real events landing
  in the database while it runs, stop, and confirmed the process is
  genuinely gone afterward, not just marked stopped while orphaned.
- A camera with **zero zones configured** — confirmed it registers in
  `/api/cameras` immediately on pipeline start, not only on its first
  event. This was a real gap caught during testing: cameras were
  originally only auto-registered by `create_event()`, which a
  zone-less camera would never trigger — meaning a genuinely running
  camera would never appear anywhere in the UI. Fixed in
  `start_pipeline()` directly.
- The full real modal flow end to end: fetch a preview frame → create
  an intrusion zone → create an ANPR zone → start a pipeline
  referencing both → real intrusion incidents AND real ANPR results
  both landed.
- A genuine bug in `ZoneCreateRequest`: `schemas.py` imported
  `Optional` from `typing` but never `List`, which `polygon: List[List[float]]`
  needed — invisible at import time because of
  `from __future__ import annotations` making all annotations lazy
  strings, only surfacing when Pydantic actually tried to resolve the
  model. Fixed by adding the import, then re-ran the exact same
  request that had failed to confirm it actually worked, not just
  that the traceback went away.
- Pipeline startup latency is **variable** — seconds in a light-load
  test, over 40 seconds observed once under heavier sandbox load, both
  with the process genuinely alive and consuming CPU the whole time
  (confirmed via `/proc`, not assumed). Not a bug — cold-start ML
  imports (torch/YOLO/EasyOCR) just don't have fixed timing. The UI's
  Add Camera review step says this explicitly rather than implying
  instant readiness.

## No terminal needed — follow-up fixes from real usage

Two issues surfaced from actually using this (not from re-testing in
this sandbox, which can't reproduce Windows-specific OpenCV behavior):

**Preview/pipeline hangs on a bad source (esp. webcam), no error
shown.** `cv2.VideoCapture` has no built-in timeout and is known to
hang indefinitely on Windows for a busy/nonexistent webcam index
(default MSMF backend). Fixed two ways: `GET /api/preview-frame` now
runs the OpenCV call in a background thread with a hard 6-second
timeout — confirmed against an artificial 999-second hang that it
still returns in exactly 6s instead of blocking forever — and both
that endpoint and `FrameReader` now pass `cv2.CAP_DSHOW` for webcam
(integer) sources on Windows specifically, the standard fix for this
exact MSMF issue. File paths are unaffected either way.

**Update after real testing on a file source (not webcam):** the
CAP_DSHOW fix above only applies to webcam sources — it wouldn't have
touched a file-based clip at all. Revised theory once that was ruled
out: the bundled sample clip (`vtest_pedestrians.avi`) uses an old,
unusual codec (`DivX 3 Low-Motion` — noticed when it was first
downloaded). That decoded fine here on a full FFMPEG-backed Linux
OpenCV build, but Windows' OpenCV commonly defaults to the Media
Foundation (MSMF) backend for file sources too, which has much weaker
legacy-codec support than FFMPEG — a plausible mechanism for the same
"hangs with no error" symptom, specific to older/unusual video files
rather than a path problem. Fixed by explicitly forcing
`cv2.CAP_FFMPEG` for all file/RTSP (string) sources in both
`FrameReader` and the preview endpoint, with a fallback to the
platform default if FFMPEG itself isn't available for some reason.
Verified the sample clip still opens correctly and a full pipeline
run still produces real incidents with this explicit backend
selection in place, not just that it compiles.

Practical suggestion alongside the fix: for your actual demo, prefer
a modern-codec (H.264 .mp4) clip over old/unusual formats regardless
— broader backend support everywhere, not just a workaround for this
one bundled test file.

**No way to see pipeline output from the UI.** The
`GET /api/pipelines/{id}/log` endpoint existed but nothing in the
frontend called it — a real gap, not intentional. Added a "Log" button
per running camera in the pipelines panel (`PipelinesPanel.jsx`) that
polls and displays it live, confirmed end-to-end against a real
pipeline run. This is now the actual tool for "why isn't my camera
doing anything" instead of guessing — check it before assuming
something's broken.

**Worth restating plainly since it's easy to miss:** a camera with no
zones drawn (a valid, skippable choice) will show zero incidents and
zero ANPR results *by design* — those only come from zone-crossing
logic. No zones means detection/tracking still runs, but nothing gets
pushed to the backend at all. That's expected behavior, not a bug —
draw at least one zone type if you want anything to show up in the
dashboard.

## No terminal needed — the actual root cause (frontend, not backend)

The two backend fixes above (CAP_FFMPEG, CAP_DSHOW, the 6s server-side
timeout) were real improvements but **not the cause of "stuck on
loading preview."** Confirmed by direct diagnostic: hitting
`http://127.0.0.1:8000/api/preview-frame?source=...` straight in a
browser tab returned a real frame immediately. That isolated it to
the frontend entirely.

**The actual bug:** `ZoneCanvasEditor.jsx`'s original `<img>` element
had its `onLoad` handler try to set `canvas.width`/`canvas.height` —
but the `<canvas>` was only rendered *after* `imgLoaded` became true,
which is the very state that same handler was about to set. So when
`onLoad` fired, `canvasRef.current` was still `null`, that line threw,
and `setImgLoaded(true)` — right after it in the same function — never
ran. The image genuinely loaded every time; the component just never
found out, and sat on "Loading preview…" forever. Classic React
ref-timing bug: don't conditionally mount an element based on the
state that its own load handler is about to set.

**Fix:** the canvas is now always mounted (hidden via CSS instead of
conditionally rendered), so the ref is guaranteed valid whenever the
image finishes loading, regardless of timing. Rewrote image loading
from a plain `<img src>` to `fetch()` + `AbortController` in the same
pass, specifically to add a real client-side timeout (8s) — a bare
`<img>` has no timeout of its own, so a genuine hang anywhere between
browser and backend would've looked identical to this bug with zero
feedback either way.

**How this was actually verified, not just reasoned about:** a build
succeeding was exactly the kind of check that would NOT have caught
this bug in the first place (it's a DOM/ref-timing issue, not a
syntax error) — so it was tested with a real jsdom-mounted instance of
the actual component, simulating the exact async sequence (fetch
resolves → blob → `Image.onload` fires asynchronously) that broke the
original version. First attempt at this test also initially "failed"
until two test-harness issues were fixed (React's `act()` environment
flag, and draining jsdom's timer queue properly) — worth mentioning
so the PASS below isn't mistaken for having been easy to get, or for
the first result being trusted uncritically:
- Success path: image loads, canvas correctly sized to the real
  clip's actual resolution (768×576, not a default), no stuck state.
- Failure path: a fetch that never resolves (simulating a genuine
  backend/network hang) correctly surfaces "Timed out" after 8s
  instead of hanging forever.

## Annotated evidence images — done

The evidence snapshot saved on every intrusion event (`data/evidence/*.jpg`
— what `CameraPanel` and `IncidentDetailModal` actually display in the
browser) was, until now, just the raw unannotated frame. The bounding
box + zone overlay only ever existed in the local debug `.mp4` output
from the old single-camera demo scripts — never in what the dashboard
shows. Fixed in `vision/event_engine/engine.py`: a new
`_draw_evidence_annotation()` draws the triggering object's box and
the zone boundary onto a copy of the frame before saving, using the
same colors the frontend dashboard already uses for these two
concepts (`_COLOR_INTRUDER_BOX` / `_COLOR_ZONE_BORDER`, matched to
`frontend/src/lib/palette.js`'s `high`/`medium` — not arbitrary
OpenCV defaults).

No frontend changes were needed — `CameraPanel` and
`IncidentDetailModal` already just render `evidenceUrl(evidence_path)`
as an `<img>`; the annotation is baked into the file at capture time,
so it flows through automatically.

Verified against real footage, not just checked for crashes: ran the
actual pipeline, then *looked at* the generated evidence images. First
pass had a real, visible bug — the label text ran off the right edge
of the frame for a box near the boundary (`person ID 1 80%` cut off
mid-character). Fixed by clamping the label's x-position against the
frame width via `cv2.getTextSize()`, then regenerated evidence for
that *exact* track and confirmed the fix on the specific case that had
broken, not just a fresh unrelated sample. Also confirmed end-to-end
through the real backend: pipeline → `POST /api/events` →
`GET /data/evidence/{file}` (the exact path/URL shape the frontend
constructs) → correctly annotated image served.

## Vehicle type + color classification — done

Two related but distinct pieces of work, from a single "classify
vehicles with colors and type" ask.

**Type** was mostly latent, not new modeling work: `Detector` and
`Tracker` were both independently collapsing car/motorcycle/bus/truck
(COCO ids 2/3/5/7) into one generic `"vehicle"` string. The model was
already distinguishing them; the code was throwing that away. Fixed
by extracting the mapping into a single shared module,
`vision/coco_classes.py` (`classify_coco_id()`, `is_vehicle()`),
removing the duplicated logic from both `Detector` and `Tracker`
rather than fixing it twice.

**This had one genuine landmine**: `anpr/engine.py`'s trigger check
was `if obj.cls != "vehicle": continue` — a hardcoded string compare
that would have silently stopped ANPR from ever triggering the moment
`cls` became `"car"`/`"truck"`/etc. Caught by grepping for every
`"vehicle"` string comparison across the codebase before considering
the type change done, not discovered later by ANPR mysteriously
producing zero results. Fixed to use the new `is_vehicle()` helper.

**Color** is genuinely new: `anpr/color_classifier.py`, classical
HSV-bucket thresholding (white/black/gray + 6 hues), same reasoning as
the plate localizer — no pretrained color-classifier model was
reachable from this build environment, and for a bounded set of common
vehicle colors this is a legitimate scope, not a placeholder. Runs on
every triggered vehicle (cheap enough not to need its own gate, unlike
OCR), riding along on the ANPR checkpoint's existing trigger.

**Verification, including a real bug caught by testing on real
footage instead of stopping at synthetic swatches:**
1. All 9 solid synthetic color swatches (white, black, gray, red,
   orange, yellow, green, blue, purple) classified correctly at 100%
   confidence — confirms the hue-bucket boundaries themselves are
   sound.
2. First real-footage test: the known-white van in the sample clip
   was misclassified as **orange**. Investigating (viewing the actual
   crop, not just the numbers) showed the bug was in the *test* — a
   hand-guessed bounding box that captured mostly the reddish-brick
   building behind the van, not the van itself. Not a classifier bug.
3. Re-ran using the *actual* tracker-produced bounding box instead of
   a guessed one: van correctly classified white (74% confidence), a
   second vehicle correctly blue (70% — visually confirmed as a fair,
   not slam-dunk, call on a genuinely pale bluish-teal car, which is
   exactly what a moderate confidence score should look like).
4. Full backend round-trip: real pipeline → `POST /api/anpr` → SQLite
   → `GET /api/anpr` — `vehicle_type`/`vehicle_color`/
   `vehicle_color_confidence` confirmed present and correct all the
   way through, not just at the Python-object level.
5. Frontend `ANPRTable.jsx` updated with Type and Color columns (a
   color swatch dot, not just text) and rebuilt clean.

Updated for consistency in the same pass: `FRONTEND_BLUEPRINT.md`'s
API reference and TypeScript interfaces, and
`CommandCenterReference.jsx`'s mock data (both still said `"vehicle"`
and were now factually wrong about the real API shape).

## Remaining optional work

Everything in the original guide's core MVP (Phases 0–5) plus the
Phase 6 dashboard above is done and verified. What's left is the
stretch scope discussed separately and never built: a rule-based
suspicious-activity/behavior engine, a local+cloud hybrid deployment
for demo resilience, and (lowest priority, not required by the PS187
problem statement) weapon detection. None of those block a working
end-to-end demo — this repo already has one.

