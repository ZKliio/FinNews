import logging
from datetime import datetime, timezone

import requests

from config.settings import FINNHUB_API_KEY
from config.watchlist import TIER_1, TIER_2, get_tier
from ingest.normalizer import NewsItem, make_id

logger = logging.getLogger(__name__)

FOMC_DATES_2026 = [
    ("2026-01-28", False),
    ("2026-03-18", True),
    ("2026-05-06", False),
    ("2026-06-17", True),
    ("2026-07-29", False),
    ("2026-09-16", True),
    ("2026-11-04", False),
    ("2026-12-16", True),
]


def check_upcoming_events() -> list[NewsItem]:
    items = []
    items.extend(_check_fomc())
    items.extend(_fetch_earnings_calendar())
    items.extend(_fetch_economic_calendar())
    return items


def _check_fomc() -> list[NewsItem]:
    items = []
    now = datetime.now(timezone.utc)
    today = now.strftime("%Y-%m-%d")

    for date_str, has_sep in FOMC_DATES_2026:
        if date_str == today:
            sep_note = " (with SEP/dot plot)" if has_sep else ""
            items.append(NewsItem(
                id=make_id("calendar", f"fomc-{date_str}"),
                source_type="calendar",
                source_name="fomc_calendar",
                original_id=f"fomc-{date_str}",
                headline=f"FOMC decision day — statement expected 2:00 PM ET{sep_note}",
                published_at=now,
                topics=["fed", "rates", "fomc"],
                category="macro",
                credibility=1.0,
            ))
    return items


def _fetch_earnings_calendar() -> list[NewsItem]:
    if not FINNHUB_API_KEY:
        return []
    now = datetime.now(timezone.utc)
    today = now.strftime("%Y-%m-%d")

    try:
        resp = requests.get(
            "https://finnhub.io/api/v1/calendar/earnings",
            params={"from": today, "to": today, "token": FINNHUB_API_KEY},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        logger.warning("Earnings calendar fetch failed: %s", e)
        return []

    earnings = data.get("earningsCalendar", [])
    items = []
    for entry in earnings:
        symbol = entry.get("symbol", "")
        tier = get_tier(symbol)
        if tier is None:
            continue

        hour = entry.get("hour", "")
        timing = "before market open" if hour == "bmo" else "after market close" if hour == "amc" else ""
        eps_est = entry.get("epsEstimate")
        eps_act = entry.get("epsActual")
        rev_est = entry.get("revenueEstimate")
        rev_act = entry.get("revenueActual")

        if eps_act is not None and eps_est:
            surprise_pct = abs(eps_act - eps_est) / abs(eps_est) * 100 if eps_est != 0 else 0
            direction = "beats" if eps_act > eps_est else "misses"
            headline = f"{symbol} earnings: EPS ${eps_act:.2f} {direction} est ${eps_est:.2f} ({surprise_pct:.1f}% surprise)"
            category = "earnings"
        else:
            headline = f"{symbol} reports earnings today {timing} (EPS est: ${eps_est:.2f})" if eps_est else f"{symbol} reports earnings today {timing}"
            category = "earnings"

        item = NewsItem(
            id=make_id("calendar", f"earnings-{symbol}-{today}"),
            source_type="calendar",
            source_name="finnhub_earnings",
            original_id=f"earnings-{symbol}-{today}",
            headline=headline,
            published_at=now,
            tickers=[symbol],
            topics=["earnings"],
            category=category,
            credibility=0.95,
        )

        if tier == 1:
            item.urgency_score = 0.80
            item.content_score = 0.80
        elif tier == 2 and eps_act is not None and eps_est and eps_est != 0:
            surprise = abs(eps_act - eps_est) / abs(eps_est) * 100
            if surprise > 5:
                item.urgency_score = 0.70
                item.content_score = 0.70
        items.append(item)

    return items


def _fetch_economic_calendar() -> list[NewsItem]:
    if not FINNHUB_API_KEY:
        return []
    try:
        resp = requests.get(
            "https://finnhub.io/api/v1/calendar/economic",
            params={"token": FINNHUB_API_KEY},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        logger.warning("Economic calendar fetch failed: %s", e)
        return []

    high_impact = {"CPI", "PPI", "NFP", "GDP", "PCE", "Retail Sales", "ISM", "Unemployment Rate",
                   "Nonfarm Payrolls", "Consumer Price Index", "Producer Price Index",
                   "Personal Consumption Expenditures", "Initial Jobless Claims"}

    events = data.get("economicCalendar", data.get("result", []))
    if not isinstance(events, list):
        return []

    now = datetime.now(timezone.utc)
    today = now.strftime("%Y-%m-%d")
    items = []

    for event in events:
        event_name = event.get("event", "")
        event_date = event.get("date", "")
        if not event_date.startswith(today):
            continue

        is_high = any(kw.lower() in event_name.lower() for kw in high_impact)
        if not is_high:
            impact = event.get("impact", "")
            if str(impact).lower() not in ("high", "3"):
                continue

        actual = event.get("actual")
        estimate = event.get("estimate")
        prev = event.get("prev")

        parts = [event_name]
        if actual is not None:
            parts.append(f"Actual: {actual}")
        if estimate is not None:
            parts.append(f"Est: {estimate}")
        if prev is not None:
            parts.append(f"Prev: {prev}")
        headline = " | ".join(parts)

        topics = []
        name_lower = event_name.lower()
        if "cpi" in name_lower or "inflation" in name_lower:
            topics = ["cpi", "inflation"]
        elif "nonfarm" in name_lower or "payroll" in name_lower:
            topics = ["nfp", "employment"]
        elif "gdp" in name_lower:
            topics = ["gdp"]
        elif "pce" in name_lower:
            topics = ["pce", "inflation"]
        else:
            topics = ["macro"]

        items.append(NewsItem(
            id=make_id("calendar", f"econ-{event_name}-{today}"),
            source_type="calendar",
            source_name="finnhub_economic",
            original_id=f"econ-{event_name}-{today}",
            headline=headline,
            published_at=now,
            topics=topics,
            category="macro",
            credibility=1.0,
        ))

    return items
