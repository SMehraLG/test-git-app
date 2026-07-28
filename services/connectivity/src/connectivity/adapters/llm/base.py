"""Abstract LLM adapter interface."""

from abc import ABC, abstractmethod
from typing import Any


class LLMAdapter(ABC):
    @abstractmethod
    async def analyze(self, data: dict[str, Any], prompt: str) -> str: ...

    async def health_check(self) -> bool:
        return True
