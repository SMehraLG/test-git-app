"""Unit tests for the score service — scoring orchestration logic."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock

import pytest

from connectivity.config.settings import Settings
from connectivity.repositories.measurements import (
    LatencyAggregate,
    SpeedAggregate,
)
from connectivity.security.auth import CallerScope
from connectivity.services.score_service import (
    NoMeasurementsError,
    compute_score,
)

SCOPE = CallerScope(country="UK", operator="virginmedia", brand="vm")
W_START = datetime(2026, 7, 1, tzinfo=UTC)
W_END = datetime(2026, 7, 30, tzinfo=UTC)


def _settings(**overrides: Any) -> Settings:
    defaults = {"latency_target_ms": 50.0}
    defaults.update(overrides)
    return Settings(**defaults)


def _speed(
    avg_speed: float = 80.0,
    avg_prov: float = 100.0,
    count: int = 10,
) -> SpeedAggregate:
    return SpeedAggregate(
        avg_speed_mbps=avg_speed,
        avg_provisioned_mbps=avg_prov,
        sample_count=count,
        window_start=W_START,
        window_end=W_END,
    )


def _latency(avg_rtt: float = 25.0, count: int = 10) -> LatencyAggregate:
    return LatencyAggregate(
        avg_rtt_ms=avg_rtt,
        sample_count=count,
        window_start=W_START,
        window_end=W_END,
    )


def _repo(
    download: SpeedAggregate | None = None,
    upload: SpeedAggregate | None = None,
    latency: LatencyAggregate | None = None,
) -> AsyncMock:
    repo = AsyncMock()
    repo.get_download_aggregate.return_value = download
    repo.get_upload_aggregate.return_value = upload
    repo.get_latency_aggregate.return_value = latency
    return repo


class TestComputeScore:
    async def test_all_metrics_present(self) -> None:
        repo = _repo(download=_speed(), upload=_speed(20, 25), latency=_latency())
        result = await compute_score("cust-1", SCOPE, repo, _settings())

        assert result.customer_id == "cust-1"
        assert 0 <= result.score <= 100
        assert result.download is not None
        assert result.upload is not None
        assert result.latency is not None
        assert result.measurements_considered == 30

    async def test_raises_when_no_measurements(self) -> None:
        repo = _repo()
        with pytest.raises(NoMeasurementsError):
            await compute_score("cust-1", SCOPE, repo, _settings())

    async def test_partial_metrics_download_only(self) -> None:
        repo = _repo(download=_speed())
        result = await compute_score("cust-1", SCOPE, repo, _settings())

        assert result.download is not None
        assert result.upload is None
        assert result.latency is None
        assert result.score > 0

    async def test_partial_metrics_latency_only(self) -> None:
        repo = _repo(latency=_latency())
        result = await compute_score("cust-1", SCOPE, repo, _settings())

        assert result.latency is not None
        assert result.download is None
        assert result.upload is None

    async def test_window_bounds_span_all_metrics(self) -> None:
        early = datetime(2026, 6, 15, tzinfo=UTC)
        late = datetime(2026, 7, 30, tzinfo=UTC)
        dl = SpeedAggregate(
            80,
            100,
            5,
            early,
            W_END,
        )
        lat = LatencyAggregate(25, 5, W_START, late)
        repo = _repo(download=dl, latency=lat)

        result = await compute_score("cust-1", SCOPE, repo, _settings())

        assert result.window_start == early
        assert result.window_end == late

    async def test_score_reflects_scoring_functions(self) -> None:
        repo = _repo(download=_speed(100, 100), latency=_latency(50, 10))
        result = await compute_score("cust-1", SCOPE, repo, _settings())

        assert result.download is not None
        assert result.download.sub_score == 100.0
        assert result.latency is not None
        assert result.latency.sub_score == 100.0

    async def test_zero_provisioned_skips_speed_metric(self) -> None:
        repo = _repo(download=_speed(80, 0))
        result = await compute_score("cust-1", SCOPE, repo, _settings())
        assert result.download is None
        assert result.score == 0.0

    async def test_status_band_assignment(self) -> None:
        repo = _repo(download=_speed(100, 100))
        result = await compute_score("cust-1", SCOPE, repo, _settings())
        assert result.status == "excellent"

    async def test_determinism(self) -> None:
        repo = _repo(download=_speed(), upload=_speed(20, 25), latency=_latency())
        r1 = await compute_score("cust-1", SCOPE, repo, _settings())
        r2 = await compute_score("cust-1", SCOPE, repo, _settings())
        assert r1.score == r2.score
        assert r1.status == r2.status
