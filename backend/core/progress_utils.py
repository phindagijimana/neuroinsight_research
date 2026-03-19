"""
Progress utilities for consistent job reporting.

Progress is quantized to coarse increments for UI stability and predictable
reporting across concurrent jobs.
"""

from __future__ import annotations

import os

_ALLOWED_INCREMENTS = {5, 10, 15}


def get_progress_increment() -> int:
    """Return configured progress increment (allowed: 5, 10, 15)."""
    raw = os.getenv("NIR_PROGRESS_INCREMENT", "10").strip()
    try:
        value = int(raw)
    except ValueError:
        return 10
    return value if value in _ALLOWED_INCREMENTS else 10


def quantize_progress(value: int | float, increment: int | None = None) -> int:
    """Quantize progress to configured increment while preserving 100."""
    try:
        pct = int(value)
    except Exception:
        pct = 0
    pct = max(0, min(100, pct))
    if pct >= 100:
        return 100
    step = increment if increment in _ALLOWED_INCREMENTS else get_progress_increment()
    return (pct // step) * step

