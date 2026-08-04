from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest
import requests

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


def test_prefetch_only_miss_skips_direct_open_meteo_when_circuit_open(monkeypatch):
    # PREFETCH_ONLY's job is to avoid a live call *while Open-Meteo is
    # actually 429ing* — simulate that by making the circuit report open.
    monkeypatch.setenv("OPEN_METEO_PREFETCH_ENABLED", "true")
    monkeypatch.setenv("OPEN_METEO_PREFETCH_ONLY", "true")
    monkeypatch.setattr(li, "load_prefetch", lambda req: (None, {"reason": "miss"}))
    monkeypatch.setattr(li, "is_circuit_open", lambda: True)
    guarded = MagicMock()
    monkeypatch.setattr(li, "guarded_get", guarded)

    assert li.get_forecast_for_spot(45.1, 141.1) == []
    guarded.assert_not_called()


def test_prefetch_only_miss_falls_back_live_when_circuit_closed(monkeypatch):
    # 2026-07-27 incident: GitHub Actions' scheduled prefetch run never fired,
    # so prefetch missed for a reason unrelated to Open-Meteo actually being
    # rate-limited. With the circuit closed, PREFETCH_ONLY must not turn a
    # one-off scheduling gap into a guaranteed empty notification — it should
    # fall back to a live fetch just like PREFETCH_ONLY=false would.
    monkeypatch.setenv("OPEN_METEO_PREFETCH_ENABLED", "true")
    monkeypatch.setenv("OPEN_METEO_PREFETCH_ONLY", "true")
    monkeypatch.setattr(li, "load_prefetch", lambda req: (None, {"reason": "miss"}))
    monkeypatch.setattr(li, "is_circuit_open", lambda: False)
    resp = MagicMock(status_code=200)
    resp.raise_for_status.return_value = None
    resp.json.return_value = sample_open_meteo()
    guarded = MagicMock(return_value=resp)
    monkeypatch.setattr(li, "guarded_get", guarded)

    days = li.get_forecast_for_spot(45.1, 141.1)

    guarded.assert_called_once()
    assert days[0]["score"] == 100


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


def test_job_fetch_one_network_timeout_does_not_crash_the_run(monkeypatch):
    # 2026-07-28 incident: an unhandled ReadTimeout from session.get() crashed
    # the entire prefetch script (exit code 1 -> GitHub "Run failed" email),
    # aborting every remaining spot in the run over a single transient
    # network hiccup unrelated to Open-Meteo rate-limiting.
    session = MagicMock()
    session.get.side_effect = requests.exceptions.ReadTimeout("read timed out")

    ok, reason = job.fetch_one({"lat": 45.1, "lon": 141.1}, session=session)

    assert ok is False
    assert reason == "network_error"


def test_fetch_request_network_timeout_does_not_crash_the_run(monkeypatch):
    session = MagicMock()
    session.get.side_effect = requests.exceptions.ConnectionError("connection reset")

    req = omp.marine_forecast_request(45.1, 141.1)
    ok, reason = job.fetch_request(
        req, ttl_seconds=100, daily_vars=None, hourly_vars=omp.MARINE_HOURLY_VARS, session=session,
    )

    assert ok is False
    assert reason == "network_error"


def test_main_continues_past_a_single_network_timeout(monkeypatch):
    # End-to-end: one target's fetch times out, the run must still complete
    # (not raise) and continue processing the rest. fetch_one()'s session
    # parameter defaults to the real `requests` module (bound at function
    # definition time), so patch requests.get directly rather than the
    # module-level `job.requests` name.
    monkeypatch.setattr(
        job, "collect_target_spots",
        lambda kind, now_jst=None: [
            {"lat": 45.1, "lon": 141.1},
            {"lat": 45.2, "lon": 141.2},
        ],
    )
    monkeypatch.setattr(job, "collect_canary_targets", lambda kind, now_jst=None: [])

    calls = []

    def flaky_get(url, timeout=None):
        calls.append(url)
        if len(calls) == 1:
            raise requests.exceptions.ReadTimeout("read timed out")
        resp = MagicMock(status_code=200)
        resp.json.return_value = sample_open_meteo()
        return resp

    monkeypatch.setattr(requests, "get", flaky_get)

    exit_code = job.main(["--kind", "morning"])

    assert exit_code == 0
    assert len(calls) == 2


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

    # A 429 is an expected, designed-for outcome, not a failure — exit 0 so
    # GitHub Actions doesn't send a "Run failed" email every time Open-Meteo
    # rate-limits us (2026-07-30 incident: exit 2 was treated as a failed
    # run for a scenario the whole prefetch mitigation exists to handle).
    assert job.main(["--kind", "morning"]) == 0
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


