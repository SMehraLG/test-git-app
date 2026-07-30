"""Unit tests for the measurement repository — partition-pruned queries and tenant routing."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock

import pytest

from connectivity.config.settings import Settings
from connectivity.repositories.measurements import (
    LatencyAggregate,
    MeasurementRepository,
    SpeedAggregate,
    _resolve_dataset,
)
from connectivity.security.auth import CallerScope

UK_VM = CallerScope(country="UK", operator="virginmedia", brand="vm")
UK_O2 = CallerScope(country="UK", operator="o2uk", brand="o2")
EU_DE = CallerScope(country="DE", operator="telefonica", brand="movistar")


def _settings(**overrides: Any) -> Settings:
    defaults = {
        "bq_project": "test-project",
        "bq_dataset": "default_ds",
        "bq_dataset_uk": "uk_ds",
        "bq_dataset_eu": "eu_ds",
        "latency_target_ms": 50.0,
    }
    defaults.update(overrides)
    return Settings(**defaults)


def _mock_adapter(rows: list[dict[str, Any]] | None = None) -> AsyncMock:
    adapter = AsyncMock()
    adapter.query.return_value = rows or []
    return adapter


class TestResolveDataset:
    def test_uk_vm_routes_to_uk_dataset(self) -> None:
        assert _resolve_dataset(UK_VM, _settings()) == "uk_ds"

    def test_uk_o2_routes_to_uk_dataset(self) -> None:
        assert _resolve_dataset(UK_O2, _settings()) == "uk_ds"

    def test_eu_routes_to_eu_dataset(self) -> None:
        assert _resolve_dataset(EU_DE, _settings()) == "eu_ds"

    def test_fallback_to_bq_dataset_when_uk_unset(self) -> None:
        assert _resolve_dataset(UK_VM, _settings(bq_dataset_uk="")) == "default_ds"

    def test_fallback_to_bq_dataset_when_eu_unset(self) -> None:
        assert _resolve_dataset(EU_DE, _settings(bq_dataset_eu="")) == "default_ds"


class TestDownloadAggregate:
    async def test_returns_aggregate_from_query_result(self) -> None:
        rows = [
            {
                "avg_speed_mbps": 80.0,
                "avg_provisioned_mbps": 100.0,
                "sample_count": 42,
                "window_start": datetime(2026, 7, 1, tzinfo=timezone.utc),
                "window_end": datetime(2026, 7, 30, tzinfo=timezone.utc),
            }
        ]
        adapter = _mock_adapter(rows)
        repo = MeasurementRepository(adapter, _settings())

        result = await repo.get_download_aggregate("cust-1", UK_VM)

        assert isinstance(result, SpeedAggregate)
        assert result.avg_speed_mbps == 80.0
        assert result.sample_count == 42

    async def test_returns_none_when_no_rows(self) -> None:
        repo = MeasurementRepository(_mock_adapter([]), _settings())
        assert await repo.get_download_aggregate("cust-1", UK_VM) is None

    async def test_returns_none_when_sample_count_zero(self) -> None:
        rows = [
            {
                "avg_speed_mbps": None,
                "avg_provisioned_mbps": None,
                "sample_count": 0,
                "window_start": None,
                "window_end": None,
            }
        ]
        repo = MeasurementRepository(_mock_adapter(rows), _settings())
        assert await repo.get_download_aggregate("cust-1", UK_VM) is None

    async def test_sql_includes_partition_predicates(self) -> None:
        adapter = _mock_adapter()
        repo = MeasurementRepository(adapter, _settings())
        await repo.get_download_aggregate("cust-1", UK_VM)

        sql = adapter.query.call_args[0][0]
        assert "dtime_utc >= @window_start" in sql
        assert "dtime_utc < @window_end" in sql

    async def test_sql_includes_tenant_predicates(self) -> None:
        adapter = _mock_adapter()
        repo = MeasurementRepository(adapter, _settings())
        await repo.get_download_aggregate("cust-1", UK_VM)

        sql = adapter.query.call_args[0][0]
        assert "country = @country" in sql
        assert "operator = @operator" in sql
        assert "brand = @brand" in sql

        params = adapter.query.call_args[0][1]
        assert params["country"] == "UK"
        assert params["operator"] == "virginmedia"
        assert params["brand"] == "vm"

    async def test_sql_references_correct_table_for_uk(self) -> None:
        adapter = _mock_adapter()
        repo = MeasurementRepository(adapter, _settings())
        await repo.get_download_aggregate("cust-1", UK_VM)

        sql = adapter.query.call_args[0][0]
        assert "`test-project.uk_ds.fact_httpget`" in sql

    async def test_sql_references_correct_table_for_eu(self) -> None:
        adapter = _mock_adapter()
        repo = MeasurementRepository(adapter, _settings())
        await repo.get_download_aggregate("cust-1", EU_DE)

        sql = adapter.query.call_args[0][0]
        assert "`test-project.eu_ds.fact_httpget`" in sql

    async def test_passes_customer_id_as_param(self) -> None:
        adapter = _mock_adapter()
        repo = MeasurementRepository(adapter, _settings())
        await repo.get_download_aggregate("cust-xyz", UK_VM)

        params = adapter.query.call_args[0][1]
        assert params["customer_id"] == "cust-xyz"


class TestUploadAggregate:
    async def test_queries_fact_httppost(self) -> None:
        adapter = _mock_adapter()
        repo = MeasurementRepository(adapter, _settings())
        await repo.get_upload_aggregate("cust-1", UK_VM)

        sql = adapter.query.call_args[0][0]
        assert "fact_httppost" in sql

    async def test_returns_aggregate(self) -> None:
        rows = [
            {
                "avg_speed_mbps": 20.0,
                "avg_provisioned_mbps": 25.0,
                "sample_count": 10,
                "window_start": datetime(2026, 7, 1, tzinfo=timezone.utc),
                "window_end": datetime(2026, 7, 30, tzinfo=timezone.utc),
            }
        ]
        repo = MeasurementRepository(_mock_adapter(rows), _settings())
        result = await repo.get_upload_aggregate("cust-1", UK_VM)
        assert result is not None
        assert result.avg_speed_mbps == 20.0


class TestLatencyAggregate:
    async def test_queries_fact_udplatency(self) -> None:
        adapter = _mock_adapter()
        repo = MeasurementRepository(adapter, _settings())
        await repo.get_latency_aggregate("cust-1", UK_VM)

        sql = adapter.query.call_args[0][0]
        assert "fact_udplatency" in sql

    async def test_returns_latency_aggregate(self) -> None:
        rows = [
            {
                "avg_rtt_ms": 25.0,
                "sample_count": 30,
                "window_start": datetime(2026, 7, 1, tzinfo=timezone.utc),
                "window_end": datetime(2026, 7, 30, tzinfo=timezone.utc),
            }
        ]
        repo = MeasurementRepository(_mock_adapter(rows), _settings())
        result = await repo.get_latency_aggregate("cust-1", UK_VM)
        assert isinstance(result, LatencyAggregate)
        assert result.avg_rtt_ms == 25.0
        assert result.sample_count == 30

    async def test_returns_none_on_empty(self) -> None:
        repo = MeasurementRepository(_mock_adapter([]), _settings())
        assert await repo.get_latency_aggregate("cust-1", UK_VM) is None
