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
