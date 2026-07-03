# Qisso — repo guide

Subscription-based short-drama streaming app (DramaBox-style). **Mobile-first phone-shell
UI** — every screen is designed for portrait phones (max-w-md column, bottom tab bar).

## Layout

- `backend/` — FastAPI + SQLAlchemy 2 (sync) + Alembic. Venv at `backend/.venv`
  (Windows: `.venv/Scripts/python`). Dev DB is SQLite (`dev.db`); Neon in prod.
- `frontend/` — Next.js 16 App Router + Tailwind v4 + hls.js. Port 3001 in dev
  (3000 is taken by another local app); backend CORS is set accordingly in `backend/.env`.
- `docs/` — architecture, api-reference, content-ingestion, deployment + design specs/plans.

## Commands

```bash
# backend (from backend/)
.venv/Scripts/python -m pytest -q          # test suite
.venv/Scripts/alembic upgrade head          # migrations
.venv/Scripts/uvicorn app.main:app --port 8000
.venv/Scripts/python -m app.seed            # demo content (needs FFmpeg on PATH)

# frontend (from frontend/)
npm run build                               # type+lint gate
PORT=3001 npm run dev
```

## Invariants (don't break)

- API errors always `{"error": {code, message}}`; 403 code `subscription_required`
  drives the frontend paywall.
- Entitlement lives ONLY in `backend/app/entitlement.py` — never inline the rule.
- Razorpay webhooks are the source of truth for subscription state, idempotent via
  `webhook_events.razorpay_event_id`.
- Models use cross-database types only (tests run on in-memory SQLite).
- Watch feed: only the ACTIVE slide attaches an hls.js player; master playlists list
  the lowest rendition first (renderer freezes otherwise on modest hardware).
- Two content modes share one catalog: `series.content_type` is `series|movie`. A movie is
  ONE series row + ONE landscape episode (`episode_number=1`); `free_episode_count` 1=free
  film, 0=premium. Reels surfaces (`/home`, `/series`, genre/search defaults) filter
  `content_type="series"`; movies mode uses `/api/v1/movies/*` and the `/movies/*` routes.
- Money = INR paise; timestamps = UTC.
