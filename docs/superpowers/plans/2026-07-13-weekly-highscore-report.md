# 高分片週報 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 每週五 09:00（台北）自動產出「爛番茄＋IMDb 雙高分新片」HTML 週報，發布到 GitHub Pages。

**Architecture:** Python 套件 `highscore/`（TMDB 撈候選 → OMDb 查雙分數 → 門檻篩選 → 產 HTML），由 GitHub Actions cron 執行並把報告 commit 回 main branch，GitHub Pages 直接發布。純標準函式庫＋requests，無資料庫，狀態存 `state.json`。

**Tech Stack:** Python 3.11、requests、pytest、GitHub Actions、GitHub Pages

## Global Constraints

- 篩選門檻：電影 RT ≥ 85 且 IMDb ≥ 7.5 且票數 ≥ 500；影集 IMDb ≥ 7.5 且票數 ≥ 500，RT 有資料時另要求 ≥ 85，無資料標「RT 無資料」
- 候選上限：電影 150、影集 150（新劇＋返場合計）
- 滾動窗口：60 天
- TMDB 一律帶 `language=zh-TW`
- OMDb 欄位值 `"N/A"` 一律視為無資料（None），不得當 0
- 報告與程式註解用繁體中文（台灣）
- Secrets 名稱：`TMDB_API_KEY`、`OMDB_API_KEY`（環境變數同名）
- repo：`jsdryan/highscore-weekly`（public）；未經用戶確認不得 push（本案用戶已授權建 repo 與 push）

## File Structure

```
highscore/
  __init__.py      # 空
  http_util.py     # get_json：帶重試的 HTTP GET
  models.py        # Title dataclass（跨模組資料介面）
  omdb.py          # OMDb 回應解析與查詢
  filtering.py     # 雙高分門檻純邏輯
  state.py         # state.json 載入/儲存/標記 🆕
  report.py        # HTML 產生
  tmdb.py          # TMDB 客戶端（discover/分類/external_ids）
  main.py          # 主流程串接
tests/
  test_http_util.py
  test_omdb.py
  test_filtering.py
  test_state.py
  test_report.py
  test_tmdb.py
  test_main.py
conftest.py        # 空，讓 pytest 把 repo root 加入 sys.path
requirements.txt
.github/workflows/weekly-report.yml
.nojekyll
README.md
```

---

### Task 1: 專案骨架 + http_util（帶重試的 GET）

**Files:**
- Create: `requirements.txt`, `conftest.py`, `highscore/__init__.py`, `highscore/http_util.py`
- Test: `tests/test_http_util.py`

**Interfaces:**
- Produces: `http_util.get_json(url, params, retries=3, backoff=2.0, timeout=30, session=None) -> dict`；失敗重試耗盡時 raise `http_util.FetchError`

- [ ] **Step 1: 建骨架檔案**

`requirements.txt`：
```
requests>=2.31
pytest>=8.0
```

`conftest.py`：空檔案。`highscore/__init__.py`：空檔案。

執行：`pip3 install -r requirements.txt`

- [ ] **Step 2: 寫失敗測試**

`tests/test_http_util.py`：
```python
import pytest
from highscore import http_util
from highscore.http_util import FetchError, get_json


class FakeResponse:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self._payload = payload or {}

    def json(self):
        return self._payload


class FakeSession:
    """依序回放預先排好的回應；'boom' 代表拋連線錯誤。"""

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = 0

    def get(self, url, params=None, timeout=None):
        self.calls += 1
        item = self.responses.pop(0)
        if item == "boom":
            import requests
            raise requests.ConnectionError("boom")
        return item


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    monkeypatch.setattr(http_util.time, "sleep", lambda s: None)


def test_success_first_try():
    sess = FakeSession([FakeResponse(200, {"ok": 1})])
    assert get_json("http://x", {}, session=sess) == {"ok": 1}
    assert sess.calls == 1


def test_retries_then_succeeds():
    sess = FakeSession(["boom", FakeResponse(500), FakeResponse(200, {"ok": 1})])
    assert get_json("http://x", {}, session=sess) == {"ok": 1}
    assert sess.calls == 3


def test_raises_after_retries_exhausted():
    sess = FakeSession(["boom", "boom", "boom"])
    with pytest.raises(FetchError):
        get_json("http://x", {}, session=sess)
    assert sess.calls == 3
```

