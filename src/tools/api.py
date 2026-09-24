import datetime
import os
import pandas as pd
import requests

from src.data.cache import get_cache
from src.data.models import (
    CompanyNews,
    CompanyNewsResponse,
    FinancialMetrics,
    FinancialMetricsResponse,
    Price,
    PriceResponse,
    LineItem,
    LineItemResponse,
    InsiderTrade,
    InsiderTradeResponse,
    CompanyFactsResponse,
)

# Global cache instance
_cache = get_cache()


def _api_headers() -> dict[str, str]:
    """Auth headers for financialdatasets.ai. The five free tickers need none."""
    if api_key := os.environ.get("FINANCIAL_DATASETS_API_KEY"):
        return {"X-API-KEY": api_key}
    return {}


def get_prices(ticker: str, start_date: str, end_date: str) -> list[Price]:
    """Fetch price data from cache or API."""
    # Serve from cache only when the whole requested window has been fetched.
    if (cached_data := _cache.get_prices(ticker, start_date, end_date)) is not None:
        return [Price(**price) for price in cached_data]

    # Fetch only the sub-windows that are still missing, then merge.
    headers = _api_headers()
    for gap_start, gap_end in _cache.price_gaps(ticker, start_date, end_date):
        url = f"https://api.financialdatasets.ai/prices/?ticker={ticker}&interval=day&interval_multiplier=1&start_date={gap_start}&end_date={gap_end}"
        response = requests.get(url, headers=headers)
        if response.status_code != 200:
            raise Exception(f"Error fetching data: {ticker} - {response.status_code} - {response.text}")

        price_response = PriceResponse(**response.json())
        _cache.set_prices(ticker, [p.model_dump() for p in price_response.prices], gap_start, gap_end)

    cached_data = _cache.get_prices(ticker, start_date, end_date) or []
    return [Price(**price) for price in cached_data]


def get_financial_metrics(
    ticker: str,
    end_date: str,
    period: str = "ttm",
    limit: int = 10,
) -> list[FinancialMetrics]:
    """Fetch financial metrics from cache or API."""
    # Serve from cache only when it holds enough reports to satisfy `limit`.
    if (cached_data := _cache.get_financial_metrics(ticker, end_date, period, limit)) is not None:
        return [FinancialMetrics(**metric) for metric in cached_data]

    url = f"https://api.financialdatasets.ai/financial-metrics/?ticker={ticker}&report_period_lte={end_date}&limit={limit}&period={period}"
    response = requests.get(url, headers=_api_headers())
    if response.status_code != 200:
        raise Exception(f"Error fetching data: {ticker} - {response.status_code} - {response.text}")

    # Parse response with Pydantic model
    metrics_response = FinancialMetricsResponse(**response.json())
    financial_metrics = metrics_response.financial_metrics

    if not financial_metrics:
        return []

    _cache.set_financial_metrics(ticker, [m.model_dump() for m in financial_metrics], end_date, period, limit)
    return financial_metrics[:limit]


def search_line_items(
    ticker: str,
    line_items: list[str],
    end_date: str,
    period: str = "ttm",
    limit: int = 10,
) -> list[LineItem]:
    """Fetch line items from cache or API."""
    if (cached_data := _cache.get_line_items(ticker, line_items, end_date, period, limit)) is not None:
        return [LineItem(**item) for item in cached_data]

    url = "https://api.financialdatasets.ai/financials/search/line-items"

    body = {
        "tickers": [ticker],
        "line_items": line_items,
        "end_date": end_date,
        "period": period,
        "limit": limit,
    }
    response = requests.post(url, headers=_api_headers(), json=body)
    if response.status_code != 200:
        raise Exception(f"Error fetching data: {ticker} - {response.status_code} - {response.text}")
    data = response.json()
    response_model = LineItemResponse(**data)
    search_results = response_model.search_results
    if not search_results:
        return []

    _cache.set_line_items(ticker, [item.model_dump() for item in search_results], line_items, end_date, period, limit)
    return search_results[:limit]


