from app import models


def seed_catalog(db):
    g = models.Genre(slug="romance", name="Romance")
    db.add(g)
    s1 = models.Series(slug="ceo-bride", title="CEO's Secret Bride", is_featured=True,
                       view_count=100, free_episode_count=2, genres=[g])
    s2 = models.Series(slug="draft-show", title="Hidden", status="draft")
    db.add_all([s1, s2])
    db.flush()
    for n in (1, 2, 3):
        db.add(models.Episode(series_id=s1.id, episode_number=n, status="ready", title=f"Ep {n}"))
    db.add(models.Episode(series_id=s1.id, episode_number=4, status="processing"))
    db.commit()
    return s1


def test_home_shape(client, db):
    seed_catalog(db)
    r = client.get("/api/v1/home")
    assert r.status_code == 200
    body = r.json()
    assert body["featured"][0]["slug"] == "ceo-bride"
    assert body["trending"][0]["episode_count"] == 3  # processing episode excluded
    assert body["genre_rails"][0]["genre"]["slug"] == "romance"
    assert body["continue_watching"] == []
    slugs = [s["slug"] for s in body["new_releases"]]
    assert "draft-show" not in slugs


def test_series_detail_lock_flags_for_guest(client, db):
    seed_catalog(db)
    r = client.get("/api/v1/series/ceo-bride")
    assert r.status_code == 200
    eps = r.json()["episodes"]
    assert [e["locked"] for e in eps] == [False, False, True]
    assert [e["is_free"] for e in eps] == [True, True, False]


def test_series_404(client):
    assert client.get("/api/v1/series/nope").status_code == 404


def test_search(client, db):
    seed_catalog(db)
    assert client.get("/api/v1/search", params={"q": "ceo"}).json()[0]["slug"] == "ceo-bride"
    assert client.get("/api/v1/search", params={"q": "zzz"}).json() == []


def test_genre_listing(client, db):
    seed_catalog(db)
    r = client.get("/api/v1/genres/romance/series")
    assert r.json()["series"][0]["slug"] == "ceo-bride"
