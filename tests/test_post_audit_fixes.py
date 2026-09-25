"""Regression tests for the post-PR-#1 P0 and P1 engine fixes.

Each test calls the production function. The old portfolio tests re-implemented
the short-margin arithmetic inline, which is how an unaffordable cover survived
a suite that claimed to cover it.
"""

import numpy as np
import pandas as pd
from pydantic import BaseModel

from src.agents.risk_manager import risk_management_agent
from src.agents.technicals import calculate_hurst_exponent
from src.backtester import Backtester
from src.data.cache import Cache
from src.data.models import FinancialMetrics, Price
from src.tools.api import get_financial_metrics, get_insider_trades, recorded_coverage_start
from src.utils.llm import call_llm, degraded_analyst_count, reset_degraded_analysts


def _backtester(cash: float, margin: float, limit: float = 0.20) -> Backtester:
    return Backtester(
        agent=lambda **_: None,
        tickers=["AAPL"],
        start_date="2024-01-01",
        end_date="2024-06-01",
        initial_capital=cash,
        initial_margin_requirement=margin,
        position_limit=limit,
        verbose=False,
    )


def test_cover_cannot_spend_cash_the_portfolio_does_not_have():
    """E1: short 100 @ $10 on $1,000, then the price goes to $100."""
    backtester = _backtester(1_000.0, 0.5, limit=1.0)
    assert backtester.execute_trade("AAPL", "short", 100, 10.0) == 100

    filled = backtester.execute_trade("AAPL", "cover", 100, 100.0)

    assert filled < 100
    assert backtester.portfolio["cash"] >= 0
    assert backtester.portfolio["positions"]["AAPL"]["short"] > 0


def test_position_limit_caps_a_zero_margin_short():
    """E2: margin requirement 0 used to make the short guard ``0 <= cash``."""
    backtester = _backtester(1_000.0, 0.0, limit=0.20)

    filled = backtester.execute_trade("AAPL", "short", 1_000_000, 100.0)

    # 20% of a $1,000 book at $100 is 2 shares, not a million.
    assert filled == 2


def test_position_limit_caps_a_concentrated_buy():
    backtester = _backtester(100_000.0, 0.0, limit=0.20)

    filled = backtester.execute_trade("AAPL", "buy", 1000, 100.0)

    assert filled == 200
    assert backtester.portfolio["cash"] == 80_000.0


def test_open_ended_coverage_stops_at_the_oldest_returned_row():
    """E3: one full page must not be recorded as 1900-01-01 through end_date."""
    assert recorded_coverage_start(None, "1900-01-01", row_count=1, limit=1, oldest="2024-06-01") == "2024-06-01"
    # A short page exhausted the endpoint, so the gap really is covered.
    assert recorded_coverage_start(None, "1900-01-01", row_count=1, limit=50, oldest="2024-06-01") == "1900-01-01"
    # A bounded request paginates, so the requested gap is what was fetched.
    assert recorded_coverage_start("2022-01-01", "2022-01-01", row_count=1, limit=1, oldest="2024-06-01") == "2022-01-01"


def test_open_ended_insider_fetch_does_not_starve_a_later_window(monkeypatch):
    cache = Cache()
    monkeypatch.setattr("src.tools.api.resolve_cache", lambda: cache)
    pages = {
        1: [{"ticker": "AAPL", "filing_date": "2024-06-01", "transaction_date": "2024-06-01"}],
        1000: [
            {"ticker": "AAPL", "filing_date": "2024-06-01", "transaction_date": "2024-06-01"},
            {"ticker": "AAPL", "filing_date": "2023-01-01", "transaction_date": "2023-01-01"},
            {"ticker": "AAPL", "filing_date": "2022-06-01", "transaction_date": "2022-06-01"},
        ],
    }
    calls: list[str] = []

    class _Response:
        def __init__(self, limit: int):
            self.status_code = 200
            self._rows = pages[limit]

        def json(self):
            # Fill the optional fields the model requires.
            trades = []
            for row in self._rows:
                trades.append(
                    {
                        "issuer": None,
                        "name": None,
                        "title": None,
                        "is_board_director": None,
                        "transaction_shares": 1,
                        "transaction_price_per_share": 1,
                        "transaction_value": 1,
                        "shares_owned_before_transaction": 1,
                        "shares_owned_after_transaction": 1,
                        "security_title": None,
                        **row,
                    }
                )
            return {"insider_trades": trades}

    def fake_get(url, headers=None):
        calls.append(url)
        limit = 1000 if "limit=1000" in url else 1
        return _Response(limit)

    monkeypatch.setattr("src.tools.api.requests.get", fake_get)

    first = get_insider_trades("AAPL", "2024-12-31", limit=1)
    assert len(first) == 1
    assert not cache.covers("insider_trades", "AAPL", "2022-01-01", "2024-12-31")

    second = get_insider_trades("AAPL", "2024-12-31", start_date="2022-01-01", limit=1000)
    assert len(calls) == 2
    assert len(second) == 3


