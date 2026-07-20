import pandas as pd
from pathlib import Path
import json


TMP_DIR = Path(__file__).parent / "_tmp_accuracy_sheets"


def test_accuracy_sheets_rows_include_upsert_key(monkeypatch):
    import start

    feedback_file = TMP_DIR / "feedback_log_rows.csv"
    spots_file = TMP_DIR / "hoshiba_spots_rows.csv"

    pd.DataFrame([
        {
            "date": "2026-06-10",
            "spot_name": "H_1631_1434",
            "days_ahead": 1,
            "actual_precip_0416_mm": 0.0,
            "actual_precip_total_mm": 0.0,
            "actual_rain_0416": False,
            "forecast_precip_mm": 0.0,
            "forecast_rain": False,
            "precip_forecast_correct": True,
            "forecast_score": 82,
            "forecast_suitability": "good",
            "forecast_label": "可",
            "actual_result": "完全乾燥",
            "actual_label": "可",
            "judgment_correct": True,
            "has_drying_record": True,
            "data_source": "openmeteo_archive",
            "recorded_at": "2026-06-11T03:10:00+09:00",
        }
    ]).to_csv(feedback_file, index=False)

    pd.DataFrame([
        {
            "name": "H_1631_1434",
            "lat": 45.1631,
            "lon": 141.1434,
            "town": "利尻町",
            "district": "沓形",
            "buraku": "神居",
        }
    ]).to_csv(spots_file, index=False)

    monkeypatch.setattr(start, "FEEDBACK_FILE", str(feedback_file))
    monkeypatch.setattr(start, "CSV_FILE", str(spots_file))

    client = start.app.test_client()
    response = client.get("/api/validation/accuracy/sheets?days=90")
    data = response.get_json()

    assert response.status_code == 200
    assert data["status"] == "ok"
    assert data["columns"][0] == "upsert_key"
    assert data["rows"][0]["upsert_key"] == "2026-06-10|H_1631_1434|1"
    assert data["rows"][0]["town"] == "利尻町"
    assert data["summary"]["precip_hit_rate_pct"] == 100.0
    assert data["summary"]["judgment_hit_rate_pct"] == 100.0


def test_accuracy_sheets_summary_includes_summary_keys(monkeypatch):
    import start

    feedback_file = TMP_DIR / "feedback_log_summary.csv"
    spots_file = TMP_DIR / "hoshiba_spots_summary.csv"

    pd.DataFrame([
        {
            "date": "2026-06-10",
            "spot_name": "H_1631_1434",
            "days_ahead": 1,
            "actual_precip_0416_mm": 0.0,
            "actual_precip_total_mm": 0.0,
            "actual_rain_0416": False,
            "forecast_precip_mm": 0.0,
            "forecast_rain": False,
            "precip_forecast_correct": True,
            "forecast_score": 82,
            "forecast_suitability": "good",
            "forecast_label": "可",
            "actual_result": "完全乾燥",
            "actual_label": "可",
            "judgment_correct": True,
            "has_drying_record": True,
            "data_source": "openmeteo_archive",
            "recorded_at": "2026-06-11T03:10:00+09:00",
        },
        {
            "date": "2026-06-10",
            "spot_name": "H_1782_1394",
            "days_ahead": 2,
            "actual_precip_0416_mm": 1.2,
            "actual_precip_total_mm": 1.2,
            "actual_rain_0416": True,
            "forecast_precip_mm": 0.0,
            "forecast_rain": False,
            "precip_forecast_correct": False,
            "forecast_score": 76,
            "forecast_suitability": "good",
            "forecast_label": "可",
            "actual_result": "ほぼ乾燥なし",
            "actual_label": "不可",
            "judgment_correct": False,
            "has_drying_record": True,
            "data_source": "openmeteo_archive",
            "recorded_at": "2026-06-11T03:10:00+09:00",
        },
    ]).to_csv(feedback_file, index=False)

    pd.DataFrame([
        {
            "name": "H_1631_1434",
            "lat": 45.1631,
            "lon": 141.1434,
            "town": "利尻町",
            "district": "沓形",
            "buraku": "神居",
        },
        {
            "name": "H_1782_1394",
            "lat": 45.1782,
            "lon": 141.1394,
            "town": "利尻町",
            "district": "沓形",
            "buraku": "泉町",
        },
    ]).to_csv(spots_file, index=False)

    monkeypatch.setattr(start, "FEEDBACK_FILE", str(feedback_file))
    monkeypatch.setattr(start, "CSV_FILE", str(spots_file))

    client = start.app.test_client()
    response = client.get("/api/validation/accuracy/sheets/summary?days=90")
    data = response.get_json()

    assert response.status_code == 200
    by_day = data["tables"]["by_day"]
    by_area = data["tables"]["by_area"]

    assert by_day[0]["summary_key"] == "2026-06-10"
    assert by_day[0]["rows"] == 2
    assert by_day[0]["precip_hit_rate_pct"] == 50.0
    assert by_day[0]["judgment_hit_rate_pct"] == 50.0
    assert by_area[0]["summary_key"] == "利尻町|沓形"
    assert data["tables"]["by_day_days_ahead"][0]["summary_key"] == "2026-06-10|1"
    assert data["tables"]["reliability_by_days_ahead"][0]["days_ahead"] == 1
    assert data["tables"]["coverage_by_day_days_ahead"][0]["date"] == "2026-06-10"


