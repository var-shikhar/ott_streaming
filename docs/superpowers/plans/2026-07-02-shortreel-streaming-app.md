# ShortReel Streaming Platform Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a subscription-based short-drama streaming web app (vertical micro-drama episodes, first N free per series, rest behind a Razorpay subscription).

**Architecture:** Next.js (App Router) is a pure UI layer calling a FastAPI backend that owns auth (JWT in httpOnly cookies), catalog, entitlements, Razorpay billing, and an S3+FFmpeg+CloudFront HLS video pipeline with a local-disk dev mode. Neon Postgres via sync SQLAlchemy 2 + Alembic.

**Tech Stack:** Python 3.11+, FastAPI, SQLAlchemy 2 (sync), Alembic, psycopg, bcrypt, PyJWT, razorpay SDK, boto3, cryptography, FFmpeg; Next.js 15+, TypeScript, Tailwind, hls.js.

**Spec:** `docs/superpowers/specs/2026-07-02-short-drama-streaming-design.md`

## Global Constraints

- Python 3.11+; Node 20+; FFmpeg + ffprobe must be on PATH for ingest/seed (not needed for API tests).
- Backend serves at `http://localhost:8000`, frontend at `http://localhost:3000`. All API routes under `/api/v1`.
- DB defaults to `sqlite:///./dev.db` so everything runs with zero external services; Neon/S3/Razorpay/ImageKit plug in via `backend/.env`.
- Models use only cross-database column types (`sa.Uuid`, `sa.JSON`, no JSONB/ARRAY) — tests run on in-memory SQLite.
- Money is INR paise (integer). Timestamps are UTC (`datetime.now(timezone.utc)`).
- API errors always `{"error": {"code": "...", "message": "..."}}`. `401` unauthenticated, `403` + code `subscription_required` = paywall.
- Entitlement rule (single function, used everywhere): episode watchable iff `episode_number <= series.free_episode_count` OR user has a subscription with `status IN ('active','cancelled')` AND `now < current_period_end`.
- Auth cookies: `access_token` (15 min JWT) and `refresh_token` (30 days, sha256-hashed in DB), httpOnly, SameSite=Lax.
- Commit after every task. Backend tests: `cd backend && python -m pytest -q`. Frontend gate: `cd frontend && npm run build`.

## File Structure

```
backend/
├── requirements.txt, .env.example, alembic.ini
├── alembic/env.py, alembic/versions/
├── app/
│   ├── __init__.py, main.py, config.py, db.py, errors.py
│   ├── models.py, security.py, deps.py, entitlement.py
│   ├── billing_client.py            # razorpay client factory (mockable)
│   ├── routers/ (__init__.py, auth.py, catalog.py, playback.py,
│   │             progress.py, watchlist.py, billing.py, webhooks.py, media.py)
│   ├── storage/ (__init__.py, base.py, local.py, s3.py)
│   ├── transcode.py, ingest.py, seed.py
├── media/                            # local-mode HLS output (gitignored)
└── tests/ (conftest.py, test_health.py, test_auth.py, test_entitlement.py,
             test_catalog.py, test_progress_watchlist.py, test_billing.py,
             test_webhooks.py, test_playback.py, test_transcode.py)
frontend/
├── src/app/ (layout.tsx, page.tsx, globals.css,
│   login/page.tsx, signup/page.tsx, series/[slug]/page.tsx,
│   watch/[slug]/[ep]/page.tsx, plans/page.tsx, account/page.tsx,
│   my-list/page.tsx, search/page.tsx, genre/[slug]/page.tsx)
├── src/lib/ (types.ts, api-client.ts, api-server.ts)
├── src/components/ (Navbar.tsx, Hero.tsx, Rail.tsx, SeriesCard.tsx,
│   EpisodeGrid.tsx, Player.tsx, Paywall.tsx, PlanCards.tsx, AuthForm.tsx)
```

---

### Task 1: Backend scaffold + health endpoint

**Files:**
- Create: `.gitignore`, `backend/requirements.txt`, `backend/.env.example`, `backend/app/__init__.py`, `backend/app/config.py`, `backend/app/db.py`, `backend/app/errors.py`, `backend/app/main.py`, `backend/tests/conftest.py`
- Test: `backend/tests/test_health.py`

**Interfaces:**
- Produces: `app.config.settings` (Settings object), `app.db.Base` / `get_db()` / `engine`, `app.errors.ApiError(status_code, code, message)`, FastAPI `app.main.app` with error envelope handler, test fixtures `db`, `client`.

- [ ] **Step 1: Create `.gitignore` at repo root**

```gitignore
__pycache__/
*.pyc
.venv/
venv/
backend/.env
backend/dev.db
backend/media/
backend/.pytest_cache/
node_modules/
frontend/.next/
frontend/.env.local
.DS_Store
```

- [ ] **Step 2: Create `backend/requirements.txt`**

```
fastapi>=0.115
uvicorn[standard]>=0.30
sqlalchemy>=2.0
alembic>=1.13
psycopg[binary]>=3.2
pydantic-settings>=2.4
pydantic[email]>=2.8
bcrypt>=4.1
PyJWT>=2.9
razorpay>=1.4
boto3>=1.34
cryptography>=43
httpx>=0.27
pytest>=8.2
```

Then create the venv and install:

```bash
cd backend && python -m venv .venv && .venv/Scripts/pip install -r requirements.txt
```

- [ ] **Step 3: Create `backend/app/config.py`**

```python
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "sqlite:///./dev.db"
    direct_database_url: str = ""  # Neon direct URL for Alembic; falls back to database_url

    jwt_secret: str = "dev-secret-change-me"
    access_token_minutes: int = 15
    refresh_token_days: int = 30
    cookie_secure: bool = False

    frontend_origin: str = "http://localhost:3000"
    api_base_url: str = "http://localhost:8000"

    storage_mode: str = "local"  # "local" | "s3"
    media_root: str = "media"
    aws_region: str = "ap-south-1"
    s3_bucket: str = ""
    cloudfront_domain: str = ""
    cloudfront_key_pair_id: str = ""
    cloudfront_private_key_path: str = ""
    cdn_cookie_domain: str = ""  # e.g. ".example.com" so API-set cookies reach the CDN

    imagekit_public_key: str = ""
    imagekit_private_key: str = ""
    imagekit_url_endpoint: str = ""

    razorpay_key_id: str = "rzp_test_dummy"
    razorpay_key_secret: str = "dummy"
    razorpay_webhook_secret: str = "whsec_dummy"

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
```

- [ ] **Step 4: Create `backend/.env.example`** (same keys as Settings, all commented with hints; DATABASE_URL example shows Neon pooled URL `postgresql+psycopg://user:pass@ep-xxx-pooler.region.aws.neon.tech/dbname?sslmode=require` and DIRECT_DATABASE_URL the non-pooler host)

- [ ] **Step 5: Create `backend/app/db.py`**

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings


class Base(DeclarativeBase):
    pass


connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, pool_pre_ping=True, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

- [ ] **Step 6: Create `backend/app/errors.py`**

```python
from fastapi import HTTPException


class ApiError(HTTPException):
    def __init__(self, status_code: int, code: str, message: str):
        super().__init__(status_code=status_code, detail={"code": code, "message": message})
```

- [ ] **Step 7: Create `backend/app/main.py`**

```python
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings

app = FastAPI(title="ShortReel API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    detail = exc.detail if isinstance(exc.detail, dict) else {"code": "error", "message": str(exc.detail)}
    return JSONResponse(status_code=exc.status_code, content={"error": detail}, headers=exc.headers)


@app.get("/health")
def health():
    return {"status": "ok"}
```

- [ ] **Step 8: Create `backend/tests/conftest.py`**

```python
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base, get_db
from app.main import app

engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
TestingSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


@pytest.fixture()
def db():
    Base.metadata.create_all(engine)
    session = TestingSession()
    yield session
    session.close()
    Base.metadata.drop_all(engine)


@pytest.fixture()
def client(db):
    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
```

- [ ] **Step 9: Write failing test `backend/tests/test_health.py`**

```python
def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}
```

- [ ] **Step 10: Run tests**

Run: `cd backend && .venv/Scripts/python -m pytest -q`
Expected: 1 passed (empty `backend/app/__init__.py` and `backend/tests/__init__.py` may be needed; create both empty).

- [ ] **Step 11: Commit**

```bash
git add -A && git commit -m "feat(backend): scaffold FastAPI app with config, db, error envelope, health check"
```

---

### Task 2: Data models + Alembic

**Files:**
- Create: `backend/app/models.py`, `backend/alembic.ini`, `backend/alembic/env.py`, `backend/alembic/script.py.mako`, first migration under `backend/alembic/versions/`
- Test: `backend/tests/test_models.py`

**Interfaces:**
- Produces: SQLAlchemy models `User, RefreshToken, Genre, Series, Episode, Plan, Subscription, WebhookEvent, WatchProgress, WatchlistItem` importable from `app.models`, with relationships `Series.episodes`, `Series.genres`, `Episode.series`.

- [ ] **Step 1: Write failing test `backend/tests/test_models.py`**

```python
import uuid

from app import models


def test_series_episode_roundtrip(db):
    s = models.Series(slug="test-show", title="Test Show", synopsis="x", language="en",
                      poster_url="p", banner_url="b", free_episode_count=2)
    db.add(s)
    db.flush()
    e = models.Episode(series_id=s.id, episode_number=1, title="Ep 1", duration_seconds=60,
                       hls_path="x/master.m3u8", status="ready")
    db.add(e)
    db.commit()
    assert isinstance(s.id, uuid.UUID)
    assert db.query(models.Episode).one().series.slug == "test-show"
```

- [ ] **Step 2: Run to verify it fails** — `ModuleNotFoundError: app.models` / attribute errors.

- [ ] **Step 3: Create `backend/app/models.py`**

```python
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


class WatchlistItem(Base):
    __tablename__ = "watchlist"
    user_id: Mapped[uuid.UUID] = mapped_column(sa.ForeignKey("users.id"), primary_key=True)
    series_id: Mapped[uuid.UUID] = mapped_column(sa.ForeignKey("series.id"), primary_key=True)
    added_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), default=utcnow)

    series: Mapped["Series"] = relationship(lazy="selectin")
```

- [ ] **Step 4: Run tests** — `pytest -q` → all pass.

- [ ] **Step 5: Initialize Alembic**

```bash
cd backend && .venv/Scripts/alembic init alembic
```

Edit `backend/alembic/env.py`: after imports add

```python
from app.config import settings
from app.db import Base
from app import models  # noqa: F401  (register tables)

config.set_main_option("sqlalchemy.url", settings.direct_database_url or settings.database_url)
target_metadata = Base.metadata
```

