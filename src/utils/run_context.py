"""Per-run isolation for state that used to be process-global.

``src/utils/progress.py`` and ``src/data/cache.py`` were written for a CLI that
runs one simulation per process. The web backend imported both verbatim, so two
concurrent ``POST /hedge-fund/run`` calls pushed into one shared handler list —
each browser animated the other user's agents — and shared a single untenanted
cache.

A run now owns its own cache and its own progress handlers, published through a
:class:`contextvars.ContextVar`. Both LangGraph's internal thread pool and
``asyncio.to_thread`` copy the active context, so agents executing off the event
loop still resolve the run they belong to. With no context set, callers fall
back to the process-wide instances, which is exactly what the CLI wants.
"""

import contextvars
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Callable, Iterator, Optional

from src.data.cache import Cache, get_cache

# (agent_name, ticker, status, timestamp)
ProgressHandler = Callable[[str, Optional[str], str, str], None]


@dataclass
class RunContext:
    """Everything one hedge-fund run must not share with another."""

    run_id: str
    cache: Cache
    handlers: list[ProgressHandler] = field(default_factory=list)
    agent_status: dict[str, dict[str, str]] = field(default_factory=dict)

    def register_handler(self, handler: ProgressHandler) -> ProgressHandler:
        self.handlers.append(handler)
        return handler

    def unregister_handler(self, handler: ProgressHandler) -> None:
        if handler in self.handlers:
            self.handlers.remove(handler)


_current_run: contextvars.ContextVar[Optional[RunContext]] = contextvars.ContextVar(
    "ai_hedge_fund_run_context",
    default=None,
)


def new_run_context(run_id: str | None = None) -> RunContext:
    """Create an isolated run with its own cache."""
    return RunContext(run_id=run_id or uuid.uuid4().hex, cache=Cache())


def current_run() -> Optional[RunContext]:
    """Return the run bound to this context, or ``None`` outside a run scope."""
    return _current_run.get()


def current_run_id() -> Optional[str]:
    run = current_run()
    return run.run_id if run else None


def resolve_cache() -> Cache:
    """Return the active run's cache, or the process-wide one for the CLI."""
    run = current_run()
    return run.cache if run is not None else get_cache()


@contextmanager
def run_scope(context: RunContext) -> Iterator[RunContext]:
    """Bind ``context`` for the duration of the block."""
    token = _current_run.set(context)
    try:
        yield context
    finally:
        _current_run.reset(token)
