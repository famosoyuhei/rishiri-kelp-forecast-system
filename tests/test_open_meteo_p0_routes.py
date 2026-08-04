from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

import start
from open_meteo_guard import OpenMeteoCircuitOpenError, OpenMeteoRateLimitError


@pytest.fixture(autouse=True)
def enable_guard(monkeypatch):
    monkeypatch.setenv("OPEN_METEO_CIRCUIT_BREAKER_ENABLED", "true")
    yield


def _rate_limited(source="field"):
    return OpenMeteoRateLimitError(
        http_status=429,
        retry_after_raw=None,
        retry_after_at="2026-07-26T00:30:00Z",
        source=source,
        occurred_at="2026-07-26T00:00:00Z",
        body_excerpt="",
        consecutive_429_count=1,
    )


def test_field_multi_propagates_rate_limit_error(monkeypatch):
    """
    2026-08-04: _fetch_open_meteo_multi() was redesigned to issue a single
    batched request (comma-separated lat/lon, mirroring
    _fetch_elevations_batch()) instead of up to 49 individual requests, so
    there is no longer a "some points already succeeded" partial state --
    a 429 on the one request must simply propagate.
    """
    calls = []

    def fake_guarded_get(url, **kwargs):
        calls.append(url)
        raise _rate_limited("field")

    monkeypatch.setattr(start, "guarded_get", fake_guarded_get)

    with pytest.raises(OpenMeteoRateLimitError):
        start._fetch_open_meteo_multi(
            [45.1, 45.2, 45.3, 45.4],
            [141.1, 141.2, 141.3, 141.4],
            ["temperature_2m"],
        )

    assert len(calls) == 1


def test_forecast_route_circuit_open_skips_open_meteo(monkeypatch):
    client = start.app.test_client()
    monkeypatch.setattr(
        start,
        "ensure_request_allowed",
        MagicMock(side_effect=OpenMeteoCircuitOpenError("forecast", "2026-07-26T00:30:00Z")),
    )
    guarded = MagicMock()
    monkeypatch.setattr(start, "guarded_get", guarded)

    resp = client.get("/api/forecast?lat=45.1&lon=141.1")

    assert resp.status_code == 503
    guarded.assert_not_called()


def test_forecast_route_success_shape_is_unchanged(monkeypatch):
    client = start.app.test_client()
    monkeypatch.setattr(start, "ensure_request_allowed", lambda *a, **k: None)
    monkeypatch.setattr(start, "get_elevation", lambda *a, **k: 0.0)
    monkeypatch.setattr(start, "_get_summit_hourly_temps", lambda *a, **k: None)
    monkeypatch.setattr(start, "get_sea_surface_temperature", lambda *a, **k: [None] * 7)
    monkeypatch.setattr(start, "_save_forecast_history", lambda *a, **k: None)

    times = []
    for day in range(7):
        date = f"2026-07-{day + 1:02d}"
        for hour in range(24):
            times.append(f"{date}T{hour:02d}:00")

    hourly = {
        "time": times,
        "temperature_2m": [15.0] * len(times),
        "relative_humidity_2m": [70.0] * len(times),
        "wind_speed_10m": [14.4] * len(times),
        "wind_direction_10m": [270.0] * len(times),
        "cloud_cover": [20.0] * len(times),
        "shortwave_radiation": [300.0] * len(times),
        "direct_radiation": [300.0] * len(times),
        "pressure_msl": [1010.0] * len(times),
        "precipitation": [0.0] * len(times),
        "precipitation_probability": [0.0] * len(times),
        "cape": [0.0] * len(times),
        "temperature_700hPa": [0.0] * len(times),
        "relative_humidity_700hPa": [50.0] * len(times),
        "wind_speed_700hPa": [10.0] * len(times),
        "wind_direction_700hPa": [270.0] * len(times),
        "temperature_850hPa": [5.0] * len(times),
        "relative_humidity_850hPa": [60.0] * len(times),
        "wind_speed_850hPa": [10.0] * len(times),
        "wind_direction_850hPa": [270.0] * len(times),
        "dewpoint_2m": [5.0] * len(times),
        "surface_pressure": [1010.0] * len(times),
    }
    daily = {
        "time": [f"2026-07-{day + 1:02d}" for day in range(7)],
        "temperature_2m_max": [18.0] * 7,
        "temperature_2m_min": [10.0] * 7,
        "wind_speed_10m_max": [14.4] * 7,
        "relative_humidity_2m_mean": [70.0] * 7,
        "precipitation_sum": [0.0] * 7,
        "precipitation_probability_max": [0.0] * 7,
    }
    forecast_resp = MagicMock(status_code=200)
    forecast_resp.raise_for_status.return_value = None
    forecast_resp.json.return_value = {"hourly": hourly, "daily": daily}
    monkeypatch.setattr(start, "guarded_get", MagicMock(return_value=forecast_resp))

    resp = client.get("/api/forecast?lat=45.1&lon=141.1")

    assert resp.status_code == 200
    body = resp.get_json()
    assert body["status"] == "success"
    assert "forecasts" in body
    assert "coordinates" in body


