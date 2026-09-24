"""Auth and rate limiting are opt-in, and must stay out of the way when off."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.backend.middleware import BearerTokenMiddleware, RateLimitMiddleware


def _app(**middleware_kwargs) -> FastAPI:
    app = FastAPI()

    @app.get("/")
    def root():
        return {"ok": True}

    @app.get("/agents")
    def agents():
        return []

    @app.post("/hedge-fund/run")
    def run():
        return {"ok": True}

    app.add_middleware(RateLimitMiddleware, **middleware_kwargs)
    app.add_middleware(BearerTokenMiddleware)
    return app


class TestBearerToken:
    def test_requests_pass_through_when_no_token_is_configured(self, monkeypatch):
        monkeypatch.delenv("API_AUTH_TOKEN", raising=False)
        client = TestClient(_app(requests_per_minute=0))

        assert client.get("/agents").status_code == 200

    def test_a_configured_token_is_required(self, monkeypatch):
        monkeypatch.setenv("API_AUTH_TOKEN", "s3cret")
        client = TestClient(_app(requests_per_minute=0))

        assert client.get("/agents").status_code == 401
        assert client.get("/agents", headers={"Authorization": "Bearer s3cret"}).status_code == 200
        assert client.get("/agents", headers={"Authorization": "Bearer wrong"}).status_code == 401

    def test_health_stays_reachable_so_probes_need_no_credentials(self, monkeypatch):
        monkeypatch.setenv("API_AUTH_TOKEN", "s3cret")
        client = TestClient(_app(requests_per_minute=0))

        assert client.get("/").status_code == 200


class TestRateLimit:
    def test_runs_are_capped_per_client(self, monkeypatch):
        monkeypatch.delenv("API_AUTH_TOKEN", raising=False)
        client = TestClient(_app(requests_per_minute=2))

        assert client.post("/hedge-fund/run").status_code == 200
        assert client.post("/hedge-fund/run").status_code == 200

        response = client.post("/hedge-fund/run")
        assert response.status_code == 429
        assert "Retry-After" in response.headers

    def test_only_the_expensive_endpoints_are_metered(self, monkeypatch):
        monkeypatch.delenv("API_AUTH_TOKEN", raising=False)
        client = TestClient(_app(requests_per_minute=1))

        client.post("/hedge-fund/run")

        # The catalog is cheap and must not be blocked by a run in flight.
        assert client.get("/agents").status_code == 200

    def test_a_limit_of_zero_disables_metering(self, monkeypatch):
        monkeypatch.delenv("API_AUTH_TOKEN", raising=False)
        client = TestClient(_app(requests_per_minute=0))

        for _ in range(5):
            assert client.post("/hedge-fund/run").status_code == 200


@pytest.fixture(autouse=True)
def _clear_auth_env(monkeypatch):
    monkeypatch.delenv("RATE_LIMIT_PER_MINUTE", raising=False)
