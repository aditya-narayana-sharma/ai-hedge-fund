"""Progress events must not leak between concurrent runs."""

import pytest

from src.utils.progress import AgentProgress


@pytest.fixture
def tracker() -> AgentProgress:
    progress = AgentProgress()
    progress.display_enabled = False
    return progress


def _collector(sink: list):
    def handler(agent_name, ticker, status, timestamp):
        sink.append((agent_name, ticker, status))

    return handler


def test_a_handler_only_sees_its_own_run(tracker):
    first, second = [], []
    tracker.register_handler(_collector(first), run_id="run-1")
    tracker.register_handler(_collector(second), run_id="run-2")

    tracker.update_status("warren_buffett_agent", "AAPL", "Done", run_id="run-1")

    assert first == [("warren_buffett_agent", "AAPL", "Done")]
    assert second == []


def test_a_run_scope_tags_updates_that_omit_the_run_id(tracker):
    events = []
    tracker.register_handler(_collector(events), run_id="run-1")

    with tracker.run_scope("run-1"):
        # Agents call update_status without knowing about runs.
        tracker.update_status("ben_graham_agent", "MSFT", "Analyzing")

    assert events == [("ben_graham_agent", "MSFT", "Analyzing")]


def test_a_global_handler_sees_every_run(tracker):
    events = []
    tracker.register_handler(_collector(events))

    tracker.update_status("sentiment_agent", None, "Done", run_id="run-1")
    tracker.update_status("sentiment_agent", None, "Done", run_id="run-2")

    assert len(events) == 2


def test_handlers_are_unregistered_per_run(tracker):
    events = []
    handler = tracker.register_handler(_collector(events), run_id="run-1")
    tracker.unregister_handler(handler, run_id="run-1")

    tracker.update_status("sentiment_agent", None, "Done", run_id="run-1")

    assert events == []


def test_statuses_do_not_accumulate_across_runs(tracker):
    tracker.update_status("warren_buffett_agent", "AAPL", "Done", run_id="run-1")
    tracker.update_status("ben_graham_agent", "MSFT", "Done", run_id="run-2")

    assert set(tracker.get_all_status("run-1")) == {"warren_buffett_agent"}

    tracker.clear_run("run-1")

    assert tracker.get_all_status("run-1") == {}
    assert set(tracker.get_all_status("run-2")) == {"ben_graham_agent"}


def test_handler_signature_matches_the_declared_contract(tracker):
    """register_handler was annotated for 3 args but always called with 4."""
    received = {}

    def handler(agent_name, ticker, status, timestamp):
        received.update(agent=agent_name, ticker=ticker, status=status, timestamp=timestamp)

    tracker.register_handler(handler, run_id="run-1")
    tracker.update_status("valuation_agent", "NVDA", "Done", run_id="run-1")

    assert received["agent"] == "valuation_agent"
    assert received["timestamp"]
