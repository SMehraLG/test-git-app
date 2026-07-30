"""Tests for per-IP token-bucket rate-limiting middleware."""

import pytest
from httpx import ASGITransport, AsyncClient

from connectivity.adapters.bigquery.mock import MockBigQueryAdapter
from connectivity.adapters.llm.mock import MockLLMAdapter
from connectivity.dependencies import get_bq_adapter, get_llm_adapter
from connectivity.security.rate_limiter import (
    CAPACITY,
    REFILL_RATE,
    RateLimiterMiddleware,
    _TokenBucket,
)


def _make_client(app) -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


def _find_rate_middleware(app) -> RateLimiterMiddleware | None:
    """Walk the middleware stack to find the RateLimiterMiddleware instance."""
    node = getattr(app, "middleware_stack", None)
    while node is not None:
        if isinstance(node, RateLimiterMiddleware):
            return node
        node = getattr(node, "app", None)
    return None


@pytest.fixture
def fresh_app(mock_bq: MockBigQueryAdapter, mock_llm: MockLLMAdapter):
    """Return a freshly constructed app so each test has an empty rate-limiter state."""
    from connectivity.main import create_app

    application = create_app()
    application.dependency_overrides[get_bq_adapter] = lambda: mock_bq
    application.dependency_overrides[get_llm_adapter] = lambda: mock_llm
    return application


# ---------------------------------------------------------------------------
# Unit tests for _TokenBucket
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_bucket_allows_up_to_capacity() -> None:
    bucket = _TokenBucket()
    for _ in range(CAPACITY):
        assert await bucket.consume() is True


@pytest.mark.asyncio
async def test_bucket_rejects_when_exhausted() -> None:
    bucket = _TokenBucket()
    for _ in range(CAPACITY):
        await bucket.consume()
    assert await bucket.consume() is False


@pytest.mark.asyncio
async def test_bucket_refills_after_token_injection() -> None:
    bucket = _TokenBucket()
    for _ in range(CAPACITY):
        await bucket.consume()
    assert await bucket.consume() is False

    # Simulate 1 second of refill by injecting tokens directly.
    bucket._tokens = REFILL_RATE
    assert await bucket.consume() is True


# ---------------------------------------------------------------------------
# Integration tests via the HTTP client
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_requests_within_capacity_succeed(fresh_app) -> None:
    async with _make_client(fresh_app) as client:
        for _ in range(CAPACITY):
            resp = await client.get("/health")
            assert resp.status_code == 200


@pytest.mark.asyncio
async def test_request_after_exhaustion_returns_429(fresh_app) -> None:
    async with _make_client(fresh_app) as client:
        for _ in range(CAPACITY):
            await client.get("/health")
        resp = await client.get("/health")
        assert resp.status_code == 429


@pytest.mark.asyncio
async def test_429_response_body(fresh_app) -> None:
    async with _make_client(fresh_app) as client:
        for _ in range(CAPACITY):
            await client.get("/health")
        resp = await client.get("/health")
        assert resp.json() == {"detail": "Too Many Requests"}


@pytest.mark.asyncio
async def test_429_includes_retry_after_header(fresh_app) -> None:
    async with _make_client(fresh_app) as client:
        for _ in range(CAPACITY):
            await client.get("/health")
        resp = await client.get("/health")
        assert resp.headers.get("retry-after") == "1"


@pytest.mark.asyncio
async def test_different_ips_have_separate_buckets(fresh_app) -> None:
    async with _make_client(fresh_app) as client:
        for _ in range(CAPACITY):
            await client.get("/health", headers={"X-Forwarded-For": "10.0.0.1"})

        resp_exhausted = await client.get("/health", headers={"X-Forwarded-For": "10.0.0.1"})
        assert resp_exhausted.status_code == 429

        resp_fresh = await client.get("/health", headers={"X-Forwarded-For": "10.0.0.2"})
        assert resp_fresh.status_code == 200


@pytest.mark.asyncio
async def test_x_forwarded_for_first_hop_used(fresh_app) -> None:
    """Only the first address in X-Forwarded-For identifies the client IP."""
    async with _make_client(fresh_app) as client:
        for _ in range(CAPACITY):
            await client.get("/health", headers={"X-Forwarded-For": "1.2.3.4, 5.6.7.8"})

        resp_same = await client.get("/health", headers={"X-Forwarded-For": "1.2.3.4, 5.6.7.8"})
        assert resp_same.status_code == 429

        resp_diff = await client.get("/health", headers={"X-Forwarded-For": "9.9.9.9, 5.6.7.8"})
        assert resp_diff.status_code == 200


@pytest.mark.asyncio
async def test_tokens_refill_allows_further_requests(fresh_app) -> None:
    """After exhaustion, injecting tokens (simulating elapsed time) unblocks requests."""
    async with _make_client(fresh_app) as client:
        for _ in range(CAPACITY):
            await client.get("/health")

        assert (await client.get("/health")).status_code == 429

        mw = _find_rate_middleware(fresh_app)
        assert mw is not None, "RateLimiterMiddleware not found in the middleware stack"

        for bucket in mw._buckets.values():
            bucket._tokens = REFILL_RATE

        resp = await client.get("/health")
        assert resp.status_code == 200
