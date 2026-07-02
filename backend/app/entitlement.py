from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app import models


def active_subscription(db: Session, user: models.User | None) -> models.Subscription | None:
    if user is None:
        return None
    now = datetime.now(timezone.utc)
    subs = (db.query(models.Subscription)
              .filter(models.Subscription.user_id == user.id,
                      models.Subscription.status.in_(["active", "cancelled"]))
              .all())
    for sub in subs:
        end = sub.current_period_end
        if end is None:
            continue
        if end.tzinfo is None:
            end = end.replace(tzinfo=timezone.utc)
        if end > now:
            return sub
    return None


def can_watch(db: Session, user: models.User | None, episode: models.Episode) -> bool:
    if episode.episode_number <= episode.series.free_episode_count:
        return True
    return active_subscription(db, user) is not None
