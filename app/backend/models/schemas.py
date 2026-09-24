import uuid
from datetime import datetime, timedelta
from typing import List, Optional

from pydantic import BaseModel, Field

from src.data.portfolio import DEFAULT_POSITION_LIMIT
from src.llm.models import ModelProvider


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
    # can filter, correlate and cancel. Nothing identified a run before this.
    run_id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    tickers: List[str] = Field(min_length=1)
    selected_agents: List[str] = Field(min_length=1)
    end_date: str = Field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d"))
    start_date: Optional[str] = None
    model_name: str = "gpt-4o"
    model_provider: ModelProvider = ModelProvider.OPENAI
    initial_cash: float = Field(default=100000.0, gt=0)
    margin_requirement: float = Field(default=0.0, ge=0)
    position_limit: float = Field(default=DEFAULT_POSITION_LIMIT, gt=0, le=1)

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
