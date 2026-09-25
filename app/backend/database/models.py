"""Persisted run history.

``pyproject.toml`` has declared SQLAlchemy and Alembic since the backend was
added, with no models, no ``alembic.ini`` and no migrations directory. This is
the table those dependencies were for: one row per hedge-fund or backtest run,
so a run identifier stays meaningful after the SSE stream closes.
"""

from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Declarative base for every backend table."""


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Run(Base):
    """One hedge-fund pass or backtest, keyed by the run_id sent on every event."""

    __tablename__ = "runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    # "hedge_fund" or "backtest".
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    # "running", "complete" or "error".
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="running")

    tickers: Mapped[str] = mapped_column(String(512), nullable=False)
    selected_agents: Mapped[str] = mapped_column(Text, nullable=False)
    model_name: Mapped[str] = mapped_column(String(128), nullable=False)
    model_provider: Mapped[str] = mapped_column(String(64), nullable=False)
    start_date: Mapped[str] = mapped_column(String(10), nullable=False)
    end_date: Mapped[str] = mapped_column(String(10), nullable=False)
    initial_cash: Mapped[float] = mapped_column(Float, nullable=False)
    margin_requirement: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    position_limit: Mapped[float] = mapped_column(Float, nullable=False, default=0.2)

    # JSON-encoded result payload, or the error message when status is "error".
    result: Mapped[str | None] = mapped_column(Text, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