- [ ] **Step 3: 跑測試確認失敗**

Run: `python3 -m pytest tests/test_http_util.py -v`
Expected: FAIL（`No module named 'highscore.http_util'` 或 import error）

- [ ] **Step 4: 實作**

`highscore/http_util.py`：
```python
"""帶重試的 HTTP GET，TMDB 與 OMDb 共用。"""
import time

import requests


class FetchError(Exception):
    """API 呼叫在重試耗盡後仍失敗。"""


def get_json(url, params, retries=3, backoff=2.0, timeout=30, session=None):
    sess = session or requests
    last_err = None
    for attempt in range(retries):
        try:
            resp = sess.get(url, params=params, timeout=timeout)
            if resp.status_code == 200:
                return resp.json()
            last_err = FetchError(f"HTTP {resp.status_code}: {url}")
        except requests.RequestException as exc:
            last_err = FetchError(f"{type(exc).__name__}: {exc}")
        if attempt < retries - 1:
            time.sleep(backoff * (2 ** attempt))
    raise last_err
```

- [ ] **Step 5: 跑測試確認通過**

Run: `python3 -m pytest tests/test_http_util.py -v`
Expected: 3 passed

- [ ] **Step 6: Commit**

```bash
git add requirements.txt conftest.py highscore/ tests/
git commit -m "feat: http_util 帶重試的 GET"
```

---

### Task 2: OMDb 回應解析與查詢

**Files:**
- Create: `highscore/omdb.py`
- Test: `tests/test_omdb.py`

**Interfaces:**
- Consumes: `http_util.get_json`
- Produces: `omdb.Ratings`（欄位 `imdb_score: float|None, imdb_votes: int|None, rt_score: int|None`）、`omdb.parse_ratings(data: dict) -> Ratings`、`omdb.fetch_ratings(imdb_id: str, api_key: str) -> Ratings`

- [ ] **Step 1: 寫失敗測試**

`tests/test_omdb.py`：
```python
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
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `python3 -m pytest tests/test_omdb.py -v`
Expected: FAIL（import error）

- [ ] **Step 3: 實作**

`highscore/omdb.py`：
```python
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
```

- [ ] **Step 4: 跑測試確認通過**

Run: `python3 -m pytest tests/test_omdb.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add highscore/omdb.py tests/test_omdb.py
git commit -m "feat: OMDb 回應解析（N/A 視為無資料）"
```

---

### Task 3: Title 資料模型 + 篩選邏輯

**Files:**
- Create: `highscore/models.py`, `highscore/filtering.py`
- Test: `tests/test_filtering.py`

**Interfaces:**
- Produces: `models.Title` dataclass（欄位見下方程式碼，跨模組共用）、`filtering.qualifies(t: Title) -> bool`、常數 `RT_MIN=85, IMDB_MIN=7.5, VOTES_MIN=500`

- [ ] **Step 1: 寫失敗測試**

`tests/test_filtering.py`：
```python
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
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `python3 -m pytest tests/test_filtering.py -v`
Expected: FAIL（import error）

- [ ] **Step 3: 實作**

`highscore/models.py`：
```python
"""跨模組共用的資料模型。"""
from dataclasses import dataclass, field


@dataclass
class Title:
    media_type: str                 # "movie" 或 "tv"
    tmdb_id: int
    name: str                       # 繁中片名（TMDB 無翻譯時為原文）
    original_name: str
    overview: str                   # 繁中簡介，可為空字串
    poster_url: str | None
    date: str                       # 上映日或本季開播日 YYYY-MM-DD
    genres: list[str] = field(default_factory=list)
    season_number: int | None = None  # tv：本次開播的季數
    imdb_id: str | None = None
    imdb_score: float | None = None
    imdb_votes: int | None = None
    rt_score: int | None = None
    is_new: bool = False            # 本週新入選（報告標 🆕）
```

