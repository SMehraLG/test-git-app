"""Per-IP token-bucket rate-limiter tests."""

import asyncio

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from connectivity.security.rate_limiter import RateLimitMiddleware


def _make_app(capacity: int = 60, refill_rate: float = 10.0, enabled: bool = True) -> FastAPI:
    app = FastAPI()

    @app.get("/ping")
    async def ping() -> dict[str, bool]:
        return {"ok": True}

    app.add_middleware(
        RateLimitMiddleware,
        capacity=capacity,
        refill_rate=refill_rate,
        enabled=enabled,
    )
    return app


@pytest.mark.asyncio
async def test_requests_pass_within_capacity() -> None:
    app = _make_app(capacity=5)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        for _ in range(5):
            resp = await client.get("/ping")
            assert resp.status_code == 200


@pytest.mark.asyncio
async def test_returns_429_when_bucket_exhausted() -> None:
    app = _make_app(capacity=2)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        for _ in range(2):
            resp = await client.get("/ping")
            assert resp.status_code == 200

        resp = await client.get("/ping")
        assert resp.status_code == 429
        body = resp.json()
        assert "detail" in body


@pytest.mark.asyncio
async def test_different_ips_have_separate_buckets() -> None:
    app = _make_app(capacity=1)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/ping", headers={"x-forwarded-for": "10.0.0.1"})
        assert resp.status_code == 200

        resp = await client.get("/ping", headers={"x-forwarded-for": "10.0.0.1"})
        assert resp.status_code == 429

        # Second IP still has a full bucket
        resp = await client.get("/ping", headers={"x-forwarded-for": "10.0.0.2"})
        assert resp.status_code == 200


@pytest.mark.asyncio
async def test_disabled_middleware_allows_unlimited_requests() -> None:
    app = _make_app(capacity=1, enabled=False)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        for _ in range(10):
            resp = await client.get("/ping")
            assert resp.status_code == 200


@pytest.mark.asyncio
async def test_tokens_refill_over_time() -> None:
    # capacity=1, refill_rate=100 tokens/s -> 1 token restored after ~10 ms
    app = _make_app(capacity=1, refill_rate=100.0)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/ping")
        assert resp.status_code == 200

        resp = await client.get("/ping")
        assert resp.status_code == 429

        await asyncio.sleep(0.02)

        resp = await client.get("/ping")
        assert resp.status_code == 200


@pytest.mark.asyncio
async def test_first_request_always_succeeds() -> None:
    app = _make_app(capacity=60)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/ping")
        assert resp.status_code == 200


@pytest.mark.asyncio
async def test_xff_header_takes_precedence_over_client_addr() -> None:
    app = _make_app(capacity=1)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # IP from XFF header exhausts its bucket
        resp = await client.get("/ping", headers={"x-forwarded-for": "1.2.3.4"})
        assert resp.status_code == 200

        resp = await client.get("/ping", headers={"x-forwarded-for": "1.2.3.4"})
        assert resp.status_code == 429

        # Without the XFF header the client uses a different key and still has tokens
        resp = await client.get("/ping")
        assert resp.status_code == 200


@pytest.mark.asyncio
async def test_xff_multi_value_uses_first_ip() -> None:
    middleware = RateLimitMiddleware(app=None, capacity=60, refill_rate=10.0)  # type: ignore[arg-type]

    class _FakeRequest:
        headers = {"x-forwarded-for": "203.0.113.5, 10.0.0.1, 172.16.0.1"}
        client = None

    assert middleware._client_ip(_FakeRequest()) == "203.0.113.5"  # type: ignore[arg-type]
