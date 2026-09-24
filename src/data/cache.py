"""In-memory cache for financial data, with per-key coverage tracking.

Keying by ticker alone is not enough: readers need to know *which date range*
has been fetched, not just that some rows exist. Without that, a narrow early
request permanently starves every wider later request, because any single
overlapping row looks like a hit.
"""

from datetime import date, timedelta
from typing import Any, Iterable

# Stands in for "no lower bound" on requests that only specify an end date.
_MIN_DATE = "0001-01-01"


def _to_date(value: str) -> date:
    """Parse a date or ISO timestamp into a date."""
    return date.fromisoformat(value.split("T")[0])


class DateCoverage:
    """The set of date ranges already fetched, held as merged closed intervals."""

    def __init__(self) -> None:
        self._intervals: list[tuple[str, str]] = []

    def add(self, start: str, end: str) -> None:
        """Record ``[start, end]`` as fetched, merging into existing intervals."""
        if start > end:
            return
        merged: list[tuple[str, str]] = []
        for interval_start, interval_end in sorted(self._intervals + [(start, end)]):
            if not merged:
                merged.append((interval_start, interval_end))
                continue
            last_start, last_end = merged[-1]
            # Adjacent days count as contiguous, so day-by-day fetches coalesce.
            if _to_date(interval_start) <= _to_date(last_end) + timedelta(days=1):
                merged[-1] = (last_start, max(last_end, interval_end))
            else:
                merged.append((interval_start, interval_end))
        self._intervals = merged

    def covers(self, start: str, end: str) -> bool:
        """Whether every day in ``[start, end]`` has already been fetched."""
        if start > end:
            return True
        return any(interval_start <= start and end <= interval_end for interval_start, interval_end in self._intervals)

    def gaps(self, start: str, end: str) -> list[tuple[str, str]]:
        """The sub-ranges of ``[start, end]`` that have not been fetched yet."""
        if start > end:
            return []
        remaining = [(start, end)]
        for interval_start, interval_end in sorted(self._intervals):
            next_remaining: list[tuple[str, str]] = []
            for gap_start, gap_end in remaining:
                if interval_end < gap_start or interval_start > gap_end:
                    next_remaining.append((gap_start, gap_end))
                    continue
                if gap_start < interval_start:
                    next_remaining.append((gap_start, (_to_date(interval_start) - timedelta(days=1)).isoformat()))
                if interval_end < gap_end:
                    next_remaining.append(((_to_date(interval_end) + timedelta(days=1)).isoformat(), gap_end))
            remaining = next_remaining
        return remaining