`highscore/filtering.py`：
```python
"""雙高分門檻。電影兩邊都要；影集缺 RT 資料時退回 IMDb 單邊門檻。"""
from .models import Title

RT_MIN = 85
IMDB_MIN = 7.5
VOTES_MIN = 500


def qualifies(t: Title) -> bool:
    if t.imdb_score is None or t.imdb_votes is None:
        return False
    if t.imdb_score < IMDB_MIN or t.imdb_votes < VOTES_MIN:
        return False
    if t.media_type == "movie":
        return t.rt_score is not None and t.rt_score >= RT_MIN
    return t.rt_score is None or t.rt_score >= RT_MIN
```

- [ ] **Step 4: 跑測試確認通過**

Run: `python3 -m pytest tests/test_filtering.py -v`
Expected: 11 passed

- [ ] **Step 5: Commit**

```bash
git add highscore/models.py highscore/filtering.py tests/test_filtering.py
git commit -m "feat: Title 模型與雙高分篩選邏輯"
```

---

### Task 4: 狀態管理（🆕 標記）

**Files:**
- Create: `highscore/state.py`
- Test: `tests/test_state.py`

**Interfaces:**
- Consumes: `models.Title`
- Produces: `state.load_state(path: Path) -> dict`、`state.mark_new(titles: list[Title], state: dict, today: str) -> dict`（就地把首次入選的 Title.is_new 設 True 並寫入 state）、`state.save_state(state: dict, path: Path) -> None`

- [ ] **Step 1: 寫失敗測試**

`tests/test_state.py`：
```python
import json

from highscore.models import Title
from highscore.state import load_state, mark_new, save_state


def make(tmdb_id, media_type="movie"):
    return Title(media_type=media_type, tmdb_id=tmdb_id, name="片", original_name="T",
                 overview="", poster_url=None, date="2026-06-01")


def test_load_missing_file_returns_empty(tmp_path):
    assert load_state(tmp_path / "no.json") == {}


def test_first_listing_marks_new(tmp_path):
    t = make(101)
    st = mark_new([t], {}, "2026-07-17")
    assert t.is_new is True
    assert st["movie:101"] == {"first_listed": "2026-07-17"}


def test_second_listing_not_new():
    t = make(101)
    st = {"movie:101": {"first_listed": "2026-07-10"}}
    mark_new([t], st, "2026-07-17")
    assert t.is_new is False
    assert st["movie:101"]["first_listed"] == "2026-07-10"


def test_same_id_different_media_type_is_distinct():
    movie, show = make(101, "movie"), make(101, "tv")
    st = mark_new([movie, show], {}, "2026-07-17")
    assert set(st) == {"movie:101", "tv:101"}


def test_roundtrip(tmp_path):
    path = tmp_path / "state.json"
    save_state({"movie:1": {"first_listed": "2026-07-17"}}, path)
    assert load_state(path) == {"movie:1": {"first_listed": "2026-07-17"}}
    # 存檔須為 UTF-8 JSON、鍵排序，diff 才乾淨
    raw = path.read_text(encoding="utf-8")
    assert json.loads(raw) == {"movie:1": {"first_listed": "2026-07-17"}}
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `python3 -m pytest tests/test_state.py -v`
Expected: FAIL（import error）

- [ ] **Step 3: 實作**

`highscore/state.py`：
```python
"""state.json：記錄歷次入選片單，用來標記本週新入選（🆕）。"""
import json
from pathlib import Path

from .models import Title


