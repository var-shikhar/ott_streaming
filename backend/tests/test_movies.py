import uuid

from app import models


def seed_mixed(db):
    """One published series (3 ready eps) + one published movie + one draft movie."""
    g = models.Genre(slug="drama", name="Drama")
    db.add(g)
    s = models.Series(slug="ceo-bride", title="CEO's Secret Bride", free_episode_count=2,
                      view_count=100, is_featured=True, genres=[g])
    m = models.Series(slug="daal", title="Daal", content_type="movie", free_episode_count=0,
                      release_year=2025, maturity_rating="U/A 13+", view_count=500,
                      is_featured=True, genres=[g])
    draft = models.Series(slug="unreleased", title="Unreleased", content_type="movie",
                          status="draft")
    db.add_all([s, m, draft])
    db.flush()
    for n in (1, 2, 3):
        db.add(models.Episode(series_id=s.id, episode_number=n, status="ready",
                              title=f"Ep {n}", duration_seconds=60,
                              hls_path=f"{uuid.uuid4()}/master.m3u8"))
    db.add(models.Episode(series_id=m.id, episode_number=1, status="ready", title="Daal",
                          duration_seconds=1320, hls_path=f"{uuid.uuid4()}/master.m3u8"))
    db.commit()
    return s, m


def test_series_out_carries_movie_fields(client, db):
    seed_mixed(db)
    body = client.get("/api/v1/search", params={"q": "daal"}).json()
    assert body[0]["content_type"] == "movie"
    assert body[0]["release_year"] == 2025
    assert body[0]["maturity_rating"] == "U/A 13+"
    assert body[0]["duration_seconds"] == 1320


def test_reels_home_excludes_movies(client, db):
    seed_mixed(db)
    body = client.get("/api/v1/home").json()
    for key in ("featured", "trending", "new_releases"):
        assert all(item["content_type"] == "series" for item in body[key]), key
    for rail in body["genre_rails"]:
        assert all(item["content_type"] == "series" for item in rail["series"])


def test_series_list_excludes_movies(client, db):
    seed_mixed(db)
    slugs = [s["slug"] for s in client.get("/api/v1/series").json()]
    assert "daal" not in slugs and "ceo-bride" in slugs


def test_search_content_type_filter(client, db):
    seed_mixed(db)
    both = client.get("/api/v1/search", params={"q": "d"}).json()
    assert {b["content_type"] for b in both} == {"series", "movie"}
    only_movies = client.get("/api/v1/search", params={"q": "d", "content_type": "movie"}).json()
    assert only_movies and all(b["content_type"] == "movie" for b in only_movies)


def test_genre_series_defaults_to_series_only(client, db):
    seed_mixed(db)
    body = client.get("/api/v1/genres/drama/series").json()
    assert [s["slug"] for s in body["series"]] == ["ceo-bride"]
    movies = client.get("/api/v1/genres/drama/series", params={"content_type": "movie"}).json()
    assert [s["slug"] for s in movies["series"]] == ["daal"]


def test_movies_home_is_movies_only(client, db):
    seed_mixed(db)
    body = client.get("/api/v1/movies/home").json()
    assert [m["slug"] for m in body["featured"]] == ["daal"]
    assert all(m["content_type"] == "movie" for m in body["trending"])
    assert "unreleased" not in [m["slug"] for m in body["new_releases"]]  # draft excluded
    assert body["continue_watching"] == []


def test_movies_list(client, db):
    seed_mixed(db)
    assert [m["slug"] for m in client.get("/api/v1/movies").json()] == ["daal"]


def test_movie_detail_payload(client, db):
    _, m = seed_mixed(db)
    db.add_all([
        models.Credit(series_id=m.id, person_name="Arjun Mehta", role="director",
                      display_order=0),
        models.Credit(series_id=m.id, person_name="Riya Sen", role="cast",
                      character_name="Asha", display_order=1),
        models.Still(series_id=m.id, image_url="https://ik.io/b.jpg", display_order=0),
        models.Still(series_id=m.id, image_url="https://ik.io/a.jpg", display_order=1),
    ])
    db.commit()
    body = client.get("/api/v1/movies/daal").json()
    assert body["slug"] == "daal"
    assert body["episode"]["duration_seconds"] == 1320
    # premium movie (free_episode_count=0), guest -> locked
    assert body["episode"]["is_free"] is False and body["episode"]["locked"] is True
    assert [c["role"] for c in body["credits"]] == ["director", "cast"]
    assert body["credits"][1]["character_name"] == "Asha"
    assert body["stills"] == ["https://ik.io/b.jpg", "https://ik.io/a.jpg"]
    assert isinstance(body["related"], list)


def test_movie_detail_404_for_series_slug_and_unknown(client, db):
    seed_mixed(db)
    assert client.get("/api/v1/movies/ceo-bride").status_code == 404
    assert client.get("/api/v1/movies/nope").status_code == 404


def test_free_movie_unlocked_for_guest(client, db):
    seed_mixed(db)
    free = models.Series(slug="free-film", title="Free Film", content_type="movie",
                         free_episode_count=1)
    db.add(free)
    db.flush()
    db.add(models.Episode(series_id=free.id, episode_number=1, status="ready",
                          duration_seconds=600, hls_path=f"{uuid.uuid4()}/master.m3u8"))
    db.commit()
    body = client.get("/api/v1/movies/free-film").json()
    assert body["episode"]["is_free"] is True and body["episode"]["locked"] is False


def test_related_movies_share_a_genre(client, db):
    _, m = seed_mixed(db)
    g2 = models.Genre(slug="comedy", name="Comedy")
    db.add(g2)
    drama_movie = models.Series(slug="sister-film", title="Sister Film", content_type="movie",
                                genres=[m.genres[0]])
    comedy_movie = models.Series(slug="other-film", title="Other Film", content_type="movie",
                                 genres=[g2])
    db.add_all([drama_movie, comedy_movie])
    db.flush()
    for mv in (drama_movie, comedy_movie):
        db.add(models.Episode(series_id=mv.id, episode_number=1, status="ready",
                              duration_seconds=300, hls_path=f"{uuid.uuid4()}/master.m3u8"))
    db.commit()
    related = client.get("/api/v1/movies/daal").json()["related"]
    slugs = [r["slug"] for r in related]
    assert "sister-film" in slugs and "other-film" not in slugs and "daal" not in slugs


def test_premium_movie_playback_403_for_guest(client, db):
    _, m = seed_mixed(db)
    ep_id = str(m.episodes[0].id)
    r = client.get(f"/api/v1/episodes/{ep_id}/playback")
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "subscription_required"
