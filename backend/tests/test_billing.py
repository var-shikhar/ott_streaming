from datetime import datetime, timedelta, timezone

import pytest

from app import models


class FakeSubAPI:
    def __init__(self):
        self.created, self.cancelled = [], []

    def create(self, data):
        self.created.append(data)
        return {"id": f"sub_fake{len(self.created)}", "status": "created"}

    def cancel(self, sub_id, data=None):
        self.cancelled.append(sub_id)
        return {"id": sub_id, "status": "cancelled"}


class FakeClient:
    def __init__(self):
        self.subscription = FakeSubAPI()


@pytest.fixture()
def fake_rzp(monkeypatch):
    fake = FakeClient()
    monkeypatch.setattr("app.routers.billing.get_razorpay_client", lambda: fake)
    return fake


def login(client):
    client.post("/api/v1/auth/signup", json={"email": "u@t.co", "password": "password1", "name": "U"})


def make_plan(db):
    p = models.Plan(name="Monthly", price_inr=14900, interval="monthly", razorpay_plan_id="plan_x")
    db.add(p)
    db.commit()
    return p


def test_list_plans(client, db):
    make_plan(db)
    body = client.get("/api/v1/plans").json()
    assert body[0]["name"] == "Monthly" and body[0]["price_inr"] == 14900


def test_create_subscription(client, db, fake_rzp):
    p = make_plan(db)
    login(client)
    r = client.post("/api/v1/subscriptions", json={"plan_id": p.id})
    assert r.status_code == 201
    assert r.json()["razorpay_subscription_id"] == "sub_fake1"
    assert fake_rzp.subscription.created[0]["plan_id"] == "plan_x"
    row = db.query(models.Subscription).one()
    assert row.status == "created"


def test_create_requires_auth(client, db, fake_rzp):
    p = make_plan(db)
    assert client.post("/api/v1/subscriptions", json={"plan_id": p.id}).status_code == 401


def test_already_subscribed_conflict(client, db, fake_rzp):
    p = make_plan(db)
    login(client)
    u = db.query(models.User).one()
    db.add(models.Subscription(user_id=u.id, plan_id=p.id, razorpay_subscription_id="sub_live",
                               status="active",
                               current_period_end=datetime.now(timezone.utc) + timedelta(days=5)))
    db.commit()
    r = client.post("/api/v1/subscriptions", json={"plan_id": p.id})
    assert r.status_code == 409 and r.json()["error"]["code"] == "already_subscribed"


def test_cancel_and_current(client, db, fake_rzp):
    p = make_plan(db)
    login(client)
    u = db.query(models.User).one()
    db.add(models.Subscription(user_id=u.id, plan_id=p.id, razorpay_subscription_id="sub_live",
                               status="active",
                               current_period_end=datetime.now(timezone.utc) + timedelta(days=5)))
    db.commit()
    cur = client.get("/api/v1/subscriptions/current").json()
    assert cur["status"] == "active" and cur["plan"]["name"] == "Monthly"
    assert client.post("/api/v1/subscriptions/cancel").status_code == 200
    assert fake_rzp.subscription.cancelled == ["sub_live"]


def test_current_none(client, db):
    login(client)
    assert client.get("/api/v1/subscriptions/current").json() is None
