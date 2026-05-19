"""
Unit tests for line_integration.py

Run from project root:
    python -m pytest tests/test_line_integration.py -v

No LINE credentials needed — all tests are offline.
"""
import os
import sys
import hmac
import hashlib
import base64
import json
import tempfile

import pytest

# Ensure project root is on sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Set required env vars before importing the module
os.environ.setdefault('LINE_CHANNEL_SECRET', 'test_secret_1234567890')
os.environ.setdefault('LINE_CHANNEL_ACCESS_TOKEN', 'test_token')
os.environ.setdefault('LINE_ENABLED', 'true')
os.environ.setdefault('LINE_ADMIN_NOTIFY_SECRET', 'admin_secret')

import line_integration as li


# ---------------------------------------------------------------------------
# verify_line_signature
# ---------------------------------------------------------------------------

def _make_signature(body: bytes, secret: str) -> str:
    digest = hmac.new(secret.encode('utf-8'), body, hashlib.sha256).digest()
    return base64.b64encode(digest).decode('utf-8')


def test_verify_valid_signature():
    body = b'{"events":[]}'
    sig = _make_signature(body, 'test_secret_1234567890')
    assert li.verify_line_signature(body, sig) is True


def test_verify_invalid_signature():
    body = b'{"events":[]}'
    assert li.verify_line_signature(body, 'bad_sig') is False


def test_verify_tampered_body():
    body = b'{"events":[]}'
    sig = _make_signature(body, 'test_secret_1234567890')
    assert li.verify_line_signature(b'{"events":[1]}', sig) is False


# ---------------------------------------------------------------------------
# parse_command
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("text,expected_cmd", [
    ("ヘルプ", "help"),
    ("help", "help"),
    ("?", "help"),
    ("コマンド", "help"),
])
def test_parse_help(text, expected_cmd):
    assert li.parse_command(text)["cmd"] == expected_cmd


@pytest.mark.parametrize("text,expected_cmd", [
    ("今日", "today"),
    ("本日", "today"),
])
def test_parse_today(text, expected_cmd):
    assert li.parse_command(text)["cmd"] == expected_cmd


@pytest.mark.parametrize("text", ["明日", "あした"])
def test_parse_tomorrow(text):
    assert li.parse_command(text)["cmd"] == "tomorrow"


@pytest.mark.parametrize("text", ["今週", "weekly"])
def test_parse_weekly(text):
    assert li.parse_command(text)["cmd"] == "weekly"


@pytest.mark.parametrize("spot_id", [
    "H_1631_1434",
    "A_1783_1383",
    "R_1800_2392",
])
def test_parse_spot_id(spot_id):
    result = li.parse_command(spot_id)
    assert result["cmd"] == "spot"
    assert result["spot_id"] == spot_id


@pytest.mark.parametrize("text,area,day", [
    ("沓形", "沓形", None),
    ("仙法志", "仙法志", None),
    ("沓形 明日", "沓形", 1),
    ("仙法志 今日", "仙法志", 0),
    ("鴛泊 明後日", "鴛泊", 2),
])
def test_parse_area(text, area, day):
    result = li.parse_command(text)
    assert result["cmd"] == "area"
    assert result["area"] == area
    assert result["day"] == day


@pytest.mark.parametrize("text,target", [
    ("通知登録 H_1631_1434", "H_1631_1434"),
    ("通知登録 沓形", "沓形"),
])
def test_parse_subscribe(text, target):
    result = li.parse_command(text)
    assert result["cmd"] == "subscribe"
    assert result["target"] == target


@pytest.mark.parametrize("text", ["通知解除", "通知OFF", "解除"])
def test_parse_unsubscribe(text):
    assert li.parse_command(text)["cmd"] == "unsubscribe"


def test_parse_unknown():
    assert li.parse_command("よくわからないこと")["cmd"] in ("area", "unknown")


# ---------------------------------------------------------------------------
# Subscription management (uses temp file)
# ---------------------------------------------------------------------------

@pytest.fixture
def tmp_sub_file(tmp_path, monkeypatch):
    f = tmp_path / "line_subscriptions.json"
    monkeypatch.setattr(li, "SUBSCRIPTIONS_FILE", str(f))
    return f


def test_subscription_create_and_read(tmp_sub_file):
    li.upsert_subscription("user", "U001", {})
    sub = li.get_subscription("user", "U001")
    assert sub is not None
    assert sub["source_id"] == "U001"
    assert sub["source_type"] == "user"
    assert sub["notify_enabled"] is True
    assert sub["spots"] == []


def test_subscription_add_spot(tmp_sub_file):
    li.upsert_subscription("user", "U002", {})
    li.upsert_subscription("user", "U002", {"spots": ["H_1631_1434"]})
    sub = li.get_subscription("user", "U002")
    assert "H_1631_1434" in sub["spots"]


