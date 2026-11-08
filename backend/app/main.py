"""ForgeMind FastAPI application with fail-closed security defaults."""

from __future__ import annotations

import logging

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from backend.app.routers.machine_telemetry import router as machine_telemetry_router
from backend.app.routers.sensor_readings import router as sensor_readings_router
from backend.app.security import SecuritySettings, load_security_settings, require_api_key

logger = logging.getLogger(__name__)


class _RequestTooLarge(Exception):
    pass


class RequestSizeLimitMiddleware:
    """Enforce a body limit for declared and streamed request bodies."""

    def __init__(self, app, max_bytes: int):
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = {key.lower(): value for key, value in scope.get("headers", [])}
        content_length = headers.get(b"content-length")
        if content_length:
            try:
                declared_size = int(content_length)
            except ValueError:
                await JSONResponse({"detail": "Invalid Content-Length"}, 400)(scope, receive, send)
                return
            if declared_size < 0:
                await JSONResponse({"detail": "Invalid Content-Length"}, 400)(scope, receive, send)
                return
            if declared_size > self.max_bytes:
                await JSONResponse({"detail": "Request body too large"}, 413)(scope, receive, send)
                return

        received = 0

        async def limited_receive():
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > self.max_bytes:
                    raise _RequestTooLarge
            return message

        async def secured_send(message):
            if message["type"] == "http.response.start":
                response_headers = list(message.get("headers", []))
                response_headers.extend([
                    (b"x-content-type-options", b"nosniff"),
                    (b"x-frame-options", b"DENY"),
                    (b"referrer-policy", b"no-referrer"),
                    (b"content-security-policy", b"default-src 'none'; frame-ancestors 'none'; base-uri 'none'"),
                    (b"permissions-policy", b"camera=(), microphone=(), geolocation=()"),
                ])
                if scope.get("scheme") == "https":
                    response_headers.append((b"strict-transport-security", b"max-age=31536000; includeSubDomains"))
                message["headers"] = response_headers
            await send(message)

        try:
            await self.app(scope, limited_receive, secured_send)
        except _RequestTooLarge:
            await JSONResponse({"detail": "Request body too large"}, 413)(scope, receive, secured_send)


def create_app(settings: SecuritySettings | None = None) -> FastAPI:
    """Build an application using explicit, validated security configuration."""
    security_settings = settings or load_security_settings()
    application = FastAPI(
        title="ForgeMind API",
        version="0.1.0",
        docs_url="/docs" if security_settings.docs_enabled and not security_settings.production else None,
        redoc_url="/redoc" if security_settings.docs_enabled and not security_settings.production else None,
        openapi_url="/openapi.json" if security_settings.docs_enabled and not security_settings.production else None,
        debug=False,
    )
    application.state.security_settings = security_settings
    application.add_middleware(RequestSizeLimitMiddleware, max_bytes=security_settings.max_request_bytes)
    application.add_middleware(TrustedHostMiddleware, allowed_hosts=list(security_settings.allowed_hosts))
    if security_settings.cors_origins:
        application.add_middleware(
            CORSMiddleware,
            allow_origins=list(security_settings.cors_origins),
            allow_credentials=False,
            allow_methods=["GET", "POST"],
            allow_headers=["Authorization", "Content-Type"],
            max_age=600,
        )

    protected = [Depends(require_api_key)]
    application.include_router(sensor_readings_router, dependencies=protected)
    application.include_router(machine_telemetry_router, dependencies=protected)

    @application.get("/health", tags=["health"])
    def health_check() -> dict[str, str]:
        """Unauthenticated liveness probe; reveals no infrastructure details."""
        return {"status": "ok"}

    @application.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        errors = [
            {key: value for key, value in error.items() if key in {"type", "loc", "msg"}}
            for error in exc.errors()
        ]
        return JSONResponse(status_code=422, content={"detail": errors})

    @application.exception_handler(Exception)
    async def unexpected_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.error("Unhandled request error (type=%s)", type(exc).__name__)
        return JSONResponse(status_code=500, content={"detail": "Internal server error"})

    return application


app = create_app()
