from highscore.filtering import qualifies
from highscore.models import Title


def make(media_type="movie", imdb=8.0, votes=1000, rt=90):
    return Title(
        media_type=media_type, tmdb_id=1, name="測試片", original_name="Test",
        overview="", poster_url=None, date="2026-06-01",
        imdb_score=imdb, imdb_votes=votes, rt_score=rt,
    )


def test_movie_double_high_qualifies():
    assert qualifies(make()) is True


def test_movie_rt_below_85_fails():
    assert qualifies(make(rt=84)) is False


def test_movie_imdb_below_7_5_fails():
    assert qualifies(make(imdb=7.4)) is False


def test_movie_votes_below_500_fails():
    assert qualifies(make(votes=499)) is False


def test_movie_missing_rt_fails():
    assert qualifies(make(rt=None)) is False


def test_movie_missing_imdb_fails():
    assert qualifies(make(imdb=None)) is False


def test_tv_missing_rt_falls_back_to_imdb_only():
    assert qualifies(make(media_type="tv", rt=None)) is True


def test_tv_with_low_rt_fails():
    assert qualifies(make(media_type="tv", rt=60)) is False


def test_tv_with_high_rt_qualifies():
    assert qualifies(make(media_type="tv", rt=95)) is True


def test_tv_low_imdb_fails_even_without_rt():
    assert qualifies(make(media_type="tv", imdb=7.0, rt=None)) is False


def test_boundary_values_qualify():
    assert qualifies(make(imdb=7.5, votes=500, rt=85)) is True
