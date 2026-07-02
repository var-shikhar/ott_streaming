import uuid

from app import models


def test_series_episode_roundtrip(db):
    s = models.Series(slug="test-show", title="Test Show", synopsis="x", language="en",
                      poster_url="p", banner_url="b", free_episode_count=2)
    db.add(s)
    db.flush()
    e = models.Episode(series_id=s.id, episode_number=1, title="Ep 1", duration_seconds=60,
                       hls_path="x/master.m3u8", status="ready")
    db.add(e)
    db.commit()
    assert isinstance(s.id, uuid.UUID)
    assert db.query(models.Episode).one().series.slug == "test-show"
