"""A narrow request must not starve a later, wider one."""

from src.data.cache import Cache, DateCoverage


def _price(day: str) -> dict:
    return {"time": day, "open": 1.0, "close": 1.0, "high": 1.0, "low": 1.0, "volume": 1}


class TestDateCoverage:
    def test_a_window_covers_itself(self):
        coverage = DateCoverage()
        coverage.add("2024-01-01", "2024-01-31")

        assert coverage.covers("2024-01-01", "2024-01-31")
        assert coverage.covers("2024-01-10", "2024-01-20")

    def test_a_wider_window_is_not_covered_by_a_narrower_one(self):
        coverage = DateCoverage()
        coverage.add("2024-01-01", "2024-01-05")

        assert not coverage.covers("2024-01-01", "2024-06-30")

    def test_gaps_exclude_what_has_already_been_fetched(self):
        coverage = DateCoverage()
        coverage.add("2024-01-01", "2024-01-05")

        assert coverage.gaps("2024-01-01", "2024-01-10") == [("2024-01-06", "2024-01-10")]

    def test_gaps_can_straddle_a_covered_window(self):
        coverage = DateCoverage()
        coverage.add("2024-02-01", "2024-02-10")

        assert coverage.gaps("2024-01-01", "2024-03-01") == [
            ("2024-01-01", "2024-01-31"),
            ("2024-02-11", "2024-03-01"),
        ]

    def test_adjacent_windows_coalesce(self):
        coverage = DateCoverage()
        coverage.add("2024-01-01", "2024-01-05")
        coverage.add("2024-01-06", "2024-01-10")

        assert coverage.covers("2024-01-01", "2024-01-10")
        assert coverage.gaps("2024-01-01", "2024-01-10") == []


class TestPriceCache:
    def test_a_narrow_fetch_does_not_satisfy_a_wider_request(self):
        cache = Cache()
        cache.set_prices("AAPL", [_price("2024-01-02")], "2024-01-01", "2024-01-05")

        assert cache.get_prices("AAPL", "2024-01-01", "2024-01-05") is not None
        assert cache.get_prices("AAPL", "2024-01-01", "2024-06-30") is None

    def test_filling_the_gap_completes_the_wider_request(self):
        cache = Cache()
        cache.set_prices("AAPL", [_price("2024-01-02")], "2024-01-01", "2024-01-05")
        cache.set_prices("AAPL", [_price("2024-03-04")], "2024-01-06", "2024-06-30")

        rows = cache.get_prices("AAPL", "2024-01-01", "2024-06-30")

        assert rows is not None
        assert {row["time"] for row in rows} == {"2024-01-02", "2024-03-04"}

    def test_an_empty_window_is_still_recorded_as_fetched(self):
        cache = Cache()
        cache.set_prices("AAPL", [], "2024-01-01", "2024-01-05")

        assert cache.get_prices("AAPL", "2024-01-01", "2024-01-05") == []

    def test_gaps_are_reported_for_the_uncovered_part_only(self):
        cache = Cache()
        cache.set_prices("AAPL", [_price("2024-01-02")], "2024-01-01", "2024-01-05")

        assert cache.price_gaps("AAPL", "2024-01-01", "2024-01-10") == [("2024-01-06", "2024-01-10")]


class TestFinancialMetricsCache:
    def _metric(self, period: str) -> dict:
        return {"ticker": "AAPL", "report_period": period, "period": "ttm", "currency": "USD"}

    def test_fewer_cached_rows_than_requested_is_a_miss(self):
        cache = Cache()
        cache.set_financial_metrics("AAPL", [self._metric("2023-12-31")], "2024-01-01", "ttm", 1)

        assert cache.get_financial_metrics("AAPL", "2024-01-01", "ttm", 1) is not None
        assert cache.get_financial_metrics("AAPL", "2024-01-01", "ttm", 10) is None

    def test_a_short_upstream_history_is_not_refetched_forever(self):
        cache = Cache()
        cache.set_financial_metrics("AAPL", [self._metric("2023-12-31")], "2024-01-01", "ttm", 10)

        # Upstream only had one report; a repeat of the same request is a hit.
        assert cache.get_financial_metrics("AAPL", "2024-01-01", "ttm", 10) is not None

    def test_periods_are_cached_separately(self):
        cache = Cache()
        cache.set_financial_metrics("AAPL", [self._metric("2023-12-31")], "2024-01-01", "ttm", 1)

        assert cache.get_financial_metrics("AAPL", "2024-01-01", "annual", 1) is None


class TestLineItemCache:
    def _item(self, period: str) -> dict:
        return {"ticker": "AAPL", "report_period": period, "period": "ttm", "currency": "USD"}

    def test_line_items_are_cached_per_requested_field_set(self):
        cache = Cache()
        cache.set_line_items("AAPL", [self._item("2023-12-31")], ["revenue"], "2024-01-01", "ttm", 1)

        assert cache.get_line_items("AAPL", ["revenue"], "2024-01-01", "ttm", 1) is not None
        assert cache.get_line_items("AAPL", ["revenue", "net_income"], "2024-01-01", "ttm", 1) is None

    def test_field_order_does_not_change_the_key(self):
        cache = Cache()
        cache.set_line_items("AAPL", [self._item("2023-12-31")], ["revenue", "net_income"], "2024-01-01", "ttm", 1)

        assert cache.get_line_items("AAPL", ["net_income", "revenue"], "2024-01-01", "ttm", 1) is not None
