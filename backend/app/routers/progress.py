import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app import models
from app.db import get_db
from app.deps import get_current_user
from app.errors import ApiError
from app.routers.catalog import series_out

router = APIRouter(prefix="/api/v1/progress", tags=["progress"])


class ProgressIn(BaseModel):
    position_seconds: int = Field(ge=0)
    completed: bool = False


@router.put("/{episode_id}")
def upsert_progress(episode_id: uuid.UUID, body: ProgressIn,
                    db: Session = Depends(get_db), user=Depends(get_current_user)):
    ep = db.get(models.Episode, episode_id)
    if not ep:
        raise ApiError(404, "not_found", "Episode not found")
    row = db.get(models.WatchProgress, (user.id, episode_id))
    if row is None:
        row = models.WatchProgress(user_id=user.id, episode_id=episode_id)
        db.add(row)
    row.position_seconds = body.position_seconds
    row.completed = body.completed
    db.commit()
    return {"status": "ok"}


@router.get("/continue-watching")
def continue_watching(db: Session = Depends(get_db), user=Depends(get_current_user)):
    rows = (db.query(models.WatchProgress)
              .filter(models.WatchProgress.user_id == user.id,
                      models.WatchProgress.completed.is_(False))
              .order_by(models.WatchProgress.updated_at.desc()).limit(10).all())
    out = []
    for row in rows:
        ep = row.episode
        if ep.status == "ready" and ep.series.status == "published":
            out.append({"series": series_out(ep.series), "episode_number": ep.episode_number,
                        "episode_id": str(ep.id), "position_seconds": row.position_seconds})
    return out
