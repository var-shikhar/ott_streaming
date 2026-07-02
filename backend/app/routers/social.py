import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from app import models
from app.db import get_db
from app.deps import get_current_user, get_optional_user
from app.errors import ApiError

router = APIRouter(prefix="/api/v1", tags=["social"])


def social_stats(db: Session, episode_ids: list[uuid.UUID],
                 user: models.User | None) -> dict[uuid.UUID, dict]:
    """like_count / comment_count / liked_by_me for a batch of episodes."""
    likes = dict(db.query(models.EpisodeLike.episode_id, func.count())
                   .filter(models.EpisodeLike.episode_id.in_(episode_ids))
                   .group_by(models.EpisodeLike.episode_id).all())
    comments = dict(db.query(models.Comment.episode_id, func.count())
                      .filter(models.Comment.episode_id.in_(episode_ids))
                      .group_by(models.Comment.episode_id).all())
    liked: set[uuid.UUID] = set()
    if user is not None:
        liked = {row.episode_id for row in
                 db.query(models.EpisodeLike)
                   .filter(models.EpisodeLike.user_id == user.id,
                           models.EpisodeLike.episode_id.in_(episode_ids)).all()}
    return {eid: {"like_count": likes.get(eid, 0),
                  "comment_count": comments.get(eid, 0),
                  "liked_by_me": eid in liked} for eid in episode_ids}


def _get_episode(db: Session, episode_id: uuid.UUID) -> models.Episode:
    ep = db.get(models.Episode, episode_id)
    if not ep or ep.status != "ready" or ep.series.status != "published":
        raise ApiError(404, "not_found", "Episode not found")
    return ep


def _like_state(db: Session, episode_id: uuid.UUID, user: models.User) -> dict:
    count = (db.query(func.count()).select_from(models.EpisodeLike)
               .filter(models.EpisodeLike.episode_id == episode_id).scalar())
    liked = db.get(models.EpisodeLike, (user.id, episode_id)) is not None
    return {"liked": liked, "like_count": count}


@router.post("/episodes/{episode_id}/like")
def like_episode(episode_id: uuid.UUID, db: Session = Depends(get_db),
                 user=Depends(get_current_user)):
    _get_episode(db, episode_id)
    if db.get(models.EpisodeLike, (user.id, episode_id)) is None:
        db.add(models.EpisodeLike(user_id=user.id, episode_id=episode_id))
        db.commit()
    return _like_state(db, episode_id, user)


@router.delete("/episodes/{episode_id}/like")
def unlike_episode(episode_id: uuid.UUID, db: Session = Depends(get_db),
                   user=Depends(get_current_user)):
    row = db.get(models.EpisodeLike, (user.id, episode_id))
    if row:
        db.delete(row)
        db.commit()
    return _like_state(db, episode_id, user)


class CommentIn(BaseModel):
    body: str = Field(min_length=1, max_length=500)


def comment_out(c: models.Comment, user: models.User | None) -> dict:
    return {"id": str(c.id), "body": c.body, "created_at": c.created_at.isoformat(),
            "user_name": c.user.name,
            "is_mine": user is not None and c.user_id == user.id}


@router.get("/episodes/{episode_id}/comments")
def list_comments(episode_id: uuid.UUID, db: Session = Depends(get_db),
                  user=Depends(get_optional_user)):
    _get_episode(db, episode_id)
    rows = (db.query(models.Comment).filter(models.Comment.episode_id == episode_id)
              .order_by(models.Comment.created_at.desc()).limit(100).all())
    return [comment_out(c, user) for c in rows]


@router.post("/episodes/{episode_id}/comments", status_code=201)
def add_comment(episode_id: uuid.UUID, body: CommentIn,
                db: Session = Depends(get_db), user=Depends(get_current_user)):
    _get_episode(db, episode_id)
    comment = models.Comment(episode_id=episode_id, user_id=user.id, body=body.body.strip())
    db.add(comment)
    db.commit()
    return comment_out(comment, user)


@router.delete("/comments/{comment_id}")
def delete_comment(comment_id: uuid.UUID, db: Session = Depends(get_db),
                   user=Depends(get_current_user)):
    row = db.get(models.Comment, comment_id)
    if not row:
        raise ApiError(404, "not_found", "Comment not found")
    if row.user_id != user.id:
        raise ApiError(403, "forbidden", "You can only delete your own comments")
    db.delete(row)
    db.commit()
    return {"status": "ok"}
