"""Backend contract tests.

Covers the three things the web tier previously got wrong: an unknown agent
list produced a hollow 200, a failing run closed the stream with no error
event, and the catalogs were not served at all.
"""

import json

import pytest
from fastapi.testclient import TestClient

from app.backend.api.deps import API_KEY_ENV_VAR, RATE_LIMIT_ENV_VAR, reset_rate_limits
from app.backend.main import app


@pytest.fixture
def client():
    reset_rate_limits()
    with TestClient(app) as test_client:
        yield test_client


def parse_sse(body: str) -> list[tuple[str, dict]]:
    """Split an SSE body into (event type, payload) pairs."""
    events = []
    for frame in body.split("\n\n"):
        if not frame.strip():
            continue
        lines = dict(line.split(": ", 1) for line in frame.splitlines() if ": " in line)
        if "event" in lines and "data" in lines:
            events.append((lines["event"], json.loads(lines["data"])))
    return events


class TestCatalog:
    def test_agents_endpoint_serves_the_analyst_config(self, client):
        response = client.get("/agents")
        assert response.status_code == 200

        agents = response.json()
        assert len(agents) == 14
        keys = {agent["key"] for agent in agents}
        assert {"warren_buffett", "technical_analyst", "valuation_analyst"} <= keys
        # Descriptions used to exist only in the hand-copied TS mirror.
        assert all(agent["description"] for agent in agents)
        assert [agent["order"] for agent in agents] == sorted(agent["order"] for agent in agents)

    def test_models_endpoint_includes_ollama(self, client):
        """The TS mirror omitted Ollama, making the local-LLM path unreachable."""
        response = client.get("/models")
        assert response.status_code == 200

        models = response.json()
        providers = {model["provider"] for model in models}
        assert "Ollama" in providers
        assert {"Anthropic", "DeepSeek", "Gemini", "Groq", "OpenAI"} <= providers

    def test_models_carry_their_json_mode_capability(self, client):
        models = {model["model_name"]: model for model in client.get("/models").json()}

        assert models["gpt-4o"]["supports_json_mode"] is True
        # Shipped in ollama_models.json but absent from the old substring
        # allow-list, so it silently took the manual parsing path.
        assert models["gemma3:4b"]["supports_json_mode"] is False
        assert models["deepseek-chat"]["supports_json_mode"] is False


class TestRequestValidation:
    def test_unknown_agent_is_rejected_with_400(self, client):
        response = client.post(
            "/hedge-fund/run",
            json={"tickers": ["AAPL"], "selected_agents": ["nope"]},
        )
        assert response.status_code == 400
        assert "nope" in response.json()["detail"]

    def test_empty_agent_list_is_rejected(self, client):
        response = client.post("/hedge-fund/run", json={"tickers": ["AAPL"], "selected_agents": []})
        assert response.status_code == 422

    def test_empty_ticker_list_is_rejected(self, client):
        response = client.post("/hedge-fund/run", json={"tickers": [], "selected_agents": ["warren_buffett"]})
        assert response.status_code == 422

    def test_backtest_rejects_an_inverted_date_range(self, client):
        response = client.post(
            "/backtest",
            json={
                "tickers": ["AAPL"],
                "selected_agents": ["warren_buffett"],
                "start_date": "2024-06-01",
                "end_date": "2024-01-01",
            },
        )
        assert response.status_code == 400


class TestStreaming:
    def test_a_failing_run_emits_an_error_event(self, client, monkeypatch):
        """Previously the exception surfaced after the 200 and the stream just stopped."""
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("FINANCIAL_DATASETS_API_KEY", raising=False)

        response = client.post(
            "/hedge-fund/run",
            json={"tickers": ["DEFINITELY_NOT_A_TICKER"], "selected_agents": ["warren_buffett"]},
        )
        assert response.status_code == 200

        events = parse_sse(response.text)
        types = [event_type for event_type, _ in events]
        assert types[0] == "start"
        assert "error" in types, f"expected an error event, got {types}"

        error_payload = next(payload for event_type, payload in events if event_type == "error")
        assert error_payload["message"]
        # Every event is addressable to its run.
        assert all(payload.get("run_id") for _, payload in events)

    def test_the_run_id_is_echoed_on_the_response_and_every_event(self, client):
        response = client.post(
            "/hedge-fund/run",
            json={"tickers": ["NOPE"], "selected_agents": ["warren_buffett"], "run_id": "test-run-123"},
        )
        assert response.headers["X-Run-Id"] == "test-run-123"
        assert all(payload.get("run_id") == "test-run-123" for _, payload in parse_sse(response.text))


class TestAuthAndRateLimiting:
    def test_api_is_open_when_no_key_is_configured(self, client, monkeypatch):
        monkeypatch.delenv(API_KEY_ENV_VAR, raising=False)
        assert client.post("/hedge-fund/run", json={"tickers": ["AAPL"], "selected_agents": ["nope"]}).status_code == 400

    def test_a_configured_key_is_required(self, client, monkeypatch):
        monkeypatch.setenv(API_KEY_ENV_VAR, "s3cret")

        unauthorised = client.post("/hedge-fund/run", json={"tickers": ["AAPL"], "selected_agents": ["nope"]})
        assert unauthorised.status_code == 401

        authorised = client.post(
            "/hedge-fund/run",
            json={"tickers": ["AAPL"], "selected_agents": ["nope"]},
            headers={"X-API-Key": "s3cret"},
        )
        # 400 for the unknown agent means it got past authentication.
        assert authorised.status_code == 400

    def test_catalog_reads_are_never_guarded(self, client, monkeypatch):
        monkeypatch.setenv(API_KEY_ENV_VAR, "s3cret")
        assert client.get("/agents").status_code == 200
        assert client.get("/models").status_code == 200

    def test_requests_beyond_the_limit_are_rejected(self, client, monkeypatch):
        monkeypatch.setenv(RATE_LIMIT_ENV_VAR, "2")
        reset_rate_limits()

        body = {"tickers": ["AAPL"], "selected_agents": ["nope"]}
        assert client.post("/hedge-fund/run", json=body).status_code == 400
        assert client.post("/hedge-fund/run", json=body).status_code == 400

        throttled = client.post("/hedge-fund/run", json=body)
        assert throttled.status_code == 429
        assert "Retry-After" in throttled.headers
