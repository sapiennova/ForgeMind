"""ForgeMind Backend API - Minimal FastAPI Application"""

from fastapi import FastAPI

from backend.app.routers.sensor_readings import router as sensor_readings_router

app = FastAPI(title="ForgeMind API", version="0.1.0")
app.include_router(sensor_readings_router)


@app.get("/health")
def health_check() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok"}
