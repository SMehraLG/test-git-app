"""API-key authentication and per-OpCo/brand tenant-scope FastAPI dependency.

The incoming raw key (from X-API-Key header) is SHA-256 hashed and compared
against the pre-computed hash stored in settings using constant-time comparison
(hmac.compare_digest) to prevent timing attacks.

When CONNECTIVITY_API_KEY_ENABLED is false (dev/test), the check is skipped and
a scope populated from settings defaults is returned so routes remain exercisable.
"""

import hashlib
import hmac
from dataclasses import dataclass

import structlog
from fastapi import Depends, HTTPException
from fastapi.security import APIKeyHeader

from connectivity.config.settings import Settings, get_settings

logger = structlog.get_logger(__name__)

_API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)


@dataclass(frozen=True)
class CallerScope:
    """Authorised tenant scope resolved from the API key context."""

    country: str
    operator: str
    brand: str


def require_api_key(
    raw_key: str | None = Depends(_API_KEY_HEADER),
    settings: Settings = Depends(get_settings),
) -> CallerScope:
    """Validate the service API key and return the caller's authorised scope.

    Raises HTTP 401 when the key is absent or invalid and auth is enabled.
    """
    if not settings.api_key_enabled:
        return CallerScope(
            country=settings.api_key_scope_country,
            operator=settings.api_key_scope_operator,
            brand=settings.api_key_scope_brand,
        )

    if not raw_key:
        logger.warning("api_key_missing")
        raise HTTPException(status_code=401, detail="Missing API key")

    incoming_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    if not hmac.compare_digest(incoming_hash, settings.api_key):
        logger.warning("api_key_invalid")
        raise HTTPException(status_code=401, detail="Invalid API key")

    return CallerScope(
        country=settings.api_key_scope_country,
        operator=settings.api_key_scope_operator,
        brand=settings.api_key_scope_brand,
    )
