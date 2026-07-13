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
