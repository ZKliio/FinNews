import os

TIER_1 = ["AAPL", "MSFT", "NVDA", "AMZN", "GOOG", "META", "TSLA", "BRK.B"]

TIER_2 = [
    "JPM", "GS", "BAC",
    "UNH", "JNJ", "LLY",
    "XOM", "CVX",
    "HD", "WMT", "COST",
    "CRM", "ORCL", "ADBE",
    "AVGO", "TSM", "AMD",
    "BA", "CAT", "UNP",
    "DIS", "NFLX",
]

TIER_3 = [
    t.strip()
    for t in os.getenv("WATCHLIST_TIER_3", "").split(",")
    if t.strip()
]

ALL_TICKERS = TIER_1 + TIER_2 + TIER_3


def get_tier(ticker: str) -> int | None:
    if ticker in TIER_1:
        return 1
    if ticker in TIER_2:
        return 2
    if ticker in TIER_3:
        return 3
    return None