def test_job_success_log_contains_safe_fetched_at(monkeypatch, capsys):
    monkeypatch.setenv("UPSTASH_REDIS_REST_URL", "https://redis.example.invalid")
    monkeypatch.setenv("UPSTASH_REDIS_REST_TOKEN", "token")
    resp = MagicMock(status_code=200)
    resp.json.return_value = sample_open_meteo()
    session = MagicMock()
    session.get.return_value = resp
    monkeypatch.setattr(job, "redis_set_json", lambda *args, **kwargs: True)

    ok, reason = job.fetch_one({"lat": 45.1, "lon": 141.1}, session=session)

    assert ok is True
    assert reason == "ok"
    out = capsys.readouterr().out
    assert '"event": "success"' in out
    assert '"fetched_at":' in out
    assert "redis.example.invalid" not in out
    assert "temperature_2m_max" not in out


def test_workflow_contains_expected_cron_times():
    text = (job.ROOT / ".github" / "workflows" / "fetch-open-meteo-cache.yml").read_text(encoding="utf-8")
    assert 'cron: "30 6 * * *"' in text   # 15:30 JST primary evening
    assert 'cron: "40 6 * * *"' in text   # 15:40 JST backup evening (2026-07-27 missed-schedule incident)
    assert 'cron: "0 16 * * *"' in text   # 01:00 JST primary morning
    assert 'cron: "10 16 * * *"' in text  # 01:10 JST backup morning
    assert "concurrency:" in text
    assert "fetch_open_meteo_for_notifications.py" in text
    # Both evening cron strings must resolve to kind=evening, not just the primary.
    assert '"${{ github.event.schedule }}" = "30 6 * * *" ] || [ "${{ github.event.schedule }}" = "40 6 * * *"' in text


# ---------------------------------------------------------------------------
# Enhanced/summit/marine prefetch (LINE canary-spot Open-Meteo 429 resilience)
# ---------------------------------------------------------------------------

def _hourly_time_series():
    days = [f"2026-07-{i + 1:02d}" for i in range(7)]
    hours = []
    for day in days:
        for h in range(24):
            hours.append(f"{day}T{h:02d}:00")
    return days, hours


def sample_enhanced_open_meteo():
    days, hours = _hourly_time_series()
    hourly = {"time": hours}
    for var in omp._split_vars(omp.ENHANCED_HOURLY_VARS):
        hourly[var] = [0.0] * len(hours)
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
        "hourly": hourly,
    }


def sample_summit_open_meteo():
    _, hours = _hourly_time_series()
    return {"hourly": {"time": hours, "temperature_2m": [5.0] * len(hours)}}


def sample_marine_open_meteo():
    # 2026-08-04: sea_surface_temperature is an hourly-only Marine API
    # variable -- requesting it as `daily` 400s in production (see
    # MARINE_HOURLY_VARS comment in open_meteo_prefetch.py).
    _, hours = _hourly_time_series()
    return {"hourly": {"time": hours, "sea_surface_temperature": [16.0] * len(hours)}}


def test_enhanced_forecast_request_has_distinct_namespace_and_ignores_elevation_in_identity():
    req = omp.enhanced_forecast_request(45.1, 141.1, 30.0)
    assert req.api_type == "enhanced_forecast"
    assert req.redis_key.startswith(f"{omp.KEY_PREFIX}:enhanced_forecast:")
    assert req.params["elevation"] == "30.0"

    # Elevation must not affect the cache identity — it's a fixed, spot-specific
    # value (see enhanced_forecast_request()'s docstring), so GitHub Actions and
    # Render always land on the same redis_key as long as they agree on lat/lon.
    other = omp.enhanced_forecast_request(45.1, 141.1, 999.0)
    assert req.identity == other.identity
    assert req.redis_key == other.redis_key


