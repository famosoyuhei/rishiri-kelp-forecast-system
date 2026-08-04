"""
Tests for start.py's prefetch-first Open-Meteo loading in get_forecast(),
added so the LINE-corrected (foehn/terrain) canary spot keeps serving
forecasts even if the Open-Meteo 429 situation on Render's egress IP never
clears.

Covers:
  - _enhanced_prefetch_enabled(): off by default, canary-allowlist gated
  - _load_enhanced_prefetch_bundle(): requires a statically-seeded elevation
    plus all three prefetch entries (enhanced forecast, summit, marine SST);
    returns None (safe fallback to the live path) otherwise
  - get_forecast(): non-canary spots and flag-disabled requests take the
    exact same live Open-Meteo path as before this feature existed
    (regression guard — zero behavior change for ordinary web-app users)
  - get_forecast(): a canary + full-prefetch-hit request produces the same
    foehn-corrected score as an equivalent live fetch given identical data,
    while making zero live Open-Meteo calls

Run from project root:
    python -m pytest tests/test_forecast_prefetch.py -v
"""
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

# Import start.py exactly once, here, before any test's monkeypatched env vars
# could be active (see tests/test_field_cache.py for the full rationale —
# Flask-Limiter reads UPSTASH_REDIS_REST_URL at module import time).
import start  # noqa: E402
import open_meteo_prefetch as omp  # noqa: E402


CANARY_SPOT_ID = "H_2088_1443"
CANARY_LAT = 45.2088707
CANARY_LON = 141.1443995
CANARY_ELEVATION_M = 26.0


def _hourly_time_series():
    days = [f"2026-07-{i + 1:02d}" for i in range(7)]
    hours = []
    for day in days:
        for h in range(24):
            hours.append(f"{day}T{h:02d}:00")
    return days, hours


def sample_enhanced_forecast_data():
    days, hours = _hourly_time_series()
    n = len(hours)
    hourly = {var: [0.0] * n for var in omp._split_vars(omp.ENHANCED_HOURLY_VARS)}
    hourly["time"] = hours
    # Give the fields the scoring/foehn path actually reads sane, non-zero values.
    hourly["temperature_2m"] = [12.0] * n
    hourly["relative_humidity_2m"] = [70.0] * n
    hourly["wind_speed_10m"] = [14.4] * n  # km/h -> 4 m/s after conversion
    hourly["wind_direction_10m"] = [250.0] * n
    hourly["cloud_cover"] = [30.0] * n
    hourly["shortwave_radiation"] = [400.0] * n
    hourly["direct_radiation"] = [350.0] * n
    hourly["pressure_msl"] = [1013.0] * n
    hourly["precipitation"] = [0.0] * n
    hourly["precipitation_probability"] = [5.0] * n
    hourly["cape"] = [100.0] * n
    hourly["dewpoint_2m"] = [8.0] * n
    hourly["surface_pressure"] = [1010.0] * n
    for suffix in ("700hPa", "850hPa"):
        hourly[f"temperature_{suffix}"] = [2.0] * n
        hourly[f"relative_humidity_{suffix}"] = [60.0] * n
        hourly[f"wind_speed_{suffix}"] = [30.0] * n
        hourly[f"wind_direction_{suffix}"] = [250.0] * n
    return {
        "daily": {
            "time": days,
            "temperature_2m_max": [18.0] * 7,
            "temperature_2m_min": [10.0] * 7,
            "wind_speed_10m_max": [14.4] * 7,
            "relative_humidity_2m_mean": [70.0] * 7,
            "precipitation_sum": [0.0] * 7,
            "precipitation_probability_max": [5] * 7,
        },
        "hourly": hourly,
    }


def sample_summit_hourly():
    _, hours = _hourly_time_series()
    return {"time": hours, "temperature_2m": [5.0] * len(hours)}


def sample_sst_list():
    return [16.0] * 7


def sample_sst_hourly():
    # 2026-08-04: sea_surface_temperature is hourly-only in the Marine API
    # (daily errors 400 in production -- see MARINE_HOURLY_VARS comment in
    # open_meteo_prefetch.py). A constant value across all hours means the
    # daily average _load_enhanced_prefetch_bundle() computes still equals
    # sample_sst_list() exactly, so existing assertions don't need to change.
    _, hours = _hourly_time_series()
    return {"time": hours, "sea_surface_temperature": [16.0] * len(hours)}


