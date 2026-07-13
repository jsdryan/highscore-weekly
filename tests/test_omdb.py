from highscore.omdb import Ratings, parse_ratings


def test_full_response():
    data = {
        "Response": "True",
        "imdbRating": "8.1",
        "imdbVotes": "12,345",
        "Ratings": [
            {"Source": "Internet Movie Database", "Value": "8.1/10"},
            {"Source": "Rotten Tomatoes", "Value": "93%"},
            {"Source": "Metacritic", "Value": "77/100"},
        ],
    }
    assert parse_ratings(data) == Ratings(8.1, 12345, 93)


def test_series_without_rt():
    data = {
        "Response": "True",
        "imdbRating": "8.6",
        "imdbVotes": "45,678",
        "Ratings": [{"Source": "Internet Movie Database", "Value": "8.6/10"}],
    }
    assert parse_ratings(data) == Ratings(8.6, 45678, None)


def test_na_fields_are_none_not_zero():
    data = {"Response": "True", "imdbRating": "N/A", "imdbVotes": "N/A", "Ratings": []}
    assert parse_ratings(data) == Ratings(None, None, None)


def test_error_response():
    assert parse_ratings({"Response": "False", "Error": "Incorrect IMDb ID."}) == Ratings(None, None, None)


def test_missing_ratings_key():
    data = {"Response": "True", "imdbRating": "7.9", "imdbVotes": "800"}
    assert parse_ratings(data) == Ratings(7.9, 800, None)
