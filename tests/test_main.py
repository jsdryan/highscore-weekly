import datetime
import json

import pytest

from highscore.http_util import FetchError
from highscore.main import run
from highscore.models import Title
from highscore.omdb import Ratings


def make_title(tmdb_id, media_type="movie", name="沙丘"):
    return Title(media_type=media_type, tmdb_id=tmdb_id, name=name,
                 original_name="Dune", overview="", poster_url=None,
                 date="2026-06-01")


class FakeTmdb:
    def __init__(self, movies, shows):
        self.movies, self.shows = movies, shows

    def discover_movies(self, date_from, date_to, limit=150):
        return self.movies

    def discover_tv(self, date_from, date_to, limit=150):
        return self.shows

    def imdb_id(self, media_type, tmdb_id):
        if tmdb_id == 999:
            return None            # 無 IMDb ID → 略過
        return f"tt{tmdb_id:07d}"


RATINGS = {
    "tt0000001": Ratings(8.3, 120000, 93),   # 電影達標
    "tt0000002": Ratings(6.0, 50000, 95),    # IMDb 太低
    "tt0000003": Ratings(8.6, 45000, None),  # 影集缺 RT → 達標
}


def fake_fetch(imdb_id, api_key=""):
    if imdb_id == "tt0000004":
        raise FetchError("HTTP 500")
    return RATINGS[imdb_id]


def test_run_end_to_end(tmp_path, monkeypatch):
    monkeypatch.setenv("TMDB_API_KEY", "x")
    monkeypatch.setenv("OMDB_API_KEY", "y")
    movies = [make_title(1), make_title(2, name="爛片"), make_title(999),
              make_title(4, name="查掛的片")]
    shows = [make_title(3, media_type="tv", name="熊家餐館")]
    run(today=datetime.date(2026, 7, 17), root=tmp_path,
        tmdb_client=FakeTmdb(movies, shows), fetch_ratings_fn=fake_fetch)

    index = (tmp_path / "index.html").read_text(encoding="utf-8")
    assert "沙丘" in index                  # 達標入選
    assert "熊家餐館" in index              # 影集 fallback 入選
    assert "爛片" not in index.replace("查掛的片", "")  # 未達標不入選
    assert "查掛的片" in index and "HTTP 500" in index  # 失敗清單
    assert "🆕" in index                    # 首次入選標記

    assert (tmp_path / "reports" / "2026-07-17.html").exists()
    state = json.loads((tmp_path / "state.json").read_text(encoding="utf-8"))
    assert state["movie:1"]["first_listed"] == "2026-07-17"
    assert state["tv:3"]["first_listed"] == "2026-07-17"


def test_second_run_not_new(tmp_path, monkeypatch):
    monkeypatch.setenv("TMDB_API_KEY", "x")
    monkeypatch.setenv("OMDB_API_KEY", "y")
    client = FakeTmdb([make_title(1)], [])
    run(today=datetime.date(2026, 7, 17), root=tmp_path,
        tmdb_client=client, fetch_ratings_fn=fake_fetch)
    run(today=datetime.date(2026, 7, 24), root=tmp_path,
        tmdb_client=client, fetch_ratings_fn=fake_fetch)
    index = (tmp_path / "index.html").read_text(encoding="utf-8")
    assert "🆕" not in index
    # 歷期連結含上一期
    assert "reports/2026-07-17.html" in index


def test_mass_failures_abort_without_writing_report(tmp_path, monkeypatch):
    """額度耗盡等大範圍故障時要中止，不能用近空報告覆蓋上一期好報告。"""
    monkeypatch.setenv("TMDB_API_KEY", "x")
    monkeypatch.setenv("OMDB_API_KEY", "y")

    def always_fail(imdb_id, api_key=""):
        raise FetchError("HTTP 401")

    client = FakeTmdb([make_title(1), make_title(2), make_title(3)], [])
    with pytest.raises(SystemExit):
        run(today=datetime.date(2026, 7, 17), root=tmp_path,
            tmdb_client=client, fetch_ratings_fn=always_fail)
    assert not (tmp_path / "index.html").exists()
    assert not (tmp_path / "state.json").exists()
