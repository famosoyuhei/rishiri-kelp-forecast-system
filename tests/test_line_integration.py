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
    from datetime import datetime, timezone, timedelta
    JST = timezone(timedelta(hours=9))
    class _FakeDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 7, 1, 12, 0, 0, tzinfo=JST)
    monkeypatch.setattr(li, "datetime", _FakeDatetime)
    li.upsert_subscription("user", "U_off", {"notify_enabled": False, "spots": ["H_1631_1434"]})
    monkeypatch.setattr(li, "push_text", lambda to, text: True)
    result = li.notify_all("morning")
    assert result["sent"] == 0
    assert result["skipped"] >= 1


def test_notify_all_out_of_season(tmp_sub_file, monkeypatch):
    """notify_all returns out_of_season when current JST month is outside 6-9."""
    from datetime import datetime, timezone, timedelta
    JST = timezone(timedelta(hours=9))
    # Patch datetime.now to return January (month=1)
    class _FakeDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 1, 15, 12, 0, 0, tzinfo=JST)
    monkeypatch.setattr(li, "datetime", _FakeDatetime)
    result = li.notify_all("evening")
    assert result.get("reason") == "out_of_season"
    assert result["sent"] == 0


def test_notify_all_in_season(tmp_sub_file, monkeypatch):
    """notify_all proceeds (no out_of_season) when JST month is in 6-9."""
    from datetime import datetime, timezone, timedelta
    JST = timezone(timedelta(hours=9))
    class _FakeDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 7, 1, 12, 0, 0, tzinfo=JST)
    monkeypatch.setattr(li, "datetime", _FakeDatetime)
    monkeypatch.setattr(li, "push_text", lambda to, text: True)
    result = li.notify_all("evening")
    assert result.get("reason") != "out_of_season"


# ---------------------------------------------------------------------------
# parse_command — new commands
# ---------------------------------------------------------------------------

def test_parse_set_nogo_no_date():
    assert li.parse_command("沖止め") == {"cmd": "set_nogo", "date": None}


def test_parse_set_nogo_with_date():
    r = li.parse_command("沖止め 6/25")
    assert r["cmd"] == "set_nogo"
    assert r["date"] == "6/25"


def test_parse_cancel_nogo():
    assert li.parse_command("沖止め解除") == {"cmd": "cancel_nogo"}


def test_parse_set_season_start():
    r = li.parse_command("漁期開始 6/15")
    assert r["cmd"] == "set_season_start"
    assert r["date"] == "6/15"


def test_parse_set_season_end():
    r = li.parse_command("漁期終了 9/5")
    assert r["cmd"] == "set_season_end"
    assert r["date"] == "9/5"


def test_parse_show_settings():
    assert li.parse_command("設定確認") == {"cmd": "show_settings"}


# ---------------------------------------------------------------------------
# _parse_date_arg
# ---------------------------------------------------------------------------

def test_parse_date_arg_mm_dd():
    result = li._parse_date_arg("6/25")
    assert result is not None
    assert result.endswith("-06-25") or "-06-25" in result


def test_parse_date_arg_full():
    result = li._parse_date_arg("2026/6/25")
    assert result == "2026-06-25"


def test_parse_date_arg_invalid():
    assert li._parse_date_arg("abc") is None


# ---------------------------------------------------------------------------
# handle_set_nogo / handle_cancel_nogo
# ---------------------------------------------------------------------------

def test_handle_set_nogo_tomorrow(tmp_sub_file):
    li.upsert_subscription("user", "U1", {"notify_enabled": True, "spots": ["H_1631_1434"]})
    result = li.handle_set_nogo("user", "U1", None)
    assert "沖止め" in result or "✓" in result
    sub = li.get_subscription("user", "U1")
    assert len(sub.get("nogo_dates", [])) == 1


def test_handle_set_nogo_specific_date(tmp_sub_file):
    li.upsert_subscription("user", "U1", {"notify_enabled": True, "spots": ["H_1631_1434"]})
    result = li.handle_set_nogo("user", "U1", "2026/8/15")
    assert "✓" in result
    sub = li.get_subscription("user", "U1")
    assert "2026-08-15" in sub.get("nogo_dates", [])


