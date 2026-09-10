"""
Tests for feedback_log.csv's Redis save/restore compression (2026-09-10 fix)
and its 365-day archive/prune job (also 2026-09-10).

Background: feedback_log.csv is saved to Redis as a whole-CSV-string blob on
every accuracy update (_feedback_log_redis_save), the same pattern as
hoshiba_records.csv (see tests/test_records_persistence.py, which covers the
shared _redis_blob_encode/_redis_blob_decode helpers in more depth). By
2026-09-01 the file had grown to 8,829,889 characters (~8.8MB) and every
subsequent Redis SET silently failed against Upstash's free-tier 10MB "Max
Request Size" limit -- confirmed live via repeated "Max Request Size Limit"
emails from Upstash (2026-09-01, 09-03, 09-06, 09-09) and a
_check_redis_persistence() reading that stayed frozen at exactly 8,829,889
chars across all of that period, meaning every Render redeploy since
2026-09-01 was silently restoring that stale 09-01 snapshot instead of the
day's actual accuracy data. The fix compresses the blob with gzip+base64
before sending it, buying back an order of magnitude of headroom.

Compression alone doesn't stop the file from growing forever, so
_archive_and_prune_old_feedback_rows() was added the same day: every API
that reads feedback_log.csv clamps its `days` parameter to a maximum of 365
(three separate call sites), so any row older than that is provably never
read by any existing endpoint again. That job moves such rows to a separate
feedback_log:archive:csv Redis key (10-year TTL, effectively permanent) and
only then removes them from the live file -- the user explicitly asked for
an archive-before-delete design rather than outright deletion, and for it to
run as part of the existing 05:00 JST integrity-check thread rather than a
new one.

Run from project root:
    python -m pytest tests/test_feedback_log_redis_persistence.py -v
"""
from datetime import timedelta
from io import StringIO

import pandas as pd
import pytest

import start


SAMPLE_FEEDBACK_CSV = (
    "date,spot_name,days_ahead,has_drying_record,judgment_correct\n"
    "2026-07-14,H_2480_2198,0,True,True\n"
)


def _days_ago(n):
    return (start.datetime.now(tz=start.JST) - timedelta(days=n)).strftime("%Y-%m-%d")


@pytest.fixture
def feedback_file(tmp_path, monkeypatch):
    path = tmp_path / "feedback_log.csv"
    monkeypatch.setattr(start, "FEEDBACK_FILE", str(path))
    return path


def test_feedback_log_redis_save_sends_compressed_blob_not_raw_csv(monkeypatch):
    """The exact fix: the Redis payload must be the gzip+base64 blob, not
    the raw CSV text, so a large feedback_log.csv doesn't hit Upstash's
    10MB request-size cap the way it did from 2026-09-01 onward."""
    calls = []
    monkeypatch.setattr(
        start, "_obs_redis_set",
        lambda key, data, ttl=None: calls.append((key, data, ttl)) or True,
    )
    df = pd.read_csv(StringIO(SAMPLE_FEEDBACK_CSV))

    ok = start._feedback_log_redis_save(df)

    assert ok is True
    assert len(calls) == 1
    key, data, ttl = calls[0]
    assert key == start._FEEDBACK_REDIS_KEY
    assert data != df.to_csv(index=False)  # not the raw CSV -- it's compressed
    assert "H_2480_2198" in start._redis_blob_decode(data)
    assert ttl == start._FEEDBACK_REDIS_TTL


def test_feedback_log_redis_restore_decompresses_new_format(feedback_file, monkeypatch):
    blob = start._redis_blob_encode(SAMPLE_FEEDBACK_CSV)
    monkeypatch.setattr(start, "_obs_redis_get", lambda key: blob)

    restored = start._feedback_log_redis_restore()

    assert restored is True
    assert feedback_file.read_text(encoding="utf-8") == SAMPLE_FEEDBACK_CSV


