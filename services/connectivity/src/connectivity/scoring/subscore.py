"""Tier-relative per-component subscores (pure functions, no I/O)."""

from __future__ import annotations


def download_subscore(performance_ratio: float) -> float:
    """Return 0-100 download subscore from speed_mbps / provisioned_mbps ratio."""
    return max(0.0, min(100.0, performance_ratio * 100.0))


def upload_subscore(performance_ratio: float) -> float:
    """Return 0-100 upload subscore from speed_mbps / provisioned_mbps ratio."""
    return max(0.0, min(100.0, performance_ratio * 100.0))


def latency_subscore(rtt_avg_ms: float, tier_rtt_ms: float) -> float:
    """Return 0-100 latency subscore from actual vs tier target RTT (ms).

    Score is 100 when rtt_avg_ms is at or below the tier target, declining
    proportionally as RTT increases beyond it.

    Raises:
        ValueError: if tier_rtt_ms is not positive.
    """
    if tier_rtt_ms <= 0.0:
        raise ValueError(f"tier_rtt_ms must be positive, got {tier_rtt_ms}")
    if rtt_avg_ms <= 0.0:
        return 100.0
    return max(0.0, min(100.0, 100.0 * tier_rtt_ms / rtt_avg_ms))
