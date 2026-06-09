import json
import logging
import re
import time

import requests
from bs4 import BeautifulSoup

from config.accounts import ALL_ACCOUNTS
from config.settings import APIFY_API_KEY
from ingest.normalizer import NewsItem, normalize_x_tweet

logger = logging.getLogger(__name__)

_consecutive_failures: dict[str, int] = {}


def fetch_latest() -> list[NewsItem]:
    items = []
    for account in ALL_ACCOUNTS:
        tweets = _fetch_account(account)
        for raw in tweets:
            try:
                items.append(normalize_x_tweet(raw, account))
            except Exception as e:
                logger.warning("Failed to normalize tweet from @%s: %s", account, e)
    return items


def _fetch_account(account: str) -> list[dict]:
    tweets = _fetch_syndication(account)
    if tweets:
        _consecutive_failures[account] = 0
        return tweets

    _consecutive_failures[account] = _consecutive_failures.get(account, 0) + 1
    if _consecutive_failures[account] >= 3:
        logger.warning("@%s: %d consecutive syndication failures", account, _consecutive_failures[account])

    if APIFY_API_KEY:
        tweets = _fetch_apify(account)
        if tweets:
            return tweets

    logger.debug("No tweets fetched for @%s this cycle", account)
    return []


# ── Tier 1: Twitter Syndication API ──

def _fetch_syndication(username: str) -> list[dict]:
    url = f"https://syndication.twitter.com/srv/timeline-profile/screen-name/{username}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        return _parse_syndication_html(resp.text)
    except requests.RequestException as e:
        logger.debug("Syndication failed for @%s: %s", username, e)
        return []


def _parse_syndication_html(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    tweets = []

    script_tags = soup.find_all("script")
    for script in script_tags:
        text = script.string or ""
        json_match = re.search(r'(\{.*"tweet_id".*\})', text, re.DOTALL)
        if not json_match:
            json_match = re.search(r'(\[.*"id_str".*\])', text, re.DOTALL)
        if json_match:
            try:
                data = json.loads(json_match.group(1))
                if isinstance(data, list):
                    tweets.extend(data)
                elif isinstance(data, dict):
                    tweets.append(data)
            except json.JSONDecodeError:
                pass

    if not tweets:
        tweet_divs = soup.find_all("div", class_=re.compile(r"timeline-Tweet|tweet"))
        for div in tweet_divs:
            tweet_data = _extract_tweet_from_div(div)
            if tweet_data:
                tweets.append(tweet_data)

    return tweets


def _extract_tweet_from_div(div) -> dict | None:
    text_el = div.find(class_=re.compile(r"tweet-text|TweetText"))
    if not text_el:
        text_el = div.find("p")
    if not text_el:
        return None

    tweet_id = div.get("data-tweet-id", "")
    if not tweet_id:
        link = div.find("a", href=re.compile(r"/status/\d+"))
        if link:
            match = re.search(r"/status/(\d+)", link["href"])
            if match:
                tweet_id = match.group(1)

    if not tweet_id:
        return None

    time_el = div.find("time")
    created_at = time_el.get("datetime", "") if time_el else ""

    likes = _extract_count(div, r"like|heart|favorite")
    rts = _extract_count(div, r"retweet|rt")
    replies = _extract_count(div, r"repl")

    return {
        "id": tweet_id,
        "text": text_el.get_text(strip=True),
        "created_at": created_at,
        "favorite_count": likes,
        "retweet_count": rts,
        "reply_count": replies,
    }


def _extract_count(div, pattern: str) -> int:
    el = div.find(class_=re.compile(pattern, re.I))
    if el:
        num_match = re.search(r"(\d[\d,.]*)", el.get_text())
        if num_match:
            return int(num_match.group(1).replace(",", "").replace(".", ""))
    return 0


# ── Tier 2: Apify ──

def _fetch_apify(username: str) -> list[dict]:
    if not APIFY_API_KEY:
        return []
    try:
        actor_id = "gentle_cloud~x-twitter-public-data-scraper"
        run_url = f"https://api.apify.com/v2/acts/{actor_id}/runs?token={APIFY_API_KEY}"
        payload = {
            "handles": [username],
            "tweetsDesired": 20,
            "proxyConfig": {"useApifyProxy": True},
        }
        resp = requests.post(run_url, json=payload, timeout=30)
        resp.raise_for_status()
        run_data = resp.json().get("data", {})
        dataset_id = run_data.get("defaultDatasetId")
        if not dataset_id:
            return []

        for _ in range(12):
            time.sleep(5)
            status_url = f"https://api.apify.com/v2/acts/{actor_id}/runs/{run_data['id']}?token={APIFY_API_KEY}"
            status = requests.get(status_url, timeout=10).json()
            if status.get("data", {}).get("status") in ("SUCCEEDED", "FAILED", "ABORTED"):
                break

        items_url = f"https://api.apify.com/v2/datasets/{dataset_id}/items?token={APIFY_API_KEY}"
        items_resp = requests.get(items_url, timeout=10)
        items_resp.raise_for_status()
        return items_resp.json()
    except Exception as e:
        logger.warning("Apify failed for @%s: %s", username, e)
        return []


# ── Engagement re-check (for velocity scoring) ──

def recheck_engagement(pending: list[dict], db) -> None:
    for entry in pending:
        tweet_id = entry["tweet_id"]
        news_item_id = entry["news_item_id"]
        updated = _refetch_tweet_engagement(tweet_id)
        if updated:
            from scoring.velocity import compute_velocity_from_recheck
            compute_velocity_from_recheck(entry, updated, db)
        db.mark_velocity_rechecked(tweet_id)


def _refetch_tweet_engagement(tweet_id: str) -> dict | None:
    try:
        url = f"https://api.fxtwitter.com/x/status/{tweet_id}"
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            data = resp.json().get("tweet", {})
            return {
                "likes": data.get("likes", 0),
                "retweets": data.get("retweets", 0),
                "replies": data.get("replies", 0),
            }
    except Exception as e:
        logger.debug("FXTwitter re-check failed for %s: %s", tweet_id, e)
    return None
