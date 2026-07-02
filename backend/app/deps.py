import uuid

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app import models
from app.db import get_db
from app.errors import ApiError
from app.security import decode_access_token


def _user_from_request(request: Request, db: Session) -> models.User | None:
    token = request.cookies.get("access_token")
    if not token:
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            token = auth.removeprefix("Bearer ")
    if not token:
        return None
    user_id = decode_access_token(token)
    if not user_id:
        return None
    try:
        return db.get(models.User, uuid.UUID(user_id))
    except ValueError:
        return None


def get_optional_user(request: Request, db: Session = Depends(get_db)) -> models.User | None:
    return _user_from_request(request, db)


def get_current_user(request: Request, db: Session = Depends(get_db)) -> models.User:
    user = _user_from_request(request, db)
    if user is None:
        raise ApiError(401, "unauthenticated", "Login required")
    return user
