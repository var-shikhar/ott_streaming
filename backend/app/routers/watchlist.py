import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app import models
from app.db import get_db
from app.deps import get_current_user
from app.errors import ApiError
from app.routers.catalog import series_out

router = APIRouter(prefix="/api/v1/watchlist", tags=["watchlist"])


class WatchlistIn(BaseModel):
    series_id: uuid.UUID


@router.get("")
def list_watchlist(db: Session = Depends(get_db), user=Depends(get_current_user)):
    rows = (db.query(models.WatchlistItem).filter(models.WatchlistItem.user_id == user.id)
              .order_by(models.WatchlistItem.added_at.desc()).all())
    return [series_out(r.series) for r in rows if r.series.status == "published"]


@router.post("", status_code=201)
def add_to_watchlist(body: WatchlistIn, db: Session = Depends(get_db),
                     user=Depends(get_current_user)):
    if not db.get(models.Series, body.series_id):
        raise ApiError(404, "not_found", "Series not found")
    if db.get(models.WatchlistItem, (user.id, body.series_id)) is None:
        db.add(models.WatchlistItem(user_id=user.id, series_id=body.series_id))
        db.commit()
    return {"status": "ok"}


@router.delete("/{series_id}")
def remove_from_watchlist(series_id: uuid.UUID, db: Session = Depends(get_db),
                          user=Depends(get_current_user)):
    row = db.get(models.WatchlistItem, (user.id, series_id))
    if row:
        db.delete(row)
        db.commit()
    return {"status": "ok"}
