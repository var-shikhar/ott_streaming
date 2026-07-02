"""Seed demo content. Requires FFmpeg. Usage: python -m app.seed"""
import subprocess
import tempfile
from pathlib import Path

from app import models
from app.db import SessionLocal
from app.ingest import upload_thumbnail
from app.storage import get_storage
from app.transcode import extract_thumbnail, transcode_to_hls

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
                    ep.duration_seconds = transcode_to_hls(clip, tmpdir / "hls")
                    ep.hls_path = storage.publish(str(ep.id), tmpdir / "hls")
                    thumb = tmpdir / "thumb.jpg"
                    extract_thumbnail(clip, thumb)
                    ep.thumbnail_url = upload_thumbnail(str(ep.id), thumb)
                ep.status = "ready"
                db.commit()
                print(f"seeded {spec['slug']} ep{n}")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
