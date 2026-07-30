"""Tests for the partition-pruned measurement repository."""

from __future__ import annotations

import pytest

from connectivity.adapters.bigquery.mock import MockBigQueryAdapter
from connectivity.repositories.measurements import (
    DatasetRouting,
    MeasurementRepository,
    _build_partition_predicate,
    _build_tenant_filter,
    _fqn,
    resolve_dataset,
)
from connectivity.security.auth import TenantScope

PROJECT = "my-gcp-project"
UK_DATASET = "connectivity_europe_west2"
EU_DATASET = "connectivity_europe_west1"


def _uk_scope(brand: str = "virginmedia") -> TenantScope:
    return TenantScope(country="GB", operator="vmuk", brand=brand)


def _eu_scope() -> TenantScope:
    return TenantScope(country="DE", operator="o2de", brand="o2")


def _empty_scope() -> TenantScope:
    return TenantScope(country="", operator="", brand="")


def _make_repo(adapter: MockBigQueryAdapter) -> MeasurementRepository:
    return MeasurementRepository(
        adapter=adapter,
        project=PROJECT,
        uk_dataset=UK_DATASET,
        eu_dataset=EU_DATASET,
    )


# ---------------------------------------------------------------------------
# Dataset routing
# ---------------------------------------------------------------------------

class TestResolveDataset:
    def test_uk_routes_to_europe_west2(self) -> None:
        routing = resolve_dataset(PROJECT, _uk_scope(), uk_dataset=UK_DATASET, eu_dataset=EU_DATASET)
        assert routing == DatasetRouting(project=PROJECT, dataset=UK_DATASET)

    def test_uk_case_insensitive(self) -> None:
        scope = TenantScope(country="gb", operator="vmuk", brand="vm")
        routing = resolve_dataset(PROJECT, scope, uk_dataset=UK_DATASET, eu_dataset=EU_DATASET)
        assert routing.dataset == UK_DATASET

    def test_eu_routes_to_europe_west1(self) -> None:
        routing = resolve_dataset(PROJECT, _eu_scope(), uk_dataset=UK_DATASET, eu_dataset=EU_DATASET)
        assert routing == DatasetRouting(project=PROJECT, dataset=EU_DATASET)

    def test_empty_country_routes_to_eu(self) -> None:
        routing = resolve_dataset(PROJECT, _empty_scope(), uk_dataset=UK_DATASET, eu_dataset=EU_DATASET)
        assert routing.dataset == EU_DATASET

    def test_other_country_routes_to_eu(self) -> None:
        scope = TenantScope(country="ES", operator="o2es", brand="o2")
        routing = resolve_dataset(PROJECT, scope, uk_dataset=UK_DATASET, eu_dataset=EU_DATASET)
        assert routing.dataset == EU_DATASET


# ---------------------------------------------------------------------------
# SQL building helpers
# ---------------------------------------------------------------------------

class TestFqn:
    def test_fully_qualified_name(self) -> None:
        routing = DatasetRouting(project="proj", dataset="ds")
        assert _fqn(routing, "fact_httpget") == "`proj.ds.fact_httpget`"


class TestPartitionPredicate:
    def test_30_day_window(self) -> None:
        pred = _build_partition_predicate()
        assert "_PARTITIONDATE >= DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY)" in pred
        assert "_PARTITIONDATE <= CURRENT_DATE()" in pred


class TestTenantFilter:
    def test_full_scope(self) -> None:
        clause, params = _build_tenant_filter(_uk_scope())
        assert "country = @country" in clause
        assert "operator = @operator" in clause
        assert "brand = @brand" in clause
        assert params == {"country": "GB", "operator": "vmuk", "brand": "virginmedia"}

    def test_empty_scope_no_filters(self) -> None:
        clause, params = _build_tenant_filter(_empty_scope())
        assert clause == ""
        assert params == {}

    def test_partial_scope(self) -> None:
        scope = TenantScope(country="GB", operator="", brand="o2")
        clause, params = _build_tenant_filter(scope)
        assert "country = @country" in clause
        assert "brand = @brand" in clause
        assert "operator" not in clause
        assert params == {"country": "GB", "brand": "o2"}

    def test_country_uppercased(self) -> None:
        scope = TenantScope(country="gb", operator="", brand="")
        _, params = _build_tenant_filter(scope)
        assert params["country"] == "GB"