def test_history_snapshot_stops_after_429(tmp_path, monkeypatch):
    """
    2026-08-04: _save_daily_forecast_snapshot() was redesigned to fetch all
    spots via line_integration.get_simple_forecasts_batch() (one batched
    Open-Meteo request per chunk) instead of one request per spot, so a rate
    limit now aborts a whole chunk rather than a single spot -- with both
    spots here comfortably under the default chunk size, the entire 2-spot
    batch is one chunk, and a 429 on it aborts both.
    """
    csv_path = tmp_path / "spots.csv"
    csv_path.write_text("name,lat,lon\nA,45.1,141.1\nB,45.2,141.2\n", encoding="utf-8")
    monkeypatch.setattr(start, "CSV_FILE", str(csv_path))
    monkeypatch.setattr(start, "_obs_redis_mget", lambda keys: {})
    monkeypatch.setattr(start, "_obs_redis_mset", lambda values: len(values))

    import line_integration

    calls = []

    def fake_guarded_get(url, **kwargs):
        calls.append(url)
        raise _rate_limited("history")

    monkeypatch.setattr(line_integration, "guarded_get", fake_guarded_get)

    result = start._save_daily_forecast_snapshot()

    assert len(calls) == 1
    assert result["status"] == "rate_limited"
    assert result["processed_spots"] == 0
    assert result["aborted_spots"] == 2


def test_history_snapshot_batches_all_spots_into_one_request(tmp_path, monkeypatch):
    """The whole point of this redesign: N spots (well under the chunk size)
    now cost exactly 1 Open-Meteo request instead of N."""
    csv_path = tmp_path / "spots.csv"
    csv_path.write_text(
        "name,lat,lon\nA,45.1,141.1\nB,45.2,141.2\nC,45.3,141.3\n", encoding="utf-8"
    )
    monkeypatch.setattr(start, "CSV_FILE", str(csv_path))
    monkeypatch.setattr(start, "_obs_redis_mget", lambda keys: {})
    monkeypatch.setattr(start, "_obs_redis_mset", lambda values: len(values))

    import line_integration

    calls = []
    times = ["2026-08-05", "2026-08-06"]

    def fake_guarded_get(url, **kwargs):
        calls.append(url)
        resp = MagicMock(status_code=200)
        resp.raise_for_status.return_value = None
        resp.json.return_value = [
            {
                "daily": {
                    "time": times,
                    "precipitation_sum": [0.0, 0.0],
                    "wind_speed_10m_max": [10.0, 10.0],
                    "precipitation_probability_max": [0, 0],
                    "temperature_2m_max": [20.0, 20.0],
                    "relative_humidity_2m_mean": [70.0, 70.0],
                },
                "hourly": {
                    "relative_humidity_2m": [70.0] * 48,
                    "wind_speed_10m": [10.0] * 48,
                    "wind_direction_10m": [270.0] * 48,
                    "precipitation": [0.0] * 48,
                },
            }
            for _ in range(3)
        ]
        return resp

    monkeypatch.setattr(line_integration, "guarded_get", fake_guarded_get)

    result = start._save_daily_forecast_snapshot()

    assert len(calls) == 1
    assert "45.10000,45.20000,45.30000" in calls[0]
    assert result["status"] == "ok"
    assert result["processed_spots"] == 3
    assert result["aborted_spots"] == 0
    assert result["errors"] == 0
    assert result["planned_records"] == 6  # 3 spots x 2 forecast days


