"""Unified scoring test suite: unit, integration (mock BQ adapter), and performance.

Unit tests cover band boundaries (80/60/40), weight redistribution for 1 and 2
present components, scoring determinism, and the auth dependency 401 paths.

Integration tests exercise the full HTTP pipeline via the mock BigQuery adapter
covering the happy path, both 404 cases, out-of-scope 404, and both CASAS
envelopes.

The performance test load-tests the endpoint at 2x expected peak validating
p95 < 3s.
"""

from __future__ import annotations

import asyncio
import hashlib
import os
import time
from typing import Any

import pytest
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient

from connectivity.adapters.bigquery.mock import MockBigQueryAdapter
from connectivity.config.settings import Settings, get_settings
from connectivity.dependencies import get_bq_adapter
from connectivity.scoring.bands import score_to_band
from connectivity.scoring.composite import composite_score
from connectivity.security.auth import require_api_key

SCORE_URL = "/api/v1/customers/cust-123/connectivity-score"


# ---------------------------------------------------------------------------
# Unit: band boundaries at 80 / 60 / 40
# ---------------------------------------------------------------------------


class TestBandBoundaries:
    @pytest.mark.parametrize(
        ("score", "expected"),
        [
            (100.0, "excellent"),
            (80.0, "excellent"),
            (80.1, "excellent"),
            (79.9, "good"),
            (60.0, "good"),
            (60.1, "good"),
            (59.9, "degraded"),
            (40.0, "degraded"),
            (40.1, "degraded"),
            (39.9, "critical"),
            (0.0, "critical"),
        ],
    )
    def test_boundary(self, score: float, expected: str) -> None:
        assert score_to_band(score) == expected


# ---------------------------------------------------------------------------
# Unit: weight redistribution for 1 and 2 present components
# ---------------------------------------------------------------------------


class TestWeightRedistribution:
    def test_single_download(self) -> None:
        assert composite_score(download=75.0) == pytest.approx(75.0)

    def test_single_upload(self) -> None:
        assert composite_score(upload=90.0) == pytest.approx(90.0)

    def test_single_latency(self) -> None:
        assert composite_score(latency=60.0) == pytest.approx(60.0)

    def test_two_download_upload(self) -> None:
        result = composite_score(download=80.0, upload=60.0)
        expected = (0.5 * 80.0 + 0.2 * 60.0) / 0.7
        assert result == pytest.approx(expected, rel=1e-6)

    def test_two_download_latency(self) -> None:
        result = composite_score(download=80.0, latency=60.0)
        expected = (0.5 * 80.0 + 0.3 * 60.0) / 0.8
        assert result == pytest.approx(expected, rel=1e-6)

    def test_two_upload_latency(self) -> None:
        result = composite_score(upload=50.0, latency=100.0)
        expected = (0.2 * 50.0 + 0.3 * 100.0) / 0.5
        assert result == pytest.approx(expected, rel=1e-6)

    def test_all_absent_returns_zero(self) -> None:
        assert composite_score() == 0.0


# ---------------------------------------------------------------------------
# Unit: determinism
# ---------------------------------------------------------------------------


class TestScoringDeterminism:
    def test_composite_deterministic(self) -> None:
        results = [composite_score(download=72.5, upload=45.3, latency=88.1) for _ in range(10)]
        assert len(set(results)) == 1

    def test_band_deterministic(self) -> None:
        results = [score_to_band(79.9) for _ in range(10)]
        assert len(set(results)) == 1

    def test_redistribution_deterministic(self) -> None:
        results = [composite_score(download=72.5, latency=88.1) for _ in range(10)]
        assert len(set(results)) == 1


# ---------------------------------------------------------------------------
# Unit: auth dependency 401 paths
# ---------------------------------------------------------------------------


