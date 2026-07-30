"""Shared test fixtures."""

import os

os.environ["CONNECTIVITY_API_KEY_ENABLED"] = "false"
os.environ["CONNECTIVITY_RATE_LIMIT_ENABLED"] = "false"

import pytest
from httpx import ASGITransport, AsyncClient

from connectivity.adapters.bigquery.mock import MockBigQueryAdapter
from connectivity.adapters.llm.mock import MockLLMAdapter
from connectivity.config.settings import get_settings
from connectivity.dependencies import get_bq_adapter, get_llm_adapter

get_settings.cache_clear()

from connectivity.main import app  # noqa: E402


@pytest.fixture
def mock_bq() -> MockBigQueryAdapter:
    return MockBigQueryAdapter()


@pytest.fixture
def mock_llm() -> MockLLMAdapter:
    return MockLLMAdapter()


@pytest.fixture
async def client(mock_bq: MockBigQueryAdapter, mock_llm: MockLLMAdapter) -> AsyncClient:
    app.dependency_overrides[get_bq_adapter] = lambda: mock_bq
    app.dependency_overrides[get_llm_adapter] = lambda: mock_llm

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()
