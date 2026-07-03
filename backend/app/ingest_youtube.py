"""Add episodes that play via the official YouTube embed (nothing is downloaded
or re-hosted — the video streams from YouTube inside our player shell).

Usage:
    python -m app.ingest_youtube "https://youtu.be/XXXX" \
        --series-slug my-show --series-title "My Show" --episode-number 1 \
        --episode-title "Pilot" --genres drama --duration 180

Accepts watch URLs, youtu.be short links, /shorts/ links, or a bare video id.
"""
import argparse
import re
import sys

from app import models
from app.db import SessionLocal
from app.ingest import get_or_create_series

_YT_PATTERNS = [
    r"(?:v=|/shorts/|/embed/|youtu\.be/)([A-Za-z0-9_-]{11})",
    r"^([A-Za-z0-9_-]{11})$",
]


def extract_youtube_id(url_or_id: str) -> str | None:
    for pattern in _YT_PATTERNS:
        m = re.search(pattern, url_or_id.strip())
        if m:
            return m.group(1)
    return None


def ingest_youtube(args) -> None:
    youtube_id = extract_youtube_id(args.video)
    if not youtube_id:
        sys.exit(f"error: could not parse a YouTube video id from: {args.video}")
    db = SessionLocal()
    try:
        series = get_or_create_series(db, args)
        episode = (db.query(models.Episode)
                     .filter(models.Episode.series_id == series.id,
                             models.Episode.episode_number == args.episode_number).first())
        if episode is None:
            episode = models.Episode(series_id=series.id, episode_number=args.episode_number)
            db.add(episode)
        episode.title = args.episode_title or f"Episode {args.episode_number}"
        episode.youtube_id = youtube_id
        episode.hls_path = ""
        episode.duration_seconds = args.duration
        episode.thumbnail_url = f"https://i.ytimg.com/vi/{youtube_id}/hqdefault.jpg"
        episode.status = "ready"
        db.commit()
        print(f"ready: {series.slug} ep{episode.episode_number} -> youtube:{youtube_id}")
    finally:
        db.close()


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Add a YouTube-embedded episode")
    p.add_argument("video", help="YouTube URL or 11-char video id")
    p.add_argument("--series-slug", required=True)
    p.add_argument("--series-title", default="")
    p.add_argument("--episode-number", type=int, required=True)
    p.add_argument("--episode-title", default="")
    p.add_argument("--synopsis", default="")
    p.add_argument("--language", default="en")
    p.add_argument("--genres", default="drama")
    p.add_argument("--free-episodes", type=int, default=3)
    p.add_argument("--poster-url", default="")
    p.add_argument("--banner-url", default="")
    p.add_argument("--featured", action="store_true")
    p.add_argument("--duration", type=int, default=0, help="seconds (optional, display only)")
    return p


if __name__ == "__main__":
    ingest_youtube(build_parser().parse_args())
