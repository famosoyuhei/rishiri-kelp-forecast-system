from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest

import open_meteo_guard as omg


@pytest.fixture(autouse=True)
def reset_guard(monkeypatch):
    monkeypatch.setenv("OPEN_METEO_CIRCUIT_BREAKER_ENABLED", "true")
    monkeypatch.delenv("UPSTASH_REDIS_REST_URL", raising=False)
    monkeypatch.delenv("UPSTASH_REDIS_REST_TOKEN", raising=False)
    omg._MEM_CIRCUIT = None
    yield
    omg._MEM_CIRCUIT = None


def test_retry_after_seconds_is_parsed():
    now = datetime(2026, 7, 26, 0, 0, tzinfo=timezone.utc)
    assert omg.parse_retry_after("120", now=now) == now + timedelta(seconds=120)


def test_retry_after_http_date_is_parsed():
    parsed = omg.parse_retry_after("Sun, 26 Jul 2026 00:02:00 GMT")
    assert parsed == datetime(2026, 7, 26, 0, 2, tzinfo=timezone.utc)


def test_first_429_without_retry_after_opens_30_minute_circuit(monkeypatch):
    now = datetime(2026, 7, 26, 0, 0, tzinfo=timezone.utc)
    monkeypatch.setattr(omg, "utc_now", lambda: now)
    err = omg.open_circuit("line", None)
    assert err.consecutive_429_count == 1
    assert err.retry_after_at == "2026-07-26T00:30:00Z"


def test_consecutive_429_backoff_sequence_without_retry_after(monkeypatch):
    now = datetime(2026, 7, 26, 0, 0, tzinfo=timezone.utc)

    monkeypatch.setattr(omg, "utc_now", lambda: now)
    assert omg.open_circuit("line", None).retry_after_at == "2026-07-26T00:30:00Z"

    now = datetime(2026, 7, 26, 0, 1, tzinfo=timezone.utc)
    monkeypatch.setattr(omg, "utc_now", lambda: now)
    assert omg.open_circuit("line", None).retry_after_at == "2026-07-26T01:01:00Z"

    now = datetime(2026, 7, 26, 0, 2, tzinfo=timezone.utc)
    monkeypatch.setattr(omg, "utc_now", lambda: now)
    assert omg.open_circuit("line", None).retry_after_at == "2026-07-26T02:02:00Z"

    now = datetime(2026, 7, 26, 0, 3, tzinfo=timezone.utc)
    monkeypatch.setattr(omg, "utc_now", lambda: now)
    assert omg.open_circuit("line", None).retry_after_at == "2026-07-26T06:03:00Z"


def test_circuit_open_skips_http_client(monkeypatch):
    now = datetime(2026, 7, 26, 0, 0, tzinfo=timezone.utc)
    monkeypatch.setattr(omg, "utc_now", lambda: now)
    omg.open_circuit("forecast", "120")

    requests_module = MagicMock()
    with pytest.raises(omg.OpenMeteoCircuitOpenError):
        omg.guarded_get("https://example.invalid", source="forecast", requests_module=requests_module)
    requests_module.get.assert_not_called()


def test_success_closes_open_circuit(monkeypatch):
    now = datetime(2026, 7, 26, 0, 0, tzinfo=timezone.utc)
    monkeypatch.setattr(omg, "utc_now", lambda: now)
    omg.open_circuit("forecast", "120")

    later = datetime(2026, 7, 26, 0, 10, tzinfo=timezone.utc)
    monkeypatch.setattr(omg, "utc_now", lambda: later)
    resp = MagicMock(status_code=200)
    resp.raise_for_status.return_value = None
    requests_module = MagicMock()
    requests_module.get.return_value = resp

    assert omg.guarded_get("https://example.invalid", source="forecast", requests_module=requests_module) is resp
    assert omg.get_circuit() is None


def test_redis_failure_does_not_raise(monkeypatch):
    monkeypatch.setattr(omg.requests, "get", MagicMock(side_effect=RuntimeError("redis down")))
    monkeypatch.setenv("UPSTASH_REDIS_REST_URL", "https://redis.example.invalid")
    monkeypatch.setenv("UPSTASH_REDIS_REST_TOKEN", "token")
    assert omg.get_circuit() is None


def test_feature_flag_off_bypasses_circuit(monkeypatch):
    monkeypatch.setenv("OPEN_METEO_CIRCUIT_BREAKER_ENABLED", "false")
    omg.open_circuit("forecast", None)
    resp = MagicMock(status_code=200)
    resp.raise_for_status.return_value = None
    requests_module = MagicMock()
    requests_module.get.return_value = resp
    assert omg.guarded_get("https://example.invalid", source="forecast", requests_module=requests_module) is resp
