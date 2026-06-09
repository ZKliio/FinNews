import logging
from datetime import datetime, time, timedelta, timezone

import pytz

logger = logging.getLogger(__name__)

ET = pytz.timezone("US/Eastern")


class PollState:
    NORMAL = "normal"
    ELEVATED = "elevated"
    CRITICAL = "critical"


def get_poll_interval(db=None) -> int:
    if db:
        state = db.get_poll_state()
        current = state.get("current_state", PollState.NORMAL)
        if current == PollState.CRITICAL:
            return 10
        if current == PollState.ELEVATED:
            return 20

    now = datetime.now(ET)
    t = now.time()
    weekday = now.weekday()

    if weekday >= 5:
        return 1800

    if time(4, 0) <= t < time(9, 30):
        return 120

    if time(9, 30) <= t < time(16, 0):
        return 60

    if time(16, 0) <= t < time(20, 0):
        return 90

    return 600


def update_poll_state(scored_items: list, db) -> None:
    state = db.get_poll_state()
    current = state.get("current_state", PollState.NORMAL)
    state_since = state.get("state_since", "")

    if state_since:
        try:
            since = datetime.fromisoformat(state_since)
            if since.tzinfo is None:
                since = since.replace(tzinfo=timezone.utc)
            elapsed = (datetime.now(timezone.utc) - since).total_seconds()
            if current != PollState.NORMAL and elapsed > 1800:
                logger.info("Poll state auto-decay: %s → NORMAL (30 min elapsed)", current)
                db.set_poll_state(PollState.NORMAL)
                return
        except ValueError:
            pass

    max_score = max((i.urgency_score for i in scored_items), default=0)

    topic_sources = {}
    for item in scored_items:
        for topic in item.topics:
            if topic not in topic_sources:
                topic_sources[topic] = set()
            topic_sources[topic].add(item.source_name)
    multi_source_topic = any(len(sources) >= 2 for sources in topic_sources.values())

    cluster_density = 0
    for item in scored_items:
        if item.cluster_id:
            count = sum(1 for other in scored_items if other.cluster_id == item.cluster_id)
            cluster_density = max(cluster_density, count)

    new_state = current

    if current == PollState.NORMAL:
        if max_score > 0.80 or cluster_density >= 3:
            new_state = PollState.CRITICAL
        elif max_score > 0.60 or multi_source_topic:
            new_state = PollState.ELEVATED
    elif current == PollState.ELEVATED:
        if max_score > 0.80 or cluster_density >= 3:
            new_state = PollState.CRITICAL
    elif current == PollState.CRITICAL:
        pass

    if max_score < 0.45:
        if state_since:
            try:
                since = datetime.fromisoformat(state_since)
                if since.tzinfo is None:
                    since = since.replace(tzinfo=timezone.utc)
                if (datetime.now(timezone.utc) - since).total_seconds() > 900:
                    new_state = PollState.NORMAL
            except ValueError:
                pass

    if new_state != current:
        logger.info("Poll state: %s → %s (max_score=%.2f, cluster=%d)",
                     current, new_state, max_score, cluster_density)
        db.set_poll_state(new_state)
