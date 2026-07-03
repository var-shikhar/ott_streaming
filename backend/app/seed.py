"""Seed demo content. Requires FFmpeg. Usage: python -m app.seed"""
import subprocess
import tempfile
from pathlib import Path

from app import models
from app.config import settings
from app.db import SessionLocal
from app.ingest import upload_image, upload_thumbnail, upload_video_imagekit
from app.storage import get_storage
from app.transcode import (extract_frame, extract_thumbnail, make_progressive_mp4,
                           transcode_to_hls)


def publish_clip(storage, episode, clip: Path, workdir: Path,
                 orientation: str = "portrait") -> None:
    """Store a clip the way the configured storage mode expects: progressive MP4
    on ImageKit, or an HLS ladder via the Storage backend otherwise."""
    if settings.storage_mode == "imagekit":
        mp4 = workdir / "video.mp4"
        episode.duration_seconds = make_progressive_mp4(clip, mp4)
        episode.hls_path = upload_video_imagekit(str(episode.id), mp4)
    else:
        episode.duration_seconds = transcode_to_hls(clip, workdir / "hls",
                                                    orientation=orientation)
        episode.hls_path = storage.publish(str(episode.id), workdir / "hls")

GENRES = [("romance", "Romance"), ("drama", "Drama"), ("comedy", "Comedy"),
          ("suspense", "Suspense"), ("action", "Action")]

PLANS = [("Weekly", 4900, "weekly"), ("Monthly", 14900, "monthly"), ("Yearly", 99900, "yearly")]

SERIES = [
    {"slug": "ceos-secret-bride", "title": "CEO's Secret Bride", "genres": ["romance", "drama"],
     "synopsis": "A contract marriage with the city's coldest billionaire was supposed to be "
                 "business — until it wasn't.", "featured": True, "hue": 0},
    {"slug": "revenge-of-the-heiress", "title": "Revenge of the Heiress",
     "genres": ["drama", "suspense"],
     "synopsis": "Betrayed and left for dead, she returns with a new face and one plan: "
                 "make them all pay.", "featured": True, "hue": 90},
    {"slug": "midnight-campus", "title": "Midnight Campus", "genres": ["suspense"],
     "synopsis": "Every night at 12:03, someone in the dorm gets a text from a number "
                 "that doesn't exist.", "featured": False, "hue": 180},
    {"slug": "accidentally-famous", "title": "Accidentally Famous", "genres": ["comedy", "romance"],
     "synopsis": "A delivery girl's rant goes viral and now the whole country thinks she's "
                 "dating a superstar.", "featured": False, "hue": 270},
]

EPISODES_PER_SERIES = 5
FREE_EPISODES = 2

MOVIES = [
    {"slug": "the-last-metro", "title": "The Last Metro", "genres": ["drama", "suspense"],
     "synopsis": "A night-shift metro driver finds a passenger who was declared dead "
                 "three years ago.", "featured": True, "hue": 30, "year": 2025,
     "rating": "U/A 16+", "free": 1, "director": "Arjun Mehta",
     "cast": [("Priya Sharma", "Meera"), ("Rohan Kapoor", "Dev"),
              ("Neha Joshi", "Inspector Rane")]},
    {"slug": "monsoon-wedding-crashers", "title": "Monsoon Wedding Crashers",
     "genres": ["comedy", "romance"],
     "synopsis": "Two broke caterers crash big-fat weddings for the buffet — until one of "
                 "them falls for a bride.", "featured": True, "hue": 120, "year": 2024,
     "rating": "U/A 13+", "free": 0, "director": "Sana Qureshi",
     "cast": [("Vik Das", "Monty"), ("Ananya Rao", "Tara")]},
    {"slug": "paper-boats", "title": "Paper Boats", "genres": ["drama"],
     "synopsis": "A father and daughter rebuild their flooded bookshop one shelf at a time.",
     "featured": False, "hue": 210, "year": 2025, "rating": "U", "free": 0,
     "director": "K. Balan", "cast": [("Meenakshi Iyer", "Anju"), ("Prakash Nair", "Appa")]},
    {"slug": "signal-lost", "title": "Signal Lost", "genres": ["suspense", "action"],
     "synopsis": "A trekking vlogger's live stream keeps broadcasting after her phone "
                 "battery dies.", "featured": False, "hue": 300, "year": 2023,
     "rating": "A", "free": 0, "director": "Dev Anand Pillai",
     "cast": [("Shreya Menon", "Ira"), ("Aditya Verma", "The Voice")]},
]
MOVIE_SECONDS = 30
STILLS_PER_MOVIE = 4


def generate_movie_clip(dest: Path, hue: int) -> None:
    subprocess.run(
        ["ffmpeg", "-y",
         "-f", "lavfi", "-i", f"testsrc2=size=1280x720:rate=30,hue=h={hue}",
         "-f", "lavfi", "-i", "sine=frequency=200",
         "-t", str(MOVIE_SECONDS), "-c:v", "libx264", "-preset", "veryfast",
         "-c:a", "aac", "-shortest", str(dest)],
        check=True, capture_output=True)


