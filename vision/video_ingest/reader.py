"""Video ingestion — Phase 0/1.

Reads frames from a local video file, webcam, or (later) an RTSP stream,
and yields them as `Frame` objects carrying camera_id, frame_id and
timestamp. Keeping this separate from detection means the AI layer never
has to know or care where a frame came from (per the IBVAP architecture:
video_ingest is independent of the model layer).
"""
from __future__ import annotations

import sys
import time
from dataclasses import dataclass
from typing import Iterator, Optional, Union

import cv2
import numpy as np


@dataclass
class Frame:
    camera_id: str
    frame_id: int
    timestamp: float          # unix epoch seconds, when the frame was read
    image: np.ndarray         # BGR frame, as returned by OpenCV


class FrameReader:
    """Iterable frame source for a file path, webcam index, or RTSP URL.

    Usage:
        reader = FrameReader(source="data/sample_videos/demo.mp4", camera_id="CAM-01")
        for frame in reader:
            ...
        reader.release()
    """

    def __init__(
        self,
        source: Union[str, int],
        camera_id: str,
        loop: bool = False,
        target_fps: Optional[float] = None,
    ) -> None:
        """
        Args:
            source: video file path, webcam index (e.g. 0), or RTSP URL.
            camera_id: logical camera identifier stamped onto every frame.
            loop: if True, restart from frame 0 when the source ends
                  (useful for a repeatable demo loop; ignored for live streams).
            target_fps: if set, frames are dropped to approximate this rate
                  instead of processing every frame at source FPS.
        """
        self.source = source
        self.camera_id = camera_id
        self.loop = loop
        self.target_fps = target_fps

        self._cap = self._open_capture(source)
        if not self._cap.isOpened():
            raise RuntimeError(f"Could not open video source: {source!r}")

        self._frame_id = 0
        self._min_frame_interval = (1.0 / target_fps) if target_fps else None
        self._last_emit_time = 0.0

    @staticmethod
    def _open_capture(source: Union[str, int]) -> cv2.VideoCapture:
        # Webcam (integer) sources: CAP_DSHOW avoids a known
        # slow/hanging default-backend (MSMF) issue on Windows.
        if isinstance(source, int) and sys.platform == "win32":
            return cv2.VideoCapture(source, cv2.CAP_DSHOW)
        # File/RTSP (string) sources: force FFMPEG explicitly rather
        # than letting OpenCV pick a platform default. Windows'
        # default (often MSMF) has much weaker legacy-codec support
        # than FFMPEG — an old/unusual codec (e.g. the bundled sample
        # clip's DivX 3) can hang or fail to open under MSMF while
        # opening fine under FFMPEG, which is available cross-platform
        # in a standard opencv-python install. Falls back to the
        # platform default if CAP_FFMPEG itself isn't available for
        # some reason, rather than hard-failing.
        cap = cv2.VideoCapture(source, cv2.CAP_FFMPEG)
        if not cap.isOpened():
            cap.release()
            cap = cv2.VideoCapture(source)
        return cap

    def __iter__(self) -> Iterator["Frame"]:
        return self

    def __next__(self) -> "Frame":
        while True:
            ok, image = self._cap.read()
            if not ok:
                if self.loop:
                    self._cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    continue
                self._cap.release()
                raise StopIteration

            now = time.time()
            if self._min_frame_interval is not None:
                elapsed = now - self._last_emit_time
                if elapsed < self._min_frame_interval:
                    continue  # drop this frame to hit target_fps
            self._last_emit_time = now

            frame = Frame(
                camera_id=self.camera_id,
                frame_id=self._frame_id,
                timestamp=now,
                image=image,
            )
            self._frame_id += 1
            return frame

    def release(self) -> None:
        self._cap.release()