def test_enhanced_forecast_prefetch_roundtrip(monkeypatch):
    req = omp.enhanced_forecast_request(45.1, 141.1, 30.0)
    data = sample_enhanced_open_meteo()
    record = omp.make_prefetch_record(req, data)
    monkeypatch.setattr(omp, "redis_get_json", lambda key, requests_module=None: record)

    loaded, meta = omp.load_prefetch(req)

    assert loaded == data
    assert meta["prefetched"] is True


def test_summit_forecast_request_has_no_daily_section(monkeypatch):
    req = omp.summit_forecast_request(omp.SUMMIT_LAT, omp.SUMMIT_LON)
    data = sample_summit_open_meteo()
    ok, reason = omp.validate_forecast_response(data, daily_vars=None, hourly_vars=omp.SUMMIT_HOURLY_VARS)
    assert ok is True, reason

    record = omp.make_prefetch_record(req, data)
    monkeypatch.setattr(omp, "redis_get_json", lambda key, requests_module=None: record)
    loaded, meta = omp.load_prefetch(req)
    assert loaded == data
    assert meta["prefetched"] is True


def test_marine_forecast_request_has_no_daily_section(monkeypatch):
    req = omp.marine_forecast_request(45.1, 141.1)
    data = sample_marine_open_meteo()
    ok, reason = omp.validate_forecast_response(data, daily_vars=None, hourly_vars=omp.MARINE_HOURLY_VARS)
    assert ok is True, reason

    record = omp.make_prefetch_record(req, data)
    monkeypatch.setattr(omp, "redis_get_json", lambda key, requests_module=None: record)
    loaded, meta = omp.load_prefetch(
        req,
        fresh_max_age_minutes=omp.MARINE_FRESH_MAX_AGE_MINUTES,
        stale_max_age_minutes=omp.MARINE_STALE_MAX_AGE_MINUTES,
    )
    assert loaded == data
    assert meta["prefetched"] is True


def test_marine_prefetch_stale_within_48h_window(monkeypatch):
    req = omp.marine_forecast_request(45.1, 141.1)
    now = datetime(2026, 7, 26, 12, 0, tzinfo=timezone.utc)
    record = omp.make_prefetch_record(req, sample_marine_open_meteo(), fetched_at=now - timedelta(hours=30))
    monkeypatch.setattr(omp, "redis_get_json", lambda key, requests_module=None: record)

    data, meta = omp.load_prefetch(
        req, now=now,
        fresh_max_age_minutes=omp.MARINE_FRESH_MAX_AGE_MINUTES,
        stale_max_age_minutes=omp.MARINE_STALE_MAX_AGE_MINUTES,
    )
    assert data is not None
    assert meta["stale"] is True


def test_marine_prefetch_expired_after_48h_window(monkeypatch):
    req = omp.marine_forecast_request(45.1, 141.1)
    now = datetime(2026, 7, 26, 12, 0, tzinfo=timezone.utc)
    record = omp.make_prefetch_record(req, sample_marine_open_meteo(), fetched_at=now - timedelta(hours=50))
    monkeypatch.setattr(omp, "redis_get_json", lambda key, requests_module=None: record)

    data, meta = omp.load_prefetch(
        req, now=now,
        fresh_max_age_minutes=omp.MARINE_FRESH_MAX_AGE_MINUTES,
        stale_max_age_minutes=omp.MARINE_STALE_MAX_AGE_MINUTES,
    )
    assert data is None
    assert meta["reason"] == "stale_expired"


# ---------------------------------------------------------------------------
# GitHub Actions job: canary-spot enhanced/summit/marine fetch
# ---------------------------------------------------------------------------