def test_accuracy_reliability_reports_recent_completeness(monkeypatch):
    import start

    feedback_file = TMP_DIR / "feedback_log_reliability.csv"
    spots_file = TMP_DIR / "hoshiba_spots_reliability.csv"

    pd.DataFrame([
        {
            "date": "2026-06-10",
            "spot_name": "H_1631_1434",
            "days_ahead": 1,
            "actual_rain_0416": False,
            "forecast_rain": False,
            "precip_forecast_correct": True,
            "forecast_label": "可",
            "actual_label": "可",
            "judgment_correct": True,
            "has_drying_record": True,
        },
        {
            "date": "2026-06-10",
            "spot_name": "H_1782_1394",
            "days_ahead": 1,
            "actual_rain_0416": True,
            "forecast_rain": False,
            "precip_forecast_correct": False,
            "forecast_label": "可",
            "actual_label": "不可",
            "judgment_correct": False,
            "has_drying_record": True,
        },
        {
            "date": "2026-06-10",
            "spot_name": "H_1631_1434",
            "days_ahead": 2,
            "actual_rain_0416": False,
            "forecast_rain": False,
            "precip_forecast_correct": True,
            "forecast_label": "可",
            "actual_label": "可",
            "judgment_correct": True,
            "has_drying_record": True,
        },
    ]).to_csv(feedback_file, index=False)

    pd.DataFrame([
        {"name": "H_1631_1434", "town": "利尻町", "district": "沓形", "buraku": "神居"},
        {"name": "H_1782_1394", "town": "利尻町", "district": "沓形", "buraku": "泉町"},
        {"name": "A_1783_1383", "town": "利尻町", "district": "沓形", "buraku": "泉町"},
    ]).to_csv(spots_file, index=False)

    monkeypatch.setattr(start, "FEEDBACK_FILE", str(feedback_file))
    monkeypatch.setattr(start, "CSV_FILE", str(spots_file))

    response = start.app.test_client().get("/api/validation/accuracy/reliability?days=90&recent_days=1")
    data = response.get_json()

    assert response.status_code == 200
    assert data["status"] == "ok"
    assert data["recent_health"]["expected_spots"] == 2
    assert data["recent_health"]["overall_complete"] is True
    assert data["coverage_by_day_days_ahead"][0]["complete"] is True
    assert data["coverage_by_day_days_ahead"][0]["coverage_pct"] == 100.0
    assert data["reliability_by_days_ahead"][0]["days_ahead"] == 1
    assert data["reliability_by_days_ahead"][0]["judgment_hit_rate_pct"] == 50.0
    assert data["reliability_by_days_ahead"][0]["primary_metric"] == "judgment_hit_rate_pct"


