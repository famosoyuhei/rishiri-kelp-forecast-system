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


def test_field_multi_stops_remaining_points_on_429(monkeypatch):
    calls = []

    def fake_guarded_get(url, **kwargs):
        calls.append(url)
        if len(calls) == 3:
            raise _rate_limited("field")
        resp = MagicMock(status_code=200)
        resp.raise_for_status.return_value = None
        resp.json.return_value = {"hourly": {"time": []}}
        return resp

    monkeypatch.setattr(start, "guarded_get", fake_guarded_get)

    with pytest.raises(OpenMeteoRateLimitError):
        start._fetch_open_meteo_multi(
            [45.1, 45.2, 45.3, 45.4],
            [141.1, 141.2, 141.3, 141.4],
            ["temperature_2m"],
        )

    assert len(calls) == 3


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
    csv_path = tmp_path / "spots.csv"
    csv_path.write_text("name,lat,lon\nA,45.1,141.1\nB,45.2,141.2\n", encoding="utf-8")
    monkeypatch.setattr(start, "CSV_FILE", str(csv_path))
    monkeypatch.setattr(start, "ensure_request_allowed", lambda *a, **k: None)
    monkeypatch.setattr(start, "_obs_redis_mget", lambda keys: {})
    monkeypatch.setattr(start, "_obs_redis_mset", lambda values: len(values))

    import line_integration

    calls = []

    def fake_forecast(lat, lon, timeout=15, source="history"):
        calls.append((lat, lon, source))
        raise _rate_limited("history")

    monkeypatch.setattr(line_integration, "get_forecast_for_spot", fake_forecast)

    result = start._save_daily_forecast_snapshot()

    assert len(calls) == 1
    assert result["status"] == "rate_limited"
    assert result["processed_spots"] == 0
    assert result["aborted_spots"] == 2


def test_field_multi_paces_requests_between_successful_fetches(monkeypatch):
    """
    2026-08-04: this loop made up to 49 consecutive Open-Meteo requests with
    no delay at all between successful fetches (unlike the 334-spot history
    snapshot batch, which already paced itself) -- a burst pattern that can
    plausibly trigger Open-Meteo's rate limiting on its own, and this runs on
    every /api/analysis/field request, not just once a day. Verifies a sleep
    now happens between each pair of successful requests (N-1 sleeps for N
    points), and none after the last one.
    """
    import time as real_time

    sleeps = []
    monkeypatch.setattr(real_time, "sleep", lambda s: sleeps.append(s))

    def fake_guarded_get(url, **kwargs):
        resp = MagicMock(status_code=200)
        resp.raise_for_status.return_value = None
        resp.json.return_value = {"hourly": {"time": []}}
        return resp

    monkeypatch.setattr(start, "guarded_get", fake_guarded_get)

    result = start._fetch_open_meteo_multi(
        [45.1, 45.2, 45.3],
        [141.1, 141.2, 141.3],
        ["temperature_2m"],
    )

    assert len(result) == 3
    assert sleeps == [0.3, 0.3]  # N-1 sleeps for 3 points, none trailing after the last


def test_feature_flag_off_keeps_field_parallel_path(monkeypatch):
    monkeypatch.setenv("OPEN_METEO_CIRCUIT_BREAKER_ENABLED", "false")
    calls = []

    def fake_get(url, timeout=15):
        calls.append(url)
        resp = MagicMock(status_code=200)
        resp.raise_for_status.return_value = None
        resp.json.return_value = {"hourly": {"time": []}}
        return resp

    monkeypatch.setattr(start.requests, "get", fake_get)
    result = start._fetch_open_meteo_multi([45.1, 45.2], [141.1, 141.2], ["temperature_2m"])

    assert len(result) == 2
    assert len(calls) == 2