def generate_clip(dest: Path, hue: int, episode_number: int) -> None:
    seconds = 8
    subprocess.run(
        ["ffmpeg", "-y",
         "-f", "lavfi", "-i", f"testsrc2=size=720x1280:rate=30,hue=h={hue}",
         "-f", "lavfi", "-i", f"sine=frequency={300 + 60 * episode_number}",
         "-t", str(seconds), "-c:v", "libx264", "-preset", "veryfast",
         "-c:a", "aac", "-shortest", str(dest)],
        check=True, capture_output=True)


def seed():
    db = SessionLocal()
    try:
        genres = {}
        for slug, name in GENRES:
            g = db.query(models.Genre).filter(models.Genre.slug == slug).first()
            if not g:
                g = models.Genre(slug=slug, name=name)
                db.add(g)
            genres[slug] = g
        for name, price, interval in PLANS:
            if not db.query(models.Plan).filter(models.Plan.name == name).first():
                db.add(models.Plan(name=name, price_inr=price, interval=interval,
                                   razorpay_plan_id=""))
        db.commit()

        storage = get_storage()
        for spec in SERIES:
            if db.query(models.Series).filter(models.Series.slug == spec["slug"]).first():
                print(f"skip existing: {spec['slug']}")
                continue
            series = models.Series(
                slug=spec["slug"], title=spec["title"], synopsis=spec["synopsis"],
                language="en", free_episode_count=FREE_EPISODES, is_featured=spec["featured"],
                poster_url=f"https://picsum.photos/seed/{spec['slug']}/540/960",
                banner_url=f"https://picsum.photos/seed/{spec['slug']}-b/1280/720",
                genres=[genres[g] for g in spec["genres"]])
            db.add(series)
            db.flush()
            for n in range(1, EPISODES_PER_SERIES + 1):
                ep = models.Episode(series_id=series.id, episode_number=n,
                                    title=f"Episode {n}", status="processing")
                db.add(ep)
                db.flush()
                with tempfile.TemporaryDirectory() as tmp:
                    tmpdir = Path(tmp)
                    clip = tmpdir / "clip.mp4"
                    generate_clip(clip, spec["hue"], n)
                    publish_clip(storage, ep, clip, tmpdir, orientation="portrait")
                    thumb = tmpdir / "thumb.jpg"
                    extract_thumbnail(clip, thumb)
                    ep.thumbnail_url = upload_thumbnail(str(ep.id), thumb)
                ep.status = "ready"
                db.commit()
                print(f"seeded {spec['slug']} ep{n}")

        for spec in MOVIES:
            if db.query(models.Series).filter(models.Series.slug == spec["slug"]).first():
                print(f"skip existing: {spec['slug']}")
                continue
            movie = models.Series(
                slug=spec["slug"], title=spec["title"], synopsis=spec["synopsis"],
                language="en", content_type="movie", free_episode_count=spec["free"],
                is_featured=spec["featured"], release_year=spec["year"],
                maturity_rating=spec["rating"],
                poster_url=f"https://picsum.photos/seed/{spec['slug']}/540/960",
                banner_url=f"https://picsum.photos/seed/{spec['slug']}-b/1280/720",
                genres=[genres[g] for g in spec["genres"]])
            db.add(movie)
            db.flush()
            db.add(models.Credit(series_id=movie.id, person_name=spec["director"],
                                 role="director", display_order=0))
            for i, (name, character) in enumerate(spec["cast"], start=1):
                db.add(models.Credit(series_id=movie.id, person_name=name, role="cast",
                                     character_name=character, display_order=i))
            ep = models.Episode(series_id=movie.id, episode_number=1,
                                title=spec["title"], status="processing")
            db.add(ep)
            db.flush()
            with tempfile.TemporaryDirectory() as tmp:
                tmpdir = Path(tmp)
                clip = tmpdir / "film.mp4"
                generate_movie_clip(clip, spec["hue"])
                publish_clip(storage, ep, clip, tmpdir, orientation="landscape")
                thumb = tmpdir / "thumb.jpg"
                extract_frame(clip, thumb, at_seconds=1.0, height=720)
                ep.thumbnail_url = upload_image(str(ep.id), thumb, (640, 360))
                for i in range(STILLS_PER_MOVIE):
                    at = max(1.0, ep.duration_seconds * (i + 1) / (STILLS_PER_MOVIE + 1))
                    still = tmpdir / f"still_{i}.jpg"
                    extract_frame(clip, still, at_seconds=at, height=720)
                    url = upload_image(f"{ep.id}-still-{i}", still, (640, 360))
                    db.add(models.Still(series_id=movie.id, image_url=url, display_order=i))
            ep.status = "ready"
            db.commit()
            print(f"seeded movie {spec['slug']}")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