(replace the default `target_metadata = None`; leave `alembic.ini`'s `sqlalchemy.url` blank).

- [ ] **Step 6: Generate + apply initial migration**

```bash
cd backend && .venv/Scripts/alembic revision --autogenerate -m "initial schema" && .venv/Scripts/alembic upgrade head
```

Expected: migration file created; `dev.db` gets all tables. (Against Neon later: set `DIRECT_DATABASE_URL` and rerun `alembic upgrade head`.)

- [ ] **Step 7: Commit**

```bash
git add -A && git commit -m "feat(backend): data models and initial Alembic migration"
```

---

### Task 3: Security utils + auth endpoints

**Files:**
- Create: `backend/app/security.py`, `backend/app/deps.py`, `backend/app/routers/__init__.py`, `backend/app/routers/auth.py`
- Modify: `backend/app/main.py` (include router)
- Test: `backend/tests/test_auth.py`

**Interfaces:**
- Consumes: `models.User`, `models.RefreshToken`, `get_db`, `ApiError`, `settings`.
- Produces:
  - `security.hash_password(p: str) -> str`, `security.verify_password(p: str, h: str) -> bool`
  - `security.create_access_token(user_id: str) -> str`, `security.decode_access_token(token: str) -> str | None`
  - `security.new_refresh_token() -> tuple[str, str]` (raw, sha256 hash), `security.hash_refresh(raw: str) -> str`
  - `deps.get_current_user` (FastAPI dependency -> `User`, raises 401), `deps.get_optional_user` (-> `User | None`)
  - Endpoints: `POST /api/v1/auth/signup`, `POST /api/v1/auth/login`, `POST /api/v1/auth/refresh`, `POST /api/v1/auth/logout`, `GET /api/v1/auth/me`; login/signup set both cookies.

- [ ] **Step 1: Write failing tests `backend/tests/test_auth.py`**

```python
def signup(client, email="a@b.com", password="password1", name="A"):
    return client.post("/api/v1/auth/signup", json={"email": email, "password": password, "name": name})


def test_signup_sets_cookies_and_me(client):
    r = signup(client)
    assert r.status_code == 201
    assert "access_token" in r.cookies and "refresh_token" in r.cookies
    me = client.get("/api/v1/auth/me")
    assert me.status_code == 200 and me.json()["email"] == "a@b.com"


def test_signup_duplicate_email(client):
    signup(client)
    r = signup(client)
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "email_taken"


def test_login_wrong_password(client):
    signup(client)
    r = client.post("/api/v1/auth/login", json={"email": "a@b.com", "password": "wrong-pass"})
    assert r.status_code == 401


def test_me_unauthenticated(client):
    assert client.get("/api/v1/auth/me").status_code == 401


def test_refresh_rotates_token(client):
    signup(client)
    old_refresh = client.cookies["refresh_token"]
    r = client.post("/api/v1/auth/refresh")
    assert r.status_code == 200
    assert client.cookies["refresh_token"] != old_refresh
    client.cookies.set("refresh_token", old_refresh)
    assert client.post("/api/v1/auth/refresh").status_code == 401


def test_logout_clears_session(client):
    signup(client)
    assert client.post("/api/v1/auth/logout").status_code == 200
    client.cookies.delete("access_token")
    assert client.get("/api/v1/auth/me").status_code == 401
```

- [ ] **Step 2: Run to verify failure** — 404s (router missing).

- [ ] **Step 3: Create `backend/app/security.py`**

```python
import hashlib
import secrets
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from app.config import settings


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode(), password_hash.encode())


def create_access_token(user_id: str) -> str:
    payload = {
        "sub": user_id,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def decode_access_token(token: str) -> str | None:
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])["sub"]
    except jwt.PyJWTError:
        return None


def hash_refresh(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def new_refresh_token() -> tuple[str, str]:
    raw = secrets.token_urlsafe(48)
    return raw, hash_refresh(raw)
```

- [ ] **Step 4: Create `backend/app/deps.py`**

```python
import uuid

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app import models
from app.db import get_db
from app.errors import ApiError
from app.security import decode_access_token


def _user_from_request(request: Request, db: Session) -> models.User | None:
    token = request.cookies.get("access_token")
    if not token:
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            token = auth.removeprefix("Bearer ")
    if not token:
        return None
    user_id = decode_access_token(token)
    if not user_id:
        return None
    try:
        return db.get(models.User, uuid.UUID(user_id))
    except ValueError:
        return None


def get_optional_user(request: Request, db: Session = Depends(get_db)) -> models.User | None:
    return _user_from_request(request, db)


def get_current_user(request: Request, db: Session = Depends(get_db)) -> models.User:
    user = _user_from_request(request, db)
    if user is None:
        raise ApiError(401, "unauthenticated", "Login required")
    return user
```

- [ ] **Step 5: Create `backend/app/routers/__init__.py`** (empty) **and `backend/app/routers/auth.py`**

```python
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from app import models
from app.config import settings
from app.db import get_db
from app.deps import get_current_user
from app.errors import ApiError
from app.security import (create_access_token, hash_password, hash_refresh,
                          new_refresh_token, verify_password)

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


class SignupIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    name: str = Field(min_length=1, max_length=120)


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: str
    email: str
    name: str


def _user_out(user: models.User) -> UserOut:
    return UserOut(id=str(user.id), email=user.email, name=user.name)


def _issue_session(response: Response, db: Session, user: models.User) -> None:
    raw, token_hash = new_refresh_token()
    db.add(models.RefreshToken(
        user_id=user.id, token_hash=token_hash,
        expires_at=datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_days)))
    db.commit()
    common = dict(httponly=True, samesite="lax", secure=settings.cookie_secure)
    response.set_cookie("access_token", create_access_token(str(user.id)),
                        max_age=settings.access_token_minutes * 60, **common)
    response.set_cookie("refresh_token", raw,
                        max_age=settings.refresh_token_days * 86400, **common)


@router.post("/signup", status_code=201)
def signup(body: SignupIn, response: Response, db: Session = Depends(get_db)) -> UserOut:
    if db.query(models.User).filter(models.User.email == body.email.lower()).first():
        raise ApiError(409, "email_taken", "An account with this email already exists")
    user = models.User(email=body.email.lower(), password_hash=hash_password(body.password), name=body.name)
    db.add(user)
    db.commit()
    _issue_session(response, db, user)
    return _user_out(user)


@router.post("/login")
def login(body: LoginIn, response: Response, db: Session = Depends(get_db)) -> UserOut:
    user = db.query(models.User).filter(models.User.email == body.email.lower()).first()
    if not user or not verify_password(body.password, user.password_hash):
        raise ApiError(401, "invalid_credentials", "Invalid email or password")
    _issue_session(response, db, user)
    return _user_out(user)


@router.post("/refresh")
def refresh(request: Request, response: Response, db: Session = Depends(get_db)) -> UserOut:
    raw = request.cookies.get("refresh_token")
    if not raw:
        raise ApiError(401, "unauthenticated", "Missing refresh token")
    row = db.query(models.RefreshToken).filter(models.RefreshToken.token_hash == hash_refresh(raw)).first()
    now = datetime.now(timezone.utc)
    expired = row is not None and (row.expires_at.tzinfo and row.expires_at < now
                                   or row.expires_at.tzinfo is None and row.expires_at.replace(tzinfo=timezone.utc) < now)
    if not row or row.revoked_at is not None or expired:
        raise ApiError(401, "invalid_refresh", "Session expired, please log in again")
    row.revoked_at = now
    user = db.get(models.User, row.user_id)
    _issue_session(response, db, user)
    return _user_out(user)


@router.post("/logout")
def logout(request: Request, response: Response, db: Session = Depends(get_db)):
    raw = request.cookies.get("refresh_token")
    if raw:
        row = db.query(models.RefreshToken).filter(models.RefreshToken.token_hash == hash_refresh(raw)).first()
        if row:
            row.revoked_at = datetime.now(timezone.utc)
            db.commit()
    response.delete_cookie("access_token")
    response.delete_cookie("refresh_token")
    return {"status": "ok"}


@router.get("/me")
def me(user: models.User = Depends(get_current_user)) -> UserOut:
    return _user_out(user)
```

- [ ] **Step 6: Register router in `backend/app/main.py`** — after the middleware setup add:

```python
from app.routers import auth as auth_router

app.include_router(auth_router.router)
```

- [ ] **Step 7: Run tests** — `pytest -q` → all pass.

- [ ] **Step 8: Commit**

```bash
git add -A && git commit -m "feat(backend): email/password auth with JWT access + rotating refresh tokens"
```

---

### Task 4: Entitlement rule

**Files:**
- Create: `backend/app/entitlement.py`
- Test: `backend/tests/test_entitlement.py`

**Interfaces:**
- Consumes: models.
- Produces:
  - `entitlement.active_subscription(db, user) -> models.Subscription | None` — subscription with `status in ('active','cancelled')` and `current_period_end > now`.
  - `entitlement.can_watch(db, user: models.User | None, episode: models.Episode) -> bool`

- [ ] **Step 1: Write failing tests `backend/tests/test_entitlement.py`**

```python
import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app import models
from app.entitlement import can_watch


def make_series(db, free=2):
    s = models.Series(slug=f"s-{uuid.uuid4().hex[:6]}", title="S", free_episode_count=free)
    db.add(s)
    db.flush()
    eps = []
    for n in (1, 2, 3):
        e = models.Episode(series_id=s.id, episode_number=n, status="ready")
        db.add(e)
        eps.append(e)
    db.commit()
    return s, eps


def make_user(db):
    u = models.User(email=f"{uuid.uuid4().hex[:8]}@t.co", password_hash="x", name="U")
    db.add(u)
    db.commit()
    return u


def make_sub(db, user, status, ends_in_days):
    p = models.Plan(name="M", price_inr=14900, interval="monthly")
    db.add(p)
    db.flush()
    sub = models.Subscription(
        user_id=user.id, plan_id=p.id, razorpay_subscription_id=f"sub_{uuid.uuid4().hex[:8]}",
        status=status, current_period_end=datetime.now(timezone.utc) + timedelta(days=ends_in_days))
    db.add(sub)
    db.commit()
    return sub


def test_free_episode_watchable_by_guest(db):
    _, eps = make_series(db, free=2)
    assert can_watch(db, None, eps[0]) is True
    assert can_watch(db, None, eps[1]) is True


def test_locked_episode_blocked_for_guest_and_unsubscribed(db):
    _, eps = make_series(db, free=2)
    assert can_watch(db, None, eps[2]) is False
    assert can_watch(db, make_user(db), eps[2]) is False


@pytest.mark.parametrize("status,days,expected", [
    ("active", 10, True),
    ("cancelled", 10, True),
    ("active", -1, False),
    ("expired", 10, False),
    ("created", 10, False),
    ("past_due", 10, False),
])
def test_subscription_states(db, status, days, expected):
    _, eps = make_series(db, free=2)
    u = make_user(db)
    make_sub(db, u, status, days)
    assert can_watch(db, u, eps[2]) is expected
```

- [ ] **Step 2: Run to verify failure** — import error.

- [ ] **Step 3: Create `backend/app/entitlement.py`**

```python
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
```

- [ ] **Step 4: Run tests** — all pass.

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat(backend): entitlement rule (free gate + active/cancelled-in-period subscription)"
```

---

### Task 5: Catalog endpoints

**Files:**
- Create: `backend/app/routers/catalog.py`
- Modify: `backend/app/main.py` (include router)
- Test: `backend/tests/test_catalog.py`

**Interfaces:**
- Consumes: models, `get_db`, `get_optional_user`, `entitlement.active_subscription`.
- Produces endpoints (public; only `status='published'` series and `status='ready'` episodes are exposed):
  - `GET /api/v1/home` → `{featured: SeriesOut[], trending: SeriesOut[], new_releases: SeriesOut[], genre_rails: [{genre: GenreOut, series: SeriesOut[]}], continue_watching: ContinueOut[]}`
  - `GET /api/v1/series` → `SeriesOut[]`; `GET /api/v1/series/{slug}` → `SeriesDetailOut` (adds `episodes: EpisodeOut[]`)
  - `GET /api/v1/genres` → `GenreOut[]`; `GET /api/v1/genres/{slug}/series` → `{genre, series}`
  - `GET /api/v1/search?q=` → `SeriesOut[]`
- Shapes: `SeriesOut {id, slug, title, synopsis, language, poster_url, banner_url, free_episode_count, is_featured, view_count, genres: [str], episode_count: int}`; `EpisodeOut {id, episode_number, title, duration_seconds, thumbnail_url, is_free: bool, locked: bool}`; `GenreOut {slug, name}`; `ContinueOut {series: SeriesOut, episode_number: int, episode_id: str, position_seconds: int}`
- Also exports helpers `series_out(s) -> dict` and `ready_episodes(s) -> list[Episode]` reused by progress/watchlist routers.

- [ ] **Step 1: Write failing tests `backend/tests/test_catalog.py`**

```python
from app import models


def seed_catalog(db):
    g = models.Genre(slug="romance", name="Romance")
    db.add(g)
    s1 = models.Series(slug="ceo-bride", title="CEO's Secret Bride", is_featured=True,
                       view_count=100, free_episode_count=2, genres=[g])
    s2 = models.Series(slug="draft-show", title="Hidden", status="draft")
    db.add_all([s1, s2])
    db.flush()
    for n in (1, 2, 3):
        db.add(models.Episode(series_id=s1.id, episode_number=n, status="ready", title=f"Ep {n}"))
    db.add(models.Episode(series_id=s1.id, episode_number=4, status="processing"))
    db.commit()
    return s1


def test_home_shape(client, db):
    seed_catalog(db)
    r = client.get("/api/v1/home")
    assert r.status_code == 200
    body = r.json()
    assert body["featured"][0]["slug"] == "ceo-bride"
    assert body["trending"][0]["episode_count"] == 3  # processing episode excluded
    assert body["genre_rails"][0]["genre"]["slug"] == "romance"
    assert body["continue_watching"] == []
    slugs = [s["slug"] for s in body["new_releases"]]
    assert "draft-show" not in slugs


def test_series_detail_lock_flags_for_guest(client, db):
    seed_catalog(db)
    r = client.get("/api/v1/series/ceo-bride")
    assert r.status_code == 200
    eps = r.json()["episodes"]
    assert [e["locked"] for e in eps] == [False, False, True]
    assert [e["is_free"] for e in eps] == [True, True, False]


def test_series_404(client):
    assert client.get("/api/v1/series/nope").status_code == 404


def test_search(client, db):
    seed_catalog(db)
    assert client.get("/api/v1/search", params={"q": "ceo"}).json()[0]["slug"] == "ceo-bride"
    assert client.get("/api/v1/search", params={"q": "zzz"}).json() == []


def test_genre_listing(client, db):
    seed_catalog(db)
    r = client.get("/api/v1/genres/romance/series")
    assert r.json()["series"][0]["slug"] == "ceo-bride"
```

- [ ] **Step 2: Run to verify failure** — 404s.

- [ ] **Step 3: Create `backend/app/routers/catalog.py`**

```python
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app import models
from app.db import get_db
from app.deps import get_optional_user
from app.entitlement import active_subscription
from app.errors import ApiError

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
    out["episodes"] = [{
        "id": str(e.id), "episode_number": e.episode_number, "title": e.title,
        "duration_seconds": e.duration_seconds, "thumbnail_url": e.thumbnail_url,
        "is_free": e.episode_number <= s.free_episode_count,
        "locked": e.episode_number > s.free_episode_count and not subscribed,
    } for e in ready_episodes(s)]
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
```

- [ ] **Step 4: Register in `main.py`** (`from app.routers import catalog as catalog_router` / `app.include_router(catalog_router.router)`).

- [ ] **Step 5: Run tests** — all pass.

- [ ] **Step 6: Commit**

```bash
git add -A && git commit -m "feat(backend): catalog endpoints (home, series, genres, search)"
```

---

### Task 6: Watch progress + watchlist endpoints

**Files:**
- Create: `backend/app/routers/progress.py`, `backend/app/routers/watchlist.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_progress_watchlist.py`

**Interfaces:**
- Consumes: `get_current_user`, models, `catalog.series_out`.
- Produces:
  - `PUT /api/v1/progress/{episode_id}` body `{position_seconds: int, completed: bool}` (auth) — upsert
  - `GET /api/v1/progress/continue-watching` (auth) → `ContinueOut[]` (same shape as home rail)
  - `GET /api/v1/watchlist` (auth) → `SeriesOut[]`; `POST /api/v1/watchlist` body `{series_id}` (201, idempotent); `DELETE /api/v1/watchlist/{series_id}` (200)

- [ ] **Step 1: Write failing tests `backend/tests/test_progress_watchlist.py`**

```python
from tests.test_catalog import seed_catalog


def login(client):
    client.post("/api/v1/auth/signup", json={"email": "u@t.co", "password": "password1", "name": "U"})


def test_progress_upsert_and_continue(client, db):
    s = seed_catalog(db)
    ep = s.episodes[0]
    login(client)
    r = client.put(f"/api/v1/progress/{ep.id}", json={"position_seconds": 42, "completed": False})
    assert r.status_code == 200
    client.put(f"/api/v1/progress/{ep.id}", json={"position_seconds": 55, "completed": False})
    cw = client.get("/api/v1/progress/continue-watching").json()
    assert cw[0]["position_seconds"] == 55 and cw[0]["episode_number"] == 1


def test_progress_requires_auth(client, db):
    s = seed_catalog(db)
    r = client.put(f"/api/v1/progress/{s.episodes[0].id}",
                   json={"position_seconds": 1, "completed": False})
    assert r.status_code == 401


def test_watchlist_crud(client, db):
    s = seed_catalog(db)
    login(client)
    assert client.post("/api/v1/watchlist", json={"series_id": str(s.id)}).status_code == 201
    assert client.post("/api/v1/watchlist", json={"series_id": str(s.id)}).status_code == 201
    assert [x["slug"] for x in client.get("/api/v1/watchlist").json()] == ["ceo-bride"]
    assert client.delete(f"/api/v1/watchlist/{s.id}").status_code == 200
    assert client.get("/api/v1/watchlist").json() == []
```

- [ ] **Step 2: Run to verify failure.**

- [ ] **Step 3: Create `backend/app/routers/progress.py`**

```python
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
```

- [ ] **Step 4: Create `backend/app/routers/watchlist.py`**

```python
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
```

- [ ] **Step 5: Register both routers in `main.py`; run tests** — all pass.

- [ ] **Step 6: Commit**

```bash
git add -A && git commit -m "feat(backend): watch progress and watchlist endpoints"
```

---

### Task 7: Billing — plans + subscription lifecycle (Razorpay client mocked in tests)

**Files:**
- Create: `backend/app/billing_client.py`, `backend/app/routers/billing.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_billing.py`

**Interfaces:**
- Consumes: models, `get_current_user`, `entitlement.active_subscription`, `settings`.
- Produces:
  - `billing_client.get_razorpay_client()` — returns `razorpay.Client`; tests monkeypatch `app.routers.billing.get_razorpay_client`.
  - `GET /api/v1/plans` → `[{id, name, price_inr, interval}]`
  - `POST /api/v1/subscriptions` body `{plan_id: int}` (auth) → 201 `{razorpay_subscription_id, razorpay_key_id}`; 409 `already_subscribed` if entitled already
  - `POST /api/v1/subscriptions/cancel` (auth) → cancels at cycle end via Razorpay
  - `GET /api/v1/subscriptions/current` (auth) → `{status, plan: {id,name,price_inr,interval}, current_period_end} | null`

- [ ] **Step 1: Write failing tests `backend/tests/test_billing.py`**

```python
from datetime import datetime, timedelta, timezone

import pytest

from app import models


class FakeSubAPI:
    def __init__(self):
        self.created, self.cancelled = [], []

    def create(self, data):
        self.created.append(data)
        return {"id": f"sub_fake{len(self.created)}", "status": "created"}

    def cancel(self, sub_id, data=None):
        self.cancelled.append(sub_id)
        return {"id": sub_id, "status": "cancelled"}


class FakeClient:
    def __init__(self):
        self.subscription = FakeSubAPI()


@pytest.fixture()
def fake_rzp(monkeypatch):
    fake = FakeClient()
    monkeypatch.setattr("app.routers.billing.get_razorpay_client", lambda: fake)
    return fake


def login(client):
    client.post("/api/v1/auth/signup", json={"email": "u@t.co", "password": "password1", "name": "U"})


def make_plan(db):
    p = models.Plan(name="Monthly", price_inr=14900, interval="monthly", razorpay_plan_id="plan_x")
    db.add(p)
    db.commit()
    return p


def test_list_plans(client, db):
    make_plan(db)
    body = client.get("/api/v1/plans").json()
    assert body[0]["name"] == "Monthly" and body[0]["price_inr"] == 14900


def test_create_subscription(client, db, fake_rzp):
    p = make_plan(db)
    login(client)
    r = client.post("/api/v1/subscriptions", json={"plan_id": p.id})
    assert r.status_code == 201
    assert r.json()["razorpay_subscription_id"] == "sub_fake1"
    assert fake_rzp.subscription.created[0]["plan_id"] == "plan_x"
    row = db.query(models.Subscription).one()
    assert row.status == "created"


def test_create_requires_auth(client, db, fake_rzp):
    p = make_plan(db)
    assert client.post("/api/v1/subscriptions", json={"plan_id": p.id}).status_code == 401


def test_already_subscribed_conflict(client, db, fake_rzp):
    p = make_plan(db)
    login(client)
    u = db.query(models.User).one()
    db.add(models.Subscription(user_id=u.id, plan_id=p.id, razorpay_subscription_id="sub_live",
                               status="active",
                               current_period_end=datetime.now(timezone.utc) + timedelta(days=5)))
    db.commit()
    r = client.post("/api/v1/subscriptions", json={"plan_id": p.id})
    assert r.status_code == 409 and r.json()["error"]["code"] == "already_subscribed"


def test_cancel_and_current(client, db, fake_rzp):
    p = make_plan(db)
    login(client)
    u = db.query(models.User).one()
    db.add(models.Subscription(user_id=u.id, plan_id=p.id, razorpay_subscription_id="sub_live",
                               status="active",
                               current_period_end=datetime.now(timezone.utc) + timedelta(days=5)))
    db.commit()
    cur = client.get("/api/v1/subscriptions/current").json()
    assert cur["status"] == "active" and cur["plan"]["name"] == "Monthly"
    assert client.post("/api/v1/subscriptions/cancel").status_code == 200
    assert fake_rzp.subscription.cancelled == ["sub_live"]


def test_current_none(client, db):
    login(client)
    assert client.get("/api/v1/subscriptions/current").json() is None
```

- [ ] **Step 2: Run to verify failure.**

- [ ] **Step 3: Create `backend/app/billing_client.py`**

```python
import razorpay

from app.config import settings


def get_razorpay_client() -> razorpay.Client:
    return razorpay.Client(auth=(settings.razorpay_key_id, settings.razorpay_key_secret))
```

- [ ] **Step 4: Create `backend/app/routers/billing.py`**

```python
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app import models
from app.billing_client import get_razorpay_client
from app.config import settings
from app.db import get_db
from app.deps import get_current_user
from app.entitlement import active_subscription
from app.errors import ApiError

router = APIRouter(prefix="/api/v1", tags=["billing"])


class SubscribeIn(BaseModel):
    plan_id: int


def sub_out(sub: models.Subscription) -> dict:
    return {
        "status": sub.status,
        "plan": {"id": sub.plan.id, "name": sub.plan.name,
                 "price_inr": sub.plan.price_inr, "interval": sub.plan.interval},
        "current_period_end": sub.current_period_end.isoformat() if sub.current_period_end else None,
    }


@router.get("/plans")
def list_plans(db: Session = Depends(get_db)):
    rows = (db.query(models.Plan).filter(models.Plan.is_active.is_(True))
              .order_by(models.Plan.price_inr).all())
    return [{"id": p.id, "name": p.name, "price_inr": p.price_inr, "interval": p.interval}
            for p in rows]


@router.post("/subscriptions", status_code=201)
def create_subscription(body: SubscribeIn, db: Session = Depends(get_db),
                        user=Depends(get_current_user)):
    plan = db.get(models.Plan, body.plan_id)
    if not plan or not plan.is_active:
        raise ApiError(404, "not_found", "Plan not found")
    if active_subscription(db, user) is not None:
        raise ApiError(409, "already_subscribed", "You already have an active subscription")
    total_count = {"weekly": 52, "monthly": 12, "yearly": 5}.get(plan.interval, 12)
    rzp = get_razorpay_client().subscription.create({
        "plan_id": plan.razorpay_plan_id, "total_count": total_count, "customer_notify": 1,
        "notes": {"user_id": str(user.id)},
    })
    db.add(models.Subscription(user_id=user.id, plan_id=plan.id,
                               razorpay_subscription_id=rzp["id"], status="created"))
    db.commit()
    return {"razorpay_subscription_id": rzp["id"], "razorpay_key_id": settings.razorpay_key_id}


@router.post("/subscriptions/cancel")
def cancel_subscription(db: Session = Depends(get_db), user=Depends(get_current_user)):
    sub = active_subscription(db, user)
    if sub is None:
        raise ApiError(404, "no_subscription", "No active subscription to cancel")
    get_razorpay_client().subscription.cancel(sub.razorpay_subscription_id,
                                              {"cancel_at_cycle_end": 1})
    return {"status": "ok", "message": "Subscription will end at the current period"}


@router.get("/subscriptions/current")
def current_subscription(db: Session = Depends(get_db), user=Depends(get_current_user)):
    sub = active_subscription(db, user)
    return sub_out(sub) if sub else None
```

- [ ] **Step 5: Register router in `main.py`; run tests** — all pass.

- [ ] **Step 6: Commit**

```bash
git add -A && git commit -m "feat(backend): plans and Razorpay subscription create/cancel/current"
```

---

### Task 8: Razorpay webhook handler

**Files:**
- Create: `backend/app/routers/webhooks.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_webhooks.py`

**Interfaces:**
- Consumes: models, `settings.razorpay_webhook_secret`.
- Produces: `POST /api/v1/webhooks/razorpay` — verifies `X-Razorpay-Signature` (HMAC-SHA256 hex of raw body), idempotent on `X-Razorpay-Event-Id`, updates `Subscription.status` / period:
  - `subscription.activated`, `subscription.charged` → `active` + period from entity `current_start`/`current_end` (unix ts)
  - `subscription.cancelled` → `cancelled` (period end kept); `subscription.completed`, `subscription.expired` → `expired`; `subscription.pending` → `past_due`

- [ ] **Step 1: Write failing tests `backend/tests/test_webhooks.py`**

```python
import hashlib
import hmac
import json
import time
import uuid

from app import models
from app.config import settings


def make_sub(db, status="created"):
    u = models.User(email=f"{uuid.uuid4().hex[:8]}@t.co", password_hash="x", name="U")
    p = models.Plan(name="M", price_inr=14900, interval="monthly", razorpay_plan_id="plan_x")
    db.add_all([u, p])
    db.flush()
    sub = models.Subscription(user_id=u.id, plan_id=p.id,
                              razorpay_subscription_id="sub_live", status=status)
    db.add(sub)
    db.commit()
    return sub


def send(client, event_type, sub_id="sub_live", event_id=None, sig=None):
    now = int(time.time())
    payload = {"event": event_type, "payload": {"subscription": {"entity": {
        "id": sub_id, "current_start": now, "current_end": now + 30 * 86400}}}}
    body = json.dumps(payload).encode()
    signature = sig or hmac.new(settings.razorpay_webhook_secret.encode(), body,
                                hashlib.sha256).hexdigest()
    return client.post("/api/v1/webhooks/razorpay", content=body, headers={
        "X-Razorpay-Signature": signature,
        "X-Razorpay-Event-Id": event_id or f"evt_{uuid.uuid4().hex[:10]}",
        "Content-Type": "application/json",
    })


def test_bad_signature_rejected(client, db):
    make_sub(db)
    assert send(client, "subscription.activated", sig="deadbeef").status_code == 400


def test_activated_sets_active_and_period(client, db):
    sub = make_sub(db)
    assert send(client, "subscription.activated").status_code == 200
    db.refresh(sub)
    assert sub.status == "active" and sub.current_period_end is not None


def test_duplicate_event_ignored(client, db):
    sub = make_sub(db)
    assert send(client, "subscription.activated", event_id="evt_dup").status_code == 200
    sub.status = "created"
    db.commit()
    r = send(client, "subscription.activated", event_id="evt_dup")
    assert r.status_code == 200 and r.json()["status"] == "duplicate"
    db.refresh(sub)
    assert sub.status == "created"  # not reprocessed


def test_cancelled_and_expired(client, db):
    sub = make_sub(db, status="active")
    send(client, "subscription.cancelled")
    db.refresh(sub)
    assert sub.status == "cancelled"
    send(client, "subscription.completed")
    db.refresh(sub)
    assert sub.status == "expired"


def test_unknown_subscription_is_noop(client, db):
    assert send(client, "subscription.activated", sub_id="sub_ghost").status_code == 200
```

- [ ] **Step 2: Run to verify failure.**

- [ ] **Step 3: Create `backend/app/routers/webhooks.py`**

```python
import hashlib
import hmac
import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import models
from app.config import settings
from app.db import get_db
from app.errors import ApiError

router = APIRouter(prefix="/api/v1/webhooks", tags=["webhooks"])

STATUS_BY_EVENT = {
    "subscription.activated": "active",
    "subscription.charged": "active",
    "subscription.cancelled": "cancelled",
    "subscription.completed": "expired",
    "subscription.expired": "expired",
    "subscription.pending": "past_due",
}


@router.post("/razorpay")
async def razorpay_webhook(request: Request, db: Session = Depends(get_db)):
    body = await request.body()
    signature = request.headers.get("X-Razorpay-Signature", "")
    expected = hmac.new(settings.razorpay_webhook_secret.encode(), body,
                        hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, signature):
        raise ApiError(400, "bad_signature", "Webhook signature mismatch")

    event = json.loads(body)
    event_id = request.headers.get("X-Razorpay-Event-Id") or hashlib.sha256(body).hexdigest()
    db.add(models.WebhookEvent(razorpay_event_id=event_id,
                               event_type=event.get("event", ""), payload=event))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return {"status": "duplicate"}

    event_type = event.get("event", "")
    new_status = STATUS_BY_EVENT.get(event_type)
    entity = (event.get("payload", {}).get("subscription", {}) or {}).get("entity", {})
    rzp_sub_id = entity.get("id", "")
    if new_status and rzp_sub_id:
        sub = (db.query(models.Subscription)
                 .filter(models.Subscription.razorpay_subscription_id == rzp_sub_id).first())
        if sub:
            sub.status = new_status
            if new_status == "active":
                if entity.get("current_start"):
                    sub.current_period_start = datetime.fromtimestamp(
                        entity["current_start"], tz=timezone.utc)
                if entity.get("current_end"):
                    sub.current_period_end = datetime.fromtimestamp(
                        entity["current_end"], tz=timezone.utc)
            db.commit()
    return {"status": "processed"}
```

- [ ] **Step 4: Register router in `main.py`; run tests** — all pass.

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat(backend): signature-verified idempotent Razorpay webhook handler"
```

---

### Task 9: Storage adapters + playback endpoint + local media serving

**Files:**
- Create: `backend/app/storage/__init__.py`, `backend/app/storage/base.py`, `backend/app/storage/local.py`, `backend/app/storage/s3.py`, `backend/app/routers/playback.py`, `backend/app/routers/media.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_playback.py`

**Interfaces:**
- Consumes: models, `can_watch`, `settings`.
- Produces:
  - `storage.base.PlaybackAuth` dataclass: `url: str`, `cookies: dict[str, str]`
  - `storage.base.Storage` protocol: `publish(episode_id: str, local_dir: Path) -> str` (returns hls_path), `playback(hls_path: str) -> PlaybackAuth`
  - `storage.get_storage() -> Storage` (in `storage/__init__.py`, switches on `settings.storage_mode`)
  - `GET /api/v1/episodes/{episode_id}/playback` → `{url, episode_id, episode_number, series_slug, resume_position: int}`; sets CDN cookies in s3 mode; 403 `subscription_required` when locked; 404 when missing/not-ready; increments `series.view_count`
  - `GET /media/{episode_id}/{filename}` (local mode) — serves HLS files; entitlement re-checked when `filename == "master.m3u8"`

- [ ] **Step 1: Write failing tests `backend/tests/test_playback.py`**

```python
from datetime import datetime, timedelta, timezone

from app import models
from tests.test_catalog import seed_catalog


def login(client):
    client.post("/api/v1/auth/signup", json={"email": "u@t.co", "password": "password1", "name": "U"})


def subscribe(db):
    u = db.query(models.User).one()
    p = models.Plan(name="M", price_inr=14900, interval="monthly")
    db.add(p)
    db.flush()
    db.add(models.Subscription(user_id=u.id, plan_id=p.id, razorpay_subscription_id="sub_t",
                               status="active",
                               current_period_end=datetime.now(timezone.utc) + timedelta(days=5)))
    db.commit()


def prep_hls(db):
    s = seed_catalog(db)
    for e in s.episodes:
        e.hls_path = f"{e.id}/master.m3u8"
    db.commit()
    return s


def test_free_episode_playback_guest(client, db):
    s = prep_hls(db)
    ep = s.episodes[0]
    r = client.get(f"/api/v1/episodes/{ep.id}/playback")
    assert r.status_code == 200
    body = r.json()
    assert body["url"].endswith(f"/media/{ep.id}/master.m3u8")
    assert body["resume_position"] == 0
    db.refresh(s)
    assert s.view_count == 101  # incremented


def test_locked_episode_403_guest_and_unsubscribed(client, db):
    s = prep_hls(db)
    ep = s.episodes[2]  # episode 3, free_episode_count=2
    r = client.get(f"/api/v1/episodes/{ep.id}/playback")
    assert r.status_code == 403 and r.json()["error"]["code"] == "subscription_required"
    login(client)
    assert client.get(f"/api/v1/episodes/{ep.id}/playback").status_code == 403


def test_locked_episode_ok_for_subscriber(client, db):
    s = prep_hls(db)
    login(client)
    subscribe(db)
    assert client.get(f"/api/v1/episodes/{s.episodes[2].id}/playback").status_code == 200


def test_resume_position_returned(client, db):
    s = prep_hls(db)
    ep = s.episodes[0]
    login(client)
    client.put(f"/api/v1/progress/{ep.id}", json={"position_seconds": 33, "completed": False})
    assert client.get(f"/api/v1/episodes/{ep.id}/playback").json()["resume_position"] == 33


def test_processing_episode_404(client, db):
    s = prep_hls(db)
    processing = [e for e in s.episodes if e.status == "processing"][0]
    assert client.get(f"/api/v1/episodes/{processing.id}/playback").status_code == 404
```

Note: `seed_catalog` marks episodes 1-3 `ready` and episode 4 `processing`; `Series.episodes` relationship only lists them all — `prep_hls` sets `hls_path` on all.

- [ ] **Step 2: Run to verify failure.**

- [ ] **Step 3: Create `backend/app/storage/base.py`**

```python
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol


@dataclass
class PlaybackAuth:
    url: str
    cookies: dict[str, str] = field(default_factory=dict)


class Storage(Protocol):
    def publish(self, episode_id: str, local_dir: Path) -> str:
        """Upload a directory of HLS files; return the hls_path to store on the episode."""
        ...

    def playback(self, hls_path: str) -> PlaybackAuth:
        """Return the playable master playlist URL plus any auth cookies."""
        ...
```

- [ ] **Step 4: Create `backend/app/storage/local.py`**

```python
import shutil
from pathlib import Path

from app.config import settings
from app.storage.base import PlaybackAuth


class LocalStorage:
    def __init__(self):
        self.root = Path(settings.media_root)

    def publish(self, episode_id: str, local_dir: Path) -> str:
        dest = self.root / episode_id
        if dest.resolve() != local_dir.resolve():
            dest.mkdir(parents=True, exist_ok=True)
            for f in local_dir.iterdir():
                shutil.copy2(f, dest / f.name)
        return f"{episode_id}/master.m3u8"

    def playback(self, hls_path: str) -> PlaybackAuth:
        return PlaybackAuth(url=f"{settings.api_base_url}/media/{hls_path}")
```

- [ ] **Step 5: Create `backend/app/storage/s3.py`**

```python
import base64
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import boto3
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

from app.config import settings
from app.storage.base import PlaybackAuth

CONTENT_TYPES = {".m3u8": "application/vnd.apple.mpegurl", ".ts": "video/mp2t",
                 ".jpg": "image/jpeg", ".mp4": "video/mp4"}


def _cf_b64(data: bytes) -> str:
    return base64.b64encode(data).decode().replace("+", "-").replace("=", "_").replace("/", "~")


class S3Storage:
    def __init__(self):
        self.s3 = boto3.client("s3", region_name=settings.aws_region)

    def publish(self, episode_id: str, local_dir: Path) -> str:
        prefix = f"hls/{episode_id}"
        for f in local_dir.iterdir():
            self.s3.upload_file(
                str(f), settings.s3_bucket, f"{prefix}/{f.name}",
                ExtraArgs={"ContentType": CONTENT_TYPES.get(f.suffix, "application/octet-stream")})
        return f"{prefix}/master.m3u8"

    def playback(self, hls_path: str) -> PlaybackAuth:
        resource = f"https://{settings.cloudfront_domain}/{hls_path.rsplit('/', 1)[0]}/*"
        expires = int((datetime.now(timezone.utc) + timedelta(hours=6)).timestamp())
        policy = json.dumps({"Statement": [{"Resource": resource, "Condition": {
            "DateLessThan": {"AWS:EpochTime": expires}}}]}, separators=(",", ":"))
        key = serialization.load_pem_private_key(
            Path(settings.cloudfront_private_key_path).read_bytes(), password=None)
        signature = key.sign(policy.encode(), padding.PKCS1v15(), hashes.SHA1())
        return PlaybackAuth(
            url=f"https://{settings.cloudfront_domain}/{hls_path}",
            cookies={
                "CloudFront-Policy": _cf_b64(policy.encode()),
                "CloudFront-Signature": _cf_b64(signature),
                "CloudFront-Key-Pair-Id": settings.cloudfront_key_pair_id,
            })
```

- [ ] **Step 6: Create `backend/app/storage/__init__.py`**

```python
from app.config import settings
from app.storage.base import PlaybackAuth, Storage  # noqa: F401


def get_storage() -> Storage:
    if settings.storage_mode == "s3":
        from app.storage.s3 import S3Storage
        return S3Storage()
    from app.storage.local import LocalStorage
    return LocalStorage()
```

- [ ] **Step 7: Create `backend/app/routers/playback.py`**

```python
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
```

- [ ] **Step 8: Create `backend/app/routers/media.py`** (local mode only; mounted always, 404s in s3 mode)

```python
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
    media_type = "application/vnd.apple.mpegurl" if filename.endswith(".m3u8") else "video/mp2t"
    return FileResponse(path, media_type=media_type)
```

- [ ] **Step 9: Register `playback` and `media` routers in `main.py`; run tests.**

Tests don't touch the filesystem (they only check URLs/status codes), so local mode works as-is. All pass.

- [ ] **Step 10: Commit**

```bash
git add -A && git commit -m "feat(backend): storage adapters (local/S3+CloudFront) and entitlement-gated playback"
```

---

### Task 10: FFmpeg transcode + ingest CLI

**Files:**
- Create: `backend/app/transcode.py`, `backend/app/ingest.py`
- Test: `backend/tests/test_transcode.py` (skipped when FFmpeg is absent)

**Interfaces:**
- Consumes: models, `get_storage()`, `SessionLocal`, `settings`.
- Produces:
  - `transcode.transcode_to_hls(src: Path, outdir: Path) -> int` — writes `{height}.m3u8` + segments + `master.m3u8` into outdir, returns duration in seconds. Ladder: `RENDITIONS = [(1920, 4000), (1280, 2000), (854, 1000)]` (target long-side height, kbps).
  - `transcode.extract_thumbnail(src: Path, out_jpg: Path) -> None`
  - `transcode.probe_duration(src: Path) -> float`
  - CLI: `python -m app.ingest <video> --series-slug X --series-title "Y" --episode-number N [--episode-title T] [--synopsis S] [--language en] [--genres a,b] [--free-episodes 3] [--poster-url URL] [--banner-url URL] [--featured]`

- [ ] **Step 1: Write test `backend/tests/test_transcode.py`**

```python
import shutil
import subprocess
from pathlib import Path

import pytest

ffmpeg_missing = shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None


@pytest.mark.skipif(ffmpeg_missing, reason="ffmpeg not installed")
def test_transcode_produces_hls(tmp_path):
    from app.transcode import probe_duration, transcode_to_hls

    src = tmp_path / "src.mp4"
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", "testsrc2=size=360x640:rate=30",
         "-f", "lavfi", "-i", "sine=frequency=440", "-t", "2",
         "-c:v", "libx264", "-c:a", "aac", "-shortest", str(src)],
        check=True, capture_output=True)
    out = tmp_path / "hls"
    duration = transcode_to_hls(src, out)
    assert (out / "master.m3u8").is_file()
    assert (out / "854.m3u8").is_file()
    assert list(out.glob("854_*.ts"))
    assert 1 <= duration <= 3
    master = (out / "master.m3u8").read_text()
    assert "#EXT-X-STREAM-INF" in master and "854.m3u8" in master
    assert probe_duration(src) > 0
```

- [ ] **Step 2: Run** — fails with import error (or skips on machines without FFmpeg — executor must have FFmpeg; verify with `ffmpeg -version` first and install via `winget install Gyan.FFmpeg` if missing).

- [ ] **Step 3: Create `backend/app/transcode.py`**

```python
import subprocess
from pathlib import Path

RENDITIONS = [(1920, 4000), (1280, 2000), (854, 1000)]  # (long-side px, video kbps)


def probe_duration(src: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(src)],
        check=True, capture_output=True, text=True).stdout.strip()
    return float(out)


def transcode_to_hls(src: Path, outdir: Path) -> int:
    outdir.mkdir(parents=True, exist_ok=True)
    for height, kbps in RENDITIONS:
        subprocess.run(
            ["ffmpeg", "-y", "-i", str(src),
             "-vf", f"scale=-2:{height}",
             "-c:v", "libx264", "-preset", "veryfast",
             "-b:v", f"{kbps}k", "-maxrate", f"{int(kbps * 1.2)}k", "-bufsize", f"{kbps * 2}k",
             "-c:a", "aac", "-b:a", "128k", "-ac", "2",
             "-hls_time", "4", "-hls_playlist_type", "vod",
             "-hls_segment_filename", str(outdir / f"{height}_%04d.ts"),
             str(outdir / f"{height}.m3u8")],
            check=True, capture_output=True)
    lines = ["#EXTM3U", "#EXT-X-VERSION:3"]
    for height, kbps in RENDITIONS:
        width = int(height * 9 / 16 / 2) * 2
        lines.append(f"#EXT-X-STREAM-INF:BANDWIDTH={kbps * 1100},RESOLUTION={width}x{height}")
        lines.append(f"{height}.m3u8")
    (outdir / "master.m3u8").write_text("\n".join(lines) + "\n")
    return round(probe_duration(src))


def extract_thumbnail(src: Path, out_jpg: Path) -> None:
    subprocess.run(
        ["ffmpeg", "-y", "-ss", "1", "-i", str(src), "-frames:v", "1",
         "-vf", "scale=-2:854", str(out_jpg)],
        check=True, capture_output=True)
```

- [ ] **Step 4: Run test** — passes (with FFmpeg installed).

- [ ] **Step 5: Create `backend/app/ingest.py`**

```python
"""Content ingest CLI. Usage:
    python -m app.ingest video.mp4 --series-slug ceo-bride --series-title "CEO's Secret Bride" \
        --episode-number 1 --episode-title "The Wedding" --genres romance,drama
Requires FFmpeg on PATH. Uses STORAGE_MODE from .env (local by default).
"""
import argparse
import shutil
import sys
import tempfile
from pathlib import Path

from app import models
from app.config import settings
from app.db import SessionLocal
from app.storage import get_storage
from app.transcode import extract_thumbnail, transcode_to_hls


def slugify(text: str) -> str:
    return "".join(c if c.isalnum() else "-" for c in text.lower()).strip("-")


def get_or_create_series(db, args) -> models.Series:
    series = db.query(models.Series).filter(models.Series.slug == args.series_slug).first()
    if series:
        return series
    series = models.Series(
        slug=args.series_slug, title=args.series_title or args.series_slug,
        synopsis=args.synopsis, language=args.language,
        free_episode_count=args.free_episodes, is_featured=args.featured,
        poster_url=args.poster_url or f"https://picsum.photos/seed/{args.series_slug}/540/960",
        banner_url=args.banner_url or f"https://picsum.photos/seed/{args.series_slug}-b/1280/720",
    )
    for gslug in [g.strip() for g in args.genres.split(",") if g.strip()]:
        genre = db.query(models.Genre).filter(models.Genre.slug == gslug).first()
        if not genre:
            genre = models.Genre(slug=gslug, name=gslug.replace("-", " ").title())
            db.add(genre)
        series.genres.append(genre)
    db.add(series)
    db.flush()
    return series


def upload_thumbnail(episode_id: str, jpg: Path) -> str:
    if settings.imagekit_private_key:
        from imagekitio import ImageKit  # optional dep: pip install imagekitio
        ik = ImageKit(private_key=settings.imagekit_private_key,
                      public_key=settings.imagekit_public_key,
                      url_endpoint=settings.imagekit_url_endpoint)
        with open(jpg, "rb") as f:
            result = ik.upload_file(file=f, file_name=f"{episode_id}.jpg")
        return result.url
    # local fallback: keep it next to the HLS files, served by /media
    dest = Path(settings.media_root) / episode_id / "thumb.jpg"
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(jpg, dest)
    return f"{settings.api_base_url}/media/{episode_id}/thumb.jpg"


def ingest(args) -> None:
    src = Path(args.video)
    if not src.is_file():
        sys.exit(f"error: video file not found: {src}")
    db = SessionLocal()
    try:
        series = get_or_create_series(db, args)
        episode = (db.query(models.Episode)
                     .filter(models.Episode.series_id == series.id,
                             models.Episode.episode_number == args.episode_number).first())
        if episode is None:
            episode = models.Episode(series_id=series.id, episode_number=args.episode_number)
            db.add(episode)
        episode.title = args.episode_title or f"Episode {args.episode_number}"
        episode.status = "processing"
        db.commit()

        try:
            with tempfile.TemporaryDirectory() as tmp:
                tmpdir = Path(tmp)
                hls_dir = tmpdir / "hls"
                episode.duration_seconds = transcode_to_hls(src, hls_dir)
                episode.hls_path = get_storage().publish(str(episode.id), hls_dir)
                thumb = tmpdir / "thumb.jpg"
                extract_thumbnail(src, thumb)
                episode.thumbnail_url = upload_thumbnail(str(episode.id), thumb)
            episode.status = "ready"
            db.commit()
            print(f"ready: {series.slug} ep{episode.episode_number} ({episode.duration_seconds}s)")
        except Exception as exc:
            episode.status = "failed"
            db.commit()
            sys.exit(f"error: ingest failed, episode marked failed: {exc}")
    finally:
        db.close()


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Ingest a video as a series episode")
    p.add_argument("video")
    p.add_argument("--series-slug", required=True)
    p.add_argument("--series-title", default="")
    p.add_argument("--episode-number", type=int, required=True)
    p.add_argument("--episode-title", default="")
    p.add_argument("--synopsis", default="")
    p.add_argument("--language", default="en")
    p.add_argument("--genres", default="drama")
    p.add_argument("--free-episodes", type=int, default=3)
    p.add_argument("--poster-url", default="")
    p.add_argument("--banner-url", default="")
    p.add_argument("--featured", action="store_true")
    return p


if __name__ == "__main__":
    ingest(build_parser().parse_args())
```

- [ ] **Step 6: Manual smoke test** (needs FFmpeg): generate a clip and ingest it:

```bash
cd backend
ffmpeg -y -f lavfi -i testsrc2=size=720x1280:rate=30 -f lavfi -i sine=frequency=440 -t 8 -c:v libx264 -c:a aac -shortest /tmp/clip.mp4
.venv/Scripts/python -m app.ingest /tmp/clip.mp4 --series-slug smoke-test --series-title "Smoke" --episode-number 1
```

Expected: `ready: smoke-test ep1 (8s)`; `backend/media/<episode-id>/master.m3u8` exists. Then delete the test row: it's fine to leave it — seed task will wipe nothing; optionally remove via `python -c` or leave for the demo.

- [ ] **Step 7: Commit**

```bash
git add -A && git commit -m "feat(backend): FFmpeg HLS transcode pipeline and ingest CLI"
```

---

### Task 11: Seed script (demo content + plans)

**Files:**
- Create: `backend/app/seed.py`
- Test: manual run + existing suite stays green

**Interfaces:**
- Consumes: `ingest.get_or_create_series` internals (reuses models directly), `transcode`, `get_storage`, `SessionLocal`.
- Produces: `python -m app.seed` — idempotent; creates 5 genres, 3 plans, 4 demo series × 5 episodes each with FFmpeg-generated vertical clips (distinct colors/tones per series), first 2 episodes free on each.

- [ ] **Step 1: Create `backend/app/seed.py`**

```python
"""Seed demo content. Requires FFmpeg. Usage: python -m app.seed"""
import subprocess
import tempfile
from pathlib import Path

from app import models
from app.db import SessionLocal
from app.storage import get_storage
from app.transcode import extract_thumbnail, transcode_to_hls
from app.ingest import upload_thumbnail

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
```

Note on Razorpay plans: seeding leaves `razorpay_plan_id` empty. To enable real checkout later, create plans in the Razorpay dashboard (test mode) and copy their ids into the `plans` rows; document this in the README (Task 19). Subscription creation with an empty plan id fails at Razorpay — acceptable until keys exist.

- [ ] **Step 2: Run the seed** (FFmpeg required)

```bash
cd backend && .venv/Scripts/python -m app.seed
```

Expected: `seeded <slug> ep1..ep5` for 4 series (~60 HLS renditions; takes a couple of minutes). Re-running prints `skip existing`.

- [ ] **Step 3: Verify API end-to-end**

```bash
cd backend && .venv/Scripts/uvicorn app.main:app --port 8000
```

Then `curl http://localhost:8000/api/v1/home` → featured + rails populated; open a free episode's playback URL and confirm `master.m3u8` downloads. Full pytest suite still green.

- [ ] **Step 4: Commit**

```bash
git add -A && git commit -m "feat(backend): seed script with generated demo series, genres, and plans"
```

---

## Phase B — Frontend

### Task 12: Next.js scaffold, types, API clients, layout + navbar

**Files:**
- Create: `frontend/` via create-next-app, `frontend/.env.local`, `frontend/src/lib/types.ts`, `frontend/src/lib/api-client.ts`, `frontend/src/lib/api-server.ts`, `frontend/src/components/Navbar.tsx`
- Modify: `frontend/src/app/layout.tsx`, `frontend/src/app/globals.css`, `frontend/src/app/page.tsx` (placeholder)

**Interfaces:**
- Produces (used by all later frontend tasks):
  - `types.ts`: `SeriesSummary`, `EpisodeSummary`, `SeriesDetail`, `GenreOut`, `ContinueItem`, `HomeData`, `User`, `Plan`, `CurrentSubscription`, `PlaybackInfo`
  - `api-client.ts`: `apiFetch<T>(path, init?): Promise<T>` (browser; credentials included; silent refresh-retry on 401) and `class ApiError extends Error { status: number; code: string }`
  - `api-server.ts`: `serverFetch<T>(path): Promise<T | null>` (server components; forwards cookies; `cache: "no-store"`; null on any non-2xx)

- [ ] **Step 1: Scaffold**

```bash
npx create-next-app@latest frontend --typescript --tailwind --eslint --app --src-dir --use-npm --import-alias "@/*" --turbopack
cd frontend && npm i hls.js
```

Create `frontend/.env.local`:

```
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_RAZORPAY_KEY_ID=rzp_test_dummy
```

- [ ] **Step 2: Create `frontend/src/lib/types.ts`**

```ts
export interface SeriesSummary {
  id: string; slug: string; title: string; synopsis: string; language: string;
  poster_url: string; banner_url: string; free_episode_count: number;
  is_featured: boolean; view_count: number; genres: string[]; episode_count: number;
}
export interface EpisodeSummary {
  id: string; episode_number: number; title: string; duration_seconds: number;
  thumbnail_url: string; is_free: boolean; locked: boolean;
}
export interface SeriesDetail extends SeriesSummary { episodes: EpisodeSummary[] }
export interface GenreOut { slug: string; name: string }
export interface ContinueItem {
  series: SeriesSummary; episode_number: number; episode_id: string; position_seconds: number;
}
export interface HomeData {
  featured: SeriesSummary[]; trending: SeriesSummary[]; new_releases: SeriesSummary[];
  genre_rails: { genre: GenreOut; series: SeriesSummary[] }[];
  continue_watching: ContinueItem[];
}
export interface User { id: string; email: string; name: string }
export interface Plan { id: number; name: string; price_inr: number; interval: string }
export interface CurrentSubscription {
  status: string; plan: Plan; current_period_end: string | null;
}
export interface PlaybackInfo {
  url: string; episode_id: string; episode_number: number;
  series_slug: string; resume_position: number;
}
```

- [ ] **Step 3: Create `frontend/src/lib/api-client.ts`**

```ts
const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  constructor(public status: number, public code: string, message: string) {
    super(message);
  }
}

function doFetch(path: string, init?: RequestInit) {
  return fetch(`${API}${path}`, {
    ...init,
    credentials: "include",
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
  });
}

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  let res = await doFetch(path, init);
  if (res.status === 401 && !path.startsWith("/api/v1/auth/")) {
    const refreshed = await doFetch("/api/v1/auth/refresh", { method: "POST" });
    if (refreshed.ok) res = await doFetch(path, init);
  }
  if (!res.ok) {
    let code = "error";
    let message = res.statusText;
    try {
      const body = await res.json();
      code = body.error?.code ?? code;
      message = body.error?.message ?? message;
    } catch {}
    throw new ApiError(res.status, code, message);
  }
  return res.json();
}
```

- [ ] **Step 4: Create `frontend/src/lib/api-server.ts`**

```ts
import { cookies } from "next/headers";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export async function serverFetch<T>(path: string): Promise<T | null> {
  const cookieHeader = (await cookies()).toString();
  try {
    const res = await fetch(`${API}${path}`, {
      headers: cookieHeader ? { cookie: cookieHeader } : {},
      cache: "no-store",
    });
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}
```

- [ ] **Step 5: Create `frontend/src/components/Navbar.tsx`**

```tsx
"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { apiFetch } from "@/lib/api-client";
import type { User } from "@/lib/types";

export default function Navbar() {
  const [user, setUser] = useState<User | null>(null);
  const [loaded, setLoaded] = useState(false);
  const router = useRouter();

  useEffect(() => {
    apiFetch<User>("/api/v1/auth/me")
      .then(setUser)
      .catch(() => setUser(null))
      .finally(() => setLoaded(true));
  }, []);

  async function logout() {
    await apiFetch("/api/v1/auth/logout", { method: "POST" }).catch(() => {});
    setUser(null);
    router.push("/");
    router.refresh();
  }

  return (
    <header className="sticky top-0 z-40 border-b border-zinc-800 bg-zinc-950/90 backdrop-blur">
      <nav className="mx-auto flex h-14 max-w-6xl items-center gap-5 px-4 text-sm">
        <Link href="/" className="text-lg font-extrabold tracking-tight text-rose-500">
          ShortReel
        </Link>
        <Link href="/search" className="text-zinc-300 hover:text-white">Search</Link>
        <Link href="/my-list" className="text-zinc-300 hover:text-white">My List</Link>
        <Link href="/plans" className="text-zinc-300 hover:text-white">Plans</Link>
        <div className="ml-auto flex items-center gap-3">
          {!loaded ? null : user ? (
            <>
              <Link href="/account" className="text-zinc-300 hover:text-white">{user.name}</Link>
              <button onClick={logout} className="rounded bg-zinc-800 px-3 py-1.5 hover:bg-zinc-700">
                Log out
              </button>
            </>
          ) : (
            <>
              <Link href="/login" className="text-zinc-300 hover:text-white">Log in</Link>
              <Link href="/signup" className="rounded bg-rose-600 px-3 py-1.5 font-medium hover:bg-rose-500">
                Sign up
              </Link>
            </>
          )}
        </div>
      </nav>
    </header>
  );
}
```

- [ ] **Step 6: Replace `frontend/src/app/layout.tsx`**

```tsx
import type { Metadata } from "next";
import "./globals.css";
import Navbar from "@/components/Navbar";

export const metadata: Metadata = {
  title: "ShortReel — Short Dramas, Big Feelings",
  description: "Vertical micro-drama series. First episodes free.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <body className="min-h-screen bg-zinc-950 text-zinc-100 antialiased">
        <Navbar />
        <main>{children}</main>
      </body>
    </html>
  );
}
```

Replace `frontend/src/app/page.tsx` with a placeholder (`export default function Home() { return <div className="p-8">ShortReel</div> }`) and strip create-next-app boilerplate from `globals.css` beyond the Tailwind import.

- [ ] **Step 7: Verify** — `cd frontend && npm run build` → succeeds. Then `npm run dev` and confirm the navbar renders at http://localhost:3000 with the backend running (login state resolves to logged-out).

- [ ] **Step 8: Commit**

```bash
git add -A && git commit -m "feat(frontend): Next.js scaffold with typed API clients, layout and navbar"
```

---

### Task 13: Auth pages (login/signup)

**Files:**
- Create: `frontend/src/components/AuthForm.tsx`, `frontend/src/app/login/page.tsx`, `frontend/src/app/signup/page.tsx`

**Interfaces:**
- Consumes: `apiFetch`, `ApiError`.
- Produces: `/login`, `/signup` pages. On success → `router.push(next ?? "/")` + `router.refresh()`; both accept `?next=` query param (used by paywall later).

- [ ] **Step 1: Create `frontend/src/components/AuthForm.tsx`**

```tsx
"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useState } from "react";
import { apiFetch, ApiError } from "@/lib/api-client";

export default function AuthForm({ mode }: { mode: "login" | "signup" }) {
  const params = useSearchParams();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const body = mode === "signup" ? { email, password, name } : { email, password };
      await apiFetch(`/api/v1/auth/${mode}`, { method: "POST", body: JSON.stringify(body) });
      // full reload so the navbar picks up the session cookie
      window.location.href = params.get("next") ?? "/";
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong");
      setBusy(false);
    }
  }

  const input = "w-full rounded bg-zinc-900 border border-zinc-700 px-3 py-2 outline-none focus:border-rose-500";
  return (
    <div className="mx-auto mt-16 max-w-sm px-4">
      <h1 className="mb-6 text-2xl font-bold">{mode === "login" ? "Welcome back" : "Create your account"}</h1>
      <form onSubmit={submit} className="space-y-4">
        {mode === "signup" && (
          <input className={input} placeholder="Name" value={name}
                 onChange={(e) => setName(e.target.value)} required />
        )}
        <input className={input} type="email" placeholder="Email" value={email}
               onChange={(e) => setEmail(e.target.value)} required />
        <input className={input} type="password" placeholder="Password (min 8 chars)" value={password}
               onChange={(e) => setPassword(e.target.value)} minLength={8} required />
        {error && <p className="text-sm text-rose-400">{error}</p>}
        <button disabled={busy}
                className="w-full rounded bg-rose-600 py-2 font-semibold hover:bg-rose-500 disabled:opacity-50">
          {busy ? "..." : mode === "login" ? "Log in" : "Sign up"}
        </button>
      </form>
      <p className="mt-4 text-sm text-zinc-400">
        {mode === "login" ? (
          <>New here? <Link className="text-rose-400" href="/signup">Create an account</Link></>
        ) : (
          <>Already have an account? <Link className="text-rose-400" href="/login">Log in</Link></>
        )}
      </p>
    </div>
  );
}
```

- [ ] **Step 2: Create the two pages**

`frontend/src/app/login/page.tsx`:

```tsx
import { Suspense } from "react";
import AuthForm from "@/components/AuthForm";

export default function LoginPage() {
  return (
    <Suspense>
      <AuthForm mode="login" />
    </Suspense>
  );
}
```

`frontend/src/app/signup/page.tsx`: identical but `mode="signup"` and named `SignupPage`.

- [ ] **Step 3: Verify** — `npm run build` passes. Manual: with backend running, sign up at `/signup`, navbar shows your name after redirect; log out; log in again at `/login`.

- [ ] **Step 4: Commit**

```bash
git add -A && git commit -m "feat(frontend): login and signup pages"
```

---

### Task 14: Home page — hero, rails, series cards

**Files:**
- Create: `frontend/src/components/SeriesCard.tsx`, `frontend/src/components/Rail.tsx`, `frontend/src/components/Hero.tsx`
- Modify: `frontend/src/app/page.tsx`

**Interfaces:**
- Consumes: `serverFetch`, `HomeData`, `SeriesSummary`, `ContinueItem`.
- Produces: `SeriesCard({ series })`, `Rail({ title, series })`, `Hero({ items })` — reused by genre/search/my-list pages.

- [ ] **Step 1: Create `frontend/src/components/SeriesCard.tsx`**

```tsx
import Link from "next/link";
import type { SeriesSummary } from "@/lib/types";

export default function SeriesCard({ series }: { series: SeriesSummary }) {
  return (
    <Link href={`/series/${series.slug}`}
          className="group w-36 shrink-0 sm:w-40" title={series.title}>
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img src={series.poster_url} alt={series.title}
           className="aspect-[9/16] w-full rounded-lg object-cover ring-1 ring-zinc-800 transition group-hover:ring-rose-500" />
      <p className="mt-2 line-clamp-1 text-sm font-medium">{series.title}</p>
      <p className="text-xs text-zinc-500">{series.episode_count} episodes</p>
    </Link>
  );
}
```

- [ ] **Step 2: Create `frontend/src/components/Rail.tsx`**

```tsx
import SeriesCard from "@/components/SeriesCard";
import type { SeriesSummary } from "@/lib/types";

export default function Rail({ title, series }: { title: string; series: SeriesSummary[] }) {
  if (!series.length) return null;
  return (
    <section className="mt-8">
      <h2 className="mb-3 px-4 text-lg font-bold">{title}</h2>
      <div className="flex gap-3 overflow-x-auto px-4 pb-2">
        {series.map((s) => <SeriesCard key={s.id} series={s} />)}
      </div>
    </section>
  );
}
```

- [ ] **Step 3: Create `frontend/src/components/Hero.tsx`**

```tsx
"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import type { SeriesSummary } from "@/lib/types";

export default function Hero({ items }: { items: SeriesSummary[] }) {
  const [index, setIndex] = useState(0);
  useEffect(() => {
    if (items.length < 2) return;
    const t = setInterval(() => setIndex((i) => (i + 1) % items.length), 5000);
    return () => clearInterval(t);
  }, [items.length]);
  if (!items.length) return null;
  const s = items[index];
  return (
    <div className="relative h-72 w-full overflow-hidden sm:h-96">
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img src={s.banner_url} alt={s.title} className="h-full w-full object-cover" />
      <div className="absolute inset-0 bg-gradient-to-t from-zinc-950 via-zinc-950/40 to-transparent" />
      <div className="absolute bottom-6 left-4 right-4 mx-auto max-w-6xl">
        <p className="text-xs font-semibold uppercase tracking-widest text-rose-400">Featured</p>
        <h1 className="mt-1 text-3xl font-extrabold">{s.title}</h1>
        <p className="mt-1 line-clamp-2 max-w-xl text-sm text-zinc-300">{s.synopsis}</p>
        <div className="mt-3 flex gap-2">
          <Link href={`/watch/${s.slug}/1`}
                className="rounded bg-rose-600 px-5 py-2 text-sm font-semibold hover:bg-rose-500">
            ▶ Play
          </Link>
          <Link href={`/series/${s.slug}`}
                className="rounded bg-zinc-800/80 px-5 py-2 text-sm font-semibold hover:bg-zinc-700">
            Details
          </Link>
        </div>
        {items.length > 1 && (
          <div className="mt-3 flex gap-1.5">
            {items.map((_, i) => (
              <button key={i} onClick={() => setIndex(i)}
                      className={`h-1.5 w-6 rounded-full ${i === index ? "bg-rose-500" : "bg-zinc-600"}`} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Replace `frontend/src/app/page.tsx`**

```tsx
import Link from "next/link";
import Hero from "@/components/Hero";
import Rail from "@/components/Rail";
import { serverFetch } from "@/lib/api-server";
import type { HomeData } from "@/lib/types";

export default async function HomePage() {
  const data = await serverFetch<HomeData>("/api/v1/home");
  if (!data) {
    return <div className="p-10 text-center text-zinc-400">
      Could not reach the API. Is the backend running on port 8000?
    </div>;
  }
  return (
    <div className="mx-auto max-w-6xl pb-16">
      <Hero items={data.featured} />
      {data.continue_watching.length > 0 && (
        <section className="mt-8">
          <h2 className="mb-3 px-4 text-lg font-bold">Continue Watching</h2>
          <div className="flex gap-3 overflow-x-auto px-4 pb-2">
            {data.continue_watching.map((c) => (
              <Link key={c.episode_id} href={`/watch/${c.series.slug}/${c.episode_number}`}
                    className="w-36 shrink-0 sm:w-40">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src={c.series.poster_url} alt={c.series.title}
                     className="aspect-[9/16] w-full rounded-lg object-cover ring-1 ring-zinc-800" />
                <p className="mt-2 line-clamp-1 text-sm font-medium">{c.series.title}</p>
                <p className="text-xs text-rose-400">Resume Ep {c.episode_number}</p>
              </Link>
            ))}
          </div>
        </section>
      )}
      <Rail title="Trending Now" series={data.trending} />
      <Rail title="New Releases" series={data.new_releases} />
      {data.genre_rails.map((rail) => (
        <Rail key={rail.genre.slug} title={rail.genre.name} series={rail.series} />
      ))}
    </div>
  );
}
```

- [ ] **Step 5: Verify** — `npm run build` passes; with backend + seed running, home shows hero carousel and rails with posters.

- [ ] **Step 6: Commit**

```bash
git add -A && git commit -m "feat(frontend): home page with hero carousel, continue watching, and genre rails"
```

---

### Task 15: Series detail page

**Files:**
- Create: `frontend/src/app/series/[slug]/page.tsx`, `frontend/src/components/EpisodeGrid.tsx`, `frontend/src/components/WatchlistButton.tsx`

**Interfaces:**
- Consumes: `serverFetch`, `SeriesDetail`, `apiFetch`.
- Produces: `/series/[slug]` route; `EpisodeGrid({ series })` (also used on watch page paywall "back to series" flow).

- [ ] **Step 1: Create `frontend/src/components/EpisodeGrid.tsx`**

```tsx
import Link from "next/link";
import type { SeriesDetail } from "@/lib/types";

export default function EpisodeGrid({ series }: { series: SeriesDetail }) {
  return (
    <div className="grid grid-cols-3 gap-3 sm:grid-cols-4 md:grid-cols-6">
      {series.episodes.map((e) => (
        <Link key={e.id} href={`/watch/${series.slug}/${e.episode_number}`}
              className="group relative">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={e.thumbnail_url || series.poster_url} alt={e.title}
               className={`aspect-[9/16] w-full rounded-md object-cover ring-1 ring-zinc-800 ${e.locked ? "opacity-50" : ""}`} />
          <span className="absolute left-1.5 top-1.5 rounded bg-zinc-950/80 px-1.5 py-0.5 text-xs font-semibold">
            {e.episode_number}
          </span>
          {e.locked && (
            <span className="absolute inset-0 flex items-center justify-center text-2xl">🔒</span>
          )}
        </Link>
      ))}
    </div>
  );
}
```

- [ ] **Step 2: Create `frontend/src/components/WatchlistButton.tsx`**

```tsx
"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { apiFetch, ApiError } from "@/lib/api-client";
import type { SeriesSummary } from "@/lib/types";

export default function WatchlistButton({ seriesId }: { seriesId: string }) {
  const [inList, setInList] = useState<boolean | null>(null);
  const router = useRouter();

  useEffect(() => {
    apiFetch<SeriesSummary[]>("/api/v1/watchlist")
      .then((items) => setInList(items.some((s) => s.id === seriesId)))
      .catch(() => setInList(false));
  }, [seriesId]);

  async function toggle() {
    try {
      if (inList) {
        await apiFetch(`/api/v1/watchlist/${seriesId}`, { method: "DELETE" });
        setInList(false);
      } else {
        await apiFetch("/api/v1/watchlist", {
          method: "POST", body: JSON.stringify({ series_id: seriesId }),
        });
        setInList(true);
      }
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) router.push("/login");
    }
  }

  return (
    <button onClick={toggle}
            className="rounded bg-zinc-800 px-5 py-2 text-sm font-semibold hover:bg-zinc-700">
      {inList ? "✓ In My List" : "+ My List"}
    </button>
  );
}
```

- [ ] **Step 3: Create `frontend/src/app/series/[slug]/page.tsx`**

```tsx
import Link from "next/link";
import { notFound } from "next/navigation";
import EpisodeGrid from "@/components/EpisodeGrid";
import WatchlistButton from "@/components/WatchlistButton";
import { serverFetch } from "@/lib/api-server";
import type { SeriesDetail } from "@/lib/types";

