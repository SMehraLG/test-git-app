"""In-memory mock BigQuery adapter for local development and tests."""

from typing import Any

import structlog
from pydantic import BaseModel

from connectivity.adapters.bigquery.base import BigQueryAdapter

logger = structlog.get_logger(__name__)


class MockBigQueryAdapter(BigQueryAdapter):
    """Simple in-memory adapter — stores rows per table, returns them on query."""

    def __init__(self) -> None:
        self._tables: dict[str, list[dict[str, Any]]] = {}

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
        logger.info("Mock query", sql=sql[:120])
        for table_name, rows in self._tables.items():
            if table_name in sql:
                return rows
        return []

    async def health_check(self) -> bool:
        return True

    def get_table_rows(self, table: str) -> list[dict[str, Any]]:
        return self._tables.get(table, [])

    def clear(self) -> None:
        self._tables.clear()
