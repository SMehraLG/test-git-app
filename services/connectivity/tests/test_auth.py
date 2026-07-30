"""Unit tests for API-key authentication and tenant-scope resolution."""

import pytest
from fastapi import HTTPException
from pydantic import SecretStr

from connectivity.config.settings import Settings
from connectivity.security.auth import TenantScope, _keys_equal, _sha256_hex, require_api_key


def _settings(api_key: str = "secret-key", **overrides) -> Settings:
    base: dict = {
        "api_key_enabled": True,
        "api_key": SecretStr(api_key),
        "api_key_country": "GB",
        "api_key_operator": "vmuk",
        "api_key_brand": "virginmedia",
    }
    base.update(overrides)
    return Settings.model_construct(**base)


# --- helpers ---


def test_sha256_hex_is_deterministic() -> None:
    assert _sha256_hex("hello") == _sha256_hex("hello")
    assert _sha256_hex("hello") != _sha256_hex("world")


def test_keys_equal_match() -> None:
    assert _keys_equal("secret", "secret") is True


def test_keys_equal_mismatch() -> None:
    assert _keys_equal("secret", "wrong") is False


# --- require_api_key dependency ---


@pytest.mark.asyncio
async def test_auth_disabled_returns_empty_scope() -> None:
    settings = _settings(api_key_enabled=False)
    scope = await require_api_key(raw_key=None, settings=settings)
    assert scope == TenantScope(country="", operator="", brand="")


@pytest.mark.asyncio
async def test_auth_valid_key_returns_tenant_scope() -> None:
    settings = _settings()
    scope = await require_api_key(raw_key="secret-key", settings=settings)
    assert scope == TenantScope(country="GB", operator="vmuk", brand="virginmedia")


@pytest.mark.asyncio
async def test_auth_missing_key_raises_401() -> None:
    settings = _settings()
    with pytest.raises(HTTPException) as exc_info:
        await require_api_key(raw_key=None, settings=settings)
    assert exc_info.value.status_code == 401
    assert exc_info.value.headers == {"WWW-Authenticate": "ApiKey"}


@pytest.mark.asyncio
async def test_auth_invalid_key_raises_401() -> None:
    settings = _settings()
    with pytest.raises(HTTPException) as exc_info:
        await require_api_key(raw_key="wrong-key", settings=settings)
    assert exc_info.value.status_code == 401
    assert exc_info.value.headers == {"WWW-Authenticate": "ApiKey"}


@pytest.mark.asyncio
async def test_auth_empty_configured_key_raises_401() -> None:
    settings = _settings(api_key="")
    with pytest.raises(HTTPException) as exc_info:
        await require_api_key(raw_key="any-key", settings=settings)
    assert exc_info.value.status_code == 401
    assert exc_info.value.headers == {"WWW-Authenticate": "ApiKey"}
