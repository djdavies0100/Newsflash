"""
Simple SQLite storage for topics and daily briefing cache.
Single-user, no auth needed.
"""
import sqlite3
from datetime import date
from pathlib import Path
from contextlib import contextmanager

DB_PATH = Path(__file__).parent / "briefing.db"


@contextmanager
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS topics (
                name TEXT PRIMARY KEY,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS headlines (
                id TEXT,
                topic TEXT,
                title TEXT,
                link TEXT,
                source TEXT,
                published TEXT,
                fetch_date TEXT,
                PRIMARY KEY (id, fetch_date)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS summaries (
                id TEXT PRIMARY KEY,
                summary TEXT,
                generated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS feedback (
                id TEXT PRIMARY KEY,
                topic TEXT,
                title TEXT,
                source TEXT,
                link TEXT,
                rating INTEGER,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)


def add_topic(name: str):
    name = name.strip()
    if not name:
        return
    with get_db() as conn:
        conn.execute("INSERT OR IGNORE INTO topics (name) VALUES (?)", (name,))


def remove_topic(name: str):
    with get_db() as conn:
        conn.execute("DELETE FROM topics WHERE name = ?", (name,))


def get_topics() -> list[str]:
    with get_db() as conn:
        rows = conn.execute("SELECT name FROM topics ORDER BY created_at").fetchall()
        return [r["name"] for r in rows]


def save_headlines(topic: str, headlines: list[dict], fetch_date: str = None):
    fetch_date = fetch_date or date.today().isoformat()
    with get_db() as conn:
        for h in headlines:
            conn.execute("""
                INSERT OR IGNORE INTO headlines (id, topic, title, link, source, published, fetch_date)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (h["id"], topic, h["title"], h["link"], h["source"], h["published"], fetch_date))


def get_briefing(fetch_date: str = None) -> dict:
    fetch_date = fetch_date or date.today().isoformat()
    with get_db() as conn:
        rows = conn.execute("""
            SELECT * FROM headlines WHERE fetch_date = ? ORDER BY topic, published DESC
        """, (fetch_date,)).fetchall()

    all_ids = [r["id"] for r in rows]
    ratings = get_feedback_map(all_ids)

    briefing = {}
    for r in rows:
        briefing.setdefault(r["topic"], []).append({
            "id": r["id"],
            "title": r["title"],
            "link": r["link"],
            "source": r["source"],
            "published": r["published"],
            "rating": ratings.get(r["id"], 0),
        })
    return briefing


def get_cached_summary(headline_id: str) -> str | None:
    with get_db() as conn:
        row = conn.execute(
            "SELECT summary FROM summaries WHERE id = ?", (headline_id,)
        ).fetchone()
        return row["summary"] if row else None


def save_summary(headline_id: str, summary: str):
    with get_db() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO summaries (id, summary) VALUES (?, ?)",
            (headline_id, summary),
        )


def set_feedback(headline_id: str, topic: str, title: str, source: str, link: str, rating: int):
    """rating: 1 (like), -1 (dislike), or 0 (clear/undo)"""
    with get_db() as conn:
        if rating == 0:
            conn.execute("DELETE FROM feedback WHERE id = ?", (headline_id,))
        else:
            conn.execute("""
                INSERT OR REPLACE INTO feedback (id, topic, title, source, link, rating)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (headline_id, topic, title, source, link, rating))


def get_feedback_map(headline_ids: list[str]) -> dict[str, int]:
    """Returns {headline_id: rating} for the given ids that have feedback."""
    if not headline_ids:
        return {}
    with get_db() as conn:
        placeholders = ",".join("?" for _ in headline_ids)
        rows = conn.execute(
            f"SELECT id, rating FROM feedback WHERE id IN ({placeholders})",
            headline_ids,
        ).fetchall()
        return {r["id"]: r["rating"] for r in rows}


def get_source_scores() -> dict[str, int]:
    """Net like/dislike score per source, across all topics and time."""
    with get_db() as conn:
        rows = conn.execute("""
            SELECT source, SUM(rating) as score FROM feedback
            WHERE source IS NOT NULL AND source != ''
            GROUP BY source
        """).fetchall()
        return {r["source"]: r["score"] for r in rows}


def get_blocked_sources(threshold: int = -2) -> set[str]:
    """Sources with a net score at or below threshold get excluded from future fetches."""
    scores = get_source_scores()
    return {source for source, score in scores.items() if score <= threshold}


def get_topic_boosts(min_likes: int = 2, max_boost: int = 6) -> dict[str, int]:
    """
    Extra headline count to fetch for topics with a strong positive like history,
    so topics you engage with more show up with more stories.
    """
    with get_db() as conn:
        rows = conn.execute("""
            SELECT topic, SUM(rating) as score FROM feedback
            GROUP BY topic
        """).fetchall()
    boosts = {}
    for r in rows:
        if r["score"] and r["score"] >= min_likes:
            boosts[r["topic"]] = min(r["score"], max_boost)
    return boosts


SUGGESTED_TOPICS = [
    "World News",
    "U.S. Politics",
    "Technology",
    "Artificial Intelligence",
    "Business & Markets",
    "Science",
    "Climate & Environment",
    "Health",
    "Sports",
    "Entertainment",
    "Space",
    "Personal Finance",
]


def has_briefing_for_today() -> bool:
    with get_db() as conn:
        row = conn.execute(
            "SELECT COUNT(*) as c FROM headlines WHERE fetch_date = ?",
            (date.today().isoformat(),)
        ).fetchone()
        return row["c"] > 0
