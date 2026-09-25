"""Coverage tracking in the API cache.

The regression under test: a narrow early request used to permanently starve
every wider later request, because any single overlapping row short-circuited
the fetch.
"""

from src.data.cache import Cache, covers, merge_ranges, missing_ranges


def _price(day: str, close: float = 1.0) -> dict:
    return {"time": day, "open": close, "close": close, "high": close, "low": close, "volume": 1}


class TestRangeArithmetic:
    def test_merges_overlapping_ranges(self):
        assert merge_ranges([("2024-01-01", "2024-01-10"), ("2024-01-05", "2024-01-20")]) == [("2024-01-01", "2024-01-20")]

    def test_merges_day_adjacent_ranges(self):
        assert merge_ranges([("2024-01-01", "2024-01-10"), ("2024-01-11", "2024-01-20")]) == [("2024-01-01", "2024-01-20")]

    def test_keeps_disjoint_ranges_apart(self):
        assert merge_ranges([("2024-01-01", "2024-01-10"), ("2024-02-01", "2024-02-10")]) == [
            ("2024-01-01", "2024-01-10"),
            ("2024-02-01", "2024-02-10"),
        ]

    def test_everything_is_missing_when_nothing_is_covered(self):
        assert missing_ranges([], "2024-01-01", "2024-06-30") == [("2024-01-01", "2024-06-30")]

    def test_reports_the_tail_gap_after_a_narrow_range(self):
        covered = [("2024-01-01", "2024-01-05")]
        assert missing_ranges(covered, "2024-01-01", "2024-06-30") == [("2024-01-06", "2024-06-30")]

    def test_reports_the_head_gap_before_a_covered_range(self):
        covered = [("2024-03-01", "2024-06-30")]
        assert missing_ranges(covered, "2024-01-01", "2024-06-30") == [("2024-01-01", "2024-02-29")]

    def test_reports_an_interior_gap(self):
        covered = [("2024-01-01", "2024-01-31"), ("2024-03-01", "2024-03-31")]
        assert missing_ranges(covered, "2024-01-01", "2024-03-31") == [("2024-02-01", "2024-02-29")]

    def test_full_coverage_leaves_no_gap(self):
        assert covers([("2024-01-01", "2024-12-31")], "2024-03-01", "2024-04-01")

    def test_partial_coverage_is_not_coverage(self):
        assert not covers([("2024-01-01", "2024-01-05")], "2024-01-01", "2024-06-30")


class TestCacheCoverage:
    def test_narrow_request_does_not_satisfy_a_wider_one(self):
        """The original bug: five January days answering a six-month query."""
        cache = Cache()
        cache.set_prices(
            "AAPL",
            [_price(f"2024-01-0{d}") for d in range(1, 6)],
            "2024-01-01",
            "2024-01-05",
        )

        assert cache.covers("prices", "AAPL", "2024-01-01", "2024-01-05")
        assert not cache.covers("prices", "AAPL", "2024-01-01", "2024-06-30")
        assert cache.missing_ranges("prices", "AAPL", "2024-01-01", "2024-06-30") == [("2024-01-06", "2024-06-30")]

    def test_backfilling_the_gap_completes_coverage(self):
        cache = Cache()
        cache.set_prices("AAPL", [_price("2024-01-03")], "2024-01-01", "2024-01-05")
        cache.set_prices("AAPL", [_price("2024-03-04")], "2024-01-06", "2024-06-30")

        assert cache.covers("prices", "AAPL", "2024-01-01", "2024-06-30")
        assert cache.missing_ranges("prices", "AAPL", "2024-01-01", "2024-06-30") == []
        assert len(cache.get_prices("AAPL", "2024-01-01", "2024-06-30")) == 2

    def test_empty_window_still_records_coverage(self):
        """A holiday or pre-IPO range must not be re-fetched forever."""
        cache = Cache()
        cache.set_prices("AAPL", [], "2024-01-01", "2024-01-02")

        assert cache.covers("prices", "AAPL", "2024-01-01", "2024-01-02")

    def test_rows_are_filtered_to_the_requested_window(self):
        cache = Cache()
        cache.set_prices(
            "AAPL",
            [_price("2024-01-01"), _price("2024-02-01"), _price("2024-03-01")],
            "2024-01-01",
            "2024-03-01",
        )

        rows = cache.get_prices("AAPL", "2024-01-15", "2024-02-15")
        assert [row["time"] for row in rows] == ["2024-02-01"]

    def test_timestamps_compare_by_calendar_day(self):
        cache = Cache()
        cache.store(
            "company_news",
            "AAPL",
            [{"date": "2024-02-01T13:45:00Z", "title": "x"}],
            "2024-01-01",
            "2024-02-01",
        )

        assert len(cache.get_company_news("AAPL", "2024-02-01", "2024-02-01")) == 1

    def test_duplicate_rows_are_not_stored_twice(self):
        cache = Cache()
        cache.set_prices("AAPL", [_price("2024-01-01")], "2024-01-01", "2024-01-01")
        cache.set_prices("AAPL", [_price("2024-01-01")], "2024-01-01", "2024-01-02")

        assert len(cache.get_prices("AAPL", "2024-01-01", "2024-01-02")) == 1

    def test_tickers_do_not_share_coverage(self):
        cache = Cache()
        cache.set_prices("AAPL", [_price("2024-01-01")], "2024-01-01", "2024-01-31")

        assert cache.covers("prices", "AAPL", "2024-01-01", "2024-01-31")
        assert not cache.covers("prices", "MSFT", "2024-01-01", "2024-01-31")

    def test_expired_entries_are_dropped(self):
        cache = Cache(ttl_seconds=-1)  # already expired on read
        cache.set_prices("AAPL", [_price("2024-01-01")], "2024-01-01", "2024-01-31")

        assert not cache.covers("prices", "AAPL", "2024-01-01", "2024-01-31")

    def test_clear_drops_rows_and_coverage(self):
        cache = Cache()
        cache.set_prices("AAPL", [_price("2024-01-01")], "2024-01-01", "2024-01-31")
        cache.clear()

        assert cache.get_prices("AAPL", "2024-01-01", "2024-01-31") == []
        assert not cache.covers("prices", "AAPL", "2024-01-01", "2024-01-31")

    def test_persisted_cache_round_trips(self, tmp_path):
        first = Cache(persist_dir=str(tmp_path))
        first.set_prices("AAPL", [_price("2024-01-02")], "2024-01-01", "2024-01-31")

        second = Cache(persist_dir=str(tmp_path))
        assert second.covers("prices", "AAPL", "2024-01-01", "2024-01-31")
        assert len(second.get_prices("AAPL", "2024-01-01", "2024-01-31")) == 1
