import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app import models
from app.entitlement import can_watch


def make_series(db, free=2):
    s = models.Series(slug=f"s-{uuid.uuid4().hex[:6]}", title="S", free_episode_count=free)
    db.add(s)
    db.flush()
    eps = []
    for n in (1, 2, 3):
        e = models.Episode(series_id=s.id, episode_number=n, status="ready")
        db.add(e)
        eps.append(e)
    db.commit()
    return s, eps


def make_user(db):
    u = models.User(email=f"{uuid.uuid4().hex[:8]}@t.co", password_hash="x", name="U")
    db.add(u)
    db.commit()
    return u


def make_sub(db, user, status, ends_in_days):
    p = models.Plan(name="M", price_inr=14900, interval="monthly")
    db.add(p)
    db.flush()
    sub = models.Subscription(
        user_id=user.id, plan_id=p.id, razorpay_subscription_id=f"sub_{uuid.uuid4().hex[:8]}",
        status=status, current_period_end=datetime.now(timezone.utc) + timedelta(days=ends_in_days))
    db.add(sub)
    db.commit()
    return sub


def test_free_episode_watchable_by_guest(db):
    _, eps = make_series(db, free=2)
    assert can_watch(db, None, eps[0]) is True
    assert can_watch(db, None, eps[1]) is True


def test_locked_episode_blocked_for_guest_and_unsubscribed(db):
    _, eps = make_series(db, free=2)
    assert can_watch(db, None, eps[2]) is False
    assert can_watch(db, make_user(db), eps[2]) is False


@pytest.mark.parametrize("status,days,expected", [
    ("active", 10, True),
    ("cancelled", 10, True),   # cancelled but still inside paid period
    ("active", -1, False),     # period lapsed
    ("expired", 10, False),
    ("created", 10, False),
    ("past_due", 10, False),
])
def test_subscription_states(db, status, days, expected):
    _, eps = make_series(db, free=2)
    u = make_user(db)
    make_sub(db, u, status, days)
    assert can_watch(db, u, eps[2]) is expected
