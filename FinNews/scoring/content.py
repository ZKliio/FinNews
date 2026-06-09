from config.accounts import WIRE_ACCOUNTS
from config.watchlist import get_tier

MACRO_CRITICAL = {
    "emergency meeting": 1.0,
    "rate cut": 0.85,
    "rate hike": 0.85,
    "basis points": 0.7,
    "quantitative tightening": 0.7,
    "balance sheet": 0.6,
    "dot plot": 0.6,
    "powell": 0.65,
    "fed chair": 0.65,
    "nonfarm payrolls": 0.7,
    "cpi": 0.7,
    "inflation": 0.6,
    "gdp": 0.6,
    "pce": 0.65,
    "unemployment": 0.55,
    "retail sales": 0.5,
    "ism": 0.5,
    "ppi": 0.5,
    "jobless claims": 0.45,
}

EARNINGS_CRITICAL = {
    "beats": 0.5,
    "misses": 0.6,
    "guides lower": 0.8,
    "guides higher": 0.7,
    "profit warning": 0.85,
    "revenue miss": 0.65,
    "revenue beat": 0.5,
    "raises guidance": 0.7,
    "cuts guidance": 0.85,
    "lowers outlook": 0.8,
    "record revenue": 0.5,
    "layoffs": 0.6,
    "restructuring": 0.55,
}

GEOPOLITICAL_CRITICAL = {
    "tariff": 0.7,
    "sanctions": 0.65,
    "embargo": 0.7,
    "invasion": 0.8,
    "military": 0.5,
    "war": 0.7,
    "ceasefire": 0.6,
    "trade war": 0.75,
    "export controls": 0.6,
    "opec": 0.6,
    "oil production": 0.55,
}

MARKET_STRUCTURE_CRITICAL = {
    "circuit breaker": 0.95,
    "trading halt": 0.8,
    "margin call": 0.7,
    "liquidation": 0.65,
    "flash crash": 0.9,
    "short squeeze": 0.65,
    "gamma squeeze": 0.6,
    "bank run": 0.9,
    "bankruptcy": 0.75,
    "default": 0.7,
    "downgrade": 0.6,
    "upgrade": 0.5,
}

ALL_KEYWORDS = {}
ALL_KEYWORDS.update(MACRO_CRITICAL)
ALL_KEYWORDS.update(EARNINGS_CRITICAL)
ALL_KEYWORDS.update(GEOPOLITICAL_CRITICAL)
ALL_KEYWORDS.update(MARKET_STRUCTURE_CRITICAL)


def score_content(item) -> float:
    text = (item.headline + " " + (item.body or "")).lower()

    matched_scores = []
    for keyword, weight in ALL_KEYWORDS.items():
        if keyword in text:
            matched_scores.append(weight)

    if not matched_scores:
        return 0.1

    base_score = max(matched_scores)

    credibility = item.credibility if item.credibility else 0.5
    score = base_score * credibility

    # ALL-CAPS boost for wire accounts
    if (item.source_name in WIRE_ACCOUNTS and
            item.headline == item.headline.upper() and
            len(item.headline) > 10):
        score += 0.15

    # Ticker tier bonus
    tier_bonus = 0.0
    for ticker in item.tickers:
        t = get_tier(ticker)
        if t == 1:
            tier_bonus = max(tier_bonus, 0.10)
        elif t == 2:
            tier_bonus = max(tier_bonus, 0.05)
    score += tier_bonus

    return min(score, 1.0)
