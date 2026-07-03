"""Wipe all CONTENT from the database — series, episodes, and everything hanging
off them (likes, comments, progress, watchlist, credits, stills). Keeps users,
plans, subscriptions, and webhook events.

Usage: python -m app.wipe_content --yes
"""
import sys

from sqlalchemy import delete

from app import models
from app.db import SessionLocal


def wipe() -> None:
    db = SessionLocal()
    try:
        counts = {}
        # FK-safe order: leaves first, series last
        for model in (models.Comment, models.EpisodeLike, models.WatchProgress,
                      models.WatchlistItem, models.Still, models.Credit,
                      models.Episode):
            counts[model.__tablename__] = db.execute(delete(model)).rowcount
        db.execute(models.series_genres.delete())
        counts["series"] = db.execute(delete(models.Series)).rowcount
        db.commit()
        for table, n in counts.items():
            print(f"deleted {n:>4}  {table}")
    finally:
        db.close()


if __name__ == "__main__":
    if "--yes" not in sys.argv:
        sys.exit("refusing to wipe without --yes (this deletes ALL content rows)")
    wipe()
