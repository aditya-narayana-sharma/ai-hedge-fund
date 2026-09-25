"""Cross-cutting request dependencies: authentication and rate limiting.

The backend previously had no middleware beyond CORS, which is fine while it
only ever listens on localhost but not once it is exposed. Both controls are
opt-in through environment variables so the default developer experience —
clone, run, open the canvas — is unchanged.
"""

import os
import time
from collections import defaultdict, deque
from typing import Deque, Dict

from fastapi import Header, HTTPException, Request, status

# Shared secret required in X-API-Key. Unset means the API is open.
API_KEY_ENV_VAR = "AI_HEDGE_FUND_API_KEY"
# Requests allowed per client per window. Unset or 0 disables rate limiting.
RATE_LIMIT_ENV_VAR = "AI_HEDGE_FUND_RATE_LIMIT"
RATE_LIMIT_WINDOW_ENV_VAR = "AI_HEDGE_FUND_RATE_LIMIT_WINDOW"
DEFAULT_WINDOW_SECONDS = 60.0

# client key -> timestamps of recent requests. In-process only: one uvicorn
# worker is the deployment this backend actually has, and a shared store would
# mean adding Redis for a limit that exists to stop accidental self-DoS.
_request_log: Dict[str, Deque[float]] = defaultdict(deque)


def _configured_limit() -> int:
    try:
        return int(os.environ.get(RATE_LIMIT_ENV_VAR, "0"))
    except ValueError:
        return 0


def _configured_window() -> float:
    try:
        return float(os.environ.get(RATE_LIMIT_WINDOW_ENV_VAR, DEFAULT_WINDOW_SECONDS))
    except ValueError:
        return DEFAULT_WINDOW_SECONDS


async def require_api_key(x_api_key: str | None = Header(default=None)) -> None:
    """Reject the request when an API key is configured and does not match."""
    expected = os.environ.get(API_KEY_ENV_VAR)
    if not expected:
        return

    if x_api_key != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing X-API-Key header.",
            headers={"WWW-Authenticate": "ApiKey"},
        )


async def enforce_rate_limit(request: Request, x_api_key: str | None = Header(default=None)) -> None:
    """Allow at most N requests per window, keyed by API key or client address."""
    limit = _configured_limit()
    if limit <= 0:
        return

    window = _configured_window()
    now = time.monotonic()
    # The header is a bucket id only after it has been checked against the
    # configured secret. Otherwise any caller rotates X-API-Key and gets a
    # fresh bucket, and the dict grows without bound.
    expected = os.environ.get(API_KEY_ENV_VAR)
    if expected and x_api_key == expected:
        client_key = f"key:{x_api_key}"
    else:
        client_key = request.client.host if request.client else "unknown"

    _evict_stale_buckets(now, window)
    timestamps = _request_log[client_key]

    if len(timestamps) >= limit:
        retry_after = max(1, int(window - (now - timestamps[0])))
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit of {limit} requests per {int(window)}s exceeded.",
            headers={"Retry-After": str(retry_after)},
        )

    timestamps.append(now)


def _evict_stale_buckets(now: float, window: float) -> None:
    """Drop timestamps outside the window, and drop buckets that are then empty."""
    empty = []
    for key, timestamps in _request_log.items():
        while timestamps and now - timestamps[0] > window:
            timestamps.popleft()
        if not timestamps:
            empty.append(key)
    for key in empty:
        del _request_log[key]


def reset_rate_limits() -> None:
    """Drop all rate-limit bookkeeping. Used by tests."""
    _request_log.clear()