def test_field_multi_makes_single_batched_request(monkeypatch):
    """
    2026-08-04: verifies the 49-request burst pattern that could plausibly
    trigger Open-Meteo's rate limiting was replaced with exactly one request
    per /api/analysis/field call, using comma-separated lat/lon (the same
    technique _fetch_elevations_batch() already uses for elevation data).
    """
    calls = []

    def fake_guarded_get(url, **kwargs):
        calls.append(url)
        resp = MagicMock(status_code=200)
        resp.raise_for_status.return_value = None
        resp.json.return_value = [
            {"hourly": {"time": []}},
            {"hourly": {"time": []}},
            {"hourly": {"time": []}},
        ]
        return resp

    monkeypatch.setattr(start, "guarded_get", fake_guarded_get)

    result = start._fetch_open_meteo_multi(
        [45.1, 45.2, 45.3],
        [141.1, 141.2, 141.3],
        ["temperature_2m"],
    )

    assert len(result) == 3
    assert len(calls) == 1
    assert "45.1000,45.2000,45.3000" in calls[0]
    assert "141.1000,141.2000,141.3000" in calls[0]


def test_field_multi_pads_response_when_shorter_than_requested(monkeypatch):
    def fake_guarded_get(url, **kwargs):
        resp = MagicMock(status_code=200)
        resp.raise_for_status.return_value = None
        resp.json.return_value = [{"hourly": {"time": []}}]  # only 1 of 2 points returned
        return resp

    monkeypatch.setattr(start, "guarded_get", fake_guarded_get)

    result = start._fetch_open_meteo_multi([45.1, 45.2], [141.1, 141.2], ["temperature_2m"])

    assert len(result) == 2
    assert result[1] == {"hourly": {}}


def test_field_multi_wraps_single_object_response(monkeypatch):
    """Open-Meteo may return a bare object (not a list) for a single point."""

    def fake_guarded_get(url, **kwargs):
        resp = MagicMock(status_code=200)
        resp.raise_for_status.return_value = None
        resp.json.return_value = {"hourly": {"time": ["2026-08-04T00:00"]}}
        return resp

    monkeypatch.setattr(start, "guarded_get", fake_guarded_get)

    result = start._fetch_open_meteo_multi([45.1], [141.1], ["temperature_2m"])

    assert result == [{"hourly": {"time": ["2026-08-04T00:00"]}}]


def test_field_multi_returns_empty_hourly_for_all_points_on_unexpected_failure(monkeypatch):
    def fake_guarded_get(url, **kwargs):
        raise ValueError("boom")

    monkeypatch.setattr(start, "guarded_get", fake_guarded_get)

    result = start._fetch_open_meteo_multi([45.1, 45.2], [141.1, 141.2], ["temperature_2m"])

    assert result == [{"hourly": {}}, {"hourly": {}}]


