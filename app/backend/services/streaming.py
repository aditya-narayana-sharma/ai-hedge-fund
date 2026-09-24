"""Shared Server-Sent Events plumbing for long-running endpoints.

Both ``POST /hedge-fund/run`` and ``POST /backtest`` need the same four things:
an isolated run context, progress bridged from a worker thread onto the event
loop, a terminal ``complete`` event, and — the part that was missing — an
``error`` event when the work raises.

Previously the graph's exception surfaced from ``run_task.result()`` *inside*
the generator, after ``200 OK`` and the ``start`` event had already been
flushed. The ``ErrorEvent`` was only reachable when the result was falsy, not
when it threw, so a failed run simply stopped mid-stream with no explanation.
"""

import asyncio
import traceback
from typing import Any, AsyncIterator, Awaitable, Callable

from app.backend.models.events import CompleteEvent, ErrorEvent, ProgressUpdateEvent, StartEvent
from src.utils.run_context import new_run_context, run_scope, RunContext

# How long to wait for a progress event before re-checking whether the work
# finished. Bounds shutdown latency without busy-waiting.
_POLL_TIMEOUT_SECONDS = 1.0


async def sse_run_stream(
    run_id: str,
    runner: Callable[[], Awaitable[Any]],
    to_payload: Callable[[Any], dict],
    on_complete: Callable[[dict], None] | None = None,
    on_error: Callable[[str], None] | None = None,
) -> AsyncIterator[str]:
    """Stream one run as SSE: ``start``, then ``progress``*, then ``complete`` or ``error``."""
    context = new_run_context(run_id)
    queue: asyncio.Queue[ProgressUpdateEvent] = asyncio.Queue()
    loop = asyncio.get_running_loop()

    def progress_handler(agent_name: str, ticker: str | None, status: str, timestamp: str) -> None:
        # Called from the worker thread, so hand the event to the loop rather
        # than touching the queue directly.
        event = ProgressUpdateEvent(run_id=run_id, agent=agent_name, ticker=ticker, status=status, timestamp=timestamp)
        loop.call_soon_threadsafe(queue.put_nowait, event)

    context.register_handler(progress_handler)

    # Bind the context only while the task is created: the task captures it,
    # and asyncio.to_thread copies it on into the worker thread. Holding the
    # binding across a yield would risk resetting a token from another context.
    task = _create_task_in_run(context, runner())

    try:
        yield StartEvent(run_id=run_id).to_sse()

        while not task.done():
            try:
                event = await asyncio.wait_for(queue.get(), timeout=_POLL_TIMEOUT_SECONDS)
            except asyncio.TimeoutError:
                continue
            yield event.to_sse()

        # Drain progress emitted between the last poll and completion.
        while not queue.empty():
            yield queue.get_nowait().to_sse()

        result = task.result()
        payload = to_payload(result)
        if on_complete is not None:
            on_complete(payload)
        yield CompleteEvent(run_id=run_id, data=payload).to_sse()

    except asyncio.CancelledError:
        raise
    except Exception as exc:
        traceback.print_exc()
        message = f"{type(exc).__name__}: {exc}"
        if on_error is not None:
            on_error(message)
        yield ErrorEvent(run_id=run_id, message=message).to_sse()
    finally:
        context.unregister_handler(progress_handler)
        if not task.done():
            task.cancel()


def _create_task_in_run(context: RunContext, coro: Awaitable[Any]) -> asyncio.Task:
    """Schedule ``coro`` with ``context`` bound, so agents resolve this run."""
    with run_scope(context):
        return asyncio.create_task(coro)