def test_handle_cancel_nogo_removes_nearest(tmp_sub_file):
    li.upsert_subscription("user", "U1", {
        "notify_enabled": True,
        "spots": ["H_1631_1434"],
        "nogo_dates": ["2026-08-10", "2026-08-20"],
    })
    result = li.handle_cancel_nogo("user", "U1")
    assert "✓" in result
    sub = li.get_subscription("user", "U1")
    assert "2026-08-10" not in sub.get("nogo_dates", [])


def test_handle_cancel_nogo_none(tmp_sub_file):
    li.upsert_subscription("user", "U1", {"notify_enabled": True})
    result = li.handle_cancel_nogo("user", "U1")
    assert "ありません" in result


# ---------------------------------------------------------------------------
# handle_set_season_start / handle_set_season_end
# ---------------------------------------------------------------------------

def test_handle_set_season_start(tmp_sub_file):
    li.upsert_subscription("user", "U1", {"notify_enabled": True})
    result = li.handle_set_season_start("user", "U1", "6/15")
    assert "✓" in result
    sub = li.get_subscription("user", "U1")
    assert sub.get("season_start") == "06-15"


def test_handle_set_season_end(tmp_sub_file):
    li.upsert_subscription("user", "U1", {"notify_enabled": True})
    result = li.handle_set_season_end("user", "U1", "9/5")
    assert "✓" in result
    sub = li.get_subscription("user", "U1")
    assert sub.get("season_end") == "09-05"


def test_handle_set_season_invalid_date(tmp_sub_file):
    li.upsert_subscription("user", "U1", {"notify_enabled": True})
    result = li.handle_set_season_start("user", "U1", "abc")
    assert "正しくありません" in result


# ---------------------------------------------------------------------------
# notify_all — nogo / personal season skip
# ---------------------------------------------------------------------------

def _in_season_datetime():
    """Returns a _FakeDatetime class fixed at 2026-07-01 12:00 JST."""
    from datetime import datetime, timezone, timedelta
    JST = timezone(timedelta(hours=9))
    class _FakeDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 7, 1, 12, 0, 0, tzinfo=JST)
    return _FakeDatetime


def test_notify_all_skips_nogo_date(tmp_sub_file, monkeypatch):
    """Subscriber with nogo_dates matching target day is skipped."""
    monkeypatch.setattr(li, "datetime", _in_season_datetime())
    monkeypatch.setattr(li, "push_text", lambda to, text: True)
    li.upsert_subscription("user", "U1", {
        "notify_enabled": True,
        "spots": ["H_1631_1434"],
        "nogo_dates": ["2026-07-02"],  # evening → target is 2026-07-02
    })
    result = li.notify_all("evening")
    assert result["skipped"] >= 1
    assert result["sent"] == 0


def test_notify_all_skips_before_season_start(tmp_sub_file, monkeypatch):
    """Subscriber with season_start after target date is skipped."""
    monkeypatch.setattr(li, "datetime", _in_season_datetime())
    monkeypatch.setattr(li, "push_text", lambda to, text: True)
    li.upsert_subscription("user", "U1", {
        "notify_enabled": True,
        "spots": ["H_1631_1434"],
        "season_start": "07-10",  # starts 7/10, but target is 7/2 (evening)
    })
    result = li.notify_all("evening")
    assert result["skipped"] >= 1
    assert result["sent"] == 0


def test_notify_all_skips_after_season_end(tmp_sub_file, monkeypatch):
    """Subscriber with season_end before target date is skipped."""
    monkeypatch.setattr(li, "datetime", _in_season_datetime())
    monkeypatch.setattr(li, "push_text", lambda to, text: True)
    li.upsert_subscription("user", "U1", {
        "notify_enabled": True,
        "spots": ["H_1631_1434"],
        "season_end": "06-30",  # ended 6/30, but today morning target is 7/1
    })
    result = li.notify_all("morning")
    assert result["skipped"] >= 1
    assert result["sent"] == 0


# ---------------------------------------------------------------------------
# handle_show_settings
# ---------------------------------------------------------------------------

