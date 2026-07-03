from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings

app = FastAPI(title="ShortReel API")

app.add_middleware(
    CORSMiddleware,
    # FRONTEND_ORIGIN accepts a comma-separated list, e.g.
    # "http://localhost:3000,http://localhost:3001"
    allow_origins=[o.strip() for o in settings.frontend_origin.split(",") if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    detail = exc.detail if isinstance(exc.detail, dict) else {"code": "error", "message": str(exc.detail)}
    return JSONResponse(status_code=exc.status_code, content={"error": detail}, headers=exc.headers)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    first = exc.errors()[0] if exc.errors() else {}
    field = ".".join(str(p) for p in first.get("loc", []) if p != "body")
    message = f"{field}: {first.get('msg', 'invalid input')}" if field else first.get("msg", "Invalid input")
    return JSONResponse(status_code=422,
                        content={"error": {"code": "validation_error", "message": message}})


from app.routers import (auth, billing, catalog, media,  # noqa: E402
                         playback, progress, social, watchlist, webhooks)

app.include_router(auth.router)
app.include_router(social.router)
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