def test_collect_canary_targets_empty_without_env_or_active_subscriptions(monkeypatch):
    monkeypatch.delenv(job.CANARY_SPOT_IDS_ENV, raising=False)
    monkeypatch.setattr(job, "collect_target_spots", lambda kind, now_jst=None: [])
    assert job.collect_canary_targets("morning") == []


def test_collect_canary_targets_resolves_known_static_spot(monkeypatch):
    monkeypatch.setenv(job.CANARY_SPOT_IDS_ENV, "H_2088_1443")
    monkeypatch.setattr(job, "collect_target_spots", lambda kind, now_jst=None: [])
    targets = job.collect_canary_targets("morning")
    assert len(targets) == 1
    assert targets[0]["spot_id"] == "H_2088_1443"
    assert "lat" in targets[0] and "lon" in targets[0]


def test_collect_canary_targets_skips_unknown_static_spot(monkeypatch):
    monkeypatch.setenv(job.CANARY_SPOT_IDS_ENV, "H_9999_9999")
    monkeypatch.setattr(job, "collect_target_spots", lambda kind, now_jst=None: [])
    assert job.collect_canary_targets("morning") == []


def test_collect_canary_targets_unions_static_list_with_active_notification_targets(monkeypatch):
    # Static list covers one spot; collect_target_spots() (the same set that
    # will actually receive a LINE notification this run) covers another —
    # both must end up in the enhanced-prefetch target list, deduplicated.
    monkeypatch.setenv(job.CANARY_SPOT_IDS_ENV, "H_2088_1443")
    monkeypatch.setattr(
        job, "collect_target_spots",
        lambda kind, now_jst=None: [
            {"spot_id": "H_2088_1443", "lat": 45.2, "lon": 141.1},  # overlaps static list
            {"spot_id": "H_1631_1434", "lat": 45.16, "lon": 141.14},
        ],
    )

    targets = job.collect_canary_targets("evening")

    ids = sorted(t["spot_id"] for t in targets)
    assert ids == ["H_1631_1434", "H_2088_1443"]


def test_canary_requests_use_approximate_elevation_without_manual_entry(monkeypatch):
    monkeypatch.setattr(job, "CANARY_SPOT_ELEVATIONS_M", {})
    reqs = list(job._canary_requests_for_target({"spot_id": "H_NEW_SPOT", "lat": 45.2, "lon": 141.1}))
    api_types = [r[0].api_type for r in reqs]
    # Enhanced-forecast prefetch is never skipped now — a newly-registered
    # spot without a manually-verified elevation still gets covered via a
    # network-free approximation, not left out.
    assert api_types == ["enhanced_forecast", "marine"]
    enhanced_req = reqs[0][0]
    assert float(enhanced_req.params["elevation"]) == omp.approximate_elevation_m(45.2, 141.1)


def test_canary_requests_prefer_manually_verified_elevation(monkeypatch):
    monkeypatch.setattr(job, "CANARY_SPOT_ELEVATIONS_M", {"H_2088_1443": 26.0})
    reqs = list(job._canary_requests_for_target({"spot_id": "H_2088_1443", "lat": 45.2, "lon": 141.1}))
    api_types = [r[0].api_type for r in reqs]
    assert api_types == ["enhanced_forecast", "marine"]
    enhanced_req = reqs[0][0]
    assert float(enhanced_req.params["elevation"]) == 26.0


def test_fetch_request_success_writes_cache(monkeypatch):
    resp = MagicMock(status_code=200)
    resp.json.return_value = sample_summit_open_meteo()
    session = MagicMock()
    session.get.return_value = resp
    writes = []
    monkeypatch.setattr(job, "redis_set_json", lambda *a, **kw: writes.append(a) or True)

    req = omp.summit_forecast_request(omp.SUMMIT_LAT, omp.SUMMIT_LON)
    ok, reason = job.fetch_request(
        req, ttl_seconds=100, daily_vars=None, hourly_vars=omp.SUMMIT_HOURLY_VARS, session=session,
    )

    assert ok is True
    assert reason == "ok"
    assert len(writes) == 1
    assert writes[0][0] == req.redis_key


