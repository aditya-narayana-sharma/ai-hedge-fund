import datetime
import os

import pandas as pd
import requests

from src.data.models import (
    CompanyFactsResponse,
    CompanyNews,
    CompanyNewsResponse,
    FinancialMetrics,
    FinancialMetricsResponse,
    InsiderTrade,
    InsiderTradeResponse,
    LineItem,
    LineItemResponse,
    Price,
    PriceResponse,
)
from src.utils.run_context import resolve_cache

# Financial statements are filed at most quarterly, so a metrics/line-item
# request for `limit` periods needs to reach back roughly that many quarters.
_DAYS_PER_PERIOD = 100
# Large accelerated filers have 40 days for a 10-Q and 60 for a 10-K.
# 45 days is the default stand-in for "this report is public".
_PUBLICATION_LAG_ENV = "AI_HEDGE_FUND_PUBLICATION_LAG_DAYS"
_DEFAULT_PUBLICATION_LAG_DAYS = 45


def publication_lag_days() -> int:
    """Days after ``report_period`` before a filing is treated as visible."""
    raw = os.environ.get(_PUBLICATION_LAG_ENV)
    if raw is None or not raw.strip():
        return _DEFAULT_PUBLICATION_LAG_DAYS
    try:
        return max(0, int(raw))
    except ValueError:
        return _DEFAULT_PUBLICATION_LAG_DAYS


def visible_report_end(end_date: str) -> str:
    """Decision date shifted back by the publication lag.

    A backtest day otherwise sees the fiscal period that *ended* that day,
    including numbers that were not filed yet. Restatements are still not
    modelled; this only removes the filing-delay lookahead.
    """
    lag = publication_lag_days()
    day = datetime.datetime.strptime(end_date[:10], "%Y-%m-%d").date()
    if lag <= 0:
        return day.isoformat()
    return (day - datetime.timedelta(days=lag)).isoformat()


def publication_lag_note() -> str:
    """One-line limitation printed with every backtest summary."""
    lag = publication_lag_days()
    return "Note: fundamentals are not point-in-time. A report is treated as visible " f"{lag} days after its period end (set {_PUBLICATION_LAG_ENV}). " "Restatements are not modelled."


def _oldest_day(values: list[str | None]) -> str | None:
    days = [value[:10] for value in values if value]
    return min(days) if days else None


def recorded_coverage_start(requested_start: str | None, gap_start: str, row_count: int, limit: int, oldest: str | None) -> str:
    """Coverage actually fetched, not the range the caller wished for.

    An open-ended news or insider request paginates a single page. Recording
    that page as ``1900-01-01 → end_date`` makes every later, wider request
    look fully cached. A full page therefore covers only ``[oldest row, end]``.
    A short page exhausted the history, so the whole gap is a real answer.
    """
    if requested_start is not None:
        return gap_start
    if row_count < limit or not oldest:
        return gap_start
    return oldest


def _headers() -> dict[str, str]:
    """Auth header, omitted entirely when no key is configured.

    Five tickers (AAPL, GOOGL, MSFT, NVDA, TSLA) are free without a key, and
    sending an empty X-API-KEY would break that.
    """
    api_key = os.environ.get("FINANCIAL_DATASETS_API_KEY")
    return {"X-API-KEY": api_key} if api_key else {}


def _lookback_start(end_date: str, limit: int) -> str:
    """Approximate start date covering `limit` reporting periods before `end_date`."""
    end = datetime.datetime.strptime(end_date[:10], "%Y-%m-%d").date()
    return (end - datetime.timedelta(days=_DAYS_PER_PERIOD * max(limit, 1))).isoformat()


def get_prices(ticker: str, start_date: str, end_date: str) -> list[Price]:
    """Fetch price data, requesting only the date ranges not already cached."""
    cache = resolve_cache()

    for gap_start, gap_end in cache.missing_ranges("prices", ticker, start_date, end_date):
        url = f"https://api.financialdatasets.ai/prices/?ticker={ticker}" f"&interval=day&interval_multiplier=1&start_date={gap_start}&end_date={gap_end}"
        response = requests.get(url, headers=_headers())
        if response.status_code != 200:
            raise Exception(f"Error fetching data: {ticker} - {response.status_code} - {response.text}")

        prices = PriceResponse(**response.json()).prices or []
        # Record coverage even for an empty window, so holidays and pre-IPO
        # ranges are not re-fetched on every call.
        cache.set_prices(ticker, [p.model_dump() for p in prices], gap_start, gap_end)

    rows = cache.get_prices(ticker, start_date, end_date)
    return sorted((Price(**row) for row in rows), key=lambda p: p.time)


