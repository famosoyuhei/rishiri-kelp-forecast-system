"""
Tests for _check_records_have_feedback() (2026-09-01 safeguard).

Background: two severe, unrelated bugs both caused the same symptom this
season -- a fisherman submits a drying record via LINE or the web app, and
it silently never contributes to judgment_accuracy/precip_forecast_accuracy
at all:
  1. hoshiba_records.csv itself wasn't being persisted to Redis, so it was
     wiped on every redeploy (fixed 2026-08-04/08).
  2. _record_forecast_feedback() only ever looked at local-disk forecast
     history (also wiped on redeploy), so judgment_correct was essentially
     never populated even for records that DID survive (fixed 2026-08-09).

Both were only discovered because the user happened to ask "did my record
actually improve accuracy?" -- nothing in the system would have caught a
third, still-unknown bug with the same symptom. This check closes that gap:
every day, verify that records submitted in roughly the last two days all
have a matching feedback_log.csv row (has_drying_record=True). If any are
missing, _daily_data_integrity_check() must not report overall_ok=True.

Run from project root:
    python -m pytest tests/test_records_feedback_integrity_check.py -v
"""
import pytest

import start


@pytest.fixture
def integrity_env(tmp_path, monkeypatch):
    record_file = tmp_path / "hoshiba_records.csv"
    feedback_file = tmp_path / "feedback_log.csv"
    monkeypatch.setattr(start, "RECORD_FILE", str(record_file))
    monkeypatch.setattr(start, "FEEDBACK_FILE", str(feedback_file))
    monkeypatch.setattr(start, "_records_redis_restore", lambda: False)
    monkeypatch.setattr(start, "_records_redis_save", lambda df: True)
    monkeypatch.setattr(start, "_obs_redis_get", lambda key: None)
    monkeypatch.setattr(start, "_feedback_log_redis_restore", lambda: False)
    return record_file, feedback_file


def _now_jst_iso():
    from datetime import datetime
    return datetime.now(tz=start.JST).strftime("%Y-%m-%dT%H:%M:%S+09:00")


def test_ok_when_no_records_exist(integrity_env):
    result = start._check_records_have_feedback()
    assert result["ok"] is True
    assert result["checked"] == 0


def test_ok_when_recent_record_has_matching_feedback_row(integrity_env):
    record_file, feedback_file = integrity_env
    record_file.write_text(
        "date,name,result,stop_cause,did_dry,collection_time,recorded_at,correction_count,correction_reason\n"
        f"2026-07-14,H_2480_2198,完全乾燥,,True,,{_now_jst_iso()},0,\n",
        encoding="utf-8",
    )
    feedback_file.write_text(
        "date,spot_name,days_ahead,has_drying_record,judgment_correct\n"
        "2026-07-14,H_2480_2198,0,True,True\n",
        encoding="utf-8",
    )

    result = start._check_records_have_feedback()

    assert result["ok"] is True
    assert result["checked"] == 1
    assert result["missing_count"] == 0


def test_flags_recent_record_with_no_matching_feedback_row(integrity_env):
    """The exact regression this check exists to catch: a record was
    submitted but _record_forecast_feedback() (for whatever reason) never
    wrote a corresponding feedback_log row for it."""
    record_file, feedback_file = integrity_env
    record_file.write_text(
        "date,name,result,stop_cause,did_dry,collection_time,recorded_at,correction_count,correction_reason\n"
        f"2026-07-14,H_2480_2198,完全乾燥,,True,,{_now_jst_iso()},0,\n",
        encoding="utf-8",
    )
    feedback_file.write_text(
        "date,spot_name,days_ahead,has_drying_record,judgment_correct\n",
        encoding="utf-8",
    )

    result = start._check_records_have_feedback()

    assert result["ok"] is False
    assert result["checked"] == 1
    assert result["missing_count"] == 1
    assert result["missing"][0]["name"] == "H_2480_2198"
    assert result["missing"][0]["date"] == "2026-07-14"


def test_ignores_old_records_outside_the_window(integrity_env):
    """A record submitted weeks ago with no feedback row is not this
    check's concern -- only recently-submitted records are checked, so an
    old backlog doesn't perpetually fail the daily integrity check."""
    record_file, feedback_file = integrity_env
    record_file.write_text(
        "date,name,result,stop_cause,did_dry,collection_time,recorded_at,correction_count,correction_reason\n"
        "2025-06-20,H_1631_1434,完全乾燥,,True,,2025-06-20T09:00:00+09:00,0,\n",
        encoding="utf-8",
    )
    feedback_file.write_text(
        "date,spot_name,days_ahead,has_drying_record,judgment_correct\n",
        encoding="utf-8",
    )

    result = start._check_records_have_feedback(hours_back=48)

    assert result["ok"] is True
    assert result["checked"] == 0


def test_missing_list_is_capped_at_twenty_for_report_size(integrity_env):
    record_file, feedback_file = integrity_env
    now = _now_jst_iso()
    header = "date,name,result,stop_cause,did_dry,collection_time,recorded_at,correction_count,correction_reason\n"
    rows = "".join(f"2026-07-{(i % 28) + 1:02d},H_TEST_{i},完全乾燥,,True,,{now},0,\n" for i in range(25))
    record_file.write_text(header + rows, encoding="utf-8")
    feedback_file.write_text("date,spot_name,days_ahead,has_drying_record,judgment_correct\n", encoding="utf-8")

    result = start._check_records_have_feedback()

    assert result["missing_count"] == 25
    assert len(result["missing"]) == 20


def test_daily_integrity_check_is_not_ok_when_records_missing_feedback(integrity_env, monkeypatch):
    """Integration: _daily_data_integrity_check()'s overall_ok must go False
    when this check fails, even if every other subsystem is healthy."""
    record_file, feedback_file = integrity_env
    record_file.write_text(
        "date,name,result,stop_cause,did_dry,collection_time,recorded_at,correction_count,correction_reason\n"
        f"2026-07-14,H_2480_2198,完全乾燥,,True,,{_now_jst_iso()},0,\n",
        encoding="utf-8",
    )
    feedback_file.write_text("date,spot_name,days_ahead,has_drying_record,judgment_correct\n", encoding="utf-8")

    # Make every other sub-check report healthy so only this one can fail overall_ok.
    monkeypatch.setattr(start, "_check_redis_persistence", lambda date_str: {"all_ok": True, "checks": {
        f"forecast_hist_{date_str}": {"ok": True, "spot_count": 334},
    }})
    monkeypatch.setattr(start, "_compare_amedas_full_weather", lambda date_str: {})
    monkeypatch.setattr(start, "_obs_redis_set", lambda key, data, ttl=None: True)
    monkeypatch.setattr(start, "_obs_redis_scan_keys", lambda pattern: [])

    report = start._daily_data_integrity_check(target_date="20260714")

    assert report["overall_ok"] is False
    assert report["records_without_feedback"]["missing_count"] == 1
