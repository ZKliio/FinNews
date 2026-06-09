import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from config.settings import (
    DELIVERY_EMAIL_TO,
    SMTP_HOST,
    SMTP_PASS,
    SMTP_PORT,
    SMTP_USER,
)

logger = logging.getLogger(__name__)


def send_email(draft: str, newsletter_type: str) -> bool:
    if not all([DELIVERY_EMAIL_TO, SMTP_USER, SMTP_PASS]):
        logger.debug("Email not configured, skipping")
        return False

    subject = f"FinTwit {newsletter_type.replace('_', ' ').title()}"
    html_body = _markdown_to_html(draft)

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = SMTP_USER
    msg["To"] = DELIVERY_EMAIL_TO
    msg.attach(MIMEText(draft, "plain"))
    msg.attach(MIMEText(html_body, "html"))

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASS)
            server.send_message(msg)
        logger.info("Email sent to %s", DELIVERY_EMAIL_TO)
        return True
    except Exception as e:
        logger.error("Email send failed: %s", e)
        return False


def _markdown_to_html(md: str) -> str:
    import re
    html = md
    html = re.sub(r"^# (.+)$", r"<h1>\1</h1>", html, flags=re.MULTILINE)
    html = re.sub(r"^## (.+)$", r"<h2>\1</h2>", html, flags=re.MULTILINE)
    html = re.sub(r"^### (.+)$", r"<h3>\1</h3>", html, flags=re.MULTILINE)
    html = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", html)
    html = re.sub(r"\*(.+?)\*", r"<em>\1</em>", html)
    html = re.sub(r"^- (.+)$", r"<li>\1</li>", html, flags=re.MULTILINE)
    html = re.sub(r"^---$", r"<hr>", html, flags=re.MULTILINE)
    html = html.replace("\n", "<br>\n")
    return f"""<html><body style="font-family: -apple-system, sans-serif; max-width: 600px; margin: auto; padding: 20px;">{html}</body></html>"""
