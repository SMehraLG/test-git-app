"""Abstract BigQuery adapter interface."""

from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel


class BigQueryAdapter(ABC):
    @property
    @abstractmethod
    def dataset(self) -> str: ...

    @abstractmethod
    async def insert_records(self, table: str, records: list[BaseModel]) -> int: ...

    @abstractmethod
    async def query(
        self, sql: str, params: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]: ...

    @abstractmethod
    async def health_check(self) -> bool: ...
