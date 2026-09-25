"""In-memory cache for API responses, with explicit coverage tracking.

The previous implementation stored one flat list per ticker and short-circuited
the network fetch whenever *any* cached row fell inside the requested window.
A cache holding five January days therefore satisfied a six-month request with
five rows, silently, and never backfilled the gap. Agents then reasoned over a
truncated window and emitted fully confident signals.

Each dated collection now records which date ranges have actually been fetched.
Readers ask :meth:`Cache.missing_ranges` what is still uncovered, fetch only
that, and serve from the cache once coverage is complete.
"""

import atexit
import json
import os
import threading
import time
from datetime import date, timedelta
from pathlib import Path
from typing import Any

try:
    import fcntl
except ImportError:  # Windows has no fcntl; the in-process lock still applies.
    fcntl = None  # type: ignore[assignment]

# Optional wall-clock expiry for cached rows, in seconds. Unset means no expiry,
# which is the right default for historical market data.
_TTL_ENV_VAR = "AI_HEDGE_FUND_CACHE_TTL"
# Optional directory for cross-process persistence. Unset keeps the cache in memory.
_DIR_ENV_VAR = "AI_HEDGE_FUND_CACHE_DIR"

DateRange = tuple[str, str]


def _to_date(value: str) -> date:
    """Parse the leading YYYY-MM-DD of a date or timestamp string."""
    return date.fromisoformat(value[:10])


def _day_key(value: Any) -> str:
    """Normalise a row's date field to YYYY-MM-DD for range comparisons."""
    return str(value)[:10]


def merge_ranges(ranges: list[DateRange]) -> list[DateRange]:
    """Collapse overlapping and day-adjacent ranges into a minimal list."""
    if not ranges:
        return []

    ordered = sorted(ranges, key=lambda r: (r[0], r[1]))
    merged: list[DateRange] = [ordered[0]]

    for start, end in ordered[1:]:
        last_start, last_end = merged[-1]
        # Touching ranges (end == next start - 1 day) count as contiguous.
        if _to_date(start) <= _to_date(last_end) + timedelta(days=1):
            if _to_date(end) > _to_date(last_end):
                merged[-1] = (last_start, end)
        else:
            merged.append((start, end))

    return merged


def missing_ranges(covered: list[DateRange], start: str, end: str) -> list[DateRange]:
    """Return the sub-ranges of ``[start, end]`` not present in ``covered``."""
    if _to_date(start) > _to_date(end):
        return []

    gaps: list[DateRange] = []
    cursor = _to_date(start)
    end_date = _to_date(end)

    for range_start, range_end in merge_ranges(covered):
        range_start_date, range_end_date = _to_date(range_start), _to_date(range_end)
        if range_end_date < cursor:
            continue
        if range_start_date > end_date:
            break
        if range_start_date > cursor:
            gaps.append((cursor.isoformat(), (range_start_date - timedelta(days=1)).isoformat()))
        cursor = max(cursor, range_end_date + timedelta(days=1))
        if cursor > end_date:
            return gaps

    if cursor <= end_date:
        gaps.append((cursor.isoformat(), end_date.isoformat()))

    return gaps


def covers(covered: list[DateRange], start: str, end: str) -> bool:
    """True when ``[start, end]`` is fully contained in ``covered``."""
    return not missing_ranges(covered, start, end)


class _Collection:
    """Rows for one ticker plus the ranges that have actually been fetched."""

    def __init__(self, key_field: str) -> None:
        self.key_field = key_field
        self.rows: list[dict[str, Any]] = []
        self.covered: list[DateRange] = []
        self.fetched_at: float = time.time()

    def merge(self, new_rows: list[dict[str, Any]]) -> None:
        """Append rows whose key is not already present."""
        existing_keys = {row[self.key_field] for row in self.rows}
        self.rows.extend(row for row in new_rows if row[self.key_field] not in existing_keys)
        self.fetched_at = time.time()

    def add_coverage(self, start: str, end: str) -> None:
        self.covered = merge_ranges([*self.covered, (start, end)])

    def is_expired(self, ttl_seconds: float | None) -> bool:
        return ttl_seconds is not None and (time.time() - self.fetched_at) > ttl_seconds

    def to_json(self) -> dict[str, Any]:
        return {
            "key_field": self.key_field,
            "rows": self.rows,
            "covered": [list(r) for r in self.covered],
            "fetched_at": self.fetched_at,
        }

    @classmethod
    def from_json(cls, payload: dict[str, Any]) -> "_Collection":
        collection = cls(payload["key_field"])
        collection.rows = payload.get("rows", [])
        collection.covered = [tuple(r) for r in payload.get("covered", [])]
        collection.fetched_at = payload.get("fetched_at", time.time())
        return collection


