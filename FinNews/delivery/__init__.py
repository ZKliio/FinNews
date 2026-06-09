import logging

from delivery.file_dump import save_to_file
from delivery.telegram_bot import send_telegram
from delivery.email_sender import send_email

logger = logging.getLogger(__name__)


def deliver(draft: str, newsletter_type: str) -> list[str]:
    delivered_via = []

    save_to_file(draft, newsletter_type)
    delivered_via.append("file")

    if send_telegram(draft, newsletter_type):
        delivered_via.append("telegram")

    from config.settings import DELIVERY_EMAIL_ENABLED
    if DELIVERY_EMAIL_ENABLED and newsletter_type == "daily_digest":
        if send_email(draft, newsletter_type):
            delivered_via.append("email")

    logger.info("Delivered via: %s", ", ".join(delivered_via))
    return delivered_via
