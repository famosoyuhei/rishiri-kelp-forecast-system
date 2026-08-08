"""
Tests for _auto_compare_precip_forecast()'s nowcast-first ground truth
(2026-08-09 fix).

Background: this function verifies each spot's precipitation forecast
against "what actually happened", writing the result to feedback_log.csv.
It used to source "what actually happened" from a single AMEDAS station
(Kutsugata, station 11151) and apply that SAME value to all 334 spots
regardless of where they are on the island. Rishiri is small but the
mountain splits weather systems, so a spot 10km away on the opposite side
of the summit (e.g. H_2480_2198 in Onishibetsu/Kutsugata... actually
Oshidomari) could be marked "forecast was correct" purely because rain
fell at the distant station, even though nothing fell at the spot itself
(confirmed live: 21 of 22 "missed" 2026-07 records for H_2480_2198 were an
artifact of this, verified against the JMA nowcast mesh which already
observes precipitation per-spot).

_record_nowcast_snapshot() already saves per-spot precipitation (JMA
high-res nowcast, 250m mesh) to Redis every 10 minutes during the 04:00-
16:00 drying window. This fix makes _auto_compare_precip_forecast() use
that per-spot data as the primary source, falling back to the AMEDAS
station only for spots whose nowcast coverage for that day is incomplete.

Run from project root:
    python -m pytest tests/test_precip_verification_nowcast.py -v
"""
import json

import pytest

import start


@pytest.fixture
def precip_env(tmp_path, monkeypatch):
    feedback_file = tmp_path / "feedback_log.csv"
    record_file = tmp_path / "hoshiba_records.csv"
    monkeypatch.setattr(start, "FEEDBACK_FILE", str(feedback_file))
    monkeypatch.setattr(start, "RECORD_FILE", str(record_file))
    monkeypatch.setattr(start, "_records_redis_restore", lambda: False)
    monkeypatch.setattr(start, "_feedback_log_redis_restore", lambda: False)
    monkeypatch.setattr(start, "_feedback_log_redis_save", lambda df: True)
    monkeypatch.setattr(start, "_load_spot_metadata_map", lambda: {})
    return feedback_file


FC_ENTRY = {
    "forecast_date": "20260713",
    "target_date": "2026-07-14",
    "day_number": 1,
    "drying_score": 10,
    "suitability": "poor",
    "precipitation_0416": 0.5,
    "precipitation": 0.5,
}


def _mock_redis(monkeypatch, forecast_by_spot: dict, amedas: dict | None):
    """forecast_by_spot: {spot_name: [fc_entry, ...]}. Wires up
    _obs_redis_scan_keys/_obs_redis_get so the forecast-history + AMEDAS
    reads inside _auto_compare_precip_forecast() come from these fixtures
    instead of real Redis."""
    date_str = "20260714"
    scan_keys = [f"forecast:hist:{name}:{date_str}" for name in forecast_by_spot]
    monkeypatch.setattr(start, "_obs_redis_scan_keys", lambda pattern: scan_keys)

    def fake_get(key):
        if key == f"amedas:obs:11151:{date_str}":
            return amedas
        for name, entries in forecast_by_spot.items():
            if key == f"forecast:hist:{name}:{date_str}":
                return entries
        return None

    monkeypatch.setattr(start, "_obs_redis_get", fake_get)


def test_uses_nowcast_when_spot_coverage_is_complete(precip_env, monkeypatch):
    nowcast_row = {
        "spot_name": "H_2480_2198", "coverage_pct": 100.0,
        "observed_rain_0416": False, "observed_precip_sum_0416_mm": 0.0,
        "first_rain_time": None, "last_rain_time": None,
    }
    monkeypatch.setattr(start, "_load_nowcast_daily_summary_rows", lambda date_str: ([nowcast_row], {}))
    # AMEDAS fallback says the opposite (rain) -- must NOT be used since nowcast covers this spot.
    amedas = {
        "hourly": [{"time": "2026-07-14T10:00", "precipitation": 5.0}],
        "daily_summary": {"total_precipitation": 5.0},
    }
    _mock_redis(monkeypatch, {"H_2480_2198": [FC_ENTRY]}, amedas)

    n = start._auto_compare_precip_forecast("20260714")

    assert n == 1
    df = start.pd.read_csv(precip_env)
    row = df.iloc[0]
    assert row["data_source"] == "jma_nowcast_per_spot"
    assert row["actual_rain_0416"] == False  # noqa: E712
    assert row["actual_precip_0416_mm"] == 0.0
    assert row["precip_forecast_correct"] == False  # noqa: E712  forecast said rain (0.5mm), nowcast says none


