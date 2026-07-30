"""Weighted composite score with proportional weight redistribution (pure functions, no I/O)."""

from __future__ import annotations

_WEIGHTS: dict[str, float] = {
    "download": 0.50,
    "upload": 0.20,
    "latency": 0.30,
}


def composite_score(
    *,
    download: float | None = None,
    upload: float | None = None,
    latency: float | None = None,
) -> float:
    """Return 0-100 weighted composite score.

    Weights: download 50 %, upload 20 %, latency 30 %.  When a component is
    absent (None), its weight is redistributed proportionally among the
    components that are present.  Returns 0.0 when all components are absent.
    Output is clamped to [0, 100].
    """
    present: dict[str, float] = {}
    if download is not None:
        present["download"] = download
    if upload is not None:
        present["upload"] = upload
    if latency is not None:
        present["latency"] = latency

    if not present:
        return 0.0

    total_weight = sum(_WEIGHTS[k] for k in present)
    score = sum(_WEIGHTS[k] * v / total_weight for k, v in present.items())

    return max(0.0, min(100.0, score))
