from datetime import datetime, timezone

from ingest.normalizer import NewsItem


def assemble_context(triggered_items: list[NewsItem], db) -> str:
    sections = []

    sections.append("## BREAKING DEVELOPMENTS\n")
    for item in sorted(triggered_items, key=lambda x: x.urgency_score, reverse=True)[:5]:
        sections.append(_format_item(item))

    related = db.query_related(triggered_items, hours=2, min_score=0.3)
    if related:
        sections.append("\n## RELATED CONTEXT (past 2 hours)\n")
        for item in related[:5]:
            sections.append(_format_item(item))

    calendar_ctx = _get_calendar_context(db)
    if calendar_ctx:
        sections.append(f"\n## UPCOMING EVENTS\n{calendar_ctx}")

    from scoring.market import get_market_snapshot
    snapshot = get_market_snapshot()
    sections.append(f"\n## MARKET SNAPSHOT\n{snapshot}")

    return "\n".join(sections)


def _format_item(item: NewsItem) -> str:
    ticker_str = f" [{', '.join(item.tickers)}]" if item.tickers else ""
    topic_str = f" ({', '.join(item.topics)})" if item.topics else ""
    src = f"@{item.source_name}" if item.source_type == "x_tweet" else item.source_name
    return (
        f"- [{item.published_at.strftime('%H:%M')} UTC] "
        f"{src}: {item.headline}{ticker_str}{topic_str} "
        f"[score: {item.urgency_score:.2f}]"
    )


def _get_calendar_context(db) -> str:
    events = db.get_events_within_hours(24)
    if not events:
        return ""
    lines = []
    for ev in events:
        ticker = f" ({ev['ticker']})" if ev.get("ticker") else ""
        time_str = f" at {ev['event_time']}" if ev.get("event_time") else ""
        lines.append(f"- {ev['event_type'].upper()}: {ev['description']}{ticker}{time_str}")
    return "\n".join(lines)
