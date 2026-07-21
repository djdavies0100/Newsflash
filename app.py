"""
Daily News Briefing app.
Run with: uvicorn app:app --reload --port 8000
Then open http://localhost:8000
"""
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from apscheduler.schedulers.background import BackgroundScheduler
from pathlib import Path
from datetime import date

import storage
import news_fetcher
import summarizer

app = FastAPI(title="Daily News Briefing")

storage.init_db()

STATIC_DIR = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


class TopicIn(BaseModel):
    name: str


class FeedbackIn(BaseModel):
    id: str
    topic: str
    title: str
    source: str = ""
    link: str = ""
    rating: int  # 1 = like, -1 = dislike, 0 = clear


@app.get("/")
def root():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/topics")
def list_topics():
    return {"topics": storage.get_topics()}


@app.post("/api/topics")
def add_topic(topic: TopicIn):
    storage.add_topic(topic.name)
    return {"topics": storage.get_topics()}


@app.delete("/api/topics/{name}")
def delete_topic(name: str):
    storage.remove_topic(name)
    return {"topics": storage.get_topics()}


@app.get("/api/suggested-topics")
def suggested_topics():
    existing = set(storage.get_topics())
    return {"suggestions": [t for t in storage.SUGGESTED_TOPICS if t not in existing]}


@app.get("/api/summary/{headline_id}")
def get_summary(headline_id: str, title: str, link: str):
    """
    Returns a cached AI summary for a story, generating and caching one
    on first request. Returns enabled=false if no API key is configured.
    """
    if not summarizer.summaries_enabled():
        return {"enabled": False, "summary": None}

    cached = storage.get_cached_summary(headline_id)
    if cached:
        return {"enabled": True, "summary": cached}

    try:
        summary = summarizer.generate_summary(title, link)
        storage.save_summary(headline_id, summary)
        return {"enabled": True, "summary": summary}
    except RuntimeError as e:
        return {"enabled": True, "summary": None, "error": str(e)}


@app.post("/api/feedback")
def submit_feedback(feedback: FeedbackIn):
    if feedback.rating not in (-1, 0, 1):
        return {"ok": False, "error": "rating must be -1, 0, or 1"}
    storage.set_feedback(
        feedback.id, feedback.topic, feedback.title,
        feedback.source, feedback.link, feedback.rating,
    )
    return {"ok": True}


@app.get("/api/briefing")
def get_briefing(refresh: bool = False):
    """
    Get today's briefing. If it doesn't exist yet (or refresh=true),
    fetch fresh headlines for all saved topics first.
    """
    if refresh or not storage.has_briefing_for_today():
        topics = storage.get_topics()
        excluded_sources = storage.get_blocked_sources()
        topic_boosts = storage.get_topic_boosts()
        results = news_fetcher.fetch_all(topics, excluded_sources=excluded_sources, topic_boosts=topic_boosts)
        for topic, headlines in results.items():
            storage.save_headlines(topic, headlines)

    return {
        "date": date.today().isoformat(),
        "briefing": storage.get_briefing(),
    }


# --- Daily auto-refresh scheduler ---
def _daily_refresh_job():
    topics = storage.get_topics()
    if not topics:
        return
    excluded_sources = storage.get_blocked_sources()
    topic_boosts = storage.get_topic_boosts()
    results = news_fetcher.fetch_all(topics, excluded_sources=excluded_sources, topic_boosts=topic_boosts)
    for topic, headlines in results.items():
        storage.save_headlines(topic, headlines)


scheduler = BackgroundScheduler()
scheduler.add_job(_daily_refresh_job, "cron", hour=7, minute=0)  # 7:00 AM daily
scheduler.start()
