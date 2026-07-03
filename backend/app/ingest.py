"""Content ingest CLI. Usage:
    python -m app.ingest video.mp4 --series-slug ceo-bride --series-title "CEO's Secret Bride" \
        --episode-number 1 --episode-title "The Wedding" --genres romance,drama

    # movies (Netflix-style mode): one landscape video per title
    python -m app.ingest film.mp4 --series-slug daal --series-title "Daal" \
        --content-type movie --release-year 2025 --maturity-rating "U/A 13+" \
        --director "Arjun Mehta" --cast "Riya Sen:Asha,Vik Das" --stills 4 --genres drama

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
from app.transcode import extract_frame, extract_thumbnail, make_progressive_mp4, transcode_to_hls


def _imagekit_client():
    from imagekitio import ImageKit  # optional dep: pip install imagekitio (v5 SDK)
    return ImageKit(private_key=settings.imagekit_private_key)


def _imagekit_upload(file_path: Path, file_name: str) -> str:
    with open(file_path, "rb") as f:
        result = _imagekit_client().files.upload(file=f, file_name=file_name)
    return result.url


def upload_video_imagekit(episode_id: str, mp4: Path) -> str:
    return _imagekit_upload(mp4, f"{episode_id}.mp4")


def parse_cast(cast_arg: str) -> list[tuple[str, str]]:
    """'Name:Character,Name2' -> [(name, character), ...]"""
    out = []
    for entry in [c.strip() for c in cast_arg.split(",") if c.strip()]:
        name, _, character = entry.partition(":")
        out.append((name.strip(), character.strip()))
    return out


def resolve_free_episodes(value: int | None, content_type: str) -> int:
    if value is not None:
        return value
    return 0 if content_type == "movie" else 3


def get_or_create_series(db, args) -> models.Series:
    series = db.query(models.Series).filter(models.Series.slug == args.series_slug).first()
    if series:
        return series
    content_type = getattr(args, "content_type", "series")
    series = models.Series(
        slug=args.series_slug, title=args.series_title or args.series_slug,
        synopsis=args.synopsis, language=args.language,
        content_type=content_type,
        release_year=getattr(args, "release_year", None),
        maturity_rating=getattr(args, "maturity_rating", ""),
        free_episode_count=resolve_free_episodes(args.free_episodes, content_type),
        is_featured=args.featured,
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


def upload_image(name: str, jpg: Path, placeholder_size: tuple[int, int]) -> str:
    if settings.imagekit_private_key:
        return _imagekit_upload(jpg, f"{name}.jpg")
    # No ImageKit configured: keep a local copy for dev, but store a URL that
    # works from ANY device — a machine-local /media URL breaks the moment the
    # DB is shared (e.g. Neon rows read by the deployed frontend on a phone).
    dest = Path(settings.media_root) / "images" / f"{name}.jpg"
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(jpg, dest)
    w, h = placeholder_size
    return f"https://picsum.photos/seed/{name}/{w}/{h}"


def upload_thumbnail(episode_id: str, jpg: Path) -> str:
    return upload_image(episode_id, jpg, (360, 640))


def add_movie_metadata(db, series: models.Series, episode: models.Episode,
                       src: Path, tmpdir: Path, args) -> None:
    """Credits + stills for a movie ingest. Idempotent per series."""
    if args.director and not any(c.role == "director" for c in series.credits):
        db.add(models.Credit(series_id=series.id, person_name=args.director,
                             role="director", display_order=0))
    if args.cast and not any(c.role == "cast" for c in series.credits):
        for i, (name, character) in enumerate(parse_cast(args.cast), start=1):
            db.add(models.Credit(series_id=series.id, person_name=name, role="cast",
                                 character_name=character, display_order=i))
    if args.stills > 0 and not series.stills:
        for i in range(args.stills):
            at = max(1.0, episode.duration_seconds * (i + 1) / (args.stills + 1))
            still_jpg = tmpdir / f"still_{i}.jpg"
            extract_frame(src, still_jpg, at_seconds=at, height=720)
            url = upload_image(f"{episode.id}-still-{i}", still_jpg, (640, 360))
            db.add(models.Still(series_id=series.id, image_url=url, display_order=i))


def ingest(args) -> None:
    src = Path(args.video)
    if not src.is_file():
        sys.exit(f"error: video file not found: {src}")
    if args.content_type == "movie" and args.episode_number != 1:
        sys.exit("error: a movie has exactly one video; omit --episode-number (it must be 1)")
    db = SessionLocal()
    try:
        series = get_or_create_series(db, args)
        episode = (db.query(models.Episode)
                     .filter(models.Episode.series_id == series.id,
                             models.Episode.episode_number == args.episode_number).first())
        if episode is None:
            episode = models.Episode(series_id=series.id, episode_number=args.episode_number)
            db.add(episode)
        episode.title = args.episode_title or (
            series.title if args.content_type == "movie" else f"Episode {args.episode_number}")
        episode.status = "processing"
        db.commit()

        orientation = "landscape" if args.content_type == "movie" else "portrait"
        thumb_height = 720 if orientation == "landscape" else 854
        thumb_placeholder = (640, 360) if orientation == "landscape" else (360, 640)
        try:
            with tempfile.TemporaryDirectory() as tmp:
                tmpdir = Path(tmp)
                if settings.storage_mode == "imagekit":
                    mp4 = tmpdir / "video.mp4"
                    episode.duration_seconds = make_progressive_mp4(
                        src, mp4, max_mb=args.max_video_mb)
                    episode.hls_path = upload_video_imagekit(str(episode.id), mp4)
                else:
                    hls_dir = tmpdir / "hls"
                    episode.duration_seconds = transcode_to_hls(src, hls_dir,
                                                                orientation=orientation)
                    episode.hls_path = get_storage().publish(str(episode.id), hls_dir)
                thumb = tmpdir / "thumb.jpg"
                extract_frame(src, thumb, height=thumb_height)
                episode.thumbnail_url = upload_image(str(episode.id), thumb, thumb_placeholder)
                if args.content_type == "movie":
                    add_movie_metadata(db, series, episode, src, tmpdir, args)
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
    p = argparse.ArgumentParser(description="Ingest a video as a series episode or movie")
    p.add_argument("video")
    p.add_argument("--series-slug", required=True)
    p.add_argument("--series-title", default="")
    p.add_argument("--episode-number", type=int, default=1)
    p.add_argument("--episode-title", default="")
    p.add_argument("--synopsis", default="")
    p.add_argument("--language", default="en")
    p.add_argument("--genres", default="drama")
    p.add_argument("--free-episodes", type=int, default=None,
                   help="default: 3 for series, 0 for movies (0=premium, 1=free film)")
    p.add_argument("--poster-url", default="")
    p.add_argument("--banner-url", default="")
    p.add_argument("--featured", action="store_true")
    p.add_argument("--content-type", choices=["series", "movie"], default="series")
    p.add_argument("--release-year", type=int, default=None)
    p.add_argument("--maturity-rating", default="")
    p.add_argument("--director", default="")
    p.add_argument("--cast", default="", help='comma list "Name:Character,Name2"')
    p.add_argument("--stills", type=int, default=0,
                   help="movies: extract N stills evenly across the runtime")
    p.add_argument("--max-video-mb", type=int, default=90,
                   help="imagekit mode: encode size budget (raise for feature films)")
    return p


if __name__ == "__main__":
    ingest(build_parser().parse_args())
