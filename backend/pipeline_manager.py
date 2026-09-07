"""Spawns and tracks AI-node pipeline subprocesses (scripts/run_camera_pipeline.py)
so a camera can be added and started from the UI's "Add Camera" button
instead of typing a python command in a terminal.

Cross-platform note, stated plainly rather than glossed over: pipeline
shutdown uses subprocess.Popen.terminate(), which on POSIX sends
SIGTERM (a signal the child *could* catch to clean up gracefully) but
on Windows calls TerminateProcess — an immediate hard kill with no
chance for the child to run any cleanup code, regardless of what
signal handling exists in run_camera_pipeline.py. Since the actual
demo machine is Windows, this is effectively always a hard stop, not
a graceful one. That's an acceptable simplification for a hackathon
tool (the OS reclaims file/camera handles when the process dies
either way), not a hidden gap — noted here so it isn't a surprise
later if a "did it clean up properly" question comes up.
"""
from __future__ import annotations

import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional


@dataclass
class PipelineHandle:
    camera_id: str
    source: str
    proc: subprocess.Popen
    log_path: Path
    started_at: float

    def is_running(self) -> bool:
        return self.proc.poll() is None

    def stop(self, timeout: float = 5.0) -> None:
        self.proc.terminate()
        try:
            self.proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            self.proc.kill()
            self.proc.wait(timeout=timeout)


class PipelineManager:
    def __init__(self, project_root: Path) -> None:
        self.project_root = Path(project_root)
        self._pipelines: Dict[str, PipelineHandle] = {}
        self._log_files: Dict[str, "TextIO"] = {}

    def start(
        self,
        camera_id: str,
        source: str,
        zones_path: Optional[str] = None,
        anpr_zones_path: Optional[str] = None,
        backend_url: str = "http://127.0.0.1:8000",
        device: str = "auto",
        ocr_gpu: str = "auto",
    ) -> PipelineHandle:
        existing = self._pipelines.get(camera_id)
        if existing and existing.is_running():
            raise ValueError(f"A pipeline for {camera_id!r} is already running (pid {existing.proc.pid})")

        log_dir = self.project_root / "data" / "pipeline_logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_path = log_dir / f"{camera_id}.log"

        cmd = [
            sys.executable, "-u",
            str(self.project_root / "scripts" / "run_camera_pipeline.py"),
            "--source", source,
            "--camera-id", camera_id,
            "--backend-url", backend_url,
            "--device", device,
            "--ocr-gpu", ocr_gpu,
        ]
        if zones_path:
            cmd += ["--zones", zones_path]
        if anpr_zones_path:
            cmd += ["--anpr-zones", anpr_zones_path]

        log_file = open(log_path, "w", encoding="utf-8", errors="replace")
        proc = subprocess.Popen(
            cmd,
            cwd=str(self.project_root),
            stdout=log_file,
            stderr=subprocess.STDOUT,
        )

        handle = PipelineHandle(camera_id=camera_id, source=source, proc=proc, log_path=log_path, started_at=time.time())
        self._pipelines[camera_id] = handle
        self._log_files[camera_id] = log_file
        return handle

    def stop(self, camera_id: str) -> None:
        handle = self._pipelines.get(camera_id)
        if handle is None:
            raise KeyError(camera_id)
        handle.stop()
        log_file = self._log_files.pop(camera_id, None)
        if log_file:
            log_file.close()
        del self._pipelines[camera_id]

    def list(self) -> List[dict]:
        return [
            {
                "camera_id": h.camera_id,
                "source": h.source,
                "running": h.is_running(),
                "pid": h.proc.pid,
                "started_at": h.started_at,
            }
            for h in self._pipelines.values()
        ]

    def get_log_tail(self, camera_id: str, lines: int = 50) -> str:
        handle = self._pipelines.get(camera_id)
        if handle is None or not handle.log_path.exists():
            return ""
        text = handle.log_path.read_text(encoding="utf-8", errors="replace")
        return "\n".join(text.splitlines()[-lines:])

    def stop_all(self) -> None:
        for camera_id in list(self._pipelines.keys()):
            try:
                self.stop(camera_id)
            except Exception:
                pass
