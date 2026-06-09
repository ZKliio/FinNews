import logging

logger = logging.getLogger(__name__)

_price_cache: dict[str, dict] = {}


def _get_quote(symbol: str) -> dict | None:
    from config.settings import FINNHUB_API_KEY
    if not FINNHUB_API_KEY:
        return _get_quote_yfinance(symbol)

    import requests
    try:
        resp = requests.get(
            "https://finnhub.io/api/v1/quote",
            params={"symbol": symbol, "token": FINNHUB_API_KEY},
            timeout=5,
        )
        if resp.status_code == 200:
            data = resp.json()
            if data.get("c"):
                return {
                    "current": data["c"],
                    "change": data.get("d", 0),
                    "change_pct": data.get("dp", 0),
                    "open": data.get("o", 0),
                    "high": data.get("h", 0),
                    "low": data.get("l", 0),
                }
    except Exception as e:
        logger.debug("Finnhub quote failed for %s: %s", symbol, e)

    return _get_quote_yfinance(symbol)


def _get_quote_yfinance(symbol: str) -> dict | None:
    try:
        import yfinance as yf
        ticker = yf.Ticker(symbol)
        info = ticker.fast_info
        current = info.get("lastPrice") or info.get("last_price")
        prev = info.get("previousClose") or info.get("previous_close")
        if current and prev:
            change = current - prev
            change_pct = (change / prev) * 100
            return {
                "current": current,
                "change": change,
                "change_pct": change_pct,
                "open": info.get("open", 0),
                "high": info.get("dayHigh", info.get("day_high", 0)),
                "low": info.get("dayLow", info.get("day_low", 0)),
            }
    except Exception as e:
        logger.debug("yfinance failed for %s: %s", symbol, e)
    return None


def score_market(item) -> float:
    score = 0.0

    # SPY check
    spy = _get_quote("SPY")
    if spy and spy["change_pct"]:
        pct = abs(spy["change_pct"])
        if pct > 1.0:
            score = max(score, 1.0)
        elif pct > 0.5:
            score = max(score, 0.8)

    # VIX check
    vix = _get_quote("VIX")
    if not vix:
        vix = _get_quote("^VIX")
    if vix:
        vix_level = vix.get("current", 0)
        vix_change = abs(vix.get("change_pct", 0))
        if vix_level > 30:
            score = max(score, 0.9)
        elif vix_level > 25:
            score = max(score, 0.6)
        if vix_change > 10:
            score = max(score, 0.7)

    # Individual ticker check
    for ticker in item.tickers:
        quote = _get_quote(ticker)
        if not quote:
            continue
        pct = abs(quote.get("change_pct", 0))
        if pct > 10:
            score = max(score, 1.0)
        elif pct > 5:
            score = max(score, 0.9)
        elif pct > 3:
            score = max(score, 0.7)

    return score


def get_market_snapshot() -> str:
    lines = []
    for symbol, label in [("SPY", "S&P 500 (SPY)"), ("QQQ", "Nasdaq (QQQ)")]:
        q = _get_quote(symbol)
        if q:
            direction = "+" if q["change"] >= 0 else ""
            lines.append(f"- {label}: ${q['current']:.2f} ({direction}{q['change_pct']:.2f}%)")

    vix = _get_quote("VIX") or _get_quote("^VIX")
    if vix:
        lines.append(f"- VIX: {vix['current']:.2f}")

    tnx = _get_quote("^TNX")
    if tnx:
        lines.append(f"- 10Y Yield: {tnx['current']:.3f}%")

    if not lines:
        return "Market data unavailable"
    return "\n".join(lines)
