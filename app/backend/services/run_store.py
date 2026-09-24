"""Recording run history, when a database is configured.

Every function here is a no-op without ``AI_HEDGE_FUND_DATABASE_URL``, and none
of them is allowed to fail a request: losing a history row must never cost the
caller their simulation.
"""

import json
from datetime import datetime, timezone
from typing import Any, Optional

from app.backend.database import is_enabled, Run, session_scope
from app.backend.models.schemas import RunRequestBase


def record_started(kind: str, request: RunRequestBase) -> None:
    """Insert a 'running' row for this request."""
    if not is_enabled():
        return

    try:
        with session_scope() as session:
            if session is None:
                return
            session.add(
                Run(
                    run_id=request.run_id,
                    kind=kind,
                    status="running",
                    tickers=",".join(request.tickers),
                    selected_agents=json.dumps(request.selected_agents),
                    model_name=request.model_name,
                    model_provider=getattr(request.model_provider, "value", str(request.model_provider)),
                    start_date=request.get_start_date(),
                    end_date=request.end_date,
                    initial_cash=request.initial_cash,
                    margin_requirement=request.margin_requirement,
                    position_limit=request.position_limit,
                )
            )
    except Exception as exc:
        print(f"Could not record run {request.run_id}: {exc}")


def record_finished(run_id: str, result: Optional[Any] = None, error: Optional[str] = None) -> None:
    """Mark the run complete or failed."""
    if not is_enabled():
        return

    try:
        with session_scope() as session:
            if session is None:
                return
            run = session.query(Run).filter(Run.run_id == run_id).one_or_none()
            if run is None:
                return
            run.status = "error" if error else "complete"
            run.error = error
            run.result = json.dumps(result, default=str) if result is not None else None
            run.finished_at = datetime.now(timezone.utc)
    except Exception as exc:
        print(f"Could not finalise run {run_id}: {exc}")
