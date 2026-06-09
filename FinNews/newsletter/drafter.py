import logging

import anthropic

from newsletter.templates import NEWSLETTER_PROMPTS

logger = logging.getLogger(__name__)


def draft_newsletter(context: str, newsletter_type: str = "breaking") -> str:
    system_prompt = NEWSLETTER_PROMPTS.get(newsletter_type, NEWSLETTER_PROMPTS["breaking"])

    try:
        client = anthropic.Anthropic()
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2000,
            system=system_prompt,
            messages=[{"role": "user", "content": context}],
        )
        draft = response.content[0].text
        logger.info("Newsletter drafted (%s): %d chars", newsletter_type, len(draft))
        return draft
    except Exception as e:
        logger.error("Claude API call failed: %s", e)
        return _fallback_draft(context, newsletter_type)


def _fallback_draft(context: str, newsletter_type: str) -> str:
    return f"# FinTwit Alert — {newsletter_type.upper()}\n\n{context}\n\n---\n*Auto-generated (Claude API unavailable)*"