def fake_guarded_get_response(data):
    resp = MagicMock()
    resp.raise_for_status.return_value = None
    resp.json.return_value = data
    return resp


def call_get_forecast(lat, lon, name=None):
    query = {"lat": str(lat), "lon": str(lon)}
    if name:
        query["name"] = name
    with start.app.test_request_context("/api/forecast", query_string=query):
        return start.get_forecast()


@pytest.fixture(autouse=True)
def _isolate_elevation_cache():
    start._elevation_cache.clear()
    start._canary_elevation_seeded = False
    omp._registered_spots_cache["ids"] = None
    omp._registered_spots_cache["expires_at"] = 0.0
    yield
    start._elevation_cache.clear()
    start._canary_elevation_seeded = False
    omp._registered_spots_cache["ids"] = None
    omp._registered_spots_cache["expires_at"] = 0.0


# ---------------------------------------------------------------------------
# _enhanced_prefetch_enabled()
# ---------------------------------------------------------------------------

def test_enhanced_prefetch_disabled_by_default(monkeypatch):
    monkeypatch.delenv("OPEN_METEO_ENHANCED_PREFETCH_ENABLED", raising=False)
    monkeypatch.setenv("LINE_WEB_FORECAST_CANARY_SPOT_IDS", CANARY_SPOT_ID)
    assert start._enhanced_prefetch_enabled(CANARY_SPOT_ID) is False


def test_enhanced_prefetch_requires_canary_membership(monkeypatch):
    monkeypatch.setenv("OPEN_METEO_ENHANCED_PREFETCH_ENABLED", "true")
    monkeypatch.setenv("LINE_WEB_FORECAST_CANARY_SPOT_IDS", CANARY_SPOT_ID)
    monkeypatch.setattr(omp, "registered_spot_ids", lambda: set())
    assert start._enhanced_prefetch_enabled(CANARY_SPOT_ID) is True
    assert start._enhanced_prefetch_enabled("H_9999_9999") is False
    assert start._enhanced_prefetch_enabled("") is False


def test_enhanced_prefetch_also_covers_registered_spots_not_on_static_list(monkeypatch):
    # At least the spots currently registered for LINE notifications must be
    # covered, without needing a manual LINE_WEB_FORECAST_CANARY_SPOT_IDS
    # update per registration.
    monkeypatch.setenv("OPEN_METEO_ENHANCED_PREFETCH_ENABLED", "true")
    monkeypatch.setenv("LINE_WEB_FORECAST_CANARY_SPOT_IDS", CANARY_SPOT_ID)
    monkeypatch.setattr(omp, "registered_spot_ids", lambda: {"H_1631_1434", "H_9999_0001"})

    assert start._enhanced_prefetch_enabled("H_1631_1434") is True
    assert start._enhanced_prefetch_enabled("H_9999_0001") is True
    assert start._enhanced_prefetch_enabled("H_NOT_REGISTERED") is False


# ---------------------------------------------------------------------------
# _load_enhanced_prefetch_bundle()
# ---------------------------------------------------------------------------

def test_bundle_uses_approximate_elevation_without_manual_entry(monkeypatch):
    # A spot with no manually-verified CANARY_SPOT_ELEVATIONS_M entry (e.g. a
    # newly-registered LINE spot) must still get full prefetch coverage —
    # elevation falls back to a network-free approximation rather than
    # bailing out, so registered_spot_ids() coverage isn't quietly gutted by
    # a missing elevation entry.
    monkeypatch.setattr(omp, "CANARY_SPOT_ELEVATIONS_M", {})

    seen_elevations = []

    def fake_load_prefetch(req, **kwargs):
        if req.api_type == "enhanced_forecast":
            seen_elevations.append(float(req.params["elevation"]))
            return sample_enhanced_forecast_data(), {"fetched_at": "2026-07-26T00:00:00Z"}
        if req.api_type == "summit_forecast":
            return {"hourly": sample_summit_hourly()}, {"fetched_at": "2026-07-26T00:00:00Z"}
        return {"hourly": sample_sst_hourly()}, {"fetched_at": "2026-07-26T00:00:00Z"}

    monkeypatch.setattr(omp, "load_prefetch", fake_load_prefetch)

    bundle = start._load_enhanced_prefetch_bundle(CANARY_LAT, CANARY_LON)

    assert bundle is not None
    assert bundle["elevation"] == start._approximate_elevation_no_network(CANARY_LAT, CANARY_LON)
    assert seen_elevations == [bundle["elevation"]]


