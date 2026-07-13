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
