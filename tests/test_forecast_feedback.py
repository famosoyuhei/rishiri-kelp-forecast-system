"""
Tests for _record_forecast_feedback()'s Redis-first forecast-history lookup
(2026-08-08 fix).

Background: this function is called every time a drying record is added or
corrected, and is supposed to look up the forecast that was made for that
spot+date and log whether it was right or wrong. It previously searched
*only* forecast_history/{spot}/*.json on local disk. Render's disk is wiped
on every redeploy, so by the time a user actually submits a record -- often
days or weeks after the forecast was made -- the local snapshot is almost
always already gone. Production was found to have exactly 0 rows with
has_drying_record=True across a full year, despite thousands of real
drying records having been submitted: the "judgment accuracy" metric had
never actually measured anything.

_save_forecast_history() already writes each snapshot to Redis under
forecast:hist:{spot_name}:{target_YYYYMMDD} (a list, one entry per lead
time) as the primary store. This fix makes _record_forecast_feedback()
read from there first, falling back to the local JSON files only if Redis
has nothing for that key.

Run from project root:
    python -m pytest tests/test_forecast_feedback.py -v
"""
import json
import os

import pytest

import start


@pytest.fixture
def feedback_env(tmp_path, monkeypatch):
    feedback_file = tmp_path / "feedback_log.csv"
    history_dir = tmp_path / "forecast_history"
    spots_file = tmp_path / "hoshiba_spots.csv"
    spots_file.write_text("name,lat,lon,town,district,buraku\nH_1631_1434,45.1631,141.1434,A,B,C\n",
                           encoding="utf-8")

    monkeypatch.setattr(start, "FEEDBACK_FILE", str(feedback_file))
    monkeypatch.setattr(start, "FORECAST_HISTORY_DIR", str(history_dir))
    monkeypatch.setattr(start, "CSV_FILE", str(spots_file))
    monkeypatch.setattr(start, "_feedback_log_redis_restore", lambda: False)
    monkeypatch.setattr(start, "_feedback_log_redis_save", lambda df: True)
    return feedback_file


SAMPLE_FC = {
    "logic_source": "web_forecast",
    "forecast_date": "20260701",
    "target_date": "2026-07-02",
    "day_number": 1,
    "drying_score": 85,
    "suitability": "excellent",
    "precipitation_0416": 0.0,
    "precipitation": 0.0,
}


def test_reads_from_redis_first_and_records_correct_judgment(feedback_env, monkeypatch):
    monkeypatch.setattr(start, "_obs_redis_get",
                         lambda key: [SAMPLE_FC] if key == "forecast:hist:H_1631_1434:20260702" else None)

    start._record_forecast_feedback("H_1631_1434", "2026-07-02", "完全乾燥")

    df = start.pd.read_csv(feedback_env)
    assert len(df) == 1
    row = df.iloc[0]
    assert row["has_drying_record"] == True  # noqa: E712
    assert row["actual_label"] == "可"
    assert row["forecast_label"] == "可"
    assert row["judgment_correct"] == True  # noqa: E712
    assert row["days_ahead"] == 1


def test_falls_back_to_local_json_when_redis_has_nothing(feedback_env, monkeypatch):
    monkeypatch.setattr(start, "_obs_redis_get", lambda key: None)
    spot_dir = os.path.join(start.FORECAST_HISTORY_DIR, "H_1631_1434")
    os.makedirs(spot_dir, exist_ok=True)
    with open(os.path.join(spot_dir, "forecast_20260701_for_20260702.json"), "w", encoding="utf-8") as f:
        json.dump(SAMPLE_FC, f)

    start._record_forecast_feedback("H_1631_1434", "2026-07-02", "完全乾燥")

    df = start.pd.read_csv(feedback_env)
    assert len(df) == 1
    assert df.iloc[0]["has_drying_record"] == True  # noqa: E712


def test_noop_when_neither_redis_nor_local_has_a_snapshot(feedback_env, monkeypatch):
    monkeypatch.setattr(start, "_obs_redis_get", lambda key: None)

    start._record_forecast_feedback("H_1631_1434", "2026-07-02", "完全乾燥")

    assert not os.path.exists(feedback_env)


def test_detects_false_negative_forecast_said_unfit_but_actually_dried(feedback_env, monkeypatch):
    """The exact scenario the user suspected: forecast said 不可 (can't dry),
    but the fisherman actually dried it successfully -- must show up as
    judgment_correct=False with forecast_label=不可 / actual_label=可."""
    fc = dict(SAMPLE_FC, suitability="poor")  # -> forecast_label = 不可
    monkeypatch.setattr(start, "_obs_redis_get",
                         lambda key: [fc] if key == "forecast:hist:H_1631_1434:20260702" else None)

    start._record_forecast_feedback("H_1631_1434", "2026-07-02", "完全乾燥")

    df = start.pd.read_csv(feedback_env)
    row = df.iloc[0]
    assert row["forecast_label"] == "不可"
    assert row["actual_label"] == "可"
    assert row["judgment_correct"] == False  # noqa: E712


def test_correcting_a_record_updates_the_existing_row_not_a_new_one(feedback_env, monkeypatch):
    monkeypatch.setattr(start, "_obs_redis_get",
                         lambda key: [SAMPLE_FC] if key == "forecast:hist:H_1631_1434:20260702" else None)

    start._record_forecast_feedback("H_1631_1434", "2026-07-02", "ほぼ乾燥なし")  # 不可, wrong at first
    start._record_forecast_feedback("H_1631_1434", "2026-07-02", "完全乾燥")      # corrected -> 可

    df = start.pd.read_csv(feedback_env)
    assert len(df) == 1
    assert df.iloc[0]["actual_label"] == "可"
    assert df.iloc[0]["judgment_correct"] == True  # noqa: E712


def test_persists_to_redis_after_writing(feedback_env, monkeypatch):
    monkeypatch.setattr(start, "_obs_redis_get",
                         lambda key: [SAMPLE_FC] if key == "forecast:hist:H_1631_1434:20260702" else None)
    saved = []
    monkeypatch.setattr(start, "_feedback_log_redis_save", lambda df: saved.append(df) or True)

    start._record_forecast_feedback("H_1631_1434", "2026-07-02", "完全乾燥")

    assert len(saved) == 1
    assert saved[-1].iloc[0]["has_drying_record"] == True  # noqa: E712
