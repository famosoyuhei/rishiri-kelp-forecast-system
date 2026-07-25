from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest

import line_integration as li
import open_meteo_prefetch as omp
from jobs import fetch_open_meteo_for_notifications as job


def sample_open_meteo():
    days = [f"2026-07-{i + 1:02d}" for i in range(7)]
    hours = []
    for day in days:
        for h in range(24):
            hours.append(f"{day}T{h:02d}:00")
    return {
        "daily": {
            "time": days,
            "temperature_2m_max": [18.0] * 7,
            "temperature_2m_min": [10.0] * 7,
            "wind_speed_10m_max": [14.4] * 7,
            "relative_humidity_2m_mean": [70.0] * 7,
            "precipitation_sum": [0.0] * 7,
            "precipitation_probability_max": [2] * 7,
        },
        "hourly": {
            "time": hours,
            "relative_humidity_2m": [70.0] * len(hours),
            "wind_speed_10m": [14.4] * len(hours),
            "wind_direction_10m": [247.0 if i % 24 == 6 else 337.0 for i in range(len(hours))],
            "precipitation": [0.0] * len(hours),
        },
    }


def strip_prefetch(days):
    return [{k: v for k, v in d.items() if k != "prefetch"} for d in days]


def test_prefetch_record_wraps_valid_response():
    req = omp.line_forecast_request(45.1, 141.1)
    data = sample_open_meteo()
    ok, reason = omp.validate_forecast_response(data)
    record = omp.make_prefetch_record(
        req,
        data,
        fetched_at=datetime(2026, 7, 26, 0, 0, tzinfo=timezone.utc),
    )

    assert ok is True
    assert reason == "ok"
    assert record["schema_version"] == 1
    assert record["source"] == "github_actions_prefetch"
    assert record["request_fingerprint"] == req.fingerprint
    assert record["data"] == data


def test_error_json_is_not_valid_prefetch_data():
    ok, reason = omp.validate_forecast_response({"error": True, "reason": "bad"})
    assert ok is False
    assert reason == "error_json"


def test_broken_hourly_length_is_not_valid_prefetch_data():
    data = sample_open_meteo()
    data["hourly"]["wind_speed_10m"] = [1.0]
    ok, reason = omp.validate_forecast_response(data)
    assert ok is False
    assert reason.startswith("bad_hourly_length")


def test_load_prefetch_rejects_fingerprint_mismatch(monkeypatch):
    req = omp.line_forecast_request(45.1, 141.1)
    record = omp.make_prefetch_record(req, sample_open_meteo())
    record["request_fingerprint"] = "wrong"
    monkeypatch.setattr(omp, "redis_get_json", lambda key, requests_module=None: record)

    data, meta = omp.load_prefetch(req)

    assert data is None
    assert meta["reason"] == "fingerprint_mismatch"


def test_load_prefetch_rejects_schema_mismatch(monkeypatch):
    req = omp.line_forecast_request(45.1, 141.1)
    record = omp.make_prefetch_record(req, sample_open_meteo())
    record["schema_version"] = 999
    monkeypatch.setattr(omp, "redis_get_json", lambda key, requests_module=None: record)

    data, meta = omp.load_prefetch(req)

    assert data is None
    assert meta["reason"] == "schema_mismatch"


def test_fresh_prefetch_is_usable(monkeypatch):
    req = omp.line_forecast_request(45.1, 141.1)
    now = datetime(2026, 7, 26, 1, 0, tzinfo=timezone.utc)
    record = omp.make_prefetch_record(req, sample_open_meteo(), fetched_at=now - timedelta(minutes=30))
    monkeypatch.setattr(omp, "redis_get_json", lambda key, requests_module=None: record)

    data, meta = omp.load_prefetch(req, now=now)

    assert data is not None
    assert meta["prefetched"] is True
    assert meta["stale"] is False
    assert meta["age_minutes"] == 30


def test_stale_prefetch_within_12_hours_is_usable_with_stale_flag(monkeypatch):
    req = omp.line_forecast_request(45.1, 141.1)
    now = datetime(2026, 7, 26, 12, 0, tzinfo=timezone.utc)
    record = omp.make_prefetch_record(req, sample_open_meteo(), fetched_at=now - timedelta(hours=8))
    monkeypatch.setattr(omp, "redis_get_json", lambda key, requests_module=None: record)

    data, meta = omp.load_prefetch(req, now=now)

    assert data is not None
    assert meta["stale"] is True
    assert meta["reason"] == "stale_hit"


def test_stale_prefetch_over_12_hours_is_rejected(monkeypatch):
    req = omp.line_forecast_request(45.1, 141.1)
    now = datetime(2026, 7, 26, 12, 0, tzinfo=timezone.utc)
    record = omp.make_prefetch_record(req, sample_open_meteo(), fetched_at=now - timedelta(hours=13))
    monkeypatch.setattr(omp, "redis_get_json", lambda key, requests_module=None: record)

    data, meta = omp.load_prefetch(req, now=now)

    assert data is None
    assert meta["reason"] == "stale_expired"


def test_redis_malformed_prefetch_is_miss(monkeypatch):
    req = omp.line_forecast_request(45.1, 141.1)
    monkeypatch.setattr(omp, "redis_get_json", lambda key, requests_module=None: ["bad"])

    data, meta = omp.load_prefetch(req)

    assert data is None
    assert meta["reason"] == "miss"


