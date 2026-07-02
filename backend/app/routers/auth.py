from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from app import models
from app.config import settings
from app.db import get_db
from app.deps import get_current_user
from app.errors import ApiError
from app.security import (create_access_token, hash_password, hash_refresh,
                          new_refresh_token, verify_password)

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


class SignupIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    name: str = Field(min_length=1, max_length=120)


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: str
    email: str
    name: str


def _user_out(user: models.User) -> UserOut:
    return UserOut(id=str(user.id), email=user.email, name=user.name)


def _issue_session(response: Response, db: Session, user: models.User) -> None:
    raw, token_hash = new_refresh_token()
    db.add(models.RefreshToken(
        user_id=user.id, token_hash=token_hash,
        expires_at=datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_days)))
    db.commit()
    common = dict(httponly=True, samesite="lax", secure=settings.cookie_secure)
    response.set_cookie("access_token", create_access_token(str(user.id)),
                        max_age=settings.access_token_minutes * 60, **common)
    response.set_cookie("refresh_token", raw,
                        max_age=settings.refresh_token_days * 86400, **common)


@router.post("/signup", status_code=201)
def signup(body: SignupIn, response: Response, db: Session = Depends(get_db)) -> UserOut:
    if db.query(models.User).filter(models.User.email == body.email.lower()).first():
        raise ApiError(409, "email_taken", "An account with this email already exists")
    user = models.User(email=body.email.lower(), password_hash=hash_password(body.password), name=body.name)
    db.add(user)
    db.commit()
    _issue_session(response, db, user)
    return _user_out(user)


@router.post("/login")
def login(body: LoginIn, response: Response, db: Session = Depends(get_db)) -> UserOut:
    user = db.query(models.User).filter(models.User.email == body.email.lower()).first()
    if not user or not verify_password(body.password, user.password_hash):
        raise ApiError(401, "invalid_credentials", "Invalid email or password")
    _issue_session(response, db, user)
    return _user_out(user)


@router.post("/refresh")
def refresh(request: Request, response: Response, db: Session = Depends(get_db)) -> UserOut:
    raw = request.cookies.get("refresh_token")
    if not raw:
        raise ApiError(401, "unauthenticated", "Missing refresh token")
    row = db.query(models.RefreshToken).filter(models.RefreshToken.token_hash == hash_refresh(raw)).first()
    now = datetime.now(timezone.utc)
    if not row or row.revoked_at is not None:
        raise ApiError(401, "invalid_refresh", "Session expired, please log in again")
    expires_at = row.expires_at if row.expires_at.tzinfo else row.expires_at.replace(tzinfo=timezone.utc)
    if expires_at < now:
        raise ApiError(401, "invalid_refresh", "Session expired, please log in again")
    row.revoked_at = now
    user = db.get(models.User, row.user_id)
    _issue_session(response, db, user)
    return _user_out(user)


@router.post("/logout")
def logout(request: Request, response: Response, db: Session = Depends(get_db)):
    raw = request.cookies.get("refresh_token")
    if raw:
        row = db.query(models.RefreshToken).filter(models.RefreshToken.token_hash == hash_refresh(raw)).first()
        if row:
            row.revoked_at = datetime.now(timezone.utc)
            db.commit()
    response.delete_cookie("access_token")
    response.delete_cookie("refresh_token")
    return {"status": "ok"}


@router.get("/me")
def me(user: models.User = Depends(get_current_user)) -> UserOut:
    return _user_out(user)