def test_financial_metrics_are_keyed_on_period(monkeypatch):
    monkeypatch.setenv("AI_HEDGE_FUND_PUBLICATION_LAG_DAYS", "0")
    cache = Cache()
    monkeypatch.setattr("src.tools.api.resolve_cache", lambda: cache)
    seen: list[str] = []

    def fake_get(url, headers=None):
        period = "annual" if "period=annual" in url else "ttm"
        seen.append(period)

        class _Response:
            status_code = 200

            def json(self_inner):
                fields = {name: None for name in FinancialMetrics.model_fields}
                fields.update(
                    ticker="AAPL",
                    report_period="2024-09-28",
                    period=period,
                    currency="USD",
                    earnings_per_share=6.08 if period == "annual" else 7.12,
                )
                return {"financial_metrics": [fields]}

        return _Response()

    monkeypatch.setattr("src.tools.api.requests.get", fake_get)

    ttm = get_financial_metrics("AAPL", "2024-12-31", period="ttm", limit=1)
    annual = get_financial_metrics("AAPL", "2024-12-31", period="annual", limit=1)

    assert seen == ["ttm", "annual"]
    assert ttm[0].earnings_per_share == 7.12
    assert annual[0].earnings_per_share == 6.08


def test_hurst_exponent_is_not_identically_zero():
    rng = np.random.default_rng(0)
    walk = pd.Series(np.cumsum(rng.normal(size=2000)))

    hurst = calculate_hurst_exponent(walk, max_lag=20)

    assert 0.2 < hurst < 0.8


def test_remaining_position_limit_is_floored_and_gross(monkeypatch):
    def fake_prices(ticker, start_date, end_date):
        return [Price(open=100, close=100, high=100, low=100, volume=1, time=end_date)]

    monkeypatch.setattr("src.agents.risk_manager.get_prices", fake_prices)
    portfolio = {
        "cash": 1_000.0,
        "margin_requirement": 0.0,
        "margin_used": 0.0,
        "positions": {"AAPL": {"long": 90, "short": 0, "long_cost_basis": 100.0, "short_cost_basis": 0.0, "short_margin_used": 0.0}},
        "realized_gains": {"AAPL": {"long": 0.0, "short": 0.0}},
    }
    state = {
        "messages": [],
        "data": {"portfolio": portfolio, "tickers": ["AAPL"], "end_date": "2024-01-02", "analyst_signals": {}},
        "metadata": {"position_limit": 0.20, "show_reasoning": False},
    }

    result = risk_management_agent(state)
    remaining = result["data"]["analyst_signals"]["risk_management_agent"]["AAPL"]["remaining_position_limit"]

    assert remaining == 0.0

    portfolio["positions"]["AAPL"]["long"] = 500
    portfolio["positions"]["AAPL"]["short"] = 500
    portfolio["cash"] = 100_000.0
    result = risk_management_agent(state)
    hedged = result["data"]["analyst_signals"]["risk_management_agent"]["AAPL"]["remaining_position_limit"]
    # Gross exposure is the whole book, so the limit is already spent.
    assert hedged == 0.0


def test_torn_cache_file_is_reported(tmp_path, capsys):
    (tmp_path / "api-cache.json").write_text("{not-json", encoding="utf-8")

    Cache(persist_dir=str(tmp_path))

    assert "could not be read" in capsys.readouterr().out


def test_disk_cache_writes_are_atomic_and_debounced(tmp_path):
    cache = Cache(persist_dir=str(tmp_path), debounce_seconds=60)
    cache.set_prices("AAPL", [{"time": "2024-01-01", "close": 1}], "2024-01-01", "2024-01-01")
    cache.set_prices("MSFT", [{"time": "2024-01-02", "close": 1}], "2024-01-02", "2024-01-02")

    assert not (tmp_path / "api-cache.json.tmp").exists()
    reread = Cache(persist_dir=str(tmp_path))
    assert reread.get_prices("AAPL", "2024-01-01", "2024-01-01")
    assert reread.get_prices("MSFT", "2024-01-01", "2024-01-02") == []

    cache.flush()
    flushed = Cache(persist_dir=str(tmp_path))
    assert flushed.get_prices("MSFT", "2024-01-01", "2024-01-02")

    cache.clear()
    assert not (tmp_path / "api-cache.json").exists()


def test_failed_llm_calls_back_off_and_are_counted(monkeypatch):
    monkeypatch.setenv("AI_HEDGE_FUND_LLM_BACKOFF_SECONDS", "0")

    class _Signal(BaseModel):
        signal: str
        confidence: float

    class _Boom:
        def invoke(self, prompt):
            raise RuntimeError("429 rate limit")

        def with_structured_output(self, model, method=None):
            return self

    monkeypatch.setattr("src.utils.llm.get_model", lambda *args, **kwargs: _Boom())
    monkeypatch.setattr("src.utils.llm.get_model_info", lambda *args, **kwargs: None)
    reset_degraded_analysts()

    result = call_llm(
        "prompt",
        "gpt-4o",
        "OpenAI",
        _Signal,
        agent_name=None,
        max_retries=3,
        default_factory=lambda: _Signal(signal="neutral", confidence=0.0),
    )

    assert result.signal == "neutral"
    assert degraded_analyst_count() == 1
