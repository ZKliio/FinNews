import logging

from config.settings import CONTENT_WEIGHT, MARKET_WEIGHT, VELOCITY_WEIGHT
from scoring.content import score_content
from scoring.dedup import deduplicate
from scoring.market import score_market
from scoring.tagger import tag_item
from scoring.velocity import score_velocity

logger = logging.getLogger(__name__)

FORCE_TRIGGER_KEYWORDS = [
    "circuit breaker",
    "trading halt",
    "exchange halt",
]

FORCE_TRIGGER_TOPICS = {"fomc", "cpi", "nfp", "gdp"}

RUMOR_KEYWORDS = [
    "rumor", "rumour", "unconfirmed", "reportedly", "sources say",
    "according to sources", "alleged", "speculation", "speculated",
    "may be planning", "said to be", "could be",
]


def _is_rumor(item) -> bool:
    if item.source_type != "x_tweet":
        return False
    text = (item.headline + " " + (item.body or "")).lower()
    return any(kw in text for kw in RUMOR_KEYWORDS)


def _is_force_trigger(item) -> bool:
    text = (item.headline + " " + (item.body or "")).lower()
    for kw in FORCE_TRIGGER_KEYWORDS:
        if kw in text:
            return True

    if item.source_type == "calendar":
        if any(t in FORCE_TRIGGER_TOPICS for t in item.topics):
            return True

    from config.watchlist import get_tier
    if item.category == "earnings":
        for ticker in item.tickers:
            if get_tier(ticker) == 1:
                return True

    return False


def _has_second_source_confirmation(item, all_items: list) -> bool:
    from scoring.dedup import jaccard_similarity
    for other in all_items:
        if other.id == item.id:
            continue
        if other.source_type == item.source_type and other.source_name == item.source_name:
            continue
        time_diff = abs((item.published_at - other.published_at).total_seconds())
        if time_diff > 300:
            continue
        sim = jaccard_similarity(item.headline, other.headline)
        if sim >= 0.5:
            return True
    return False


def _has_market_confirmation(item) -> bool:
    for ticker in item.tickers:
        from scoring.market import _get_quote
        quote = _get_quote(ticker)
        if quote and abs(quote.get("change_pct", 0)) > 2:
            return True
    return item.market_score >= 0.5


def score_and_trigger(items: list, db) -> list:
    recent_items = db.get_recent_items(hours=1)

    for item in items:
        tag_item(item)

    items = deduplicate(items)

    all_context = items + recent_items

    for item in items:
        item.content_score = score_content(item)
        item.velocity_score = score_velocity(item, all_context)

        if item.content_score > 0.3:
            item.market_score = score_market(item)

        item.urgency_score = (
            CONTENT_WEIGHT * item.content_score +
            VELOCITY_WEIGHT * item.velocity_score +
            MARKET_WEIGHT * item.market_score
        )

        if _is_force_trigger(item):
            item.urgency_score = max(item.urgency_score, 0.80)
            logger.info("Force trigger: %s", item.headline[:80])

        if _is_rumor(item) and item.urgency_score >= 0.80:
            confirmed = (_has_second_source_confirmation(item, all_context) or
                         _has_market_confirmation(item))
            if not confirmed:
                item.urgency_score = min(item.urgency_score, 0.55)
                item.headline = f"[UNCONFIRMED] {item.headline}"
                logger.info("Rumor downgraded to watch: %s", item.headline[:80])

        db.update_scores(item)

        if item.urgency_score >= 0.80:
            logger.info("IMMEDIATE: [%.2f] %s", item.urgency_score, item.headline[:80])
        elif item.urgency_score >= 0.60:
            logger.info("BATCH: [%.2f] %s", item.urgency_score, item.headline[:80])

    return items