def test_fetch_request_429_opens_circuit_and_raises(monkeypatch):
    resp = MagicMock(status_code=429, headers={"Retry-After": "60"})
    session = MagicMock()
    session.get.return_value = resp
    writes = []
    monkeypatch.setattr(job, "redis_set_json", lambda *a, **kw: writes.append(a) or True)

    req = omp.marine_forecast_request(45.1, 141.1)
    with pytest.raises(job.RateLimited):
        job.fetch_request(req, ttl_seconds=100, daily_vars=None, hourly_vars=omp.MARINE_HOURLY_VARS, session=session)

    assert writes[0][0] == job.GITHUB_ACTIONS_CIRCUIT_KEY


def test_main_fetches_canary_targets_after_simple_targets(monkeypatch):
    monkeypatch.setattr(job, "collect_target_spots", lambda kind, now_jst=None: [])
    monkeypatch.setattr(
        job, "collect_canary_targets",
        lambda kind, now_jst=None: [{"spot_id": "H_2088_1443", "lat": 45.2, "lon": 141.1}],
    )
    monkeypatch.setattr(job, "CANARY_SPOT_ELEVATIONS_M", {"H_2088_1443": 26.0})

    calls = []

    def fake_fetch_request(req, *, ttl_seconds, daily_vars, hourly_vars, session=None):
        calls.append(req.api_type)
        return True, "ok"

    monkeypatch.setattr(job, "fetch_request", fake_fetch_request)

    exit_code = job.main(["--kind", "morning"])

    assert exit_code == 0
    assert calls == ["summit_forecast", "enhanced_forecast", "marine"]


# ---------------------------------------------------------------------------
# registered_spot_ids(): "currently registered for LINE notifications"
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _reset_registered_spots_cache():
    omp._registered_spots_cache["ids"] = None
    omp._registered_spots_cache["expires_at"] = 0.0
    yield
    omp._registered_spots_cache["ids"] = None
    omp._registered_spots_cache["expires_at"] = 0.0


def test_registered_spot_ids_unions_all_subscriptions(monkeypatch):
    subs = {
        "user:U1": {"spots": ["H_1631_1434", "H_2088_1443"]},
        "user:U2": {"spots": ["H_2088_1443", "H_9999_0001"]},
        "user:U3": {"notify_enabled": False},  # no 'spots' key at all
    }
    monkeypatch.setattr(omp, "redis_get_json", lambda key, requests_module=None: subs)

    ids = omp.registered_spot_ids()

    assert ids == {"H_1631_1434", "H_2088_1443", "H_9999_0001"}


def test_registered_spot_ids_empty_when_redis_unavailable(monkeypatch):
    monkeypatch.setattr(omp, "redis_get_json", lambda key, requests_module=None: None)
    assert omp.registered_spot_ids() == set()


def test_registered_spot_ids_is_cached_between_calls(monkeypatch):
    calls = []

    def fake_redis_get(key, requests_module=None):
        calls.append(1)
        return {"user:U1": {"spots": ["H_1631_1434"]}}

    monkeypatch.setattr(omp, "redis_get_json", fake_redis_get)

    now = 1000.0
    first = omp.registered_spot_ids(now=now)
    second = omp.registered_spot_ids(now=now + 60)  # within the 5-minute TTL

    assert first == second == {"H_1631_1434"}
    assert len(calls) == 1  # second call served from the in-process cache


def test_registered_spot_ids_refetches_after_ttl_expires(monkeypatch):
    calls = []

    def fake_redis_get(key, requests_module=None):
        calls.append(1)
        return {"user:U1": {"spots": ["H_1631_1434"]}}

    monkeypatch.setattr(omp, "redis_get_json", fake_redis_get)

    now = 1000.0
    omp.registered_spot_ids(now=now)
    omp.registered_spot_ids(now=now + omp._REGISTERED_SPOTS_CACHE_TTL_SECONDS + 1)

    assert len(calls) == 2


# ---------------------------------------------------------------------------
# line_integration._line_web_forecast_enabled(): registered-spot coverage
# ---------------------------------------------------------------------------