# ---------------------------------------------------------------------------
# MeasurementRepository — resolve_unit_ids
# ---------------------------------------------------------------------------

class TestResolveUnitIds:
    async def test_returns_unit_ids_for_customer(self) -> None:
        mock = MockBigQueryAdapter()
        mock._tables["dim_cpe"] = [
            {"unit_id": 100, "customer_id": "CUST-1", "country": "GB", "operator": "vmuk", "brand": "virginmedia"},
            {"unit_id": 200, "customer_id": "CUST-1", "country": "GB", "operator": "vmuk", "brand": "virginmedia"},
            {"unit_id": 300, "customer_id": "CUST-2", "country": "GB", "operator": "vmuk", "brand": "virginmedia"},
        ]
        repo = _make_repo(mock)
        ids = await repo.resolve_unit_ids("CUST-1", _uk_scope())
        assert sorted(ids) == [100, 200]

    async def test_empty_when_no_match(self) -> None:
        mock = MockBigQueryAdapter()
        mock._tables["dim_cpe"] = [
            {"unit_id": 100, "customer_id": "CUST-1", "country": "GB", "operator": "vmuk", "brand": "virginmedia"},
        ]
        repo = _make_repo(mock)
        ids = await repo.resolve_unit_ids("CUST-UNKNOWN", _uk_scope())
        assert ids == []

    async def test_tenant_filter_applied(self) -> None:
        mock = MockBigQueryAdapter()
        mock._tables["dim_cpe"] = [
            {"unit_id": 100, "customer_id": "CUST-1", "country": "GB", "operator": "vmuk", "brand": "virginmedia"},
            {"unit_id": 200, "customer_id": "CUST-1", "country": "DE", "operator": "o2de", "brand": "o2"},
        ]
        repo = _make_repo(mock)
        ids = await repo.resolve_unit_ids("CUST-1", _uk_scope())
        assert ids == [100]


# ---------------------------------------------------------------------------
# MeasurementRepository — query_30d_metrics
# ---------------------------------------------------------------------------

