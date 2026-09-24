"""Optional auth and rate limiting for the API.

This is a single-user desktop tool by default, so neither is switched on out
of the box. Both exist because a run costs real money at an LLM provider: a
runaway client loop is the realistic threat, not a hostile one.

- Set ``API_AUTH_TOKEN`` to require ``Authorization: Bearer <token>`` on every
  request except the health endpoints.
- ``RATE_LIMIT_PER_MINUTE`` caps how many runs one client may start per
  minute. Set it to 0 to disable.
"""

import os
import time
from collections import defaultdict, deque

from fastapi import Request, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

# Health endpoints stay reachable so a container probe needs no credentials.
UNAUTHENTICATED_PATHS = frozenset({"/", "/ping", "/docs", "/redoc", "/openapi.json"})

# Only the endpoints that spend money are metered.
RATE_LIMITED_PREFIXES = ("/hedge-fund/", "/backtest/")

DEFAULT_RATE_LIMIT_PER_MINUTE = 10


class BearerTokenMiddleware(BaseHTTPMiddleware):
    """Require a shared bearer token when API_AUTH_TOKEN is set."""

    async def dispatch(self, request: Request, call_next):
        token = os.getenv("API_AUTH_TOKEN")
        if not token or request.method == "OPTIONS" or request.url.path in UNAUTHENTICATED_PATHS:
            return await call_next(request)

        header = request.headers.get("authorization", "")
        if header.removeprefix("Bearer ").strip() != token:
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"message": "Missing or invalid bearer token", "error": "unauthorized"},
                headers={"WWW-Authenticate": "Bearer"},
            )

        return await call_next(request)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Cap how often one client may start a run.

    A fixed-size sliding window held in process memory: enough for a
    single-process desktop deployment, and deliberately not a distributed
    limiter.
    """

    def __init__(self, app, requests_per_minute: int | None = None):
        super().__init__(app)
        self._limit = requests_per_minute if requests_per_minute is not None else int(os.getenv("RATE_LIMIT_PER_MINUTE", DEFAULT_RATE_LIMIT_PER_MINUTE))
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    async def dispatch(self, request: Request, call_next):
        if self._limit <= 0 or not request.url.path.startswith(RATE_LIMITED_PREFIXES):
            return await call_next(request)

        client = request.client.host if request.client else "unknown"
        now = time.monotonic()
        window = self._hits[client]

        while window and now - window[0] > 60:
            window.popleft()

        if len(window) >= self._limit:
            retry_after = int(60 - (now - window[0])) + 1
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={"message": f"At most {self._limit} runs per minute. Try again in {retry_after}s.", "error": "rate_limited"},
                headers={"Retry-After": str(retry_after)},
            )

        window.append(now)
        return await call_next(request)
