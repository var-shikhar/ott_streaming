from datetime import datetime, timedelta, timezone

from app import models
from tests.test_catalog import seed_catalog


def login(client):
    client.post("/api/v1/auth/signup", json={"email": "u@t.co", "password": "password1", "name": "U"})


def subscribe(db):
    u = db.query(models.User).one()
    p = models.Plan(name="M", price_inr=14900, interval="monthly")
    db.add(p)
    db.flush()
    db.add(models.Subscription(user_id=u.id, plan_id=p.id, razorpay_subscription_id="sub_t",
                               status="active",
                               current_period_end=datetime.now(timezone.utc) + timedelta(days=5)))
    db.commit()


def prep_hls(db):
    s = seed_catalog(db)
    for e in s.episodes:
        e.hls_path = f"{e.id}/master.m3u8"
    db.commit()
    return s


def test_free_episode_playback_guest(client, db):
    s = prep_hls(db)
    ep = s.episodes[0]
    r = client.get(f"/api/v1/episodes/{ep.id}/playback")
    assert r.status_code == 200
    body = r.json()
    assert body["url"].endswith(f"/media/{ep.id}/master.m3u8")
    assert body["resume_position"] == 0
    db.refresh(s)
    assert s.view_count == 101  # incremented


def test_locked_episode_403_guest_and_unsubscribed(client, db):
    s = prep_hls(db)
    ep = s.episodes[2]  # episode 3, free_episode_count=2
    r = client.get(f"/api/v1/episodes/{ep.id}/playback")
    assert r.status_code == 403 and r.json()["error"]["code"] == "subscription_required"
    login(client)
    assert client.get(f"/api/v1/episodes/{ep.id}/playback").status_code == 403


def test_locked_episode_ok_for_subscriber(client, db):
    s = prep_hls(db)
    login(client)
    subscribe(db)
    assert client.get(f"/api/v1/episodes/{s.episodes[2].id}/playback").status_code == 200


def test_resume_position_returned(client, db):
    s = prep_hls(db)
    ep = s.episodes[0]
    login(client)
    client.put(f"/api/v1/progress/{ep.id}", json={"position_seconds": 33, "completed": False})
    assert client.get(f"/api/v1/episodes/{ep.id}/playback").json()["resume_position"] == 33


def test_processing_episode_404(client, db):
    s = prep_hls(db)
    processing = [e for e in s.episodes if e.status == "processing"][0]
    assert client.get(f"/api/v1/episodes/{processing.id}/playback").status_code == 404
