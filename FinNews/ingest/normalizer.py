import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class NewsItem:
    id: str
    source_type: str
    source_name: str
    original_id: str
    headline: str
    body: str | None = None
    url: str | None = None
    published_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    ingested_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    tickers: list[str] = field(default_factory=list)
    topics: list[str] = field(default_factory=list)
    category: str | None = None
    likes: int = 0
    retweets: int = 0
    replies: int = 0
    views: int = 0
    urgency_score: float = 0.0
    velocity_score: float = 0.0
    content_score: float = 0.0
    market_score: float = 0.0
    account_tier: str | None = None
    credibility: float = 0.5
    cluster_id: str | None = None
    is_primary: bool = True


def make_id(source_type: str, original_id: str) -> str:
    raw = f"{source_type}:{original_id}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def normalize_x_tweet(raw: dict, account: str) -> NewsItem:
    from config.accounts import ACCOUNT_RELIABILITY

    meta = ACCOUNT_RELIABILITY.get(account, {})
    tweet_id = str(raw.get("id", raw.get("tweet_id", "")))
    text = raw.get("text", raw.get("full_text", ""))
    published = raw.get("created_at")
    if isinstance(published, str):
        try:
            published = datetime.fromisoformat(published.replace("Z", "+00:00"))
        except ValueError:
            published = datetime.now(timezone.utc)
    elif not isinstance(published, datetime):
        published = datetime.now(timezone.utc)

    return NewsItem(
        id=make_id("x_tweet", tweet_id),
        source_type="x_tweet",
        source_name=account,
        original_id=tweet_id,
        headline=text[:500],
        url=f"https://x.com/{account}/status/{tweet_id}" if tweet_id else None,
        published_at=published,
        likes=raw.get("favorite_count", raw.get("likes", 0)) or 0,
        retweets=raw.get("retweet_count", raw.get("retweets", 0)) or 0,
        replies=raw.get("reply_count", raw.get("replies", 0)) or 0,
        views=raw.get("views", raw.get("view_count", 0)) or 0,
        account_tier=meta.get("tier"),
        credibility=meta.get("credibility", 0.5),
    )


def normalize_finnhub_news(raw: dict) -> NewsItem:
    article_id = str(raw.get("id", raw.get("url", "")))
    ts = raw.get("datetime", 0)
    if isinstance(ts, (int, float)):
        published = datetime.fromtimestamp(ts, tz=timezone.utc)
    else:
        published = datetime.now(timezone.utc)

    return NewsItem(
        id=make_id("finnhub", article_id),
        source_type="finnhub",
        source_name=raw.get("source", "finnhub"),
        original_id=article_id,
        headline=raw.get("headline", "")[:500],
        body=raw.get("summary", ""),
        url=raw.get("url"),
        published_at=published,
        tickers=raw.get("related", "").split(",") if raw.get("related") else [],
        credibility=0.85,
    )


def normalize_polygon_news(raw: dict) -> NewsItem:
    article_id = raw.get("id", raw.get("article_url", ""))
    published_str = raw.get("published_utc", "")
    try:
        published = datetime.fromisoformat(published_str.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        published = datetime.now(timezone.utc)

    tickers = [t.get("ticker", t) if isinstance(t, dict) else t
               for t in (raw.get("tickers", []) or [])]

    return NewsItem(
        id=make_id("polygon", str(article_id)),
        source_type="polygon",
        source_name="polygon",
        original_id=str(article_id),
        headline=raw.get("title", "")[:500],
        body=raw.get("description", ""),
        url=raw.get("article_url"),
        published_at=published,
        tickers=tickers,
        credibility=0.85,
    )


def normalize_newsapi(raw: dict) -> NewsItem:
    url = raw.get("url", "")
    source = raw.get("source", {})
    source_name = source.get("name", "newsapi") if isinstance(source, dict) else "newsapi"

    published_str = raw.get("publishedAt", "")
    try:
        published = datetime.fromisoformat(published_str.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        published = datetime.now(timezone.utc)

    return NewsItem(
        id=make_id("newsapi", url),
        source_type="newsapi",
        source_name=source_name,
        original_id=url,
        headline=(raw.get("title") or "")[:500],
        body=raw.get("description", ""),
        url=url,
        published_at=published,
        credibility=0.75,
    )


def normalize_eodhd(raw: dict) -> NewsItem:
    link = raw.get("link", "")
    symbols = raw.get("symbols", [])
    tickers = [s.split(".")[0] for s in symbols] if symbols else []

    published_str = raw.get("date", "")
    try:
        published = datetime.fromisoformat(published_str.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        published = datetime.now(timezone.utc)

    return NewsItem(
        id=make_id("eodhd", link),
        source_type="eodhd",
        source_name="eodhd",
        original_id=link,
        headline=(raw.get("title") or "")[:500],
        body=raw.get("content", ""),
        url=link,
        published_at=published,
        tickers=tickers,
        credibility=0.75,
    )