export default async function SeriesPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const series = await serverFetch<SeriesDetail>(`/api/v1/series/${slug}`);
  if (!series) notFound();
  return (
    <div className="mx-auto max-w-6xl pb-16">
      <div className="relative h-64 w-full overflow-hidden sm:h-80">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src={series.banner_url} alt={series.title} className="h-full w-full object-cover" />
        <div className="absolute inset-0 bg-gradient-to-t from-zinc-950 to-transparent" />
      </div>
      <div className="px-4">
        <h1 className="mt-4 text-3xl font-extrabold">{series.title}</h1>
        <p className="mt-1 text-sm text-zinc-400">
          {series.genres.join(" · ")} · {series.episode_count} episodes ·
          first {series.free_episode_count} free
        </p>
        <p className="mt-3 max-w-2xl text-zinc-300">{series.synopsis}</p>
        <div className="mt-4 flex gap-2">
          <Link href={`/watch/${series.slug}/1`}
                className="rounded bg-rose-600 px-5 py-2 text-sm font-semibold hover:bg-rose-500">
            ▶ Play Ep 1
          </Link>
          <WatchlistButton seriesId={series.id} />
        </div>
        <h2 className="mb-3 mt-8 text-lg font-bold">Episodes</h2>
        <EpisodeGrid series={series} />
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Verify** — build passes; clicking a home card opens the series page; locked episodes show the lock overlay for a guest.

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat(frontend): series detail page with episode grid and watchlist button"
```

---

### Task 16: Watch page — vertical player, paywall, progress, auto-advance

**Files:**
- Create: `frontend/src/app/watch/[slug]/[ep]/page.tsx`, `frontend/src/components/Player.tsx`, `frontend/src/components/Paywall.tsx`

**Interfaces:**
- Consumes: `serverFetch` (series detail), `apiFetch` (`PlaybackInfo`, progress PUT), `hls.js`, `ApiError`.
- Produces: `/watch/[slug]/[ep]` route. Player behavior: native controls + custom prev/next, resume from `resume_position`, PUT progress every 5s and on unmount, auto-advance to next episode on end (marks completed), paywall overlay on 403 `subscription_required`.

- [ ] **Step 1: Create `frontend/src/components/Paywall.tsx`**

```tsx
import Link from "next/link";

export default function Paywall({ seriesSlug, poster }: { seriesSlug: string; poster: string }) {
  return (
    <div className="relative flex h-full w-full items-center justify-center overflow-hidden rounded-xl">
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img src={poster} alt="" className="absolute inset-0 h-full w-full object-cover opacity-20 blur-sm" />
      <div className="relative z-10 mx-6 text-center">
        <div className="text-5xl">🔒</div>
        <h2 className="mt-3 text-xl font-bold">Subscribe to keep watching</h2>
        <p className="mt-1 text-sm text-zinc-400">
          You&apos;ve reached the end of the free episodes for this series.
        </p>
        <div className="mt-5 flex flex-col gap-2">
          <Link href="/plans" className="rounded bg-rose-600 px-6 py-2.5 font-semibold hover:bg-rose-500">
            View Plans
          </Link>
          <Link href={`/login?next=/series/${seriesSlug}`} className="text-sm text-zinc-400 hover:text-white">
            Already subscribed? Log in
          </Link>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Create `frontend/src/components/Player.tsx`**

```tsx
"use client";

import Hls from "hls.js";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import Paywall from "@/components/Paywall";
import { apiFetch, ApiError } from "@/lib/api-client";
import type { PlaybackInfo, SeriesDetail } from "@/lib/types";

export default function Player({ series, episodeNumber }: {
  series: SeriesDetail; episodeNumber: number;
}) {
  const episode = series.episodes.find((e) => e.episode_number === episodeNumber);
  const videoRef = useRef<HTMLVideoElement>(null);
  const lastSaved = useRef(0);
  const router = useRouter();
  const [state, setState] = useState<"loading" | "playing" | "locked" | "error">("loading");
  const [info, setInfo] = useState<PlaybackInfo | null>(null);

  const hasNext = series.episodes.some((e) => e.episode_number === episodeNumber + 1);
  const hasPrev = episodeNumber > 1;

  const saveProgress = useCallback((position: number, completed: boolean) => {
    if (!episode) return;
    apiFetch(`/api/v1/progress/${episode.id}`, {
      method: "PUT",
      body: JSON.stringify({ position_seconds: Math.floor(position), completed }),
    }).catch(() => {}); // guests: 401 is fine, just don't save
  }, [episode]);

  useEffect(() => {
    if (!episode) { setState("error"); return; }
    let hls: Hls | null = null;
    let cancelled = false;
    setState("loading");
    apiFetch<PlaybackInfo>(`/api/v1/episodes/${episode.id}/playback`)
      .then((playback) => {
        if (cancelled) return;
        setInfo(playback);
        const video = videoRef.current;
        if (!video) return;
        if (video.canPlayType("application/vnd.apple.mpegurl")) {
          video.src = playback.url;
        } else if (Hls.isSupported()) {
          hls = new Hls({ xhrSetup: (xhr) => { xhr.withCredentials = true; } });
          hls.loadSource(playback.url);
          hls.attachMedia(video);
          hls.on(Hls.Events.ERROR, (_evt, data) => {
            if (data.fatal) setState("error");
          });
        } else {
          setState("error");
          return;
        }
        video.addEventListener("loadedmetadata", () => {
          if (playback.resume_position > 0 && playback.resume_position < video.duration - 2) {
            video.currentTime = playback.resume_position;
          }
          video.play().catch(() => {});
        }, { once: true });
        setState("playing");
      })
      .catch((err) => {
        if (cancelled) return;
        if (err instanceof ApiError && err.code === "subscription_required") setState("locked");
        else setState("error");
      });
    return () => {
      cancelled = true;
      const video = videoRef.current;
      if (video && video.currentTime > 0) saveProgress(video.currentTime, false);
      hls?.destroy();
    };
  }, [episode, saveProgress]);

  function onTimeUpdate() {
    const video = videoRef.current;
    if (!video) return;
    if (video.currentTime - lastSaved.current >= 5) {
      lastSaved.current = video.currentTime;
      saveProgress(video.currentTime, false);
    }
  }

  function onEnded() {
    const video = videoRef.current;
    if (video) saveProgress(video.duration, true);
    if (hasNext) router.push(`/watch/${series.slug}/${episodeNumber + 1}`);
    else router.push(`/series/${series.slug}`);
  }

  return (
    <div className="mx-auto flex h-[calc(100dvh-56px)] max-w-md flex-col px-2 py-2">
      <div className="flex items-center justify-between py-2 text-sm">
        <Link href={`/series/${series.slug}`} className="text-zinc-400 hover:text-white">
          ← {series.title}
        </Link>
        <span className="text-zinc-400">
          Ep {episodeNumber} / {series.episode_count}
        </span>
      </div>
      <div className="relative min-h-0 flex-1 rounded-xl bg-black">
        {state === "locked" && <Paywall seriesSlug={series.slug} poster={series.poster_url} />}
        {state === "error" && (
          <div className="flex h-full items-center justify-center text-zinc-400">
            Playback failed.{" "}
            <button className="ml-2 underline" onClick={() => window.location.reload()}>Retry</button>
          </div>
        )}
        {(state === "playing" || state === "loading") && (
          <video ref={videoRef} controls playsInline
                 onTimeUpdate={onTimeUpdate} onEnded={onEnded}
                 className="h-full w-full rounded-xl object-contain" />
        )}
      </div>
      <div className="flex items-center justify-between py-3">
        <button disabled={!hasPrev}
                onClick={() => router.push(`/watch/${series.slug}/${episodeNumber - 1}`)}
                className="rounded bg-zinc-800 px-4 py-2 text-sm disabled:opacity-40 hover:bg-zinc-700">
          ← Prev
        </button>
        <span className="text-sm text-zinc-400">{info ? episode?.title : ""}</span>
        <button disabled={!hasNext}
                onClick={() => router.push(`/watch/${series.slug}/${episodeNumber + 1}`)}
                className="rounded bg-zinc-800 px-4 py-2 text-sm disabled:opacity-40 hover:bg-zinc-700">
          Next →
        </button>
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Create `frontend/src/app/watch/[slug]/[ep]/page.tsx`**

```tsx
import { notFound } from "next/navigation";
import Player from "@/components/Player";
import { serverFetch } from "@/lib/api-server";
import type { SeriesDetail } from "@/lib/types";

export default async function WatchPage({ params }: {
  params: Promise<{ slug: string; ep: string }>;
}) {
  const { slug, ep } = await params;
  const episodeNumber = Number(ep);
  const series = await serverFetch<SeriesDetail>(`/api/v1/series/${slug}`);
  if (!series || !Number.isInteger(episodeNumber) || episodeNumber < 1) notFound();
  if (!series.episodes.some((e) => e.episode_number === episodeNumber)) notFound();
  return <Player series={series} episodeNumber={episodeNumber} />;
}
```

- [ ] **Step 4: Verify manually** (backend + seed + frontend running):
  - Free episode plays (video + audio), resume works after seeking then reloading.
  - Ep 3+ as guest shows the paywall (not an error state).
  - Auto-advance: let an episode finish → lands on the next one.
  - Prev/Next buttons navigate; last episode's "Next" is disabled.
  - `npm run build` passes.

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat(frontend): vertical HLS player with resume, auto-advance, progress saving and paywall"
```

---

### Task 17: Plans page (Razorpay checkout) + account page

**Files:**
- Create: `frontend/src/components/PlanCards.tsx`, `frontend/src/app/plans/page.tsx`, `frontend/src/components/CancelSubscription.tsx`, `frontend/src/app/account/page.tsx`

**Interfaces:**
- Consumes: `serverFetch`, `apiFetch`, `Plan`, `CurrentSubscription`, `User`; Razorpay checkout script `https://checkout.razorpay.com/v1/checkout.js`.
- Produces: `/plans` (subscribe flow) and `/account` (profile, subscription status, cancel).

- [ ] **Step 1: Create `frontend/src/components/PlanCards.tsx`**

```tsx
"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { apiFetch, ApiError } from "@/lib/api-client";
import type { CurrentSubscription, Plan } from "@/lib/types";

declare global {
  interface Window { Razorpay?: new (options: Record<string, unknown>) => { open: () => void } }
}

function loadRazorpay(): Promise<boolean> {
  return new Promise((resolve) => {
    if (window.Razorpay) return resolve(true);
    const s = document.createElement("script");
    s.src = "https://checkout.razorpay.com/v1/checkout.js";
    s.onload = () => resolve(true);
    s.onerror = () => resolve(false);
    document.body.appendChild(s);
  });
}

export default function PlanCards({ plans }: { plans: Plan[] }) {
  const router = useRouter();
  const [busy, setBusy] = useState<number | null>(null);
  const [error, setError] = useState("");

  async function pollActivation(tries = 10): Promise<boolean> {
    for (let i = 0; i < tries; i++) {
      const sub = await apiFetch<CurrentSubscription | null>("/api/v1/subscriptions/current")
        .catch(() => null);
      if (sub) return true;
      await new Promise((r) => setTimeout(r, 2000));
    }
    return false;
  }

  async function subscribe(planId: number) {
    setBusy(planId);
    setError("");
    try {
      const res = await apiFetch<{ razorpay_subscription_id: string; razorpay_key_id: string }>(
        "/api/v1/subscriptions", { method: "POST", body: JSON.stringify({ plan_id: planId }) });
      if (!(await loadRazorpay()) || !window.Razorpay) {
        setError("Could not load the payment window. Check your connection.");
        return;
      }
      new window.Razorpay({
        key: res.razorpay_key_id,
        subscription_id: res.razorpay_subscription_id,
        name: "ShortReel",
        description: "Unlimited short dramas",
        theme: { color: "#e11d48" },
        handler: async () => {
          await pollActivation();
          window.location.href = "/account";
        },
      }).open();
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        router.push("/login?next=/plans");
      } else if (err instanceof ApiError && err.code === "already_subscribed") {
        setError("You already have an active subscription.");
      } else {
        setError(err instanceof ApiError ? err.message : "Could not start checkout");
      }
    } finally {
      setBusy(null);
    }
  }

  return (
    <div>
      <div className="grid gap-4 sm:grid-cols-3">
        {plans.map((p) => (
          <div key={p.id} className="rounded-xl border border-zinc-800 bg-zinc-900 p-6">
            <h3 className="text-lg font-bold">{p.name}</h3>
            <p className="mt-2 text-3xl font-extrabold">
              ₹{(p.price_inr / 100).toFixed(0)}
              <span className="text-sm font-normal text-zinc-400"> / {p.interval.replace("ly", "")}</span>
            </p>
            <ul className="mt-4 space-y-1 text-sm text-zinc-400">
              <li>✓ All episodes, every series</li>
              <li>✓ New releases daily</li>
              <li>✓ Cancel anytime</li>
            </ul>
            <button onClick={() => subscribe(p.id)} disabled={busy !== null}
                    className="mt-5 w-full rounded bg-rose-600 py-2 font-semibold hover:bg-rose-500 disabled:opacity-50">
              {busy === p.id ? "Opening checkout..." : "Subscribe"}
            </button>
          </div>
        ))}
      </div>
      {error && <p className="mt-4 text-sm text-rose-400">{error}</p>}
    </div>
  );
}
```

- [ ] **Step 2: Create `frontend/src/app/plans/page.tsx`**

```tsx
import PlanCards from "@/components/PlanCards";
import { serverFetch } from "@/lib/api-server";
import type { Plan } from "@/lib/types";

export default async function PlansPage() {
  const plans = (await serverFetch<Plan[]>("/api/v1/plans")) ?? [];
  return (
    <div className="mx-auto max-w-4xl px-4 py-12">
      <h1 className="text-3xl font-extrabold">Watch everything. One plan.</h1>
      <p className="mt-2 text-zinc-400">
        First episodes of every series are always free. Subscribe to unlock the rest.
      </p>
      <div className="mt-8">
        <PlanCards plans={plans} />
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Create `frontend/src/components/CancelSubscription.tsx`**

```tsx
"use client";

import { useState } from "react";
import { apiFetch, ApiError } from "@/lib/api-client";

export default function CancelSubscription() {
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);

  async function cancel() {
    if (!confirm("Cancel your subscription? You keep access until the period ends.")) return;
    setBusy(true);
    try {
      const res = await apiFetch<{ message: string }>("/api/v1/subscriptions/cancel", { method: "POST" });
      setMessage(res.message);
    } catch (err) {
      setMessage(err instanceof ApiError ? err.message : "Could not cancel");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mt-3">
      <button onClick={cancel} disabled={busy}
              className="rounded bg-zinc-800 px-4 py-2 text-sm hover:bg-zinc-700 disabled:opacity-50">
        Cancel subscription
      </button>
      {message && <p className="mt-2 text-sm text-zinc-400">{message}</p>}
    </div>
  );
}
```

- [ ] **Step 4: Create `frontend/src/app/account/page.tsx`**

```tsx
import Link from "next/link";
import { redirect } from "next/navigation";
import CancelSubscription from "@/components/CancelSubscription";
import { serverFetch } from "@/lib/api-server";
import type { ContinueItem, CurrentSubscription, User } from "@/lib/types";

export default async function AccountPage() {
  const user = await serverFetch<User>("/api/v1/auth/me");
  if (!user) redirect("/login?next=/account");
  const sub = await serverFetch<CurrentSubscription | null>("/api/v1/subscriptions/current");
  const history = (await serverFetch<ContinueItem[]>("/api/v1/progress/continue-watching")) ?? [];

  return (
    <div className="mx-auto max-w-3xl px-4 py-10">
      <h1 className="text-2xl font-bold">Account</h1>
      <div className="mt-4 rounded-xl border border-zinc-800 bg-zinc-900 p-5">
        <p className="font-medium">{user.name}</p>
        <p className="text-sm text-zinc-400">{user.email}</p>
      </div>

      <h2 className="mt-8 text-lg font-bold">Subscription</h2>
      <div className="mt-3 rounded-xl border border-zinc-800 bg-zinc-900 p-5">
        {sub ? (
          <>
            <p className="font-medium">
              {sub.plan.name} — ₹{(sub.plan.price_inr / 100).toFixed(0)}/{sub.plan.interval.replace("ly", "")}
            </p>
            <p className="mt-1 text-sm text-zinc-400">
              Status: {sub.status}
              {sub.current_period_end &&
                ` · renews/ends ${new Date(sub.current_period_end).toLocaleDateString()}`}
            </p>
            {sub.status === "active" && <CancelSubscription />}
          </>
        ) : (
          <p className="text-sm text-zinc-400">
            No active subscription.{" "}
            <Link href="/plans" className="text-rose-400">See plans</Link>
          </p>
        )}
      </div>

      <h2 className="mt-8 text-lg font-bold">Watch history</h2>
      {history.length === 0 ? (
        <p className="mt-3 text-sm text-zinc-400">Nothing yet — go watch something!</p>
      ) : (
        <ul className="mt-3 space-y-2">
          {history.map((h) => (
            <li key={h.episode_id}>
              <Link href={`/watch/${h.series.slug}/${h.episode_number}`}
                    className="text-sm text-zinc-300 hover:text-white">
                {h.series.title} — Ep {h.episode_number} ({h.position_seconds}s in)
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
```

- [ ] **Step 5: Verify** — build passes. Manual: guest clicking Subscribe is sent to login; logged-in user with dummy Razorpay keys sees checkout fail gracefully with the error message (real keys make it open the Razorpay modal). Account page shows profile + "No active subscription".

To verify the full paid flow without real payments: activate manually by simulating the webhook (documented in README, Task 19) —

```bash
cd backend && .venv/Scripts/python -c "import hashlib, hmac, json, time, httpx; from app.config import settings; body=json.dumps({'event':'subscription.activated','payload':{'subscription':{'entity':{'id':'SUB_ID_HERE','current_start':int(time.time()),'current_end':int(time.time())+2592000}}}}).encode(); sig=hmac.new(settings.razorpay_webhook_secret.encode(), body, hashlib.sha256).hexdigest(); print(httpx.post('http://localhost:8000/api/v1/webhooks/razorpay', content=body, headers={'X-Razorpay-Signature':sig,'X-Razorpay-Event-Id':'evt_manual1','Content-Type':'application/json'}).text)"
```

(replace `SUB_ID_HERE` with the `razorpay_subscription_id` printed in the subscriptions table). After this, locked episodes play and Account shows the active plan.

- [ ] **Step 6: Commit**

```bash
git add -A && git commit -m "feat(frontend): plans page with Razorpay checkout and account page with cancel"
```

---

### Task 18: Search, genre, and my-list pages

**Files:**
- Create: `frontend/src/app/search/page.tsx`, `frontend/src/app/genre/[slug]/page.tsx`, `frontend/src/app/my-list/page.tsx`

**Interfaces:**
- Consumes: `apiFetch`, `serverFetch`, `SeriesCard`, `SeriesSummary`, `GenreOut`.

- [ ] **Step 1: Create `frontend/src/app/search/page.tsx`**

```tsx
"use client";

import { useEffect, useState } from "react";
import SeriesCard from "@/components/SeriesCard";
import { apiFetch } from "@/lib/api-client";
import type { SeriesSummary } from "@/lib/types";

export default function SearchPage() {
  const [q, setQ] = useState("");
  const [results, setResults] = useState<SeriesSummary[]>([]);
  const [searched, setSearched] = useState(false);

  useEffect(() => {
    const query = q.trim();
    if (!query) { setResults([]); setSearched(false); return; }
    const t = setTimeout(() => {
      apiFetch<SeriesSummary[]>(`/api/v1/search?q=${encodeURIComponent(query)}`)
        .then((r) => { setResults(r); setSearched(true); })
        .catch(() => setResults([]));
    }, 300);
    return () => clearTimeout(t);
  }, [q]);

  return (
    <div className="mx-auto max-w-6xl px-4 py-8">
      <input autoFocus value={q} onChange={(e) => setQ(e.target.value)}
             placeholder="Search series..."
             className="w-full rounded-lg border border-zinc-700 bg-zinc-900 px-4 py-3 outline-none focus:border-rose-500" />
      <div className="mt-6 flex flex-wrap gap-3">
        {results.map((s) => <SeriesCard key={s.id} series={s} />)}
      </div>
      {searched && results.length === 0 && (
        <p className="mt-6 text-zinc-400">No results for &quot;{q}&quot;</p>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Create `frontend/src/app/genre/[slug]/page.tsx`**

```tsx
import { notFound } from "next/navigation";
import SeriesCard from "@/components/SeriesCard";
import { serverFetch } from "@/lib/api-server";
import type { GenreOut, SeriesSummary } from "@/lib/types";

export default async function GenrePage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const data = await serverFetch<{ genre: GenreOut; series: SeriesSummary[] }>(
    `/api/v1/genres/${slug}/series`);
  if (!data) notFound();
  return (
    <div className="mx-auto max-w-6xl px-4 py-8">
      <h1 className="text-2xl font-bold">{data.genre.name}</h1>
      <div className="mt-6 flex flex-wrap gap-3">
        {data.series.map((s) => <SeriesCard key={s.id} series={s} />)}
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Create `frontend/src/app/my-list/page.tsx`**

```tsx
import Link from "next/link";
import { redirect } from "next/navigation";
import SeriesCard from "@/components/SeriesCard";
import { serverFetch } from "@/lib/api-server";
import type { SeriesSummary, User } from "@/lib/types";

export default async function MyListPage() {
  const user = await serverFetch<User>("/api/v1/auth/me");
  if (!user) redirect("/login?next=/my-list");
  const items = (await serverFetch<SeriesSummary[]>("/api/v1/watchlist")) ?? [];
  return (
    <div className="mx-auto max-w-6xl px-4 py-8">
      <h1 className="text-2xl font-bold">My List</h1>
      {items.length === 0 ? (
        <p className="mt-6 text-zinc-400">
          Your list is empty. <Link href="/" className="text-rose-400">Find something to watch</Link>
        </p>
      ) : (
        <div className="mt-6 flex flex-wrap gap-3">
          {items.map((s) => <SeriesCard key={s.id} series={s} />)}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 4: Verify** — build passes; search finds seeded titles; genre pages open from home rails (add genre links later if desired — rails already group by genre); my-list shows saved series.

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat(frontend): search, genre, and my-list pages"
```

---

### Task 19: README + end-to-end verification checklist

**Files:**
- Create: `README.md` (repo root)

**Interfaces:** none (documentation).

- [ ] **Step 1: Write `README.md`** covering, with exact commands:
  - What this is (one paragraph + screenshot placeholder).
  - Prereqs: Python 3.11+, Node 20+, FFmpeg (`winget install Gyan.FFmpeg`).
  - Backend setup: venv, `pip install -r requirements.txt`, `alembic upgrade head`, `python -m app.seed`, `uvicorn app.main:app --reload --port 8000`.
  - Frontend setup: `npm install`, `.env.local` contents, `npm run dev`.
  - Environment variables table (all Settings keys, which are optional, dev defaults).
  - Going to production: switching `DATABASE_URL` to Neon pooled + `DIRECT_DATABASE_URL` for Alembic; `STORAGE_MODE=s3` + S3/CloudFront setup summary (bucket, distribution with the API's signed-cookie key pair, `CDN_COOKIE_DOMAIN`); real Razorpay keys + creating plans in the dashboard and updating `plans.razorpay_plan_id`; ImageKit keys; setting the Razorpay webhook URL to `https://api.<domain>/api/v1/webhooks/razorpay`.
  - The manual webhook-simulation command from Task 17 for testing the paid flow locally.
  - Ingest usage: the `python -m app.ingest ...` command with all flags.

- [ ] **Step 2: Full E2E verification pass** — with backend (seeded) + frontend running, walk through and confirm:
  1. Home: hero rotates, rails render.
  2. Guest plays Ep 1 of a featured series; video + audio play; seek; reload → resumes only after login (guests don't persist).
  3. Guest hits Ep 3 → paywall.
  4. Sign up → play Ep 1 → progress saves (home shows Continue Watching).
  5. Subscribe (with dummy keys: graceful error; simulate webhook per Task 17) → Ep 3 plays.
  6. Account: shows plan; cancel works (fake client in dev will fail Razorpay call — with dummy keys expect the error message; acceptable).
  7. My List add/remove; search finds titles; genre page renders.
  8. `cd backend && python -m pytest -q` green; `cd frontend && npm run build` green.
- [ ] **Step 3: Fix anything found, then commit**

```bash
git add -A && git commit -m "docs: README with setup, production, and verification guide"
```

---

## Post-plan notes for the executor

- Tasks 1–11 are backend-only and independent of Node; Tasks 12–19 need the backend running for manual verification but only `npm run build` as a hard gate.
- Cross-cutting invariants come from **Global Constraints** — especially the error envelope and the entitlement rule; if a task's code and a constraint conflict, the constraint wins and the discrepancy should be flagged in the task report.
- Windows notes: venv scripts live in `.venv/Scripts/`; use `python -m pytest` / `python -m uvicorn` forms if PATH issues arise; FFmpeg via `winget install Gyan.FFmpeg` then restart the shell.
