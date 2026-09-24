"""Run isolation.

Two concurrent runs used to share one progress handler list and one cache, so
each browser animated the other user's agents and status accumulated forever.
"""

import threading

from src.utils.progress import progress
from src.utils.run_context import current_run, new_run_context, resolve_cache, run_scope


def test_no_context_resolves_the_process_cache():
    from src.data.cache import get_cache

    assert current_run() is None
    assert resolve_cache() is get_cache()


def test_each_run_gets_its_own_cache():
    first, second = new_run_context(), new_run_context()

    assert first.run_id != second.run_id
    assert first.cache is not second.cache

    with run_scope(first):
        assert resolve_cache() is first.cache
    with run_scope(second):
        assert resolve_cache() is second.cache


def test_scope_is_restored_on_exit():
    context = new_run_context()

    with run_scope(context):
        assert current_run() is context
    assert current_run() is None


def test_handlers_only_receive_their_own_run():
    first, second = new_run_context("run-1"), new_run_context("run-2")
    first_events, second_events = [], []

    first.register_handler(lambda agent, ticker, status, ts: first_events.append((agent, status)))
    second.register_handler(lambda agent, ticker, status, ts: second_events.append((agent, status)))

    with run_scope(first):
        progress.update_status("warren_buffett_agent", "AAPL", "Analysing")
    with run_scope(second):
        progress.update_status("michael_burry_agent", "MSFT", "Analysing")

    assert first_events == [("warren_buffett_agent", "Analysing")]
    assert second_events == [("michael_burry_agent", "Analysing")]


def test_agent_status_does_not_leak_between_runs():
    first, second = new_run_context(), new_run_context()

    with run_scope(first):
        progress.update_status("warren_buffett_agent", "AAPL", "Done")
        assert "warren_buffett_agent" in progress.get_all_status()

    with run_scope(second):
        assert progress.get_all_status() == {}


def test_context_propagates_into_a_worker_thread():
    """LangGraph runs nodes on a thread pool, and asyncio.to_thread copies context."""
    import contextvars

    context = new_run_context()
    seen = {}

    def worker():
        seen["cache"] = resolve_cache()
        seen["run_id"] = context.run_id if current_run() else None

    with run_scope(context):
        thread = threading.Thread(target=contextvars.copy_context().run, args=(worker,))
        thread.start()
        thread.join()

    assert seen["cache"] is context.cache
    assert seen["run_id"] == context.run_id


def test_unregistering_a_handler_stops_delivery():
    context = new_run_context()
    events = []

    def handler(agent, ticker, status, timestamp):
        events.append(agent)

    context.register_handler(handler)
    with run_scope(context):
        progress.update_status("warren_buffett_agent", None, "Analysing")

    context.unregister_handler(handler)
    with run_scope(context):
        progress.update_status("michael_burry_agent", None, "Analysing")

    assert events == ["warren_buffett_agent"]