def test_deleted_spot_keeps_snapshot_metadata(monkeypatch):
    import start

    feedback_file = TMP_DIR / "feedback_log_deleted.csv"
    spots_file = TMP_DIR / "hoshiba_spots_deleted.csv"

    pd.DataFrame([{
        "date": "2026-06-10",
        "spot_name": "H_9999_9999",
        "days_ahead": 1,
        "town": "利尻町",
        "district": "仙法志",
        "buraku": "長浜",
        "precip_forecast_correct": True,
        "judgment_correct": True,
        "has_drying_record": False,
    }]).to_csv(feedback_file, index=False)

    # The historical spot no longer exists in the current master.
    pd.DataFrame([{
        "name": "H_1631_1434",
        "lat": 45.1631,
        "lon": 141.1434,
        "town": "利尻町",
        "district": "沓形",
        "buraku": "神居",
    }]).to_csv(spots_file, index=False)

    monkeypatch.setattr(start, "FEEDBACK_FILE", str(feedback_file))
    monkeypatch.setattr(start, "CSV_FILE", str(spots_file))

    response = start.app.test_client().get("/api/validation/accuracy/sheets?days=90")
    row = response.get_json()["rows"][0]

    assert response.status_code == 200
    assert row["spot_name"] == "H_9999_9999"
    assert row["town"] == "利尻町"
    assert row["district"] == "仙法志"
    assert row["buraku"] == "長浜"


def test_spot_master_endpoint_returns_current_snapshot(monkeypatch):
    import start

    spots_file = TMP_DIR / "hoshiba_spots_master.csv"
    pd.DataFrame([
        {
            "name": "H_1631_1434", "lat": 45.1631, "lon": 141.1434,
            "town": "利尻町", "district": "沓形", "buraku": "神居",
        },
        {
            "name": "A_1783_1383", "lat": 45.1783, "lon": 141.1383,
            "town": "利尻町", "district": "沓形", "buraku": "泉町",
        },
    ]).to_csv(spots_file, index=False)

    monkeypatch.setattr(start, "CSV_FILE", str(spots_file))
    response = start.app.test_client().get("/api/integration/spots/sheets")
    data = response.get_json()

    assert response.status_code == 200
    assert data["status"] == "ok"
    assert data["sync_mode"] == "replace_current_snapshot"
    assert data["summary"] == {"total": 2, "hoshiba": 1, "special_points": 1}
    assert data["rows"][0]["master_key"] == "H_1631_1434"
    assert data["rows"][1]["spot_type"] == "amedas"
    assert data["rows"][1]["is_protected"] is True


