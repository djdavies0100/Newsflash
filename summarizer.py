"""
Generates short AI summaries for news stories.

Tries to fetch and extract the actual article text (for a better summary),
falls back to summarizing from the headline alone if that fails (paywalls,
JS-heavy pages, timeouts, etc. are common with news sites).
"""
import os
import trafilatura
from anthropic import Anthropic, APIError

_client = None


def _get_client():
    global _client
    if _client is None:
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            return None
        _client = Anthropic(api_key=api_key)
    return _client


def summaries_enabled() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


def _extract_article_text(url: str, timeout: int = 8) -> str | None:
    try:
        downloaded = trafilatura.fetch_url(url)
        if not downloaded:
            return None
        text = trafilatura.extract(downloaded)
        if text and len(text) > 200:
            return text[:4000]  # cap to keep prompts small/cheap
    except Exception:
        pass
    return None


def generate_summary(title: str, link: str) -> str:
    """
    Returns a 1-2 sentence AI summary of the story.
    Raises RuntimeError if summaries aren't configured (no API key).
    """
    client = _get_client()
    if client is None:
        raise RuntimeError("ANTHROPIC_API_KEY not set")

    article_text = _extract_article_text(link)

    if article_text:
        prompt = (
            f"Here is a news article. Write a single, information-dense sentence "
            f"(max 30 words) summarizing the key news, suitable for a newspaper "
            f"briefing. No preamble, just the sentence.\n\n"
            f"Headline: {title}\n\nArticle text:\n{article_text}"
        )
    else:
        # Fall back to headline-only summarization
        prompt = (
            f"Based only on this news headline, write a single brief sentence "
            f"(max 20 words) giving likely context or implication, phrased "
            f"neutrally and factually. If you can't infer anything beyond the "
            f"headline, just lightly rephrase it. No preamble, just the sentence.\n\n"
            f"Headline: {title}"
        )

    try:
        msg = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=100,
            messages=[{"role": "user", "content": prompt}],
        )
        return msg.content[0].text.strip()
    except APIError as e:
        raise RuntimeError(f"Anthropic API error: {e}")