def load_state(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _key(t: Title) -> str:
    return f"{t.media_type}:{t.tmdb_id}"


def mark_new(titles: list[Title], state: dict, today: str) -> dict:
    for t in titles:
        k = _key(t)
        if k not in state:
            t.is_new = True
            state[k] = {"first_listed": today}
    return state


def save_state(state: dict, path: Path) -> None:
    path.write_text(
        json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
```

- [ ] **Step 4: 跑測試確認通過**

Run: `python3 -m pytest tests/test_state.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add highscore/state.py tests/test_state.py
git commit -m "feat: state.json 管理與 🆕 標記"
```

---

### Task 5: HTML 報告產生

**Files:**
- Create: `highscore/report.py`
- Test: `tests/test_report.py`

**Interfaces:**
- Consumes: `models.Title`
- Produces: `report.render(movies: list[Title], shows: list[Title], run_date: str, failures: list[str], archives: list[str] | None = None) -> str`。`archives` 為歷期日期字串列表（新到舊），None 表示存檔版（不渲染歷期區塊）。

- [ ] **Step 1: 寫失敗測試**

`tests/test_report.py`：
```python
from highscore.models import Title
from highscore.report import render


def make(**kw):
    base = dict(
        media_type="movie", tmdb_id=1, name="沙丘", original_name="Dune",
        overview="沙漠星球的故事", poster_url="https://img/x.jpg", date="2026-06-01",
        genres=["科幻"], imdb_id="tt0001", imdb_score=8.3, imdb_votes=120000, rt_score=93,
    )
    base.update(kw)
    return Title(**base)


def test_contains_titles_and_scores():
    html = render([make()], [], "2026-07-17", [])
    assert "沙丘" in html and "Dune" in html
    assert "93%" in html and "8.3" in html
    assert "https://www.imdb.com/title/tt0001/" in html


def test_new_badge():
    html = render([make(is_new=True)], [], "2026-07-17", [])
    assert "🆕" in html
    html2 = render([make(is_new=False)], [], "2026-07-17", [])
    assert "🆕" not in html2


def test_tv_missing_rt_shows_no_data_badge():
    show = make(media_type="tv", rt_score=None, season_number=2, name="熊家餐館",
                original_name="The Bear")
    html = render([], [show], "2026-07-17", [])
    assert "RT 無資料" in html
    assert "第 2 季" in html


def test_failures_section():
    html = render([], [], "2026-07-17", ["某片（movie:99）：HTTP 500"])
    assert "查詢失敗" in html and "HTTP 500" in html
    assert "查詢失敗" not in render([], [], "2026-07-17", [])


def test_archives_only_when_given():
    html = render([make()], [], "2026-07-17", [], archives=["2026-07-17", "2026-07-10"])
    assert "reports/2026-07-10.html" in html
    assert "reports/" not in render([make()], [], "2026-07-17", [], archives=None)


def test_html_escaping():
    html = render([make(name="<script>alert(1)</script>")], [], "2026-07-17", [])
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html


def test_empty_sections_show_placeholder():
    html = render([], [], "2026-07-17", [])
    assert "本期沒有達標作品" in html
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `python3 -m pytest tests/test_report.py -v`
Expected: FAIL（import error）

- [ ] **Step 3: 實作**

`highscore/report.py`：
```python
"""產出單檔 HTML 週報（inline CSS，支援深淺色）。"""
import html as html_mod
from urllib.parse import quote

from .models import Title

_CSS = """
:root { color-scheme: light dark; --card: #fff; --fg: #1a1a1a; --muted: #666;
        --bg: #f4f4f5; --accent: #c0392b; }
@media (prefers-color-scheme: dark) {
  :root { --card: #1e1e22; --fg: #eee; --muted: #9a9aa2; --bg: #111114; }
}
* { box-sizing: border-box; margin: 0; }
body { font-family: -apple-system, "PingFang TC", "Noto Sans TC", sans-serif;
       background: var(--bg); color: var(--fg); padding: 24px; max-width: 1080px;
       margin: 0 auto; }
h1 { font-size: 1.5rem; margin-bottom: 4px; }
h2 { font-size: 1.2rem; margin: 28px 0 12px; }
.meta { color: var(--muted); font-size: .85rem; margin-bottom: 8px; }
.grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
        gap: 16px; }
.card { background: var(--card); border-radius: 12px; overflow: hidden;
        display: flex; box-shadow: 0 1px 4px rgba(0,0,0,.12); }
.card img { width: 110px; object-fit: cover; flex-shrink: 0; }
.noposter { width: 110px; background: var(--muted); flex-shrink: 0; }
.info { padding: 12px 14px; min-width: 0; }
.title { font-weight: 700; }
.orig { color: var(--muted); font-size: .8rem; }
.scores { margin: 6px 0; font-size: .95rem; }
.badge { font-size: .7rem; border: 1px solid var(--muted); color: var(--muted);
         border-radius: 4px; padding: 1px 5px; margin-left: 4px; }
.genres { color: var(--muted); font-size: .75rem; }
.overview { font-size: .8rem; color: var(--muted); margin-top: 6px;
            display: -webkit-box; -webkit-line-clamp: 3;
            -webkit-box-orient: vertical; overflow: hidden; }
.links a { font-size: .75rem; margin-right: 10px; color: var(--accent); }
.empty { color: var(--muted); padding: 16px 0; }
.failures { margin-top: 32px; font-size: .8rem; color: var(--muted); }
.archives { margin-top: 32px; font-size: .85rem; }
.archives a { margin-right: 12px; }
"""


def _esc(s):
    return html_mod.escape(s or "")


def _card(t: Title) -> str:
    poster = (
        f'<img src="{_esc(t.poster_url)}" alt="" loading="lazy">'
        if t.poster_url else '<div class="noposter"></div>'
    )
    new = " 🆕" if t.is_new else ""
    season = f'<span class="badge">第 {t.season_number} 季</span>' if (
        t.media_type == "tv" and t.season_number) else ""
    rt = f"🍅 {t.rt_score}%" if t.rt_score is not None else '🍅 <span class="badge">RT 無資料</span>'
    votes = f"（{t.imdb_votes:,} 票）" if t.imdb_votes else ""
    rt_url = f"https://www.rottentomatoes.com/search?search={quote(t.original_name)}"
    imdb_url = f"https://www.imdb.com/title/{t.imdb_id}/" if t.imdb_id else ""
    imdb_link = f'<a href="{imdb_url}">IMDb</a>' if imdb_url else ""
    genres = "・".join(_esc(g) for g in t.genres if g)
    return f"""<div class="card">{poster}<div class="info">
<div class="title">{_esc(t.name)}{new}{season}</div>
<div class="orig">{_esc(t.original_name)}　{_esc(t.date)}</div>
<div class="scores">{rt}　⭐ {t.imdb_score}{votes}</div>
<div class="genres">{genres}</div>
<div class="overview">{_esc(t.overview)}</div>
<div class="links">{imdb_link}<a href="{_esc(rt_url)}">Rotten Tomatoes</a></div>
</div></div>"""


def _section(heading: str, items: list[Title]) -> str:
    if not items:
        return f"<h2>{heading}</h2>\n<div class=\"empty\">本期沒有達標作品。</div>"
    cards = "\n".join(_card(t) for t in items)
    return f"<h2>{heading}（{len(items)}）</h2>\n<div class=\"grid\">\n{cards}\n</div>"


def render(movies, shows, run_date, failures, archives=None) -> str:
    parts = [
        "<!doctype html>",
        '<html lang="zh-Hant"><head><meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        f"<title>高分片週報 {_esc(run_date)}</title>",
        f"<style>{_CSS}</style></head><body>",
        f"<h1>高分片週報 <small>{_esc(run_date)}</small></h1>",
        '<div class="meta">門檻：🍅 爛番茄 ≥ 85% 且 ⭐ IMDb ≥ 7.5（≥ 500 票）；'
        "影集缺 RT 資料時以 IMDb 為準。🆕 = 本週新入選。</div>",
        _section("電影", movies),
        _section("影集", shows),
    ]
    if failures:
        items = "\n".join(f"<li>{_esc(f)}</li>" for f in failures)
        parts.append(f'<div class="failures"><h2>本次查詢失敗</h2><ul>{items}</ul></div>')
    if archives:
        links = "".join(
            f'<a href="reports/{_esc(d)}.html">{_esc(d)}</a>' for d in archives
        )
        parts.append(f'<div class="archives">歷期報告：{links}</div>')
    parts.append("</body></html>")
    return "\n".join(parts)
```

- [ ] **Step 4: 跑測試確認通過**

Run: `python3 -m pytest tests/test_report.py -v`
Expected: 7 passed

- [ ] **Step 5: Commit**

```bash
git add highscore/report.py tests/test_report.py
git commit -m "feat: HTML 週報產生"
```

---

### Task 6: TMDB 客戶端

**Files:**
- Create: `highscore/tmdb.py`
- Test: `tests/test_tmdb.py`

**Interfaces:**
- Consumes: `http_util.get_json`、`models.Title`
- Produces: `tmdb.TmdbClient(api_key, get_json_fn=get_json)`，方法：
  - `discover_movies(date_from: str, date_to: str, limit: int = 150) -> list[Title]`
  - `discover_tv(date_from: str, date_to: str, limit: int = 150) -> list[Title]`（含新劇與返場劇分類，非窗口內開播的略過）
  - `imdb_id(media_type: str, tmdb_id: int) -> str | None`

- [ ] **Step 1: 寫失敗測試**

`tests/test_tmdb.py`：
```python
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


def test_imdb_id():
    routes = {("/movie/1/external_ids",): {"imdb_id": "tt0001"},
              ("/tv/2/external_ids",): {"imdb_id": None}}
    client = TmdbClient("k", get_json_fn=FakeApi(routes))
    assert client.imdb_id("movie", 1) == "tt0001"
    assert client.imdb_id("tv", 2) is None
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `python3 -m pytest tests/test_tmdb.py -v`
Expected: FAIL（import error）

- [ ] **Step 3: 實作**

`highscore/tmdb.py`：
```python
"""TMDB API：撈候選片單（繁中詮釋資料）與 IMDb ID。"""
from .http_util import get_json
from .models import Title

BASE = "https://api.themoviedb.org/3"
IMG = "https://image.tmdb.org/t/p/w342"


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
            if page >= data.get("total_pages", 1):
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
        genre_names = [g["name"] for g in d.get("genres", [])] or [
            genres[g] for g in d.get("genre_ids", []) if g in genres]
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
```

- [ ] **Step 4: 跑測試確認通過**

Run: `python3 -m pytest tests/test_tmdb.py -v`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add highscore/tmdb.py tests/test_tmdb.py
git commit -m "feat: TMDB 候選撈取與新劇/返場分類"
```

---

### Task 7: 主流程 main.py

**Files:**
- Create: `highscore/main.py`
- Test: `tests/test_main.py`

**Interfaces:**
- Consumes: 前述全部模組
- Produces: `main.run(today: datetime.date | None = None, root: Path = Path("."), tmdb_client=None, fetch_ratings_fn=None) -> None`；副作用：寫 `index.html`、`reports/<date>.html`、`state.json`。環境變數 `TMDB_API_KEY`、`OMDB_API_KEY`（注入 client 時不需要）。

- [ ] **Step 1: 寫失敗測試**

`tests/test_main.py`：
```python
import datetime
import json

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
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `python3 -m pytest tests/test_main.py -v`
Expected: FAIL（import error）

- [ ] **Step 3: 實作**

`highscore/main.py`：
```python
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
```

注意：`fetch_ratings_fn` 測試注入時只吃 `imdb_id` 一個參數，測試裡的 `fake_fetch(imdb_id, api_key="")` 第二參數有預設值所以相容。

- [ ] **Step 4: 跑測試確認通過**

Run: `python3 -m pytest tests/test_main.py -v`
Expected: 2 passed

- [ ] **Step 5: 全套件回歸**

Run: `python3 -m pytest -q`
Expected: 39 passed

- [ ] **Step 6: Commit**

```bash
git add highscore/main.py tests/test_main.py
git commit -m "feat: 主流程串接與報告輸出"
```

---

### Task 8: GitHub Actions workflow + repo 雜項

**Files:**
- Create: `.github/workflows/weekly-report.yml`, `.nojekyll`, `README.md`, `.gitignore`

**Interfaces:**
- Consumes: `python -m highscore.main`（Task 7）、secrets `TMDB_API_KEY`/`OMDB_API_KEY`
- Produces: 每週五 01:00 UTC（台北 09:00）自動執行並 commit 報告的 workflow，名稱 `weekly-report.yml`

- [ ] **Step 1: 寫 workflow**

`.github/workflows/weekly-report.yml`：
```yaml
name: weekly-report

on:
  schedule:
    - cron: "0 1 * * 5"   # 週五 01:00 UTC = 台北週五 09:00
  workflow_dispatch:

permissions:
  contents: write

jobs:
  report:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: 安裝依賴
        run: pip install -r requirements.txt

      - name: 單元測試
        run: python -m pytest -q

      - name: 產出週報
        env:
          TMDB_API_KEY: ${{ secrets.TMDB_API_KEY }}
          OMDB_API_KEY: ${{ secrets.OMDB_API_KEY }}
        run: python -m highscore.main

      - name: Commit 報告
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git add index.html reports/ state.json
          git diff --cached --quiet || git commit -m "report: $(date -u +%F)"
          git push
```

- [ ] **Step 2: 其餘檔案**

`.nojekyll`：空檔案（讓 Pages 跳過 Jekyll 處理）。

`.gitignore`：
```
__pycache__/
.pytest_cache/
```

`README.md`：
```markdown
# 高分片週報

每週五 09:00（台北）自動撈取近 60 天的新片，篩出爛番茄 ≥ 85% 且 IMDb ≥ 7.5
的電影與影集，發布到 GitHub Pages。

- 最新報告：https://jsdryan.github.io/highscore-weekly/
- 資料來源：TMDB（候選與繁中詮釋資料）、OMDb（IMDb ＋爛番茄分數）
- 影集缺爛番茄分數時（OMDb 覆蓋限制），以 IMDb 單邊門檻入選並標「RT 無資料」

本地執行：`TMDB_API_KEY=... OMDB_API_KEY=... python3 -m highscore.main`
```

- [ ] **Step 3: 驗證 YAML 可解析**

Run: `python3 -c "import yaml,sys; yaml.safe_load(open('.github/workflows/weekly-report.yml')); print('OK')"`（若無 pyyaml 則 `pip3 install pyyaml`）
Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add .github .nojekyll README.md .gitignore
git commit -m "ci: 每週五 09:00 自動產報告的 workflow"
```

---

### Task 9: 部署與端對端驗證（需用戶提供 API keys）

**Files:**
- 無新檔案；操作 GitHub

**Interfaces:**
- Consumes: 全部前置任務、用戶提供的兩個 API key

- [ ] **Step 1: 本機端對端驗證（真實 API）**

```bash
TMDB_API_KEY=<用戶提供> OMDB_API_KEY=<用戶提供> python3 -m highscore.main
open index.html
```
Expected: 終端印出「電影 N 部、影集 M 部入選」，瀏覽器實看報告內容合理（有片、分數正確、無版面破損）。抽查 2–3 部片的分數與 IMDb/RT 網站一致。

- [ ] **Step 2: 清除本機測試產物**

本機驗證產生的 `index.html`、`reports/`、`state.json` 不要 commit（首次正式資料由 Actions 產生）：
```bash
git status --short   # 確認上述檔案未被追蹤，若曾誤 add 則 git restore --staged
rm -f index.html state.json && rm -rf reports/
```

- [ ] **Step 3: 建 repo 並 push（用戶已授權）**

```bash
gh repo create highscore-weekly --public --source . --push
```
Expected: repo 建立且 main branch 推上。

- [ ] **Step 4: 設 secrets**

```bash
gh secret set TMDB_API_KEY --body "<用戶提供>" -R jsdryan/highscore-weekly
gh secret set OMDB_API_KEY --body "<用戶提供>" -R jsdryan/highscore-weekly
gh secret list -R jsdryan/highscore-weekly
```
Expected: 兩個 secrets 列出。

- [ ] **Step 5: 啟用 GitHub Pages（main branch root）**

```bash
gh api -X POST repos/jsdryan/highscore-weekly/pages \
  -f "source[branch]=main" -f "source[path]=/"
```
Expected: HTTP 201。

- [ ] **Step 6: 手動觸發 workflow 並確認成功**

```bash
gh workflow run weekly-report.yml -R jsdryan/highscore-weekly
sleep 30 && gh run list -R jsdryan/highscore-weekly --limit 1
gh run watch -R jsdryan/highscore-weekly $(gh run list -R jsdryan/highscore-weekly --limit 1 --json databaseId --jq '.[0].databaseId')
```
Expected: run 狀態 `completed success`，repo 出現 `index.html` 等產物 commit。

- [ ] **Step 7: 確認 Pages 上線**

```bash
sleep 60 && curl -sI https://jsdryan.github.io/highscore-weekly/ | head -3
```
Expected: `HTTP/2 200`。瀏覽器開 https://jsdryan.github.io/highscore-weekly/ 實看報告。

- [ ] **Step 8: 回報用戶**

附上 Pages 網址、本期入選清單摘要、下次自動執行時間。