def test_field_multi_single_request_regardless_of_feature_flag(monkeypatch):
    """
    2026-08-04: the old ThreadPoolExecutor fallback path (used when
    OPEN_METEO_CIRCUIT_BREAKER_ENABLED=false) is gone -- guarded_get() itself
    already bypasses circuit-breaker bookkeeping when the flag is off
    (see open_meteo_guard.guarded_get -> is_enabled()), so this function now
    always issues exactly one batched request either way.
    """
    monkeypatch.setenv("OPEN_METEO_CIRCUIT_BREAKER_ENABLED", "false")
    calls = []

    def fake_get(url, timeout=15):
        calls.append(url)
        resp = MagicMock(status_code=200)
        resp.raise_for_status.return_value = None
        resp.json.return_value = [{"hourly": {"time": []}}, {"hourly": {"time": []}}]
        return resp

    monkeypatch.setattr(start.requests, "get", fake_get)
    result = start._fetch_open_meteo_multi([45.1, 45.2], [141.1, 141.2], ["temperature_2m"])

    assert len(result) == 2
    assert len(calls) == 1


# ---------------------------------------------------------------------------
# 2026-08-04: /api/analysis/field prefetch-first gating (_field_prefetch_allowed
# / _fetch_field_grid_data) -- GitHub-Actions-prefetched 49-point grid as a
# fallback data source when Open-Meteo is rate limited, scoped initially to
# type=score, day=0 per the explicit incremental rollout plan.
# ---------------------------------------------------------------------------

def test_field_prefetch_allowed_false_when_flag_off(monkeypatch):
    monkeypatch.delenv("FIELD_PREFETCH_ENABLED", raising=False)
    assert start._field_prefetch_allowed("score", 0) is False


def test_field_prefetch_allowed_true_for_default_score_day0(monkeypatch):
    monkeypatch.setenv("FIELD_PREFETCH_ENABLED", "true")
    monkeypatch.delenv("FIELD_PREFETCH_TYPES", raising=False)
    monkeypatch.delenv("FIELD_PREFETCH_DAYS", raising=False)
    assert start._field_prefetch_allowed("score", 0) is True


def test_field_prefetch_allowed_false_for_non_allowlisted_type(monkeypatch):
    monkeypatch.setenv("FIELD_PREFETCH_ENABLED", "true")
    monkeypatch.delenv("FIELD_PREFETCH_TYPES", raising=False)
    assert start._field_prefetch_allowed("wind", 0) is False


def test_field_prefetch_allowed_false_for_non_allowlisted_day(monkeypatch):
    monkeypatch.setenv("FIELD_PREFETCH_ENABLED", "true")
    monkeypatch.delenv("FIELD_PREFETCH_DAYS", raising=False)
    assert start._field_prefetch_allowed("score", 3) is False


def test_field_prefetch_allowed_widens_with_env_vars(monkeypatch):
    """The whole point of this design: widening coverage from day=0 to the
    full week (or to more field types) is a pure env var change, no code/
    redeploy of the prefetch data itself needed."""
    monkeypatch.setenv("FIELD_PREFETCH_ENABLED", "true")
    monkeypatch.setenv("FIELD_PREFETCH_TYPES", "score,wind")
    monkeypatch.setenv("FIELD_PREFETCH_DAYS", "0,1,2,3,4,5,6")

    assert start._field_prefetch_allowed("score", 6) is True
    assert start._field_prefetch_allowed("wind", 3) is True
    assert start._field_prefetch_allowed("humidity", 0) is False


def test_fetch_field_grid_data_uses_prefetch_when_allowed_and_hit(monkeypatch):
    monkeypatch.setenv("FIELD_PREFETCH_ENABLED", "true")
    monkeypatch.delenv("FIELD_PREFETCH_TYPES", raising=False)
    monkeypatch.delenv("FIELD_PREFETCH_DAYS", raising=False)

    import open_meteo_prefetch as omp
    prefetched_data = [{"hourly": {"time": ["x"]}}] * 49
    monkeypatch.setattr(omp, "field_grid_request", lambda: MagicMock())
    monkeypatch.setattr(
        omp, "load_field_grid_prefetch",
        lambda req: (prefetched_data, {"age_minutes": 5, "stale": False}),
    )
    live_calls = []
    monkeypatch.setattr(
        start, "_fetch_open_meteo_multi",
        lambda lats, lons, hourly_vars: live_calls.append(1) or [],
    )

    result = start._fetch_field_grid_data("score", 0, [45.1], [141.1], ["temperature_2m"])

    assert result == prefetched_data
    assert live_calls == []  # live path never touched on a prefetch hit