def test_line_web_forecast_enabled_passes_static_canary_spot(monkeypatch):
    monkeypatch.setenv("LINE_WEB_FORECAST_ENABLED", "true")
    monkeypatch.setenv("LINE_WEB_FORECAST_CANARY_SPOT_IDS", "H_2088_1443")
    monkeypatch.setattr(li, "registered_spot_ids", lambda: set())
    assert li._line_web_forecast_enabled("line", spot_id="H_2088_1443") is True
    assert li._line_web_forecast_enabled("line", spot_id="H_NOT_LISTED") is False


def test_line_web_forecast_enabled_also_passes_registered_spots(monkeypatch):
    monkeypatch.setenv("LINE_WEB_FORECAST_ENABLED", "true")
    monkeypatch.setenv("LINE_WEB_FORECAST_CANARY_SPOT_IDS", "H_2088_1443")
    monkeypatch.setattr(li, "registered_spot_ids", lambda: {"H_1631_1434"})

    assert li._line_web_forecast_enabled("line", spot_id="H_1631_1434") is True
    assert li._line_web_forecast_enabled("line", spot_id="H_NOT_REGISTERED") is False


def test_line_web_forecast_enabled_empty_canary_list_means_full_rollout(monkeypatch):
    monkeypatch.setenv("LINE_WEB_FORECAST_ENABLED", "true")
    monkeypatch.delenv("LINE_WEB_FORECAST_CANARY_SPOT_IDS", raising=False)
    monkeypatch.setattr(li, "registered_spot_ids", lambda: set())
    assert li._line_web_forecast_enabled("line", spot_id="H_ANY_SPOT") is True


def test_line_web_forecast_enabled_false_for_non_line_source(monkeypatch):
    monkeypatch.setenv("LINE_WEB_FORECAST_ENABLED", "true")
    monkeypatch.setenv("LINE_WEB_FORECAST_CANARY_SPOT_IDS", "H_2088_1443")
    monkeypatch.setattr(li, "registered_spot_ids", lambda: {"H_1631_1434"})
    assert li._line_web_forecast_enabled("web", spot_id="H_1631_1434") is False


# ---------------------------------------------------------------------------
# 2026-08-04: island-distribution 49-point grid prefetch
# (build_rishiri_grid / field_grid_request / validate_field_grid_response /
# load_field_grid_prefetch)
# ---------------------------------------------------------------------------

def sample_field_grid_point(hourly_vars=None):
    """One grid point's raw Open-Meteo response, matching field_grid_request()'s
    hourly variable list and FIELD_GRID_FORECAST_DAYS (8 days, no `daily` key)."""
    vars_ = hourly_vars or omp._split_vars(omp.FIELD_GRID_HOURLY_VARS)
    hours = []
    for day in range(omp.FIELD_GRID_FORECAST_DAYS):
        for h in range(24):
            hours.append(f"2026-08-{day + 1:02d}T{h:02d}:00")
    n = len(hours)
    return {"hourly": {"time": hours, **{var: [1.0] * n for var in vars_}}}


def sample_field_grid_response(n_points=None):
    n_points = n_points or len(omp.build_rishiri_grid())
    return [sample_field_grid_point() for _ in range(n_points)]


def test_build_rishiri_grid_has_49_points_including_summit():
    grid = omp.build_rishiri_grid()
    assert len(grid) == 49
    assert grid[0]["label"] == "利尻山頂"
    assert grid[0]["lat"] == omp.SUMMIT_LAT
    assert grid[0]["lon"] == omp.SUMMIT_LON
    # 24 inner-ring + 24 outer-ring, remaining labels all present
    assert sum(1 for g in grid if g["label"].startswith("内")) == 24
    assert sum(1 for g in grid if g["label"].startswith("外")) == 24


def test_field_grid_request_is_deterministic():
    """The grid is fixed, so two independent calls must produce the exact
    same identity/redis_key -- critical since GitHub Actions (writer) and
    Render (reader) build this request independently."""
    req1 = omp.field_grid_request()
    req2 = omp.field_grid_request()
    assert req1.identity == req2.identity
    assert req1.redis_key == req2.redis_key
    assert req1.api_type == "field_grid"


