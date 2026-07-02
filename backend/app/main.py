from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings

app = FastAPI(title="ShortReel API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    detail = exc.detail if isinstance(exc.detail, dict) else {"code": "error", "message": str(exc.detail)}
    return JSONResponse(status_code=exc.status_code, content={"error": detail}, headers=exc.headers)


from app.routers import (auth, billing, catalog, media,  # noqa: E402
                         playback, progress, watchlist, webhooks)

app.include_router(auth.router)
app.include_router(catalog.router)
app.include_router(progress.router)
app.include_router(watchlist.router)
app.include_router(billing.router)
app.include_router(webhooks.router)
app.include_router(playback.router)
app.include_router(media.router)


@app.get("/health")
def health():
    return {"status": "ok"}