def test_handle_show_settings_no_sub(tmp_sub_file):
    result = li.handle_show_settings("user", "UNKNOWN")
    assert "見つかりません" in result


def test_handle_show_settings_displays_info(tmp_sub_file):
    li.upsert_subscription("user", "U1", {
        "notify_enabled": True,
        "spots": ["H_1631_1434"],
        "season_start": "06-15",
        "season_end": "09-05",
        "nogo_dates": ["2026-08-10"],
    })
    result = li.handle_show_settings("user", "U1")
    assert "6/15" in result
    assert "9/5" in result or "09-05" in result.replace('/', '-')
    assert "8/10" in result


# ---------------------------------------------------------------------------
# Notification footer present in push messages
# ---------------------------------------------------------------------------

def test_notify_footer_in_push(tmp_sub_file, monkeypatch):
    """Push notification message contains the settings footer."""
    monkeypatch.setattr(li, "datetime", _in_season_datetime())
    pushed = []
    monkeypatch.setattr(li, "push_text", lambda to, text: pushed.append(text) or True)
    monkeypatch.setattr(li, "find_spot_by_id",
                        lambda sid: {"name": sid, "lat": 45.1631, "lon": 141.1434})
    monkeypatch.setattr(li, "get_forecast_for_spot", lambda lat, lon: [
        {"date": "2026-07-01", "day_number": 0, "precipitation": 0.0,
         "min_humidity": 80.0, "avg_wind": 3.0, "pop": None,
         "score": 90, "suitability": "excellent"},
        {"date": "2026-07-02", "day_number": 1, "precipitation": 0.0,
         "min_humidity": 80.0, "avg_wind": 3.0, "pop": None,
         "score": 90, "suitability": "excellent"},
    ])
    li.upsert_subscription("user", "U1", {
        "notify_enabled": True,
        "spots": ["H_1631_1434"],
    })
    li.notify_all("evening")
    assert pushed, "No push was sent"
    assert "沖止め" in pushed[0]
    assert "設定確認" in pushed[0]


# ---------------------------------------------------------------------------
# parse_command — record commands
# ---------------------------------------------------------------------------

def test_parse_record_start():
    assert li.parse_command("記録") == {"cmd": "record_start"}

def test_parse_register_spot():
    r = li.parse_command("干場登録 浜の前 H_1631_1434")
    assert r["cmd"] == "register_spot"
    assert r["nickname"] == "浜の前"
    assert r["spot_id"] == "H_1631_1434"

def test_parse_list_spots():
    assert li.parse_command("干場一覧") == {"cmd": "list_spots"}


# ---------------------------------------------------------------------------
# Spot nickname registration
# ---------------------------------------------------------------------------

def test_register_spot_nickname(tmp_sub_file, monkeypatch):
    monkeypatch.setattr(li, "find_spot_by_id",
                        lambda sid: {"name": sid, "lat": 45.1631, "lon": 141.1434})
    result = li.handle_register_spot_nickname("user", "U1", "浜の前", "H_1631_1434")
    assert "✓" in result
    sub = li.get_subscription("user", "U1")
    assert sub["spot_nicknames"]["浜の前"] == "H_1631_1434"

def test_register_spot_invalid_id(tmp_sub_file):
    result = li.handle_register_spot_nickname("user", "U1", "浜の前", "INVALID")
    assert "形式" in result

def test_list_spots_none(tmp_sub_file):
    li.upsert_subscription("user", "U1", {"notify_enabled": True})
    result = li.handle_list_spots("user", "U1")
    assert "ニックネームが登録されていません" in result

def test_list_spots_with_nicknames(tmp_sub_file):
    li.upsert_subscription("user", "U1", {
        "notify_enabled": True,
        "spot_nicknames": {"浜の前": "H_1631_1434"},
    })
    result = li.handle_list_spots("user", "U1")
    assert "浜の前" in result
    assert "H_1631_1434" in result


