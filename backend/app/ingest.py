"""Content ingest CLI. Usage:
    python -m app.ingest video.mp4 --series-slug ceo-bride --series-title "CEO's Secret Bride" \
        --episode-number 1 --episode-title "The Wedding" --genres romance,drama
Requires FFmpeg on PATH. Uses STORAGE_MODE from .env (local by default).
"""
import argparse
import shutil
import sys
import tempfile
from pathlib import Path

from app import models
from app.config import settings
from app.db import SessionLocal
from app.storage import get_storage
from app.transcode import extract_thumbnail, transcode_to_hls


def get_or_create_series(db, args) -> models.Series:
    series = db.query(models.Series).filter(models.Series.slug == args.series_slug).first()
    if series:
        return series
    series = models.Series(
        slug=args.series_slug, title=args.series_title or args.series_slug,
        synopsis=args.synopsis, language=args.language,
        free_episode_count=args.free_episodes, is_featured=args.featured,
        poster_url=args.poster_url or f"https://picsum.photos/seed/{args.series_slug}/540/960",
        banner_url=args.banner_url or f"https://picsum.photos/seed/{args.series_slug}-b/1280/720",
    )
    for gslug in [g.strip() for g in args.genres.split(",") if g.strip()]:
        genre = db.query(models.Genre).filter(models.Genre.slug == gslug).first()
        if not genre:
            genre = models.Genre(slug=gslug, name=gslug.replace("-", " ").title())
            db.add(genre)
        series.genres.append(genre)
    db.add(series)
    db.flush()
    return series


def upload_thumbnail(episode_id: str, jpg: Path) -> str:
    if settings.imagekit_private_key:
        from imagekitio import ImageKit  # optional dep: pip install imagekitio
        ik = ImageKit(private_key=settings.imagekit_private_key,
                      public_key=settings.imagekit_public_key,
                      url_endpoint=settings.imagekit_url_endpoint)
        with open(jpg, "rb") as f:
            result = ik.upload_file(file=f, file_name=f"{episode_id}.jpg")
        return result.url
    # No ImageKit configured: keep a local copy for dev, but store a URL that
    # works from ANY device — a machine-local /media URL breaks the moment the
    # DB is shared (e.g. Neon rows read by the deployed frontend on a phone).
    dest = Path(settings.media_root) / episode_id / "thumb.jpg"
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(jpg, dest)
    return f"https://picsum.photos/seed/{episode_id}/360/640"


def ingest(args) -> None:
    src = Path(args.video)
    if not src.is_file():
        sys.exit(f"error: video file not found: {src}")
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
        episode.status = "processing"
        db.commit()

        try:
            with tempfile.TemporaryDirectory() as tmp:
                tmpdir = Path(tmp)
                hls_dir = tmpdir / "hls"
                episode.duration_seconds = transcode_to_hls(src, hls_dir)
                episode.hls_path = get_storage().publish(str(episode.id), hls_dir)
                thumb = tmpdir / "thumb.jpg"
                extract_thumbnail(src, thumb)
                episode.thumbnail_url = upload_thumbnail(str(episode.id), thumb)
            episode.status = "ready"
            db.commit()
            print(f"ready: {series.slug} ep{episode.episode_number} ({episode.duration_seconds}s)")
        except Exception as exc:
            episode.status = "failed"
            db.commit()
            sys.exit(f"error: ingest failed, episode marked failed: {exc}")
    finally:
        db.close()


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Ingest a video as a series episode")
    p.add_argument("video")
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
    return p


if __name__ == "__main__":
    ingest(build_parser().parse_args())
