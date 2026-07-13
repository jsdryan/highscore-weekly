"""帶重試的 HTTP GET，TMDB 與 OMDb 共用。"""
import re
import time

import requests

# 連線層錯誤訊息會含完整 query string；錯誤最終會渲染進公開報告，金鑰必須遮蔽
_REDACT = re.compile(r"(api_?key=)[^&\s'\"]+", re.IGNORECASE)


class FetchError(Exception):
    """API 呼叫在重試耗盡後仍失敗。"""


def _redact(message: str) -> str:
    return _REDACT.sub(r"\1***", message)


def get_json(url, params, retries=3, backoff=2.0, timeout=30, session=None):
    sess = session or requests
    last_err = None
    for attempt in range(retries):
        try:
            resp = sess.get(url, params=params, timeout=timeout)
            if resp.status_code == 200:
                return resp.json()
            last_err = FetchError(_redact(f"HTTP {resp.status_code}: {url}"))
        except requests.RequestException as exc:
            last_err = FetchError(_redact(f"{type(exc).__name__}: {exc}"))
        if attempt < retries - 1:
            time.sleep(backoff * (2 ** attempt))
    raise last_err
