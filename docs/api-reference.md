# ShortReel — API Reference

Base URL: `http://localhost:8000` (interactive docs at `/docs`). All routes under `/api/v1`
unless noted. Auth is cookie-based (`access_token` httpOnly JWT); protected routes return
`401 {"error":{"code":"unauthenticated"}}` without it.

**Error envelope (all errors, including validation):**

```json
{ "error": { "code": "subscription_required", "message": "Subscribe to watch this episode" } }
```

## Auth

| Method & path | Auth | Body | Returns |
|---|---|---|---|
| `POST /auth/signup` | – | `{email, password (≥8), name}` | `201 {id, email, name}` + session cookies. `409 email_taken` |
| `POST /auth/login` | – | `{email, password}` | `200` user + cookies. `401 invalid_credentials` |
| `POST /auth/refresh` | refresh cookie | – | rotates both cookies. `401 invalid_refresh` if revoked/expired |
| `POST /auth/logout` | – | – | revokes refresh token, clears cookies |
| `GET /auth/me` | ✓ | – | `{id, email, name}` |

## Catalog (public)

| Method & path | Returns |
|---|---|
| `GET /home` | `{featured, trending, new_releases, genre_rails: [{genre, series}], continue_watching}` (continue_watching filled when authenticated) |
| `GET /series` | `SeriesOut[]` |
| `GET /series/{slug}` | `SeriesOut` + `episodes: EpisodeOut[]`. `404 not_found` |
| `GET /genres` | `[{slug, name}]` |
| `GET /genres/{slug}/series` | `{genre, series}` |
| `GET /search?q=text` | `SeriesOut[]` (title match, max 20) |

**SeriesOut:** `{id, slug, title, synopsis, language, poster_url, banner_url,
free_episode_count, is_featured, view_count, genres: [name], episode_count}`

**EpisodeOut:** `{id, episode_number, title, duration_seconds, thumbnail_url,
is_free, locked, like_count, comment_count, liked_by_me}` — `locked` already accounts
for the caller's subscription.

Only `published` series and `ready` episodes are ever returned.

## Playback

| Method & path | Auth | Notes |
|---|---|---|
| `GET /episodes/{id}/playback` | optional | Entitlement-gated. `200 {url, episode_id, episode_number, series_slug, resume_position}`; in s3 mode also sets CloudFront signed cookies. `403 subscription_required` when locked, `404` when missing/not-ready. Increments series view_count. |
| `GET /media/{episode_id}/{file}` | optional | Local mode only — serves HLS/thumbnails; re-checks entitlement on `master.m3u8`. |

## Progress & watchlist (auth required)

| Method & path | Body | Returns |
|---|---|---|
| `PUT /progress/{episode_id}` | `{position_seconds ≥ 0, completed}` | upsert, `{status: "ok"}` |
| `GET /progress/continue-watching` | – | `[{series, episode_number, episode_id, position_seconds}]` (latest 10, incomplete only) |
| `GET /watchlist` | – | `SeriesOut[]` |
| `POST /watchlist` | `{series_id}` | `201` (idempotent) |
| `DELETE /watchlist/{series_id}` | – | `{status: "ok"}` |

## Social

| Method & path | Auth | Returns |
|---|---|---|
| `POST /episodes/{id}/like` | ✓ | `{liked: true, like_count}` (idempotent) |
| `DELETE /episodes/{id}/like` | ✓ | `{liked: false, like_count}` |
| `GET /episodes/{id}/comments` | optional | newest-first, max 100: `[{id, body, created_at, user_name, is_mine}]` |
| `POST /episodes/{id}/comments` | ✓ | body `{body: 1–500 chars}` → `201` comment |
| `DELETE /comments/{id}` | ✓ | own comments only; `403 forbidden` otherwise |

## Billing

| Method & path | Auth | Notes |
|---|---|---|
| `GET /plans` | – | `[{id, name, price_inr (paise), interval}]` active plans, cheapest first |
| `POST /subscriptions` | ✓ | `{plan_id}` → `201 {razorpay_subscription_id, razorpay_key_id}` for Razorpay Checkout. `409 already_subscribed` |
| `POST /subscriptions/cancel` | ✓ | cancel-at-cycle-end; access continues until period end. `404 no_subscription` |
| `GET /subscriptions/current` | ✓ | `{status, plan, current_period_end}` or `null` |
| `POST /webhooks/razorpay` | HMAC | Headers: `X-Razorpay-Signature` (HMAC-SHA256 hex of raw body with webhook secret), `X-Razorpay-Event-Id` (idempotency). Handles `subscription.activated/charged/cancelled/completed/expired/pending`. `400 bad_signature` on mismatch; duplicates → `{"status": "duplicate"}` |

## Misc

- `GET /health` → `{status: "ok"}`
