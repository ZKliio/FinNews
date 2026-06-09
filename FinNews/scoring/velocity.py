import logging
from datetime import datetime, timezone

from scoring.dedup import jaccard_similarity

logger = logging.getLogger(__name__)


def score_velocity(item, recent_items: list) -> float:
    score = 0.0

    # Cluster density: how many tracked accounts posted the same thing recently
    cluster_size = 1
    cross_source = False
    for other in recent_items:
        if other.id == item.id:
            continue
        time_diff = abs((item.published_at - other.published_at).total_seconds())
        if time_diff > 180:  # 3-minute window
            continue
        sim = jaccard_similarity(item.headline, other.headline)
        if sim >= 0.6:
            cluster_size += 1
            if other.source_type != item.source_type:
                cross_source = True

    if cluster_size >= 4:
        score = max(score, 0.9)
    elif cluster_size >= 3:
        score = max(score, 0.7)
    elif cluster_size >= 2:
        score = max(score, 0.5)

    if cross_source:
        score = min(score + 0.1, 1.0)

    # For X tweets, factor in basic engagement at ingest time
    if item.source_type == "x_tweet":
        rts = item.retweets or 0
        if rts > 500:
            score = max(score, 0.5)
        elif rts > 200:
            score = max(score, 0.3)

    return score


def compute_velocity_from_recheck(entry: dict, updated: dict, db) -> None:
    first_seen = datetime.fromisoformat(entry["first_seen_at"])
    elapsed = (datetime.now(timezone.utc) - first_seen).total_seconds() / 60
    if elapsed <= 0:
        return

    rt_velocity = (updated["retweets"] - entry["rts_t0"]) / elapsed

    if rt_velocity > 100:
        vel_score = 1.0
    elif rt_velocity > 50:
        vel_score = 0.8
    elif rt_velocity > 20:
        vel_score = 0.6
    elif rt_velocity > 10:
        vel_score = 0.4
    else:
        vel_score = 0.2

    from ingest.normalizer import NewsItem
    row = db.conn.execute(
        "SELECT * FROM news_items WHERE id = ?", (entry["news_item_id"],)
    ).fetchone()
    if row:
        item = db._row_to_newsitem(row)
        item.velocity_score = max(item.velocity_score, vel_score)

        from config.settings import CONTENT_WEIGHT, VELOCITY_WEIGHT, MARKET_WEIGHT
        item.urgency_score = (
            CONTENT_WEIGHT * item.content_score +
            VELOCITY_WEIGHT * item.velocity_score +
            MARKET_WEIGHT * item.market_score
        )
        db.update_scores(item)
        logger.info(
            "Velocity recheck: %s — %.1f RT/min → vel=%.2f, urgency=%.2f",
            item.headline[:60], rt_velocity, vel_score, item.urgency_score,
        )
