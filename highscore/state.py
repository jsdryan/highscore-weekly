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
