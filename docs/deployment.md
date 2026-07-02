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

## 5. App hosting

- **Backend**: any host that runs uvicorn (Railway/Render/Fly/EC2):
  `uvicorn app.main:app --host 0.0.0.0 --port 8000`. Set `JWT_SECRET` (long random),
  `COOKIE_SECURE=true`, `FRONTEND_ORIGIN=https://app.example.com`,
  `API_BASE_URL=https://api.example.com`.
- **Frontend**: Vercel is the natural fit (Next.js 16). Set
  `NEXT_PUBLIC_API_URL=https://api.example.com` and `NEXT_PUBLIC_RAZORPAY_KEY_ID`.
- Cookies are SameSite=Lax, so serve frontend and API from the **same parent domain**
  (app.example.com + api.example.com) for auth to work across them.

## 6. Production checklist

- [ ] `JWT_SECRET` rotated, `COOKIE_SECURE=true`
- [ ] Neon URLs set; `alembic upgrade head` run against Neon
- [ ] `STORAGE_MODE=s3`, CloudFront restricted to the key group, `CDN_COOKIE_DOMAIN` set
- [ ] Razorpay live keys + plan ids in DB + webhook URL/secret configured
- [ ] ImageKit keys set
- [ ] `FRONTEND_ORIGIN` / `API_BASE_URL` / `NEXT_PUBLIC_API_URL` point at real domains
- [ ] `cd backend && python -m pytest -q` green; `cd frontend && npm run build` green
