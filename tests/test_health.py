"""Tests for the health check endpoint."""

import pytest
from fastapi.testclient import TestClient

from backend.app.main import app


@pytest.fixture
def client():
    """Create a test client for the FastAPI application."""
    return TestClient(app)


def test_health_endpoint_exists(client):
    """Test that the /health endpoint exists."""
    response = client.get("/health")
    assert response.status_code == 200


def test_health_status_code(client):
    """Test that /health returns HTTP 200."""
    response = client.get("/health")
    assert response.status_code == 200


def test_health_response_content(client):
    """Test that /health returns status=ok."""
    response = client.get("/health")
    assert response.json() == {"status": "ok"}
