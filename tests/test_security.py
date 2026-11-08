"""Security regression tests for the API boundary."""

import pytest
from fastapi.testclient import TestClient

from backend.app.main import create_app
from backend.app.security import SecuritySettings, load_security_settings

TEST_KEY = "test-only-key-with-at-least-thirty-two-bytes"


def settings(**overrides):
    values = dict(
        environment="test",
        api_key=TEST_KEY,
        allowed_hosts=("testserver", "localhost"),
        cors_origins=("https://console.example.test",),
        max_request_bytes=1024,
        docs_enabled=True,
    )
    values.update(overrides)
    return SecuritySettings(**values)


def test_operational_endpoint_rejects_missing_credentials():
    with TestClient(create_app(settings())) as client:
        response = client.get("/api/v1/machines/aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa/telemetry")
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_operational_endpoint_rejects_invalid_credentials():
    with TestClient(create_app(settings())) as client:
        response = client.get(
            "/api/v1/machines/aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa/telemetry",
            headers={"Authorization": "Bearer wrong"},
        )
    assert response.status_code == 401


def test_operational_endpoint_rejects_malformed_authentication_scheme():
    with TestClient(create_app(settings())) as client:
        response = client.get(
            "/api/v1/machines/aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa/telemetry",
            headers={"Authorization": "Basic dXNlcjpwYXNz"},
        )
    assert response.status_code == 401


def test_valid_credentials_reach_resource_handler():
    with TestClient(create_app(settings())) as client:
        response = client.get(
            "/api/v1/machines/aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa/telemetry",
            headers={"Authorization": f"Bearer {TEST_KEY}"},
        )
    assert response.status_code == 404
    assert response.json()["detail"] == "Machine not found"


def test_missing_server_credential_fails_closed():
    with TestClient(create_app(settings(api_key=None))) as client:
        response = client.get("/api/v1/machines/aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa/telemetry")
    assert response.status_code == 503


def test_central_boundary_protects_future_api_routes_without_route_dependencies():
    application = create_app(settings())

    @application.get("/api/v1/future-operational-resource")
    def future_route():
        return {"ok": True}

    with TestClient(application) as client:
        denied = client.get("/api/v1/future-operational-resource")
        allowed = client.get(
            "/api/v1/future-operational-resource",
            headers={"Authorization": f"Bearer {TEST_KEY}"},
        )

    assert denied.status_code == 401
    assert allowed.status_code == 200


def test_health_is_public_and_minimal():
    with TestClient(create_app(settings())) as client:
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.parametrize(
    "environment",
    [
        {"FORGEMIND_ENV": "production", "FORGEMIND_ALLOWED_HOSTS": "api.example.com"},
        {"FORGEMIND_ENV": "production", "FORGEMIND_API_KEY": "short", "FORGEMIND_ALLOWED_HOSTS": "api.example.com"},
        {"FORGEMIND_ENV": "production", "FORGEMIND_API_KEY": TEST_KEY},
        {"FORGEMIND_ENV": "production", "FORGEMIND_API_KEY": TEST_KEY, "FORGEMIND_ALLOWED_HOSTS": "*"},
        {"FORGEMIND_ENV": "development", "FORGEMIND_ALLOWED_HOSTS": "   "},
    ],
)
def test_production_configuration_fails_without_required_secrets_or_safe_hosts(environment):
    with pytest.raises(RuntimeError):
        load_security_settings(environment)


def test_valid_production_configuration_disables_docs():
    configured = load_security_settings({
        "FORGEMIND_ENV": "production",
        "FORGEMIND_API_KEY": TEST_KEY,
        "FORGEMIND_ALLOWED_HOSTS": "api.example.com",
        "FORGEMIND_CORS_ORIGINS": "https://console.example.com",
    })
    assert configured.production
    assert configured.docs_enabled is False
    assert configured.allowed_hosts == ("api.example.com",)


def test_production_docs_and_openapi_are_not_exposed():
    production = settings(
        environment="production",
        allowed_hosts=("api.example.com",),
        cors_origins=(),
        docs_enabled=False,
    )
    with TestClient(create_app(production), base_url="https://api.example.com") as client:
        assert client.get("/docs").status_code == 404
        assert client.get("/redoc").status_code == 404
        assert client.get("/openapi.json").status_code == 404


def test_trusted_host_rejects_unlisted_host():
    with TestClient(create_app(settings()), base_url="http://attacker.example") as client:
        response = client.get("/health")
    assert response.status_code == 400


def test_cors_does_not_allow_unconfigured_origin():
    with TestClient(create_app(settings())) as client:
        response = client.options(
            "/api/v1/sensors/aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa/readings",
            headers={
                "Origin": "https://attacker.example",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "authorization,content-type",
            },
        )
    assert "access-control-allow-origin" not in response.headers


def test_cors_allows_only_configured_origin_without_credentials():
    with TestClient(create_app(settings())) as client:
        response = client.options(
            "/api/v1/sensors/aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa/readings",
            headers={
                "Origin": "https://console.example.test",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "authorization,content-type",
            },
        )
    assert response.headers["access-control-allow-origin"] == "https://console.example.test"
    assert response.headers.get("access-control-allow-credentials") != "true"


def test_request_body_size_limit_returns_413():
    with TestClient(create_app(settings())) as client:
        response = client.post(
            "/api/v1/sensors/aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa/readings",
            content=b"x" * 2048,
            headers={"Authorization": f"Bearer {TEST_KEY}", "Content-Type": "application/json"},
        )
    assert response.status_code == 413
    assert response.json() == {"detail": "Request body too large"}


def test_security_headers_are_present():
    with TestClient(create_app(settings())) as client:
        response = client.get("/health")
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["referrer-policy"] == "no-referrer"


def test_validation_error_does_not_echo_submitted_secret():
    with TestClient(create_app(settings()), headers={"Authorization": f"Bearer {TEST_KEY}"}) as client:
        response = client.post(
            "/api/v1/sensors/aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa/readings",
            json={"value": "sensitive-submitted-value"},
        )
    assert response.status_code == 422
    assert "sensitive-submitted-value" not in response.text


def test_unexpected_exception_does_not_leak_details():
    application = create_app(settings())

    @application.get("/test-exception")
    def raise_error():
        raise RuntimeError("database-password=do-not-disclose")

    with TestClient(application, raise_server_exceptions=False) as client:
        response = client.get("/test-exception")

    assert response.status_code == 500
    assert response.json() == {"detail": "Internal server error"}
    assert "do-not-disclose" not in response.text