def test_register_spot_nickname_replaces_old_name(tmp_sub_file, monkeypatch):
    """Same user registering a new nickname for an already-named spot replaces the old one."""
    monkeypatch.setattr(li, "find_spot_by_id",
                        lambda sid: {"name": sid, "lat": 45.1, "lon": 141.1})
    li.upsert_subscription("user", "U1", {
        "spot_nicknames": {"浜の前": "H_1631_1434"},
    })
    result = li.handle_register_spot_nickname("user", "U1", "砂浜", "H_1631_1434")
    assert "浜の前" in result and "砂浜" in result  # shows rename
    sub = li.get_subscription("user", "U1")
    nicks = sub["spot_nicknames"]
    assert "砂浜" in nicks
    assert "浜の前" not in nicks  # old name removed


def test_register_spot_nickname_different_users_independent(tmp_sub_file, monkeypatch):
    """Two users can have different nicknames for the same spot without interference."""
    monkeypatch.setattr(li, "find_spot_by_id",
                        lambda sid: {"name": sid, "lat": 45.1, "lon": 141.1})
    li.handle_register_spot_nickname("user", "UserA", "浜の前", "H_1631_1434")
    li.handle_register_spot_nickname("user", "UserB", "山の下", "H_1631_1434")
    subA = li.get_subscription("user", "UserA")
    subB = li.get_subscription("user", "UserB")
    assert subA["spot_nicknames"].get("浜の前") == "H_1631_1434"
    assert subB["spot_nicknames"].get("山の下") == "H_1631_1434"
    assert "山の下" not in subA["spot_nicknames"]
    assert "浜の前" not in subB["spot_nicknames"]


# ---------------------------------------------------------------------------
# _parse_date_for_record
# ---------------------------------------------------------------------------

def test_parse_date_for_record_today():
    result = li._parse_date_for_record("今日")
    from datetime import datetime, timezone, timedelta
    today = datetime.now(li.JST).strftime("%Y-%m-%d")
    assert result == today

def test_parse_date_for_record_yesterday():
    result = li._parse_date_for_record("昨日")
    from datetime import datetime, timezone, timedelta
    yesterday = (datetime.now(li.JST) - timedelta(days=1)).strftime("%Y-%m-%d")
    assert result == yesterday

def test_parse_date_for_record_future():
    result = li._parse_date_for_record("2099/12/31")
    assert result == "future"

def test_parse_date_for_record_invalid():
    assert li._parse_date_for_record("abc") is None


# ---------------------------------------------------------------------------
# Record flow state machine (full happy path)
# ---------------------------------------------------------------------------

def test_record_flow_happy_path_good_result(tmp_sub_file, tmp_path, monkeypatch):
    """Full flow: 記録 → spot → date → good result → confirm → done."""
    monkeypatch.setattr(li, "RECORDS_CSV", str(tmp_path / "records.csv"))
    monkeypatch.setattr(li, "find_spot_by_id",
                        lambda sid: {"name": sid, "lat": 45.1631, "lon": 141.1434} if sid == "H_1631_1434" else None)
    li.upsert_subscription("user", "U1", {
        "notify_enabled": True,
        "spot_nicknames": {"浜の前": "H_1631_1434"},
    })

    # Step 1: start
    r1 = li.handle_record_start("user", "U1")
    assert "浜の前" in r1
    assert li.get_pending_action("user", "U1") is not None

    # Step 2: spot name
    r2 = li.handle_record_flow("user", "U1", "浜の前")
    assert "浜の前" in r2
    assert li.get_pending_action("user", "U1")["step"] == "ask_date"

    # Step 3: date
    r3 = li.handle_record_flow("user", "U1", "今日")
    assert "乾燥結果" in r3
    assert li.get_pending_action("user", "U1")["step"] == "ask_result"

    # Step 4: result (good → skip stop_cause)
    r4 = li.handle_record_flow("user", "U1", "1")  # 完全乾燥
    assert "完全乾燥" in r4
    assert li.get_pending_action("user", "U1")["step"] == "confirm"

    # Step 5: confirm
    r5 = li.handle_record_flow("user", "U1", "確定")
    assert "記録しました" in r5
    assert li.get_pending_action("user", "U1") is None

    # CSV written
    import csv as _csv
    with open(str(tmp_path / "records.csv"), encoding="utf-8") as f:
        rows = list(_csv.DictReader(f))
    assert len(rows) == 1
    assert rows[0]["result"] == "完全乾燥"
    assert rows[0]["name"] == "H_1631_1434"


