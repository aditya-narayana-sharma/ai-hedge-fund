from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.backend.models.schemas import BacktestRequest, ErrorResponse
from app.backend.services.backtest import build_backtester, run_backtest_async, to_response
from app.backend.services.graph import create_graph, validate_agents
from app.backend.services.run_store import record_finished, record_started
from app.backend.services.streaming import sse_run_stream

router = APIRouter()


@router.post(
    path="/backtest",
    responses={
        200: {"description": "Successful response with streaming updates"},
        400: {"model": ErrorResponse, "description": "Invalid request parameters"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)
async def run_backtest(request: BacktestRequest):
    """Simulate the strategy day by day, streaming the same SSE envelope as /hedge-fund/run."""
    try:
        selected_agents = validate_agents(request.selected_agents)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    if request.get_start_date() >= request.end_date:
        raise HTTPException(status_code=400, detail="start_date must be earlier than end_date.")

    graph = create_graph(selected_agents).compile()
    backtester = build_backtester(request, graph)

    async def runner():
        return await run_backtest_async(backtester)

    def to_payload(completed) -> dict:
        return to_response(request.run_id, completed).model_dump()

    record_started("backtest", request)

    return StreamingResponse(
        sse_run_stream(
            request.run_id,
            runner,
            to_payload,
            on_complete=lambda payload: record_finished(request.run_id, result=payload),
            on_error=lambda message: record_finished(request.run_id, error=message),
        ),
        media_type="text/event-stream",
        headers={"X-Run-Id": request.run_id},
    )
