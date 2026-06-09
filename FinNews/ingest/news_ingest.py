import logging
import time
from datetime import datetime, timezone

import requests

from config.settings import (
    ALPHA_VANTAGE_API_KEY,
    EODHD_API_KEY,
    FINNHUB_API_KEY,
    NEWSAPI_API_KEY,
    POLYGON_API_KEY,
)
from config.watchlist import TIER_1, TIER_2
from ingest.normalizer import (
    NewsItem,
    normalize_eodhd,
    normalize_finnhub_news,
    normalize_newsapi,
    normalize_polygon_news,
)

logger = logging.getLogger(__name__)

_last_fetch: dict[str, float] = {}


def _should_fetch(source: str, interval_seconds: int) -> bool:
    last = _last_fetch.get(source, 0)
    if time.time() - last < interval_seconds:
        return False
    _last_fetch[source] = time.time()
    return True


def fetch_latest() -> list[NewsItem]:
    items = []
    items.extend(_fetch_finnhub_general())
    items.extend(_fetch_finnhub_company())
    items.extend(_fetch_polygon())
    items.extend(_fetch_newsapi())
    items.extend(_fetch_eodhd())
    return items


def _api_get(url: str, params: dict | None = None, timeout: int = 10) -> dict | list | None:
    try:
        resp = requests.get(url, params=params, timeout=timeout)
        if resp.status_code == 429:
            logger.warning("Rate limited: %s", url)
            return None
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as e:
        logger.warning("API request failed: %s — %s", url, e)
        return None


# ── Finnhub ──

def _fetch_finnhub_general() -> list[NewsItem]:
    if not FINNHUB_API_KEY or not _should_fetch("finnhub_general", 120):
        return []
    data = _api_get(
        "https://finnhub.io/api/v1/news",
        params={"category": "general", "token": FINNHUB_API_KEY},
    )
    if not isinstance(data, list):
        return []
    items = []
    for raw in data[:30]:
        try:
            items.append(normalize_finnhub_news(raw))
        except Exception as e:
            logger.debug("Finnhub normalize error: %s", e)
    return items


_ticker_cycle_index = 0


def _fetch_finnhub_company() -> list[NewsItem]:
    global _ticker_cycle_index
    if not FINNHUB_API_KEY or not _should_fetch("finnhub_company", 300):
        return []

    all_tickers = TIER_1 + TIER_2
    if not all_tickers:
        return []

    ticker = all_tickers[_ticker_cycle_index % len(all_tickers)]
    _ticker_cycle_index += 1

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    data = _api_get(
        "https://finnhub.io/api/v1/company-news",
        params={
            "symbol": ticker,
            "from": today,
            "to": today,
            "token": FINNHUB_API_KEY,
        },
    )
    if not isinstance(data, list):
        return []
    items = []
    for raw in data[:10]:
        try:
            item = normalize_finnhub_news(raw)
            if ticker not in item.tickers:
                item.tickers.append(ticker)
            items.append(item)
        except Exception as e:
            logger.debug("Finnhub company normalize error: %s", e)
    return items


# ── Polygon ──

def _fetch_polygon() -> list[NewsItem]:
    if not POLYGON_API_KEY or not _should_fetch("polygon", 300):
        return []
    data = _api_get(
        "https://api.polygon.io/v2/reference/news",
        params={"limit": 50, "apiKey": POLYGON_API_KEY},
    )
    if not isinstance(data, dict):
        return []
    results = data.get("results", [])
    items = []
    for raw in results[:30]:
        try:
            items.append(normalize_polygon_news(raw))
        except Exception as e:
            logger.debug("Polygon normalize error: %s", e)
    return items


# ── NewsAPI ──

def _fetch_newsapi() -> list[NewsItem]:
    if not NEWSAPI_API_KEY or not _should_fetch("newsapi", 900):
        return []
    data = _api_get(
        "https://newsapi.org/v2/top-headlines",
        params={
            "category": "business",
            "language": "en",
            "pageSize": 50,
            "apiKey": NEWSAPI_API_KEY,
        },
    )
    if not isinstance(data, dict):
        return []
    articles = data.get("articles", [])
    items = []
    for raw in articles:
        try:
            items.append(normalize_newsapi(raw))
        except Exception as e:
            logger.debug("NewsAPI normalize error: %s", e)
    return items


# ── EODHD ──

def _fetch_eodhd() -> list[NewsItem]:
    if not EODHD_API_KEY or not _should_fetch("eodhd", 1800):
        return []
    data = _api_get(
        "https://eodhd.com/api/news",
        params={"s": "AAPL.US", "limit": 20, "api_token": EODHD_API_KEY, "fmt": "json"},
    )
    if not isinstance(data, list):
        return []
    items = []
    for raw in data:
        try:
            items.append(normalize_eodhd(raw))
        except Exception as e:
            logger.debug("EODHD normalize error: %s", e)
    return items
