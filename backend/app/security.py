"""Security configuration and reusable API authentication dependencies."""

from __future__ import annotations

import hmac
import os
from dataclasses import dataclass
from typing import Mapping

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer


@dataclass(frozen=True)
class SecuritySettings:
    environment: str
    api_key: str | None
    allowed_hosts: tuple[str, ...]
    cors_origins: tuple[str, ...]
    max_request_bytes: int
    docs_enabled: bool

    def __post_init__(self) -> None:
        if self.environment not in {"development", "test", "production"}:
            raise RuntimeError("Invalid ForgeMind environment")
        if not self.allowed_hosts or any("*" in host for host in self.allowed_hosts):
            raise RuntimeError("FORGEMIND_ALLOWED_HOSTS must contain exact hostnames")
        if any("*" in origin for origin in self.cors_origins):
            raise RuntimeError("FORGEMIND_CORS_ORIGINS must contain exact origins")
        if self.environment == "production":
            if not self.api_key or len(self.api_key.encode("utf-8")) < 32:
                raise RuntimeError("Production requires FORGEMIND_API_KEY of at least 32 bytes")
        if not 1024 <= self.max_request_bytes <= 104857600:
            raise RuntimeError("FORGEMIND_MAX_REQUEST_BYTES must be between 1024 and 104857600")

    @property
    def production(self) -> bool:
        return self.environment == "production"


def load_security_settings(environ: Mapping[str, str] | None = None) -> SecuritySettings:
    """Load explicit settings and fail closed for incomplete production configuration."""
    env = os.environ if environ is None else environ
    environment = env.get("FORGEMIND_ENV", "development").strip().lower()
    if environment not in {"development", "test", "production"}:
        raise RuntimeError("FORGEMIND_ENV must be development, test, or production")

    api_key = env.get("FORGEMIND_API_KEY") or None
    raw_hosts = env.get("FORGEMIND_ALLOWED_HOSTS")
    raw_origins = env.get("FORGEMIND_CORS_ORIGINS")
    if environment == "production":
        if not api_key or len(api_key.encode("utf-8")) < 32:
            raise RuntimeError("Production requires FORGEMIND_API_KEY of at least 32 bytes")
        if not raw_hosts or not [v.strip() for v in raw_hosts.split(",") if v.strip()]:
            raise RuntimeError("Production requires explicit FORGEMIND_ALLOWED_HOSTS")
        allowed_hosts = tuple(v.strip() for v in raw_hosts.split(",") if v.strip())
        cors_origins = tuple(v.strip() for v in (raw_origins or "").split(",") if v.strip())
    else:
        allowed_hosts = tuple(v.strip() for v in (raw_hosts or "localhost,127.0.0.1,testserver").split(",") if v.strip())
        cors_origins = tuple(v.strip() for v in (raw_origins or "").split(",") if v.strip())

    try:
        max_request_bytes = int(env.get("FORGEMIND_MAX_REQUEST_BYTES", "1048576"))
    except ValueError as exc:
        raise RuntimeError("FORGEMIND_MAX_REQUEST_BYTES must be an integer") from exc
    if not 1024 <= max_request_bytes <= 104857600:
        raise RuntimeError("FORGEMIND_MAX_REQUEST_BYTES must be between 1024 and 104857600")

    docs_enabled = environment != "production" and env.get("FORGEMIND_DOCS_ENABLED", "true").lower() == "true"
    return SecuritySettings(environment, api_key, allowed_hosts, cors_origins, max_request_bytes, docs_enabled)


def validate_api_key(settings: SecuritySettings, token: bytes | None) -> tuple[int, str] | None:
    """Return a safe authentication failure, or None when the key is valid."""
    if not settings.api_key:
        return 503, "API authentication is not configured"
    if token is None or not hmac.compare_digest(token, settings.api_key.encode("utf-8")):
        return 401, "Authentication required" if token is None else "Invalid credentials"
    return None


_bearer = HTTPBearer(auto_error=False)


def require_api_key(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> str:
    """Require a configured bearer API key; missing configuration never grants access."""
    settings: SecuritySettings = request.app.state.security_settings
    token = (
        credentials.credentials.encode("utf-8")
        if credentials is not None and credentials.scheme.lower() == "bearer"
        else None
    )
    failure = validate_api_key(settings, token)
    if failure is not None:
        code, detail = failure
        headers = {"WWW-Authenticate": "Bearer"} if code == 401 else None
        raise HTTPException(status_code=code, detail=detail, headers=headers)
    return "api-key"
