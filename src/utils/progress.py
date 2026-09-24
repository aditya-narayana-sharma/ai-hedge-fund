from datetime import datetime, timezone
from typing import Callable, Dict, List, Optional

from rich.console import Console
from rich.live import Live
from rich.style import Style
from rich.table import Table
from rich.text import Text

from src.utils.run_context import current_run

console = Console()

# (agent_name, ticker, status, timestamp) — four arguments, matching the call
# site below. The previous annotation declared three, so any handler written to
# the declared contract raised TypeError on the backend's own extension point.
ProgressHandler = Callable[[str, Optional[str], str, str], None]


class AgentProgress:
    """Manages progress tracking for multiple agents."""

    def __init__(self):
        self.agent_status: Dict[str, Dict[str, str]] = {}
        self.table = Table(show_header=False, box=None, padding=(0, 1))
        self.live = Live(self.table, console=console, refresh_per_second=4)
        self.started = False
        self.update_handlers: List[ProgressHandler] = []

    def register_handler(self, handler: ProgressHandler) -> ProgressHandler:
        """Register a process-wide handler for agent status updates.

        Server code should register on the active :class:`RunContext` instead,
        so concurrent runs do not receive each other's events.
        """
        self.update_handlers.append(handler)
        return handler  # Return handler to support use as decorator

    def unregister_handler(self, handler: ProgressHandler) -> None:
        """Unregister a previously registered handler."""
        if handler in self.update_handlers:
            self.update_handlers.remove(handler)

    def start(self):
        """Start the progress display."""
        if not self.started:
            self.live.start()
            self.started = True

    def stop(self):
        """Stop the progress display."""
        if self.started:
            self.live.stop()
            self.started = False

    def update_status(self, agent_name: str, ticker: Optional[str] = None, status: str = ""):
        """Update the status of an agent.

        Inside a run scope the status and the handlers both belong to that run,
        so two concurrent web requests never see each other's agents. Outside
        one (the CLI) this falls back to the process-wide state and repaints
        the live table.
        """
        run = current_run()
        store = run.agent_status if run is not None else self.agent_status

        if agent_name not in store:
            store[agent_name] = {"status": "", "ticker": None}

        if ticker:
            store[agent_name]["ticker"] = ticker
        if status:
            store[agent_name]["status"] = status

        # Set the timestamp as UTC datetime
        timestamp = datetime.now(timezone.utc).isoformat()
        store[agent_name]["timestamp"] = timestamp

        # Notify process-wide handlers, then this run's own handlers.
        for handler in list(self.update_handlers):
            handler(agent_name, ticker, status, timestamp)

        if run is not None:
            for handler in list(run.handlers):
                handler(agent_name, ticker, status, timestamp)
            return

        self._refresh_display()

    def get_all_status(self):
        """Get the current status of all agents in the active run as a dictionary."""
        run = current_run()
        store = run.agent_status if run is not None else self.agent_status
        return {agent_name: {"ticker": info["ticker"], "status": info["status"], "display_name": self._get_display_name(agent_name)} for agent_name, info in store.items()}

    def _get_display_name(self, agent_name: str) -> str:
        """Convert agent_name to a display-friendly format."""
        return agent_name.replace("_agent", "").replace("_", " ").title()

    def _refresh_display(self):
        """Refresh the progress display."""
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

        for agent_name, info in sorted(self.agent_status.items(), key=sort_key):
            status = info["status"]
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