# Every dated collection and the row field that uniquely identifies its rows.
_KEY_FIELDS = {
    "prices": "time",
    "financial_metrics": "report_period",
    "line_items": "report_period",
    "insider_trades": "filing_date",
    "company_news": "date",
}


class Cache:
    """Per-ticker cache of API responses with date-range coverage tracking."""

    def __init__(self, ttl_seconds: float | None = None, persist_dir: str | None = None, debounce_seconds: float = 0.0) -> None:
        self.ttl_seconds = ttl_seconds
        self.persist_dir = persist_dir
        self.debounce_seconds = debounce_seconds
        self._dirty = False
        self._last_save = 0.0
        self._write_lock = threading.Lock()
        # collection name -> ticker -> rows and coverage
        self._data: dict[str, dict[str, _Collection]] = {name: {} for name in _KEY_FIELDS}
        if self.persist_dir:
            self.load()

    # ---- generic access -------------------------------------------------

    def _collection(self, name: str, ticker: str) -> _Collection:
        bucket = self._data[name]
        existing = bucket.get(ticker)
        if existing is None or existing.is_expired(self.ttl_seconds):
            existing = _Collection(_KEY_FIELDS[name])
            bucket[ticker] = existing
        return existing

    def get_rows(self, name: str, ticker: str, start_date: str | None, end_date: str) -> list[dict[str, Any]]:
        """Return cached rows falling inside ``[start_date, end_date]``."""
        collection = self._collection(name, ticker)
        return [row for row in collection.rows if (start_date is None or _day_key(row[collection.key_field]) >= start_date[:10]) and _day_key(row[collection.key_field]) <= end_date[:10]]

    def missing_ranges(self, name: str, ticker: str, start_date: str, end_date: str) -> list[DateRange]:
        """Return the parts of ``[start_date, end_date]`` still to be fetched."""
        return missing_ranges(self._collection(name, ticker).covered, start_date, end_date)

    def covers(self, name: str, ticker: str, start_date: str, end_date: str) -> bool:
        """True when the requested window has already been fetched in full."""
        return not self.missing_ranges(name, ticker, start_date, end_date)

    def store(
        self,
        name: str,
        ticker: str,
        rows: list[dict[str, Any]],
        start_date: str,
        end_date: str,
    ) -> None:
        """Merge ``rows`` and record ``[start_date, end_date]`` as fetched.

        Coverage is recorded even when the API returned nothing, because an
        empty window is a real answer: without this, a market holiday or a
        pre-IPO range would be re-fetched on every single call.
        """
        collection = self._collection(name, ticker)
        collection.merge(rows)
        collection.add_coverage(start_date, end_date)
        self._dirty = True
        self.save()

    # ---- per-collection convenience -------------------------------------

    def get_prices(self, ticker: str, start_date: str, end_date: str) -> list[dict[str, Any]]:
        return self.get_rows("prices", ticker, start_date, end_date)

    def set_prices(self, ticker: str, data: list[dict[str, Any]], start_date: str, end_date: str) -> None:
        self.store("prices", ticker, data, start_date, end_date)

    @staticmethod
    def period_slot(ticker: str, period: str) -> str:
        """Cache identity for one statement frequency.

        ``ttm`` and ``annual`` share a ``report_period`` and must not share a
        slot, or the first fetch answers every later request.
        """
        return f"{ticker}::{period}"

    def get_financial_metrics(self, ticker: str, end_date: str, period: str = "ttm") -> list[dict[str, Any]]:
        return self.get_rows("financial_metrics", self.period_slot(ticker, period), None, end_date)

    def set_financial_metrics(self, ticker: str, data: list[dict[str, Any]], start_date: str, end_date: str, period: str = "ttm") -> None:
        self.store("financial_metrics", self.period_slot(ticker, period), data, start_date, end_date)

    def get_line_items(self, ticker: str, end_date: str, period: str = "ttm") -> list[dict[str, Any]]:
        return self.get_rows("line_items", self.period_slot(ticker, period), None, end_date)

    def set_line_items(self, ticker: str, data: list[dict[str, Any]], start_date: str, end_date: str, period: str = "ttm") -> None:
        self.store("line_items", self.period_slot(ticker, period), data, start_date, end_date)

    def get_insider_trades(self, ticker: str, start_date: str | None, end_date: str) -> list[dict[str, Any]]:
        return self.get_rows("insider_trades", ticker, start_date, end_date)

    def set_insider_trades(self, ticker: str, data: list[dict[str, Any]], start_date: str, end_date: str) -> None:
        self.store("insider_trades", ticker, data, start_date, end_date)

    def get_company_news(self, ticker: str, start_date: str | None, end_date: str) -> list[dict[str, Any]]:
        return self.get_rows("company_news", ticker, start_date, end_date)

    def set_company_news(self, ticker: str, data: list[dict[str, Any]], start_date: str, end_date: str) -> None:
        self.store("company_news", ticker, data, start_date, end_date)

    # ---- optional persistence -------------------------------------------

    def _persist_path(self) -> Path | None:
        if not self.persist_dir:
            return None
        return Path(self.persist_dir) / "api-cache.json"

    def save(self, force: bool = False) -> None:
        """Write the cache atomically when a persistence directory is configured.

        Rapid ``store`` calls coalesce until ``debounce_seconds`` has elapsed.
        ``flush`` (and process exit, for the global cache) force the write.
        """
        path = self._persist_path()
        if path is None or not self._dirty:
            return
        now = time.monotonic()
        if not force and self.debounce_seconds > 0 and (now - self._last_save) < self.debounce_seconds:
            return
        self._write_atomic(path)

    def flush(self) -> None:
        """Write any coalesced changes immediately."""
        self.save(force=True)

    def _write_atomic(self, path: Path) -> None:
        """Lock, merge anything another process wrote, then replace the file."""
        path.parent.mkdir(parents=True, exist_ok=True)
        lock_path = path.with_name(path.name + ".lock")
        with self._write_lock:
            with open(lock_path, "a+", encoding="utf-8") as lock_file:
                if fcntl is not None:
                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
                try:
                    self._merge_from_disk(path)
                    payload = {name: {ticker: collection.to_json() for ticker, collection in bucket.items()} for name, bucket in self._data.items()}
                    temporary = path.with_name(path.name + ".tmp")
                    temporary.write_text(json.dumps(payload), encoding="utf-8")
                    os.replace(temporary, path)
                    self._dirty = False
                    self._last_save = time.monotonic()
                finally:
                    if fcntl is not None:
                        fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)

    def _merge_from_disk(self, path: Path) -> None:
        """Fold another process's rows into memory before we overwrite the file."""
        if not path.exists():
            return
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            print(f"Warning: cache file {path} could not be read ({exc}); keeping the in-memory copy.")
            return
        if not isinstance(payload, dict):
            print(f"Warning: cache file {path} is not an object; keeping the in-memory copy.")
            return
        for name, bucket in payload.items():
            if name not in self._data or not isinstance(bucket, dict):
                continue
            for ticker, raw in bucket.items():
                other = _Collection.from_json(raw)
                current = self._data[name].get(ticker)
                if current is None:
                    self._data[name][ticker] = other
                    continue
                current.merge(other.rows)
                for start, end in other.covered:
                    current.add_coverage(start, end)

    def load(self) -> None:
        """Restore a previously persisted cache. A torn file is a warning, not silence."""
        path = self._persist_path()
        if path is None or not path.exists():
            return
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            print(f"Warning: cache file {path} could not be read ({exc}); starting empty.")
            return
        if not isinstance(payload, dict):
            print(f"Warning: cache file {path} is not an object; starting empty.")
            return
        for name, bucket in payload.items():
            if name not in self._data or not isinstance(bucket, dict):
                continue
            self._data[name] = {ticker: _Collection.from_json(raw) for ticker, raw in bucket.items()}

    def clear(self) -> None:
        """Drop every cached row and all coverage, including the persisted copy."""
        self._data = {name: {} for name in _KEY_FIELDS}
        self._dirty = False
        path = self._persist_path()
        if path is not None and path.exists():
            path.unlink()


def _ttl_from_env() -> float | None:
    raw = os.environ.get(_TTL_ENV_VAR)
    if not raw:
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def _debounce_from_env(persist_dir: str | None) -> float:
    """Coalesce disk writes only when persistence is actually on."""
    if not persist_dir:
        return 0.0
    raw = os.environ.get("AI_HEDGE_FUND_CACHE_DEBOUNCE", "0.5")
    try:
        return max(0.0, float(raw))
    except ValueError:
        return 0.5


# Global cache instance, used by the CLI. The web backend creates one per run.
_persist_dir = os.environ.get(_DIR_ENV_VAR)
_cache = Cache(ttl_seconds=_ttl_from_env(), persist_dir=_persist_dir, debounce_seconds=_debounce_from_env(_persist_dir))
atexit.register(_cache.flush)


def get_cache() -> Cache:
    """Get the global cache instance."""
    return _cache