class TestQuery30dMetrics:
    async def test_returns_rows_for_unit_ids(self) -> None:
        mock = MockBigQueryAdapter()
        mock._tables["fact_httpget"] = [
            {"unit_id": 100, "bytes_sec": 50000, "country": "GB", "operator": "vmuk", "brand": "virginmedia"},
            {"unit_id": 200, "bytes_sec": 60000, "country": "GB", "operator": "vmuk", "brand": "virginmedia"},
            {"unit_id": 999, "bytes_sec": 70000, "country": "GB", "operator": "vmuk", "brand": "virginmedia"},
        ]
        repo = _make_repo(mock)
        rows = await repo.query_30d_metrics("fact_httpget", [100, 200], _uk_scope())
        unit_ids = {r["unit_id"] for r in rows}
        assert unit_ids == {100, 200}

    async def test_empty_unit_ids_returns_empty(self) -> None:
        mock = MockBigQueryAdapter()
        repo = _make_repo(mock)
        rows = await repo.query_30d_metrics("fact_httpget", [], _uk_scope())
        assert rows == []

    async def test_rejects_unsupported_table(self) -> None:
        mock = MockBigQueryAdapter()
        repo = _make_repo(mock)
        with pytest.raises(ValueError, match="Unsupported fact table"):
            await repo.query_30d_metrics("fact_udpjitter", [1], _uk_scope())

    async def test_tenant_scope_filters_rows(self) -> None:
        mock = MockBigQueryAdapter()
        mock._tables["fact_httppost"] = [
            {"unit_id": 100, "bytes_sec": 50000, "country": "GB", "operator": "vmuk", "brand": "virginmedia"},
            {"unit_id": 100, "bytes_sec": 60000, "country": "DE", "operator": "o2de", "brand": "o2"},
        ]
        repo = _make_repo(mock)
        rows = await repo.query_30d_metrics("fact_httppost", [100], _uk_scope())
        assert len(rows) == 1
        assert rows[0]["country"] == "GB"

    async def test_brand_filtering(self) -> None:
        mock = MockBigQueryAdapter()
        mock._tables["fact_httpget"] = [
            {"unit_id": 100, "country": "GB", "operator": "vmuk", "brand": "virginmedia"},
            {"unit_id": 100, "country": "GB", "operator": "vmuk", "brand": "o2"},
        ]
        repo = _make_repo(mock)
        rows = await repo.query_30d_metrics("fact_httpget", [100], _uk_scope(brand="o2"))
        assert len(rows) == 1
        assert rows[0]["brand"] == "o2"

    async def test_sql_contains_partition_predicate(self) -> None:
        mock = MockBigQueryAdapter()
        mock._tables["fact_udplatency"] = []
        repo = _make_repo(mock)
        await repo.query_30d_metrics("fact_udplatency", [1], _uk_scope())
        last_call = mock._last_query
        assert "_PARTITIONDATE" in last_call["sql"]
        assert "INTERVAL 30 DAY" in last_call["sql"]

    async def test_sql_contains_fully_qualified_table(self) -> None:
        mock = MockBigQueryAdapter()
        mock._tables["fact_httpget"] = []
        repo = _make_repo(mock)
        await repo.query_30d_metrics("fact_httpget", [1], _uk_scope())
        sql = mock._last_query["sql"]
        assert f"`{PROJECT}.{UK_DATASET}.fact_httpget`" in sql

    async def test_eu_scope_uses_eu_dataset(self) -> None:
        mock = MockBigQueryAdapter()
        mock._tables["fact_httpget"] = []
        repo = _make_repo(mock)
        await repo.query_30d_metrics("fact_httpget", [1], _eu_scope())
        sql = mock._last_query["sql"]
        assert f"`{PROJECT}.{EU_DATASET}.fact_httpget`" in sql

    async def test_all_three_tables_supported(self) -> None:
        mock = MockBigQueryAdapter()
        repo = _make_repo(mock)
        for table in ("fact_httpget", "fact_httppost", "fact_udplatency"):
            mock._tables[table] = [{"unit_id": 1, "country": "GB", "operator": "vmuk", "brand": "virginmedia"}]
            rows = await repo.query_30d_metrics(table, [1], _uk_scope())
            assert len(rows) == 1


# ---------------------------------------------------------------------------
# MeasurementRepository — query_all_30d_metrics
# ---------------------------------------------------------------------------

class TestQueryAll30dMetrics:
    async def test_returns_all_tables(self) -> None:
        mock = MockBigQueryAdapter()
        mock._tables["dim_cpe"] = [
            {"unit_id": 100, "customer_id": "CUST-1", "country": "GB", "operator": "vmuk", "brand": "virginmedia"},
        ]
        mock._tables["fact_httpget"] = [
            {"unit_id": 100, "bytes_sec": 50000, "country": "GB", "operator": "vmuk", "brand": "virginmedia"},
        ]
        mock._tables["fact_httppost"] = [
            {"unit_id": 100, "bytes_sec": 30000, "country": "GB", "operator": "vmuk", "brand": "virginmedia"},
        ]
        mock._tables["fact_udplatency"] = [
            {"unit_id": 100, "rtt_avg": 15000, "country": "GB", "operator": "vmuk", "brand": "virginmedia"},
        ]
        repo = _make_repo(mock)
        result = await repo.query_all_30d_metrics("CUST-1", _uk_scope())

        assert len(result["fact_httpget"]) == 1
        assert len(result["fact_httppost"]) == 1
        assert len(result["fact_udplatency"]) == 1

    async def test_no_units_returns_empty_tables(self) -> None:
        mock = MockBigQueryAdapter()
        mock._tables["dim_cpe"] = []
        repo = _make_repo(mock)
        result = await repo.query_all_30d_metrics("NONEXISTENT", _uk_scope())
        assert all(len(v) == 0 for v in result.values())

    async def test_result_keys(self) -> None:
        mock = MockBigQueryAdapter()
        mock._tables["dim_cpe"] = []
        repo = _make_repo(mock)
        result = await repo.query_all_30d_metrics("X", _uk_scope())
        assert set(result.keys()) == {"fact_httpget", "fact_httppost", "fact_udplatency"}
