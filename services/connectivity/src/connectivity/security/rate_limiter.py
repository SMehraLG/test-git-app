"""Per-IP token-bucket rate-limiting middleware (Horizon v2 security baseline).

Capacity : 60 tokens per IP address.
Refill   : 10 tokens per second.
Response : HTTP 429 with Retry-After: 1 when the bucket is exhausted.
"""

import asyncio
import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

CAPACITY: int = 60
REFILL_RATE: float = 10.0  # tokens per second


class _TokenBucket:
    __slots__ = ("_lock", "_tokens", "_last_refill")

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._tokens: float = float(CAPACITY)
        self._last_refill: float = time.monotonic()

    async def consume(self) -> bool:
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_refill
            self._tokens = min(float(CAPACITY), self._tokens + elapsed * REFILL_RATE)
            self._last_refill = now
            if self._tokens >= 1.0:
                self._tokens -= 1.0
                return True
            return False


class RateLimiterMiddleware(BaseHTTPMiddleware):
    """Token-bucket rate limiter keyed by client IP (Horizon v2 security baseline)."""

    def __init__(self, app) -> None:
        super().__init__(app)
        self._buckets: dict[str, _TokenBucket] = {}
        self._registry_lock = asyncio.Lock()

    @staticmethod
    def _client_ip(request: Request) -> str:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.client.host if request.client else "unknown"

    async def _bucket_for(self, ip: str) -> _TokenBucket:
        async with self._registry_lock:
            if ip not in self._buckets:
                self._buckets[ip] = _TokenBucket()
            return self._buckets[ip]

    async def dispatch(self, request: Request, call_next) -> Response:
        ip = self._client_ip(request)
        bucket = await self._bucket_for(ip)
        if not await bucket.consume():
            return JSONResponse(
                status_code=429,
                content={"detail": "Too Many Requests"},
                headers={"Retry-After": "1"},
            )
        return await call_next(request)
