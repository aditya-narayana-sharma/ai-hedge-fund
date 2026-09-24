from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timezone
from rich.console import Console
from rich.live import Live
from rich.table import Table
from rich.style import Style
from rich.text import Text
from typing import Dict, Iterator, Optional, Callable, List

console = Console()

# Handlers receive (agent_name, ticker, status, timestamp).
ProgressHandler = Callable[[str, Optional[str], str, str], None]

# Identifies the run whose agents are currently emitting progress. The CLI
# leaves it unset; the API sets it per request so two concurrent runs do not
# push their events into each other's streams.
_current_run_id: ContextVar[Optional[str]] = ContextVar("current_run_id", default=None)


class AgentProgress:
    """Manages progress tracking for multiple agents, scoped per run."""

    def __init__(self):
        self.agent_status: Dict[Optional[str], Dict[str, Dict[str, Optional[str]]]] = {}
        self.update_handlers: Dict[Optional[str], List[ProgressHandler]] = {}
        self.table = Table(show_header=False, box=None, padding=(0, 1))
        self.live = Live(self.table, console=console, refresh_per_second=4)
        self.started = False
        # The rich Live table is a terminal affordance; a server process
        # registers handlers instead and must not paint to stdout.
        self.display_enabled = True

    def disable_display(self) -> None:
        """Stop rendering the terminal progress table."""
        self.stop()
        self.display_enabled = False

    def register_handler(self, handler: ProgressHandler, run_id: Optional[str] = None) -> ProgressHandler:
        """Register a handler for one run, or for every run when run_id is None."""
        self.update_handlers.setdefault(run_id, []).append(handler)
        return handler  # Return handler to support use as decorator

    def unregister_handler(self, handler: ProgressHandler, run_id: Optional[str] = None) -> None:
        """Unregister a previously registered handler."""
        handlers = self.update_handlers.get(run_id, [])
        if handler in handlers:
            handlers.remove(handler)
        if not handlers:
            self.update_handlers.pop(run_id, None)

    @contextmanager
    def run_scope(self, run_id: str) -> Iterator[str]:
        """Tag every progress update inside this block with ``run_id``.

        Works across the executor thread the API runs the graph on, provided
        the thread enters the scope itself.
        """
        token = _current_run_id.set(run_id)
        try:
            yield run_id
        finally:
            _current_run_id.reset(token)

    def clear_run(self, run_id: Optional[str]) -> None:
        """Drop a run's accumulated agent statuses."""
        self.agent_status.pop(run_id, None)

    def start(self):
        """Start the progress display."""
        if self.display_enabled and not self.started:
            self.live.start()
            self.started = True

    def stop(self):
        """Stop the progress display."""
        if self.started:
            self.live.stop()
            self.started = False

    def update_status(self, agent_name: str, ticker: Optional[str] = None, status: str = "", run_id: Optional[str] = None):
        """Update the status of an agent."""
        run_id = run_id if run_id is not None else _current_run_id.get()
        statuses = self.agent_status.setdefault(run_id, {})

        if agent_name not in statuses:
            statuses[agent_name] = {"status": "", "ticker": None}

        if ticker:
            statuses[agent_name]["ticker"] = ticker
        if status:
            statuses[agent_name]["status"] = status

        # Set the timestamp as UTC datetime
        timestamp = datetime.now(timezone.utc).isoformat()
        statuses[agent_name]["timestamp"] = timestamp

        # Notify this run's handlers plus any handler registered for all runs.
        for handler in [*self.update_handlers.get(run_id, []), *(self.update_handlers.get(None, []) if run_id is not None else [])]:
            handler(agent_name, ticker, status, timestamp)

        self._refresh_display(run_id)

    def get_all_status(self, run_id: Optional[str] = None):
        """Get the current status of all agents as a dictionary."""
        run_id = run_id if run_id is not None else _current_run_id.get()
        statuses = self.agent_status.get(run_id, {})
        return {agent_name: {"ticker": info["ticker"], "status": info["status"], "display_name": self._get_display_name(agent_name)} for agent_name, info in statuses.items()}

    def _get_display_name(self, agent_name: str) -> str:
        """Convert agent_name to a display-friendly format."""
        return agent_name.replace("_agent", "").replace("_", " ").title()

    def _refresh_display(self, run_id: Optional[str] = None):
        """Refresh the progress display."""
        if not self.display_enabled:
            return

        self.table.columns.clear()
        self.table.add_column(width=100)

        # Sort agents with Risk Management and Portfolio Management at the bottom
        def sort_key(item):
            agent_name = item[0]
            if "risk_management" in agent_name:
                return (2, agent_name)
            elif "portfolio_management" in agent_name:
                return (3, agent_name)
            else:
                return (1, agent_name)

        for agent_name, info in sorted(self.agent_status.get(run_id, {}).items(), key=sort_key):
            status = info["status"] or ""
            ticker = info["ticker"]
            # Create the status text with appropriate styling
            if status.lower() == "done":
                style = Style(color="green", bold=True)
                symbol = "✓"
            elif status.lower() == "error":
                style = Style(color="red", bold=True)
                symbol = "✗"
            else:
                style = Style(color="yellow")
                symbol = "⋯"

            agent_display = self._get_display_name(agent_name)
            status_text = Text()
            status_text.append(f"{symbol} ", style=style)
            status_text.append(f"{agent_display:<20}", style=Style(bold=True))

            if ticker:
                status_text.append(f"[{ticker}] ", style=Style(color="cyan"))
            status_text.append(status, style=style)

            self.table.add_row(status_text)


# Create a global instance
progress = AgentProgress()