def test_fetch_field_grid_data_falls_back_to_live_on_prefetch_miss(monkeypatch):
    monkeypatch.setenv("FIELD_PREFETCH_ENABLED", "true")
    monkeypatch.delenv("FIELD_PREFETCH_TYPES", raising=False)
    monkeypatch.delenv("FIELD_PREFETCH_DAYS", raising=False)

    import open_meteo_prefetch as omp
    monkeypatch.setattr(omp, "field_grid_request", lambda: MagicMock())
    monkeypatch.setattr(
        omp, "load_field_grid_prefetch",
        lambda req: (None, {"reason": "stale_expired"}),
    )
    live_result = [{"hourly": {"time": ["live"]}}]
    monkeypatch.setattr(
        start, "_fetch_open_meteo_multi",
        lambda lats, lons, hourly_vars: live_result,
    )

    result = start._fetch_field_grid_data("score", 0, [45.1], [141.1], ["temperature_2m"])

    assert result == live_result


def test_fetch_field_grid_data_falls_back_to_live_when_not_allowed(monkeypatch):
    """type/day not in the allowlist (e.g. wind before it's been widened in)
    must behave 100% like the pre-prefetch code -- never even touch the
    prefetch loader."""
    monkeypatch.setenv("FIELD_PREFETCH_ENABLED", "true")
    monkeypatch.delenv("FIELD_PREFETCH_TYPES", raising=False)  # default: score only
    monkeypatch.delenv("FIELD_PREFETCH_DAYS", raising=False)

    import open_meteo_prefetch as omp
    prefetch_calls = []
    monkeypatch.setattr(omp, "field_grid_request", lambda: prefetch_calls.append(1))
    live_result = [{"hourly": {"time": ["live"]}}]
    monkeypatch.setattr(
        start, "_fetch_open_meteo_multi",
        lambda lats, lons, hourly_vars: live_result,
    )

    result = start._fetch_field_grid_data("wind", 0, [45.1], [141.1], ["wind_speed_10m"])

    assert result == live_result
    assert prefetch_calls == []


def test_fetch_field_grid_data_propagates_rate_limit_from_live_fallback(monkeypatch):
    monkeypatch.delenv("FIELD_PREFETCH_ENABLED", raising=False)  # disabled -> straight to live

    def fake_live(lats, lons, hourly_vars):
        raise _rate_limited("field")

    monkeypatch.setattr(start, "_fetch_open_meteo_multi", fake_live)

    with pytest.raises(OpenMeteoRateLimitError):
        start._fetch_field_grid_data("score", 0, [45.1], [141.1], ["temperature_2m"])


# ---------------------------------------------------------------------------
# 2026-08-04 incident fix: _compute_score_field()'s elevation fetch happens
# BEFORE _fetch_field_grid_data()'s weather-grid prefetch, so with the P0
# circuit open, the live elevation call short-circuited the whole function
# before the weather prefetch ever ran -- confirmed live on production
# (/api/analysis/field?type=score&day=0 still 503'd with
# FIELD_PREFETCH_ENABLED=true). _get_field_grid_elevations() closes this gap.
# ---------------------------------------------------------------------------

def test_get_field_grid_elevations_uses_approximation_when_prefetch_allowed(monkeypatch):
    monkeypatch.setenv("FIELD_PREFETCH_ENABLED", "true")
    monkeypatch.delenv("FIELD_PREFETCH_TYPES", raising=False)  # default: score
    monkeypatch.delenv("FIELD_PREFETCH_DAYS", raising=False)   # default: 0

    live_calls = []
    monkeypatch.setattr(
        start, "_fetch_elevations_batch",
        lambda lats, lons, source=None: live_calls.append(1) or [0.0] * len(lats),
    )

    result = start._get_field_grid_elevations("score", 0, [45.1786, 45.2], [141.2419, 141.3])

    assert live_calls == []  # never touches the live Elevation API
    assert len(result) == 2
    assert all(isinstance(v, (int, float)) for v in result)


