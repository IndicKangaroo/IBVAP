"""Plate text normalization — Phase 5.

Deliberately conservative: uppercase and strip non-alphanumeric
characters, plus a basic length sanity check. Does NOT attempt
character-level "corrections" (guessing O vs 0, I vs 1, etc.) — the
guide is explicit that OCR output should be stored as a recognition
result with a confidence score, not silently rewritten into something
that looks more certain than it is. Tighten `is_plausible` with a
country/state-specific regex once you know your demo plates' format.
"""
from __future__ import annotations

import re

_ALNUM = re.compile(r"[^A-Z0-9]")


def normalize(raw_text: str) -> str:
    return _ALNUM.sub("", raw_text.upper())


def is_plausible(normalized_text: str, min_len: int = 4, max_len: int = 10) -> bool:
    return min_len <= len(normalized_text) <= max_len
