import hashlib
import hmac
import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import models
from app.config import settings
from app.db import get_db
from app.errors import ApiError

router = APIRouter(prefix="/api/v1/webhooks", tags=["webhooks"])

STATUS_BY_EVENT = {
    "subscription.activated": "active",
    "subscription.charged": "active",
    "subscription.cancelled": "cancelled",
    "subscription.completed": "expired",
    "subscription.expired": "expired",
    "subscription.pending": "past_due",
}


@router.post("/razorpay")
async def razorpay_webhook(request: Request, db: Session = Depends(get_db)):
    body = await request.body()
    signature = request.headers.get("X-Razorpay-Signature", "")
    expected = hmac.new(settings.razorpay_webhook_secret.encode(), body,
                        hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, signature):
        raise ApiError(400, "bad_signature", "Webhook signature mismatch")

    event = json.loads(body)
    event_id = request.headers.get("X-Razorpay-Event-Id") or hashlib.sha256(body).hexdigest()
    db.add(models.WebhookEvent(razorpay_event_id=event_id,
                               event_type=event.get("event", ""), payload=event))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return {"status": "duplicate"}

    event_type = event.get("event", "")
    new_status = STATUS_BY_EVENT.get(event_type)
    entity = (event.get("payload", {}).get("subscription", {}) or {}).get("entity", {})
    rzp_sub_id = entity.get("id", "")
    if new_status and rzp_sub_id:
        sub = (db.query(models.Subscription)
                 .filter(models.Subscription.razorpay_subscription_id == rzp_sub_id).first())
        if sub:
            sub.status = new_status
            if new_status == "active":
                if entity.get("current_start"):
                    sub.current_period_start = datetime.fromtimestamp(
                        entity["current_start"], tz=timezone.utc)
                if entity.get("current_end"):
                    sub.current_period_end = datetime.fromtimestamp(
                        entity["current_end"], tz=timezone.utc)
            db.commit()
    return {"status": "processed"}
