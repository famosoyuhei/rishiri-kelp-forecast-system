import pandas as pd
from pathlib import Path


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
    response = client.get("/api/validation/accuracy/sheets?days=30")
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
    response = client.get("/api/validation/accuracy/sheets/summary?days=30")
    data = response.get_json()

    assert response.status_code == 200
    by_day = data["tables"]["by_day"]
    by_area = data["tables"]["by_area"]

    assert by_day[0]["summary_key"] == "2026-06-10"
    assert by_day[0]["rows"] == 2
    assert by_day[0]["precip_hit_rate_pct"] == 50.0
    assert by_day[0]["judgment_hit_rate_pct"] == 50.0
    assert by_area[0]["summary_key"] == "利尻町|沓形"


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

    response = start.app.test_client().get("/api/validation/accuracy/sheets?days=30")
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
