"""Mock LLM adapter returning canned responses."""

from typing import Any

import structlog

from connectivity.adapters.llm.base import LLMAdapter

logger = structlog.get_logger(__name__)

CANNED_ANALYSIS = (
    "The fleet is performing within expected parameters. "
    "Average download speeds are stable with no significant degradation detected."
)


class MockLLMAdapter(LLMAdapter):
    async def analyze(self, data: dict[str, Any], prompt: str) -> str:
        logger.info("Mock LLM analyze", data_keys=list(data.keys()))
        return CANNED_ANALYSIS