class TestAuthDependency401:
    _SECRET = "test-api-key-secret"
    _SECRET_HASH = hashlib.sha256(_SECRET.encode()).hexdigest()

    def _auth_settings(self, **overrides: Any) -> Settings:
        defaults: dict[str, Any] = {
            "api_key_enabled": True,
            "api_key": self._SECRET_HASH,
            "api_key_scope_country": "UK",
            "api_key_scope_operator": "virginmedia",
            "api_key_scope_brand": "vm",
        }
        defaults.update(overrides)
        return Settings(**defaults)

    def test_missing_key_raises_401(self) -> None:
        with pytest.raises(HTTPException) as exc:
            require_api_key(raw_key=None, settings=self._auth_settings())
        assert exc.value.status_code == 401

    def test_invalid_key_raises_401(self) -> None:
        with pytest.raises(HTTPException) as exc:
            require_api_key(raw_key="wrong-key", settings=self._auth_settings())
        assert exc.value.status_code == 401


# ---------------------------------------------------------------------------
# Integration helpers
# ---------------------------------------------------------------------------

_AGG_ROWS_DL: list[dict[str, Any]] = [
    {
        "avg_speed_mbps": 80.0,
        "avg_provisioned_mbps": 100.0,
        "sample_count": 10,
        "window_start": "2026-07-01T00:00:00+00:00",
        "window_end": "2026-07-30T00:00:00+00:00",
    }
]

_AGG_ROWS_UL: list[dict[str, Any]] = [
    {
        "avg_speed_mbps": 20.0,
        "avg_provisioned_mbps": 25.0,
        "sample_count": 5,
        "window_start": "2026-07-01T00:00:00+00:00",
        "window_end": "2026-07-30T00:00:00+00:00",
    }
]

_AGG_ROWS_LAT: list[dict[str, Any]] = [
    {
        "avg_rtt_ms": 25.0,
        "sample_count": 8,
        "window_start": "2026-07-01T00:00:00+00:00",
        "window_end": "2026-07-30T00:00:00+00:00",
    }
]


def _seed_mock(
    adapter: MockBigQueryAdapter,
    *,
    dl: bool = True,
    ul: bool = True,
    lat: bool = True,
) -> None:
    if dl:
        adapter._tables["fact_httpget"] = list(_AGG_ROWS_DL)
    if ul:
        adapter._tables["fact_httppost"] = list(_AGG_ROWS_UL)
    if lat:
        adapter._tables["fact_udplatency"] = list(_AGG_ROWS_LAT)


@pytest.fixture
def _score_env():
    prev: dict[str, str | None] = {}
    env_vars = {
        "CONNECTIVITY_BQ_DATASET_UK": "uk_ds",
        "CONNECTIVITY_BQ_DATASET_EU": "eu_ds",
        "CONNECTIVITY_LATENCY_TARGET_MS": "50.0",
    }
    for k, v in env_vars.items():
        prev[k] = os.environ.get(k)
        os.environ[k] = v
    get_settings.cache_clear()
    yield
    for k, v in prev.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v
    get_settings.cache_clear()


# ---------------------------------------------------------------------------
# Integration: happy path via mock BigQuery adapter
# ---------------------------------------------------------------------------


class TestIntegrationHappyPath:
    async def test_all_metrics_200(self, _score_env: None) -> None:
        from connectivity.main import app

        adapter = MockBigQueryAdapter()
        _seed_mock(adapter)
        app.dependency_overrides[get_bq_adapter] = lambda: adapter
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.get(SCORE_URL)
        app.dependency_overrides.clear()

        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["customer_id"] == "cust-123"
        assert 0 <= data["score"] <= 100
        assert data["status"] in ("excellent", "good", "degraded", "critical")
        assert data["download"] is not None
        assert data["upload"] is not None
        assert data["latency"] is not None
        assert data["measurements_considered"] == 23

    async def test_partial_download_only(self, _score_env: None) -> None:
        from connectivity.main import app

        adapter = MockBigQueryAdapter()
        _seed_mock(adapter, dl=True, ul=False, lat=False)
        app.dependency_overrides[get_bq_adapter] = lambda: adapter
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.get(SCORE_URL)
        app.dependency_overrides.clear()

        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["download"] is not None
        assert data["upload"] is None
        assert data["latency"] is None
        assert data["score"] > 0


# ---------------------------------------------------------------------------
# Integration: both 404 cases
# ---------------------------------------------------------------------------


