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
