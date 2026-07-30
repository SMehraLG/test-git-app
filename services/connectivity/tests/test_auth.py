"""Unit tests for API-key authentication."""

import hashlib

import pytest
from fastapi import HTTPException

from connectivity.config.settings import Settings
from connectivity.security.auth import CallerScope, require_api_key

SECRET = "mysecretkey"
SECRET_HASH = hashlib.sha256(SECRET.encode()).hexdigest()

_SCOPE_SETTINGS = dict(
    api_key_scope_country="NL",
    api_key_scope_operator="ziggo",
    api_key_scope_brand="ziggo",
)


def _settings(**overrides) -> Settings:
    return Settings(
        api_key_enabled=True,
        api_key=SECRET_HASH,
        **_SCOPE_SETTINGS,
        **overrides,
    )


def test_auth_disabled_returns_scope() -> None:
    settings = Settings(api_key_enabled=False, **_SCOPE_SETTINGS)
    scope = require_api_key(raw_key=None, settings=settings)
    assert isinstance(scope, CallerScope)
    assert scope.country == "NL"


def test_missing_key_raises_401() -> None:
    with pytest.raises(HTTPException) as exc_info:
        require_api_key(raw_key=None, settings=_settings())
    assert exc_info.value.status_code == 401
    assert "Missing" in exc_info.value.detail


def test_invalid_key_raises_401() -> None:
    with pytest.raises(HTTPException) as exc_info:
        require_api_key(raw_key="wrongkey", settings=_settings())
    assert exc_info.value.status_code == 401
    assert "Invalid" in exc_info.value.detail


def test_valid_key_returns_scope() -> None:
    scope = require_api_key(raw_key=SECRET, settings=_settings())
    assert isinstance(scope, CallerScope)
    assert scope.operator == "ziggo"
    assert scope.brand == "ziggo"
