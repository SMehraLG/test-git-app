"""API-key authentication and tenant-scope resolution for the Connectivity service.

The caller sends the raw API key in the ``X-API-Key`` request header.  The
dependency hashes the incoming value with SHA-256 and performs a constant-time
comparison against the SHA-256 digest of the configured key, so the secret is
never held in memory as a plain-text comparison target and timing side-channels
are eliminated.

When ``CONNECTIVITY_API_KEY_ENABLED=false`` (set in tests via conftest) the
dependency is a no-op and returns an unconstrained :class:`TenantScope`.
"""

import hashlib
import hmac
from dataclasses import dataclass

import structlog
from fastapi import Depends, HTTPException, Security
from fastapi.security import APIKeyHeader

from connectivity.config.settings import Settings, get_settings

logger = structlog.get_logger(__name__)

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


@dataclass(frozen=True, slots=True)
class TenantScope:
    """Authorised country / operator / brand scope resolved from the API key."""

    country: str
    operator: str
    brand: str


def _sha256_hex(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _keys_equal(incoming: str, expected: str) -> bool:
    """Constant-time comparison of the SHA-256 digests of two strings."""
    return hmac.compare_digest(_sha256_hex(incoming), _sha256_hex(expected))


async def require_api_key(
    raw_key: str | None = Security(_api_key_header),
    settings: Settings = Depends(get_settings),
) -> TenantScope:
    """FastAPI dependency — validates the API key and returns the tenant scope.

    Raises HTTP 401 when auth is enabled and the key is absent or invalid.
    Returns an unconstrained :class:`TenantScope` when auth is disabled.
    """
    if not settings.api_key_enabled:
        return TenantScope(country="", operator="", brand="")

    if not raw_key:
        logger.warning("api_key_missing")
        raise HTTPException(
            status_code=401,
            detail="Missing API key",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    expected = settings.api_key.get_secret_value()
    if not expected or not _keys_equal(raw_key, expected):
        logger.warning("api_key_invalid")
        raise HTTPException(
            status_code=401,
            detail="Invalid API key",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    return TenantScope(
        country=settings.api_key_country,
        operator=settings.api_key_operator,
        brand=settings.api_key_brand,
    )
