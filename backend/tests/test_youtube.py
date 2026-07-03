from app.ingest_youtube import extract_youtube_id
from tests.test_catalog import seed_catalog


def test_extract_youtube_id_variants():
    for raw in [
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "https://youtu.be/dQw4w9WgXcQ",
        "https://www.youtube.com/shorts/dQw4w9WgXcQ",
        "https://www.youtube.com/embed/dQw4w9WgXcQ?rel=0",
        "dQw4w9WgXcQ",
    ]:
        assert extract_youtube_id(raw) == "dQw4w9WgXcQ", raw
    assert extract_youtube_id("https://example.com/notyoutube") is None


def test_playback_returns_youtube_type(client, db):
    s = seed_catalog(db)
    ep = s.episodes[0]
    ep.youtube_id = "dQw4w9WgXcQ"
    ep.hls_path = ""
    db.commit()
    body = client.get(f"/api/v1/episodes/{ep.id}/playback").json()
    assert body["type"] == "youtube" and body["youtube_id"] == "dQw4w9WgXcQ"


def test_playback_returns_mp4_type_for_direct_url(client, db):
    s = seed_catalog(db)
    ep = s.episodes[0]
    ep.hls_path = "https://ik.imagekit.io/demo/video.mp4"
    db.commit()
    body = client.get(f"/api/v1/episodes/{ep.id}/playback").json()
    assert body["type"] == "mp4" and body["url"].endswith("video.mp4")


def test_locked_youtube_episode_still_paywalled(client, db):
    s = seed_catalog(db)
    ep = s.episodes[2]  # ep 3 > free_episode_count=2
    ep.youtube_id = "dQw4w9WgXcQ"
    db.commit()
    r = client.get(f"/api/v1/episodes/{ep.id}/playback")
    assert r.status_code == 403 and r.json()["error"]["code"] == "subscription_required"
