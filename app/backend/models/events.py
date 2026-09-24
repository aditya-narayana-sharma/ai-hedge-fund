from typing import Dict, Optional, Any, Literal
from pydantic import BaseModel


class BaseEvent(BaseModel):
    """Base class for all Server-Sent Event events"""

    type: str
    # Set on every event so a client can tell whose run it is watching.
    run_id: Optional[str] = None

    def to_sse(self) -> str:
        """Convert to Server-Sent Event format"""
        event_type = self.type.lower()
        return f"event: {event_type}\ndata: {self.model_dump_json()}\n\n"


class StartEvent(BaseEvent):
    """Event indicating the start of processing"""

    type: Literal["start"] = "start"
    timestamp: Optional[str] = None


class ProgressUpdateEvent(BaseEvent):
    """Event containing an agent's progress update"""

    type: Literal["progress"] = "progress"
    agent: str
    ticker: Optional[str] = None
    status: str
    timestamp: Optional[str] = None


class ErrorEvent(BaseEvent):
    """Event indicating an error occurred"""

    type: Literal["error"] = "error"
    message: str
    timestamp: Optional[str] = None


class CompleteEvent(BaseEvent):
    """Event indicating successful completion with results"""

    type: Literal["complete"] = "complete"
    data: Dict[str, Any]
    timestamp: Optional[str] = None


class BacktestDayEvent(BaseEvent):
    """Event carrying one simulated trading day's result"""

    type: Literal["backtest_day"] = "backtest_day"
    date: str
    portfolio_value: float
    return_pct: float
    timestamp: Optional[str] = None
