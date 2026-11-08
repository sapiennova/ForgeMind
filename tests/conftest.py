"""Test-process configuration, loaded before application modules are imported."""

import os

# A test-only value is injected by pytest, never used by application defaults or deployments.
os.environ["FORGEMIND_ENV"] = "test"
os.environ["FORGEMIND_API_KEY"] = "test-only-api-key-not-for-production"
os.environ["FORGEMIND_ALLOWED_HOSTS"] = "testserver,localhost"
os.environ["FORGEMIND_CORS_ORIGINS"] = ""
