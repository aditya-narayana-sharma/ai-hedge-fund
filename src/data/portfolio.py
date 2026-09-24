"""Shared portfolio shape and valuation.

The CLI, the backtester and the FastAPI service all build the same portfolio
structure and all need its net liquidation value. Keeping three hand-rolled
copies is what let two of them silently drop the margin posted against shorts,
so both the construction and the valuation live here.
"""

from typing import Any

from pydantic import BaseModel, Field


class Position(BaseModel):
    """Long and short holdings in a single ticker."""

    long: int = 0
    short: int = 0
    long_cost_basis: float = 0.0
    short_cost_basis: float = 0.0
    short_margin_used: float = 0.0


class RealizedGains(BaseModel):
    """Booked profit and loss for a single ticker, split by side."""

    long: float = 0.0
    short: float = 0.0


class Portfolio(BaseModel):
    """A trading account: cash, margin, open positions and realized gains."""

    cash: float
    margin_requirement: float = 0.0
    margin_used: float = 0.0
    positions: dict[str, Position] = Field(default_factory=dict)
    realized_gains: dict[str, RealizedGains] = Field(default_factory=dict)

    @classmethod
    def create(cls, initial_cash: float, margin_requirement: float, tickers: list[str]) -> "Portfolio":
        """Build an empty portfolio holding a zeroed position in each ticker."""
        return cls(
            cash=initial_cash,
            margin_requirement=margin_requirement,
            margin_used=0.0,
            positions={ticker: Position() for ticker in tickers},
            realized_gains={ticker: RealizedGains() for ticker in tickers},
        )

    def net_liquidation_value(self, prices: dict[str, float]) -> float:
        """Value the account at the given prices.

        ``cash + margin_used + Σ long×price − Σ short×price``.

        ``margin_used`` is added back because opening a short deducts the posted
        margin from cash; without it, net liquidation value is understated by
        exactly the margin whenever a short is open. Tickers missing from
        ``prices`` are skipped rather than guessed at.
        """
        total = self.cash + self.margin_used
        for ticker, position in self.positions.items():
            price = prices.get(ticker)
            if price is None:
                continue
            total += position.long * price
            total -= position.short * price
        return total


def create_portfolio(initial_cash: float, margin_requirement: float, tickers: list[str]) -> dict[str, Any]:
    """Create the canonical portfolio dict consumed by the agent graph."""
    return Portfolio.create(initial_cash, margin_requirement, tickers).model_dump()


def net_liquidation_value(portfolio: Portfolio | dict[str, Any], prices: dict[str, float]) -> float:
    """Value a portfolio held either as a model or as the graph's plain dict."""
    if not isinstance(portfolio, Portfolio):
        portfolio = Portfolio.model_validate(portfolio)
    return portfolio.net_liquidation_value(prices)
