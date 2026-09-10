"""
Tests for feedback_log.csv's Redis save/restore compression (2026-09-10 fix).

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

Run from project root:
    python -m pytest tests/test_feedback_log_redis_persistence.py -v
"""
from io import StringIO

import pandas as pd
import pytest

import start


SAMPLE_FEEDBACK_CSV = (
    "date,spot_name,days_ahead,has_drying_record,judgment_correct\n"
    "2026-07-14,H_2480_2198,0,True,True\n"
)


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