def test_get_field_grid_elevations_uses_live_batch_when_not_allowed(monkeypatch):
    """type/day not allowlisted (or the flag off, the default) must behave
    100% like the pre-fix code -- still a live elevation batch call."""
    monkeypatch.delenv("FIELD_PREFETCH_ENABLED", raising=False)

    live_calls = []

    def fake_batch(lats, lons, source=None):
        live_calls.append((lats, lons, source))
        return [10.0, 20.0]

    monkeypatch.setattr(start, "_fetch_elevations_batch", fake_batch)

    result = start._get_field_grid_elevations("score", 0, [45.1, 45.2], [141.1, 141.2])

    assert result == [10.0, 20.0]
    assert len(live_calls) == 1
    assert live_calls[0][2] == "field"


def test_get_field_grid_elevations_propagates_circuit_open_when_not_allowed(monkeypatch):
    monkeypatch.delenv("FIELD_PREFETCH_ENABLED", raising=False)

    def fake_batch(lats, lons, source=None):
        raise OpenMeteoCircuitOpenError("field", "2026-08-04T00:29:17Z")

    monkeypatch.setattr(start, "_fetch_elevations_batch", fake_batch)

    with pytest.raises(OpenMeteoCircuitOpenError):
        start._get_field_grid_elevations("score", 0, [45.1], [141.1])


def test_compute_score_field_survives_open_circuit_when_prefetch_hits(monkeypatch):
    """End-to-end: both the elevation short-circuit AND the weather fetch
    must be bypassed for _compute_score_field() to actually succeed while
    the live Open-Meteo circuit is open."""
    monkeypatch.setenv("FIELD_PREFETCH_ENABLED", "true")
    monkeypatch.delenv("FIELD_PREFETCH_TYPES", raising=False)
    monkeypatch.delenv("FIELD_PREFETCH_DAYS", raising=False)

    def circuit_open_batch(lats, lons, source=None):
        raise OpenMeteoCircuitOpenError("field", "2026-08-04T00:29:17Z")

    def circuit_open_multi(lats, lons, hourly_vars):
        raise OpenMeteoCircuitOpenError("field", "2026-08-04T00:29:17Z")

    monkeypatch.setattr(start, "_fetch_elevations_batch", circuit_open_batch)
    monkeypatch.setattr(start, "_fetch_open_meteo_multi", circuit_open_multi)
    monkeypatch.setattr(start, "get_sea_surface_temperature", lambda *a, **k: [None] * 7)
    monkeypatch.setattr(start, "_get_summit_hourly_temps", lambda *a, **k: None)

    grid = start._build_rishiri_grid()
    n = len(grid)
    hours = []
    for day in range(8):
        for h in range(24):
            hours.append(f"2026-08-{day + 1:02d}T{h:02d}:00")
    m = len(hours)
    point = {
        "hourly": {
            "time": hours,
            "temperature_2m": [15.0] * m,
            "relative_humidity_2m": [70.0] * m,
            "wind_speed_10m": [10.0] * m,
            "precipitation": [0.0] * m,
            "precipitation_probability": [0] * m,
            "shortwave_radiation": [300.0] * m,
            "dewpoint_2m": [5.0] * m,
            "cape": [0.0] * m,
            "wind_direction_10m": [270.0] * m,
        }
    }
    prefetched = [point for _ in range(n)]

    import open_meteo_prefetch as omp
    monkeypatch.setattr(omp, "field_grid_request", lambda: MagicMock())
    monkeypatch.setattr(
        omp, "load_field_grid_prefetch",
        lambda req: (prefetched, {"age_minutes": 3, "stale": False}),
    )

    result = start._compute_score_field(0)

    assert "error" not in result
    assert len(result.get("points", [])) == n
