from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.backend.models.schemas import ErrorResponse, HedgeFundRequest
from app.backend.services.graph import create_graph, run_graph_async, validate_agents
from app.backend.services.portfolio import create_portfolio
from app.backend.services.run_store import record_finished, record_started
from app.backend.services.streaming import sse_run_stream
from src.utils.json_parsing import parse_hedge_fund_response

router = APIRouter(prefix="/hedge-fund")


@router.post(
    path="/run",
    responses={
        200: {"description": "Successful response with streaming updates"},
        400: {"model": ErrorResponse, "description": "Invalid request parameters"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)
async def run_hedge_fund(request: HedgeFundRequest):
    # Reject an unknown or empty agent list up front with a 400, rather than
    # silently dropping the keys and returning a hollow 200.
    try:
        selected_agents = validate_agents(request.selected_agents)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    start_date = request.get_start_date()
    portfolio = create_portfolio(request.initial_cash, request.margin_requirement, request.tickers)
    graph = create_graph(selected_agents).compile()

    model_provider = getattr(request.model_provider, "value", request.model_provider)

    async def runner():
        return await run_graph_async(
            graph=graph,
            portfolio=portfolio,
            tickers=request.tickers,
            start_date=start_date,
            end_date=request.end_date,
            model_name=request.model_name,
            model_provider=model_provider,
            position_limit=request.position_limit,
            prompt=request.prompt,
        )

    def to_payload(result: dict) -> dict:
        messages = result.get("messages") or []
        if not messages:
            raise RuntimeError("The agent graph produced no messages, so there are no decisions to report.")
        return {
            "decisions": parse_hedge_fund_response(messages[-1].content),
            "analyst_signals": result.get("data", {}).get("analyst_signals", {}),
        }

    record_started("hedge_fund", request)

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
