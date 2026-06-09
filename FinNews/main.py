"""
FinTwit Newsletter Agent — Entry point.

Usage:
    python main.py                  # Run continuous monitoring loop
    python main.py --once           # Run one cycle and exit
    python main.py --digest         # Force a daily digest now
    python main.py --dashboard      # Start web dashboard only
"""

import argparse
import logging
import sys
import time

from config.settings import TRIGGER_BATCH, TRIGGER_IMMEDIATE, NEWSLETTER_COOLDOWN_MINUTES, BATCH_INTERVAL_MINUTES
from db.store import DB
from delivery import deliver
from ingest import calendar_ingest, news_ingest, x_ingest
from newsletter.assembler import assemble_context
from newsletter.drafter import draft_newsletter
from scheduler import get_poll_interval, update_poll_state
from scoring.engine import score_and_trigger

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def classify_newsletter_type(items: list) -> str:
    categories = [i.category for i in items if i.category]
    topics = set()
    for i in items:
        topics.update(i.topics)

    if "fomc" in topics or "fed" in topics:
        if any(i.source_type == "calendar" and "fomc" in (i.headline or "").lower() for i in items):
            return "fomc"
    if all(c == "earnings" for c in categories if c):
        return "earnings"
    return "breaking"


def run_cycle(db: DB):
    pending_rechecks = db.get_pending_velocity_rechecks()
    if pending_rechecks:
        logger.info("Processing %d velocity rechecks", len(pending_rechecks))
        x_ingest.recheck_engagement(pending_rechecks, db)

    raw_items = []
    raw_items.extend(x_ingest.fetch_latest())
    raw_items.extend(news_ingest.fetch_latest())
    raw_items.extend(calendar_ingest.check_upcoming_events())

    new_items = db.insert_many(raw_items)
    db.record_cycle(len(new_items))

    if not new_items:
        logger.debug("No new items this cycle")
        return

    logger.info("Ingested %d new items", len(new_items))

    x_items = [i for i in new_items if i.source_type == "x_tweet"]
    for item in x_items:
        if item.content_score > 0.3:
            db.queue_velocity_recheck(item, delay_minutes=4)

    scored_items = score_and_trigger(new_items, db)

    update_poll_state(scored_items, db)

    immediate = [i for i in scored_items if i.urgency_score >= TRIGGER_IMMEDIATE]
    batch = [i for i in scored_items if TRIGGER_BATCH <= i.urgency_score < TRIGGER_IMMEDIATE]

    if immediate and not db.is_on_cooldown(minutes=NEWSLETTER_COOLDOWN_MINUTES):
        context = assemble_context(immediate, db)
        newsletter_type = classify_newsletter_type(immediate)
        draft = draft_newsletter(context, newsletter_type)
        delivered_via = deliver(draft, newsletter_type)
        db.log_newsletter(newsletter_type, immediate, context, draft, delivered_via)
        logger.info("Immediate newsletter sent: %s", newsletter_type)

    if batch:
        db.add_to_batch_queue(batch)

    if db.batch_queue_ready(interval_minutes=BATCH_INTERVAL_MINUTES):
        queued = db.flush_batch_queue()
        if queued:
            context = assemble_context(queued, db)
            draft = draft_newsletter(context, "breaking")
            delivered_via = deliver(draft, "breaking")
            db.log_newsletter("breaking", queued, context, draft, delivered_via)
            logger.info("Batch newsletter sent: %d items", len(queued))


def main():
    parser = argparse.ArgumentParser(description="FinTwit Newsletter Agent")
    parser.add_argument("--once", action="store_true", help="Run one cycle and exit")
    parser.add_argument("--digest", action="store_true", help="Force a daily digest now")
    parser.add_argument("--dashboard", action="store_true", help="Start web dashboard only")
    args = parser.parse_args()

    db = DB()
    db.initialize()

    if args.dashboard:
        from delivery.web_dashboard import run_dashboard
        run_dashboard(db)
        return

    if args.digest:
        items = db.get_top_items_today(limit=20)
        if not items:
            logger.info("No items today for digest")
            return
        context = assemble_context(items, db)
        draft = draft_newsletter(context, "daily_digest")
        delivered_via = deliver(draft, "daily_digest")
        db.log_newsletter("daily_digest", items, context, draft, delivered_via)
        logger.info("Daily digest sent")
        return

    if args.once:
        run_cycle(db)
        return

    logger.info("Starting continuous monitoring loop...")
    while True:
        try:
            run_cycle(db)
        except KeyboardInterrupt:
            logger.info("Shutting down...")
            db.close()
            sys.exit(0)
        except Exception as e:
            logger.error("Cycle error: %s", e, exc_info=True)

        interval = get_poll_interval(db)
        logger.debug("Sleeping %d seconds", interval)
        try:
            time.sleep(interval)
        except KeyboardInterrupt:
            logger.info("Shutting down...")
            db.close()
            sys.exit(0)


if __name__ == "__main__":
    main()