def test_feedback_log_redis_restore_still_reads_legacy_uncompressed_value(feedback_file, monkeypatch):
    """Backward compatibility: any value saved by the pre-2026-09-10 code
    (plain uncompressed CSV, e.g. the stale 2026-09-01 snapshot every
    redeploy had been restoring) must still restore correctly."""
    monkeypatch.setattr(start, "_obs_redis_get", lambda key: SAMPLE_FEEDBACK_CSV)

    restored = start._feedback_log_redis_restore()

    assert restored is True
    assert feedback_file.read_text(encoding="utf-8") == SAMPLE_FEEDBACK_CSV


def test_feedback_log_redis_restore_skips_when_local_file_already_exists(feedback_file, monkeypatch):
    feedback_file.write_text("existing local data\n", encoding="utf-8")
    monkeypatch.setattr(start, "_obs_redis_get", lambda key: start._redis_blob_encode(SAMPLE_FEEDBACK_CSV))

    restored = start._feedback_log_redis_restore()

    assert restored is False
    assert feedback_file.read_text(encoding="utf-8") == "existing local data\n"


def test_check_redis_persistence_reports_decompressed_size(monkeypatch):
    """_check_redis_persistence()'s feedback_log_csv.size_chars must keep
    meaning "decompressed CSV character count" -- the same semantics as
    the pre-compression baseline recorded in ai_review_agents/AI_MEMORY.md
    (8,829,889 chars on 2026-09-01) -- not the much smaller compressed
    blob size, which would look like a false data-loss alarm."""
    monkeypatch.setattr(start, "_obs_redis_get", lambda key: start._redis_blob_encode(SAMPLE_FEEDBACK_CSV) if key == start._FEEDBACK_REDIS_KEY else None)
    monkeypatch.setattr(start, "_compare_amedas_full_weather", lambda date_str: {})
    monkeypatch.setattr(start, "_obs_redis_scan_keys", lambda pattern: [])

    result = start._check_redis_persistence("20260714")

    assert result["checks"]["feedback_log_csv"]["ok"] is True
    assert result["checks"]["feedback_log_csv"]["size_chars"] == len(SAMPLE_FEEDBACK_CSV)


# ---------------------------------------------------------------------------
# _archive_and_prune_old_feedback_rows() (2026-09-10)
# ---------------------------------------------------------------------------

def test_prune_no_feedback_file_is_a_noop(feedback_file):
    assert not feedback_file.exists()

    result = start._archive_and_prune_old_feedback_rows()

    assert result == {"ok": True, "archived": 0, "note": "feedback_log.csv なし"}


def test_prune_leaves_recent_rows_untouched(feedback_file, monkeypatch):
    csv = (
        "date,spot_name,days_ahead,has_drying_record,judgment_correct\n"
        f"{_days_ago(10)},H_2480_2198,0,True,True\n"
        f"{_days_ago(300)},H_2480_2198,0,True,True\n"
    )
    feedback_file.write_text(csv, encoding="utf-8")
    monkeypatch.setattr(start, "_obs_redis_get", lambda key: None)
    save_calls = []
    monkeypatch.setattr(start, "_feedback_log_redis_save", lambda df: save_calls.append(df) or True)

    result = start._archive_and_prune_old_feedback_rows()

    assert result == {"ok": True, "archived": 0, "note": "365日超の行なし"}
    assert feedback_file.read_text(encoding="utf-8") == csv
    assert save_calls == []  # nothing changed -- no need to re-save


def test_prune_archives_then_removes_rows_older_than_365_days(feedback_file, monkeypatch):
    """The core behavior: a row older than the retention window is moved to
    the archive key and disappears from the live file, but a recent row in
    the same file is left alone."""
    old_row = f"{_days_ago(400)},H_OLD_SPOT,0,True,True\n"
    recent_row = f"{_days_ago(10)},H_2480_2198,0,True,True\n"
    csv = "date,spot_name,days_ahead,has_drying_record,judgment_correct\n" + old_row + recent_row
    feedback_file.write_text(csv, encoding="utf-8")
    monkeypatch.setattr(start, "_obs_redis_get", lambda key: None)  # no existing archive yet
    archive_calls = []
    monkeypatch.setattr(
        start, "_obs_redis_set",
        lambda key, data, ttl=None: archive_calls.append((key, data, ttl)) or True,
    )
    saved = []
    monkeypatch.setattr(start, "_feedback_log_redis_save", lambda df: saved.append(df) or True)

    result = start._archive_and_prune_old_feedback_rows()

    assert result == {"ok": True, "archived": 1, "remaining": 1}
    remaining_csv = feedback_file.read_text(encoding="utf-8")
    assert "H_OLD_SPOT" not in remaining_csv
    assert "H_2480_2198" in remaining_csv

    assert len(archive_calls) == 1
    archive_key, archive_blob, archive_ttl = archive_calls[0]
    assert archive_key == start._FEEDBACK_ARCHIVE_REDIS_KEY
    assert archive_ttl == start._FEEDBACK_ARCHIVE_REDIS_TTL
    assert "H_OLD_SPOT" in start._redis_blob_decode(archive_blob)

    assert len(saved) == 1  # feedback_log.csv re-saved to Redis with the trimmed rows
    assert "H_OLD_SPOT" not in saved[0].to_csv(index=False)