def test_falls_back_to_amedas_when_spot_missing_from_nowcast(precip_env, monkeypatch):
    # This spot has no complete nowcast row for the day (e.g. background thread gap).
    monkeypatch.setattr(start, "_load_nowcast_daily_summary_rows", lambda date_str: ([], {}))
    amedas = {
        "hourly": [{"time": "2026-07-14T10:00", "precipitation": 2.0}],
        "daily_summary": {"total_precipitation": 3.0},
    }
    _mock_redis(monkeypatch, {"H_1631_1434": [FC_ENTRY]}, amedas)

    n = start._auto_compare_precip_forecast("20260714")

    assert n == 1
    df = start.pd.read_csv(precip_env)
    row = df.iloc[0]
    assert row["data_source"] == "jma_amedas_station"
    assert row["actual_rain_0416"] == True  # noqa: E712
    assert row["actual_precip_0416_mm"] == 2.0
    assert pd_isna(row["actual_rain_first_time_0416"])
    assert pd_isna(row["actual_rain_last_time_0416"])


def pd_isna(v):
    import pandas as pd
    return pd.isna(v)


def test_skips_spot_with_neither_nowcast_nor_amedas(precip_env, monkeypatch):
    monkeypatch.setattr(start, "_load_nowcast_daily_summary_rows", lambda date_str: ([], {}))
    _mock_redis(monkeypatch, {"H_1631_1434": [FC_ENTRY]}, amedas=None)

    n = start._auto_compare_precip_forecast("20260714")

    assert n == 0
    assert not precip_env.exists() or start.pd.read_csv(precip_env).empty


def test_returns_zero_when_no_actual_data_source_exists_at_all(precip_env, monkeypatch):
    monkeypatch.setattr(start, "_load_nowcast_daily_summary_rows", lambda date_str: ([], {}))
    monkeypatch.setattr(start, "_obs_redis_get", lambda key: None)
    monkeypatch.setattr(start, "_obs_redis_scan_keys", lambda pattern: [])

    n = start._auto_compare_precip_forecast("20260714")

    assert n == 0


def test_two_spots_get_independently_correct_precip_forecast_correct(precip_env, monkeypatch):
    """The exact bug this fixes: two spots on the same date must be able to
    get DIFFERENT actual_rain_0416 values (and thus different
    precip_forecast_correct verdicts) instead of one blanket station value."""
    rows = [
        {"spot_name": "H_DRY", "coverage_pct": 100.0, "observed_rain_0416": False,
         "observed_precip_sum_0416_mm": 0.0, "first_rain_time": None, "last_rain_time": None},
        {"spot_name": "H_WET", "coverage_pct": 100.0, "observed_rain_0416": True,
         "observed_precip_sum_0416_mm": 4.2, "first_rain_time": "09:10", "last_rain_time": "11:40"},
    ]
    monkeypatch.setattr(start, "_load_nowcast_daily_summary_rows", lambda date_str: (rows, {}))
    _mock_redis(monkeypatch, {"H_DRY": [FC_ENTRY], "H_WET": [FC_ENTRY]}, amedas=None)

    n = start._auto_compare_precip_forecast("20260714")

    assert n == 2
    df = start.pd.read_csv(precip_env)
    dry = df[df["spot_name"] == "H_DRY"].iloc[0]
    wet = df[df["spot_name"] == "H_WET"].iloc[0]
    # forecast said rain (0.5mm) for both -- correct only for H_WET
    assert dry["precip_forecast_correct"] == False  # noqa: E712
    assert wet["precip_forecast_correct"] == True  # noqa: E712
    assert wet["actual_rain_first_time_0416"] == "09:10"
    assert wet["actual_rain_last_time_0416"] == "11:40"
