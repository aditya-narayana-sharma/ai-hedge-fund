import uuid
from datetime import date, datetime, timedelta
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

from src.data.portfolio import DEFAULT_POSITION_LIMIT
from src.llm.models import ModelProvider

# A century of business days is not a backtest, it is an unbounded LLM bill.
MAX_DATE_RANGE_DAYS = 365 * 10


def _parse_iso_date(value: str, field_name: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{field_name} must be an ISO date (YYYY-MM-DD).") from exc


class HedgeFundResponse(BaseModel):
    run_id: str
    decisions: dict
    analyst_signals: dict


class ErrorResponse(BaseModel):
    message: str
    error: str | None = None


class RunRequestBase(BaseModel):
    """Fields shared by the hedge-fund and backtest endpoints."""

    # Addressable identity for the run, echoed on every SSE event so a client
    # can filter, correlate and cancel. Assigned here, never accepted from the
    # client: a caller-chosen id overwrites another run's history row.
    run_id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    tickers: List[str] = Field(min_length=1)
    selected_agents: List[str] = Field(min_length=1)
    end_date: str = Field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d"))
    start_date: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def reject_client_run_id(cls, data):
        if isinstance(data, dict) and "run_id" in data:
            raise ValueError("run_id is assigned by the server and cannot be supplied by the client.")
        return data

    @field_validator("end_date")
    @classmethod
    def end_date_is_iso(cls, value: str) -> str:
        _parse_iso_date(value, "end_date")
        return value

    @field_validator("start_date")
    @classmethod
    def start_date_is_iso(cls, value: Optional[str]) -> Optional[str]:
        if value is not None:
            _parse_iso_date(value, "start_date")
        return value

    @model_validator(mode="after")
    def dates_form_a_bounded_range(self):
        end = date.fromisoformat(self.end_date)
        start = date.fromisoformat(self.get_start_date())
        if start >= end:
            raise ValueError("start_date must be earlier than end_date.")
        if (end - start).days > MAX_DATE_RANGE_DAYS:
            raise ValueError(f"Date range cannot exceed {MAX_DATE_RANGE_DAYS} days.")
        return self

    model_name: str = "gpt-4o"
    model_provider: ModelProvider = ModelProvider.OPENAI
    initial_cash: float = Field(default=100000.0, gt=0)
    margin_requirement: float = Field(default=0.0, ge=0)
    position_limit: float = Field(default=DEFAULT_POSITION_LIMIT, gt=0, le=1)
    # Replaces the hard-coded opening HumanMessage, so an operator can steer
    # the run ("prioritise downside risk", "assume a 12-month horizon") without
    # editing the graph.
    prompt: Optional[str] = Field(default=None, max_length=2000)

    def get_start_date(self) -> str:
        """Calculate start date if not provided"""
        if self.start_date:
            return self.start_date
        return (datetime.strptime(self.end_date, "%Y-%m-%d") - timedelta(days=90)).strftime("%Y-%m-%d")


class HedgeFundRequest(RunRequestBase):
    """One pass of the agent graph over a ticker list."""


class BacktestRequest(RunRequestBase):
    """A day-by-day simulation across a date range."""

    # Backtests need a meaningfully longer window than a single pass, so the
    # implicit default reaches back a year rather than 90 days.
    def get_start_date(self) -> str:
        if self.start_date:
            return self.start_date
        return (datetime.strptime(self.end_date, "%Y-%m-%d") - timedelta(days=365)).strftime("%Y-%m-%d")


class BacktestDay(BaseModel):
    """One simulated trading day."""

    date: str
    portfolio_value: float
    cash: float
    long_exposure: float
    short_exposure: float
    gross_exposure: float
    net_exposure: float
    long_short_ratio: Optional[float] = None


class BacktestMetrics(BaseModel):
    """Summary performance of a completed backtest."""

    total_return_pct: float
    sharpe_ratio: Optional[float] = None
    sortino_ratio: Optional[float] = None
    max_drawdown_pct: Optional[float] = None
    max_drawdown_date: Optional[str] = None
    win_rate_pct: Optional[float] = None
    win_loss_ratio: Optional[float] = None
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0


class BacktestResponse(BaseModel):
    run_id: str
    initial_capital: float
    final_portfolio_value: float
    metrics: BacktestMetrics
    portfolio_values: List[BacktestDay]


class AgentInfo(BaseModel):
    """One entry of GET /agents, derived from ANALYST_CONFIG."""

    key: str
    display_name: str
    description: str
    order: int


class ModelInfo(BaseModel):
    """One entry of GET /models, derived from the LLM catalog JSON."""

    display_name: str
    model_name: str
    provider: str
    supports_json_mode: bool
