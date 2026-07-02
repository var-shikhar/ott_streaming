# ShortReel — Short-Drama Streaming Platform

A subscription-based, **mobile-first** OTT web app for vertical micro-dramas (DramaBox / Tadka style): series of 1–3 minute portrait episodes where the first few episodes are free and the rest unlock with a Razorpay subscription.

- **Frontend**: Next.js 16 (App Router), Tailwind v4, hls.js — phone-shell UI with bottom tab navigation
- **Backend**: FastAPI, SQLAlchemy 2 + Alembic, JWT auth (httpOnly cookies)
- **Database**: SQLite for dev out-of-the-box; Neon Postgres in production
- **Video**: S3 originals → FFmpeg HLS ladder (1080/720/480) → CloudFront signed cookies; fully local dev mode with zero cloud setup
- **Images**: ImageKit (thumbnails) with local fallback; **Payments**: Razorpay Subscriptions

## Prerequisites

- Python 3.11+, Node 20+
- FFmpeg on PATH (`winget install Gyan.FFmpeg` on Windows — restart your shell after)

## Quick start (fully local, no cloud accounts needed)

**Backend** (from `backend/`):

```bash
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt      # Windows (POSIX: .venv/bin/pip)
.venv/Scripts/alembic upgrade head                 # creates dev.db
.venv/Scripts/python -m app.seed                   # demo series + plans (needs FFmpeg, ~2 min)
.venv/Scripts/uvicorn app.main:app --reload --port 8000
```

**Frontend** (from `frontend/`):

```bash
npm install
npm run dev        # http://localhost:3000
```

`frontend/.env.local` defaults to `NEXT_PUBLIC_API_URL=http://localhost:8000`.

## Environment variables (backend/.env)

See `backend/.env.example` for the full annotated list. Everything defaults to local dev. Key groups:

| Group | Keys | Notes |
|---|---|---|
| Database | `DATABASE_URL`, `DIRECT_DATABASE_URL` | Neon **pooled** URL for the app, **direct** URL for Alembic |
| Auth | `JWT_SECRET`, `COOKIE_SECURE` | set both in production |
| Video | `STORAGE_MODE` (`local`/`s3`), `S3_BUCKET`, `CLOUDFRONT_*`, `CDN_COOKIE_DOMAIN` | s3 mode signs CloudFront cookies |
| Images | `IMAGEKIT_PUBLIC_KEY`, `IMAGEKIT_PRIVATE_KEY`, `IMAGEKIT_URL_ENDPOINT` | optional; local file fallback |
| Payments | `RAZORPAY_KEY_ID`, `RAZORPAY_KEY_SECRET`, `RAZORPAY_WEBHOOK_SECRET` | test keys work |

## Adding content (ingest CLI)

```bash
.venv/Scripts/python -m app.ingest path/to/video.mp4 \
  --series-slug my-show --series-title "My Show" \
  --episode-number 1 --episode-title "Pilot" \
  --genres romance,drama --free-episodes 3 --featured
```

Transcodes to a 3-rendition HLS ladder, publishes to the configured storage, extracts a thumbnail (ImageKit if configured), and creates/updates the DB rows. Failures mark the episode `failed` (never shown in the catalog).

## Testing the paid flow without real payments

1. Sign up in the app, click Subscribe on a plan (with dummy Razorpay keys the checkout fails after creating a `created` subscription row — that's expected).
2. Find the `razorpay_subscription_id` (e.g. `sqlite3 dev.db "select razorpay_subscription_id from subscriptions"`).
3. Simulate the activation webhook:

```bash
.venv/Scripts/python -c "import hashlib, hmac, json, time, httpx; from app.config import settings; body=json.dumps({'event':'subscription.activated','payload':{'subscription':{'entity':{'id':'SUB_ID_HERE','current_start':int(time.time()),'current_end':int(time.time())+2592000}}}}).encode(); sig=hmac.new(settings.razorpay_webhook_secret.encode(), body, hashlib.sha256).hexdigest(); print(httpx.post('http://localhost:8000/api/v1/webhooks/razorpay', content=body, headers={'X-Razorpay-Signature':sig,'X-Razorpay-Event-Id':'evt_manual1','Content-Type':'application/json'}).text)"
```

Locked episodes now play and `/account` shows the active plan.

## Going to production

1. **Neon**: set `DATABASE_URL` (pooled) + `DIRECT_DATABASE_URL`; run `alembic upgrade head`.
2. **Video**: `STORAGE_MODE=s3`; create an S3 bucket + CloudFront distribution restricted to signed cookies (trusted key group); set `CLOUDFRONT_DOMAIN`, `CLOUDFRONT_KEY_PAIR_ID`, `CLOUDFRONT_PRIVATE_KEY_PATH`; serve API and CDN under one parent domain and set `CDN_COOKIE_DOMAIN=.yourdomain.com`.
3. **Razorpay**: real keys; create plans in the dashboard and copy each plan id into `plans.razorpay_plan_id`; point the webhook to `https://api.yourdomain.com/api/v1/webhooks/razorpay` with your `RAZORPAY_WEBHOOK_SECRET`.
4. **ImageKit**: set the three `IMAGEKIT_*` keys so thumbnails upload there.
5. Set `JWT_SECRET`, `COOKIE_SECURE=true`, `FRONTEND_ORIGIN`, `API_BASE_URL`.

## Tests

```bash
cd backend && .venv/Scripts/python -m pytest -q   # 41 tests
cd frontend && npm run build                       # type + lint gate
```
