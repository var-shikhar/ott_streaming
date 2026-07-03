import uuid
from datetime import datetime, timezone

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def utcnow():
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"
    id: Mapped[uuid.UUID] = mapped_column(sa.Uuid, primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(sa.String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(sa.String(255))
    name: Mapped[str] = mapped_column(sa.String(120))
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), default=utcnow)


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"
    id: Mapped[uuid.UUID] = mapped_column(sa.Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(sa.ForeignKey("users.id"), index=True)
    token_hash: Mapped[str] = mapped_column(sa.String(64), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True), nullable=True)


series_genres = sa.Table(
    "series_genres", Base.metadata,
    sa.Column("series_id", sa.ForeignKey("series.id"), primary_key=True),
    sa.Column("genre_id", sa.ForeignKey("genres.id"), primary_key=True),
)


class Genre(Base):
    __tablename__ = "genres"
    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(sa.String(50), unique=True)
    name: Mapped[str] = mapped_column(sa.String(50))


class Series(Base):
    __tablename__ = "series"
    id: Mapped[uuid.UUID] = mapped_column(sa.Uuid, primary_key=True, default=uuid.uuid4)
    slug: Mapped[str] = mapped_column(sa.String(120), unique=True, index=True)
    title: Mapped[str] = mapped_column(sa.String(255))
    synopsis: Mapped[str] = mapped_column(sa.Text, default="")
    language: Mapped[str] = mapped_column(sa.String(30), default="en")
    poster_url: Mapped[str] = mapped_column(sa.String(500), default="")
    banner_url: Mapped[str] = mapped_column(sa.String(500), default="")
    free_episode_count: Mapped[int] = mapped_column(default=3)
    is_featured: Mapped[bool] = mapped_column(default=False)
    status: Mapped[str] = mapped_column(sa.String(20), default="published")  # draft|published
    view_count: Mapped[int] = mapped_column(default=0)
    published_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), default=utcnow)

    genres: Mapped[list["Genre"]] = relationship(secondary=series_genres, lazy="selectin")
    episodes: Mapped[list["Episode"]] = relationship(
        back_populates="series", order_by="Episode.episode_number", lazy="selectin")


class Episode(Base):
    __tablename__ = "episodes"
    __table_args__ = (sa.UniqueConstraint("series_id", "episode_number"),)
    id: Mapped[uuid.UUID] = mapped_column(sa.Uuid, primary_key=True, default=uuid.uuid4)
    series_id: Mapped[uuid.UUID] = mapped_column(sa.ForeignKey("series.id"), index=True)
    episode_number: Mapped[int] = mapped_column()
    title: Mapped[str] = mapped_column(sa.String(255), default="")
    duration_seconds: Mapped[int] = mapped_column(default=0)
    hls_path: Mapped[str] = mapped_column(sa.String(500), default="")
    youtube_id: Mapped[str] = mapped_column(sa.String(20), default="")  # set => YouTube-embed source
    thumbnail_url: Mapped[str] = mapped_column(sa.String(500), default="")
    status: Mapped[str] = mapped_column(sa.String(20), default="processing")  # processing|ready|failed
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), default=utcnow)

    series: Mapped["Series"] = relationship(back_populates="episodes")


class Plan(Base):
    __tablename__ = "plans"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(sa.String(50))
    price_inr: Mapped[int] = mapped_column()  # paise
    interval: Mapped[str] = mapped_column(sa.String(10))  # weekly|monthly|yearly
    razorpay_plan_id: Mapped[str] = mapped_column(sa.String(64), default="")
    is_active: Mapped[bool] = mapped_column(default=True)


class Subscription(Base):
    __tablename__ = "subscriptions"
    id: Mapped[uuid.UUID] = mapped_column(sa.Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(sa.ForeignKey("users.id"), index=True)
    plan_id: Mapped[int] = mapped_column(sa.ForeignKey("plans.id"))
    razorpay_subscription_id: Mapped[str] = mapped_column(sa.String(64), unique=True, index=True)
    status: Mapped[str] = mapped_column(sa.String(20), default="created")
    # created|active|past_due|cancelled|expired
    current_period_start: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True), nullable=True)
    current_period_end: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), default=utcnow)

    plan: Mapped["Plan"] = relationship(lazy="selectin")


class WebhookEvent(Base):
    __tablename__ = "webhook_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    razorpay_event_id: Mapped[str] = mapped_column(sa.String(64), unique=True)
    event_type: Mapped[str] = mapped_column(sa.String(64))
    payload: Mapped[dict] = mapped_column(sa.JSON)
    processed_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), default=utcnow)


class WatchProgress(Base):
    __tablename__ = "watch_progress"
    user_id: Mapped[uuid.UUID] = mapped_column(sa.ForeignKey("users.id"), primary_key=True)
    episode_id: Mapped[uuid.UUID] = mapped_column(sa.ForeignKey("episodes.id"), primary_key=True)
    position_seconds: Mapped[int] = mapped_column(default=0)
    completed: Mapped[bool] = mapped_column(default=False)
    updated_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    episode: Mapped["Episode"] = relationship(lazy="selectin")


class EpisodeLike(Base):
    __tablename__ = "episode_likes"
    user_id: Mapped[uuid.UUID] = mapped_column(sa.ForeignKey("users.id"), primary_key=True)
    episode_id: Mapped[uuid.UUID] = mapped_column(sa.ForeignKey("episodes.id"), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), default=utcnow)


class Comment(Base):
    __tablename__ = "comments"
    id: Mapped[uuid.UUID] = mapped_column(sa.Uuid, primary_key=True, default=uuid.uuid4)
    episode_id: Mapped[uuid.UUID] = mapped_column(sa.ForeignKey("episodes.id"), index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(sa.ForeignKey("users.id"))
    body: Mapped[str] = mapped_column(sa.String(500))
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), default=utcnow)

    user: Mapped["User"] = relationship(lazy="selectin")


class WatchlistItem(Base):
    __tablename__ = "watchlist"
    user_id: Mapped[uuid.UUID] = mapped_column(sa.ForeignKey("users.id"), primary_key=True)
    series_id: Mapped[uuid.UUID] = mapped_column(sa.ForeignKey("series.id"), primary_key=True)
    added_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), default=utcnow)

    series: Mapped["Series"] = relationship(lazy="selectin")
