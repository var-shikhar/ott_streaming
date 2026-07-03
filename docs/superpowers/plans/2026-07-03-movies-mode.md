# Movies Mode Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Netflix/Pocket-Films-style Movies mode (browse, rich detail pages with cast/stills, landscape fullscreen player) alongside the existing reels mode, per `docs/superpowers/specs/2026-07-03-movies-mode-design.md`.

**Architecture:** Movies reuse the `Series`/`Episode` tables discriminated by a new `content_type` column (a movie = 1 series row + exactly 1 landscape episode, `episode_number=1`), with new `credits`/`stills` satellite tables. Reels API surfaces filter to `content_type="series"`; new `/api/v1/movies/*` endpoints serve the movies mode. Frontend gets `/movies` routes (route = mode, no cookie), a Reels|Movies switcher in TopBar, and a new `MoviePlayer` built on a `useHlsPlayback` hook extracted from `EpisodeSlide`.

**Tech Stack:** FastAPI + SQLAlchemy 2 (sync) + Alembic + pytest (in-memory SQLite); Next.js 16 App Router + Tailwind v4 + hls.js.

## Global Constraints

- API errors always `{"error": {code, message}}`; 403 code `subscription_required` drives the paywall.
- Entitlement lives ONLY in `backend/app/entitlement.py` — never inline the rule. (Movie paywall reuses it: episode 1 free iff `free_episode_count >= 1`.)
- Models use cross-database types only (tests run on in-memory SQLite).
- Master playlists list the LOWEST rendition first (ascending bitrate) — renderer freezes otherwise.
- Only one hls.js player attached at a time (reels: only the ACTIVE slide).
- Never store machine-local URLs in the DB (thumbnails/stills: ImageKit or picsum placeholder).
- Money = INR paise; timestamps = UTC.
- Backend commands run from `backend/` with `.venv/Scripts/python`; frontend gate is `npm run build` from `frontend/`.
- Next.js 16: route params are Promises (`const { slug } = await params`). Plain `<img>` (never next/image) with `{/* eslint-disable-next-line @next/next/no-img-element */}`.
- Styling: zinc-950 surfaces, rose-600 primary accent, `active:` states (mobile), phone-shell max-w-md.

## File Structure

**Backend**
- Modify `backend/app/models.py` — Series columns + `Credit`, `Still` models
- Create `backend/alembic/versions/c47d21e9a3f0_movies_mode.py` — migration
- Modify `backend/app/routers/catalog.py` — `series_out` fields, `published(content_type)`, `_home_payload`, movies endpoints
- Modify `backend/app/transcode.py` — orientation-aware ladder + `write_master_playlist` + `extract_frame`
- Modify `backend/app/ingest.py` — movie flags, `upload_image`, credits/stills
- Modify `backend/app/seed.py` — 4 seeded movies
- Create `backend/tests/test_movies.py`; modify `backend/tests/test_transcode.py`, `backend/tests/test_catalog.py`

**Frontend**
- Modify `frontend/src/lib/types.ts` — content_type fields, `Credit`, `MovieDetail`
- Create `frontend/src/components/MovieCard.tsx`, `MovieRail.tsx`, `MovieHero.tsx`, `CastList.tsx`, `StillsGallery.tsx`, `MoviePlayer.tsx`
- Create `frontend/src/lib/use-hls-playback.ts` — extracted hook
- Create `frontend/src/app/movies/page.tsx` + `loading.tsx`, `frontend/src/app/movies/[slug]/page.tsx` + `loading.tsx`, `frontend/src/app/movies/[slug]/watch/page.tsx` + `loading.tsx`
- Modify `frontend/src/components/TopBar.tsx`, `BottomNav.tsx`, `Paywall.tsx`, `EpisodeSlide.tsx`
- Modify `frontend/src/app/search/page.tsx`, `my-list/page.tsx`, `account/page.tsx`, `plans/page.tsx`, `frontend/src/components/PlanCards.tsx`, `frontend/src/app/manifest.ts`

**Docs:** modify `docs/architecture.md`, `docs/api-reference.md`, `docs/content-ingestion.md`, `CLAUDE.md`

---

### Task 1: Models + migration (`content_type`, `Credit`, `Still`)

**Files:**
- Modify: `backend/app/models.py`
- Create: `backend/alembic/versions/c47d21e9a3f0_movies_mode.py`
- Test: `backend/tests/test_models.py` (append)

**Interfaces:**
- Produces: `Series.content_type: str` ("series"|"movie", default "series"), `Series.release_year: int|None`, `Series.maturity_rating: str` (default ""), `Series.credits: list[Credit]` (ordered by `display_order`), `Series.stills: list[Still]` (ordered by `display_order`); `Credit(series_id, person_name, role, character_name, display_order)`; `Still(series_id, image_url, display_order)`.

- [ ] **Step 1: Write the failing test** — append to `backend/tests/test_models.py`:

```python
def test_movie_with_credits_and_stills(db):
    m = models.Series(slug="daal", title="Daal", content_type="movie",
                      release_year=2025, maturity_rating="U/A 13+", free_episode_count=0)
    db.add(m)
    db.flush()
    db.add_all([
        models.Credit(series_id=m.id, person_name="Riya Sen", role="cast",
                      character_name="Asha", display_order=1),
        models.Credit(series_id=m.id, person_name="Arjun Mehta", role="director", display_order=0),
        models.Still(series_id=m.id, image_url="https://ik.io/a.jpg", display_order=1),
        models.Still(series_id=m.id, image_url="https://ik.io/b.jpg", display_order=0),
    ])
    db.commit()
    db.expire_all()
    row = db.query(models.Series).filter_by(slug="daal").one()
    assert row.content_type == "movie" and row.release_year == 2025
    assert [c.role for c in row.credits] == ["director", "cast"]  # display_order
    assert [s.image_url for s in row.stills] == ["https://ik.io/b.jpg", "https://ik.io/a.jpg"]


def test_series_defaults_to_series_content_type(db):
    s = models.Series(slug="plain", title="Plain")
    db.add(s)
    db.commit()
    assert s.content_type == "series" and s.maturity_rating == "" and s.release_year is None
```

(Check the top of `test_models.py` — it already imports `from app import models`; reuse the existing `db` fixture from `conftest.py`.)

- [ ] **Step 2: Run to verify failure**

Run (from `backend/`): `.venv/Scripts/python -m pytest tests/test_models.py -q`
Expected: FAIL — `AttributeError: ... has no attribute 'Credit'` (or TypeError on `content_type=`).

- [ ] **Step 3: Implement models** — in `backend/app/models.py`, add to `Series` (after `status` line):

```python
    content_type: Mapped[str] = mapped_column(sa.String(10), default="series", index=True)
    # series|movie — a movie is one Series row + exactly one landscape Episode (episode_number=1)
    release_year: Mapped[int | None] = mapped_column(nullable=True)
    maturity_rating: Mapped[str] = mapped_column(sa.String(20), default="")
```

and after the `episodes` relationship:

```python
    credits: Mapped[list["Credit"]] = relationship(
        back_populates="series", order_by="Credit.display_order", lazy="selectin")
    stills: Mapped[list["Still"]] = relationship(
        back_populates="series", order_by="Still.display_order", lazy="selectin")
```

New models after `Episode`:

```python
class Credit(Base):
    __tablename__ = "credits"
    id: Mapped[int] = mapped_column(primary_key=True)
    series_id: Mapped[uuid.UUID] = mapped_column(sa.ForeignKey("series.id"), index=True)
    person_name: Mapped[str] = mapped_column(sa.String(120))
    role: Mapped[str] = mapped_column(sa.String(30), default="cast")  # director|cast|writer|producer
    character_name: Mapped[str] = mapped_column(sa.String(120), default="")
    display_order: Mapped[int] = mapped_column(default=0)

    series: Mapped["Series"] = relationship(back_populates="credits")


class Still(Base):
    __tablename__ = "stills"
    id: Mapped[int] = mapped_column(primary_key=True)
    series_id: Mapped[uuid.UUID] = mapped_column(sa.ForeignKey("series.id"), index=True)
    image_url: Mapped[str] = mapped_column(sa.String(500))
    display_order: Mapped[int] = mapped_column(default=0)

    series: Mapped["Series"] = relationship(back_populates="stills")
```

- [ ] **Step 4: Run tests** — `.venv/Scripts/python -m pytest tests/test_models.py -q` → PASS; then full suite `.venv/Scripts/python -m pytest -q` → all pass.

- [ ] **Step 5: Write the migration** — create `backend/alembic/versions/c47d21e9a3f0_movies_mode.py`:

```python
"""movies mode: content_type, credits, stills

Revision ID: c47d21e9a3f0
Revises: 98abc6d56da0
Create Date: 2026-07-03

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'c47d21e9a3f0'
down_revision: Union[str, Sequence[str], None] = '98abc6d56da0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('series', sa.Column('content_type', sa.String(length=10),
                                      nullable=False, server_default='series'))
    op.create_index(op.f('ix_series_content_type'), 'series', ['content_type'], unique=False)
    op.add_column('series', sa.Column('release_year', sa.Integer(), nullable=True))
    op.add_column('series', sa.Column('maturity_rating', sa.String(length=20),
                                      nullable=False, server_default=''))
    op.create_table('credits',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('series_id', sa.Uuid(), nullable=False),
        sa.Column('person_name', sa.String(length=120), nullable=False),
        sa.Column('role', sa.String(length=30), nullable=False),
        sa.Column('character_name', sa.String(length=120), nullable=False),
        sa.Column('display_order', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['series_id'], ['series.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_credits_series_id'), 'credits', ['series_id'], unique=False)
    op.create_table('stills',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('series_id', sa.Uuid(), nullable=False),
        sa.Column('image_url', sa.String(length=500), nullable=False),
        sa.Column('display_order', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['series_id'], ['series.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_stills_series_id'), 'stills', ['series_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_stills_series_id'), table_name='stills')
    op.drop_table('stills')
    op.drop_index(op.f('ix_credits_series_id'), table_name='credits')
    op.drop_table('credits')
    op.drop_column('series', 'maturity_rating')
    op.drop_column('series', 'release_year')
    op.drop_index(op.f('ix_series_content_type'), table_name='series')
    op.drop_column('series', 'content_type')
```

- [ ] **Step 6: Apply migration to dev DB** — `.venv/Scripts/alembic upgrade head`. Expected: `Running upgrade 98abc6d56da0 -> c47d21e9a3f0`. **CAUTION:** `backend/.env` may point at Neon prod (per repo memory) — check `DATABASE_URL` in `backend/.env` first; the migration is additive (safe), but note in the task report which DB it ran against.

- [ ] **Step 7: Commit** — `git add backend/app/models.py backend/alembic/versions/c47d21e9a3f0_movies_mode.py backend/tests/test_models.py && git commit -m "feat(backend): content_type on series + credits/stills tables for movies mode"`

---

### Task 2: `series_out` additive fields + reels surfaces filter to series

**Files:**
- Modify: `backend/app/routers/catalog.py`
- Test: `backend/tests/test_catalog.py` (append), `backend/tests/test_movies.py` (create)

