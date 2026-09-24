from typing import Any

from src.data.portfolio import create_portfolio as _create_portfolio


def create_portfolio(initial_cash: float, margin_requirement: float, tickers: list[str]) -> dict[str, Any]:
    return _create_portfolio(initial_cash, margin_requirement, tickers)
