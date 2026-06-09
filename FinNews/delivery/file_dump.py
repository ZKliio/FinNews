import logging
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

OUTPUT_DIR = Path("output/newsletters")


def save_to_file(draft: str, newsletter_type: str) -> str:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d-%H%M%S")
    filename = f"{timestamp}-{newsletter_type}.md"
    filepath = OUTPUT_DIR / filename
    filepath.write_text(draft, encoding="utf-8")
    logger.info("Newsletter saved: %s", filepath)
    return str(filepath)
