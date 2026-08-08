"""
Tests for hoshiba_records.csv's Redis persistence (2026-08-04 emergency fix).

Background: /record wrote only to Render's ephemeral local disk, with no
Redis backup (unlike forecast_history and feedback_log.csv, which already
had this fix). Every redeploy silently wiped whatever drying records had
been submitted since the last deploy -- discovered after a full season of
user-submitted records had likely already been lost this way.

Covers:
  - _records_redis_save() / _records_redis_restore(): same whole-CSV-as-a-
    string pattern already used for feedback_log.csv
  - _load_records(): restores from Redis when the local file is missing,
    and backfills Redis when Redis is empty but local data exists
  - add_record(): writes through to Redis on every save, not just the local file
  - delete_spot(): the "has drying records" block-reason check goes through
    _load_records() (Redis-aware), not a direct file read

Run from project root:
    python -m pytest tests/test_records_persistence.py -v
"""
from unittest.mock import patch, MagicMock

import pytest

# Import start.py exactly once, here, before any test's monkeypatched env vars
# could be active (see tests/test_field_cache.py for the full rationale --
# Flask-Limiter reads UPSTASH_REDIS_REST_URL at module import time).
import start  # noqa: E402


SAMPLE_CSV = (
    "date,name,result,stop_cause,did_dry,collection_time,recorded_at,correction_count,correction_reason\n"
    "2026-07-01,H_1631_1434,完全乾燥,,True,15:00,2026-07-01T16:00:00+09:00,0,\n"
)


@pytest.fixture
def record_file(tmp_path, monkeypatch):
    path = tmp_path / "hoshiba_records.csv"
    monkeypatch.setattr(start, "RECORD_FILE", str(path))
    # _records_restore_attempted is a per-process "already tried" latch (see
    # 2026-08-08 fix below) -- reset it per test so each test gets a fresh restore attempt.
    monkeypatch.setattr(start, "_records_restore_attempted", False)
    return path


# ---------------------------------------------------------------------------
# _records_redis_save / _records_redis_restore
# ---------------------------------------------------------------------------

def test_records_redis_save_writes_csv_string_with_long_ttl(monkeypatch):
    calls = []
    monkeypatch.setattr(
        start, "_obs_redis_set",
        lambda key, data, ttl=None: calls.append((key, data, ttl)) or True,
    )
    df = start.pd.DataFrame([{"date": "2026-07-01", "name": "H_1631_1434", "result": "完全乾燥"}])

    ok = start._records_redis_save(df)

    assert ok is True
    assert len(calls) == 1
    key, data, ttl = calls[0]
    assert key == start._RECORDS_REDIS_KEY
    assert "H_1631_1434" in data
    assert ttl == start._RECORDS_REDIS_TTL
    assert ttl >= 365 * 24 * 3600  # must survive at least a year, not the 90-day obs TTL


def test_records_redis_save_returns_false_and_logs_on_redis_failure(monkeypatch):
    monkeypatch.setattr(start, "_obs_redis_set", lambda key, data, ttl=None: False)
    df = start.pd.DataFrame([{"date": "2026-07-01", "name": "H_1631_1434", "result": "完全乾燥"}])

    ok = start._records_redis_save(df)

    assert ok is False


def test_records_redis_restore_overwrites_stale_git_committed_file(record_file, monkeypatch):
    """2026-08-08 regression: hoshiba_records.csv is checked into git, so a
    freshly-deployed container always has *some* local file on disk (the
    stale git snapshot) -- it is never actually "missing". The old
    os.path.exists(RECORD_FILE) guard treated that as "already restored"
    and silently skipped Redis forever, making every 2026 record invisible
    on any new deploy even though Redis had the up-to-date data all along.
    Restore must overwrite the local file with Redis's content regardless
    of whether a (possibly stale, git-sourced) local file already exists."""
    record_file.write_text("date,name,result\n2025-08-23,H_1631_1434,完全乾燥\n", encoding="utf-8")
    monkeypatch.setattr(start, "_obs_redis_get", lambda key: SAMPLE_CSV)

    restored = start._records_redis_restore()

    assert restored is True
    assert record_file.read_text(encoding="utf-8") == SAMPLE_CSV


def test_records_redis_restore_only_runs_once_per_process(record_file, monkeypatch):
    """The restore should hit Redis at most once per process lifetime, not
    on every _load_records() call -- otherwise every request pays a Redis
    round trip. A module-level "already attempted" flag replaces the old
    (broken) os.path.exists() check for this purpose."""
    redis_get = MagicMock(return_value=SAMPLE_CSV)
    monkeypatch.setattr(start, "_obs_redis_get", redis_get)

    first = start._records_redis_restore()
    second = start._records_redis_restore()

    assert first is True
    assert second is False
    redis_get.assert_called_once()


def test_records_redis_restore_writes_file_from_redis_when_local_missing(record_file, monkeypatch):
    assert not record_file.exists()
    monkeypatch.setattr(start, "_obs_redis_get", lambda key: SAMPLE_CSV)

    restored = start._records_redis_restore()

    assert restored is True
    assert record_file.exists()
    assert record_file.read_text(encoding="utf-8") == SAMPLE_CSV


