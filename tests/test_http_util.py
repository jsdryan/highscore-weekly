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