**Interfaces:**
- Consumes: Task 1 models.
- Produces: `series_out(s)` gains `content_type`, `release_year`, `maturity_rating`, `duration_seconds` (movie's ready ep-1 duration, else 0). `published(db, content_type: str | None = None)`. `_home_payload(db, user, content_type) -> dict` (used by Task 3). `/home`, `/series` return series only; `/genres/{slug}/series` gains `?content_type=` (default `"series"`); `/search` gains optional `?content_type=`.

- [ ] **Step 1: Write failing tests** — create `backend/tests/test_movies.py`:

```python
import uuid

from app import models


def seed_mixed(db):
    """One published series (3 ready eps) + one published movie + one draft movie."""
    g = models.Genre(slug="drama", name="Drama")
    db.add(g)
    s = models.Series(slug="ceo-bride", title="CEO's Secret Bride", free_episode_count=2,
                      view_count=100, is_featured=True, genres=[g])
    m = models.Series(slug="daal", title="Daal", content_type="movie", free_episode_count=0,
                      release_year=2025, maturity_rating="U/A 13+", view_count=500,
                      is_featured=True, genres=[g])
    draft = models.Series(slug="unreleased", title="Unreleased", content_type="movie",
                          status="draft")
    db.add_all([s, m, draft])
    db.flush()
    for n in (1, 2, 3):
        db.add(models.Episode(series_id=s.id, episode_number=n, status="ready",
                              title=f"Ep {n}", duration_seconds=60,
                              hls_path=f"{uuid.uuid4()}/master.m3u8"))
    db.add(models.Episode(series_id=m.id, episode_number=1, status="ready", title="Daal",
                          duration_seconds=1320, hls_path=f"{uuid.uuid4()}/master.m3u8"))
    db.commit()
    return s, m


def test_series_out_carries_movie_fields(client, db):
    seed_mixed(db)
    r = client.get("/api/v1/search", params={"q": "daal"})
    body = r.json()
    assert body[0]["content_type"] == "movie"
    assert body[0]["release_year"] == 2025
    assert body[0]["maturity_rating"] == "U/A 13+"
    assert body[0]["duration_seconds"] == 1320


def test_reels_home_excludes_movies(client, db):
    seed_mixed(db)
    body = client.get("/api/v1/home").json()
    for key in ("featured", "trending", "new_releases"):
        assert all(item["content_type"] == "series" for item in body[key]), key
    for rail in body["genre_rails"]:
        assert all(item["content_type"] == "series" for item in rail["series"])


def test_series_list_excludes_movies(client, db):
    seed_mixed(db)
    slugs = [s["slug"] for s in client.get("/api/v1/series").json()]
    assert "daal" not in slugs and "ceo-bride" in slugs


def test_search_content_type_filter(client, db):
    seed_mixed(db)
    # title "CEO's Secret Bride" and "Daal" don't overlap; use a common letter query
    both = client.get("/api/v1/search", params={"q": "a"}).json()
    assert {b["content_type"] for b in both} == {"series", "movie"}
    only_movies = client.get("/api/v1/search", params={"q": "a", "content_type": "movie"}).json()
    assert all(b["content_type"] == "movie" for b in only_movies) and only_movies


def test_genre_series_defaults_to_series_only(client, db):
    seed_mixed(db)
    body = client.get("/api/v1/genres/drama/series").json()
    assert [s["slug"] for s in body["series"]] == ["ceo-bride"]
    movies = client.get("/api/v1/genres/drama/series", params={"content_type": "movie"}).json()
    assert [s["slug"] for s in movies["series"]] == ["daal"]
```

- [ ] **Step 2: Run to verify failure** — `.venv/Scripts/python -m pytest tests/test_movies.py -q`. Expected: FAIL — `KeyError: 'content_type'`.

- [ ] **Step 3: Implement** in `backend/app/routers/catalog.py`. Replace `series_out` and `published`:

```python
def series_out(s: models.Series) -> dict:
    duration = 0
    if s.content_type == "movie":
        ep1 = next((e for e in ready_episodes(s) if e.episode_number == 1), None)
        duration = ep1.duration_seconds if ep1 else 0
    return {
        "id": str(s.id), "slug": s.slug, "title": s.title, "synopsis": s.synopsis,
        "language": s.language, "poster_url": s.poster_url, "banner_url": s.banner_url,
        "free_episode_count": s.free_episode_count, "is_featured": s.is_featured,
        "view_count": s.view_count, "genres": [g.name for g in s.genres],
        "episode_count": len(ready_episodes(s)),
        "content_type": s.content_type, "release_year": s.release_year,
        "maturity_rating": s.maturity_rating, "duration_seconds": duration,
    }


def published(db: Session, content_type: str | None = None):
    q = db.query(models.Series).filter(models.Series.status == "published")
    if content_type:
        q = q.filter(models.Series.content_type == content_type)
    return q
```

Refactor `home()` into a shared payload builder (movies home reuses it in Task 3):

```python
def _home_payload(db: Session, user, content_type: str) -> dict:
    all_series = published(db, content_type).all()
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
                  .order_by(models.WatchProgress.updated_at.desc()).limit(20).all())
        for row in rows:
            ep = row.episode
            if (ep.status == "ready" and ep.series.status == "published"
                    and ep.series.content_type == content_type):
                continue_watching.append({
                    "series": series_out(ep.series), "episode_number": ep.episode_number,
                    "episode_id": str(ep.id), "position_seconds": row.position_seconds,
                })
    return {"featured": featured, "trending": trending, "new_releases": new_releases,
            "genre_rails": genre_rails, "continue_watching": continue_watching[:10]}


@router.get("/home")
def home(db: Session = Depends(get_db), user=Depends(get_optional_user)):
    return _home_payload(db, user, "series")
```

Update the other reels surfaces:

```python
@router.get("/series")
def list_series(db: Session = Depends(get_db)):
    return [series_out(s)
            for s in published(db, "series").order_by(models.Series.published_at.desc()).all()]
```

`/genres/{slug}/series` — signature and filter:

```python
@router.get("/genres/{slug}/series")
def genre_series(slug: str, content_type: str = Query("series"),
                 db: Session = Depends(get_db)):
    g = db.query(models.Genre).filter(models.Genre.slug == slug).first()
    if not g:
        raise ApiError(404, "not_found", "Genre not found")
    items = [series_out(s) for s in published(db, content_type).all() if g in s.genres]
    return {"genre": {"slug": g.slug, "name": g.name}, "series": items}
```

`/search` — optional filter:

```python
@router.get("/search")
def search(q: str = Query(min_length=1), content_type: str | None = Query(None),
           db: Session = Depends(get_db)):
    pattern = f"%{q.lower()}%"
    rows = published(db, content_type).filter(models.Series.title.ilike(pattern)).limit(20).all()
    return [series_out(s) for s in rows]
```

Note: `series_detail` (`/series/{slug}`) is intentionally left serving any content_type (harmless; movie detail gets its own endpoint in Task 3).

- [ ] **Step 4: Run tests** — `.venv/Scripts/python -m pytest tests/test_movies.py tests/test_catalog.py -q` → PASS. Full suite `.venv/Scripts/python -m pytest -q` → all pass (existing `test_catalog.py` tests must keep passing — the refactor must not change reels shapes).

- [ ] **Step 5: Commit** — `git commit -am "feat(backend): content_type in series_out; reels surfaces filter to series"`

---

### Task 3: Movies endpoints (`/movies/home`, `/movies`, `/movies/{slug}`) + movie entitlement tests

**Files:**
- Modify: `backend/app/routers/catalog.py`
- Test: `backend/tests/test_movies.py` (append)

**Interfaces:**
- Consumes: `_home_payload`, `published`, `series_out`, `ready_episodes` from Task 2; `active_subscription` from `app.entitlement`.
- Produces: `GET /api/v1/movies/home` (same shape as `/home`); `GET /api/v1/movies` → `[series_out]`; `GET /api/v1/movies/{slug}` → `series_out + {episode: {id, duration_seconds, thumbnail_url, is_free, locked} | null, credits: [{person_name, role, character_name}], stills: [str], related: [series_out]}`.
- **Route-order constraint:** `/movies/home` MUST be registered before `/movies/{slug}`.

- [ ] **Step 1: Write failing tests** — append to `backend/tests/test_movies.py`:

```python
def test_movies_home_is_movies_only(client, db):
    seed_mixed(db)
    body = client.get("/api/v1/movies/home").json()
    assert [m["slug"] for m in body["featured"]] == ["daal"]
    assert all(m["content_type"] == "movie" for m in body["trending"])
    assert "unreleased" not in [m["slug"] for m in body["new_releases"]]  # draft excluded
    assert body["continue_watching"] == []


def test_movies_list(client, db):
    seed_mixed(db)
    assert [m["slug"] for m in client.get("/api/v1/movies").json()] == ["daal"]


def test_movie_detail_payload(client, db):
    _, m = seed_mixed(db)
    db.add_all([
        models.Credit(series_id=m.id, person_name="Arjun Mehta", role="director",
                      display_order=0),
        models.Credit(series_id=m.id, person_name="Riya Sen", role="cast",
                      character_name="Asha", display_order=1),
        models.Still(series_id=m.id, image_url="https://ik.io/b.jpg", display_order=0),
        models.Still(series_id=m.id, image_url="https://ik.io/a.jpg", display_order=1),
    ])
    db.commit()
    body = client.get("/api/v1/movies/daal").json()
    assert body["slug"] == "daal"
    assert body["episode"]["duration_seconds"] == 1320
    # premium movie (free_episode_count=0), guest → locked
    assert body["episode"]["is_free"] is False and body["episode"]["locked"] is True
    assert [c["role"] for c in body["credits"]] == ["director", "cast"]
    assert body["credits"][1]["character_name"] == "Asha"
    assert body["stills"] == ["https://ik.io/b.jpg", "https://ik.io/a.jpg"]
    assert isinstance(body["related"], list)


def test_movie_detail_404_for_series_slug_and_unknown(client, db):
    seed_mixed(db)
    assert client.get("/api/v1/movies/ceo-bride").status_code == 404
    assert client.get("/api/v1/movies/nope").status_code == 404


def test_free_movie_unlocked_for_guest(client, db):
    seed_mixed(db)
    free = models.Series(slug="free-film", title="Free Film", content_type="movie",
                         free_episode_count=1)
    db.add(free)
    db.flush()
    db.add(models.Episode(series_id=free.id, episode_number=1, status="ready",
                          duration_seconds=600, hls_path=f"{uuid.uuid4()}/master.m3u8"))
    db.commit()
    body = client.get("/api/v1/movies/free-film").json()
    assert body["episode"]["is_free"] is True and body["episode"]["locked"] is False


def test_related_movies_share_a_genre(client, db):
    _, m = seed_mixed(db)
    g2 = models.Genre(slug="comedy", name="Comedy")
    db.add(g2)
    drama_movie = models.Series(slug="sister-film", title="Sister Film", content_type="movie",
                                genres=[m.genres[0]])
    comedy_movie = models.Series(slug="other-film", title="Other Film", content_type="movie",
                                 genres=[g2])
    db.add_all([drama_movie, comedy_movie])
    db.flush()
    for mv in (drama_movie, comedy_movie):
        db.add(models.Episode(series_id=mv.id, episode_number=1, status="ready",
                              duration_seconds=300, hls_path=f"{uuid.uuid4()}/master.m3u8"))
    db.commit()
    related = client.get("/api/v1/movies/daal").json()["related"]
    slugs = [r["slug"] for r in related]
    assert "sister-film" in slugs and "other-film" not in slugs and "daal" not in slugs


def test_premium_movie_playback_403_for_guest(client, db):
    _, m = seed_mixed(db)
    ep_id = str(m.episodes[0].id)
    r = client.get(f"/api/v1/episodes/{ep_id}/playback")
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "subscription_required"


def test_free_movie_playback_ok_for_guest(client, db, tmp_path, monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "media_root", str(tmp_path))
    free = models.Series(slug="free-film", title="Free Film", content_type="movie",
                         free_episode_count=1)
    db.add(free)
    db.flush()
    ep = models.Episode(series_id=free.id, episode_number=1, status="ready",
                        duration_seconds=600, hls_path="x/master.m3u8")
    db.add(ep)
    db.commit()
    r = client.get(f"/api/v1/episodes/{ep.id}/playback")
    assert r.status_code == 200
    assert r.json()["resume_position"] == 0
```

(If `test_playback.py` already monkeypatches storage differently, mirror ITS pattern instead for the last test — check it before writing.)

- [ ] **Step 2: Run to verify failure** — `.venv/Scripts/python -m pytest tests/test_movies.py -q`. Expected: new tests FAIL with 404s on `/movies/...` routes.

- [ ] **Step 3: Implement** — append to `backend/app/routers/catalog.py` (AFTER the `search` route; `/movies/home` and `/movies` must be declared before `/movies/{slug}`):

```python
@router.get("/movies/home")
def movies_home(db: Session = Depends(get_db), user=Depends(get_optional_user)):
    return _home_payload(db, user, "movie")


@router.get("/movies")
def list_movies(db: Session = Depends(get_db)):
    return [series_out(s)
            for s in published(db, "movie").order_by(models.Series.published_at.desc()).all()]


@router.get("/movies/{slug}")
def movie_detail(slug: str, db: Session = Depends(get_db), user=Depends(get_optional_user)):
    s = published(db, "movie").filter(models.Series.slug == slug).first()
    if not s:
        raise ApiError(404, "not_found", "Movie not found")
    subscribed = active_subscription(db, user) is not None
    out = series_out(s)
    ep = next((e for e in ready_episodes(s) if e.episode_number == 1), None)
    out["episode"] = None if ep is None else {
        "id": str(ep.id), "duration_seconds": ep.duration_seconds,
        "thumbnail_url": ep.thumbnail_url,
        "is_free": 1 <= s.free_episode_count,
        "locked": 1 > s.free_episode_count and not subscribed,
    }
    out["credits"] = [{"person_name": c.person_name, "role": c.role,
                       "character_name": c.character_name} for c in s.credits]
    out["stills"] = [st.image_url for st in s.stills]
    my_genres = {g.id for g in s.genres}
    out["related"] = [series_out(r) for r in
                      published(db, "movie").order_by(models.Series.published_at.desc()).all()
                      if r.id != s.id and my_genres & {g.id for g in r.genres}][:10]
    return out
```

- [ ] **Step 4: Run tests** — `.venv/Scripts/python -m pytest tests/test_movies.py -q` → PASS; full suite → all pass.

- [ ] **Step 5: Commit** — `git commit -am "feat(backend): movies home/list/detail endpoints with credits, stills, related"`

---

### Task 4: Landscape transcode ladder + `extract_frame`

**Files:**
- Modify: `backend/app/transcode.py`
- Test: `backend/tests/test_transcode.py` (append)

**Interfaces:**
- Produces: `transcode_to_hls(src, outdir, orientation="portrait") -> int`; `write_master_playlist(outdir, renditions, orientation) -> None` (pure, unit-testable); `extract_frame(src, out_jpg, at_seconds=1.0, height=854)`; `extract_thumbnail(src, out_jpg)` unchanged signature (wrapper). `PORTRAIT_RENDITIONS`/`LANDSCAPE_RENDITIONS` constants.

- [ ] **Step 1: Write failing tests** — append to `backend/tests/test_transcode.py`:

```python
def test_master_playlist_landscape_resolutions(tmp_path):
    from app.transcode import LANDSCAPE_RENDITIONS, write_master_playlist

    write_master_playlist(tmp_path, LANDSCAPE_RENDITIONS, "landscape")
    master = (tmp_path / "master.m3u8").read_text().splitlines()
    stream_lines = [l for l in master if l.startswith("#EXT-X-STREAM-INF")]
    bandwidths = [int(l.split("BANDWIDTH=")[1].split(",")[0]) for l in stream_lines]
    assert bandwidths == sorted(bandwidths)  # lowest rendition FIRST — repo invariant
    assert "RESOLUTION=1920x1080" in stream_lines[-1]
    assert "RESOLUTION=852x480" in stream_lines[0]


def test_master_playlist_portrait_unchanged(tmp_path):
    from app.transcode import PORTRAIT_RENDITIONS, write_master_playlist

    write_master_playlist(tmp_path, PORTRAIT_RENDITIONS, "portrait")
    master = (tmp_path / "master.m3u8").read_text()
    assert "RESOLUTION=480x854" in master and "RESOLUTION=1080x1920" in master
    assert master.index("480x854") < master.index("1080x1920")  # ascending


@pytest.mark.skipif(ffmpeg_missing, reason="ffmpeg not installed")
def test_transcode_landscape_produces_hls(tmp_path):
    from app.transcode import transcode_to_hls

    src = tmp_path / "src.mp4"
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", "testsrc2=size=640x360:rate=30",
         "-f", "lavfi", "-i", "sine=frequency=440", "-t", "2",
         "-c:v", "libx264", "-c:a", "aac", "-shortest", str(src)],
        check=True, capture_output=True)
    out = tmp_path / "hls"
    duration = transcode_to_hls(src, out, orientation="landscape")
    assert (out / "master.m3u8").is_file()
    assert (out / "480.m3u8").is_file() and list(out.glob("480_*.ts"))
    assert (out / "1080.m3u8").is_file()
    assert 1 <= duration <= 3
```

- [ ] **Step 2: Run to verify failure** — `.venv/Scripts/python -m pytest tests/test_transcode.py -q`. Expected: FAIL — `ImportError: cannot import name 'write_master_playlist'`.

- [ ] **Step 3: Implement** — replace the whole of `backend/app/transcode.py` body above `extract_thumbnail` with:

```python
import subprocess
from pathlib import Path

PORTRAIT_RENDITIONS = [(1920, 4000), (1280, 2000), (854, 1000)]  # (height px, video kbps)
LANDSCAPE_RENDITIONS = [(1080, 4500), (720, 2500), (480, 1000)]
RENDITIONS = PORTRAIT_RENDITIONS  # back-compat alias


def probe_duration(src: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(src)],
        check=True, capture_output=True, text=True).stdout.strip()
    return float(out)


def write_master_playlist(outdir: Path, renditions: list[tuple[int, int]],
                          orientation: str) -> None:
    aspect = 16 / 9 if orientation == "landscape" else 9 / 16
    lines = ["#EXTM3U", "#EXT-X-VERSION:3"]
    # lowest rendition first: players start on it instantly, then adapt up
    for height, kbps in sorted(renditions, key=lambda r: r[1]):
        width = int(height * aspect / 2) * 2
        lines.append(f"#EXT-X-STREAM-INF:BANDWIDTH={kbps * 1100},RESOLUTION={width}x{height}")
        lines.append(f"{height}.m3u8")
    (outdir / "master.m3u8").write_text("\n".join(lines) + "\n")


def transcode_to_hls(src: Path, outdir: Path, orientation: str = "portrait") -> int:
    renditions = LANDSCAPE_RENDITIONS if orientation == "landscape" else PORTRAIT_RENDITIONS
    outdir.mkdir(parents=True, exist_ok=True)
    for height, kbps in renditions:
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
    write_master_playlist(outdir, renditions, orientation)
    return round(probe_duration(src))


def extract_frame(src: Path, out_jpg: Path, at_seconds: float = 1.0, height: int = 854) -> None:
    subprocess.run(
        ["ffmpeg", "-y", "-ss", str(at_seconds), "-i", str(src), "-frames:v", "1",
         "-vf", f"scale=-2:{height}", str(out_jpg)],
        check=True, capture_output=True)


def extract_thumbnail(src: Path, out_jpg: Path) -> None:
    extract_frame(src, out_jpg)
```

- [ ] **Step 4: Run tests** — `.venv/Scripts/python -m pytest tests/test_transcode.py -q` → PASS (ffmpeg tests run if FFmpeg on PATH; the two playlist tests must pass regardless). Full suite → all pass.

- [ ] **Step 5: Commit** — `git commit -am "feat(backend): orientation-aware HLS ladder + extract_frame for stills"`

---

### Task 5: Ingest CLI movie support (`--content-type movie`, credits, stills, `upload_image`)

**Files:**
- Modify: `backend/app/ingest.py`
- Test: `backend/tests/test_ingest.py` (create)

**Interfaces:**
- Consumes: `extract_frame`, `transcode_to_hls(orientation=...)` from Task 4; `Credit`/`Still` from Task 1.
- Produces: `upload_image(name: str, jpg: Path, placeholder_size: tuple[int, int]) -> str`; `upload_thumbnail(episode_id, jpg)` kept as wrapper (seed.py imports it); `parse_cast(cast_arg: str) -> list[tuple[str, str]]`; parser flags `--content-type {series,movie}`, `--release-year`, `--maturity-rating`, `--director`, `--cast "Name:Character,Name2"`, `--stills N`; `--free-episodes` default becomes `None` → resolved to 0 for movies / 3 for series; `--episode-number` no longer required (defaults 1), movies enforce `episode_number == 1`.

- [ ] **Step 1: Write failing tests** — create `backend/tests/test_ingest.py`:

```python
from app.ingest import build_parser, parse_cast


def test_parser_movie_flags():
    args = build_parser().parse_args(
        ["film.mp4", "--series-slug", "daal", "--content-type", "movie",
         "--release-year", "2025", "--maturity-rating", "U/A 13+",
         "--director", "Arjun Mehta", "--cast", "Riya Sen:Asha, Vik Das",
         "--stills", "4"])
    assert args.content_type == "movie" and args.release_year == 2025
    assert args.stills == 4 and args.episode_number == 1
    assert args.free_episodes is None  # resolved later: movie→0, series→3


def test_parse_cast():
    assert parse_cast("Riya Sen:Asha, Vik Das") == [("Riya Sen", "Asha"), ("Vik Das", "")]
    assert parse_cast("") == []


def test_resolve_free_episodes():
    from app.ingest import resolve_free_episodes
    assert resolve_free_episodes(None, "movie") == 0
    assert resolve_free_episodes(None, "series") == 3
    assert resolve_free_episodes(1, "movie") == 1
```

- [ ] **Step 2: Run to verify failure** — `.venv/Scripts/python -m pytest tests/test_ingest.py -q`. Expected: FAIL — `ImportError: cannot import name 'parse_cast'`.

- [ ] **Step 3: Implement** in `backend/app/ingest.py`:

Imports: add `extract_frame` to the transcode import. New helpers (above `get_or_create_series`):

```python
def parse_cast(cast_arg: str) -> list[tuple[str, str]]:
    """'Name:Character,Name2' -> [(name, character), ...]"""
    out = []
    for entry in [c.strip() for c in cast_arg.split(",") if c.strip()]:
        name, _, character = entry.partition(":")
        out.append((name.strip(), character.strip()))
    return out


def resolve_free_episodes(value: int | None, content_type: str) -> int:
    if value is not None:
        return value
    return 0 if content_type == "movie" else 3
```

`get_or_create_series` — set the new fields when creating:

```python
    series = models.Series(
        slug=args.series_slug, title=args.series_title or args.series_slug,
        synopsis=args.synopsis, language=args.language,
        content_type=args.content_type,
        release_year=args.release_year, maturity_rating=args.maturity_rating,
        free_episode_count=resolve_free_episodes(args.free_episodes, args.content_type),
        is_featured=args.featured,
        poster_url=args.poster_url or f"https://picsum.photos/seed/{args.series_slug}/540/960",
        banner_url=args.banner_url or f"https://picsum.photos/seed/{args.series_slug}-b/1280/720",
    )
```

Generalize the image uploader (replace `upload_thumbnail`; keep the machine-local-URL comment):

```python
def upload_image(name: str, jpg: Path, placeholder_size: tuple[int, int]) -> str:
    if settings.imagekit_private_key:
        from imagekitio import ImageKit  # optional dep: pip install imagekitio
        ik = ImageKit(private_key=settings.imagekit_private_key,
                      public_key=settings.imagekit_public_key,
                      url_endpoint=settings.imagekit_url_endpoint)
        with open(jpg, "rb") as f:
            result = ik.upload_file(file=f, file_name=f"{name}.jpg")
        return result.url
    # No ImageKit configured: keep a local copy for dev, but store a URL that
    # works from ANY device — a machine-local /media URL breaks the moment the
    # DB is shared (e.g. Neon rows read by the deployed frontend on a phone).
    dest = Path(settings.media_root) / "images" / f"{name}.jpg"
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(jpg, dest)
    w, h = placeholder_size
    return f"https://picsum.photos/seed/{name}/{w}/{h}"


def upload_thumbnail(episode_id: str, jpg: Path) -> str:
    return upload_image(episode_id, jpg, (360, 640))
```

In `ingest(args)` — after `src` check, movie validation:

```python
    if args.content_type == "movie" and args.episode_number != 1:
        sys.exit("error: a movie has exactly one video; omit --episode-number (it must be 1)")
```

Inside the `try` block, after `episode.thumbnail_url = ...` and before `episode.status = "ready"`, add credits/stills (movie only, idempotent):

```python
                if args.content_type == "movie":
                    thumb_h = 720
                    if args.director and not any(c.role == "director" for c in series.credits):
                        db.add(models.Credit(series_id=series.id, person_name=args.director,
                                             role="director", display_order=0))
                    if args.cast and not any(c.role == "cast" for c in series.credits):
                        for i, (name, character) in enumerate(parse_cast(args.cast), start=1):
                            db.add(models.Credit(series_id=series.id, person_name=name,
                                                 role="cast", character_name=character,
                                                 display_order=i))
                    if args.stills > 0 and not series.stills:
                        for i in range(args.stills):
                            at = episode.duration_seconds * (i + 1) / (args.stills + 1)
                            still_jpg = tmpdir / f"still_{i}.jpg"
                            extract_frame(src, still_jpg, at_seconds=at, height=thumb_h)
                            url = upload_image(f"{episode.id}-still-{i}", still_jpg, (640, 360))
                            db.add(models.Still(series_id=series.id, image_url=url,
                                                display_order=i))
```

Also switch the transcode call to pass orientation:

```python
                orientation = "landscape" if args.content_type == "movie" else "portrait"
                episode.duration_seconds = transcode_to_hls(src, hls_dir, orientation=orientation)
```

Parser updates in `build_parser()`:

```python
    p.add_argument("--episode-number", type=int, default=1)
    p.add_argument("--free-episodes", type=int, default=None,
                   help="default: 3 for series, 0 for movies (0=premium, 1=free film)")
    p.add_argument("--content-type", choices=["series", "movie"], default="series")
    p.add_argument("--release-year", type=int, default=None)
    p.add_argument("--maturity-rating", default="")
    p.add_argument("--director", default="")
    p.add_argument("--cast", default="", help='comma list "Name:Character,Name2"')
    p.add_argument("--stills", type=int, default=0,
                   help="movies: extract N stills evenly across the runtime")
```

(`--episode-number` was `required=True`; it becomes `default=1` — the module docstring example still works.)

- [ ] **Step 4: Run tests** — `.venv/Scripts/python -m pytest tests/test_ingest.py -q` → PASS; full suite → all pass.

- [ ] **Step 5: Commit** — `git commit -am "feat(backend): ingest CLI movie support (credits, stills, landscape, upload_image)"`

---

### Task 6: Seed demo movies

**Files:**
- Modify: `backend/app/seed.py`

**Interfaces:**
- Consumes: `upload_image` (Task 5), `extract_frame`, `transcode_to_hls(orientation=)` (Task 4), `Credit`/`Still` (Task 1).
- Produces: `python -m app.seed` also seeds 4 landscape movies (30 s synthetic clips) with year/rating/director/cast/stills; ≥1 premium (`free_episode_count=0`), ≥1 free (`=1`).

- [ ] **Step 1: Implement.** Update imports:

```python
from app.ingest import upload_image, upload_thumbnail
from app.transcode import extract_frame, extract_thumbnail, transcode_to_hls
```

Add after the `SERIES` list:

```python
MOVIES = [
    {"slug": "the-last-metro", "title": "The Last Metro", "genres": ["drama", "suspense"],
     "synopsis": "A night-shift metro driver finds a passenger who was declared dead "
                 "three years ago.", "featured": True, "hue": 30, "year": 2025,
     "rating": "U/A 16+", "free": 1, "director": "Arjun Mehta",
     "cast": [("Priya Sharma", "Meera"), ("Rohan Kapoor", "Dev"),
              ("Neha Joshi", "Inspector Rane")]},
    {"slug": "monsoon-wedding-crashers", "title": "Monsoon Wedding Crashers",
     "genres": ["comedy", "romance"],
     "synopsis": "Two broke caterers crash big-fat weddings for the buffet — until one of "
                 "them falls for a bride.", "featured": True, "hue": 120, "year": 2024,
     "rating": "U/A 13+", "free": 0, "director": "Sana Qureshi",
     "cast": [("Vik Das", "Monty"), ("Ananya Rao", "Tara")]},
    {"slug": "paper-boats", "title": "Paper Boats", "genres": ["drama"],
     "synopsis": "A father and daughter rebuild their flooded bookshop one shelf at a time.",
     "featured": False, "hue": 210, "year": 2025, "rating": "U", "free": 0,
     "director": "K. Balan", "cast": [("Meenakshi Iyer", "Anju"), ("Prakash Nair", "Appa")]},
    {"slug": "signal-lost", "title": "Signal Lost", "genres": ["suspense", "action"],
     "synopsis": "A trekking vlogger's live stream keeps broadcasting after her phone "
                 "battery dies.", "featured": False, "hue": 300, "year": 2023,
     "rating": "A", "free": 0, "director": "Dev Anand Pillai",
     "cast": [("Shreya Menon", "Ira"), ("Aditya Verma", "The Voice")]},
]
MOVIE_SECONDS = 30
STILLS_PER_MOVIE = 4


def generate_movie_clip(dest: Path, hue: int) -> None:
    subprocess.run(
        ["ffmpeg", "-y",
         "-f", "lavfi", "-i", f"testsrc2=size=1280x720:rate=30,hue=h={hue}",
         "-f", "lavfi", "-i", "sine=frequency=200",
         "-t", str(MOVIE_SECONDS), "-c:v", "libx264", "-preset", "veryfast",
         "-c:a", "aac", "-shortest", str(dest)],
        check=True, capture_output=True)
```

Append inside `seed()` after the SERIES loop (same indent as `for spec in SERIES:`):

```python
        for spec in MOVIES:
            if db.query(models.Series).filter(models.Series.slug == spec["slug"]).first():
                print(f"skip existing: {spec['slug']}")
                continue
            movie = models.Series(
                slug=spec["slug"], title=spec["title"], synopsis=spec["synopsis"],
                language="en", content_type="movie", free_episode_count=spec["free"],
                is_featured=spec["featured"], release_year=spec["year"],
                maturity_rating=spec["rating"],
                poster_url=f"https://picsum.photos/seed/{spec['slug']}/540/960",
                banner_url=f"https://picsum.photos/seed/{spec['slug']}-b/1280/720",
                genres=[genres[g] for g in spec["genres"]])
            db.add(movie)
            db.flush()
            db.add(models.Credit(series_id=movie.id, person_name=spec["director"],
                                 role="director", display_order=0))
            for i, (name, character) in enumerate(spec["cast"], start=1):
                db.add(models.Credit(series_id=movie.id, person_name=name, role="cast",
                                     character_name=character, display_order=i))
            ep = models.Episode(series_id=movie.id, episode_number=1,
                                title=spec["title"], status="processing")
            db.add(ep)
            db.flush()
            with tempfile.TemporaryDirectory() as tmp:
                tmpdir = Path(tmp)
                clip = tmpdir / "film.mp4"
                generate_movie_clip(clip, spec["hue"])
                ep.duration_seconds = transcode_to_hls(clip, tmpdir / "hls",
                                                       orientation="landscape")
                ep.hls_path = storage.publish(str(ep.id), tmpdir / "hls")
                thumb = tmpdir / "thumb.jpg"
                extract_frame(clip, thumb, at_seconds=1.0, height=720)
                ep.thumbnail_url = upload_image(str(ep.id), thumb, (640, 360))
                for i in range(STILLS_PER_MOVIE):
                    at = ep.duration_seconds * (i + 1) / (STILLS_PER_MOVIE + 1)
                    still = tmpdir / f"still_{i}.jpg"
                    extract_frame(clip, still, at_seconds=at, height=720)
                    url = upload_image(f"{ep.id}-still-{i}", still, (640, 360))
                    db.add(models.Still(series_id=movie.id, image_url=url, display_order=i))
            ep.status = "ready"
            db.commit()
            print(f"seeded movie {spec['slug']}")
```

- [ ] **Step 2: Run it** (needs FFmpeg on PATH; per repo memory it's installed via winget) — `.venv/Scripts/python -m app.seed`. Expected: `skip existing:` lines for the 4 series (already seeded), then `seeded movie the-last-metro` … ×4. **CAUTION:** check which DB `.env` points at first; if it's Neon prod, confirm seeding demo movies there is desired (memory says dummy data wipe was planned — seeding more dummy data into prod may be unwanted; if in doubt run with a local SQLite override: set `DATABASE_URL=sqlite:///./dev.db` for the command).
- [ ] **Step 3: Sanity-check via API** — `.venv/Scripts/uvicorn app.main:app --port 8000` (background), then `curl http://localhost:8000/api/v1/movies/home` → 4 movies with genres/credits-backed data; `curl http://localhost:8000/api/v1/movies/the-last-metro` → `episode.is_free true`, 4 stills, credits. Stop the server.
- [ ] **Step 4: Commit** — `git commit -am "feat(backend): seed 4 demo landscape movies with credits and stills"`

---

### Task 7: Frontend types + MovieCard/MovieRail + shared-surface branching (search, my-list, account)

**Files:**
- Modify: `frontend/src/lib/types.ts`
- Create: `frontend/src/components/MovieCard.tsx`, `frontend/src/components/MovieRail.tsx`
- Modify: `frontend/src/app/search/page.tsx`, `frontend/src/app/my-list/page.tsx`, `frontend/src/app/account/page.tsx`

**Interfaces:**
- Consumes: backend fields from Task 2/3.
- Produces: `SeriesSummary` gains `content_type: "series" | "movie"`, `release_year: number | null`, `maturity_rating: string`, `duration_seconds: number`. New `Credit`, `MovieEpisode`, `MovieDetail` types. `<MovieCard movie={SeriesSummary} />` (links `/movies/{slug}`), `<MovieRail title series />`.

- [ ] **Step 1: types** — in `frontend/src/lib/types.ts`, replace `SeriesSummary` and add movie types:

```ts
export interface SeriesSummary {
  id: string; slug: string; title: string; synopsis: string; language: string;
  poster_url: string; banner_url: string; free_episode_count: number;
  is_featured: boolean; view_count: number; genres: string[]; episode_count: number;
  content_type: "series" | "movie"; release_year: number | null;
  maturity_rating: string; duration_seconds: number;
}
export interface Credit { person_name: string; role: string; character_name: string }
export interface MovieEpisode {
  id: string; duration_seconds: number; thumbnail_url: string;
  is_free: boolean; locked: boolean;
}
export interface MovieDetail extends SeriesSummary {
  episode: MovieEpisode | null; credits: Credit[]; stills: string[];
  related: SeriesSummary[];
}
```

- [ ] **Step 2: MovieCard** — create `frontend/src/components/MovieCard.tsx`:

```tsx
import Link from "next/link";
import type { SeriesSummary } from "@/lib/types";

export function movieMeta(m: SeriesSummary): string {
  const mins = m.duration_seconds > 0 ? Math.max(1, Math.round(m.duration_seconds / 60)) : 0;
  return [m.release_year ? String(m.release_year) : null, mins ? `${mins}m` : null]
    .filter(Boolean).join(" · ");
}

export default function MovieCard({ movie }: { movie: SeriesSummary }) {
  return (
    <Link href={`/movies/${movie.slug}`}
          className="group w-40 shrink-0 transition-transform duration-200 active:scale-95"
          title={movie.title}>
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img src={movie.banner_url} alt={movie.title} loading="lazy"
           className="aspect-video w-full rounded-lg object-cover ring-1 ring-zinc-800 transition duration-200 group-hover:ring-rose-500/70 group-active:ring-rose-500" />
      <p className="mt-1.5 line-clamp-1 text-xs font-medium">{movie.title}</p>
      <p className="text-[10px] text-zinc-500">{movieMeta(movie)}</p>
    </Link>
  );
}
```

- [ ] **Step 3: MovieRail** — create `frontend/src/components/MovieRail.tsx` (RSC, no "use client"):

```tsx
import MovieCard from "@/components/MovieCard";
import type { SeriesSummary } from "@/lib/types";

export default function MovieRail({ title, movies }: { title: string; movies: SeriesSummary[] }) {
  if (!movies.length) return null;
  return (
    <section className="mt-6">
      <h2 className="mb-2 px-4 text-base font-bold">{title}</h2>
      <div className="flex gap-3 overflow-x-auto px-4 pb-2 scrollbar-none">
        {movies.map((m) => <MovieCard key={m.id} movie={m} />)}
      </div>
    </section>
  );
}
```

- [ ] **Step 4: Search page** — replace `frontend/src/app/search/page.tsx` body with filter chips + branched cards:

```tsx
"use client";

import { useEffect, useState } from "react";
import MovieCard from "@/components/MovieCard";
import SeriesCard from "@/components/SeriesCard";
import { apiFetch } from "@/lib/api-client";
import type { SeriesSummary } from "@/lib/types";

const FILTERS = [
  { value: "", label: "All" },
  { value: "series", label: "Series" },
  { value: "movie", label: "Movies" },
] as const;

export default function SearchPage() {
  const [q, setQ] = useState("");
  const [type, setType] = useState<"" | "series" | "movie">("");
  const [results, setResults] = useState<SeriesSummary[]>([]);
  const [searched, setSearched] = useState(false);

  useEffect(() => {
    const query = q.trim();
    if (!query) { setResults([]); setSearched(false); return; }
    const t = setTimeout(() => {
      const typeParam = type ? `&content_type=${type}` : "";
      apiFetch<SeriesSummary[]>(`/api/v1/search?q=${encodeURIComponent(query)}${typeParam}`)
        .then((r) => { setResults(r); setSearched(true); })
        .catch(() => setResults([]));
    }, 300);
    return () => clearTimeout(t);
  }, [q, type]);

  const seriesResults = results.filter((s) => s.content_type !== "movie");
  const movieResults = results.filter((s) => s.content_type === "movie");

  return (
    <div className="px-4 py-4">
      <input autoFocus value={q} onChange={(e) => setQ(e.target.value)}
             placeholder="Search series & films..."
             className="w-full rounded-lg border border-zinc-700 bg-zinc-900 px-4 py-3 text-sm outline-none focus:border-rose-500" />
      <div className="mt-3 flex gap-2">
        {FILTERS.map((f) => (
          <button key={f.value} onClick={() => setType(f.value)}
                  className={`rounded-full px-3 py-1 text-xs font-semibold ${
                    type === f.value ? "bg-rose-600 text-white"
                                     : "bg-zinc-800 text-zinc-400 active:text-white"}`}>
            {f.label}
          </button>
        ))}
      </div>
      {seriesResults.length > 0 && (
        <div className="mt-4 grid grid-cols-3 gap-2.5">
          {seriesResults.map((s) => <SeriesCard key={s.id} series={s} />)}
        </div>
      )}
      {movieResults.length > 0 && (
        <div className="mt-4 grid grid-cols-2 gap-2.5">
          {movieResults.map((m) => <MovieCard key={m.id} movie={m} />)}
        </div>
      )}
      {searched && results.length === 0 && (
        <p className="mt-6 text-sm text-zinc-400">No results for &quot;{q}&quot;</p>
      )}
    </div>
  );
}
```

- [ ] **Step 5: My List** — in `frontend/src/app/my-list/page.tsx`, replace the grid block:

```tsx
      {items.length === 0 ? (
        <p className="mt-4 text-sm text-zinc-400">
          Your list is empty. <Link href="/" className="text-rose-400">Find something to watch</Link>
        </p>
      ) : (
        <>
          {items.some((s) => s.content_type !== "movie") && (
            <>
              <h2 className="mt-4 text-sm font-bold text-zinc-300">Series</h2>
              <div className="mt-2 grid grid-cols-3 gap-2.5">
                {items.filter((s) => s.content_type !== "movie")
                      .map((s) => <SeriesCard key={s.id} series={s} />)}
              </div>
            </>
          )}
          {items.some((s) => s.content_type === "movie") && (
            <>
              <h2 className="mt-4 text-sm font-bold text-zinc-300">Movies</h2>
              <div className="mt-2 grid grid-cols-2 gap-2.5">
                {items.filter((s) => s.content_type === "movie")
                      .map((m) => <MovieCard key={m.id} movie={m} />)}
              </div>
            </>
          )}
        </>
      )}
```

with `import MovieCard from "@/components/MovieCard";` added.

- [ ] **Step 6: Account watch history** — in `frontend/src/app/account/page.tsx`, replace the history `<li>` body:

```tsx
            <li key={h.episode_id}>
              <Link href={h.series.content_type === "movie"
                            ? `/movies/${h.series.slug}/watch`
                            : `/watch/${h.series.slug}/${h.episode_number}`}
                    className="text-sm text-zinc-300 active:text-white">
                {h.series.content_type === "movie"
                  ? `${h.series.title} (${h.position_seconds}s in)`
                  : `${h.series.title} — Ep ${h.episode_number} (${h.position_seconds}s in)`}
              </Link>
            </li>
```

- [ ] **Step 7: Build gate** — from `frontend/`: `npm run build` → success, no type/lint errors.
- [ ] **Step 8: Commit** — `git commit -am "feat(frontend): movie types, MovieCard/MovieRail, movies-aware search/my-list/account"`

---

### Task 8: TopBar Reels|Movies switcher + mode-aware BottomNav

**Files:**
- Modify: `frontend/src/components/TopBar.tsx`, `frontend/src/components/BottomNav.tsx`

**Interfaces:**
- Produces: TopBar renders a centered segmented switcher (`/` vs `/movies`), hides entirely on the movie player route; BottomNav Home tab targets `/movies` while in movies context and hides on the movie player route. Both use `MOVIE_WATCH_RE = /^\/movies\/[^/]+\/watch$/`.

- [ ] **Step 1: TopBar** — in `frontend/src/components/TopBar.tsx`: add `usePathname` to the next/navigation import; inside the component add:

```tsx
  const pathname = usePathname();
  const inMovies = pathname === "/movies" || pathname.startsWith("/movies/");
  if (/^\/movies\/[^/]+\/watch$/.test(pathname)) return null; // immersive movie player
```

(Place the early return AFTER all hook calls.) Replace the inner row JSX with:

```tsx
      <div className="flex h-12 items-center justify-between gap-2 px-4">
        <Link href="/" className="text-lg font-extrabold tracking-tight text-rose-500">
          ShortReel
        </Link>
        <nav className="flex rounded-full border border-zinc-800 bg-zinc-900 p-0.5 text-xs font-semibold"
             aria-label="Mode">
          <Link href="/" className={`rounded-full px-3 py-1 ${
            !inMovies ? "bg-rose-600 text-white" : "text-zinc-400 active:text-white"}`}>
            Reels
          </Link>
          <Link href="/movies" className={`rounded-full px-3 py-1 ${
            inMovies ? "bg-rose-600 text-white" : "text-zinc-400 active:text-white"}`}>
            Movies
          </Link>
        </nav>
        {!loaded ? null : user ? (
          <button onClick={logout} className="text-xs text-zinc-400 active:text-white">
            Log out
          </button>
        ) : (
          <Link href="/login"
                className="rounded-full bg-rose-600 px-3 py-1 text-xs font-semibold active:bg-rose-500">
            Log in
          </Link>
        )}
      </div>
```

- [ ] **Step 2: BottomNav** — in `frontend/src/components/BottomNav.tsx`, replace the body of `BottomNav()` up to the `return`:

```tsx
export default function BottomNav() {
  const pathname = usePathname();
  if (pathname.startsWith("/watch/")) return null; // fullscreen player
  if (/^\/movies\/[^/]+\/watch$/.test(pathname)) return null; // movie player
  const inMovies = pathname === "/movies" || pathname.startsWith("/movies/");
  const tabs = TABS.map((t) =>
    t.label === "Home" ? { ...t, href: inMovies ? "/movies" : "/" } : t);
```

and in the JSX change `TABS.map` → `tabs.map`. The active check works unchanged (`tab.href === "/" ? pathname === "/" : pathname.startsWith(tab.href)` — `/movies` uses the startsWith branch).

- [ ] **Step 3: Build gate** — `npm run build` → success.
- [ ] **Step 4: Commit** — `git commit -am "feat(frontend): Reels|Movies mode switcher and mode-aware bottom nav"`

---

### Task 9: Movies home (`/movies`) + MovieHero

**Files:**
- Create: `frontend/src/components/MovieHero.tsx`, `frontend/src/app/movies/page.tsx`, `frontend/src/app/movies/loading.tsx`

**Interfaces:**
- Consumes: `GET /api/v1/movies/home` (`HomeData` shape), `MovieRail`, `movieMeta` from `MovieCard`.
- Produces: routes `/movies`.

- [ ] **Step 1: MovieHero** — create `frontend/src/components/MovieHero.tsx` (mirror of `Hero.tsx`, landscape, movie routes):

```tsx
"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import type { SeriesSummary } from "@/lib/types";

export default function MovieHero({ items }: { items: SeriesSummary[] }) {
  const [index, setIndex] = useState(0);
  useEffect(() => {
    if (items.length < 2) return;
    const t = setInterval(() => setIndex((i) => (i + 1) % items.length), 5000);
    return () => clearInterval(t);
  }, [items.length]);
  if (!items.length) return null;
  const m = items[index % items.length];
  return (
    <div className="relative w-full overflow-hidden">
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img key={m.id} src={m.banner_url} alt={m.title}
           className="aspect-video w-full object-cover animate-fade-in" />
      <div className="absolute inset-0 bg-gradient-to-t from-zinc-950 via-zinc-950/20 to-transparent" />
      <div className="absolute inset-x-0 bottom-3 px-4">
        <p className="text-[10px] font-semibold uppercase tracking-widest text-rose-400">
          Featured Film
        </p>
        <h1 className="mt-1 text-2xl font-extrabold leading-tight">{m.title}</h1>
        <div className="mt-2 flex gap-2">
          <Link href={`/movies/${m.slug}/watch`}
                className="flex-1 rounded-lg bg-rose-600 py-2.5 text-center text-sm font-semibold active:bg-rose-500">
            ▶ Play
          </Link>
          <Link href={`/movies/${m.slug}`}
                className="flex-1 rounded-lg bg-zinc-800/90 py-2.5 text-center text-sm font-semibold active:bg-zinc-700">
            Details
          </Link>
        </div>
        {items.length > 1 && (
          <div className="mt-2.5 flex justify-center gap-1.5">
            {items.map((item, i) => (
              <button key={item.id} onClick={() => setIndex(i)} aria-label={`Show ${item.title}`}
                      className={`h-1 rounded-full transition-all ${
                        i === index ? "w-6 bg-rose-500" : "w-3 bg-zinc-600"}`} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Movies home page** — create `frontend/src/app/movies/page.tsx`:

```tsx
import Link from "next/link";
import MovieHero from "@/components/MovieHero";
import MovieRail from "@/components/MovieRail";
import { serverFetch } from "@/lib/api-server";
import type { HomeData } from "@/lib/types";

export default async function MoviesHomePage() {
  const data = await serverFetch<HomeData>("/api/v1/movies/home");
  if (!data) {
    return <div className="p-10 text-center text-sm text-zinc-400">
      Could not reach the API. Is the backend running on port 8000?
    </div>;
  }
  return (
    <div className="animate-fade-in pb-4">
      <MovieHero items={data.featured} />
      {data.continue_watching.length > 0 && (
        <section className="mt-6">
          <h2 className="mb-2 px-4 text-base font-bold">Continue Watching</h2>
          <div className="flex gap-3 overflow-x-auto px-4 pb-2 scrollbar-none">
            {data.continue_watching.map((c) => (
              <Link key={c.episode_id} href={`/movies/${c.series.slug}/watch`}
                    className="w-40 shrink-0">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src={c.series.banner_url} alt={c.series.title}
                     className="aspect-video w-full rounded-lg object-cover ring-1 ring-zinc-800" />
                <p className="mt-1.5 line-clamp-1 text-xs font-medium">{c.series.title}</p>
                <p className="text-[10px] text-rose-400">Resume</p>
              </Link>
            ))}
          </div>
        </section>
      )}
      <MovieRail title="Trending Now" movies={data.trending} />
      <MovieRail title="New Releases" movies={data.new_releases} />
      {data.genre_rails.map((rail) => (
        <MovieRail key={rail.genre.slug} title={rail.genre.name} movies={rail.series} />
      ))}
    </div>
  );
}
```

- [ ] **Step 3: Loading skeleton** — create `frontend/src/app/movies/loading.tsx`:

```tsx
export default function Loading() {
  return (
    <div className="pb-4">
      <div className="skeleton aspect-video w-full rounded-none" />
      <div className="mt-6 px-4">
        <div className="skeleton h-5 w-32" />
        <div className="mt-3 flex gap-3 overflow-hidden">
          {[0, 1, 2].map((i) => (
            <div key={i} className="w-40 shrink-0">
              <div className="skeleton aspect-video w-full" />
              <div className="skeleton mt-2 h-3 w-24" />
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Build gate** — `npm run build` → success (route `/movies` listed).
- [ ] **Step 5: Commit** — `git commit -am "feat(frontend): movies home with landscape hero and 16:9 rails"`

---

### Task 10: Movie detail page (`/movies/[slug]`) + CastList + StillsGallery

**Files:**
- Create: `frontend/src/components/CastList.tsx`, `frontend/src/components/StillsGallery.tsx`, `frontend/src/app/movies/[slug]/page.tsx`, `frontend/src/app/movies/[slug]/loading.tsx`

**Interfaces:**
- Consumes: `GET /api/v1/movies/{slug}` → `MovieDetail`; `WatchlistButton` (unchanged, movies share the series id space); `MovieRail`, `FallbackImage`, `movieMeta`.
- Produces: route `/movies/[slug]`; `<CastList credits={Credit[]} />`; `<StillsGallery stills={string[]} fallback={string} />`.

- [ ] **Step 1: CastList** — create `frontend/src/components/CastList.tsx`:

```tsx
import type { Credit } from "@/lib/types";

const ROLE_LABEL: Record<string, string> = {
  director: "Director", writer: "Writer", producer: "Producer",
};

export default function CastList({ credits }: { credits: Credit[] }) {
  if (!credits.length) return null;
  const crew = credits.filter((c) => c.role !== "cast");
  const cast = credits.filter((c) => c.role === "cast");
  return (
    <section className="mt-6">
      <h2 className="mb-2 text-base font-bold">Cast &amp; Crew</h2>
      <ul className="space-y-1.5">
        {crew.map((c, i) => (
          <li key={`crew-${i}`} className="flex items-baseline justify-between text-sm">
            <span className="font-medium">{c.person_name}</span>
            <span className="text-xs text-zinc-500">{ROLE_LABEL[c.role] ?? c.role}</span>
          </li>
        ))}
        {cast.map((c, i) => (
          <li key={`cast-${i}`} className="flex items-baseline justify-between text-sm">
            <span className="font-medium">{c.person_name}</span>
            <span className="text-xs text-zinc-500">
              {c.character_name ? `as ${c.character_name}` : "Cast"}
            </span>
          </li>
        ))}
      </ul>
    </section>
  );
}
```

- [ ] **Step 2: StillsGallery** — create `frontend/src/components/StillsGallery.tsx`:

```tsx
import FallbackImage from "@/components/FallbackImage";

export default function StillsGallery({ stills, fallback }: {
  stills: string[]; fallback: string;
}) {
  if (!stills.length) return null;
  return (
    <section className="mt-6">
      <h2 className="mb-2 text-base font-bold">Stills</h2>
      <div className="-mx-4 flex gap-3 overflow-x-auto px-4 pb-2 scrollbar-none">
        {stills.map((url, i) => (
          <div key={i} className="w-56 shrink-0">
            <FallbackImage src={url} fallback={fallback} alt={`Still ${i + 1}`}
                           className="aspect-video w-full rounded-lg object-cover ring-1 ring-zinc-800" />
          </div>
        ))}
      </div>
    </section>
  );
}
```

- [ ] **Step 3: Detail page** — create `frontend/src/app/movies/[slug]/page.tsx`:

```tsx
import Link from "next/link";
import { notFound } from "next/navigation";
import CastList from "@/components/CastList";
import { movieMeta } from "@/components/MovieCard";
import MovieRail from "@/components/MovieRail";
import StillsGallery from "@/components/StillsGallery";
import WatchlistButton from "@/components/WatchlistButton";
import { serverFetch } from "@/lib/api-server";
import type { MovieDetail } from "@/lib/types";

export default async function MoviePage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const movie = await serverFetch<MovieDetail>(`/api/v1/movies/${slug}`);
  if (!movie) notFound();
  const meta = [
    movieMeta(movie),
    movie.maturity_rating || null,
    movie.genres.join(" · ") || null,
  ].filter(Boolean).join(" · ");
  return (
    <div className="animate-fade-in pb-4">
      <div className="relative w-full overflow-hidden">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src={movie.banner_url} alt={movie.title}
             className="aspect-video w-full object-cover" />
        <div className="absolute inset-0 bg-gradient-to-t from-zinc-950 to-transparent" />
      </div>
      <div className="px-4">
        <h1 className="mt-3 text-2xl font-extrabold leading-tight">{movie.title}</h1>
        <p className="mt-1 text-xs text-zinc-400">{meta}</p>
        <p className="mt-2 text-sm leading-relaxed text-zinc-300">{movie.synopsis}</p>
        <div className="mt-4 flex gap-2">
          {movie.episode ? (
            <Link href={`/movies/${movie.slug}/watch`}
                  className="flex-1 rounded-lg bg-rose-600 py-2.5 text-center text-sm font-semibold active:bg-rose-500">
              ▶ {movie.episode.is_free ? "Play" : "Play · Premium"}
            </Link>
          ) : (
            <span className="flex-1 rounded-lg bg-zinc-800 py-2.5 text-center text-sm font-semibold text-zinc-500">
              Coming soon
            </span>
          )}
          <WatchlistButton seriesId={movie.id} />
        </div>
        <CastList credits={movie.credits} />
        <StillsGallery stills={movie.stills} fallback={movie.banner_url} />
      </div>
      <MovieRail title="More Like This" movies={movie.related} />
    </div>
  );
}
```

- [ ] **Step 4: Loading skeleton** — create `frontend/src/app/movies/[slug]/loading.tsx`:

```tsx
export default function Loading() {
  return (
    <div className="pb-4">
      <div className="skeleton aspect-video w-full rounded-none" />
      <div className="px-4">
        <div className="skeleton mt-4 h-7 w-2/3" />
        <div className="skeleton mt-2 h-3 w-1/2" />
        <div className="skeleton mt-3 h-16 w-full" />
        <div className="skeleton mt-4 h-10 w-full" />
      </div>
    </div>
  );
}
```

- [ ] **Step 5: Build gate** — `npm run build` → success (`/movies/[slug]` listed). Note: `movieMeta` is a named export used by a server component — it lives in `MovieCard.tsx` which has no `"use client"`, so this is fine.
- [ ] **Step 6: Commit** — `git commit -am "feat(frontend): movie detail page with cast, stills, related rail"`

---

### Task 11: Extract `useHlsPlayback` hook; refactor EpisodeSlide onto it

**Files:**
- Create: `frontend/src/lib/use-hls-playback.ts`
- Modify: `frontend/src/components/EpisodeSlide.tsx`

**Interfaces:**
- Produces: `useHlsPlayback(videoRef: React.RefObject<HTMLVideoElement | null>, episodeId: string, enabled: boolean): "idle" | "loading" | "ready" | "locked" | "error"` — one-shot lazy load when `enabled` first true; Safari-native or hls.js with `capLevelToPlayerSize` + `withCredentials`; resume-seek; destroys hls on unmount; `locked` on 403 `subscription_required`.
- **Behavior-preserving refactor:** the reels invariant (only ACTIVE slide attaches) stays — `enabled = active && !episode.locked`.

- [ ] **Step 1: Create the hook** — `frontend/src/lib/use-hls-playback.ts` (this is the EpisodeSlide logic moved verbatim, minus the slide-specific state):

```ts
"use client";

import Hls from "hls.js";
import { useEffect, useRef, useState } from "react";
import { apiFetch, ApiError } from "@/lib/api-client";
import type { PlaybackInfo } from "@/lib/types";

export type PlaybackState = "idle" | "loading" | "ready" | "locked" | "error";

/**
 * Fetches the playback URL for an episode and attaches HLS to `videoRef`.
 * Loads at most ONCE, the first time `enabled` becomes true — callers decide
 * when (reels: only the active slide; movies: immediately). Destroys the
 * hls.js instance on unmount. withCredentials is required for CloudFront
 * signed cookies in prod.
 */
export function useHlsPlayback(
  videoRef: React.RefObject<HTMLVideoElement | null>,
  episodeId: string,
  enabled: boolean,
): PlaybackState {
  const hlsRef = useRef<Hls | null>(null);
  const loadedRef = useRef(false);
  const [state, setState] = useState<PlaybackState>("idle");

  useEffect(() => {
    if (!enabled || loadedRef.current) return;
    loadedRef.current = true;
    setState("loading");
    let cancelled = false;
    apiFetch<PlaybackInfo>(`/api/v1/episodes/${episodeId}/playback`)
      .then((playback) => {
        if (cancelled) return;
        const video = videoRef.current;
        if (!video) return;
        if (video.canPlayType("application/vnd.apple.mpegurl")) {
          video.src = playback.url;
        } else if (Hls.isSupported()) {
          const hls = new Hls({
            capLevelToPlayerSize: true,
            xhrSetup: (xhr) => { xhr.withCredentials = true; },
          });
          hlsRef.current = hls;
          hls.loadSource(playback.url);
          hls.attachMedia(video);
          hls.on(Hls.Events.ERROR, (_evt, data) => {
            if (data.fatal) setState("error");
          });
        } else {
          setState("error");
          return;
        }
        if (playback.resume_position > 0) {
          video.addEventListener("loadedmetadata", () => {
            if (playback.resume_position < video.duration - 2) {
              video.currentTime = playback.resume_position;
            }
          }, { once: true });
        }
        setState("ready");
      })
      .catch((err) => {
        if (cancelled) return;
        if (err instanceof ApiError && err.code === "subscription_required") setState("locked");
        else setState("error");
      });
    return () => { cancelled = true; };
  }, [enabled, episodeId, videoRef]);

  useEffect(() => () => { hlsRef.current?.destroy(); }, []);

  return state;
}
```

- [ ] **Step 2: Refactor EpisodeSlide** — in `frontend/src/components/EpisodeSlide.tsx`:
  - Remove the `Hls` import, `hlsRef`, `loadedRef`, the `state` useState, the whole load-effect (lines 37–82 in the current file), and the teardown effect (`useEffect(() => () => { hlsRef.current?.destroy(); }, [])`).
  - Add `import { useHlsPlayback } from "@/lib/use-hls-playback";` and replace with:

```tsx
  const state = useHlsPlayback(videoRef, episode.id, active && !episode.locked);
```

  - Everything else stays: the play/pause effect keys off `state !== "ready"` (the hook's state slots in), `togglePlay`, `saveProgress`, `onTimeUpdate`, the `if (episode.locked || state === "locked") return <Paywall .../>` branch, and all overlays. The "idle" state renders the same as before (poster only).

- [ ] **Step 3: Build gate** — `npm run build` → success.
- [ ] **Step 4: Manual reels regression check** (the invariant is not covered by automated tests): with backend + frontend running, open `http://localhost:3001/watch/ceos-secret-bride/1` — video plays, swiping to the next episode plays it and pauses the previous, paywall appears on ep 3 (free_episode_count=2) for guests. Report what you observed.
- [ ] **Step 5: Commit** — `git commit -am "refactor(frontend): extract useHlsPlayback hook from EpisodeSlide"`

---

### Task 12: MoviePlayer + watch route + Paywall variants + manifest/copy

**Files:**
- Create: `frontend/src/components/MoviePlayer.tsx`, `frontend/src/app/movies/[slug]/watch/page.tsx`, `frontend/src/app/movies/[slug]/watch/loading.tsx`
- Modify: `frontend/src/components/Paywall.tsx`, `frontend/src/app/manifest.ts`, `frontend/src/app/plans/page.tsx`, `frontend/src/components/PlanCards.tsx`

**Interfaces:**
- Consumes: `useHlsPlayback` (Task 11), `MovieDetail` (Task 7), `GET /api/v1/movies/{slug}` (Task 3).
- Produces: route `/movies/[slug]/watch`; `Paywall` gains optional `message?: string` and `detailPath?: string` props (existing call sites unchanged).

- [ ] **Step 1: Paywall props** — replace `frontend/src/components/Paywall.tsx`:

```tsx
import Link from "next/link";

export default function Paywall({ seriesSlug, poster, message, detailPath }: {
  seriesSlug: string; poster: string; message?: string; detailPath?: string;
}) {
  const next = detailPath ?? `/series/${seriesSlug}`;
  return (
    <div className="relative flex h-full w-full items-center justify-center overflow-hidden">
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img src={poster} alt="" className="absolute inset-0 h-full w-full object-cover opacity-20 blur-sm" />
      <div className="relative z-10 mx-6 text-center">
        <div className="text-5xl">🔒</div>
        <h2 className="mt-3 text-xl font-bold">Subscribe to keep watching</h2>
        <p className="mt-1 text-sm text-zinc-400">
          {message ?? "You've reached the end of the free episodes for this series."}
        </p>
        <div className="mt-5 flex flex-col gap-2">
          <Link href="/plans" className="rounded-lg bg-rose-600 px-6 py-2.5 font-semibold active:bg-rose-500">
            View Plans
          </Link>
          <Link href={`/login?next=${next}`} className="text-sm text-zinc-400 active:text-white">
            Already subscribed? Log in
          </Link>
        </div>
      </div>
    </div>
  );
}
```

(Note: the original used `&apos;` in JSX text; the default string above lives in a JS expression so a plain apostrophe is fine.)

- [ ] **Step 2: MoviePlayer** — create `frontend/src/components/MoviePlayer.tsx`:

```tsx
"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import Paywall from "@/components/Paywall";
import { apiFetch } from "@/lib/api-client";
import { useHlsPlayback } from "@/lib/use-hls-playback";
import type { MovieDetail, MovieEpisode } from "@/lib/types";

function fmt(t: number): string {
  if (!Number.isFinite(t) || t < 0) return "0:00";
  const h = Math.floor(t / 3600);
  const m = Math.floor((t % 3600) / 60);
  const s = Math.floor(t % 60).toString().padStart(2, "0");
  return h > 0 ? `${h}:${m.toString().padStart(2, "0")}:${s}` : `${m}:${s}`;
}

export default function MoviePlayer({ movie, episode }: {
  movie: MovieDetail; episode: MovieEpisode;
}) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const shellRef = useRef<HTMLDivElement>(null);
  const lastSaved = useRef(0);
  const hideTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [controlsVisible, setControlsVisible] = useState(true);
  const [paused, setPaused] = useState(true);
  const [muted, setMuted] = useState(false);
  const [fullscreen, setFullscreen] = useState(false);
  const [time, setTime] = useState(0);
  const [buffered, setBuffered] = useState(0);
  const [duration, setDuration] = useState(episode.duration_seconds);

  const state = useHlsPlayback(videoRef, episode.id, !episode.locked);

  const saveProgress = useCallback((position: number, completed: boolean) => {
    apiFetch(`/api/v1/progress/${episode.id}`, {
      method: "PUT",
      body: JSON.stringify({ position_seconds: Math.floor(position), completed }),
    }).catch(() => {}); // guests get a 401 — progress just isn't saved
  }, [episode.id]);

  const poke = useCallback(() => {
    setControlsVisible(true);
    if (hideTimer.current) clearTimeout(hideTimer.current);
    hideTimer.current = setTimeout(() => setControlsVisible(false), 3000);
  }, []);

  useEffect(() => {
    poke();
    return () => { if (hideTimer.current) clearTimeout(hideTimer.current); };
  }, [poke]);

  // autoplay once the stream is ready; fall back to muted autoplay
  useEffect(() => {
    const video = videoRef.current;
    if (!video || state !== "ready") return;
    video.play().catch(() => {
      video.muted = true;
      setMuted(true);
      video.play().catch(() => {});
    });
  }, [state]);

  useEffect(() => {
    const onChange = () => setFullscreen(Boolean(document.fullscreenElement));
    document.addEventListener("fullscreenchange", onChange);
    return () => document.removeEventListener("fullscreenchange", onChange);
  }, []);

  // flush progress when the page is hidden/left
  useEffect(() => {
    const flush = () => {
      const video = videoRef.current;
      if (video && video.currentTime > 0) saveProgress(video.currentTime, false);
    };
    document.addEventListener("visibilitychange", flush);
    return () => { flush(); document.removeEventListener("visibilitychange", flush); };
  }, [saveProgress]);

  function togglePlay() {
    const video = videoRef.current;
    if (!video) return;
    if (video.paused) {
      video.play().catch(() => {});
    } else {
      video.pause();
      saveProgress(video.currentTime, false);
    }
    poke();
  }

  function skip(delta: number) {
    const video = videoRef.current;
    if (!video) return;
    const max = Number.isFinite(video.duration) ? video.duration : duration;
    video.currentTime = Math.min(Math.max(0, video.currentTime + delta), max);
    poke();
  }

  function toggleMute() {
    const video = videoRef.current;
    if (!video) return;
    video.muted = !video.muted;
    setMuted(video.muted);
    poke();
  }

  async function toggleFullscreen() {
    const shell = shellRef.current;
    const video = videoRef.current as (HTMLVideoElement & {
      webkitEnterFullscreen?: () => void;
    }) | null;
    if (!shell || !video) return;
    poke();
    if (document.fullscreenElement) {
      await document.exitFullscreen().catch(() => {});
      try {
        (screen.orientation as unknown as { unlock?: () => void }).unlock?.();
      } catch { /* unsupported */ }
      return;
    }
    if (shell.requestFullscreen) {
      await shell.requestFullscreen().catch(() => {});
      try {
        // best-effort — unsupported on iOS Safari and most desktops
        await (screen.orientation as unknown as {
          lock?: (o: string) => Promise<void>;
        }).lock?.("landscape");
      } catch { /* unsupported */ }
    } else {
      video.webkitEnterFullscreen?.(); // iOS Safari: native video fullscreen
    }
  }

  function onTimeUpdate() {
    const video = videoRef.current;
    if (!video) return;
    setTime(video.currentTime);
    if (video.buffered.length > 0) {
      setBuffered(video.buffered.end(video.buffered.length - 1));
    }
    if (video.currentTime - lastSaved.current >= 5) {
      lastSaved.current = video.currentTime;
      saveProgress(video.currentTime, false);
    }
  }

  function onSeek(e: React.ChangeEvent<HTMLInputElement>) {
    const video = videoRef.current;
    if (!video) return;
    video.currentTime = Number(e.target.value);
    setTime(video.currentTime);
    poke();
  }

  if (episode.locked || state === "locked") {
    return (
      <div className="fixed inset-0 z-50 bg-black">
        <Paywall seriesSlug={movie.slug} poster={movie.banner_url}
                 message="This film is for subscribers. Subscribe to start watching."
                 detailPath={`/movies/${movie.slug}`} />
      </div>
    );
  }

  return (
    <div ref={shellRef} onClick={poke}
         className="fixed inset-0 z-50 flex items-center justify-center bg-black">
      <video ref={videoRef} playsInline
             poster={episode.thumbnail_url || movie.banner_url}
             onClick={(e) => { e.stopPropagation(); togglePlay(); }}
             onTimeUpdate={onTimeUpdate}
             onLoadedMetadata={() => {
               const d = videoRef.current?.duration;
               if (d && Number.isFinite(d)) setDuration(d);
             }}
             onPlay={() => setPaused(false)}
             onPause={() => setPaused(true)}
             onEnded={() => {
               saveProgress(videoRef.current?.duration ?? duration, true);
               setControlsVisible(true);
             }}
             className="max-h-full w-full object-contain" />

      {state === "loading" && (
        <div className="pointer-events-none absolute inset-0 flex items-center justify-center">
          <div className="h-10 w-10 animate-spin rounded-full border-2 border-zinc-600 border-t-rose-500" />
        </div>
      )}
      {state === "error" && (
        <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 text-sm text-zinc-400">
          Playback failed.
          <button className="underline" onClick={() => window.location.reload()}>Retry</button>
        </div>
      )}

      <div className={`absolute inset-0 flex flex-col justify-between bg-gradient-to-b from-black/70 via-transparent to-black/80 transition-opacity duration-200 ${
        controlsVisible ? "opacity-100" : "pointer-events-none opacity-0"}`}>
        <div className="flex items-center gap-3 p-4">
          <Link href={`/movies/${movie.slug}`} aria-label="Back"
                className="flex h-9 w-9 items-center justify-center rounded-full bg-black/50 text-lg">
            ←
          </Link>
          <p className="line-clamp-1 text-sm font-bold drop-shadow">{movie.title}</p>
        </div>

        <div className="flex items-center justify-center gap-10">
          <button onClick={(e) => { e.stopPropagation(); skip(-10); }} aria-label="Back 10 seconds"
                  className="text-sm font-semibold text-zinc-200">⟲ 10</button>
          <button onClick={(e) => { e.stopPropagation(); togglePlay(); }}
                  aria-label={paused ? "Play" : "Pause"}
                  className="flex h-14 w-14 items-center justify-center rounded-full bg-black/50 text-2xl backdrop-blur-sm">
            {paused ? "▶" : "⏸"}
          </button>
          <button onClick={(e) => { e.stopPropagation(); skip(10); }} aria-label="Forward 10 seconds"
                  className="text-sm font-semibold text-zinc-200">10 ⟳</button>
        </div>

        <div className="px-4 pb-5">
          <div className="mb-1 h-0.5 w-full overflow-hidden rounded bg-zinc-800">
            <div className="h-full bg-zinc-500/70"
                 style={{ width: `${duration ? Math.min(100, (buffered / duration) * 100) : 0}%` }} />
          </div>
          <input type="range" min={0} max={Math.max(1, Math.floor(duration))} step={1}
                 value={Math.min(time, duration)} onChange={onSeek} aria-label="Seek"
                 onClick={(e) => e.stopPropagation()}
                 className="w-full accent-rose-600" />
          <div className="mt-1 flex items-center justify-between text-xs text-zinc-300">
            <span>{fmt(time)} / {fmt(duration)}</span>
            <div className="flex items-center gap-5">
              <button onClick={(e) => { e.stopPropagation(); toggleMute(); }}
                      aria-label={muted ? "Unmute" : "Mute"}>{muted ? "🔇" : "🔊"}</button>
              <button onClick={(e) => { e.stopPropagation(); toggleFullscreen(); }}
                      aria-label="Fullscreen" className="text-base">{fullscreen ? "⤡" : "⛶"}</button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Watch route** — create `frontend/src/app/movies/[slug]/watch/page.tsx`:

```tsx
import { notFound } from "next/navigation";
import MoviePlayer from "@/components/MoviePlayer";
import { serverFetch } from "@/lib/api-server";
import type { MovieDetail } from "@/lib/types";

export default async function MovieWatchPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const movie = await serverFetch<MovieDetail>(`/api/v1/movies/${slug}`);
  if (!movie || !movie.episode) notFound();
  return <MoviePlayer movie={movie} episode={movie.episode} />;
}
```

and `frontend/src/app/movies/[slug]/watch/loading.tsx`:

```tsx
export default function Loading() {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black">
      <div className="h-10 w-10 animate-spin rounded-full border-2 border-zinc-800 border-t-rose-500" />
    </div>
  );
}
```

- [ ] **Step 4: Manifest + copy** — in `frontend/src/app/manifest.ts`: `orientation: "portrait"` → `orientation: "any"` and `description: "Vertical micro-drama series. First episodes free."` → `"Vertical micro-dramas and short films. First episodes free."`. In `frontend/src/app/plans/page.tsx` find the paragraph "First episodes of every series are always free. Subscribe to unlock the rest." → "First episodes of every series are free. Subscribe to unlock everything — all episodes and every film." In `frontend/src/components/PlanCards.tsx`: Razorpay `description: "Unlimited short dramas"` → `"Unlimited dramas & films"`, and the bullet `"✓ All episodes, every series"` → `"✓ Every series & every film"`.

- [ ] **Step 5: Build gate** — `npm run build` → success (`/movies/[slug]/watch` listed).
- [ ] **Step 6: Commit** — `git commit -am "feat(frontend): landscape movie player with fullscreen, scrubber, paywall variant"`

---

### Task 13: Docs + CLAUDE.md

**Files:**
- Modify: `docs/architecture.md`, `docs/api-reference.md`, `docs/content-ingestion.md`, `CLAUDE.md`

- [ ] **Step 1:** `CLAUDE.md` — in "Invariants (don't break)", append:

```markdown
- Two content modes share one catalog: `series.content_type` is `series|movie`. A movie is
  ONE series row + ONE landscape episode (`episode_number=1`); `free_episode_count` 1=free
  film, 0=premium. Reels surfaces (`/home`, `/series`, genre/search defaults) must filter
  `content_type="series"`; movies mode uses `/api/v1/movies/*`.
```

- [ ] **Step 2:** `docs/api-reference.md` — document the three new endpoints (`/movies/home`, `/movies`, `/movies/{slug}` with response shapes as implemented in Task 3), the new `series_out` fields, and the `content_type` query param on `/search` + `/genres/{slug}/series`. Follow the file's existing format exactly (read it first).
- [ ] **Step 3:** `docs/content-ingestion.md` — add a "Movies" section: the `--content-type movie` invocation example:

```bash
.venv/Scripts/python -m app.ingest film.mp4 --series-slug daal --series-title "Daal" \
  --content-type movie --release-year 2025 --maturity-rating "U/A 13+" \
  --director "Arjun Mehta" --cast "Riya Sen:Asha,Vik Das:Bhola" --stills 4 \
  --genres drama --synopsis "..."
```

plus notes: landscape ladder 1080/720/480, `--free-episodes 1` = free film (default 0 = premium), stills extracted evenly across runtime.
- [ ] **Step 4:** `docs/architecture.md` — add a "Movies mode" subsection: content model (content_type + credits/stills), route map (`/movies`, `/movies/[slug]`, `/movies/[slug]/watch`), MoviePlayer/useHlsPlayback split, mode switcher. Follow the file's existing voice (read it first).
- [ ] **Step 5: Commit** — `git commit -am "docs: movies mode (architecture, API, ingestion, CLAUDE.md invariants)"`

---

### Task 14: Full verification pass

**Files:** none (verification only)

- [ ] **Step 1: Backend suite** — from `backend/`: `.venv/Scripts/python -m pytest -q` → ALL pass, zero failures.
- [ ] **Step 2: Frontend gate** — from `frontend/`: `npm run build` → success; route list includes `/movies`, `/movies/[slug]`, `/movies/[slug]/watch`.
- [ ] **Step 3: Live drive** — start backend (`.venv/Scripts/uvicorn app.main:app --port 8000`) and frontend (`PORT=3001 npm run dev`, or `$env:PORT=3001; npm run dev` in PowerShell). Verify with curl/browser:
  - `GET http://localhost:8000/api/v1/home` → no `content_type:"movie"` items.
  - `GET http://localhost:8000/api/v1/movies/home` → 4 seeded movies, movies only.
  - `GET http://localhost:8000/api/v1/movies/the-last-metro` → credits (director first), 4 stills, `episode.is_free true`.
  - Premium movie playback as guest → `GET /api/v1/episodes/{monsoon-wedding-crashers ep id}/playback` → 403 `subscription_required`.
  - Browser `http://localhost:3001/` → reels home unchanged, switcher shows Reels active.
  - `http://localhost:3001/movies` → landscape hero + rails; tap a movie → detail page (cast, stills, More Like This); Play on the free movie → player plays with controls, scrubbing, fullscreen; premium movie → paywall with film copy.
  - `http://localhost:3001/watch/ceos-secret-bride/1` → reels feed still works (regression from Task 11).
- [ ] **Step 4: Report** — summarize every check with actual observed output (no claims without evidence).
