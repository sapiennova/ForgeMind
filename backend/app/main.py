"""ForgeMind Backend API - Minimal FastAPI Application"""

import math

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from backend.app.routers.machine_telemetry import router as machine_telemetry_router
from backend.app.routers.sensor_readings import router as sensor_readings_router

app = FastAPI(title="ForgeMind API", version="0.1.0")
app.include_router(sensor_readings_router)
app.include_router(machine_telemetry_router)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Return JSON-safe validation details, including for NaN/Infinity inputs."""
    errors = []
    for error in exc.errors():
        safe_error = {
            key: value
            for key, value in error.items()
            if key not in {"input", "ctx", "url"}
        }
        input_value = error.get("input")
        if isinstance(input_value, float) and not math.isfinite(input_value):
            safe_error["msg"] = "Input must contain only finite numeric values"
        errors.append(safe_error)

    return JSONResponse(status_code=422, content={"detail": errors})


@app.get("/health")
def health_check() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok"}
