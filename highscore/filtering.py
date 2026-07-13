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
