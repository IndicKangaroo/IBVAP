"""OCR wrapper — Phase 5.

Wraps EasyOCR (the guide's other named option, alongside PaddleOCR).
Kept as a thin wrapper on purpose — swapping to PaddleOCR later is a
one-file change here, not a rewrite of anpr/engine.py.
"""
from __future__ import annotations

from typing import List, Optional, Tuple

import easyocr
import torch


class PlateOCR:
    def __init__(self, languages: Optional[List[str]] = None, gpu="auto") -> None:
        """
        Args:
            gpu: "auto" picks CUDA if available (same convention as
                vision.tracking.tracker.Tracker); or a bool; or the
                strings "true"/"false" (accepted because this is
                commonly passed straight from an argparse string flag
                — bool("false") is True in Python, which silently
                does the wrong thing, so string values are parsed
                explicitly here instead of blindly cast with bool()).
        """
        if isinstance(gpu, str):
            gpu_lower = gpu.lower()
            if gpu_lower == "auto":
                use_gpu = torch.cuda.is_available()
            elif gpu_lower in ("true", "1", "yes"):
                use_gpu = True
            elif gpu_lower in ("false", "0", "no"):
                use_gpu = False
            else:
                raise ValueError(f"Invalid gpu value: {gpu!r} (expected 'auto', 'true', or 'false')")
        else:
            use_gpu = bool(gpu)

        self.reader = easyocr.Reader(languages or ["en"], gpu=use_gpu)
        print(f"[PlateOCR] gpu={use_gpu}")

    def read(self, plate_image) -> Tuple[Optional[str], float]:
        """Returns (best_text, confidence), or (None, 0.0) if nothing
        readable. Confidence is EasyOCR's own per-detection score,
        passed through as-is — not adjusted or "corrected", since the
        guide is explicit that OCR output is a recognition result with
        a confidence score, not something to silently rewrite into
        false certainty.
        """
        if plate_image is None or plate_image.size == 0:
            return None, 0.0

        results = self.reader.readtext(plate_image)
        if not results:
            return None, 0.0

        # A crop can contain multiple text fragments (frame trim,
        # stickers, etc.) — take the highest-confidence one rather
        # than concatenating everything found.
        best = max(results, key=lambda r: r[2])
        _, text, confidence = best
        return text, float(confidence)