def test_line_prefetch_hit_does_not_call_http(monkeypatch):
    monkeypatch.setenv("OPEN_METEO_PREFETCH_ENABLED", "true")
    data = sample_open_meteo()
    monkeypatch.setattr(li, "load_prefetch", lambda req: (data, {"prefetched": True, "stale": False, "age_minutes": 10}))
    guarded = MagicMock()
    monkeypatch.setattr(li, "guarded_get", guarded)

    days = li.get_forecast_for_spot(45.1, 141.1)

    guarded.assert_not_called()
    assert days[0]["score"] == 100
    assert days[0]["wind_direction_period"] == "WSW→NNW"


def test_prefetch_only_miss_skips_direct_open_meteo(monkeypatch):
    monkeypatch.setenv("OPEN_METEO_PREFETCH_ENABLED", "true")
    monkeypatch.setenv("OPEN_METEO_PREFETCH_ONLY", "true")
    monkeypatch.setattr(li, "load_prefetch", lambda req: (None, {"reason": "miss"}))
    guarded = MagicMock()
    monkeypatch.setattr(li, "guarded_get", guarded)

    assert li.get_forecast_for_spot(45.1, 141.1) == []
    guarded.assert_not_called()


def test_prefetch_miss_can_fallback_when_only_false(monkeypatch):
    monkeypatch.setenv("OPEN_METEO_PREFETCH_ENABLED", "true")
    monkeypatch.setenv("OPEN_METEO_PREFETCH_ONLY", "false")
    monkeypatch.setattr(li, "load_prefetch", lambda req: (None, {"reason": "miss"}))
    resp = MagicMock(status_code=200)
    resp.raise_for_status.return_value = None
    resp.json.return_value = sample_open_meteo()
    guarded = MagicMock(return_value=resp)
    monkeypatch.setattr(li, "guarded_get", guarded)

    days = li.get_forecast_for_spot(45.1, 141.1)

    guarded.assert_called_once()
    assert days[0]["score"] == 100


def test_direct_and_prefetch_paths_match_major_line_values(monkeypatch):
    data = sample_open_meteo()
    resp = MagicMock(status_code=200)
    resp.raise_for_status.return_value = None
    resp.json.return_value = data
    monkeypatch.setenv("OPEN_METEO_PREFETCH_ENABLED", "false")
    monkeypatch.setattr(li, "guarded_get", MagicMock(return_value=resp))
    direct = li.get_forecast_for_spot(45.1, 141.1)

    monkeypatch.setenv("OPEN_METEO_PREFETCH_ENABLED", "true")
    monkeypatch.setattr(li, "load_prefetch", lambda req: (data, {"prefetched": True, "stale": False, "age_minutes": 5}))
    monkeypatch.setattr(li, "guarded_get", MagicMock(side_effect=AssertionError("no direct fetch")))
    prefetched = li.get_forecast_for_spot(45.1, 141.1)

    assert strip_prefetch(prefetched) == strip_prefetch(direct)
    assert li.format_single_day("新湊", prefetched[0]) == li.format_single_day("新湊", direct[0])


def test_stale_line_message_adds_note(monkeypatch):
    monkeypatch.setenv("OPEN_METEO_PREFETCH_ENABLED", "true")
    data = sample_open_meteo()
    monkeypatch.setattr(li, "load_prefetch", lambda req: (data, {"prefetched": True, "stale": True, "age_minutes": 480}))

    days = li.get_forecast_for_spot(45.1, 141.1)
    text = li.format_single_day("新湊", days[0])

    assert "直近に取得した予報" in text


def test_job_fetch_one_429_does_not_write_cache(monkeypatch):
    monkeypatch.setenv("UPSTASH_REDIS_REST_URL", "https://redis.example.invalid")
    monkeypatch.setenv("UPSTASH_REDIS_REST_TOKEN", "token")
    resp = MagicMock(status_code=429, headers={"Retry-After": "120"})
    session = MagicMock()
    session.get.return_value = resp
    writes = []
    monkeypatch.setattr(job, "redis_set_json", lambda *args, **kwargs: writes.append(args) or True)

    with pytest.raises(job.RateLimited):
        job.fetch_one({"lat": 45.1, "lon": 141.1}, session=session)

    session.get.assert_called_once()
    assert len(writes) == 1  # github_actions circuit only, no prefetch overwrite
    assert writes[0][0] == job.GITHUB_ACTIONS_CIRCUIT_KEY


def test_job_main_stops_after_first_429(monkeypatch):
    monkeypatch.setattr(job, "collect_target_spots", lambda kind: [
        {"lat": 45.1, "lon": 141.1},
        {"lat": 45.2, "lon": 141.2},
    ])
    calls = []

    def fake_fetch(target):
        calls.append(target)
        raise job.RateLimited("120")

    monkeypatch.setattr(job, "fetch_one", fake_fetch)

    assert job.main(["--kind", "morning"]) == 2
    assert len(calls) == 1


def test_invalid_response_is_not_saved_by_job(monkeypatch):
    resp = MagicMock(status_code=200)
    bad = sample_open_meteo()
    bad["daily"] = {"time": []}
    resp.json.return_value = bad
    session = MagicMock()
    session.get.return_value = resp
    writes = []
    monkeypatch.setattr(job, "redis_set_json", lambda *args, **kwargs: writes.append(args) or True)

    ok, reason = job.fetch_one({"lat": 45.1, "lon": 141.1}, session=session)

    assert ok is False
    assert reason == "missing_daily_time"
    assert writes == []


def test_workflow_contains_expected_cron_times():
    text = (job.ROOT / ".github" / "workflows" / "fetch-open-meteo-cache.yml").read_text(encoding="utf-8")
    assert 'cron: "30 6 * * *"' in text   # 15:30 JST
    assert 'cron: "0 16 * * *"' in text   # 01:00 JST
    assert "concurrency:" in text
    assert "fetch_open_meteo_for_notifications.py" in text