def get_insider_trades(
    ticker: str,
    end_date: str,
    start_date: str | None = None,
    limit: int = 1000,
) -> list[InsiderTrade]:
    """Fetch insider trades from cache or API."""
    # Serve from cache only when the whole requested window has been fetched.
    if (cached_data := _cache.get_insider_trades(ticker, end_date, start_date)) is not None:
        trades = [InsiderTrade(**trade) for trade in cached_data]
        trades.sort(key=lambda trade: trade.transaction_date or trade.filing_date, reverse=True)
        return trades

    headers = _api_headers()
    all_trades = []
    current_end_date = end_date

    while True:
        url = f"https://api.financialdatasets.ai/insider-trades/?ticker={ticker}&filing_date_lte={current_end_date}"
        if start_date:
            url += f"&filing_date_gte={start_date}"
        url += f"&limit={limit}"

        response = requests.get(url, headers=headers)
        if response.status_code != 200:
            raise Exception(f"Error fetching data: {ticker} - {response.status_code} - {response.text}")

        data = response.json()
        response_model = InsiderTradeResponse(**data)
        insider_trades = response_model.insider_trades

        if not insider_trades:
            break

        all_trades.extend(insider_trades)

        # Only continue pagination if we have a start_date and got a full page
        if not start_date or len(insider_trades) < limit:
            break

        # Update end_date to the oldest filing date from current batch for next iteration
        current_end_date = min(trade.filing_date for trade in insider_trades).split("T")[0]

        # If we've reached or passed the start_date, we can stop
        if current_end_date <= start_date:
            break

    _cache.set_insider_trades(ticker, [trade.model_dump() for trade in all_trades], end_date, start_date)
    return all_trades


def get_company_news(
    ticker: str,
    end_date: str,
    start_date: str | None = None,
    limit: int = 1000,
) -> list[CompanyNews]:
    """Fetch company news from cache or API."""
    # Serve from cache only when the whole requested window has been fetched.
    if (cached_data := _cache.get_company_news(ticker, end_date, start_date)) is not None:
        news_items = [CompanyNews(**news) for news in cached_data]
        news_items.sort(key=lambda item: item.date, reverse=True)
        return news_items

    headers = _api_headers()
    all_news = []
    current_end_date = end_date

    while True:
        url = f"https://api.financialdatasets.ai/news/?ticker={ticker}&end_date={current_end_date}"
        if start_date:
            url += f"&start_date={start_date}"
        url += f"&limit={limit}"

        response = requests.get(url, headers=headers)
        if response.status_code != 200:
            raise Exception(f"Error fetching data: {ticker} - {response.status_code} - {response.text}")

        data = response.json()
        response_model = CompanyNewsResponse(**data)
        company_news = response_model.news

        if not company_news:
            break

        all_news.extend(company_news)

        # Only continue pagination if we have a start_date and got a full page
        if not start_date or len(company_news) < limit:
            break

        # Update end_date to the oldest date from current batch for next iteration
        current_end_date = min(news.date for news in company_news).split("T")[0]

        # If we've reached or passed the start_date, we can stop
        if current_end_date <= start_date:
            break

    _cache.set_company_news(ticker, [news.model_dump() for news in all_news], end_date, start_date)
    return all_news


def get_market_cap(
    ticker: str,
    end_date: str,
) -> float | None:
    """Fetch market cap from the API."""
    # Check if end_date is today
    if end_date == datetime.datetime.now().strftime("%Y-%m-%d"):
        url = f"https://api.financialdatasets.ai/company/facts/?ticker={ticker}"
        response = requests.get(url, headers=_api_headers())
        if response.status_code != 200:
            print(f"Error fetching company facts: {ticker} - {response.status_code}")
            return None

        data = response.json()
        response_model = CompanyFactsResponse(**data)
        return response_model.company_facts.market_cap

    financial_metrics = get_financial_metrics(ticker, end_date)
    if not financial_metrics:
        return None

    market_cap = financial_metrics[0].market_cap

    if not market_cap:
        return None

    return market_cap


def prices_to_df(prices: list[Price]) -> pd.DataFrame:
    """Convert prices to a DataFrame."""
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
