"""Repository for partition-pruned reads from SamKnows fact tables.

Routes queries to regional BigQuery datasets based on the authenticated
tenant scope and applies day-partition predicates so the query engine
prunes partitions down to the trailing 30-day window.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import structlog

from connectivity.adapters.bigquery.base import BigQueryAdapter
from connectivity.security.auth import TenantScope

logger = structlog.get_logger(__name__)

_FACT_TABLES = ("fact_httpget", "fact_httppost", "fact_udplatency")

_UK_COUNTRY = "GB"


@dataclass(frozen=True, slots=True)
class DatasetRouting:
    """Regional dataset identifiers resolved from tenant scope."""

    project: str
    dataset: str


def resolve_dataset(
    project: str, scope: TenantScope, *, uk_dataset: str, eu_dataset: str
) -> DatasetRouting:
    """Map tenant scope to the correct regional BigQuery dataset.

    UK (country=GB) → europe-west2 dataset.
    All other markets  → europe-west1 dataset.
    """
    if scope.country.upper() == _UK_COUNTRY:
        return DatasetRouting(project=project, dataset=uk_dataset)
    return DatasetRouting(project=project, dataset=eu_dataset)


def _fqn(routing: DatasetRouting, table: str) -> str:
    return f"`{routing.project}.{routing.dataset}.{table}`"


def _build_partition_predicate() -> str:
    return (
        "_PARTITIONDATE >= DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY) "
        "AND _PARTITIONDATE <= CURRENT_DATE()"
    )


def _build_tenant_filter(scope: TenantScope) -> tuple[str, dict[str, Any]]:
    """Build WHERE-clause fragments and params for tenant scoping.

    Filters on country, operator, and brand columns when the scope
    values are non-empty.  Brand values ``vm`` and ``o2`` are the two
    UK operating-company brands under VMO2.
    """
    clauses: list[str] = []
    params: dict[str, Any] = {}

    if scope.country:
        clauses.append("country = @country")
        params["country"] = scope.country.upper()
    if scope.operator:
        clauses.append("operator = @operator")
        params["operator"] = scope.operator
    if scope.brand:
        clauses.append("brand = @brand")
        params["brand"] = scope.brand

    return " AND ".join(clauses), params


class MeasurementRepository:
    """Read-path repository for 30-day windowed fact table queries.

    All queries use explicit ``_PARTITIONDATE`` predicates so BigQuery
    prunes day-partitions and avoids full-table scans.
    """

    def __init__(
        self,
        adapter: BigQueryAdapter,
        project: str,
        uk_dataset: str,
        eu_dataset: str,
    ) -> None:
        self._adapter = adapter
        self._project = project
        self._uk_dataset = uk_dataset
        self._eu_dataset = eu_dataset

    def _routing(self, scope: TenantScope) -> DatasetRouting:
        return resolve_dataset(
            self._project,
            scope,
            uk_dataset=self._uk_dataset,
            eu_dataset=self._eu_dataset,
        )

    async def resolve_unit_ids(self, customer_id: str, scope: TenantScope) -> list[int]:
        """Resolve *customer_id* to associated probe/CPE unit IDs.

        Uses ``dim_cpe`` in the tenant-routed dataset to look up the
        probes provisioned for the customer.
        """
        routing = self._routing(scope)
        table = _fqn(routing, "dim_cpe")

        sql = f"SELECT DISTINCT unit_id FROM {table} " "WHERE customer_id = @customer_id"
        params: dict[str, Any] = {"customer_id": customer_id}

        tenant_clause, tenant_params = _build_tenant_filter(scope)
        if tenant_clause:
            sql += f" AND {tenant_clause}"
            params.update(tenant_params)

        rows = await self._adapter.query(sql, params)
        unit_ids = [int(r["unit_id"]) for r in rows]
        logger.info(
            "resolved_unit_ids",
            customer_id=customer_id,
            count=len(unit_ids),
            dataset=routing.dataset,
        )
        return unit_ids

    async def query_30d_metrics(
        self,
        table: str,
        unit_ids: list[int],
        scope: TenantScope,
    ) -> list[dict[str, Any]]:
        """Query a single fact table for the trailing 30-day window.

        Args:
            table: One of ``fact_httpget``, ``fact_httppost``, or
                ``fact_udplatency``.
            unit_ids: Probe/CPE unit IDs (from :meth:`resolve_unit_ids`).
            scope: Authenticated tenant scope for dataset routing and
                row-level filtering.

        Returns:
            Raw rows from BigQuery as dicts.
        """
        if table not in _FACT_TABLES:
            raise ValueError(f"Unsupported fact table: {table}")
        if not unit_ids:
            return []

        routing = self._routing(scope)
        fqn = _fqn(routing, table)

        partition_pred = _build_partition_predicate()

        sql = (
            f"SELECT * FROM {fqn} "
            f"WHERE {partition_pred} "
            "AND unit_id IN UNNEST(@unit_ids) "
            "AND successes > 0"
        )
        params: dict[str, Any] = {"unit_ids": unit_ids}

        tenant_clause, tenant_params = _build_tenant_filter(scope)
        if tenant_clause:
            sql += f" AND {tenant_clause}"
            params.update(tenant_params)

        rows = await self._adapter.query(sql, params)
        logger.info(
            "query_30d_metrics",
            table=table,
            dataset=routing.dataset,
            unit_count=len(unit_ids),
            row_count=len(rows),
        )
        return rows

    async def query_all_30d_metrics(
        self,
        customer_id: str,
        scope: TenantScope,
    ) -> dict[str, list[dict[str, Any]]]:
        """Resolve customer and query all three fact tables in one call.

        Returns a dict keyed by table name with the raw rows for each.
        """
        unit_ids = await self.resolve_unit_ids(customer_id, scope)
        if not unit_ids:
            return {t: [] for t in _FACT_TABLES}

        results: dict[str, list[dict[str, Any]]] = {}
        for table in _FACT_TABLES:
            results[table] = await self.query_30d_metrics(table, unit_ids, scope)
        return results
