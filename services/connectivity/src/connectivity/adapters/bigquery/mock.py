"""In-memory mock BigQuery adapter for local development and tests."""

from typing import Any
import os

import structlog
from pydantic import BaseModel

from connectivity.adapters.bigquery.base import BigQueryAdapter

logger = structlog.get_logger(__name__)


class MockBigQueryAdapter(BigQueryAdapter):
    """Simple in-memory adapter — stores rows per table, returns them on query."""

    def __init__(self) -> None:
        self._tables: dict[str, list[dict[str, Any]]] = {}
        self._last_query: dict[str, Any] = {}

    @property
    def dataset(self) -> str:
        return "mock"

    async def insert_records(self, table: str, records: list[BaseModel]) -> int:
        if table not in self._tables:
            self._tables[table] = []
        rows = [r.model_dump(mode="json") for r in records]
        self._tables[table].extend(rows)
        logger.info("Mock insert", table=table, count=len(rows))
        return len(rows)

    async def query(self, sql: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        logger.info("Mock query", sql=sql[:120], params=params)
        self._last_query = {"sql": sql, "params": params}
        for table_name, rows in self._tables.items():
            if table_name in sql:
                return self._apply_mock_filters(rows, params)
        return []

    @staticmethod
    def _apply_mock_filters(
        rows: list[dict[str, Any]], params: dict[str, Any] | None
    ) -> list[dict[str, Any]]:
        if not params:
            return list(rows)
        result = rows
        if "customer_id" in params:
            result = [r for r in result if r.get("customer_id") == params["customer_id"]]
        if "unit_ids" in params:
            ids = set(params["unit_ids"])
            result = [r for r in result if r.get("unit_id") in ids]
        if "country" in params:
            result = [r for r in result if r.get("country") == params["country"]]
        if "operator" in params:
            result = [r for r in result if r.get("operator") == params["operator"]]
        if "brand" in params:
            result = [r for r in result if r.get("brand") == params["brand"]]
        return result

    async def health_check(self) -> bool:
        return True

    def get_table_rows(self, table: str) -> list[dict[str, Any]]:
        return self._tables.get(table, [])

    def clear(self) -> None:
        self._tables.clear()
