"""Integration tests for GET /api/v1/customer/{customer_id}/connectivity-score."""

from __future__ import annotations

import hashlib
import os
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from connectivity.adapters.bigquery.base import BigQueryAdapter
from connectivity.config.settings import get_settings
from connectivity.dependencies import get_bq_adapter


def _dl_row(
    speed: float = 80.0,
    prov: float = 100.0,
    count: int = 10,
) -> list[dict[str, Any]]:
    return [
        {
            "avg_speed_mbps": speed,
            "avg_provisioned_mbps": prov,
            "sample_count": count,
            "window_start": datetime(2026, 7, 1, tzinfo=UTC),
            "window_end": datetime(2026, 7, 30, tzinfo=UTC),
        }
    ]


def _ul_row(
    speed: float = 20.0,
    prov: float = 25.0,
    count: int = 5,
) -> list[dict[str, Any]]:
    return [
        {
            "avg_speed_mbps": speed,
            "avg_provisioned_mbps": prov,
            "sample_count": count,
            "window_start": datetime(2026, 7, 1, tzinfo=UTC),
            "window_end": datetime(2026, 7, 30, tzinfo=UTC),
        }
    ]


def _lat_row(
    rtt: float = 25.0,
    count: int = 8,
) -> list[dict[str, Any]]:
    return [
        {
            "avg_rtt_ms": rtt,
            "sample_count": count,
            "window_start": datetime(2026, 7, 1, tzinfo=UTC),
            "window_end": datetime(2026, 7, 30, tzinfo=UTC),
        }
    ]