def get_financial_metrics(
    ticker: str,
    end_date: str,
    period: str = "ttm",
    limit: int = 10,
) -> list[FinancialMetrics]:
    """Fetch financial metrics, returning the cache only when it can satisfy `limit`."""
    cache = resolve_cache()
    # ``period`` is part of the cache key: ttm and annual are different statements.
    visible_end = visible_report_end(end_date)
    start_date = _lookback_start(visible_end, limit)
    slot = cache.period_slot(ticker, period)

    cached = cache.get_financial_metrics(ticker, visible_end, period)
    needs_fetch = len(cached) < limit and not cache.covers("financial_metrics", slot, start_date, visible_end)

    if needs_fetch:
        url = f"https://api.financialdatasets.ai/financial-metrics/?ticker={ticker}" f"&report_period_lte={visible_end}&limit={limit}&period={period}"
        response = requests.get(url, headers=_headers())
        if response.status_code != 200:
            raise Exception(f"Error fetching data: {ticker} - {response.status_code} - {response.text}")

        metrics = FinancialMetricsResponse(**response.json()).financial_metrics or []
        cache.set_financial_metrics(ticker, [m.model_dump() for m in metrics], start_date, visible_end, period)
        cached = cache.get_financial_metrics(ticker, visible_end, period)

    results = sorted((FinancialMetrics(**row) for row in cached), key=lambda m: m.report_period, reverse=True)
    return results[:limit]


def search_line_items(
    ticker: str,
    line_items: list[str],
    end_date: str,
    period: str = "ttm",
    limit: int = 10,
) -> list[LineItem]:
    """Fetch line items, caching by the reporting window they cover.

    Cached rows only satisfy a request when every requested line item is
    already present on them; a narrower earlier query must not answer a wider
    later one.
    """
    cache = resolve_cache()
    visible_end = visible_report_end(end_date)
    start_date = _lookback_start(visible_end, limit)

    def _complete(rows: list[dict]) -> bool:
        return len(rows) >= limit and all(all(item in row for item in line_items) for row in rows)

    cached = cache.get_line_items(ticker, visible_end, period)

    if not _complete(cached):
        url = "https://api.financialdatasets.ai/financials/search/line-items"
        body = {
            "tickers": [ticker],
            "line_items": line_items,
            "end_date": visible_end,
            "period": period,
            "limit": limit,
        }
        response = requests.post(url, headers=_headers(), json=body)
        if response.status_code != 200:
            raise Exception(f"Error fetching data: {ticker} - {response.status_code} - {response.text}")

        search_results = LineItemResponse(**response.json()).search_results or []
        cache.set_line_items(ticker, [item.model_dump() for item in search_results], start_date, visible_end, period)
        cached = cache.get_line_items(ticker, visible_end, period)

    results = sorted((LineItem(**row) for row in cached), key=lambda item: item.report_period, reverse=True)
    return results[:limit]


def get_insider_trades(
    ticker: str,
    end_date: str,
    start_date: str | None = None,
    limit: int = 1000,
) -> list[InsiderTrade]:
    """Fetch insider trades, requesting only the uncovered date ranges."""
    cache = resolve_cache()
    # Without a start date the request is open-ended, so coverage is tracked
    # from the earliest date the API can return.
    coverage_start = start_date or "1900-01-01"

    for gap_start, gap_end in cache.missing_ranges("insider_trades", ticker, coverage_start, end_date):
        all_trades = _paginate_insider_trades(ticker, gap_start if start_date else None, gap_end, limit)
        recorded_start = recorded_coverage_start(
            start_date,
            gap_start,
            len(all_trades),
            limit,
            _oldest_day([trade.filing_date for trade in all_trades]),
        )
        cache.set_insider_trades(ticker, [t.model_dump() for t in all_trades], recorded_start, gap_end)

    rows = cache.get_insider_trades(ticker, start_date, end_date)
    trades = [InsiderTrade(**row) for row in rows]
    trades.sort(key=lambda t: t.transaction_date or t.filing_date, reverse=True)
    return trades


