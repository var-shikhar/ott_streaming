# Qisso — Content Ingestion Guide

How video content gets into the platform today (CLI-based; the same pipeline code will
back the admin panel's upload API later).

## Prerequisites

- FFmpeg + ffprobe on PATH (`winget install Gyan.FFmpeg`, then restart the shell)
- Backend configured (`backend/.env`); with no `.env` everything runs locally
  (SQLite + `backend/media/` + placeholder images)

## Ingest a video

From `backend/`:

```bash
.venv/Scripts/python -m app.ingest path/to/episode1.mp4 \
  --series-slug my-show \
  --series-title "My Show" \
  --episode-number 1 \
  --episode-title "The Beginning" \
  --synopsis "One-line synopsis shown on the series page" \
  --language en \
  --genres romance,drama \
  --free-episodes 3 \
  --featured
```

What happens, in order:

1. Series is created if the slug doesn't exist (genres auto-created from slugs;
   poster/banner default to placeholder URLs unless `--poster-url`/`--banner-url` given).
2. Episode row is created/updated with status **`processing`** — invisible in the app.
3. FFmpeg transcodes to a 3-rendition vertical HLS ladder (long side 854 / 1280 / 1920,
   4-second segments) + a master playlist listing the lowest rendition first.
4. `Storage.publish()` uploads the HLS directory — `backend/media/<episode_id>/` in
   local mode, `s3://$S3_BUCKET/hls/<episode_id>/` in s3 mode.
5. A thumbnail frame is extracted and uploaded to **ImageKit** when the `IMAGEKIT_*`
   keys are set, otherwise stored next to the HLS files and served via `/media`.
6. Episode flips to **`ready`** and appears in the app immediately.

Any failure marks the episode **`failed`** (never shown in the catalog) and exits with
the error. Re-running the same command retries that episode in place — series/episode
rows are matched by slug + episode number, so ingest is idempotent.

## Recommended source format

- Portrait 9:16 (e.g. 1080×1920); landscape works but will letterbox in the player
- H.264 + AAC input transcodes fastest; anything FFmpeg can read is accepted
- 1–3 minute episodes (the product's format); any duration technically works

## Video quality ladder

Defined in `backend/app/transcode.py` (`RENDITIONS`):

| Rendition (long side) | Video bitrate | Audio |
|---|---|---|
| 854 px | 1000 kbps | AAC 128k |
| 1280 px | 2000 kbps | AAC 128k |
| 1920 px | 4000 kbps | AAC 128k |

Adjust the list to change quality/cost; both ingest and seed pick it up automatically.

## Ingest a movie (Movies mode)

A movie is one catalog row + one **landscape** video (episode 1 internally):

```bash
.venv/Scripts/python -m app.ingest path/to/film.mp4 \
  --series-slug daal --series-title "Daal" \
  --content-type movie \
  --release-year 2025 --maturity-rating "U/A 13+" \
  --director "Arjun Mehta" \
  --cast "Riya Sen:Asha,Vik Das:Bhola" \
  --stills 4 \
  --genres drama --synopsis "..." --featured
```

Differences from series ingest:

- Transcodes to the **landscape ladder** (480/720/1080, 16:9 master playlist,
  still lowest-rendition-first).
- `--free-episodes` defaults to **0 = premium**; pass `--free-episodes 1` for a free film.
- `--director` / `--cast "Name:Character,..."` become `credits` rows (director first).
- `--stills N` extracts N frames evenly across the runtime for the detail-page gallery
  (ImageKit when configured, placeholder URLs otherwise).
- Credits/stills are only written the first time (idempotent per slug).

## Demo data

`python -m app.seed` creates 5 genres, 3 plans, 4 demo series × 5 episodes, and
4 demo movies (landscape clips with credits + stills; one free, three premium) with
FFmpeg-generated test clips. Idempotent — existing slugs are skipped.

## Freemium gate

`--free-episodes N` sets `series.free_episode_count`: episodes 1..N are free for
everyone, the rest require an active subscription. Change it later with a one-line DB
update; the API computes lock state per request.

## Later: admin panel

The planned admin upload flow reuses this exact pipeline: an upload endpoint will save
the file, then run `transcode → publish → thumbnail → ready` as a background job.
Nothing in the CLI is throwaway.