def test_field_grid_request_url_has_comma_separated_coordinates_for_all_points():
    req = omp.field_grid_request()
    grid = omp.build_rishiri_grid()
    lat_param = req.params["latitude"]
    lon_param = req.params["longitude"]
    assert len(lat_param.split(",")) == len(grid)
    assert len(lon_param.split(",")) == len(grid)
    assert f"{omp.SUMMIT_LAT:.4f}" in lat_param.split(",")


def test_validate_field_grid_response_accepts_well_formed_array():
    data = sample_field_grid_response()
    ok, reason = omp.validate_field_grid_response(data, expected_points=len(omp.build_rishiri_grid()))
    assert ok is True
    assert reason == "ok"


def test_validate_field_grid_response_rejects_non_array():
    ok, reason = omp.validate_field_grid_response({"hourly": {}}, expected_points=49)
    assert ok is False
    assert reason == "not_json_array"


def test_validate_field_grid_response_rejects_wrong_point_count():
    data = sample_field_grid_response(n_points=10)
    ok, reason = omp.validate_field_grid_response(data, expected_points=49)
    assert ok is False
    assert reason == "point_count_mismatch"


def test_validate_field_grid_response_rejects_bad_point():
    data = sample_field_grid_response(n_points=3)
    data[1]["hourly"]["temperature_2m"] = [1.0]  # length mismatch vs "time"
    ok, reason = omp.validate_field_grid_response(data, expected_points=3)
    assert ok is False
    assert reason.startswith("point_1:")


def test_load_field_grid_prefetch_fresh_hit(monkeypatch):
    req = omp.field_grid_request()
    data = sample_field_grid_response()
    record = omp.make_prefetch_record(req, data)
    monkeypatch.setattr(omp, "redis_get_json", lambda key, requests_module=None: record)

    now = datetime.now(timezone.utc)
    loaded, meta = omp.load_field_grid_prefetch(req, now=now)

    assert loaded == data
    assert meta["prefetched"] is True
    assert meta["stale"] is False


def test_load_field_grid_prefetch_stale_hit_within_window(monkeypatch):
    req = omp.field_grid_request()
    data = sample_field_grid_response()
    fetched_at = datetime.now(timezone.utc) - timedelta(hours=2)
    record = omp.make_prefetch_record(req, data, fetched_at=fetched_at)
    monkeypatch.setattr(omp, "redis_get_json", lambda key, requests_module=None: record)

    loaded, meta = omp.load_field_grid_prefetch(req, now=datetime.now(timezone.utc))

    assert loaded == data
    assert meta["stale"] is True


def test_load_field_grid_prefetch_expired_beyond_stale_window(monkeypatch):
    req = omp.field_grid_request()
    data = sample_field_grid_response()
    fetched_at = datetime.now(timezone.utc) - timedelta(hours=13)
    record = omp.make_prefetch_record(req, data, fetched_at=fetched_at)
    monkeypatch.setattr(omp, "redis_get_json", lambda key, requests_module=None: record)

    loaded, meta = omp.load_field_grid_prefetch(req, now=datetime.now(timezone.utc))

    assert loaded is None
    assert meta["reason"] == "stale_expired"


def test_load_field_grid_prefetch_rejects_fingerprint_mismatch(monkeypatch):
    req = omp.field_grid_request()
    record = omp.make_prefetch_record(req, sample_field_grid_response())
    record["request_fingerprint"] = "wrong"
    monkeypatch.setattr(omp, "redis_get_json", lambda key, requests_module=None: record)

    loaded, meta = omp.load_field_grid_prefetch(req)

    assert loaded is None
    assert meta["reason"] == "fingerprint_mismatch"


def test_load_field_grid_prefetch_rejects_malformed_data(monkeypatch):
    req = omp.field_grid_request()
    record = omp.make_prefetch_record(req, {"not": "an array"})
    monkeypatch.setattr(omp, "redis_get_json", lambda key, requests_module=None: record)

    loaded, meta = omp.load_field_grid_prefetch(req)

    assert loaded is None
    assert meta["reason"] == "not_json_array"
