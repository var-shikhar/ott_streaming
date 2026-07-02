from tests.test_catalog import seed_catalog


def login(client):
    client.post("/api/v1/auth/signup", json={"email": "u@t.co", "password": "password1", "name": "U"})


def test_progress_upsert_and_continue(client, db):
    s = seed_catalog(db)
    ep = s.episodes[0]
    login(client)
    r = client.put(f"/api/v1/progress/{ep.id}", json={"position_seconds": 42, "completed": False})
    assert r.status_code == 200
    client.put(f"/api/v1/progress/{ep.id}", json={"position_seconds": 55, "completed": False})
    cw = client.get("/api/v1/progress/continue-watching").json()
    assert cw[0]["position_seconds"] == 55 and cw[0]["episode_number"] == 1


def test_progress_requires_auth(client, db):
    s = seed_catalog(db)
    r = client.put(f"/api/v1/progress/{s.episodes[0].id}",
                   json={"position_seconds": 1, "completed": False})
    assert r.status_code == 401


def test_watchlist_crud(client, db):
    s = seed_catalog(db)
    login(client)
    assert client.post("/api/v1/watchlist", json={"series_id": str(s.id)}).status_code == 201
    # duplicate add is idempotent
    assert client.post("/api/v1/watchlist", json={"series_id": str(s.id)}).status_code == 201
    assert [x["slug"] for x in client.get("/api/v1/watchlist").json()] == ["ceo-bride"]
    assert client.delete(f"/api/v1/watchlist/{s.id}").status_code == 200
    assert client.get("/api/v1/watchlist").json() == []
