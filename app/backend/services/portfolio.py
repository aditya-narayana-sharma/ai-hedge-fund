from src.data.portfolio import create_portfolio as _create_portfolio


def create_portfolio(initial_cash: float, margin_requirement: float, tickers: list[str]) -> dict:
    """Thin re-export so the backend shares one portfolio definition with the engine."""
    return _create_portfolio(initial_cash, margin_requirement, tickers)