class Cache:
    """In-memory cache for API responses."""

    def __init__(self) -> None:
        self._prices_cache: dict[str, list[dict[str, Any]]] = {}
        self._financial_metrics_cache: dict[str, list[dict[str, Any]]] = {}
        self._line_items_cache: dict[str, list[dict[str, Any]]] = {}
        self._insider_trades_cache: dict[str, list[dict[str, Any]]] = {}
        self._company_news_cache: dict[str, list[dict[str, Any]]] = {}
        self._coverage: dict[str, DateCoverage] = {}
        # Highest (end_date, limit) already satisfied for report-count keyed data,
        # so a genuinely short upstream history is not refetched on every call.
        self._report_coverage: dict[str, tuple[str, int]] = {}

    def _merge_data(self, existing: list[dict] | None, new_data: list[dict], key_field: str) -> list[dict]:
        """Merge existing and new data, avoiding duplicates based on a key field."""
        if not existing:
            return list(new_data)

        # Create a set of existing keys for O(1) lookup
        existing_keys = {item[key_field] for item in existing}

        # Only add items that don't exist yet
        merged = existing.copy()
        merged.extend([item for item in new_data if item[key_field] not in existing_keys])
        return merged

    def _coverage_for(self, key: str) -> DateCoverage:
        return self._coverage.setdefault(key, DateCoverage())

    # ----- date-range keyed data -------------------------------------------------

    def get_prices(self, ticker: str, start_date: str, end_date: str) -> list[dict[str, Any]] | None:
        """Cached prices for the window, or ``None`` if it is not fully covered."""
        if not self._coverage_for(f"prices:{ticker}").covers(start_date, end_date):
            return None
        return [row for row in self._prices_cache.get(ticker, []) if start_date <= row["time"] <= end_date]

    def set_prices(self, ticker: str, data: list[dict[str, Any]], start_date: str, end_date: str) -> None:
        """Store prices and record the window they were fetched for."""
        self._prices_cache[ticker] = self._merge_data(self._prices_cache.get(ticker), data, key_field="time")
        self._coverage_for(f"prices:{ticker}").add(start_date, end_date)

    def price_gaps(self, ticker: str, start_date: str, end_date: str) -> list[tuple[str, str]]:
        """Windows within the request that still need fetching."""
        return self._coverage_for(f"prices:{ticker}").gaps(start_date, end_date)

    def get_insider_trades(self, ticker: str, end_date: str, start_date: str | None = None) -> list[dict[str, Any]] | None:
        """Cached insider trades for the window, or ``None`` if not fully covered."""
        effective_start = start_date or _MIN_DATE
        if not self._coverage_for(f"insider_trades:{ticker}").covers(effective_start, end_date):
            return None
        return [row for row in self._insider_trades_cache.get(ticker, []) if effective_start <= (row.get("transaction_date") or row["filing_date"]) <= end_date]

    def set_insider_trades(self, ticker: str, data: list[dict[str, Any]], end_date: str, start_date: str | None = None) -> None:
        """Store insider trades and record the window they were fetched for."""
        self._insider_trades_cache[ticker] = self._merge_data(self._insider_trades_cache.get(ticker), data, key_field="filing_date")
        self._coverage_for(f"insider_trades:{ticker}").add(start_date or _MIN_DATE, end_date)

    def get_company_news(self, ticker: str, end_date: str, start_date: str | None = None) -> list[dict[str, Any]] | None:
        """Cached company news for the window, or ``None`` if not fully covered."""
        effective_start = start_date or _MIN_DATE
        if not self._coverage_for(f"company_news:{ticker}").covers(effective_start, end_date):
            return None
        return [row for row in self._company_news_cache.get(ticker, []) if effective_start <= row["date"] <= end_date]

    def set_company_news(self, ticker: str, data: list[dict[str, Any]], end_date: str, start_date: str | None = None) -> None:
        """Store company news and record the window it was fetched for."""
        self._company_news_cache[ticker] = self._merge_data(self._company_news_cache.get(ticker), data, key_field="date")
        self._coverage_for(f"company_news:{ticker}").add(start_date or _MIN_DATE, end_date)

    # ----- report-count keyed data -----------------------------------------------

    def _reports_are_covered(self, key: str, end_date: str, limit: int, available: int) -> bool:
        """Whether a cached report slice can satisfy a request for ``limit`` rows."""
        if available >= limit:
            return True
        # Fewer rows than asked for is only a hit if a previous request already
        # reached at least this far back and asked for at least as many.
        covered = self._report_coverage.get(key)
        return covered is not None and end_date <= covered[0] and limit <= covered[1]

    def _record_report_coverage(self, key: str, end_date: str, limit: int) -> None:
        previous_end, previous_limit = self._report_coverage.get(key, (end_date, limit))
        self._report_coverage[key] = (max(previous_end, end_date), max(previous_limit, limit))

    def get_financial_metrics(self, ticker: str, end_date: str, period: str, limit: int) -> list[dict[str, Any]] | None:
        """Cached metrics, or ``None`` when too few rows are cached to satisfy ``limit``."""
        key = f"financial_metrics:{ticker}:{period}"
        rows = [row for row in self._financial_metrics_cache.get(key, []) if row["report_period"] <= end_date]
        rows.sort(key=lambda row: row["report_period"], reverse=True)
        if not rows or not self._reports_are_covered(key, end_date, limit, len(rows)):
            return None
        return rows[:limit]

    def set_financial_metrics(self, ticker: str, data: list[dict[str, Any]], end_date: str, period: str, limit: int) -> None:
        """Store metrics and record how far back the fetch reached."""
        key = f"financial_metrics:{ticker}:{period}"
        self._financial_metrics_cache[key] = self._merge_data(self._financial_metrics_cache.get(key), data, key_field="report_period")
        self._record_report_coverage(key, end_date, limit)

    def get_line_items(self, ticker: str, line_items: Iterable[str], end_date: str, period: str, limit: int) -> list[dict[str, Any]] | None:
        """Cached line items for this exact field set, or ``None`` when not covered."""
        key = self._line_item_key(ticker, line_items, period)
        rows = [row for row in self._line_items_cache.get(key, []) if row["report_period"] <= end_date]
        rows.sort(key=lambda row: row["report_period"], reverse=True)
        if not rows or not self._reports_are_covered(key, end_date, limit, len(rows)):
            return None
        return rows[:limit]

    def set_line_items(self, ticker: str, data: list[dict[str, Any]], line_items: Iterable[str], end_date: str, period: str, limit: int) -> None:
        """Store line items and record how far back the fetch reached."""
        key = self._line_item_key(ticker, line_items, period)
        self._line_items_cache[key] = self._merge_data(self._line_items_cache.get(key), data, key_field="report_period")
        self._record_report_coverage(key, end_date, limit)

    @staticmethod
    def _line_item_key(ticker: str, line_items: Iterable[str], period: str) -> str:
        # The response only carries the fields that were asked for, so the field
        # set is part of the identity of the cached rows.
        return f"line_items:{ticker}:{period}:{','.join(sorted(line_items))}"


# Global cache instance
_cache = Cache()


def get_cache() -> Cache:
    """Get the global cache instance."""
    return _cache


def reset_cache() -> None:
    """Drop all cached data. Intended for tests and for run isolation."""
    global _cache
    _cache = Cache()
