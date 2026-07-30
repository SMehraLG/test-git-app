"""Connectivity score service — orchestrates measurement queries and scoring.

Queries operator-scoped, partition-pruned aggregates from BigQuery via
the MeasurementRepository, delegates to the pure scoring functions, and
returns a ConnectivityScorePayload or signals not-found.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from connectivity.config.settings import Settings
from connectivity.models.score import (
    ConnectivityScorePayload,
    MetricScore,
)
from connectivity.repositories.measurements import (
    LatencyAggregate,
    MeasurementRepository,
    SpeedAggregate,
)
from connectivity.scoring import (
    composite_score,
    download_subscore,
    latency_subscore,
    score_to_band,
    upload_subscore,
)
from connectivity.security.auth import CallerScope


class NoMeasurementsError(Exception):
    """Raised when no measurements exist for the customer in the window."""


async def compute_score(
    customer_id: str,
    scope: CallerScope,
    repo: MeasurementRepository,
    settings: Settings,
) -> ConnectivityScorePayload:
    download = await repo.get_download_aggregate(customer_id, scope)
    upload = await repo.get_upload_aggregate(customer_id, scope)
    latency = await repo.get_latency_aggregate(customer_id, scope)

    if download is None and upload is None and latency is None:
        raise NoMeasurementsError(customer_id)

    dl_score = _score_speed(download, download_subscore)
    ul_score = _score_speed(upload, upload_subscore)
    lat_score = _score_latency(latency, settings.latency_target_ms)

    score = composite_score(
        download=dl_score.sub_score if dl_score else None,
        upload=ul_score.sub_score if ul_score else None,
        latency=lat_score.sub_score if lat_score else None,
    )
    status = score_to_band(score)

    window_start, window_end = _resolve_window(download, upload, latency)
    total_count = sum(m.sample_count for m in (download, upload, latency) if m is not None)

    return ConnectivityScorePayload(
        customer_id=customer_id,
        score=score,
        status=status,
        window_start=window_start,
        window_end=window_end,
        measurements_considered=total_count,
        download=dl_score,
        upload=ul_score,
        latency=lat_score,
    )


def _score_speed(
    agg: SpeedAggregate | None,
    scorer: Callable[[float], float],
) -> MetricScore | None:
    if agg is None or agg.avg_provisioned_mbps <= 0:
        return None
    ratio = agg.avg_speed_mbps / agg.avg_provisioned_mbps
    return MetricScore(sub_score=scorer(ratio), sample_count=agg.sample_count)


def _score_latency(agg: LatencyAggregate | None, target_ms: float) -> MetricScore | None:
    if agg is None:
        return None
    return MetricScore(
        sub_score=latency_subscore(agg.avg_rtt_ms, target_ms),
        sample_count=agg.sample_count,
    )


def _resolve_window(
    download: SpeedAggregate | None,
    upload: SpeedAggregate | None,
    latency: LatencyAggregate | None,
) -> tuple[datetime, datetime]:
    starts = []
    ends = []
    for agg in (download, upload, latency):
        if agg is not None:
            starts.append(agg.window_start)
            ends.append(agg.window_end)
    return min(starts), max(ends)