def _stub_adapter(
    dl: list[dict[str, Any]] | None = None,
    ul: list[dict[str, Any]] | None = None,
    lat: list[dict[str, Any]] | None = None,
) -> AsyncMock:
    """Stub BigQueryAdapter that returns different results per table."""
    adapter = AsyncMock(spec=BigQueryAdapter)
    adapter.dataset = "test_ds"

    async def route_query(sql: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        if "fact_httpget" in sql:
            return dl or []
        if "fact_httppost" in sql:
            return ul or []
        if "fact_udplatency" in sql:
            return lat or []
        return []

    adapter.query.side_effect = route_query
    adapter.health_check.return_value = True
    return adapter


def _score_url(customer_id: str = "cust-123") -> str:
    return f"/api/v1/customer/{customer_id}/connectivity-score"


@pytest.fixture
def _env_defaults():
    """Ensure settings needed by the score endpoint are set."""
    prev = {
        k: os.environ.get(k)
        for k in (
            "CONNECTIVITY_BQ_DATASET_UK",
            "CONNECTIVITY_BQ_DATASET_EU",
            "CONNECTIVITY_LATENCY_TARGET_MS",
        )
    }
    os.environ["CONNECTIVITY_BQ_DATASET_UK"] = "uk_ds"
    os.environ["CONNECTIVITY_BQ_DATASET_EU"] = "eu_ds"
    os.environ["CONNECTIVITY_LATENCY_TARGET_MS"] = "50.0"
    get_settings.cache_clear()
    yield
    for k, v in prev.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v
    get_settings.cache_clear()


@pytest.fixture
async def score_client(
    _env_defaults: None,
) -> AsyncClient:
    """Async test client with a stub BQ adapter routed per table."""
    get_settings.cache_clear()
    from connectivity.main import app

    stub = _stub_adapter(dl=_dl_row(), ul=_ul_row(), lat=_lat_row())
    app.dependency_overrides[get_bq_adapter] = lambda: stub

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest.fixture
async def empty_client(
    _env_defaults: None,
) -> AsyncClient:
    """Client with adapter returning no rows — simulates missing customer."""
    get_settings.cache_clear()
    from connectivity.main import app

    stub = _stub_adapter()
    app.dependency_overrides[get_bq_adapter] = lambda: stub

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


class TestScoreEndpoint:
    async def test_returns_scored_response(self, score_client: AsyncClient) -> None:
        resp = await score_client.get(_score_url())
        assert resp.status_code == 200
        body = resp.json()
        assert "data" in body
        data = body["data"]
        assert data["customer_id"] == "cust-123"
        assert 0 <= data["score"] <= 100
        assert data["status"] in ("excellent", "good", "degraded", "critical")
        assert data["download"] is not None
        assert data["upload"] is not None
        assert data["latency"] is not None
        assert data["measurements_considered"] == 23

    async def test_404_when_no_measurements(self, empty_client: AsyncClient) -> None:
        resp = await empty_client.get(_score_url())
        assert resp.status_code == 404
        body = resp.json()
        assert body["errors"][0]["code"] == "NOT_FOUND"
        assert "cust-123" in body["errors"][0]["message"]

    async def test_partial_metrics_still_returns_score(self, _env_defaults: None) -> None:
        get_settings.cache_clear()
        from connectivity.main import app

        stub = _stub_adapter(dl=_dl_row())
        app.dependency_overrides[get_bq_adapter] = lambda: stub

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.get(_score_url())

        app.dependency_overrides.clear()

        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["download"] is not None
        assert data["upload"] is None
        assert data["latency"] is None

    async def test_response_contains_no_internal_ids(self, score_client: AsyncClient) -> None:
        resp = await score_client.get(_score_url())
        body = resp.json()
        data = body["data"]
        assert "unit_id" not in data
        assert "line_id" not in data
        assert "mac" not in data
        assert "operator" not in data

    async def test_window_bounds_present(self, score_client: AsyncClient) -> None:
        resp = await score_client.get(_score_url())
        data = resp.json()["data"]
        assert "window_start" in data
        assert "window_end" in data


@pytest.mark.integration
class TestScoreAuth:
    async def test_rejects_missing_key_when_enabled(self, _env_defaults: None) -> None:
        os.environ["CONNECTIVITY_API_KEY_ENABLED"] = "true"
        key = "test-key-12345"
        os.environ["CONNECTIVITY_API_KEY"] = hashlib.sha256(key.encode()).hexdigest()
        os.environ["CONNECTIVITY_API_KEY_SCOPE_COUNTRY"] = "UK"
        os.environ["CONNECTIVITY_API_KEY_SCOPE_OPERATOR"] = "virginmedia"
        os.environ["CONNECTIVITY_API_KEY_SCOPE_BRAND"] = "vm"
        get_settings.cache_clear()

        from connectivity.main import app

        stub = _stub_adapter(dl=_dl_row())
        app.dependency_overrides[get_bq_adapter] = lambda: stub

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.get(_score_url())

        app.dependency_overrides.clear()
        os.environ["CONNECTIVITY_API_KEY_ENABLED"] = "false"
        os.environ.pop("CONNECTIVITY_API_KEY", None)
        get_settings.cache_clear()

        assert resp.status_code == 401

    async def test_accepts_valid_key(self, _env_defaults: None) -> None:
        key = "test-key-12345"
        os.environ["CONNECTIVITY_API_KEY_ENABLED"] = "true"
        os.environ["CONNECTIVITY_API_KEY"] = hashlib.sha256(key.encode()).hexdigest()
        os.environ["CONNECTIVITY_API_KEY_SCOPE_COUNTRY"] = "UK"
        os.environ["CONNECTIVITY_API_KEY_SCOPE_OPERATOR"] = "virginmedia"
        os.environ["CONNECTIVITY_API_KEY_SCOPE_BRAND"] = "vm"
        get_settings.cache_clear()

        from connectivity.main import app

        stub = _stub_adapter(dl=_dl_row())
        app.dependency_overrides[get_bq_adapter] = lambda: stub

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.get(_score_url(), headers={"X-API-Key": key})

        app.dependency_overrides.clear()
        os.environ["CONNECTIVITY_API_KEY_ENABLED"] = "false"
        os.environ.pop("CONNECTIVITY_API_KEY", None)
        get_settings.cache_clear()

        assert resp.status_code == 200
