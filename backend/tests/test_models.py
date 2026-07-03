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


def test_movie_with_credits_and_stills(db):
    m = models.Series(slug="daal", title="Daal", content_type="movie",
                      release_year=2025, maturity_rating="U/A 13+", free_episode_count=0)
    db.add(m)
    db.flush()
    db.add_all([
        models.Credit(series_id=m.id, person_name="Riya Sen", role="cast",
                      character_name="Asha", display_order=1),
        models.Credit(series_id=m.id, person_name="Arjun Mehta", role="director",
                      display_order=0),
        models.Still(series_id=m.id, image_url="https://ik.io/a.jpg", display_order=1),
        models.Still(series_id=m.id, image_url="https://ik.io/b.jpg", display_order=0),
    ])
    db.commit()
    db.expire_all()
    row = db.query(models.Series).filter_by(slug="daal").one()
    assert row.content_type == "movie" and row.release_year == 2025
    assert [c.role for c in row.credits] == ["director", "cast"]  # display_order
    assert [s.image_url for s in row.stills] == ["https://ik.io/b.jpg", "https://ik.io/a.jpg"]


def test_series_defaults_to_series_content_type(db):
    s = models.Series(slug="plain", title="Plain")
    db.add(s)
    db.commit()
    assert s.content_type == "series" and s.maturity_rating == "" and s.release_year is None
