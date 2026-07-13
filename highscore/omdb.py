"""OMDb API：一次拿到 IMDb 分數/票數與爛番茄分數。"""
from dataclasses import dataclass

from .http_util import get_json

OMDB_URL = "https://www.omdbapi.com/"


@dataclass
class Ratings:
    imdb_score: float | None
    imdb_votes: int | None
    rt_score: int | None


def parse_ratings(data: dict) -> Ratings:
    if data.get("Response") != "True":
        return Ratings(None, None, None)
    rt_score = None
    for r in data.get("Ratings", []):
        value = r.get("Value", "")
        if r.get("Source") == "Rotten Tomatoes" and value.endswith("%"):
            try:
                rt_score = int(value[:-1])
            except ValueError:
                pass
    return Ratings(_to_float(data.get("imdbRating")), _to_votes(data.get("imdbVotes")), rt_score)


def _to_float(value):
    if not value or value == "N/A":
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _to_votes(value):
    if not value or value == "N/A":
        return None
    try:
        return int(value.replace(",", ""))
    except ValueError:
        return None


def fetch_ratings(imdb_id: str, api_key: str) -> Ratings:
    return parse_ratings(get_json(OMDB_URL, {"apikey": api_key, "i": imdb_id}))