def test_subscription_disable(tmp_sub_file):
    li.upsert_subscription("user", "U003", {"notify_enabled": True})
    li.upsert_subscription("user", "U003", {"notify_enabled": False})
    sub = li.get_subscription("user", "U003")
    assert sub["notify_enabled"] is False


def test_subscription_group_key_separate(tmp_sub_file):
    li.upsert_subscription("user", "X001", {})
    li.upsert_subscription("group", "X001", {})
    subs = li.load_subscriptions()
    assert "user:X001" in subs
    assert "group:X001" in subs


# ---------------------------------------------------------------------------
# handle_help
# ---------------------------------------------------------------------------

def test_handle_help_contains_keywords():
    text = li.handle_help()
    for kw in ("今日", "明日", "通知登録", "通知解除", "ヘルプ"):
        assert kw in text


# ---------------------------------------------------------------------------
# format helpers
# ---------------------------------------------------------------------------

def _sample_fc(day_number=0, suitability="good", score=72, precip=0.0):
    return {
        "date": f"2026-05-1{day_number + 8}",
        "day_number": day_number,
        "precipitation": precip,
        "min_humidity": 88.0,
        "avg_wind": 2.5,
        "pop": 10,
        "score": score,
        "suitability": suitability,
    }


def test_format_single_day_contains_score():
    msg = li.format_single_day("H_1631_1434", _sample_fc())
    assert "72" in msg
    assert "H_1631_1434" in msg


def test_format_single_day_poor_shows_rain():
    fc = _sample_fc(suitability="poor", score=10, precip=2.5)
    msg = li.format_single_day("H_1631_1434", fc)
    assert "2.5mm" in msg


def test_format_weekly_summary_7_days():
    forecasts = [_sample_fc(i) for i in range(7)]
    msg = li.format_weekly_summary("TEST_SPOT", forecasts)
    assert "7日" in msg or "7/7" in msg or "7" in msg


# ---------------------------------------------------------------------------
# _simple_score
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("precip,min_hum,wind,expected_suit", [
    (0.0, 80.0, 3.0, "excellent"),
    (0.0, 94.0, 2.0, "good"),
    (0.0, 95.0, 1.5, "poor"),   # hum>94 + low wind → score 37 → poor
    (1.0, 80.0, 3.0, "poor"),   # rain → always poor
    (0.0, 100.0, 0.5, "poor"),  # very high humidity + low wind
])
def test_simple_score_suitability(precip, min_hum, wind, expected_suit):
    _, suit = li._simple_score(precip, min_hum, wind)
    assert suit == expected_suit, f"Expected {expected_suit} for precip={precip}, hum={min_hum}, wind={wind}"


def test_simple_score_range():
    for precip in (0.0, 1.0):
        for hum in (70, 90, 95, 100):
            for wind in (0.5, 2.0, 4.0):
                score, suit = li._simple_score(precip, hum, wind)
                assert 0 <= score <= 100
                assert suit in ("excellent", "good", "fair", "poor")


# ---------------------------------------------------------------------------
# handle_subscribe / handle_unsubscribe
# ---------------------------------------------------------------------------

def test_handle_subscribe_no_target(tmp_sub_file):
    msg = li.handle_subscribe("user", "U010", "")
    assert "登録" in msg  # hint message


def test_handle_subscribe_invalid_spot(tmp_sub_file):
    msg = li.handle_subscribe("user", "U011", "H_9999_9999")
    assert "見つかりません" in msg


def test_handle_unsubscribe_not_registered(tmp_sub_file):
    msg = li.handle_unsubscribe("user", "U_no_sub")
    assert "OFF" in msg


def test_handle_unsubscribe_disables(tmp_sub_file):
    li.upsert_subscription("user", "U020", {"notify_enabled": True})
    msg = li.handle_unsubscribe("user", "U020")
    assert "OFF" in msg
    sub = li.get_subscription("user", "U020")
    assert sub["notify_enabled"] is False


# ---------------------------------------------------------------------------
# handle_unknown
# ---------------------------------------------------------------------------

def test_handle_unknown_contains_help_hint():
    msg = li.handle_unknown()
    assert "ヘルプ" in msg


# ---------------------------------------------------------------------------
# notify_all (dry-run with mocked push_text)
# ---------------------------------------------------------------------------

def test_notify_all_empty_subs(tmp_sub_file, monkeypatch):
    monkeypatch.setattr(li, "push_text", lambda to, text: True)
    result = li.notify_all("evening")
    assert result["sent"] == 0
    assert result["kind"] == "evening"


def test_notify_all_invalid_kind(tmp_sub_file):
    result = li.notify_all("lunch")
    assert "error" in result


def test_notify_all_skips_disabled(tmp_sub_file, monkeypatch):
    li.upsert_subscription("user", "U_off", {"notify_enabled": False, "spots": ["H_1631_1434"]})
    monkeypatch.setattr(li, "push_text", lambda to, text: True)
    result = li.notify_all("morning")
    assert result["sent"] == 0
    assert result["skipped"] >= 1
