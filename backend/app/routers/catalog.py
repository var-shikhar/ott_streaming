from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app import models
from app.db import get_db
from app.deps import get_optional_user
from app.entitlement import active_subscription
from app.errors import ApiError
from app.routers.social import social_stats

router = APIRouter(prefix="/api/v1", tags=["catalog"])


def ready_episodes(series: models.Series) -> list[models.Episode]:
    return [e for e in series.episodes if e.status == "ready"]


def series_out(s: models.Series) -> dict:
    return {
        "id": str(s.id), "slug": s.slug, "title": s.title, "synopsis": s.synopsis,
        "language": s.language, "poster_url": s.poster_url, "banner_url": s.banner_url,
        "free_episode_count": s.free_episode_count, "is_featured": s.is_featured,
        "view_count": s.view_count, "genres": [g.name for g in s.genres],
        "episode_count": len(ready_episodes(s)),
    }


def published(db: Session):
    return db.query(models.Series).filter(models.Series.status == "published")
 

@router.get("/home")
def home(db: Session = Depends(get_db), user=Depends(get_optional_user)):
    all_series = published(db).all()
    featured = [series_out(s) for s in all_series if s.is_featured]
    trending = [series_out(s) for s in sorted(all_series, key=lambda s: -s.view_count)[:10]]
    new_releases = [series_out(s) for s in
                    sorted(all_series, key=lambda s: s.published_at, reverse=True)[:10]]
    genre_rails = []
    for g in db.query(models.Genre).order_by(models.Genre.name).all():
        in_genre = [series_out(s) for s in all_series if g in s.genres]
        if in_genre:
            genre_rails.append({"genre": {"slug": g.slug, "name": g.name}, "series": in_genre})
    continue_watching = []
    if user is not None:
        rows = (db.query(models.WatchProgress)
                  .filter(models.WatchProgress.user_id == user.id,
                          models.WatchProgress.completed.is_(False))
                  .order_by(models.WatchProgress.updated_at.desc()).limit(10).all())
        for row in rows:
            ep = row.episode
            if ep.status == "ready" and ep.series.status == "published":
                continue_watching.append({
                    "series": series_out(ep.series), "episode_number": ep.episode_number,
                    "episode_id": str(ep.id), "position_seconds": row.position_seconds,
                })
    return {"featured": featured, "trending": trending, "new_releases": new_releases,
            "genre_rails": genre_rails, "continue_watching": continue_watching}


@router.get("/series")
def list_series(db: Session = Depends(get_db)):
    return [series_out(s) for s in published(db).order_by(models.Series.published_at.desc()).all()]


@router.get("/series/{slug}")
def series_detail(slug: str, db: Session = Depends(get_db), user=Depends(get_optional_user)):
    s = published(db).filter(models.Series.slug == slug).first()
    if not s:
        raise ApiError(404, "not_found", "Series not found")
    subscribed = active_subscription(db, user) is not None
    out = series_out(s)
    episodes = ready_episodes(s)
    stats = social_stats(db, [e.id for e in episodes], user)
    out["episodes"] = [{
        "id": str(e.id), "episode_number": e.episode_number, "title": e.title,
        "duration_seconds": e.duration_seconds, "thumbnail_url": e.thumbnail_url,
        "is_free": e.episode_number <= s.free_episode_count,
        "locked": e.episode_number > s.free_episode_count and not subscribed,
        **stats[e.id],
    } for e in episodes]
    return out


@router.get("/genres")
def genres(db: Session = Depends(get_db)):
    return [{"slug": g.slug, "name": g.name}
            for g in db.query(models.Genre).order_by(models.Genre.name)]


@router.get("/genres/{slug}/series")
def genre_series(slug: str, db: Session = Depends(get_db)):
    g = db.query(models.Genre).filter(models.Genre.slug == slug).first()
    if not g:
        raise ApiError(404, "not_found", "Genre not found")
    items = [series_out(s) for s in published(db).all() if g in s.genres]
    return {"genre": {"slug": g.slug, "name": g.name}, "series": items}


@router.get("/search")
def search(q: str = Query(min_length=1), db: Session = Depends(get_db)):
    pattern = f"%{q.lower()}%"
    rows = published(db).filter(models.Series.title.ilike(pattern)).limit(20).all()
    return [series_out(s) for s in rows]
