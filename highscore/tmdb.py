"""TMDB API：撈候選片單（繁中詮釋資料）與 IMDb ID。"""
from .http_util import get_json
from .models import Title

BASE = "https://api.themoviedb.org/3"
IMG = "https://image.tmdb.org/t/p/w342"
MAX_PAGES = 500  # TMDB page 參數上限；total_pages 可能超過它


class TmdbClient:
    def __init__(self, api_key, get_json_fn=get_json):
        self.api_key = api_key
        self._fetch = get_json_fn
        self._genre_cache = {}

    def _get(self, path, **params):
        params["api_key"] = self.api_key
        params.setdefault("language", "zh-TW")
        return self._fetch(f"{BASE}{path}", params)

    def _genres(self, media_type):
        if media_type not in self._genre_cache:
            data = self._get(f"/genre/{media_type}/list")
            self._genre_cache[media_type] = {
                g["id"]: g["name"] for g in data.get("genres", [])}
        return self._genre_cache[media_type]

    def imdb_id(self, media_type, tmdb_id):
        return self._get(f"/{media_type}/{tmdb_id}/external_ids").get("imdb_id") or None

    def _paged(self, path, **params):
        """惰性走訪 discover 分頁；呼叫端達到 limit 即中斷。"""
        page = 1
        while True:
            data = self._get(path, page=page, **params)
            yield from data.get("results", [])
            if page >= min(data.get("total_pages", 1), MAX_PAGES):
                return
            page += 1

    def discover_movies(self, date_from, date_to, limit=150):
        genres = self._genres("movie")
        titles = []
        for r in self._paged(
            "/discover/movie",
            sort_by="popularity.desc",
            **{"primary_release_date.gte": date_from,
               "primary_release_date.lte": date_to},
        ):
            titles.append(Title(
                media_type="movie",
                tmdb_id=r["id"],
                name=r.get("title") or r.get("original_title", ""),
                original_name=r.get("original_title", ""),
                overview=r.get("overview", ""),
                poster_url=IMG + r["poster_path"] if r.get("poster_path") else None,
                date=r.get("release_date", ""),
                genres=[genres[g] for g in r.get("genre_ids", []) if g in genres],
            ))
            if len(titles) >= limit:
                break
        return titles

    def discover_tv(self, date_from, date_to, limit=150):
        genres = self._genres("tv")
        shows, seen = [], set()
        # air_date 窗口會撈到「窗口內有任何一集播出」的劇，
        # 再逐劇看詳情，只留下新劇或新一季開播者。
        for r in self._paged(
            "/discover/tv",
            sort_by="popularity.desc",
            **{"air_date.gte": date_from, "air_date.lte": date_to},
        ):
            if r["id"] in seen:
                continue
            seen.add(r["id"])
            t = self._classify_tv(r["id"], date_from, date_to, genres)
            if t:
                shows.append(t)
            if len(shows) >= limit:
                break
        return shows

    def _classify_tv(self, tmdb_id, date_from, date_to, genres):
        d = self._get(f"/tv/{tmdb_id}")
        first_air = d.get("first_air_date") or ""
        season_number = season_date = None
        if date_from <= first_air <= date_to:
            season_number, season_date = 1, first_air
        else:
            for s in d.get("seasons", []):
                air = s.get("air_date") or ""
                if s.get("season_number", 0) >= 2 and date_from <= air <= date_to:
                    if season_date is None or air > season_date:
                        season_number, season_date = s["season_number"], air
        if season_number is None:
            return None
        genre_names = [g["name"] for g in d.get("genres", [])]
        return Title(
            media_type="tv",
            tmdb_id=tmdb_id,
            name=d.get("name") or d.get("original_name", ""),
            original_name=d.get("original_name", ""),
            overview=d.get("overview", ""),
            poster_url=IMG + d["poster_path"] if d.get("poster_path") else None,
            date=season_date,
            genres=genre_names,
            season_number=season_number,
        )