class TestIntegration404:
    async def test_empty_tables_404(self, _score_env: None) -> None:
        from connectivity.main import app

        adapter = MockBigQueryAdapter()
        app.dependency_overrides[get_bq_adapter] = lambda: adapter
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.get(SCORE_URL)
        app.dependency_overrides.clear()

        assert resp.status_code == 404
        assert resp.json()["errors"][0]["code"] == "NOT_FOUND"

    async def test_null_aggregates_404(self, _score_env: None) -> None:
        from connectivity.main import app

        adapter = MockBigQueryAdapter()
        adapter._tables["fact_httpget"] = [
            {
                "avg_speed_mbps": None,
                "avg_provisioned_mbps": None,
                "sample_count": 0,
                "window_start": None,
                "window_end": None,
            }
        ]
        app.dependency_overrides[get_bq_adapter] = lambda: adapter
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.get(SCORE_URL)
        app.dependency_overrides.clear()

        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Integration: out-of-scope 404
# ---------------------------------------------------------------------------


class TestIntegrationOutOfScope:
    async def test_unknown_customer_404(self, _score_env: None) -> None:
        from connectivity.main import app

        adapter = MockBigQueryAdapter()
        app.dependency_overrides[get_bq_adapter] = lambda: adapter
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.get("/api/v1/customers/out-of-scope-cust/connectivity-score")
        app.dependency_overrides.clear()

        assert resp.status_code == 404
        body = resp.json()
        assert "out-of-scope-cust" in body["errors"][0]["message"]


# ---------------------------------------------------------------------------
# Integration: both CASAS envelopes
# ---------------------------------------------------------------------------


class TestCASASEnvelopes:
    async def test_success_data_envelope(self, _score_env: None) -> None:
        from connectivity.main import app

        adapter = MockBigQueryAdapter()
        _seed_mock(adapter)
        app.dependency_overrides[get_bq_adapter] = lambda: adapter
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.get(SCORE_URL)
        app.dependency_overrides.clear()

        assert resp.status_code == 200
        body = resp.json()
        assert set(body.keys()) == {"data"}
        data = body["data"]
        required_keys = {
            "customer_id",
            "score",
            "status",
            "window_start",
            "window_end",
            "measurements_considered",
        }
        assert required_keys.issubset(data.keys())

    async def test_error_envelope(self, _score_env: None) -> None:
        from connectivity.main import app

        adapter = MockBigQueryAdapter()
        app.dependency_overrides[get_bq_adapter] = lambda: adapter
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.get(SCORE_URL)
        app.dependency_overrides.clear()

        assert resp.status_code == 404
        body = resp.json()
        assert "errors" in body
        assert isinstance(body["errors"], list)
        assert len(body["errors"]) >= 1
        error = body["errors"][0]
        assert "message" in error
        assert "code" in error


# ---------------------------------------------------------------------------
# Performance: load test at 2x expected peak, p95 < 3s
# ---------------------------------------------------------------------------


class TestScorePerformance:
    async def test_concurrent_load_p95_under_3s(self, _score_env: None) -> None:
        from connectivity.main import app

        adapter = MockBigQueryAdapter()
        _seed_mock(adapter)
        app.dependency_overrides[get_bq_adapter] = lambda: adapter
        transport = ASGITransport(app=app)

        concurrency = 50
        total_requests = 200
        latencies: list[float] = []

        async def fire(ac: AsyncClient) -> None:
            start = time.monotonic()
            resp = await ac.get(SCORE_URL)
            elapsed = time.monotonic() - start
            latencies.append(elapsed)
            assert resp.status_code == 200

        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            sem = asyncio.Semaphore(concurrency)

            async def bounded() -> None:
                async with sem:
                    await fire(ac)

            await asyncio.gather(*(bounded() for _ in range(total_requests)))

        app.dependency_overrides.clear()

        latencies.sort()
        p95_idx = int(len(latencies) * 0.95)
        p95 = latencies[p95_idx]
        assert p95 < 3.0, f"p95 latency {p95:.3f}s exceeds 3s threshold"
