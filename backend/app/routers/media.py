import uuid
from pathlib import Path

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app import models
from app.config import settings
from app.db import get_db
from app.deps import get_optional_user
from app.entitlement import can_watch
from app.errors import ApiError

router = APIRouter(tags=["media"])


@router.get("/media/{episode_id}/{filename}")
def serve_media(episode_id: str, filename: str,
                db: Session = Depends(get_db), user=Depends(get_optional_user)):
    if "/" in filename or "\\" in filename or ".." in filename:
        raise ApiError(404, "not_found", "Not found")
    path = Path(settings.media_root) / episode_id / filename
    if settings.storage_mode != "local" or not path.is_file():
        raise ApiError(404, "not_found", "Not found")
    if filename == "master.m3u8":
        try:
            ep = db.get(models.Episode, uuid.UUID(episode_id))
        except ValueError:
            ep = None
        if not ep or not can_watch(db, user, ep):
            raise ApiError(403, "subscription_required", "Subscribe to watch this episode")
    if filename.endswith(".m3u8"):
        media_type = "application/vnd.apple.mpegurl"
    elif filename.endswith(".jpg"):
        media_type = "image/jpeg"
    else:
        media_type = "video/mp2t"
    return FileResponse(path, media_type=media_type)
