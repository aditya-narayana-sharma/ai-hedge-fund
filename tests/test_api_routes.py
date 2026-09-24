"""The HTTP surface: catalogs, validation, and the documented error shapes."""

import pytest
from fastapi.testclient import TestClient

from app.backend.main import app
from src.llm.models import AVAILABLE_MODELS, OLLAMA_MODELS
from src.utils.analysts import ANALYST_CONFIG


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(app)


class TestHealth:
    def test_root(self, client):
        assert client.get("/").status_code == 200


class TestCatalog:
    def test_agents_endpoint_matches_the_python_catalog(self, client):
        response = client.get("/agents")

        assert response.status_code == 200
        assert {agent["key"] for agent in response.json()} == set(ANALYST_CONFIG)

    def test_agents_are_returned_in_display_order(self, client):
        orders = [agent["order"] for agent in client.get("/agents").json()]

        assert orders == sorted(orders)

    def test_models_endpoint_matches_the_python_catalog(self, client):
        response = client.get("/models")

        assert response.status_code == 200
        expected = {model.model_name for model in [*AVAILABLE_MODELS, *OLLAMA_MODELS] if not model.is_custom()}
        assert {model["model_name"] for model in response.json()} == expected

    def test_ollama_models_are_reachable_from_the_api(self, client):
        # The hand-copied TypeScript catalog omitted Ollama entirely, which
        # made the whole local-LLM path unreachable from the web UI.
        providers = {model["provider"] for model in client.get("/models").json()}

        assert "Ollama" in providers


class TestHedgeFundValidation:
    def test_empty_agent_selection_is_a_400_not_a_hollow_200(self, client):
        response = client.post("/hedge-fund/run", json={"tickers": ["AAPL"], "selected_agents": []})

        assert response.status_code == 400
        assert "at least one analyst" in response.json()["detail"]

    def test_unknown_agent_is_a_400(self, client):
        response = client.post("/hedge-fund/run", json={"tickers": ["AAPL"], "selected_agents": ["not_an_analyst"]})

        assert response.status_code == 400
        assert "not_an_analyst" in response.json()["detail"]

    def test_empty_ticker_list_is_rejected(self, client):
        response = client.post("/hedge-fund/run", json={"tickers": [], "selected_agents": ["warren_buffett"]})

        assert response.status_code == 422


class TestBacktestValidation:
    def test_unknown_agent_is_a_400(self, client):
        response = client.post("/backtest/run", json={"tickers": ["AAPL"], "selected_agents": ["not_an_analyst"]})

        assert response.status_code == 400

    def test_reversed_date_range_is_a_400(self, client):
        response = client.post(
            "/backtest/run",
            json={
                "tickers": ["AAPL"],
                "selected_agents": ["warren_buffett"],
                "start_date": "2024-06-01",
                "end_date": "2024-01-01",
            },
        )

        assert response.status_code == 400


class TestRequestSchema:
    def test_a_run_id_is_generated_when_absent(self, client):
        from app.backend.models.schemas import HedgeFundRequest

        request = HedgeFundRequest(tickers=["aapl"], selected_agents=["warren_buffett"])

        assert request.run_id
        assert request.tickers == ["AAPL"]

    def test_a_supplied_run_id_is_kept(self):
        from app.backend.models.schemas import HedgeFundRequest

        request = HedgeFundRequest(tickers=["AAPL"], selected_agents=["warren_buffett"], run_id="abc123")

        assert request.run_id == "abc123"
