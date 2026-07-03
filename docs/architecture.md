# ShortReel — Architecture

## System overview

```
┌─────────────────────┐        ┌──────────────────────────┐
│  Next.js frontend    │  HTTPS │  FastAPI backend          │
│  (phone-shell UI,    │───────▶│  /api/v1/*                │
│  hls.js swipe feed)  │ cookies│  auth · catalog · social  │
└─────────────────────┘        │  billing · playback       │
        │                      └────────┬─────────┬────────┘
        │ HLS segments                  │         │
        ▼                               ▼         ▼
┌─────────────────────┐        ┌──────────────┐ ┌──────────────┐
│ CDN (CloudFront) or │        │ Postgres     │ │ Razorpay     │
│ local /media route  │        │ (Neon / dev  │ │ (webhooks →  │
│ signed cookies gate │        │  SQLite)     │ │  source of   │
└─────────────────────┘        └──────────────┘ │  truth)      │
                                                └──────────────┘
```

- The frontend is a pure UI layer: every data call hits FastAPI. Server components use
  `src/lib/api-server.ts` (forwards cookies), client components use `src/lib/api-client.ts`
  (silent refresh-retry on 401).
- One backend owns all business logic, so the future admin app reuses the same API.

## Backend layout (`backend/app/`)

| Module | Responsibility |
|---|---|
| `config.py` | All settings via env vars (pydantic-settings); dev defaults for everything |
| `db.py` | SQLAlchemy engine/session; SQLite dev default, Neon pooled URL in prod |
| `models.py` | All tables (see schema below) |
| `security.py` | bcrypt hashing, JWT access tokens, hashed rotating refresh tokens |
| `deps.py` | `get_current_user` (401) / `get_optional_user` dependencies |
| `entitlement.py` | THE access rule — single function used by playback, media, catalog |
| `routers/auth.py` | signup/login/refresh/logout/me; sets httpOnly cookies |
| `routers/catalog.py` | home rails, series detail (lock flags), genres, search |
| `routers/playback.py` | entitlement-gated playback URLs + CDN cookies + resume position |
| `routers/media.py` | local-mode HLS file serving (entitlement re-check on master.m3u8) |
| `routers/progress.py` / `watchlist.py` | watch progress upsert, continue-watching, my list |
| `routers/social.py` | likes, comments, batched `social_stats()` for episode payloads |
| `routers/billing.py` | plans, Razorpay subscription create/cancel/current |
| `routers/webhooks.py` | signature-verified, idempotent Razorpay event processing |
| `storage/` | `Storage` protocol; `local.py` (dev) and `s3.py` (S3 + CloudFront signed cookies) |
| `transcode.py` | FFmpeg HLS ladder (854/1280/1920 long side), master playlist, thumbnails |
| `ingest.py` | CLI to publish a video as an episode |
| `seed.py` | demo genres/plans/series with generated clips |

## Database schema

```
users ─┬─< refresh_tokens
       ├─< subscriptions >── plans
       ├─< watch_progress >── episodes
       ├─< watchlist >──── series
       ├─< episode_likes >─ episodes
       └─< comments >────── episodes

series ─< episodes            series >─< genres (series_genres)
series ─< credits             series ─< stills          (movies-mode metadata)
webhook_events (idempotency log, unique razorpay_event_id)
```

Key columns:
- `series.content_type` `series|movie` — one shared catalog, two UI modes. A movie is
  one series row + exactly one landscape episode (`episode_number=1`) plus `credits`
  (director/cast) and `stills` rows; `release_year`/`maturity_rating` are movie-grade
  metadata. Reels surfaces filter to `series`; `/api/v1/movies/*` serves movies mode.
- `series.free_episode_count` — first N episodes are free (default 3, seed uses 2);
  for movies it's the paywall switch: `1` = free film, `0` = premium (entitlement
  rule unchanged)
- `series.status` `draft|published`; `episodes.status` `processing|ready|failed` —
  only published+ready content is ever exposed by the API
- `subscriptions.status` `created|active|past_due|cancelled|expired` + `current_period_end`
- Money is INR paise; timestamps UTC; all types cross-database (tests run on SQLite)

## The entitlement rule