def test_forecast_snapshot_sheets_returns_saved_rows(monkeypatch):
    import start

    spots_file = TMP_DIR / "hoshiba_spots_forecast_snapshot.csv"
    history_dir = TMP_DIR / "forecast_history"
    spot_dir = history_dir / "H_1631_1434"
    amedas_dir = history_dir / "A_1783_1383"
    summit_dir = history_dir / "R_1800_2392"
    spot_dir.mkdir(parents=True, exist_ok=True)
    amedas_dir.mkdir(parents=True, exist_ok=True)
    summit_dir.mkdir(parents=True, exist_ok=True)

    pd.DataFrame([
        {
            "name": "H_1631_1434", "lat": 45.1631, "lon": 141.1434,
            "town": "利尻町", "district": "沓形", "buraku": "神居",
        },
        {
            "name": "A_1783_1383", "lat": 45.1783, "lon": 141.1383,
            "town": "利尻町", "district": "沓形", "buraku": "泉町",
        },
        {
            "name": "R_1800_2392", "lat": 45.18, "lon": 141.2392,
            "town": "利尻町", "district": "山頂", "buraku": "利尻山",
        },
    ]).to_csv(spots_file, index=False)

    base_record = {
        "forecast_date": "20260629",
        "target_date": "2026-06-30",
        "day_number": 1,
        "max_temp": 18.5,
        "min_humidity": 82,
        "avg_wind": 3.2,
        "precipitation": 0.0,
        "precipitation_0416": 0.0,
        "drying_score": 84,
        "suitability": "good",
    }
    for target_dir in (spot_dir, amedas_dir, summit_dir):
        (target_dir / "forecast_20260629_for_20260630.json").write_text(
            json.dumps(base_record, ensure_ascii=False),
            encoding="utf-8",
        )

    monkeypatch.setattr(start, "CSV_FILE", str(spots_file))
    monkeypatch.setattr(start, "FORECAST_HISTORY_DIR", str(history_dir))
    monkeypatch.setattr(start, "_obs_redis_get", lambda key: None)

    response = start.app.test_client().get(
        "/api/forecast/snapshots/sheets?forecast_date=2026-06-29&max_days_ahead=1"
    )
    data = response.get_json()

    assert response.status_code == 200
    assert data["status"] == "ok"
    assert data["columns"][0] == "upsert_key"
    assert data["summary"]["expected_spots"] == 3
    assert data["summary"]["expected_rows"] == 6
    assert data["summary"]["total_rows"] == 3
    assert data["summary"]["coverage_pct"] == 50.0
    assert {row["spot_type"] for row in data["rows"]} == {"hoshiba", "amedas", "reference"}
    assert data["rows"][0]["upsert_key"] == "20260629|H_1631_1434|1"
    assert data["rows"][0]["forecast_rain_0416"] is False


def test_forecast_snapshot_manual_run_batches_redis_writes(monkeypatch):
    import start
    import sys
    import types

    spots_file = TMP_DIR / "hoshiba_spots_forecast_manual.csv"
    pd.DataFrame([
        {
            "name": "H_1631_1434", "lat": 45.1631, "lon": 141.1434,
            "town": "利尻町", "district": "沓形", "buraku": "神居",
        },
    ]).to_csv(spots_file, index=False)

    def fake_forecast(_lat, _lon, timeout=15):
        return [{
            "date": "2026-06-30",
            "day_number": 1,
            "max_temp": 18.5,
            "min_humidity": 82,
            "avg_wind": 3.2,
            "precipitation": 0.0,
            "precipitation_0416": 0.0,
            "score": 84,
            "suitability": "good",
        }]

    written = {}
    monkeypatch.setattr(start, "CSV_FILE", str(spots_file))
    monkeypatch.setitem(
        sys.modules,
        "line_integration",
        types.SimpleNamespace(get_forecast_for_spot=fake_forecast),
    )
    monkeypatch.setattr(start, "_obs_redis_mget", lambda keys: {})
    monkeypatch.setattr(start, "_obs_redis_mset", lambda values: written.update(values) or len(values))
    monkeypatch.delenv("LINE_ADMIN_NOTIFY_SECRET", raising=False)
    monkeypatch.delenv("RENDER", raising=False)

    response = start.app.test_client().post("/api/forecast/snapshots/run")
    data = response.get_json()

    assert response.status_code == 200
    assert data["status"] == "ok"
    assert data["result"]["spots"] == 1
    assert data["result"]["planned_records"] == 1
    assert data["result"]["saved_records"] == 1
    assert list(written.keys()) == ["forecast:hist:H_1631_1434:20260630"]


def test_forecast_snapshot_manual_run_requires_secret_on_render(monkeypatch):
    import start

    monkeypatch.setenv("RENDER", "true")
    monkeypatch.delenv("LINE_ADMIN_NOTIFY_SECRET", raising=False)

    response = start.app.test_client().post("/api/forecast/snapshots/run")

    assert response.status_code == 503
    assert response.get_json()["status"] == "LINE_ADMIN_NOTIFY_SECRET not configured"