def test_records_redis_restore_returns_false_when_redis_also_empty(record_file, monkeypatch):
    assert not record_file.exists()
    monkeypatch.setattr(start, "_obs_redis_get", lambda key: None)

    restored = start._records_redis_restore()

    assert restored is False
    assert not record_file.exists()


# ---------------------------------------------------------------------------
# _load_records(): restore-then-read, and lazy Redis backfill
# ---------------------------------------------------------------------------

def test_load_records_calls_restore_before_reading(record_file, monkeypatch):
    call_order = []
    monkeypatch.setattr(start, "_records_redis_restore", lambda: call_order.append("restore") or False)
    monkeypatch.setattr(start, "_obs_redis_get", lambda key: "anything")  # avoid backfill branch noise
    monkeypatch.setattr(start, "_records_redis_save", lambda df: call_order.append("save"))

    start._load_records()

    assert call_order[0] == "restore"


def test_load_records_backfills_redis_when_redis_empty_but_local_has_data(record_file, monkeypatch):
    record_file.write_text(SAMPLE_CSV, encoding="utf-8")
    monkeypatch.setattr(start, "_records_redis_restore", lambda: False)
    monkeypatch.setattr(start, "_obs_redis_get", lambda key: None)  # Redis has nothing yet
    save_calls = []
    monkeypatch.setattr(start, "_records_redis_save", lambda df: save_calls.append(df) or True)

    df = start._load_records()

    assert len(df) == 1
    assert len(save_calls) == 1  # existing local data got pushed to Redis


def test_load_records_does_not_redundantly_backfill_when_redis_already_populated(record_file, monkeypatch):
    record_file.write_text(SAMPLE_CSV, encoding="utf-8")
    monkeypatch.setattr(start, "_records_redis_restore", lambda: False)
    monkeypatch.setattr(start, "_obs_redis_get", lambda key: SAMPLE_CSV)  # Redis already has data
    save_calls = []
    monkeypatch.setattr(start, "_records_redis_save", lambda df: save_calls.append(df) or True)

    start._load_records()

    assert save_calls == []


def test_load_records_returns_empty_frame_when_no_local_and_no_redis(record_file, monkeypatch):
    monkeypatch.setattr(start, "_records_redis_restore", lambda: False)

    df = start._load_records()

    assert df.empty
    assert list(df.columns) == start.RECORD_COLUMNS


# ---------------------------------------------------------------------------
# add_record(): writes through to Redis, not just the local file
# ---------------------------------------------------------------------------

def test_add_record_writes_to_redis(record_file, monkeypatch, tmp_path):
    spots_file = tmp_path / "hoshiba_spots.csv"
    spots_file.write_text("name,lat,lon\nH_1631_1434,45.1631,141.1434\n", encoding="utf-8")
    monkeypatch.setattr(start, "CSV_FILE", str(spots_file))
    monkeypatch.setattr(start, "_records_redis_restore", lambda: False)
    monkeypatch.setattr(start, "_obs_redis_get", lambda key: None)

    redis_saves = []
    monkeypatch.setattr(start, "_records_redis_save", lambda df: redis_saves.append(df) or True)
    monkeypatch.setattr(start, "_record_forecast_feedback", lambda *a, **k: None)

    client = start.app.test_client()
    resp = client.post("/record", json={
        "name": "H_1631_1434", "date": "2026-08-04", "result": "完全乾燥",
    })

    assert resp.status_code == 200
    assert resp.get_json()["status"] == "success"
    assert len(redis_saves) == 1
    saved_df = redis_saves[-1]
    assert "H_1631_1434" in saved_df["name"].values


def test_add_record_still_succeeds_when_redis_save_fails(record_file, monkeypatch, tmp_path):
    """Redis being briefly unavailable must not block a fisherman from recording
    -- the local file write (already happening) is the last-resort fallback."""
    spots_file = tmp_path / "hoshiba_spots.csv"
    spots_file.write_text("name,lat,lon\nH_1631_1434,45.1631,141.1434\n", encoding="utf-8")
    monkeypatch.setattr(start, "CSV_FILE", str(spots_file))
    monkeypatch.setattr(start, "_records_redis_restore", lambda: False)
    monkeypatch.setattr(start, "_obs_redis_get", lambda key: None)
    monkeypatch.setattr(start, "_records_redis_save", lambda df: False)
    monkeypatch.setattr(start, "_record_forecast_feedback", lambda *a, **k: None)

    client = start.app.test_client()
    resp = client.post("/record", json={
        "name": "H_1631_1434", "date": "2026-08-04", "result": "完全乾燥",
    })

    assert resp.status_code == 200
    assert resp.get_json()["status"] == "success"
    assert record_file.exists()  # local write still happened


# ---------------------------------------------------------------------------
# delete_spot(): "has records" check must be Redis-aware, not a raw file read
# ---------------------------------------------------------------------------

