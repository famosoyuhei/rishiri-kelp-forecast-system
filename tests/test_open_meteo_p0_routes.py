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