def test_amedas_observation_sheets_returns_window_rows(monkeypatch):
    import start

    amedas_dir = TMP_DIR / "amedas_data"
    amedas_dir.mkdir(parents=True, exist_ok=True)

    for station_id, station_name in (("11151", "沓形"), ("11311", "本泊")):
        hourly = [
            {
                "time": f"2026-06-28T{hour:02d}:00",
                "temperature": 15 + hour,
                "humidity": 90 - hour,
                "wind_speed": 2.0,
                "precipitation": 0.0,
            }
            for hour in range(4, 17)
        ]
        (amedas_dir / f"amedas_{station_id}_20260628.json").write_text(
            json.dumps({
                "date": "2026-06-28",
                "station_id": station_id,
                "station_name": station_name,
                "hourly": hourly,
                "collected_at": "2026-06-29T03:00:00+09:00",
            }, ensure_ascii=False),
            encoding="utf-8",
        )

    monkeypatch.setattr(start, "AMEDAS_DATA_DIR", str(amedas_dir))
    monkeypatch.setattr(start, "_obs_redis_get", lambda key: None)

    response = start.app.test_client().get("/api/observations/amedas/sheets?date=2026-06-28")
    data = response.get_json()

    assert response.status_code == 200
    assert data["status"] == "ok"
    assert data["summary"]["expected_rows"] == 26
    assert data["summary"]["total_rows"] == 26
    assert data["summary"]["complete"] is True
    assert data["rows"][0]["upsert_key"] == "20260628|11151|04:00"
    assert data["rows"][0]["spot_name"] == "A_1783_1383"


def test_nowcast_observation_sheets_returns_mesh_rows(monkeypatch):
    import start

    spots_file = TMP_DIR / "hoshiba_spots_nowcast.csv"
    pd.DataFrame([
        {
            "name": "H_1631_1434", "lat": 45.1631, "lon": 141.1434,
            "town": "利尻町", "district": "沓形", "buraku": "神居",
        },
        {
            "name": "A_1783_1383", "lat": 45.1783, "lon": 141.1383,
            "town": "利尻町", "district": "沓形", "buraku": "泉町",
        },
    ]).to_csv(spots_file, index=False)

    snapshots = [
        {
            "time": "04:00",
            "basetime": "20260628190000",
            "spots": {"H_1631_1434": 0.0, "A_1783_1383": 1.0},
        },
        {
            "time": "16:00",
            "basetime": "20260629070000",
            "spots": {"H_1631_1434": 0.5, "A_1783_1383": 0.0},
        },
    ]

    def fake_redis_get(key):
        if key == "nowcast:daily:20260629":
            return snapshots
        return None

    monkeypatch.setattr(start, "CSV_FILE", str(spots_file))
    monkeypatch.setattr(start, "_obs_redis_get", fake_redis_get)

    response = start.app.test_client().get("/api/observations/nowcast/sheets?date=2026-06-29")
    data = response.get_json()

    assert response.status_code == 200
    assert data["status"] == "ok"
    assert data["summary"]["snapshot_count"] == 2
    assert data["summary"]["expected_spots"] == 2
    assert data["summary"]["total_rows"] == 4
    assert data["summary"]["complete_for_recorded_snapshots"] is True
    assert data["rows"][0]["upsert_key"] == "20260629|04:00|A_1783_1383"
    assert data["rows"][0]["spot_type"] == "amedas"
    assert data["rows"][0]["any_rain"] is True