One function (`entitlement.can_watch`) used by playback, local media serving, and the
catalog lock flags:

> An episode is watchable iff `episode_number <= series.free_episode_count`
> OR the user has a subscription with `status IN ('active','cancelled')`
> AND `now < current_period_end`.

`cancelled` stays entitled because cancellation is at-period-end.

## Auth flow

- Signup/login issue two httpOnly cookies: `access_token` (15-min JWT) and
  `refresh_token` (30 days, stored sha256-hashed in DB, rotated on every refresh,
  revocable).
- Guests can browse everything and watch free episodes; progress/watchlist/likes/
  comments/billing require auth (401 → frontend silently refreshes, then redirects
  to login if that fails).

## Video pipeline

```
video file ─▶ ingest CLI ─▶ FFmpeg: 3-rendition HLS ladder + master playlist
                         ─▶ Storage.publish()          ─▶ thumbnail (ImageKit or local)
                              │
              STORAGE_MODE=local            STORAGE_MODE=s3
              backend/media/<episode_id>/   s3://bucket/hls/<episode_id>/
              served by /media route        served by CloudFront
              (entitlement check on         (signed cookies scoped to
               master.m3u8)                  hls/<episode_id>/*, 6 h TTL)
```

- Master playlists list the **lowest rendition first** so playback starts instantly;
  hls.js then adapts up (frontend also sets `capLevelToPlayerSize`).
- `GET /episodes/{id}/playback` does the entitlement check, bumps `view_count`,
  returns the playlist URL + `resume_position`, and (s3 mode) sets the CloudFront
  cookies. Locked → `403 {code: subscription_required}` → frontend paywall.

## Subscription lifecycle

```
POST /subscriptions ─▶ Razorpay subscription created (status "created" locally)
        │
   Razorpay Checkout (frontend modal)
        │
   webhooks (source of truth, NOT the checkout callback):
     subscription.activated / charged  → active + period start/end
     subscription.cancelled            → cancelled (entitled until period end)
     subscription.completed / expired  → expired
     subscription.pending              → past_due
```

Webhooks are HMAC-SHA256 verified and idempotent (unique `razorpay_event_id`;
duplicates return `{"status": "duplicate"}` without reprocessing).

## Frontend layout (`frontend/src/`)

- `app/layout.tsx` — phone shell: `max-w-md` column, `TopBar`, `BottomNav`
  (hidden on `/watch/*`)
- `app/page.tsx` — hero carousel + Continue Watching + genre rails
- `app/watch/[slug]/[ep]` — **SwipeFeed**: vertical snap-scroll, one slide per
  episode; only the active slide attaches an hls.js player; URL syncs via
  `history.replaceState`; auto-advance scrolls to the next slide; locked episodes
  render the paywall as a slide
- `components/EpisodeSlide.tsx` — playback, tap-pause, progress autosave (5 s),
  autoplay-mute fallback ("Tap for sound")
- `components/ActionRail.tsx` / `CommentsSheet.tsx` — like/share buttons and the
  bottom-sheet comments UI
- **Movies mode** — `TopBar` hosts a `Reels | Movies` segmented switcher (mode is
  route-based: everything under `/movies/*`). `app/movies` = landscape hero + 16:9
  `MovieRail`s; `app/movies/[slug]` = detail (metadata line, `CastList`,
  `StillsGallery`, More Like This); `app/movies/[slug]/watch` = `MoviePlayer`, a
  `fixed inset-0` landscape player (custom controls: scrub bar + buffered indicator,
  ±10 s, mute, fullscreen with best-effort orientation lock) built on
  `lib/use-hls-playback.ts` (hls/mp4 attach + resume + paywall detection; YouTube
  sources surface as `youtubeId` and render the official embed). `TopBar` and
  `BottomNav` self-hide on the movie watch route; `BottomNav`'s Home tab retargets
  to `/movies` while in movies mode
- Skeleton `loading.tsx` files + shimmer/fade utilities in `globals.css`

## Error contract

Every API error: `{"error": {"code": "...", "message": "..."}}` (including 422
validation). `401 unauthenticated` → login flow; `403 subscription_required` →
paywall; webhook handler errors → 500 so Razorpay retries.
