"""Run the backtester over HTTP, streaming one event per simulated day.

Both app READMEs advertised "the hedge fund trading system and backtester",
but 776 lines of metrics logic were reachable only from the CLI.
"""

import asyncio
from functools import partial

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.backend.models.events import BacktestDayEvent, CompleteEvent, ErrorEvent, ProgressUpdateEvent, StartEvent
from app.backend.models.schemas import BacktestMetrics, BacktestRequest, BacktestResponse, EquityPoint, ErrorResponse
from app.backend.services.graph import validate_selected_agents
from src.backtester import Backtester
from src.main import run_hedge_fund
from src.utils.progress import progress

router = APIRouter(prefix="/backtest")


@router.post(
    path="/run",
    responses={
        200: {"description": "Successful response with streaming updates"},
        400: {"model": ErrorResponse, "description": "Invalid request parameters"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)
async def run_backtest(request: BacktestRequest):
    try:
        selected_agents = validate_selected_agents(request.selected_agents)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    start_date = request.get_start_date()
    if start_date > request.end_date:
        raise HTTPException(status_code=400, detail="start_date must not be after end_date")

    model_provider = request.model_provider
    if hasattr(model_provider, "value"):
        model_provider = model_provider.value

    run_id = request.run_id

    async def event_generator():
        loop = asyncio.get_running_loop()
        event_queue: asyncio.Queue = asyncio.Queue()

        def progress_handler(agent_name, ticker, status, timestamp):
            event_queue.put_nowait(ProgressUpdateEvent(run_id=run_id, agent=agent_name, ticker=ticker, status=status, timestamp=timestamp))

        def day_handler(day: dict):
            # Called from the executor thread, so hand the event back to the loop.
            loop.call_soon_threadsafe(
                event_queue.put_nowait,
                BacktestDayEvent(run_id=run_id, date=day["date"], portfolio_value=day["portfolio_value"], return_pct=day["return_pct"]),
            )

        progress.register_handler(progress_handler, run_id=run_id)

        backtester = Backtester(
            agent=partial(run_hedge_fund, position_limit_pct=request.position_limit_pct),
            tickers=request.tickers,
            start_date=start_date,
            end_date=request.end_date,
            initial_capital=request.initial_cash,
            model_name=request.model_name,
            model_provider=model_provider,
            selected_analysts=selected_agents,
            initial_margin_requirement=request.margin_requirement,
            on_day=day_handler,
            verbose=False,
        )

        def run_sync():
            with progress.run_scope(run_id):
                backtester.run_backtest()
                return backtester.summarize_performance()

        run_task = asyncio.create_task(loop.run_in_executor(None, run_sync))

        try:
            yield StartEvent(run_id=run_id).to_sse()

            while not run_task.done():
                try:
                    event = await asyncio.wait_for(event_queue.get(), timeout=1.0)
                    yield event.to_sse()
                except asyncio.TimeoutError:
                    pass

            # Drain anything that landed between the last poll and completion.
            while not event_queue.empty():
                yield event_queue.get_nowait().to_sse()

            try:
                summary = run_task.result()
            except asyncio.CancelledError:
                raise
            except Exception as e:
                yield ErrorEvent(run_id=run_id, message=f"{type(e).__name__}: {e}").to_sse()
                return

            if not summary:
                yield ErrorEvent(run_id=run_id, message="Backtest produced no portfolio data. Check the ticker list and date range.").to_sse()
                return

            yield CompleteEvent(run_id=run_id, data=_build_response(run_id, backtester, summary).model_dump()).to_sse()

        finally:
            progress.unregister_handler(progress_handler, run_id=run_id)
            progress.clear_run(run_id)
            if not run_task.done():
                run_task.cancel()

    return StreamingResponse(event_generator(), media_type="text/event-stream")


def _build_response(run_id: str, backtester: Backtester, summary: dict) -> BacktestResponse:
    equity_curve = [
        EquityPoint(
            date=point["Date"].strftime("%Y-%m-%d"),
            portfolio_value=float(point["Portfolio Value"]),
            long_exposure=_optional_float(point.get("Long Exposure")),
            short_exposure=_optional_float(point.get("Short Exposure")),
            gross_exposure=_optional_float(point.get("Gross Exposure")),
            net_exposure=_optional_float(point.get("Net Exposure")),
        )
        for point in backtester.portfolio_values
    ]

    return BacktestResponse(
        run_id=run_id,
        metrics=BacktestMetrics(
            total_return_pct=summary["total_return_pct"],
            sharpe_ratio=_finite(summary.get("sharpe_ratio")),
            sortino_ratio=_finite(summary.get("sortino_ratio")),
            max_drawdown_pct=summary.get("max_drawdown_pct"),
            max_drawdown_date=summary.get("max_drawdown_date"),
            win_rate_pct=summary.get("win_rate_pct"),
            win_loss_ratio=_finite(summary.get("win_loss_ratio")),
            max_consecutive_wins=summary.get("max_consecutive_wins"),
            max_consecutive_losses=summary.get("max_consecutive_losses"),
        ),
        equity_curve=equity_curve,
        final_portfolio=backtester.portfolio,
    )


def _optional_float(value) -> float | None:
    return None if value is None else float(value)


def _finite(value) -> float | None:
    """Drop infinities, which are valid Python floats but not valid JSON."""
    if value is None:
        return None
    value = float(value)
    return value if value == value and abs(value) != float("inf") else None