def test_delete_spot_blocked_by_redis_only_record(record_file, monkeypatch, tmp_path):
    """
    2026-08-04: before this fix, delete_spot() read RECORD_FILE directly --
    if the local file had been wiped by a redeploy but Redis still had the
    record (or vice versa before restore ran), a spot with real drying
    history could be deleted. Must go through _load_records() instead.
    """
    spots_file = tmp_path / "hoshiba_spots.csv"
    spots_file.write_text("name,lat,lon\nH_1631_1434,45.1631,141.1434\n", encoding="utf-8")
    monkeypatch.setattr(start, "CSV_FILE", str(spots_file))
    assert not record_file.exists()  # local file wiped, e.g. by a redeploy

    import pandas as pd
    redis_backed_df = pd.DataFrame([{
        "date": "2026-07-01", "name": "H_1631_1434", "result": "完全乾燥",
        "stop_cause": None, "did_dry": True, "collection_time": None,
        "recorded_at": "2026-07-01T16:00:00+09:00", "correction_count": 0, "correction_reason": None,
    }])
    monkeypatch.setattr(start, "_load_records", lambda: redis_backed_df)
    monkeypatch.setattr(
        "line_integration.load_subscriptions",
        lambda: {}, raising=False,
    )

    client = start.app.test_client()
    resp = client.post("/delete", json={"name": "H_1631_1434"})

    body = resp.get_json()
    assert body["status"] == "error"
    assert "乾燥記録がある" in body.get("message", "") or any(
        "乾燥記録がある" in r for r in body.get("reasons", [])
    )


# ---------------------------------------------------------------------------
# delete_record() / list_recent_records(): admin-only mis-entry cleanup
# (added 2026-08-08 after a fisherman submitted a duplicate/mistaken record
# via LINE and asked for it to be removed -- there was previously no way to
# remove a row at all, only to overwrite its result via add_record()).
# ---------------------------------------------------------------------------

def test_delete_record_requires_admin_secret(record_file, monkeypatch):
    monkeypatch.setenv("LINE_ADMIN_NOTIFY_SECRET", "s3cret")
    client = start.app.test_client()
    resp = client.delete("/record/H_1631_1434/2026-08-04")
    assert resp.status_code == 401


def test_delete_record_removes_row_and_persists_to_redis(record_file, monkeypatch):
    monkeypatch.setenv("LINE_ADMIN_NOTIFY_SECRET", "s3cret")
    record_file.write_text(
        "date,name,result,stop_cause,did_dry,collection_time,recorded_at,correction_count,correction_reason\n"
        "2026-07-02,H_2480_2198,完全乾燥,,True,,2026-08-08T16:43:56+09:00,0,\n"
        "2026-06-29,H_2480_2198,完全乾燥,,True,,2026-06-29T16:00:00+09:00,0,\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(start, "_records_redis_restore", lambda: False)
    monkeypatch.setattr(start, "_obs_redis_get", lambda key: "dummy")  # skip _load_records() backfill save

    redis_saves = []
    monkeypatch.setattr(start, "_records_redis_save", lambda df: redis_saves.append(df) or True)

    client = start.app.test_client()
    resp = client.delete(
        "/record/H_2480_2198/2026-07-02",
        headers={"X-Admin-Secret": "s3cret"},
    )

    assert resp.status_code == 200
    body = resp.get_json()
    assert body["status"] == "success"
    assert body["removed"]["date"] == "2026-07-02"
    assert len(redis_saves) == 1
    remaining = redis_saves[-1]
    assert "2026-07-02" not in remaining["date"].values
    assert "2026-06-29" in remaining["date"].values


def test_delete_record_returns_404_when_not_found(record_file, monkeypatch):
    monkeypatch.setenv("LINE_ADMIN_NOTIFY_SECRET", "s3cret")
    record_file.write_text(
        "date,name,result,stop_cause,did_dry,collection_time,recorded_at,correction_count,correction_reason\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(start, "_records_redis_restore", lambda: False)

    client = start.app.test_client()
    resp = client.delete(
        "/record/H_9999_9999/2026-01-01",
        headers={"X-Admin-Secret": "s3cret"},
    )
    assert resp.status_code == 404


def test_list_recent_records_filters_by_recorded_at(record_file, monkeypatch):
    monkeypatch.setenv("LINE_ADMIN_NOTIFY_SECRET", "s3cret")
    record_file.write_text(
        "date,name,result,stop_cause,did_dry,collection_time,recorded_at,correction_count,correction_reason\n"
        "2026-08-08,H_1631_1434,完全乾燥,,True,,2026-08-08T16:00:00+09:00,0,\n"
        "2025-06-20,H_2065_1375,中止,,False,,2025-06-20T09:00:00+09:00,0,\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(start, "_records_redis_restore", lambda: False)
    monkeypatch.setattr(start, "_obs_redis_get", lambda key: None)
    monkeypatch.setattr(start, "_records_redis_save", lambda df: True)

    client = start.app.test_client()
    resp = client.get(
        "/api/records/recent?hours=24",
        headers={"X-Admin-Secret": "s3cret"},
    )

    assert resp.status_code == 200
    body = resp.get_json()
    assert body["status"] == "ok"
    assert body["count"] == 1
    assert body["records"][0]["name"] == "H_1631_1434"
