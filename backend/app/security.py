"""Security configuration and reusable API authentication dependencies."""

from __future__ import annotations

import hmac
import os
from dataclasses import dataclass
from typing import Mapping

from fastapi import HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer


@dataclass(frozen=True)
class SecuritySettings:
    environment: str
    api_key: str | None
    allowed_hosts: tuple[str, ...]
    cors_origins: tuple[str, ...]
    max_request_bytes: int
    docs_enabled: bool

    @property
    def production(self) -> bool:
        return self.environment == "production"


def load_security_settings(environ: Mapping[str, str] | None = None) -> SecuritySettings:
    """Load explicit security settings; production fails closed."""
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
        if not raw_origins:
            cors_origins: tuple[str, ...] = ()
        else:
            cors_origins = tuple(v.strip() for v in raw_origins.split(",") if v.strip())
        allowed_hosts = tuple(v.strip() for v in raw_hosts.split(",") if v.strip())
        if "*" in allowed_hosts or "*" in cors_origins:
            raise RuntimeError("Wildcard hosts and CORS origins are forbidden")
    else:
        allowed_hosts = tuple(
            v.strip() for v in (raw_hosts or "localhost,127.0.0.1,testserver").split(",") if v.strip()
        )
        cors_origins = tuple(v.strip() for v in (raw_origins or "").split(",") if v.strip())

    try:
        max_request_bytes = int(env.get("FORGEMIND_MAX_REQUEST_BYTES", "1048576"))
    except ValueError as exc:
        raise RuntimeError("FORGEMIND_MAX_REQUEST_BYTES must be an integer") from exc
    if not 1024 <= max_request_bytes <= 104857600:
        raise RuntimeError("FORGEMIND_MAX_REQUEST_BYTES must be between 1024 and 104857600")

    docs_enabled = environment != "production" and env.get("FORGEMIND_DOCS_ENABLED", "true").lower() == "true"
    return SecuritySettings(
        environment=environment,
        api_key=api_key,
        allowed_hosts=allowed_hosts,
        cors_origins=cors_origins,
        max_request_bytes=max_request_bytes,
        docs_enabled=docs_enabled,
    )


_bearer = HTTPBearer(auto_error=False)


def require_api_key(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = None,
) -> str:
    """Require a configured bearer API key; never grant access on missing config."""
    settings: SecuritySettings = request.app.state.security_settings
    if not settings.api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="API authentication is not configured",
        )
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not hmac.compare_digest(credentials.credentials, settings.api_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return "api-key"
