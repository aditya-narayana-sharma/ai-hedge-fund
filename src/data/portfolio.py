"""Single source of truth for the portfolio shape and its valuation.

Before this module the identical portfolio dict was constructed independently in
``src/main.py``, ``src/backtester.py`` and ``app/backend/services/portfolio.py``,
and net liquidation value was re-derived in two more places. Two of those
valuation sites dropped the margin posted against short positions, which
understated NLV by exactly ``margin_used`` and corrupted every metric computed
from it, including the position limit that gates subsequent trades.

The graph state still carries a plain ``dict`` (LangGraph serialises it), so the
helpers here round-trip through the model rather than forcing every agent to
switch types.
"""

from pydantic import BaseModel, Field

# Fraction of net liquidation value any single position may occupy.
DEFAULT_POSITION_LIMIT = 0.20


class Position(BaseModel):
    """Share counts and cost bases for one ticker."""

    long: int = 0
    short: int = 0
    long_cost_basis: float = 0.0
    short_cost_basis: float = 0.0
    short_margin_used: float = 0.0


class RealizedGains(BaseModel):
    """Realised P&L for one ticker, split by side."""

    long: float = 0.0
    short: float = 0.0


class Portfolio(BaseModel):
    """A simulated portfolio supporting long and short positions on margin."""

    cash: float
    margin_requirement: float = 0.0
    margin_used: float = 0.0
    positions: dict[str, Position] = Field(default_factory=dict)
    realized_gains: dict[str, RealizedGains] = Field(default_factory=dict)

    @classmethod
    def create(cls, initial_cash: float, margin_requirement: float, tickers: list[str]) -> "Portfolio":
        """Build a flat portfolio with a zeroed position for every ticker."""
        return cls(
            cash=initial_cash,
            margin_requirement=margin_requirement,
            margin_used=0.0,
            positions={ticker: Position() for ticker in tickers},
            realized_gains={ticker: RealizedGains() for ticker in tickers},
        )

    def net_liquidation_value(self, prices: dict[str, float]) -> float:
        """Return ``cash + margin_used + long market value - short market value``.

        ``margin_used`` is added back because opening a short *reduces* cash by
        the posted margin. That cash is collateral held against the short, not
        an expense, so leaving it out understates NLV by exactly that amount.

        Tickers missing from ``prices`` are skipped rather than raising, which
        matches how the risk manager only prices what it could fetch.
        """
        total = self.cash + self.margin_used

        for ticker, position in self.positions.items():
            price = prices.get(ticker)
            if price is None:
                continue
            total += position.long * price
            total -= position.short * price

        return total


def create_portfolio(initial_cash: float, margin_requirement: float, tickers: list[str]) -> dict:
    """Construct the portfolio dict carried through ``AgentState['data']``."""
    return Portfolio.create(initial_cash, margin_requirement, tickers).model_dump()


def net_liquidation_value(portfolio: "dict | Portfolio", prices: dict[str, float]) -> float:
    """Value a portfolio held either as a dict or as a :class:`Portfolio`."""
    if isinstance(portfolio, Portfolio):
        return portfolio.net_liquidation_value(prices)
    return Portfolio.model_validate(portfolio).net_liquidation_value(prices)
