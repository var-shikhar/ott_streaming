import hashlib
import hmac
import json
import time
import uuid

from app import models
from app.config import settings


def make_sub(db, status="created"):
    u = models.User(email=f"{uuid.uuid4().hex[:8]}@t.co", password_hash="x", name="U")
    p = models.Plan(name="M", price_inr=14900, interval="monthly", razorpay_plan_id="plan_x")
    db.add_all([u, p])
    db.flush()
    sub = models.Subscription(user_id=u.id, plan_id=p.id,
                              razorpay_subscription_id="sub_live", status=status)
    db.add(sub)
    db.commit()
    return sub


def send(client, event_type, sub_id="sub_live", event_id=None, sig=None):
    now = int(time.time())
    payload = {"event": event_type, "payload": {"subscription": {"entity": {
        "id": sub_id, "current_start": now, "current_end": now + 30 * 86400}}}}
    body = json.dumps(payload).encode()
    signature = sig or hmac.new(settings.razorpay_webhook_secret.encode(), body,
                                hashlib.sha256).hexdigest()
    return client.post("/api/v1/webhooks/razorpay", content=body, headers={
        "X-Razorpay-Signature": signature,
        "X-Razorpay-Event-Id": event_id or f"evt_{uuid.uuid4().hex[:10]}",
        "Content-Type": "application/json",
    })


def test_bad_signature_rejected(client, db):
    make_sub(db)
    assert send(client, "subscription.activated", sig="deadbeef").status_code == 400


def test_activated_sets_active_and_period(client, db):
    sub = make_sub(db)
    assert send(client, "subscription.activated").status_code == 200
    db.refresh(sub)
    assert sub.status == "active" and sub.current_period_end is not None


def test_duplicate_event_ignored(client, db):
    sub = make_sub(db)
    assert send(client, "subscription.activated", event_id="evt_dup").status_code == 200
    sub.status = "created"
    db.commit()
    r = send(client, "subscription.activated", event_id="evt_dup")
    assert r.status_code == 200 and r.json()["status"] == "duplicate"
    db.refresh(sub)
    assert sub.status == "created"  # not reprocessed


def test_cancelled_and_expired(client, db):
    sub = make_sub(db, status="active")
    send(client, "subscription.cancelled")
    db.refresh(sub)
    assert sub.status == "cancelled"
    send(client, "subscription.completed")
    db.refresh(sub)
    assert sub.status == "expired"


def test_unknown_subscription_is_noop(client, db):
    assert send(client, "subscription.activated", sub_id="sub_ghost").status_code == 200
