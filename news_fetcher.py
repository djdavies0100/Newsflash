"""
Fetches headlines for a given topic using Google News RSS search.
No API key required. Works for any free-text topic/query.
"""
import feedparser
import hashlib
from datetime import datetime, timezone
from urllib.parse import quote


def _hash_id(title: str, link: str) -> str:
    return hashlib.sha256(f"{title}|{link}".encode("utf-8")).hexdigest()[:16]


def fetch_topic_headlines(topic: str, max_items: int = 12, excluded_sources: set[str] = None) -> list[dict]:
    """
    Fetch recent headlines for a topic via Google News RSS.
    Returns a list of dicts: id, title, link, source, published (ISO str), topic
    excluded_sources: source names to skip (e.g. sources the user has disliked repeatedly)
    """
    excluded_sources = excluded_sources or set()
    query = quote(topic)
    url = f"https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en"

    feed = feedparser.parse(url)
    items = []

    # Pull a bit more than needed since some may get filtered out by excluded_sources
    for entry in feed.entries[: max_items * 2]:
        if len(items) >= max_items:
            break

        title = getattr(entry, "title", "").strip()
        link = getattr(entry, "link", "")
        if not title or not link:
            continue

        # Google News RSS format is usually "Headline - Source Name"
        source = ""
        if hasattr(entry, "source") and getattr(entry.source, "title", None):
            source = entry.source.title
        elif " - " in title:
            source = title.rsplit(" - ", 1)[-1]

        if source in excluded_sources:
            continue

        published = ""
        if hasattr(entry, "published_parsed") and entry.published_parsed:
            published = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc).isoformat()

        items.append({
            "id": _hash_id(title, link),
            "title": title,
            "link": link,
            "source": source,
            "published": published,
            "topic": topic,
        })

    return items


def fetch_all(
    topics: list[str],
    max_items_per_topic: int = 8,
    excluded_sources: set[str] = None,
    topic_boosts: dict[str, int] = None,
) -> dict[str, list[dict]]:
    """Fetch headlines for multiple topics. Returns {topic: [headlines]}."""
    topic_boosts = topic_boosts or {}
    result = {}
    for topic in topics:
        count = max_items_per_topic + topic_boosts.get(topic, 0)
        result[topic] = fetch_topic_headlines(topic, count, excluded_sources)
    return result
