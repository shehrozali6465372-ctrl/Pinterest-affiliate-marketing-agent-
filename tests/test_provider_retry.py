from types import SimpleNamespace

from app.provider_retry import retry_delay_seconds


def test_retry_after_seconds_is_honored_and_bounded():
    response = SimpleNamespace(headers={"retry-after": "3"})
    assert retry_delay_seconds(response, 1) == 3
    assert retry_delay_seconds(response, 1, max_retry_after=2) is None


def test_retry_after_http_date_is_parsed(monkeypatch):
    response = SimpleNamespace(headers={"retry-after": "Thu, 01 Jan 1970 00:00:03 GMT"})
    assert 1.0 <= retry_delay_seconds(response, 1) <= 1.25
