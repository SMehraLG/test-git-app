"""Per-IP token-bucket rate-limiting middleware (Horizon v2 security baseline).

Capacity : 60 tokens per IP address.
Refill   : 10 tokens per second.
Response : HTTP 429 with Retry-After: 1 when the bucket is exhausted.
"""

import asyncio
import time

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

logger = structlog.get_logger(__name__)

CAPACITY: int = 60
REFILL_RATE: float = 10.0  # tokens per second


class _TokenBucket:
    __slots__ = ("_lock", "_tokens", "_last_refill", "_capacity", "_refill_rate")

    def __init__(self, capacity: int = CAPACITY, refill_rate: float = REFILL_RATE) -> None:
        self._lock = asyncio.Lock()
        self._capacity = float(capacity)
        self._refill_rate = refill_rate
        self._tokens: float = float(capacity)
        self._last_refill: float = time.monotonic()

    async def consume(self) -> bool:
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_refill
            self._tokens = min(self._capacity, self._tokens + elapsed * self._refill_rate)
            self._last_refill = now
            if self._tokens >= 1.0:
                self._tokens -= 1.0
                return True
            return False


class RateLimiterMiddleware(BaseHTTPMiddleware):
    """Token-bucket rate limiter keyed by client IP (Horizon v2 security baseline).

    When `enabled` is False all requests pass through unchanged.
    The client IP is read from X-Forwarded-For (first entry) then request.client.host.
    Production defaults: CAPACITY=60, REFILL_RATE=10/s.
    """

    def __init__(
        self,
        app,
        *,
        enabled: bool = True,
        capacity: int = CAPACITY,
        refill_rate: float = REFILL_RATE,
    ) -> None:
        super().__init__(app)
        self.enabled = enabled
        self._capacity = capacity
        self._refill_rate = refill_rate
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
                self._buckets[ip] = _TokenBucket(self._capacity, self._refill_rate)
            return self._buckets[ip]

    async def dispatch(self, request: Request, call_next) -> Response:
        if not self.enabled:
            return await call_next(request)

        ip = self._client_ip(request)
        bucket = await self._bucket_for(ip)
        if not await bucket.consume():
            logger.warning("rate_limit_exceeded", client_ip=ip, path=request.url.path)
            return JSONResponse(
                status_code=429,
                content={"detail": "Too Many Requests"},
                headers={"Retry-After": "1"},
            )
        return await call_next(request)
