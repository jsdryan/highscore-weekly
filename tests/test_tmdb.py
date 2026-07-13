from highscore.tmdb import TmdbClient


class FakeApi:
    """以 (path, 關鍵參數) 對照表回放 TMDB 回應。"""

    def __init__(self, routes):
        self.routes = routes

    def __call__(self, url, params):
        path = url.replace("https://api.themoviedb.org/3", "")
        if path.startswith("/discover"):
            key = (path, params.get("page", 1))
        else:
            key = (path,)
        return self.routes[key]


GENRES_MOVIE = {("/genre/movie/list",): {"genres": [{"id": 878, "name": "科幻"}]}}
GENRES_TV = {("/genre/tv/list",): {"genres": [{"id": 18, "name": "劇情"}]}}


def movie_result(id_, title="沙丘", date="2026-06-01"):
    return {"id": id_, "title": title, "original_title": "Dune", "overview": "簡介",
            "poster_path": "/p.jpg", "release_date": date, "genre_ids": [878]}


def test_discover_movies_paginates_and_maps():
    routes = dict(GENRES_MOVIE)
    routes[("/discover/movie", 1)] = {
        "page": 1, "total_pages": 2, "results": [movie_result(1), movie_result(2)]}
    routes[("/discover/movie", 2)] = {
        "page": 2, "total_pages": 2, "results": [movie_result(3)]}
    client = TmdbClient("k", get_json_fn=FakeApi(routes))
    titles = client.discover_movies("2026-05-01", "2026-07-01")
    assert [t.tmdb_id for t in titles] == [1, 2, 3]
    t = titles[0]
    assert t.media_type == "movie" and t.name == "沙丘" and t.genres == ["科幻"]
    assert t.poster_url == "https://image.tmdb.org/t/p/w342/p.jpg"


def test_discover_movies_respects_limit():
    routes = dict(GENRES_MOVIE)
    routes[("/discover/movie", 1)] = {
        "page": 1, "total_pages": 1,
        "results": [movie_result(i) for i in range(1, 6)]}
    client = TmdbClient("k", get_json_fn=FakeApi(routes))
    assert len(client.discover_movies("a", "b", limit=3)) == 3


def tv_result(id_):
    return {"id": id_, "name": "熊家餐館", "original_name": "The Bear",
            "overview": "簡介", "poster_path": "/t.jpg", "genre_ids": [18]}


def tv_detail(first_air, seasons):
    return {"name": "熊家餐館", "original_name": "The Bear", "overview": "簡介",
            "poster_path": "/t.jpg", "first_air_date": first_air,
            "genres": [{"id": 18, "name": "劇情"}],
            "seasons": [{"season_number": n, "air_date": d} for n, d in seasons]}


def test_tv_new_show_in_window():
    routes = dict(GENRES_TV)
    routes[("/discover/tv", 1)] = {"page": 1, "total_pages": 1, "results": [tv_result(10)]}
    routes[("/tv/10",)] = tv_detail("2026-06-15", [(1, "2026-06-15")])
    client = TmdbClient("k", get_json_fn=FakeApi(routes))
    shows = client.discover_tv("2026-05-10", "2026-07-09")
    assert len(shows) == 1
    assert shows[0].season_number == 1 and shows[0].date == "2026-06-15"


def test_tv_returning_season_in_window():
    routes = dict(GENRES_TV)
    routes[("/discover/tv", 1)] = {"page": 1, "total_pages": 1, "results": [tv_result(11)]}
    routes[("/tv/11",)] = tv_detail(
        "2022-06-23", [(1, "2022-06-23"), (2, "2023-06-22"), (3, "2026-06-25")])
    client = TmdbClient("k", get_json_fn=FakeApi(routes))
    shows = client.discover_tv("2026-05-10", "2026-07-09")
    assert len(shows) == 1
    assert shows[0].season_number == 3 and shows[0].date == "2026-06-25"


def test_tv_mid_season_show_skipped():
    """窗口內只是播到一半、沒有新一季開播的劇要略過。"""
    routes = dict(GENRES_TV)
    routes[("/discover/tv", 1)] = {"page": 1, "total_pages": 1, "results": [tv_result(12)]}
    routes[("/tv/12",)] = tv_detail("2024-01-01", [(1, "2024-01-01"), (2, "2026-04-01")])
    client = TmdbClient("k", get_json_fn=FakeApi(routes))
    assert client.discover_tv("2026-05-10", "2026-07-09") == []


def test_paged_respects_page_cap(monkeypatch):
    """TMDB page 參數上限 500，total_pages 可能更大；超過上限要停，不能打出 4xx。"""
    from highscore import tmdb as tmdb_mod
    monkeypatch.setattr(tmdb_mod, "MAX_PAGES", 2)
    routes = dict(GENRES_MOVIE)
    routes[("/discover/movie", 1)] = {
        "page": 1, "total_pages": 999, "results": [movie_result(1)]}
    routes[("/discover/movie", 2)] = {
        "page": 2, "total_pages": 999, "results": [movie_result(2)]}
    # 第 3 頁不存在於 routes：若未在上限停下，FakeApi 會 KeyError
    client = TmdbClient("k", get_json_fn=FakeApi(routes))
    assert [t.tmdb_id for t in client.discover_movies("a", "b")] == [1, 2]


def test_imdb_id():
    routes = {("/movie/1/external_ids",): {"imdb_id": "tt0001"},
              ("/tv/2/external_ids",): {"imdb_id": None}}
    client = TmdbClient("k", get_json_fn=FakeApi(routes))
    assert client.imdb_id("movie", 1) == "tt0001"
    assert client.imdb_id("tv", 2) is None