def test_nowcast_daily_summary_sheets_returns_per_spot_rows(monkeypatch):
    import start

    spots_file = TMP_DIR / "hoshiba_spots_nowcast_summary.csv"
    pd.DataFrame([
        {
            "name": "H_1631_1434", "lat": 45.1631, "lon": 141.1434,
            "town": "利尻町", "district": "沓形", "buraku": "神居",
        },
        {
            "name": "A_1783_1383", "lat": 45.1783, "lon": 141.1383,
            "town": "利尻町", "district": "沓形", "buraku": "泉町",
        },
    ]).to_csv(spots_file, index=False)

    snapshots = [
        {
            "time": "04:10",
            "basetime": "20260628191000",
            "spots": {"H_1631_1434": 0.0, "A_1783_1383": 1.2},
        },
        {
            "time": "04:20",
            "basetime": "20260628192000",
            "spots": {"H_1631_1434": 0.6, "A_1783_1383": 0.0},
        },
    ]

    monkeypatch.setattr(start, "CSV_FILE", str(spots_file))
    monkeypatch.setattr(start, "_obs_redis_get", lambda key: snapshots if key == "nowcast:daily:20260629" else None)

    response = start.app.test_client().get("/api/observations/nowcast/daily-summary/sheets?date=2026-06-29")
    data = response.get_json()

    assert response.status_code == 200
    assert data["status"] == "ok"
    assert data["summary"]["snapshot_count"] == 2
    assert data["summary"]["total_rows"] == 2
    assert data["summary"]["rain_spots"] == 2
    rows = {row["spot_name"]: row for row in data["rows"]}
    assert rows["H_1631_1434"]["observed_rain_0416"] is True
    assert rows["H_1631_1434"]["observed_precip_sum_0416_mm"] == 0.1
    assert rows["A_1783_1383"]["first_rain_time"] == "04:10"


def test_forecast_precip_accuracy_by_horizon_compares_forecast_and_nowcast(monkeypatch):
    import start

    spots_file = TMP_DIR / "hoshiba_spots_precip_accuracy.csv"
    pd.DataFrame([
        {
            "name": "H_1631_1434", "lat": 45.1631, "lon": 141.1434,
            "town": "利尻町", "district": "沓形", "buraku": "神居",
        },
        {
            "name": "H_1700_1400", "lat": 45.17, "lon": 141.14,
            "town": "利尻町", "district": "沓形", "buraku": "泉町",
        },
    ]).to_csv(spots_file, index=False)

    snapshots = [
        {
            "time": "04:10",
            "basetime": "20260628191000",
            "spots": {"H_1631_1434": 1.2, "H_1700_1400": 0.0},
        },
        {
            "time": "04:20",
            "basetime": "20260628192000",
            "spots": {"H_1631_1434": 0.0, "H_1700_1400": 0.0},
        },
    ]

    histories = {
        "forecast:hist:H_1631_1434:20260629": [
            {"forecast_date": "20260628", "target_date": "2026-06-29", "precipitation_0416": 0.0},
            {"forecast_date": "20260629", "target_date": "2026-06-29", "precipitation_0416": 0.3},
        ],
        "forecast:hist:H_1700_1400:20260629": [
            {"forecast_date": "20260628", "target_date": "2026-06-29", "precipitation_0416": 0.0},
            {"forecast_date": "20260629", "target_date": "2026-06-29", "precipitation_0416": 0.0},
        ],
    }

    def fake_redis_get(key):
        if key == "nowcast:daily:20260629":
            return snapshots
        return None

    def fake_redis_mget(keys):
        return {key: histories.get(key) for key in keys if key in histories}

    monkeypatch.setattr(start, "CSV_FILE", str(spots_file))
    monkeypatch.setattr(start, "_obs_redis_get", fake_redis_get)
    monkeypatch.setattr(start, "_obs_redis_mget", fake_redis_mget)

    response = start.app.test_client().get(
        "/api/validation/forecast-precip/accuracy-by-horizon/sheets?target_date=2026-06-29&max_days_ahead=1"
    )
    data = response.get_json()

    assert response.status_code == 200
    assert data["status"] == "ok"
    assert data["summary"]["horizon_rows"] == 2
    rows = {row["days_ahead"]: row for row in data["rows"]}
    assert rows[0]["spot_count"] == 2
    assert rows[0]["tp_count"] == 1
    assert rows[0]["tn_count"] == 1
    assert rows[0]["hit_rate_pct"] == 100.0
    assert rows[1]["fn_count"] == 1
    assert rows[1]["tn_count"] == 1
    assert rows[1]["hit_rate_pct"] == 50.0
