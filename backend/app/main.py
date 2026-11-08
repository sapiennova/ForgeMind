"""ForgeMind FastAPI application with fail-closed security defaults."""

from __future__ import annotations

import logging
import math
from collections import deque

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from backend.app.routers.machine_telemetry import router as machine_telemetry_router
from backend.app.routers.sensor_readings import router as sensor_readings_router
from backend.app.security import SecuritySettings, load_security_settings, require_api_key, validate_api_key

logger = logging.getLogger(__name__)


class APIAuthenticationMiddleware:
    """Protect every current and future operational route under /api/."""

    def __init__(self, app, settings: SecuritySettings):
        self.app = app
        self.settings = settings

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http" and scope.get("path", "").startswith("/api/"):
            authorization = next(
                (value for key, value in scope.get("headers", []) if key.lower() == b"authorization"),
                None,
            )
            token = None
            if authorization is not None:
                scheme, separator, credential = authorization.partition(b" ")
                if separator and scheme.lower() == b"bearer" and credential:
                    token = credential
            failure = validate_api_key(self.settings, token)
            if failure is not None:
                code, detail = failure
                headers = {"WWW-Authenticate": "Bearer"} if code == 401 else None
                response = JSONResponse({"detail": detail}, status_code=code, headers=headers)
                await response(scope, receive, send)
                return
        await self.app(scope, receive, send)


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
        if content_length is not None:
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

        # Buffer at most the configured limit before invoking the application.
        # This avoids raising from ASGI receive(), which FastAPI's body parser may
        # translate into a generic 400 before an outer middleware can return 413.
        buffered_messages = deque()
        received = 0
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                buffered_messages.append(message)
                break
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > self.max_bytes:
                    await JSONResponse(
                        {"detail": "Request body too large"}, status_code=413
                    )(scope, receive, send)
                    return
                buffered_messages.append(message)
                if not message.get("more_body", False):
                    break
            else:
                buffered_messages.append(message)
                break

        async def replay_receive():
            if buffered_messages:
                return buffered_messages.popleft()
            return await receive()

        await self.app(scope, replay_receive, send)


class SecurityHeadersMiddleware:
    """Add defensive response headers, including to early middleware responses."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def secured_send(message):
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                headers.extend([
                    (b"x-content-type-options", b"nosniff"),
                    (b"x-frame-options", b"DENY"),
                    (b"referrer-policy", b"no-referrer"),
                    (b"permissions-policy", b"camera=(), microphone=(), geolocation=()"),
                ])
                message["headers"] = headers
            await send(message)

        await self.app(scope, receive, secured_send)


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
    # Starlette wraps middleware in reverse registration order. The resulting
    # request path is SecurityHeaders -> TrustedHost -> CORS -> Authentication
    # -> RequestSize -> routing. Host validation precedes CORS, preflight is
    # answered before bearer auth, and auth rejects callers before body buffering.
    # Authenticated requests are size-checked before any route handler executes.
    application.add_middleware(RequestSizeLimitMiddleware, max_bytes=security_settings.max_request_bytes)
    application.add_middleware(APIAuthenticationMiddleware, settings=security_settings)
    if security_settings.cors_origins:
        application.add_middleware(
            CORSMiddleware,
            allow_origins=list(security_settings.cors_origins),
            allow_credentials=False,
            allow_methods=["GET", "POST"],
            allow_headers=["Authorization", "Content-Type"],
            max_age=600,
        )
    # Host validation wraps CORS; headers wrap all responses, including rejected requests.
    application.add_middleware(TrustedHostMiddleware, allowed_hosts=list(security_settings.allowed_hosts))
    application.add_middleware(SecurityHeadersMiddleware)

    protected = [Depends(require_api_key)]
    application.include_router(sensor_readings_router, dependencies=protected)
    application.include_router(machine_telemetry_router, dependencies=protected)

    @application.get("/health", tags=["health"])
    def health_check() -> dict[str, str]:
        """Unauthenticated liveness probe; reveals no infrastructure details."""
        return {"status": "ok"}

    @application.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        errors = []
        for error in exc.errors():
            input_value = error.get("input")
            message = (
                "Input must contain only finite numeric values"
                if isinstance(input_value, float) and not math.isfinite(input_value)
                else "Invalid request"
            )
            errors.append({"type": error.get("type", "validation_error"), "loc": error.get("loc", []), "msg": message})
        return JSONResponse(status_code=422, content={"detail": errors})

    @application.exception_handler(Exception)
    async def unexpected_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.error("Unhandled request error (type=%s)", type(exc).__name__)
        return JSONResponse(status_code=500, content={"detail": "Internal server error"})

    return application


app = create_app()
