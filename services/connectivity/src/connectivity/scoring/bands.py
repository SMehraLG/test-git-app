"""Score-to-status band mapping (pure functions, no I/O)."""

from __future__ import annotations

from typing import Literal

StatusBand = Literal["excellent", "good", "degraded", "critical"]

_THRESHOLDS: tuple[tuple[float, StatusBand], ...] = (
    (80.0, "excellent"),
    (60.0, "good"),
    (40.0, "degraded"),
)


def score_to_band(score: float) -> StatusBand:
    """Map a 0-100 score to a status band.

    Boundaries: >=80 excellent, >=60 good, >=40 degraded, else critical.
    Higher band wins at exact boundary values.
    """
    for threshold, band in _THRESHOLDS:
        if score >= threshold:
            return band
    return "critical"
