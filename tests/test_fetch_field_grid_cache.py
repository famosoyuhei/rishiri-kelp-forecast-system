"""
Tests for jobs/fetch_field_grid_cache.py's main().

Background: this GitHub Actions job re-runs every ~15-45 minutes (schedule +
cron-job.org backup). Confirmed live on 2026-09-01/02: a 2xx response whose
body doesn't parse as JSON ("invalid_json") happened in 2 of 100 runs that
day, and both self-healed on the very next run -- a transport-layer hiccup
for this particular large 49-point multi-location payload, not a real API or
logic error. It used to return exit code 1 (a "Run failed" email) for this;
now it's treated the same as network_error/rate_limited -- log and return 0,
relying on the next run and the existing stale-fallback TTL.

Run from project root:
    python -m pytest tests/test_fetch_field_grid_cache.py -v
"""
from unittest.mock import MagicMock

import pytest

from jobs import fetch_field_grid_cache as job
from open_meteo_prefetch import FIELD_GRID_FORECAST_DAYS, FIELD_GRID_HOURLY_VARS, _split_vars, build_rishiri_grid


def _resp(status_code=200, json_data=None, json_raises=False, headers=None):
    resp = MagicMock()
    resp.status_code = status_code
    resp.headers = headers or {}
    if json_raises:
        resp.json.side_effect = ValueError("not json")
    else:
        resp.json.return_value = json_data
    return resp


def _sample_field_grid_point():
    """One grid point's raw Open-Meteo response, matching field_grid_request()'s
    hourly variable list and FIELD_GRID_FORECAST_DAYS (no `daily` key)."""
    hours = [f"2026-08-{day + 1:02d}T{h:02d}:00" for day in range(FIELD_GRID_FORECAST_DAYS) for h in range(24)]
    n = len(hours)
    return {"hourly": {"time": hours, **{var: [1.0] * n for var in _split_vars(FIELD_GRID_HOURLY_VARS)}}}


def sample_field_grid_response(n_points=None):
    n_points = n_points or len(build_rishiri_grid())
    return [_sample_field_grid_point() for _ in range(n_points)]


def test_main_success_writes_cache(monkeypatch):
    monkeypatch.setattr(job.requests, "get", lambda url, timeout: _resp(200, sample_field_grid_response()))
    monkeypatch.setattr(job, "redis_set_json", lambda key, record, ttl: True)

    assert job.main([]) == 0


def test_main_invalid_json_does_not_fail_the_run(monkeypatch, capsys):
    """The exact regression: a 2xx response with an unparseable body must
    not exit 1 (no 'Run failed' email) -- same treatment as a network error."""
    monkeypatch.setattr(job.requests, "get", lambda url, timeout: _resp(200, json_raises=True))
    write_calls = []
    monkeypatch.setattr(job, "redis_set_json", lambda key, record, ttl: write_calls.append(1) or True)

    exit_code = job.main([])

    assert exit_code == 0
    assert write_calls == []  # nothing written -- previous cache entry stays valid
    out = capsys.readouterr().out
    assert '"event": "invalid_json"' in out


def test_main_network_error_does_not_fail_the_run(monkeypatch):
    def _raise(*a, **k):
        raise job.requests.exceptions.ConnectionError("boom")
    monkeypatch.setattr(job.requests, "get", _raise)

    assert job.main([]) == 0


def test_main_429_does_not_fail_the_run_and_opens_circuit(monkeypatch):
    monkeypatch.setattr(job.requests, "get", lambda url, timeout: _resp(429, headers={"Retry-After": "60"}))
    circuit_calls = []
    monkeypatch.setattr(job, "redis_set_json", lambda key, record, ttl: circuit_calls.append(key) or True)

    assert job.main([]) == 0
    assert job.GITHUB_ACTIONS_CIRCUIT_KEY in circuit_calls


def test_main_http_error_still_fails_the_run(monkeypatch):
    """A genuine server error (5xx) is still a real failure worth surfacing."""
    monkeypatch.setattr(job.requests, "get", lambda url, timeout: _resp(500, {}))

    assert job.main([]) == 1


def test_main_invalid_response_shape_still_fails_the_run(monkeypatch):
    """Valid JSON but the wrong shape (e.g. missing points) is a real
    validation failure, not a transport hiccup -- must still fail."""
    monkeypatch.setattr(job.requests, "get", lambda url, timeout: _resp(200, {"hourly": "not_an_array"}))

    assert job.main([]) == 1


def test_main_cache_write_failure_still_fails_the_run(monkeypatch):
    monkeypatch.setattr(job.requests, "get", lambda url, timeout: _resp(200, sample_field_grid_response()))
    monkeypatch.setattr(job, "redis_set_json", lambda key, record, ttl: False)

    assert job.main([]) == 1
