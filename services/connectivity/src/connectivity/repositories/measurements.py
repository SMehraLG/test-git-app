"""Partition-pruned BigQuery reads for connectivity fact tables.

Queries the last-30-day window from fact_httpget, fact_httppost and
fact_udplatency with explicit day-partition predicates, tenant
(country+operator+brand) scoping, and per-region dataset routing.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from connectivity.adapters.bigquery.base import BigQueryAdapter
from connectivity.config.settings import Settings
from connectivity.security.auth import CallerScope

_UK_BRANDS = frozenset({"vm", "o2"})

WINDOW_DAYS = 30


@dataclass(frozen=True)
class SpeedAggregate:
    avg_speed_mbps: float
    avg_provisioned_mbps: float
    sample_count: int
    window_start: datetime
    window_end: datetime


@dataclass(frozen=True)
class LatencyAggregate:
    avg_rtt_ms: float
    sample_count: int
    window_start: datetime
    window_end: datetime


def _resolve_dataset(scope: CallerScope, settings: Settings) -> str:
    """Route UK brands to europe-west2, EU markets to europe-west1."""
    if scope.brand in _UK_BRANDS:
        return settings.bq_dataset_uk or settings.bq_dataset
    return settings.bq_dataset_eu or settings.bq_dataset


def _qualified_table(project: str, dataset: str, table: str) -> str:
    if project and dataset:
        return f"`{project}.{dataset}.{table}`"
    return table


def _window_bounds() -> tuple[datetime, datetime]:
    now = datetime.now(timezone.utc)
    return now - timedelta(days=WINDOW_DAYS), now


def _tenant_predicates() -> str:
    return (
        "AND country = @country "
        "AND operator = @operator "
        "AND brand = @brand "
    )


def _tenant_params(scope: CallerScope) -> dict[str, str]:
    return {
        "country": scope.country,
        "operator": scope.operator,
        "brand": scope.brand,
    }


class MeasurementRepository:
    """Read-only repository for partition-pruned fact-table aggregation."""

    def __init__(self, adapter: BigQueryAdapter, settings: Settings) -> None:
        self._adapter = adapter
        self._settings = settings

    async def get_download_aggregate(
        self, customer_id: str, scope: CallerScope
    ) -> SpeedAggregate | None:
        dataset = _resolve_dataset(scope, self._settings)
        table = _qualified_table(self._settings.bq_project, dataset, "fact_httpget")
        window_start, window_end = _window_bounds()

        sql = (
            "SELECT "
            "AVG(speed_mbps) AS avg_speed_mbps, "
            "AVG(provisioned_mbps) AS avg_provisioned_mbps, "
            "COUNT(*) AS sample_count, "
            "MIN(dtime_utc) AS window_start, "
            "MAX(dtime_utc) AS window_end "
            f"FROM {table} "
            "WHERE customer_id = @customer_id "
            "AND dtime_utc >= @window_start "
            "AND dtime_utc < @window_end "
            + _tenant_predicates()
        )

        params = {
            "customer_id": customer_id,
            "window_start": window_start.isoformat(),
            "window_end": window_end.isoformat(),
            **_tenant_params(scope),
        }

        rows = await self._adapter.query(sql, params)
        return _parse_speed_rows(rows)

    async def get_upload_aggregate(
        self, customer_id: str, scope: CallerScope
    ) -> SpeedAggregate | None:
        dataset = _resolve_dataset(scope, self._settings)
        table = _qualified_table(self._settings.bq_project, dataset, "fact_httppost")
        window_start, window_end = _window_bounds()

        sql = (
            "SELECT "
            "AVG(speed_mbps) AS avg_speed_mbps, "
            "AVG(provisioned_mbps) AS avg_provisioned_mbps, "
            "COUNT(*) AS sample_count, "
            "MIN(dtime_utc) AS window_start, "
            "MAX(dtime_utc) AS window_end "
            f"FROM {table} "
            "WHERE customer_id = @customer_id "
            "AND dtime_utc >= @window_start "
            "AND dtime_utc < @window_end "
            + _tenant_predicates()
        )

        params = {
            "customer_id": customer_id,
            "window_start": window_start.isoformat(),
            "window_end": window_end.isoformat(),
            **_tenant_params(scope),
        }

        rows = await self._adapter.query(sql, params)
        return _parse_speed_rows(rows)

    async def get_latency_aggregate(
        self, customer_id: str, scope: CallerScope
    ) -> LatencyAggregate | None:
        dataset = _resolve_dataset(scope, self._settings)
        table = _qualified_table(self._settings.bq_project, dataset, "fact_udplatency")
        window_start, window_end = _window_bounds()

        sql = (
            "SELECT "
            "AVG(rtt_avg_ms) AS avg_rtt_ms, "
            "COUNT(*) AS sample_count, "
            "MIN(dtime_utc) AS window_start, "
            "MAX(dtime_utc) AS window_end "
            f"FROM {table} "
            "WHERE customer_id = @customer_id "
            "AND dtime_utc >= @window_start "
            "AND dtime_utc < @window_end "
            + _tenant_predicates()
        )

        params = {
            "customer_id": customer_id,
            "window_start": window_start.isoformat(),
            "window_end": window_end.isoformat(),
            **_tenant_params(scope),
        }

        rows = await self._adapter.query(sql, params)
        return _parse_latency_rows(rows)


def _parse_speed_rows(rows: list[dict]) -> SpeedAggregate | None:
    if not rows:
        return None
    row = rows[0]
    count = row.get("sample_count", 0)
    if not count:
        return None
    return SpeedAggregate(
        avg_speed_mbps=float(row["avg_speed_mbps"]),
        avg_provisioned_mbps=float(row["avg_provisioned_mbps"]),
        sample_count=int(count),
        window_start=_to_dt(row["window_start"]),
        window_end=_to_dt(row["window_end"]),
    )


def _parse_latency_rows(rows: list[dict]) -> LatencyAggregate | None:
    if not rows:
        return None
    row = rows[0]
    count = row.get("sample_count", 0)
    if not count:
        return None
    return LatencyAggregate(
        avg_rtt_ms=float(row["avg_rtt_ms"]),
        sample_count=int(count),
        window_start=_to_dt(row["window_start"]),
        window_end=_to_dt(row["window_end"]),
    )


def _to_dt(value: str | datetime) -> datetime:
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(value)
