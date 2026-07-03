from app.ingest import build_parser, parse_cast, resolve_free_episodes


def test_parser_movie_flags():
    args = build_parser().parse_args(
        ["film.mp4", "--series-slug", "daal", "--content-type", "movie",
         "--release-year", "2025", "--maturity-rating", "U/A 13+",
         "--director", "Arjun Mehta", "--cast", "Riya Sen:Asha, Vik Das",
         "--stills", "4"])
    assert args.content_type == "movie" and args.release_year == 2025
    assert args.stills == 4 and args.episode_number == 1
    assert args.free_episodes is None  # resolved later: movie->0, series->3


def test_parse_cast():
    assert parse_cast("Riya Sen:Asha, Vik Das") == [("Riya Sen", "Asha"), ("Vik Das", "")]
    assert parse_cast("") == []


def test_resolve_free_episodes():
    assert resolve_free_episodes(None, "movie") == 0
    assert resolve_free_episodes(None, "series") == 3
    assert resolve_free_episodes(1, "movie") == 1