def test_bundle_returns_none_when_any_prefetch_entry_missing(monkeypatch):
    monkeypatch.setattr(omp, "CANARY_SPOT_ELEVATIONS_M", {CANARY_SPOT_ID: CANARY_ELEVATION_M})

    def fake_load_prefetch(req, **kwargs):
        if req.api_type == "marine":
            return None, {"reason": "miss"}
        if req.api_type == "enhanced_forecast":
            return sample_enhanced_forecast_data(), {"fetched_at": "2026-07-26T00:00:00Z"}
        return {"time": [], "temperature_2m": []}, {"fetched_at": "2026-07-26T00:00:00Z"}

    monkeypatch.setattr(omp, "load_prefetch", fake_load_prefetch)

    assert start._load_enhanced_prefetch_bundle(CANARY_LAT, CANARY_LON) is None


def test_bundle_full_hit_assembles_all_pieces(monkeypatch):
    monkeypatch.setattr(omp, "CANARY_SPOT_ELEVATIONS_M", {CANARY_SPOT_ID: CANARY_ELEVATION_M})

    enhanced_data = sample_enhanced_forecast_data()
    summit_hourly = sample_summit_hourly()
    marine_hourly = sample_sst_hourly()

    def fake_load_prefetch(req, **kwargs):
        if req.api_type == "enhanced_forecast":
            return enhanced_data, {"fetched_at": "2026-07-26T00:00:00Z"}
        if req.api_type == "summit_forecast":
            return {"hourly": summit_hourly}, {"fetched_at": "2026-07-26T00:00:00Z"}
        if req.api_type == "marine":
            return {"hourly": marine_hourly}, {"fetched_at": "2026-07-26T00:00:00Z"}
        raise AssertionError(f"unexpected api_type {req.api_type}")

    monkeypatch.setattr(omp, "load_prefetch", fake_load_prefetch)

    bundle = start._load_enhanced_prefetch_bundle(CANARY_LAT, CANARY_LON)

    assert bundle is not None
    assert bundle["elevation"] == CANARY_ELEVATION_M
    assert bundle["forecast_data"] == enhanced_data
    assert bundle["summit_forecast"]["temperature_2m"] == summit_hourly["temperature_2m"]
    assert bundle["sst_list"] == sample_sst_list()


# ---------------------------------------------------------------------------
# get_forecast(): regression guard — non-canary / flag-disabled unaffected
# ---------------------------------------------------------------------------

def test_get_forecast_non_canary_spot_never_attempts_prefetch(monkeypatch):
    monkeypatch.setenv("OPEN_METEO_ENHANCED_PREFETCH_ENABLED", "true")
    monkeypatch.setenv("LINE_WEB_FORECAST_CANARY_SPOT_IDS", CANARY_SPOT_ID)
    monkeypatch.setattr(start, "_save_forecast_history", MagicMock())

    bundle_calls = []
    monkeypatch.setattr(
        start, "_load_enhanced_prefetch_bundle",
        lambda *a, **kw: bundle_calls.append(1) or None,
    )
    ensure_mock = MagicMock()
    monkeypatch.setattr(start, "ensure_request_allowed", ensure_mock)
    monkeypatch.setattr(start, "get_elevation", MagicMock(return_value=20.0))
    summit_mock = MagicMock(return_value=sample_summit_hourly())
    monkeypatch.setattr(start, "_get_summit_hourly_temps", summit_mock)
    guarded_mock = MagicMock(return_value=fake_guarded_get_response(sample_enhanced_forecast_data()))
    monkeypatch.setattr(start, "guarded_get", guarded_mock)
    sst_mock = MagicMock(return_value=sample_sst_list())
    monkeypatch.setattr(start, "get_sea_surface_temperature", sst_mock)

    result = call_get_forecast(45.30, 141.30, name="H_NOT_CANARY")

    assert bundle_calls == [], "prefetch bundle must never be attempted for a non-canary spot"
    ensure_mock.assert_called_once()
    guarded_mock.assert_called_once()
    sst_mock.assert_called_once()
    summit_mock.assert_called_once()
    assert result["status"] == "success"


