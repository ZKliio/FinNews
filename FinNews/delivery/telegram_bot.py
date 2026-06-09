import logging

import requests

from config.settings import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

logger = logging.getLogger(__name__)

TYPE_PREFIXES = {
    "breaking": "ALERT",
    "earnings": "EARNINGS",
    "fomc": "FOMC",
    "daily_digest": "DAILY DIGEST",
}

MAX_MESSAGE_LENGTH = 4096


def send_telegram(draft: str, newsletter_type: str) -> bool:
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logger.debug("Telegram not configured, skipping")
        return False

    prefix = TYPE_PREFIXES.get(newsletter_type, "ALERT")
    full_text = f"*{prefix}*\n\n{draft}"

    if len(full_text) <= MAX_MESSAGE_LENGTH:
        return _send_message(full_text)

    chunks = _split_message(full_text)
    success = True
    for chunk in chunks:
        if not _send_message(chunk):
            success = False
    return success


def _send_message(text: str) -> bool:
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True,
    }
    try:
        resp = requests.post(url, json=payload, timeout=10)
        if resp.status_code == 200:
            return True
        logger.warning("Telegram send failed (%d): %s", resp.status_code, resp.text[:200])
        # Retry without markdown if parsing fails
        if resp.status_code == 400 and "parse" in resp.text.lower():
            payload["parse_mode"] = None
            retry = requests.post(url, json=payload, timeout=10)
            return retry.status_code == 200
        return False
    except requests.RequestException as e:
        logger.error("Telegram request failed: %s", e)
        return False


def _split_message(text: str) -> list[str]:
    chunks = []
    parts = text.split("\n---\n")
    current = ""
    for part in parts:
        candidate = current + ("\n---\n" if current else "") + part
        if len(candidate) > MAX_MESSAGE_LENGTH:
            if current:
                chunks.append(current)
            current = part[:MAX_MESSAGE_LENGTH]
        else:
            current = candidate
    if current:
        chunks.append(current)
    return chunks
