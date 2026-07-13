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
