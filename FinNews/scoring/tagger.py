import re

from config.watchlist import ALL_TICKERS

_TICKER_RE = re.compile(r"\$([A-Z]{1,5})\b")
_BARE_TICKER_RE = re.compile(r"\b([A-Z]{2,5})\b")

TOPIC_KEYWORDS = {
    "fed": ["federal reserve", "fomc", "fed ", "powell", "fed chair", "monetary policy"],
    "rates": ["rate cut", "rate hike", "basis points", "bps", "interest rate", "fed funds"],
    "inflation": ["cpi", "pce", "inflation", "consumer price", "producer price", "ppi"],
    "employment": ["nonfarm payrolls", "nfp", "unemployment", "jobless claims", "jobs report"],
    "gdp": ["gdp", "gross domestic product", "economic growth"],
    "earnings": ["earnings", "eps", "revenue", "guidance", "profit", "quarterly results",
                  "beats", "misses", "guides lower", "guides higher"],
    "geopolitical": ["tariff", "sanctions", "embargo", "war", "invasion", "ceasefire",
                     "trade war", "export controls"],
    "energy": ["opec", "oil production", "crude oil", "natural gas", "oil price"],
    "crypto": ["bitcoin", "btc", "ethereum", "eth", "crypto"],
    "market_structure": ["circuit breaker", "trading halt", "margin call", "liquidation",
                         "flash crash", "short squeeze", "bankruptcy", "default"],
}


def tag_item(item) -> None:
    text = (item.headline + " " + (item.body or "")).lower()

    if not item.tickers:
        tickers = set()
        for match in _TICKER_RE.finditer(item.headline + " " + (item.body or "")):
            tickers.add(match.group(1))
        for match in _BARE_TICKER_RE.finditer(item.headline + " " + (item.body or "")):
            candidate = match.group(1)
            if candidate in ALL_TICKERS:
                tickers.add(candidate)
        item.tickers = list(tickers)

    if not item.topics:
        topics = set()
        for topic, keywords in TOPIC_KEYWORDS.items():
            for kw in keywords:
                if kw in text:
                    topics.add(topic)
                    break
        item.topics = list(topics)

    if not item.category:
        if item.topics:
            priority = ["market_structure", "fed", "rates", "inflation",
                        "employment", "gdp", "geopolitical", "earnings",
                        "energy", "crypto"]
            for p in priority:
                if p in item.topics:
                    if p in ("fed", "rates", "inflation", "employment", "gdp"):
                        item.category = "macro"
                    elif p == "earnings":
                        item.category = "earnings"
                    elif p == "geopolitical":
                        item.category = "geopolitical"
                    elif p == "market_structure":
                        item.category = "macro"
                    elif p == "energy":
                        item.category = "sector"
                    elif p == "crypto":
                        item.category = "crypto"
                    break

        if not item.category and item.tickers:
            item.category = "company"
