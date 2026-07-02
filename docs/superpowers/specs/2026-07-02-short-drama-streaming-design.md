# ShortReel — Short-Drama Streaming Platform (Design Spec)

**Date:** 2026-07-02
**Status:** Approved by user
**Scope:** v1, end-user (client) experience only. Admin panel deferred; content ingestion via CLI.

## 1. Product summary

A subscription-based short-drama OTT platform in the style of DramaBox, JioHotstar Tadka, ShortBox, Pocket TV, and CineShort: vertical (9:16) micro-drama series with 1–3 minute episodes, where the first N episodes of each series are free and the rest require an active subscription.

### Competitor feature research (basis for scope)

- **DramaBox** — vertical episodes 1–3 min with cliffhangers; first episodes free; coins OR all-access subscription; genre catalog; watchlist; continue-watching; daily releases; multi-language subtitles.
- **JioHotstar Tadka** — 30–60s vertical micro-dramas, swipe feed, multi-language, free ad-supported.
- **Pocket Films / Pocket TV** — curated short films, thematic collections, multi-genre/language; Pocket TV: 1–2 min episodes, first few free.
- **CineShort** — curated catalog, genre browsing, subtitles, downloads, ad-free premium, browse without signup.
- **ShortBox** — multi-language subtitles, daily updates, HD vertical fullscreen, picture-in-picture.

### v1 feature set (user-facing)

1. Home/discovery: hero banners, trending, new releases, genre rails, continue watching
2. Series detail with episode grid and free/locked indicators
3. Fullscreen vertical player: tap-pause, prev/next episode, auto-advance, resume, paywall overlay
4. Freemium gate: first `free_episode_count` episodes of each series free; rest subscription-only
5. Subscription: weekly/monthly/yearly plans via Razorpay Subscriptions; manage/cancel in account
6. Auth: email + password (JWT); guests can browse and watch free episodes
7. Watch history / continue watching, My List (watchlist), search
8. Out of scope for v1: coins/per-episode unlock, rewarded ads, downloads/offline, DRM, subtitles tracks, notifications, admin panel, native mobile apps.

## 2. Architecture decisions

| Concern | Decision | Rationale |
|---|---|---|
| Frontend | Next.js (App Router), Tailwind, shadcn/ui, hls.js | User requirement |
| Backend | FastAPI, single API for all business logic | Option A chosen: clean separation; future admin reuses API |
| ORM | SQLAlchemy 2 + Alembic (Drizzle dropped) | Drizzle is TS-only, cannot run in Python; Neon works with any Postgres client |
| DB | Neon Postgres — pooled URL for app, direct URL for Alembic | PgBouncer + DDL constraint |
| Video | S3 originals → FFmpeg HLS ladder → CloudFront + signed cookies | Industry-standard DIY pipeline; user chose over Mux/CF Stream |
| Images | ImageKit for posters/banners/thumbnails | User requirement |
| Payments | Razorpay Subscriptions (India-first) | User choice |
| Monetization | Subscription-only v1 | User choice |
| Auth | Email/password, JWT access (15 min) + DB-backed refresh (30 d), httpOnly cookies | User choice |

### Repository layout

```
ott_streaming/
├── frontend/        # Next.js app
├── backend/         # FastAPI app, alembic/, ingest CLI, seed scripts
└── docs/            # this spec, implementation plans
```

## 3. Data model

All tables in Neon Postgres, managed by Alembic migrations.

- `users` — id (uuid), email (unique), password_hash (bcrypt), name, created_at
- `refresh_tokens` — id, user_id FK, token_hash, expires_at, revoked_at
- `series` — id, slug (unique), title, synopsis, language, poster_url, banner_url, free_episode_count (default 3), is_featured, status (`draft/published`), view_count, published_at
- `genres` — id, slug, name; `series_genres` — M2M
- `episodes` — id, series_id FK, episode_number (unique per series), title, duration_seconds, hls_path (master playlist key), thumbnail_url, status (`processing/ready/failed`)
- `plans` — id, name, price_inr (paise), interval (`weekly/monthly/yearly`), razorpay_plan_id, is_active
- `subscriptions` — id, user_id FK, plan_id FK, razorpay_subscription_id, status (`created/active/past_due/cancelled/expired`), current_period_start, current_period_end
- `webhook_events` — id, razorpay_event_id (unique), event_type, payload jsonb, processed_at
- `watch_progress` — user_id + episode_id PK, position_seconds, completed, updated_at
- `watchlist` — user_id + series_id PK, added_at

**Entitlement rule (single shared function):** an episode is watchable iff
`episode.episode_number <= series.free_episode_count` OR the user has a subscription with `status = 'active'` AND `now() < current_period_end`.

## 4. Video pipeline

### Ingest (CLI now, admin API later)

`python -m app.ingest <video> --series-slug ... --episode-number ... --title ...`

1. Create/lookup series + episode rows (status `processing`).
2. Upload original to `s3://<bucket>/originals/{episode_id}/source.mp4`.
3. FFmpeg transcode to vertical HLS ladder: 1080×1920 @ ~4 Mbps, 720×1280 @ ~2 Mbps, 480×854 @ ~1 Mbps; 4s segments; master playlist.
4. Upload renditions to `s3://<bucket>/hls/{episode_id}/`.
5. Extract thumbnail frame → upload to ImageKit → save URL.
6. Mark episode `ready` (or `failed`; failed episodes never appear in the catalog).

