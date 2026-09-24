from datetime import datetime, timedelta
from pydantic import BaseModel, Field, field_validator
from typing import List, Optional
from uuid import uuid4

from src.agents.risk_manager import DEFAULT_POSITION_LIMIT_PCT
from src.llm.models import ModelProvider


class HedgeFundResponse(BaseModel):
    run_id: str
    decisions: dict
    analyst_signals: dict


class ErrorResponse(BaseModel):
    message: str
    error: str | None = None


class RunRequest(BaseModel):
    """Fields shared by every request that drives the agent graph."""

    tickers: List[str]
    selected_agents: List[str]
    model_name: str = "gpt-4o"
    model_provider: ModelProvider = ModelProvider.OPENAI
    initial_cash: float = 100000.0
    margin_requirement: float = 0.0
    position_limit_pct: float = DEFAULT_POSITION_LIMIT_PCT
    # Identifies this run in every SSE event, so a client can filter a shared
    # stream and so cancellation has something to address.
    run_id: str = Field(default_factory=lambda: str(uuid4()))

    @field_validator("tickers")
    @classmethod
    def _require_tickers(cls, tickers: List[str]) -> List[str]:
        cleaned = [ticker.strip().upper() for ticker in tickers if ticker.strip()]
        if not cleaned:
            raise ValueError("At least one ticker is required")
        return cleaned


class HedgeFundRequest(RunRequest):
    end_date: Optional[str] = Field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d"))
    start_date: Optional[str] = None

    def get_start_date(self) -> str:
        """Calculate start date if not provided"""
        if self.start_date:
            return self.start_date
        return (datetime.strptime(self.end_date, "%Y-%m-%d") - timedelta(days=90)).strftime("%Y-%m-%d")


class BacktestRequest(RunRequest):
    """A backtest over a date range, one hedge fund pass per business day."""

    end_date: str = Field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d"))
    start_date: Optional[str] = None

    def get_start_date(self) -> str:
        if self.start_date:
            return self.start_date
        return (datetime.strptime(self.end_date, "%Y-%m-%d") - timedelta(days=30)).strftime("%Y-%m-%d")


class EquityPoint(BaseModel):
    date: str
    portfolio_value: float
    long_exposure: float | None = None
    short_exposure: float | None = None
    gross_exposure: float | None = None
    net_exposure: float | None = None


class BacktestMetrics(BaseModel):
    total_return_pct: float
    sharpe_ratio: float | None = None
    sortino_ratio: float | None = None
    max_drawdown_pct: float | None = None
    max_drawdown_date: str | None = None
    win_rate_pct: float | None = None
    win_loss_ratio: float | None = None
    max_consecutive_wins: int | None = None
    max_consecutive_losses: int | None = None


class BacktestResponse(BaseModel):
    run_id: str
    metrics: BacktestMetrics
    equity_curve: List[EquityPoint]
    final_portfolio: dict


class AgentSummary(BaseModel):
    """One analyst, as the UI needs it."""

    key: str
    display_name: str
    description: str | None = None
    order: int


class ModelSummary(BaseModel):
    """One selectable LLM, as the UI needs it."""

    display_name: str
    model_name: str
    provider: str
    supports_json_mode: bool
