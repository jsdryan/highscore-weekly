"""主流程：撈候選 → 查分數 → 篩選 → 產報告。"""
import datetime
import os
from pathlib import Path

from . import filtering, omdb, report
from . import state as state_mod
from .http_util import FetchError
from .tmdb import TmdbClient

WINDOW_DAYS = 60


def run(today=None, root=Path("."), tmdb_client=None, fetch_ratings_fn=None):
    today = today or datetime.date.today()
    date_to = today.isoformat()
    date_from = (today - datetime.timedelta(days=WINDOW_DAYS)).isoformat()

    client = tmdb_client or TmdbClient(os.environ["TMDB_API_KEY"])
    fetch = fetch_ratings_fn or (
        lambda imdb_id: omdb.fetch_ratings(imdb_id, os.environ["OMDB_API_KEY"]))

    candidates = (client.discover_movies(date_from, date_to)
                  + client.discover_tv(date_from, date_to))

    qualified, failures = [], []
    for t in candidates:
        try:
            t.imdb_id = client.imdb_id(t.media_type, t.tmdb_id)
            if not t.imdb_id:
                continue
            r = fetch(t.imdb_id)
            t.imdb_score, t.imdb_votes, t.rt_score = (
                r.imdb_score, r.imdb_votes, r.rt_score)
            if filtering.qualifies(t):
                qualified.append(t)
        except FetchError as exc:
            failures.append(f"{t.name}（{t.media_type}:{t.tmdb_id}）：{exc}")

    st_path = root / "state.json"
    st = state_mod.load_state(st_path)
    state_mod.mark_new(qualified, st, date_to)

    movies = sorted((t for t in qualified if t.media_type == "movie"),
                    key=lambda t: (t.rt_score or 0, t.imdb_score or 0), reverse=True)
    shows = sorted((t for t in qualified if t.media_type == "tv"),
                   key=lambda t: (t.imdb_score or 0, t.rt_score or 0), reverse=True)

    reports_dir = root / "reports"
    reports_dir.mkdir(exist_ok=True)
    archives = sorted({p.stem for p in reports_dir.glob("*.html")} | {date_to},
                      reverse=True)
    (root / "index.html").write_text(
        report.render(movies, shows, date_to, failures, archives=archives),
        encoding="utf-8")
    (reports_dir / f"{date_to}.html").write_text(
        report.render(movies, shows, date_to, failures, archives=None),
        encoding="utf-8")
    state_mod.save_state(st, st_path)
    print(f"電影 {len(movies)} 部、影集 {len(shows)} 部入選；查詢失敗 {len(failures)} 筆")


if __name__ == "__main__":
    run()
