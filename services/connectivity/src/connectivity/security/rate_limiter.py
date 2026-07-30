"""Per-IP token-bucket rate limiter.

Horizon v2 security baseline: 60-token capacity, 10 tokens/s refill per IP.
Returns HTTP 429 when the client's bucket is exhausted.
"""

import asyncio
import time
from collections.abc import Awaitable, Callable

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

logger = structlog.get_logger(__name__)


class _Bucket:
    __slots__ = ("tokens", "last_refill")

    def __init__(self, capacity: float) -> None:
        self.tokens: float = capacity
        self.last_refill: float = time.monotonic()


class RateLimitMiddleware(BaseHTTPMiddleware):
    """ASGI middleware that enforces a per-IP token-bucket rate limit.

    Each client IP gets its own bucket. When the bucket is empty the
    request is rejected with HTTP 429.  Buckets are never evicted from
    memory; this is intentional for a single-process service — the
    steady-state memory cost is one small object per unique IP.

    Args:
        capacity: Maximum tokens (also the initial fill level).
        refill_rate: Tokens added per second.
        enabled: When False the middleware is a no-op (used to disable
            rate limiting in tests or non-production environments).
    """

    def __init__(
        self,
        app: object,
        capacity: int = 60,
        refill_rate: float = 10.0,
        enabled: bool = True,
    ) -> None:
        super().__init__(app)  # type: ignore[arg-type]
        self._capacity = float(capacity)
        self._refill_rate = refill_rate
        self._enabled = enabled
        self._buckets: dict[str, _Bucket] = {}
        self._lock = asyncio.Lock()

    def _client_ip(self, request: Request) -> str:
        xff = request.headers.get("x-forwarded-for")
        if xff:
            return xff.split(",")[0].strip()
        return request.client.host if request.client else "unknown"

    async def _consume(self, ip: str) -> bool:
        async with self._lock:
            now = time.monotonic()
            if ip not in self._buckets:
                bucket = _Bucket(self._capacity)
                self._buckets[ip] = bucket
            else:
                bucket = self._buckets[ip]
                elapsed = now - bucket.last_refill
                bucket.tokens = min(
                    self._capacity,
                    bucket.tokens + elapsed * self._refill_rate,
                )
                bucket.last_refill = now

            if bucket.tokens >= 1.0:
                bucket.tokens -= 1.0
                return True

            return False

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        if not self._enabled:
            return await call_next(request)

        ip = self._client_ip(request)
        if not await self._consume(ip):
            logger.warning("rate_limit_exceeded", client_ip=ip, path=request.url.path)
            return JSONResponse(
                {"detail": "Rate limit exceeded. Try again later."},
                status_code=429,
            )

        return await call_next(request)
