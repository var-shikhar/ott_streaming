# Movies Mode — Design Spec

**Date:** 2026-07-03
**Status:** Approved (user delegated approval; proceed autonomously)

## Goal

Add a Netflix/Pocket-Films-style **Movies mode** alongside the existing reels mode: browse a
movie catalog (landscape 16:9 cards), open a rich detail page (metadata, cast & crew, stills
gallery, related movies), and play the film in a dedicated landscape-capable full-screen player.
Both modes coexist behind a **Reels | Movies** switcher in the top bar.

## Non-goals

- Trailers, ratings/reviews, awards metadata (future).
- Multi-episode movies or "seasons" — a movie is exactly one video.
- Desktop layout changes — the app stays a phone-shell UI (max-w-md).

## Data model (backend)

One catalog: movies live in the existing `series` table, discriminated by a new column.

### `Series` — new columns

| column | type | default | notes |
|---|---|---|---|
| `content_type` | `String(10)`, indexed | `"series"` | `"series"` \| `"movie"`; Alembic `server_default="series"` backfills existing rows |
| `release_year` | `Integer`, nullable | `NULL` | movie-grade metadata |
| `maturity_rating` | `String(20)` | `""` | e.g. `"U/A 13+"` |

A movie = one `Series` row (`content_type="movie"`) + **exactly one** `Episode`
(`episode_number=1`, landscape HLS). Movie duration is the episode's `duration_seconds`
(no duplicate column). Paywall reuses `entitlement.can_watch` **unchanged**:
`free_episode_count=1` → free movie, `0` → premium. Movie creation must set
`free_episode_count` explicitly (model default is 3).

### New tables

```
credits:  id int PK · series_id FK(index) · person_name String(120)
          · role String(30) ("director"|"cast"|"writer"|"producer")
          · character_name String(120) default "" · display_order int default 0
stills:   id int PK · series_id FK(index) · image_url String(500)
          · display_order int default 0
```

Both use cross-database types only (tests run on in-memory SQLite). One Alembic migration.
Credits/stills relationships hang off `Series` (`lazy="selectin"`), so series can adopt them
later for free.

## Backend API

All in `catalog.py` (same router, same error envelope). `series_out()` gains **additive**
fields: `content_type`, `release_year`, `maturity_rating`, `duration_seconds` (episode 1's
duration when movie, else 0). Additive ⇒ existing consumers (progress, watchlist) unaffected.

### Reels surfaces now filter `content_type == "series"`

- `GET /home` — featured/trending/new_releases/genre_rails/continue_watching exclude movies.
- `GET /series` — series only.
- `GET /genres/{slug}/series` — gains optional `?content_type=` (default `series`).
- `GET /search?q=` — gains optional `?content_type=` (omitted = mixed; results carry
  `content_type` so the client can branch cards/links).

### New movie endpoints

- `GET /movies/home` → `{featured, trending, new_releases, genre_rails, continue_watching}`
  — same shapes as `/home`, filtered to movies.
- `GET /movies` → `[series_out]` (all published movies, newest first).
- `GET /movies/{slug}` → movie detail:
  `series_out + { episode: {id, duration_seconds, thumbnail_url, is_free, locked},
  credits: [{person_name, role, character_name}], stills: [image_url],
  related: [series_out] }` (related = same-genre movies, newest first, limit 10).
  404 `not_found` if slug missing or `content_type != "movie"`.

**Unchanged:** `playback.py` (paywall 403 `subscription_required`), `progress.py` PUT,
`watchlist.py`, `social.py`, `media.py`, `entitlement.py`.
`GET /progress/continue-watching` stays mixed (account history) — payload now carries
`content_type` for link branching.

## Frontend

### Mode = route, not cookie

Movies mode lives under `/movies/*`. No cookie, no hydration flash, links are shareable.

- **TopBar** gains a centered segmented switcher: `Reels` → `/`, `Movies` → `/movies`;
  active state from `usePathname()` (movies active when pathname starts with `/movies`).
- **BottomNav** becomes mode-aware: when pathname starts with `/movies`, the Home tab's
  href/active target is `/movies` instead of `/`. Hide check extended:
  `pathname.startsWith("/watch/") || isMovieWatch(pathname)`.
- **TopBar hides for the first time ever** on the movie player route (immersive player);
  same pathname technique as BottomNav.

### New routes

| route | composition |
|---|---|
| `/movies` | landscape hero (banner_url, aspect-video, auto-rotate) · Continue Watching rail · Trending / New Releases / genre rails of 16:9 `MovieCard`s · matching `loading.tsx` (aspect-video skeletons) |
| `/movies/[slug]` | 16:9 banner + gradient · title · metadata line `year · rating · duration · genres` · synopsis · ▶ Play + `WatchlistButton` (drops in unchanged) · **Cast & Crew** section (director first, then cast with character names) · **Stills** horizontal gallery (`FallbackImage`, banner fallback) · **More Like This** rail · `loading.tsx` |
| `/movies/[slug]/watch` | server component fetches detail → client `MoviePlayer` |

### New components

`MovieCard` (aspect-video, w-40, caption = title + `year · Xm`; href `/movies/{slug}`),
`MovieRail` (RSC, parallels `Rail`), `MovieHero`, `CastList`, `StillsGallery`, `MoviePlayer`.

### `MoviePlayer` (the one genuinely new build)