def test_get_forecast_canary_spot_unaffected_when_flag_disabled(monkeypatch):
    monkeypatch.delenv("OPEN_METEO_ENHANCED_PREFETCH_ENABLED", raising=False)
    monkeypatch.setenv("LINE_WEB_FORECAST_CANARY_SPOT_IDS", CANARY_SPOT_ID)
    monkeypatch.setattr(start, "_save_forecast_history", MagicMock())

    bundle_calls = []
    monkeypatch.setattr(
        start, "_load_enhanced_prefetch_bundle",
        lambda *a, **kw: bundle_calls.append(1) or None,
    )
    monkeypatch.setattr(start, "ensure_request_allowed", MagicMock())
    monkeypatch.setattr(start, "get_elevation", MagicMock(return_value=CANARY_ELEVATION_M))
    monkeypatch.setattr(start, "_get_summit_hourly_temps", MagicMock(return_value=sample_summit_hourly()))
    monkeypatch.setattr(
        start, "guarded_get",
        MagicMock(return_value=fake_guarded_get_response(sample_enhanced_forecast_data())),
    )
    monkeypatch.setattr(start, "get_sea_surface_temperature", MagicMock(return_value=sample_sst_list()))

    result = call_get_forecast(CANARY_LAT, CANARY_LON, name=CANARY_SPOT_ID)

    assert bundle_calls == [], "prefetch bundle must not be attempted while the feature flag is off"
    assert result["status"] == "success"


# ---------------------------------------------------------------------------
# get_forecast(): canary + prefetch hit matches an equivalent live fetch
# ---------------------------------------------------------------------------

def test_canary_prefetch_hit_matches_equivalent_live_fetch_with_zero_live_calls(monkeypatch):
    monkeypatch.setattr(start, "_save_forecast_history", MagicMock())
    monkeypatch.setenv("LINE_WEB_FORECAST_CANARY_SPOT_IDS", CANARY_SPOT_ID)

    forecast_data = sample_enhanced_forecast_data()
    summit_hourly = sample_summit_hourly()
    sst_list = sample_sst_list()

    # --- live path (flag disabled): identical fixture data, via the normal
    #     ensure_request_allowed / guarded_get / get_sea_surface_temperature /
    #     _get_summit_hourly_temps call sites. ---
    monkeypatch.delenv("OPEN_METEO_ENHANCED_PREFETCH_ENABLED", raising=False)
    monkeypatch.setattr(start, "ensure_request_allowed", MagicMock())
    monkeypatch.setattr(start, "get_elevation", MagicMock(return_value=CANARY_ELEVATION_M))
    monkeypatch.setattr(start, "_get_summit_hourly_temps", MagicMock(return_value=summit_hourly))
    monkeypatch.setattr(start, "guarded_get", MagicMock(return_value=fake_guarded_get_response(forecast_data)))
    monkeypatch.setattr(start, "get_sea_surface_temperature", MagicMock(return_value=sst_list))

    live_result = call_get_forecast(CANARY_LAT, CANARY_LON, name=CANARY_SPOT_ID)
    assert live_result["status"] == "success", live_result

    # --- canary + prefetch path: same fixture data, delivered entirely via
    #     _load_enhanced_prefetch_bundle(). Every live Open-Meteo call site is
    #     replaced with an assertion-raiser — if the prefetch path ever falls
    #     through to a live call, the test fails loudly. ---
    monkeypatch.setenv("OPEN_METEO_ENHANCED_PREFETCH_ENABLED", "true")
    bundle = {
        "elevation": CANARY_ELEVATION_M,
        "forecast_data": forecast_data,
        "summit_forecast": summit_hourly,
        "sst_list": sst_list,
        "fetched_at": datetime(2026, 7, 26, tzinfo=timezone.utc),
    }
    monkeypatch.setattr(start, "_load_enhanced_prefetch_bundle", MagicMock(return_value=bundle))
    forbidden = MagicMock(side_effect=AssertionError("must not hit live Open-Meteo path when prefetch bundle is used"))
    monkeypatch.setattr(start, "ensure_request_allowed", forbidden)
    monkeypatch.setattr(start, "guarded_get", forbidden)
    monkeypatch.setattr(start, "get_sea_surface_temperature", forbidden)
    monkeypatch.setattr(start, "_get_summit_hourly_temps", forbidden)

    prefetch_result = call_get_forecast(CANARY_LAT, CANARY_LON, name=CANARY_SPOT_ID)
    assert prefetch_result["status"] == "success", prefetch_result

    def day_scores(result):
        return [
            (day["daily_summary"]["drying_score"], day["daily_summary"]["foehn_bonus"])
            for day in result["forecasts"]
        ]

    assert day_scores(prefetch_result) == day_scores(live_result)
