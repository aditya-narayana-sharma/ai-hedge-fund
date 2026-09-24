"""Backtesting over HTTP.

Both ``app/backend/README.md`` and ``app/README.md`` advertised a backtester
endpoint, but ``src/backtester.py`` was reachable only from the CLI. This module
drives the same ``Backtester`` class and converts its output into the wire
schema, so the API and the CLI report identical numbers.
"""

import asyncio
import math
from typing import Optional

from app.backend.models.schemas import BacktestDay, BacktestMetrics, BacktestRequest, BacktestResponse
from src.backtester import Backtester
from src.main import run_hedge_fund


def _finite(value: Optional[float]) -> Optional[float]:
    """JSON has no inf/nan, and both occur naturally here (e.g. a zero-loss win ratio)."""
    if value is None:
        return None
    number = float(value)
    return number if math.isfinite(number) else None


def build_backtester(request: BacktestRequest, graph) -> Backtester:
    """Construct a Backtester wired to an already-compiled graph."""

    def agent(**kwargs):
        return run_hedge_fund(graph=graph, **kwargs)

    return Backtester(
        agent=agent,
        tickers=request.tickers,
        start_date=request.get_start_date(),
        end_date=request.end_date,
        initial_capital=request.initial_cash,
        model_name=request.model_name,
        model_provider=getattr(request.model_provider, "value", request.model_provider),
        selected_analysts=request.selected_agents,
        initial_margin_requirement=request.margin_requirement,
        position_limit=request.position_limit,
        # Rewriting the whole results table on every simulated day would flood
        # the server log; SSE progress events carry the same information.
        verbose=False,
    )


async def run_backtest_async(backtester: Backtester) -> Backtester:
    """Run the simulation off the event loop, preserving the run context."""
    await asyncio.to_thread(backtester.run_backtest)
    return backtester


def to_response(run_id: str, backtester: Backtester) -> BacktestResponse:
    """Convert a completed Backtester into the wire schema."""
    summary = backtester.performance_summary()

    days = [
        BacktestDay(
            date=row["Date"].strftime("%Y-%m-%d") if hasattr(row["Date"], "strftime") else str(row["Date"]),
            portfolio_value=float(row["Portfolio Value"]),
            cash=float(backtester.portfolio["cash"]),
            long_exposure=float(row.get("Long Exposure", 0.0)),
            short_exposure=float(row.get("Short Exposure", 0.0)),
            gross_exposure=float(row.get("Gross Exposure", 0.0)),
            net_exposure=float(row.get("Net Exposure", 0.0)),
            long_short_ratio=_finite(row.get("Long/Short Ratio")),
        )
        for row in backtester.portfolio_values
    ]

    if not summary:
        return BacktestResponse(
            run_id=run_id,
            initial_capital=backtester.initial_capital,
            final_portfolio_value=backtester.initial_capital,
            metrics=BacktestMetrics(total_return_pct=0.0),
            portfolio_values=days,
        )

    metrics = BacktestMetrics(
        total_return_pct=summary["total_return_pct"],
        sharpe_ratio=_finite(summary["sharpe_ratio"]),
        sortino_ratio=_finite(summary["sortino_ratio"]),
        max_drawdown_pct=_finite(summary["max_drawdown_pct"]),
        max_drawdown_date=summary["max_drawdown_date"],
        win_rate_pct=_finite(summary["win_rate_pct"]),
        win_loss_ratio=_finite(summary["win_loss_ratio"]),
        total_trades=summary["total_days"],
        winning_trades=summary["winning_days"],
        losing_trades=summary["losing_days"],
    )

    return BacktestResponse(
        run_id=run_id,
        initial_capital=backtester.initial_capital,
        final_portfolio_value=summary["final_portfolio_value"],
        metrics=metrics,
        portfolio_values=days,
    )
