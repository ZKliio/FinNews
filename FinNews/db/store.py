import json
import logging
import os
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

from ingest.normalizer import NewsItem

logger = logging.getLogger(__name__)


class DB:
    def __init__(self, db_path: str | None = None):
        from config.settings import DB_PATH
        self.db_path = db_path or DB_PATH
        self.conn: sqlite3.Connection | None = None

    def initialize(self):
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        schema_path = Path(__file__).parent / "schema.sql"
        with open(schema_path) as f:
            self.conn.executescript(f.read())
        self.conn.execute(
            "INSERT OR IGNORE INTO poll_state (id, current_state) VALUES (1, 'normal')"
        )
        self.conn.commit()

    def close(self):
        if self.conn:
            self.conn.close()

    # ── Insert ──

    def insert_many(self, items: list[NewsItem]) -> list[NewsItem]:
        new_items = []
        for item in items:
            if self._exists(item.id):
                continue
            self._insert_item(item)
            new_items.append(item)
        self.conn.commit()
        return new_items

    def _exists(self, item_id: str) -> bool:
        row = self.conn.execute(
            "SELECT 1 FROM news_items WHERE id = ?", (item_id,)
        ).fetchone()
        return row is not None

    def _insert_item(self, item: NewsItem):
        self.conn.execute(
            """INSERT INTO news_items
               (id, source_type, source_name, original_id, headline, body, url,
                published_at, ingested_at, tickers, topics, category,
                account_tier, credibility, likes, retweets, replies, views,
                urgency_score, velocity_score, content_score, market_score,
                cluster_id, is_primary, raw_json)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                item.id, item.source_type, item.source_name, item.original_id,
                item.headline, item.body, item.url,
                item.published_at.isoformat(), item.ingested_at.isoformat(),
                json.dumps(item.tickers), json.dumps(item.topics), item.category,
                item.account_tier, item.credibility,
                item.likes, item.retweets, item.replies, item.views,
                item.urgency_score, item.velocity_score,
                item.content_score, item.market_score,
                item.cluster_id, item.is_primary, None,
            ),
        )

    def update_scores(self, item: NewsItem):
        self.conn.execute(
            """UPDATE news_items
               SET urgency_score=?, velocity_score=?, content_score=?, market_score=?,
                   tickers=?, topics=?, category=?, cluster_id=?, is_primary=?
               WHERE id=?""",
            (
                item.urgency_score, item.velocity_score,
                item.content_score, item.market_score,
                json.dumps(item.tickers), json.dumps(item.topics),
                item.category, item.cluster_id, item.is_primary, item.id,
            ),
        )
        self.conn.commit()

    # ── Velocity queue ──

    def queue_velocity_recheck(self, item: NewsItem, delay_minutes: int = 4):
        recheck_at = datetime.now(timezone.utc) + timedelta(minutes=delay_minutes)
        self.conn.execute(
            """INSERT OR IGNORE INTO velocity_queue
               (tweet_id, news_item_id, likes_t0, rts_t0, replies_t0,
                first_seen_at, recheck_at)
               VALUES (?,?,?,?,?,?,?)""",
            (
                item.original_id, item.id,
                item.likes, item.retweets, item.replies,
                datetime.now(timezone.utc).isoformat(), recheck_at.isoformat(),
            ),
        )
        self.conn.commit()

    def get_pending_velocity_rechecks(self) -> list[dict]:
        now = datetime.now(timezone.utc).isoformat()
        rows = self.conn.execute(
            """SELECT tweet_id, news_item_id, likes_t0, rts_t0, replies_t0,
                      first_seen_at, recheck_at
               FROM velocity_queue
               WHERE rechecked = 0 AND recheck_at <= ?""",
            (now,),
        ).fetchall()
        return [dict(r) for r in rows]

    def mark_velocity_rechecked(self, tweet_id: str):
        self.conn.execute(
            "UPDATE velocity_queue SET rechecked = 1 WHERE tweet_id = ?",
            (tweet_id,),
        )
        self.conn.commit()

    # ── Query helpers ──

    def query_related(self, items: list[NewsItem], hours: int = 2, min_score: float = 0.3) -> list[NewsItem]:
        all_tickers = set()
        all_topics = set()
        item_ids = set()
        for item in items:
            all_tickers.update(item.tickers)
            all_topics.update(item.topics)
            item_ids.add(item.id)

        cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
        rows = self.conn.execute(
            """SELECT * FROM news_items
               WHERE published_at >= ? AND urgency_score >= ?
               ORDER BY urgency_score DESC LIMIT 20""",
            (cutoff, min_score),
        ).fetchall()

        related = []
        for row in rows:
            if row["id"] in item_ids:
                continue
            row_tickers = set(json.loads(row["tickers"]))
            row_topics = set(json.loads(row["topics"]))
            if row_tickers & all_tickers or row_topics & all_topics:
                related.append(self._row_to_newsitem(row))
        return related[:5]

    def get_recent_items(self, hours: int = 1) -> list[NewsItem]:
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
        rows = self.conn.execute(
            "SELECT * FROM news_items WHERE published_at >= ? ORDER BY published_at DESC",
            (cutoff,),
        ).fetchall()
        return [self._row_to_newsitem(r) for r in rows]

    def get_top_items_today(self, limit: int = 20) -> list[NewsItem]:
        today = datetime.now(timezone.utc).date().isoformat()
        rows = self.conn.execute(
            """SELECT * FROM news_items
               WHERE date(published_at) = ?
               ORDER BY urgency_score DESC LIMIT ?""",
            (today, limit),
        ).fetchall()
        return [self._row_to_newsitem(r) for r in rows]

    def get_items_for_dashboard(self, limit: int = 50) -> list[dict]:
        rows = self.conn.execute(
            "SELECT * FROM news_items ORDER BY ingested_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]

    # ── Newsletters ──

    def is_on_cooldown(self, minutes: int = 15) -> bool:
        cutoff = (datetime.now(timezone.utc) - timedelta(minutes=minutes)).isoformat()
        row = self.conn.execute(
            "SELECT 1 FROM newsletters WHERE created_at >= ? LIMIT 1",
            (cutoff,),
        ).fetchone()
        return row is not None

    def log_newsletter(self, newsletter_type: str, items: list[NewsItem],
                       context: str, draft: str, delivered_via: list[str] | None = None):
        self.conn.execute(
            """INSERT INTO newsletters (newsletter_type, trigger_items, context_sent,
                                        draft_markdown, delivered_via, delivered_at)
               VALUES (?,?,?,?,?,?)""",
            (
                newsletter_type,
                json.dumps([i.id for i in items]),
                context,
                draft,
                json.dumps(delivered_via or []),
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        self.conn.execute(
            "UPDATE poll_state SET newsletters_today = newsletters_today + 1 WHERE id = 1"
        )
        self.conn.commit()

    def get_newsletters(self, limit: int = 20) -> list[dict]:
        rows = self.conn.execute(
            "SELECT * FROM newsletters ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]

    # ── Batch queue ──

    def add_to_batch_queue(self, items: list[NewsItem]):
        for item in items:
            self.conn.execute(
                "INSERT OR IGNORE INTO batch_queue (news_item_id) VALUES (?)",
                (item.id,),
            )
        self.conn.commit()

    def batch_queue_ready(self, interval_minutes: int = 30) -> bool:
        row = self.conn.execute(
            "SELECT MIN(added_at) as oldest FROM batch_queue"
        ).fetchone()
        if not row or not row["oldest"]:
            return False
        oldest = datetime.fromisoformat(row["oldest"])
        return (datetime.now(timezone.utc) - oldest).total_seconds() >= interval_minutes * 60

    def flush_batch_queue(self) -> list[NewsItem]:
        rows = self.conn.execute(
            """SELECT ni.* FROM batch_queue bq
               JOIN news_items ni ON ni.id = bq.news_item_id
               ORDER BY ni.urgency_score DESC"""
        ).fetchall()
        self.conn.execute("DELETE FROM batch_queue")
        self.conn.commit()
        return [self._row_to_newsitem(r) for r in rows]

    # ── Calendar ──

    def insert_calendar_event(self, event_type: str, event_date: str,
                              event_time: str | None, ticker: str | None,
                              description: str, metadata: dict | None = None):
        existing = self.conn.execute(
            """SELECT 1 FROM calendar_events
               WHERE event_type=? AND event_date=? AND COALESCE(ticker,'')=?""",
            (event_type, event_date, ticker or ""),
        ).fetchone()
        if existing:
            return
        self.conn.execute(
            """INSERT INTO calendar_events (event_type, event_date, event_time,
                                            ticker, description, metadata)
               VALUES (?,?,?,?,?,?)""",
            (event_type, event_date, event_time, ticker, description,
             json.dumps(metadata or {})),
        )
        self.conn.commit()

    def get_upcoming_events(self, days: int = 7) -> list[dict]:
        today = datetime.now(timezone.utc).date().isoformat()
        end = (datetime.now(timezone.utc).date() + timedelta(days=days)).isoformat()
        rows = self.conn.execute(
            """SELECT * FROM calendar_events
               WHERE event_date BETWEEN ? AND ?
               ORDER BY event_date, event_time""",
            (today, end),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_events_within_hours(self, hours: int = 24) -> list[dict]:
        today = datetime.now(timezone.utc).date().isoformat()
        tomorrow = (datetime.now(timezone.utc).date() + timedelta(days=1)).isoformat()
        rows = self.conn.execute(
            """SELECT * FROM calendar_events
               WHERE event_date BETWEEN ? AND ?""",
            (today, tomorrow),
        ).fetchall()
        return [dict(r) for r in rows]

    # ── Poll state ──

    def get_poll_state(self) -> dict:
        row = self.conn.execute("SELECT * FROM poll_state WHERE id = 1").fetchone()
        return dict(row) if row else {"current_state": "normal"}

    def set_poll_state(self, state: str):
        self.conn.execute(
            "UPDATE poll_state SET current_state = ?, state_since = ? WHERE id = 1",
            (state, datetime.now(timezone.utc).isoformat()),
        )
        self.conn.commit()

    def record_cycle(self, new_item_count: int):
        self.conn.execute(
            """UPDATE poll_state
               SET last_cycle_at = ?, items_today = items_today + ?
               WHERE id = 1""",
            (datetime.now(timezone.utc).isoformat(), new_item_count),
        )
        self.conn.commit()

    # ── Helpers ──

    def _row_to_newsitem(self, row) -> NewsItem:
        return NewsItem(
            id=row["id"],
            source_type=row["source_type"],
            source_name=row["source_name"],
            original_id=row["original_id"],
            headline=row["headline"],
            body=row["body"],
            url=row["url"],
            published_at=datetime.fromisoformat(row["published_at"]),
            ingested_at=datetime.fromisoformat(row["ingested_at"]),
            tickers=json.loads(row["tickers"]),
            topics=json.loads(row["topics"]),
            category=row["category"],
            likes=row["likes"],
            retweets=row["retweets"],
            replies=row["replies"],
            views=row["views"],
            urgency_score=row["urgency_score"],
            velocity_score=row["velocity_score"],
            content_score=row["content_score"],
            market_score=row["market_score"],
            account_tier=row["account_tier"],
            credibility=row["credibility"],
            cluster_id=row["cluster_id"],
            is_primary=bool(row["is_primary"]),
        )
