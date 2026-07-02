import uuid

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app import models
from app.config import settings
from app.db import get_db
from app.deps import get_optional_user
from app.entitlement import can_watch
from app.errors import ApiError
from app.storage import get_storage

router = APIRouter(prefix="/api/v1", tags=["playback"])


@router.get("/episodes/{episode_id}/playback")
def playback(episode_id: uuid.UUID, response: Response,
             db: Session = Depends(get_db), user=Depends(get_optional_user)):
    ep = db.get(models.Episode, episode_id)
    if not ep or ep.status != "ready" or ep.series.status != "published" or not ep.hls_path:
        raise ApiError(404, "not_found", "Episode not available")
    if not can_watch(db, user, ep):
        raise ApiError(403, "subscription_required", "Subscribe to watch this episode")

    ep.series.view_count += 1
    resume = 0
    if user is not None:
        row = db.get(models.WatchProgress, (user.id, ep.id))
        if row and not row.completed:
            resume = row.position_seconds
    db.commit()

    auth = get_storage().playback(ep.hls_path)
    for name, value in auth.cookies.items():
        response.set_cookie(name, value, secure=True, httponly=True, samesite="none",
                            domain=settings.cdn_cookie_domain or None)
    return {"url": auth.url, "episode_id": str(ep.id), "episode_number": ep.episode_number,
            "series_slug": ep.series.slug, "resume_position": resume}
