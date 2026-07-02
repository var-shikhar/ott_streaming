# ShortReel — Deployment Guide (dev → production)

Everything runs locally with zero external services. Production is a set of env-var
swaps in `backend/.env` (see `backend/.env.example`) plus infra setup below.

## 1. Database — Neon Postgres

1. Create a Neon project → copy **two** connection strings:
   - Pooled (host contains `-pooler`) → `DATABASE_URL` (the app)
   - Direct (no `-pooler`) → `DIRECT_DATABASE_URL` (Alembic migrations)
   Use the `postgresql+psycopg://...?sslmode=require` form.
2. Run migrations: `cd backend && .venv/Scripts/alembic upgrade head`
3. Seed plans/genres (optionally content): `python -m app.seed`

Why two URLs: PgBouncer transaction pooling and DDL don't mix; the app pools, Alembic
goes direct.

## 2. Video — S3 + CloudFront signed cookies

1. Create a private S3 bucket (e.g. `shortreel-videos`), block all public access.
2. Create a CloudFront distribution with the bucket as origin (Origin Access Control).
3. Create a **key pair for signed cookies**: generate an RSA key
   (`openssl genrsa -out cloudfront_private_key.pem 2048`), upload the public key in
   CloudFront → Key management, add it to a **key group**, and set the distribution
   behavior to *Restrict viewer access* using that key group.
4. Serve API and CDN under one parent domain (e.g. `api.example.com` +
   `cdn.example.com`) so the API can set cookies the CDN receives.
5. Set env: `STORAGE_MODE=s3`, `AWS_REGION`, `S3_BUCKET`, `CLOUDFRONT_DOMAIN`,
   `CLOUDFRONT_KEY_PAIR_ID`, `CLOUDFRONT_PRIVATE_KEY_PATH`,
   `CDN_COOKIE_DOMAIN=.example.com`.
6. Re-ingest content (or copy `backend/media/*` to `s3://bucket/hls/` and update
   `episodes.hls_path` to `hls/<episode_id>/master.m3u8`).

Playback then returns CloudFront URLs and sets 6-hour signed cookies scoped to that
episode's path.

## 3. Payments — Razorpay

1. Get test/live keys → `RAZORPAY_KEY_ID`, `RAZORPAY_KEY_SECRET`.
2. Dashboard → Subscriptions → create the three plans (Weekly ₹49, Monthly ₹149,
   Yearly ₹999 or your pricing) and copy each `plan_...` id into the `plans` table
   (`razorpay_plan_id` column).
3. Dashboard → Webhooks → add `https://api.example.com/api/v1/webhooks/razorpay`,
   enable subscription events, set a secret → `RAZORPAY_WEBHOOK_SECRET`.
4. Frontend: set `NEXT_PUBLIC_RAZORPAY_KEY_ID` in the frontend env.

Local testing without real payments — simulate the activation webhook (replace SUB_ID):

```bash
.venv/Scripts/python -c "import hashlib, hmac, json, time, httpx; from app.config import settings; body=json.dumps({'event':'subscription.activated','payload':{'subscription':{'entity':{'id':'SUB_ID','current_start':int(time.time()),'current_end':int(time.time())+2592000}}}}).encode(); sig=hmac.new(settings.razorpay_webhook_secret.encode(), body, hashlib.sha256).hexdigest(); print(httpx.post('http://localhost:8000/api/v1/webhooks/razorpay', content=body, headers={'X-Razorpay-Signature':sig,'X-Razorpay-Event-Id':'evt_manual1','Content-Type':'application/json'}).text)"
```

## 4. Images — ImageKit

Set `IMAGEKIT_PUBLIC_KEY`, `IMAGEKIT_PRIVATE_KEY`, `IMAGEKIT_URL_ENDPOINT` and install
the SDK in the backend venv (`pip install imagekitio`). Ingest thumbnails then upload
to ImageKit automatically; series posters/banners accept any URL (point them at
ImageKit assets via `--poster-url`).

## 5. App hosting — Render (backend) + Vercel (frontend)

### Backend on Render

A blueprint is committed at the repo root (`render.yaml`) — "New + → Blueprint" on a
GitHub-connected repo picks it up. Manual setup equivalent:

- **Root Directory**: `backend` (the app is `backend/app/main.py`, not a root `main.py`)
- **Build command**: `pip install -r requirements.txt && alembic upgrade head`
  (migrations run against `DIRECT_DATABASE_URL` on every deploy — idempotent)
- **Start command**: `gunicorn -w 2 -k uvicorn.workers.UvicornWorker app.main:app --bind 0.0.0.0:$PORT`
  (must bind Render's `$PORT`; 2 workers fits the free tier)
- **Health check path**: `/health`
- Render's filesystem is **ephemeral** — production must use Neon (`DATABASE_URL`)
  and `STORAGE_MODE=s3`. SQLite/local media only exist for local dev.
- Ingest runs from your own machine (needs FFmpeg) pointed at the same Neon + S3 via
  a local `.env` — the Render service never transcodes.

### Frontend on Vercel

- Import the repo, set **Root Directory** to `frontend` (framework auto-detected).
- Env vars: `NEXT_PUBLIC_API_URL=https://<service>.onrender.com`,
  `NEXT_PUBLIC_RAZORPAY_KEY_ID=rzp_live_...`.

### Cross-domain cookies (IMPORTANT)

`*.vercel.app` and `*.onrender.com` are different registrable domains, so the auth
cookies must be sent cross-site:

- On Render set `COOKIE_SAMESITE=none` and `COOKIE_SECURE=true` (the blueprint does).
- `FRONTEND_ORIGIN` must be the exact Vercel origin (no trailing slash) for CORS.
- With custom domains under one parent (app.example.com + api.example.com) you can
  switch back to `COOKIE_SAMESITE=lax`.
- Note: some browsers (Safari ITP) restrict third-party cookies even with
  SameSite=None — custom domains under one parent are the robust long-term setup.

## 6. Production checklist

- [ ] `JWT_SECRET` rotated, `COOKIE_SECURE=true`
- [ ] Neon URLs set; `alembic upgrade head` run against Neon
- [ ] `STORAGE_MODE=s3`, CloudFront restricted to the key group, `CDN_COOKIE_DOMAIN` set
- [ ] Razorpay live keys + plan ids in DB + webhook URL/secret configured
- [ ] ImageKit keys set
- [ ] `FRONTEND_ORIGIN` / `API_BASE_URL` / `NEXT_PUBLIC_API_URL` point at real domains
- [ ] `cd backend && python -m pytest -q` green; `cd frontend && npm run build` green