- Reuses the proven recipes via a **new shared hook `useHlsPlayback(episodeId)`** extracted
  from `EpisodeSlide`: playback fetch → Safari native / `new Hls({capLevelToPlayerSize,
  xhrSetup withCredentials:true})` → resume seek on `loadedmetadata` → destroy on unmount →
  `locked` on `ApiError code === "subscription_required"`. `EpisodeSlide` is refactored to
  consume the same hook (pure refactor; the only-active-slide-attaches invariant stays in
  `EpisodeSlide`'s `active`/`loadedRef` gating, which remains untouched).
- Custom controls (none exist today): play/pause, scrub bar with buffered indicator,
  elapsed/total time, ±10 s skip, mute, fullscreen toggle, back button (→ detail page),
  auto-hide after 3 s of inactivity, tap to toggle controls.
- **Fullscreen:** container `requestFullscreen()` + best-effort
  `screen.orientation.lock("landscape")` (wrapped in try/catch — unsupported on iOS Safari;
  there, fall back to `video.webkitEnterFullscreen()`). Default (non-fullscreen) view:
  16:9 letterboxed video centered in the phone shell, `h-[100dvh]` black backdrop
  (TopBar hidden on this route).
- Progress heartbeats: same PUT `/progress/{episode_id}` pattern — ≥5 s throttle, flush on
  pause/ended (`completed: true`) — so continue-watching works for movies automatically.
- Paywall: `Paywall` gains props for copy + destination (`detailHref`, `message`) so the
  movie variant says "This film is for subscribers" and login `next=` points at
  `/movies/{slug}`; existing series usage keeps current copy via defaults.
- **PWA manifest `orientation` changes `"portrait"` → `"any"`** so installed-app users can
  rotate in fullscreen (reels screens remain portrait-designed and unaffected in practice).

### Shared surfaces

- `types.ts`: extend `SeriesSummary` (+`content_type`, `release_year`, `maturity_rating`,
  `duration_seconds`); add `Credit`, `MovieDetail`, reuse `HomeData` shape for movies home.
- `SeriesCard` stays portrait-only; every mixed surface branches on `content_type` to pick
  `SeriesCard` vs `MovieCard` (search results, my-list, genre grids).
- Search: filter chips `All | Series | Movies` driving `?content_type=`; placeholder copy
  "Search series & films...".
- My List: two sections — "Series" (grid-cols-3 of `SeriesCard`) and "Movies" (grid-cols-2
  of `MovieCard`); either section omitted when empty.
- Account watch history: branch href → `/movies/{slug}/watch` and copy (no "Ep N") when
  `content_type === "movie"`.
- Plans/paywall copy updated to mention films ("All episodes & films").

## Ingestion & seeding

### `transcode.py`

- `transcode_to_hls(src, outdir, orientation="portrait")`.
  Portrait ladder unchanged `[(1920,4000),(1280,2000),(854,1000)]`;
  landscape ladder `[(1080,4500),(720,2500),(480,1000)]` (height, kbps).
  Same `scale=-2:{height}` filter; master playlist RESOLUTION width computed per
  orientation (`h*16/9` for landscape instead of the hardcoded `h*9/16`).
  **Ascending-bitrate (lowest-first) master ordering is preserved — invariant.**
- `extract_thumbnail` generalized: `extract_frame(src, out_jpg, at_seconds=1.0, height=854)`
  so stills can be sampled across the runtime.

### `ingest.py`

New flags: `--content-type movie` (forces `episode_number=1`, requires/records movie fields),
`--release-year`, `--maturity-rating`, `--director "Name"`, `--cast "A:Char,B:Char"`,
`--stills N` (extract N frames evenly across duration, upload each).
For movies, `--free-episodes` semantic: `1` = free film, `0` = premium (default `0`).
`upload_thumbnail` generalized to `upload_image(name, jpg, placeholder_size)` — ImageKit when
configured, else picsum placeholder URL (never machine-local; landscape placeholders 640×360).

### `seed.py`

Adds 4 movie specs (landscape `testsrc2=size=1280x720` clips, ~30 s, distinct hues) with
release year, rating, director + 3 cast credits each, 4 stills each, mixed free/premium
(at least one `free_episode_count=0` to exercise the paywall). Reuses ingest primitives;
idempotent by slug, same as today.

## Testing

- **Backend (pytest, in-memory SQLite):** movies/home filtering (movies excluded from `/home`,
  series excluded from `/movies/home`); movie detail payload (credits ordering, stills,
  related same-genre, 404 for series slug on movie endpoint); entitlement — premium movie
  playback → 403 `subscription_required` without sub, 200 with; free movie plays anonymously;
  search `content_type` filter; `series_out` additive fields.
- **Transcode unit test:** landscape master playlist has ascending bitrate order + correct
  16:9 RESOLUTION strings (no ffmpeg needed — playlist writer is pure).
- **Frontend:** `npm run build` (type + lint gate) — the repo's standard.
- **End-to-end verify:** seed → run backend+frontend → drive movies home → detail → player
  (free plays; premium hits paywall) → progress resume.

## Risks & mitigations

- **EpisodeSlide refactor** touches the fragile active-slide invariant → hook extraction is
  mechanical (same code, new file); reels watch feed manually verified after.
- **iOS fullscreen/orientation quirks** → try/catch everywhere; worst case user rotates device.
- **Long movies vs 6 h CloudFront cookie expiry** → out of scope for demo content; noted.
- **Dev stills without ImageKit are picsum placeholders,** not real frames — acceptable for
  dev; prod ingest with ImageKit gets real frames.

## Docs

Update `docs/architecture.md`, `docs/api-reference.md`, `docs/content-ingestion.md`, and
`CLAUDE.md` (content model + movies-mode invariants: reels surfaces filter
`content_type="series"`; movie = 1 landscape episode, `episode_number=1`).
