"""Pure scoring functions for connectivity measurements."""

from __future__ import annotations

WEIGHTS: dict[str, float] = {
    "download": 0.50,
    "upload": 0.20,
    "latency": 0.30,
}

# (threshold, status) pairs ordered high-to-low; first match wins (upper-inclusive)
STATUS_BANDS: list[tuple[float, str]] = [
    (80.0, "excellent"),
    (60.0, "good"),
    (40.0, "degraded"),
    (0.0, "critical"),
]


def _clamp(value: float) -> float:
    return min(100.0, max(0.0, value))


def download_subscore(performance_ratio: float) -> float:
    """0–100 score for download: speed_mbps / provisioned_mbps * 100, capped at 100."""
    return _clamp(performance_ratio * 100.0)


def upload_subscore(performance_ratio: float) -> float:
    """0–100 score for upload: speed_mbps / provisioned_mbps * 100, capped at 100."""
    return _clamp(performance_ratio * 100.0)


def latency_subscore(rtt_avg_ms: float, latency_target_ms: float) -> float:
    """0–100 score for latency: lower RTT relative to tier target is better.

    At target RTT the score is 100; at 2× target it is 50.
    Values below target are capped at 100.
    """
    if rtt_avg_ms <= 0.0:
        return 100.0
    return _clamp((latency_target_ms / rtt_avg_ms) * 100.0)


def composite_score(
    download: float | None,
    upload: float | None,
    latency: float | None,
) -> float:
    """Weighted composite score with proportional redistribution of absent components.

    Default weights: download 50%, upload 20%, latency 30%.
    Missing components have their weight redistributed proportionally across present ones.
    Returns 0.0 when all components are absent.
    Result is deterministic and clamped to [0, 100].
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

    total_weight = sum(WEIGHTS[k] for k in present)
    score = sum(v * (WEIGHTS[k] / total_weight) for k, v in present.items())
    return _clamp(score)


def score_to_status(score: float) -> str:
    """Map a 0–100 composite score to a status band.

    Bands (upper-inclusive, higher band wins at boundaries):
      >= 80 → excellent
      >= 60 → good
      >= 40 → degraded
      <  40 → critical
    """
    for threshold, label in STATUS_BANDS:
        if score >= threshold:
            return label
    return "critical"