def _paginate_insider_trades(
    ticker: str,
    start_date: str | None,
    end_date: str,
    limit: int,
) -> list[InsiderTrade]:
    """Walk the insider-trades endpoint backwards until the range is exhausted."""
    all_trades: list[InsiderTrade] = []
    current_end_date = end_date

    while True:
        url = f"https://api.financialdatasets.ai/insider-trades/?ticker={ticker}&filing_date_lte={current_end_date}"
        if start_date:
            url += f"&filing_date_gte={start_date}"
        url += f"&limit={limit}"

        response = requests.get(url, headers=_headers())
        if response.status_code != 200:
            raise Exception(f"Error fetching data: {ticker} - {response.status_code} - {response.text}")

        insider_trades = InsiderTradeResponse(**response.json()).insider_trades
        if not insider_trades:
            break

        all_trades.extend(insider_trades)

        # Only continue pagination if we have a start_date and got a full page
        if not start_date or len(insider_trades) < limit:
            break

        current_end_date = min(trade.filing_date for trade in insider_trades).split("T")[0]
        if current_end_date <= start_date:
            break

    return all_trades


def get_company_news(
    ticker: str,
    end_date: str,
    start_date: str | None = None,
    limit: int = 1000,
) -> list[CompanyNews]:
    """Fetch company news, requesting only the uncovered date ranges."""
    cache = resolve_cache()
    coverage_start = start_date or "1900-01-01"

    for gap_start, gap_end in cache.missing_ranges("company_news", ticker, coverage_start, end_date):
        all_news = _paginate_company_news(ticker, gap_start if start_date else None, gap_end, limit)
        recorded_start = recorded_coverage_start(
            start_date,
            gap_start,
            len(all_news),
            limit,
            _oldest_day([item.date for item in all_news]),
        )
        cache.set_company_news(ticker, [n.model_dump() for n in all_news], recorded_start, gap_end)

    rows = cache.get_company_news(ticker, start_date, end_date)
    news = [CompanyNews(**row) for row in rows]
    news.sort(key=lambda n: n.date, reverse=True)
    return news


def _paginate_company_news(
    ticker: str,
    start_date: str | None,
    end_date: str,
    limit: int,
) -> list[CompanyNews]:
    """Walk the news endpoint backwards until the range is exhausted."""
    all_news: list[CompanyNews] = []
    current_end_date = end_date

    while True:
        url = f"https://api.financialdatasets.ai/news/?ticker={ticker}&end_date={current_end_date}"
        if start_date:
            url += f"&start_date={start_date}"
        url += f"&limit={limit}"

        response = requests.get(url, headers=_headers())
        if response.status_code != 200:
            raise Exception(f"Error fetching data: {ticker} - {response.status_code} - {response.text}")

        company_news = CompanyNewsResponse(**response.json()).news
        if not company_news:
            break

        all_news.extend(company_news)

        if not start_date or len(company_news) < limit:
            break

        current_end_date = min(news.date for news in company_news).split("T")[0]
        if current_end_date <= start_date:
            break

    return all_news


def get_market_cap(
    ticker: str,
    end_date: str,
) -> float | None:
    """Fetch market cap from the API."""
    # Check if end_date is today
    if end_date == datetime.datetime.now().strftime("%Y-%m-%d"):
        # Get the market cap from company facts API
        url = f"https://api.financialdatasets.ai/company/facts/?ticker={ticker}"
        response = requests.get(url, headers=_headers())
        if response.status_code != 200:
            print(f"Error fetching company facts: {ticker} - {response.status_code}")
            return None

        return CompanyFactsResponse(**response.json()).company_facts.market_cap

    financial_metrics = get_financial_metrics(ticker, end_date)
    if not financial_metrics:
        return None

    return financial_metrics[0].market_cap or None


def prices_to_df(prices: list[Price]) -> pd.DataFrame:
    """Convert prices to a DataFrame, empty-safe so callers can test `.empty`."""
    if not prices:
        return pd.DataFrame(columns=["time", "open", "close", "high", "low", "volume"])

    df = pd.DataFrame([p.model_dump() for p in prices])
    df["Date"] = pd.to_datetime(df["time"])
    df.set_index("Date", inplace=True)
    numeric_cols = ["open", "close", "high", "low", "volume"]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df.sort_index(inplace=True)
    return df


# Update the get_price_data function to use the new functions
def get_price_data(ticker: str, start_date: str, end_date: str) -> pd.DataFrame:
    prices = get_prices(ticker, start_date, end_date)
    return prices_to_df(prices)
