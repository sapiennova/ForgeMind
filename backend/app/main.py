"""ForgeMind Backend API - Minimal FastAPI Application"""

from fastapi import FastAPI

app = FastAPI(title="ForgeMind API", version="0.1.0")


@app.get("/health")
def health_check() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok"}