### Playback authorization

`GET /api/v1/episodes/{id}/playback`
→ run entitlement rule → if entitled: respond with playlist URL and set **CloudFront signed cookies** (policy scoped to `hls/{episode_id}/*`, short TTL). One cookie set authorizes playlist + all segments. If not entitled: `403` with code `subscription_required` (frontend shows paywall).

### Storage modes

`STORAGE_MODE=local | s3` — identical pipeline code behind a storage adapter:

- **local** (dev, no AWS needed): HLS written to `backend/media/`, served by FastAPI with the same entitlement check on playlist requests.
- **s3** (prod): S3 + CloudFront signed cookies as above.

## 5. Subscription flow (Razorpay)

1. Seed script creates plans in Razorpay and stores `razorpay_plan_id` locally.
2. `POST /api/v1/subscriptions` → backend creates Razorpay Subscription → returns `subscription_id`.
3. Frontend opens Razorpay Checkout with `subscription_id`; user pays (UPI/card/netbanking).
4. **Webhooks are the source of truth** (not the checkout success callback): `subscription.activated`, `subscription.charged`, `subscription.cancelled`, `payment.failed` → verify signature → idempotency via `webhook_events.razorpay_event_id` unique constraint → update `subscriptions` row.
5. Cancel: `POST /api/v1/subscriptions/cancel` → Razorpay cancel-at-cycle-end; access continues until `current_period_end`.

## 6. API surface (FastAPI, `/api/v1`)

- Auth: `POST /auth/signup`, `POST /auth/login`, `POST /auth/refresh`, `POST /auth/logout`, `GET /auth/me`
- Catalog (public): `GET /home` (hero + rails), `GET /series`, `GET /series/{slug}`, `GET /genres`, `GET /genres/{slug}/series`, `GET /search?q=`
- Playback: `GET /episodes/{id}/playback` (entitlement-gated)
- Progress: `PUT /progress/{episode_id}`, `GET /progress/continue-watching`
- Watchlist: `GET/POST/DELETE /watchlist`
- Billing: `GET /plans`, `POST /subscriptions`, `POST /subscriptions/cancel`, `GET /subscriptions/current`, `POST /webhooks/razorpay`

JSON error envelope: `{ "error": { "code": "...", "message": "..." } }`. `401` = unauthenticated, `403` + `subscription_required` = paywall.

## 7. Frontend pages

- `/` — hero carousel (featured series), rails: Continue Watching (auth), Trending (view_count), New Releases, one rail per genre
- `/series/[slug]` — banner, synopsis, genres, episode grid with lock icons past the free gate, Play/Resume CTA
- `/watch/[slug]/[ep]` — fullscreen 9:16 player (hls.js; native HLS on Safari): tap to pause, arrow keys/swipe for prev-next, auto-advance on end, progress autosave every 5 s, paywall overlay on `403`
- `/plans` — pricing cards → Razorpay Checkout; `/account` — profile, subscription status, cancel, watch history
- `/my-list`, `/search`, `/genre/[slug]`, `/login`, `/signup`
- Guests: full browse + free episodes; login required for progress, watchlist, subscribing
- Mobile-first dark theme; server components fetch FastAPI directly; client components use a typed fetch wrapper that handles token refresh.

## 8. Error handling

- Uniform error envelope everywhere; frontend maps `403 subscription_required` → paywall, `401` → login redirect (after silent refresh attempt).
- Webhooks: signature check → 400 on mismatch; duplicate events no-op via unique constraint; handler errors return 500 so Razorpay retries.
- Ingest: any step failure marks episode `failed` and cleans up partial S3 uploads; CLI prints actionable error.
- Player: hls.js fatal errors → retry once, then user-facing error state with reload option.

## 9. Testing

- **Backend (pytest):** auth flows, entitlement rule matrix (free ep / no sub / active sub / expired sub / cancelled-but-in-period), webhook handlers with signed fixture payloads (activate/charge/cancel/duplicate), catalog endpoints. Tests run on SQLite (aiosqlite); models avoid Postgres-only column types so the schema stays portable.
- **Frontend:** TypeScript strict + build as the gate; typed API client; player and checkout verified manually against seeded content.
- **Seed script:** genres, 3–4 sample series (placeholder/public-domain vertical videos), plans — app is demo-able immediately after setup.

## 10. Environment variables

Backend: `DATABASE_URL` (pooled), `DIRECT_DATABASE_URL` (Alembic), `JWT_SECRET`, `STORAGE_MODE`, `AWS_*` + `S3_BUCKET`, `CLOUDFRONT_DOMAIN` + `CLOUDFRONT_KEY_PAIR_ID` + `CLOUDFRONT_PRIVATE_KEY` (s3 mode only), `IMAGEKIT_*`, `RAZORPAY_KEY_ID`, `RAZORPAY_KEY_SECRET`, `RAZORPAY_WEBHOOK_SECRET`, `FRONTEND_ORIGIN`.
Frontend: `NEXT_PUBLIC_API_URL`, `NEXT_PUBLIC_RAZORPAY_KEY_ID`.