def test_prune_merges_into_existing_archive_without_duplicating(feedback_file, monkeypatch):
    """A second run must append to (not overwrite) whatever's already in the
    archive, and must not duplicate a row the archive already has."""
    already_archived = (
        "date,spot_name,days_ahead,has_drying_record,judgment_correct\n"
        f"{_days_ago(500)},H_ANCIENT,0,True,True\n"
    )
    monkeypatch.setattr(start, "_obs_redis_get", lambda key: start._redis_blob_encode(already_archived))
    new_old_row = f"{_days_ago(400)},H_OLD_SPOT,0,True,True\n"
    csv = "date,spot_name,days_ahead,has_drying_record,judgment_correct\n" + new_old_row
    feedback_file.write_text(csv, encoding="utf-8")
    archive_calls = []
    monkeypatch.setattr(
        start, "_obs_redis_set",
        lambda key, data, ttl=None: archive_calls.append((key, data, ttl)) or True,
    )
    monkeypatch.setattr(start, "_feedback_log_redis_save", lambda df: True)

    result = start._archive_and_prune_old_feedback_rows()

    assert result["ok"] is True
    merged = start._redis_blob_decode(archive_calls[0][1])
    assert "H_ANCIENT" in merged  # previously archived row preserved
    assert "H_OLD_SPOT" in merged  # newly archived row added
    assert merged.count("H_ANCIENT") == 1  # not duplicated


def test_prune_keeps_rows_with_unparseable_dates_rather_than_dropping_them(feedback_file, monkeypatch):
    """A row whose date can't be parsed must not be silently destroyed --
    err on the side of keeping data whose age is unknown."""
    csv = (
        "date,spot_name,days_ahead,has_drying_record,judgment_correct\n"
        "not-a-date,H_BROKEN,0,True,True\n"
    )
    feedback_file.write_text(csv, encoding="utf-8")
    monkeypatch.setattr(start, "_obs_redis_get", lambda key: None)
    monkeypatch.setattr(start, "_feedback_log_redis_save", lambda df: True)

    result = start._archive_and_prune_old_feedback_rows()

    assert result["archived"] == 0
    assert "H_BROKEN" in feedback_file.read_text(encoding="utf-8")


def test_prune_skips_deletion_when_archive_write_fails(feedback_file, monkeypatch):
    """If the archive write fails, the old rows must stay in the live file
    rather than being lost -- data safety over storage savings."""
    old_row = f"{_days_ago(400)},H_OLD_SPOT,0,True,True\n"
    csv = "date,spot_name,days_ahead,has_drying_record,judgment_correct\n" + old_row
    feedback_file.write_text(csv, encoding="utf-8")
    monkeypatch.setattr(start, "_obs_redis_get", lambda key: None)
    monkeypatch.setattr(start, "_obs_redis_set", lambda key, data, ttl=None: False)
    save_calls = []
    monkeypatch.setattr(start, "_feedback_log_redis_save", lambda df: save_calls.append(df) or True)

    result = start._archive_and_prune_old_feedback_rows()

    assert result["ok"] is False
    assert feedback_file.read_text(encoding="utf-8") == csv  # untouched
    assert save_calls == []  # never re-saved a (would-be-incorrect) trimmed version