def test_record_flow_poor_result_asks_stop_cause(tmp_sub_file, tmp_path, monkeypatch):
    """Poor result triggers stop_cause question."""
    monkeypatch.setattr(li, "RECORDS_CSV", str(tmp_path / "records.csv"))
    monkeypatch.setattr(li, "find_spot_by_id",
                        lambda sid: {"name": sid, "lat": 45.1, "lon": 141.1})
    li.upsert_subscription("user", "U1", {
        "spot_nicknames": {"テスト": "H_1631_1434"},
    })
    li.handle_record_start("user", "U1")
    li.handle_record_flow("user", "U1", "テスト")
    li.handle_record_flow("user", "U1", "昨日")

    r = li.handle_record_flow("user", "U1", "4")  # ほぼ乾燥なし
    assert "原因" in r
    assert li.get_pending_action("user", "U1")["step"] == "ask_stop_cause"

    r2 = li.handle_record_flow("user", "U1", "2")  # 霧
    assert "霧" in r2 or "確認" in r2 or "記録" in r2
    assert li.get_pending_action("user", "U1")["step"] == "confirm"


def test_record_flow_cancel(tmp_sub_file):
    """キャンセル clears pending action."""
    li.upsert_subscription("user", "U1", {"spot_nicknames": {}})
    li.handle_record_start("user", "U1")
    r = li.handle_record_flow("user", "U1", "キャンセル")
    assert "キャンセル" in r
    assert li.get_pending_action("user", "U1") is None


def test_record_flow_future_date_rejected(tmp_sub_file, monkeypatch):
    monkeypatch.setattr(li, "find_spot_by_id",
                        lambda sid: {"name": sid, "lat": 45.1, "lon": 141.1})
    li.upsert_subscription("user", "U1", {"spot_nicknames": {"浜": "H_1631_1434"}})
    li.handle_record_start("user", "U1")
    li.handle_record_flow("user", "U1", "浜")
    r = li.handle_record_flow("user", "U1", "2099/12/31")
    assert "未来" in r


def test_record_confirm_warns_existing_record(tmp_sub_file, tmp_path, monkeypatch):
    """Confirm message shows warning when a record already exists for the same spot+date."""
    monkeypatch.setattr(li, "RECORDS_CSV", str(tmp_path / "records.csv"))
    monkeypatch.setattr(li, "find_spot_by_id",
                        lambda sid: {"name": sid, "lat": 45.1, "lon": 141.1})

    # Pre-write an existing record
    li.write_line_record("H_1631_1434", "2026-07-01", "完全乾燥")

    li.upsert_subscription("user", "U1", {"spot_nicknames": {"浜": "H_1631_1434"}})
    li.handle_record_start("user", "U1")
    li.handle_record_flow("user", "U1", "浜")

    # Force date to the pre-written date
    pa = li.get_pending_action("user", "U1")
    pa["step"] = "ask_result"
    pa["date"] = "2026-07-01"
    li.set_pending_action("user", "U1", pa)

    r = li.handle_record_flow("user", "U1", "2")  # 概ね乾燥 → confirm
    assert "既に記録" in r or "上書き" in r


def test_record_confirm_no_warning_without_existing(tmp_sub_file, tmp_path, monkeypatch):
    """Confirm message has no warning when no prior record exists."""
    monkeypatch.setattr(li, "RECORDS_CSV", str(tmp_path / "records.csv"))
    monkeypatch.setattr(li, "find_spot_by_id",
                        lambda sid: {"name": sid, "lat": 45.1, "lon": 141.1})
    li.upsert_subscription("user", "U1", {"spot_nicknames": {"浜": "H_1631_1434"}})
    li.handle_record_start("user", "U1")
    li.handle_record_flow("user", "U1", "浜")
    pa = li.get_pending_action("user", "U1")
    pa["step"] = "ask_result"
    pa["date"] = "2026-07-01"
    li.set_pending_action("user", "U1", pa)
    r = li.handle_record_flow("user", "U1", "1")  # 完全乾燥 → confirm
    assert "既に記録" not in r
    assert "上書き" not in r
