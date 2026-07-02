from tests.test_catalog import seed_catalog


def login(client, email="u@t.co"):
    client.post("/api/v1/auth/signup", json={"email": email, "password": "password1", "name": "U"})


def test_like_requires_auth(client, db):
    s = seed_catalog(db)
    assert client.post(f"/api/v1/episodes/{s.episodes[0].id}/like").status_code == 401


def test_like_unlike_idempotent(client, db):
    s = seed_catalog(db)
    ep = s.episodes[0]
    login(client)
    r = client.post(f"/api/v1/episodes/{ep.id}/like")
    assert r.status_code == 200 and r.json() == {"liked": True, "like_count": 1}
    # double-like stays at 1
    assert client.post(f"/api/v1/episodes/{ep.id}/like").json()["like_count"] == 1
    r = client.delete(f"/api/v1/episodes/{ep.id}/like")
    assert r.json() == {"liked": False, "like_count": 0}


def test_series_detail_includes_social_stats(client, db):
    s = seed_catalog(db)
    ep = s.episodes[0]
    login(client)
    client.post(f"/api/v1/episodes/{ep.id}/like")
    client.post(f"/api/v1/episodes/{ep.id}/comments", json={"body": "so good"})
    eps = client.get("/api/v1/series/ceo-bride").json()["episodes"]
    assert eps[0]["like_count"] == 1 and eps[0]["liked_by_me"] is True
    assert eps[0]["comment_count"] == 1
    assert eps[1]["like_count"] == 0 and eps[1]["liked_by_me"] is False


def test_comments_crud(client, db):
    s = seed_catalog(db)
    ep = s.episodes[0]
    login(client)
    r = client.post(f"/api/v1/episodes/{ep.id}/comments", json={"body": "first!"})
    assert r.status_code == 201
    cid = r.json()["id"]
    listing = client.get(f"/api/v1/episodes/{ep.id}/comments").json()
    assert listing[0]["body"] == "first!" and listing[0]["user_name"] == "U"
    assert listing[0]["is_mine"] is True
    assert client.delete(f"/api/v1/comments/{cid}").status_code == 200
    assert client.get(f"/api/v1/episodes/{ep.id}/comments").json() == []


def test_cannot_delete_others_comment(client, db):
    s = seed_catalog(db)
    ep = s.episodes[0]
    login(client, "a@t.co")
    cid = client.post(f"/api/v1/episodes/{ep.id}/comments", json={"body": "mine"}).json()["id"]
    client.post("/api/v1/auth/logout")
    client.cookies.clear()
    login(client, "b@t.co")
    assert client.delete(f"/api/v1/comments/{cid}").status_code == 403


def test_empty_comment_rejected(client, db):
    s = seed_catalog(db)
    login(client)
    r = client.post(f"/api/v1/episodes/{s.episodes[0].id}/comments", json={"body": ""})
    assert r.status_code == 422
