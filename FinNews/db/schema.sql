CREATE TABLE IF NOT EXISTS news_items (
    id TEXT PRIMARY KEY,
    source_type TEXT NOT NULL,
    source_name TEXT NOT NULL,
    original_id TEXT NOT NULL,
    headline TEXT NOT NULL,
    body TEXT,
    url TEXT,
    published_at DATETIME NOT NULL,
    ingested_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    tickers TEXT DEFAULT '[]',
    topics TEXT DEFAULT '[]',
    category TEXT,
    account_tier TEXT,
    credibility REAL DEFAULT 0.5,
    likes INTEGER DEFAULT 0,
    retweets INTEGER DEFAULT 0,
    replies INTEGER DEFAULT 0,
    views INTEGER DEFAULT 0,
    urgency_score REAL DEFAULT 0.0,
    velocity_score REAL DEFAULT 0.0,
    content_score REAL DEFAULT 0.0,
    market_score REAL DEFAULT 0.0,
    cluster_id TEXT,
    is_primary BOOLEAN DEFAULT 1,
    raw_json TEXT
);

CREATE INDEX IF NOT EXISTS idx_published_at ON news_items(published_at);
CREATE INDEX IF NOT EXISTS idx_urgency_score ON news_items(urgency_score);
CREATE INDEX IF NOT EXISTS idx_source_type ON news_items(source_type);
CREATE INDEX IF NOT EXISTS idx_cluster_id ON news_items(cluster_id);

CREATE TABLE IF NOT EXISTS velocity_queue (
    tweet_id TEXT PRIMARY KEY,
    news_item_id TEXT NOT NULL REFERENCES news_items(id),
    likes_t0 INTEGER NOT NULL,
    rts_t0 INTEGER NOT NULL,
    replies_t0 INTEGER NOT NULL,
    first_seen_at DATETIME NOT NULL,
    recheck_at DATETIME NOT NULL,
    rechecked BOOLEAN DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_recheck_at ON velocity_queue(recheck_at);

CREATE TABLE IF NOT EXISTS newsletters (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    newsletter_type TEXT NOT NULL,
    trigger_items TEXT NOT NULL,
    context_sent TEXT NOT NULL,
    draft_markdown TEXT NOT NULL,
    delivered_via TEXT DEFAULT '[]',
    delivered_at DATETIME
);

CREATE TABLE IF NOT EXISTS calendar_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type TEXT NOT NULL,
    event_date DATE NOT NULL,
    event_time TIME,
    ticker TEXT,
    description TEXT,
    metadata TEXT DEFAULT '{}',
    alerted BOOLEAN DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_event_date ON calendar_events(event_date);

CREATE TABLE IF NOT EXISTS poll_state (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    current_state TEXT DEFAULT 'normal',
    state_since DATETIME DEFAULT CURRENT_TIMESTAMP,
    last_cycle_at DATETIME,
    items_today INTEGER DEFAULT 0,
    newsletters_today INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS batch_queue (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    news_item_id TEXT NOT NULL REFERENCES news_items(id),
    added_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
