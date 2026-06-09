import json
import logging

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse

logger = logging.getLogger(__name__)

app = FastAPI(title="FinTwit Dashboard")

_db = None


def run_dashboard(db):
    global _db
    _db = db

    import uvicorn
    from config.settings import DASHBOARD_HOST, DASHBOARD_PORT
    logger.info("Starting dashboard on %s:%d", DASHBOARD_HOST, DASHBOARD_PORT)
    uvicorn.run(app, host=DASHBOARD_HOST, port=DASHBOARD_PORT)


@app.get("/", response_class=HTMLResponse)
async def index():
    return DASHBOARD_HTML


@app.get("/api/feed")
async def api_feed():
    if not _db:
        return []
    return _db.get_items_for_dashboard(50)


@app.get("/api/newsletters")
async def api_newsletters():
    if not _db:
        return []
    return _db.get_newsletters(20)


@app.get("/api/status")
async def api_status():
    if not _db:
        return {}
    return _db.get_poll_state()


@app.get("/api/calendar")
async def api_calendar():
    if not _db:
        return []
    return _db.get_upcoming_events(7)


DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>FinTwit Dashboard</title>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { font-family: 'SF Mono', 'Fira Code', monospace; background: #0d1117; color: #c9d1d9; padding: 20px; }
  h1 { color: #58a6ff; margin-bottom: 20px; }
  h2 { color: #8b949e; margin: 20px 0 10px; font-size: 14px; text-transform: uppercase; letter-spacing: 1px; }
  .status-bar { display: flex; gap: 20px; margin-bottom: 20px; padding: 12px; background: #161b22; border-radius: 6px; border: 1px solid #30363d; }
  .status-item { font-size: 13px; }
  .status-label { color: #8b949e; }
  .status-value { color: #58a6ff; font-weight: bold; }
  .state-normal { color: #3fb950; }
  .state-elevated { color: #d29922; }
  .state-critical { color: #f85149; }
  .feed-item { padding: 10px 12px; border-bottom: 1px solid #21262d; font-size: 13px; display: flex; gap: 10px; }
  .feed-item:hover { background: #161b22; }
  .feed-time { color: #8b949e; min-width: 50px; }
  .feed-source { color: #58a6ff; min-width: 120px; }
  .feed-headline { flex: 1; }
  .feed-score { min-width: 50px; text-align: right; font-weight: bold; }
  .score-high { color: #f85149; }
  .score-med { color: #d29922; }
  .score-low { color: #3fb950; }
  .score-none { color: #8b949e; }
  .newsletter-item { padding: 12px; margin-bottom: 8px; background: #161b22; border-radius: 6px; border: 1px solid #30363d; }
  .newsletter-type { color: #d29922; font-weight: bold; text-transform: uppercase; font-size: 11px; }
  .newsletter-time { color: #8b949e; font-size: 12px; }
  .newsletter-preview { color: #c9d1d9; font-size: 13px; margin-top: 6px; white-space: pre-wrap; max-height: 200px; overflow-y: auto; }
  .calendar-item { padding: 6px 0; font-size: 13px; border-bottom: 1px solid #21262d; }
  .cal-date { color: #d29922; }
  .tabs { display: flex; gap: 2px; margin-bottom: 15px; }
  .tab { padding: 8px 16px; background: #21262d; color: #8b949e; cursor: pointer; border: none; font-family: inherit; font-size: 13px; border-radius: 6px 6px 0 0; }
  .tab.active { background: #161b22; color: #58a6ff; }
  .panel { display: none; }
  .panel.active { display: block; }
  .container { max-width: 1200px; margin: 0 auto; }
</style>
</head>
<body>
<div class="container">
  <h1>FinTwit Dashboard</h1>
  <div class="status-bar" id="statusBar">Loading...</div>
  <div class="tabs">
    <button class="tab active" onclick="showTab('feed')">Live Feed</button>
    <button class="tab" onclick="showTab('newsletters')">Newsletters</button>
    <button class="tab" onclick="showTab('calendar')">Calendar</button>
  </div>
  <div id="feed" class="panel active"></div>
  <div id="newsletters" class="panel"></div>
  <div id="calendar" class="panel"></div>
</div>
<script>
function showTab(name) {
  document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  document.getElementById(name).classList.add('active');
  event.target.classList.add('active');
}

function scoreClass(s) {
  if (s >= 0.80) return 'score-high';
  if (s >= 0.45) return 'score-med';
  if (s > 0) return 'score-low';
  return 'score-none';
}

function stateClass(s) {
  if (s === 'critical') return 'state-critical';
  if (s === 'elevated') return 'state-elevated';
  return 'state-normal';
}

async function refresh() {
  try {
    const [feed, nls, status, cal] = await Promise.all([
      fetch('/api/feed').then(r => r.json()),
      fetch('/api/newsletters').then(r => r.json()),
      fetch('/api/status').then(r => r.json()),
      fetch('/api/calendar').then(r => r.json()),
    ]);

    document.getElementById('statusBar').innerHTML = `
      <span class="status-item"><span class="status-label">State:</span> <span class="status-value ${stateClass(status.current_state)}">${(status.current_state||'unknown').toUpperCase()}</span></span>
      <span class="status-item"><span class="status-label">Items today:</span> <span class="status-value">${status.items_today||0}</span></span>
      <span class="status-item"><span class="status-label">Newsletters today:</span> <span class="status-value">${status.newsletters_today||0}</span></span>
      <span class="status-item"><span class="status-label">Last cycle:</span> <span class="status-value">${status.last_cycle_at ? new Date(status.last_cycle_at).toLocaleTimeString() : 'N/A'}</span></span>
    `;

    document.getElementById('feed').innerHTML = '<h2>Live Feed</h2>' +
      feed.map(i => {
        const t = i.published_at ? new Date(i.published_at).toLocaleTimeString([], {hour:'2-digit',minute:'2-digit'}) : '--:--';
        const src = i.source_type === 'x_tweet' ? '@'+i.source_name : i.source_name;
        const tickers = JSON.parse(i.tickers||'[]').join(', ');
        return `<div class="feed-item">
          <span class="feed-time">${t}</span>
          <span class="feed-source">${src}</span>
          <span class="feed-headline">${i.headline}${tickers ? ' ['+tickers+']' : ''}</span>
          <span class="feed-score ${scoreClass(i.urgency_score)}">${i.urgency_score.toFixed(2)}</span>
        </div>`;
      }).join('');

    document.getElementById('newsletters').innerHTML = '<h2>Newsletters</h2>' +
      nls.map(n => `<div class="newsletter-item">
        <span class="newsletter-type">${n.newsletter_type}</span>
        <span class="newsletter-time">${new Date(n.created_at).toLocaleString()}</span>
        <div class="newsletter-preview">${n.draft_markdown}</div>
      </div>`).join('');

    document.getElementById('calendar').innerHTML = '<h2>Upcoming Events (7 days)</h2>' +
      cal.map(c => `<div class="calendar-item">
        <span class="cal-date">${c.event_date}</span> —
        <strong>${c.event_type.toUpperCase()}</strong>: ${c.description}
        ${c.ticker ? '('+c.ticker+')' : ''}
      </div>`).join('');
  } catch(e) { console.error('Refresh failed:', e); }
}

refresh();
setInterval(refresh, 30000);
</script>
</body>
</html>"""
