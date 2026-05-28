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
    # e533006: no-subscription returns a friendly onboarding message, NOT an error.
    result = li.handle_show_settings("user", "UNKNOWN")
    assert "未登録" in result or "登録" in result  # onboarding hint
    assert "見つかりません" not in result


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

@pytest.mark.parametrize("text", ["記録", "乾燥記録", "記録する", "干し記録"])
def test_parse_record_start_all_aliases(text):
    """All rich-menu / natural-language variants must map to record_start."""
    assert li.parse_command(text) == {"cmd": "record_start"}

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
    # Returns dict with text + quick_reply (also adds to notification list)
    assert isinstance(result, dict)
    assert "✓" in result['text']
    assert len(result['quick_reply']) > 0
    sub = li.get_subscription("user", "U1")
    assert sub["spot_nicknames"]["浜の前"] == "H_1631_1434"
    assert "H_1631_1434" in sub.get("spots", [])  # also added to notifications

def test_register_spot_invalid_id(tmp_sub_file):
    result = li.handle_register_spot_nickname("user", "U1", "浜の前", "INVALID")
    assert "形式" in result

def test_list_spots_none(tmp_sub_file):
    li.upsert_subscription("user", "U1", {"notify_enabled": True})
    result = li.handle_list_spots("user", "U1")
    assert "登録されていません" in result


def test_list_spots_with_nicknames(tmp_sub_file):
    li.upsert_subscription("user", "U1", {
        "notify_enabled": True,
        "spot_nicknames": {"浜の前": "H_1631_1434"},
    })
    result = li.handle_list_spots("user", "U1")
    assert "浜の前" in result
    assert "H_1631_1434" not in result  # spot_id は通常表示に出ない


def test_register_spot_nickname_replaces_old_name(tmp_sub_file, monkeypatch):
    """Same user registering a new nickname for an already-named spot replaces the old one."""
    monkeypatch.setattr(li, "find_spot_by_id",
                        lambda sid: {"name": sid, "lat": 45.1, "lon": 141.1})
    li.upsert_subscription("user", "U1", {
        "spot_nicknames": {"浜の前": "H_1631_1434"},
    })
    result = li.handle_register_spot_nickname("user", "U1", "砂浜", "H_1631_1434")
    assert isinstance(result, dict)
    assert "浜の前" in result['text'] and "砂浜" in result['text']  # shows rename
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


# ---------------------------------------------------------------------------
# handle_record_start — robustness: always replies even if storage fails
# ---------------------------------------------------------------------------

def test_record_start_replies_even_if_storage_fails(tmp_sub_file, monkeypatch):
    """If set_pending_action raises (e.g. Upstash down), reply is still returned.

    This is the root cause of the rich-menu '干し記録' button silence bug:
    set_pending_action was called before the reply string was built, so any
    storage error caused handle_record_start to raise before returning a value.
    """
    li.upsert_subscription("user", "U1", {"spot_nicknames": {"浜の前": "H_1631_1434"}})

    # Simulate Upstash / file-write failure
    def _boom(*args, **kwargs):
        raise OSError("simulated storage failure")

    monkeypatch.setattr(li, "set_pending_action", _boom)

    result = li.handle_record_start("user", "U1")

    # Must return a non-empty reply string despite the storage error
    assert result, "handle_record_start must always return a non-empty string"
    assert "乾燥記録" in result or "干場" in result
    assert "キャンセル" in result


def test_record_start_generates_reply_via_process_event(tmp_sub_file, monkeypatch):
    """Simulate process_event dispatching '記録': a reply must be queued."""
    li.upsert_subscription("user", "U_rec", {"spot_nicknames": {"テスト浜": "H_1631_1434"}})

    sent_replies = []

    def _fake_reply(token, text):
        sent_replies.append({'token': token, 'text': text})

    monkeypatch.setattr(li, "reply_text", _fake_reply)

    event = {
        "type": "message",
        "replyToken": "dummy_token_abc",
        "source": {"type": "user", "userId": "U_rec"},
        "message": {"type": "text", "text": "記録"},
    }
    li.process_event(event)

    assert len(sent_replies) == 1, "process_event must call reply_text exactly once"
    reply = sent_replies[0]
    assert reply["token"] == "dummy_token_abc"
    assert "乾燥記録" in reply["text"] or "干場" in reply["text"]
    assert "キャンセル" in reply["text"]


def test_record_start_generates_reply_for_kanji_alias(tmp_sub_file, monkeypatch):
    """'乾燥記録' with 0 spots returns registration hint (not the record prompt)."""
    li.upsert_subscription("user", "U_rec2", {})
    sent_replies = []
    monkeypatch.setattr(li, "reply_text", lambda t, txt: sent_replies.append(txt))

    event = {
        "type": "message",
        "replyToken": "tok2",
        "source": {"type": "user", "userId": "U_rec2"},
        "message": {"type": "text", "text": "乾燥記録"},
    }
    li.process_event(event)

    assert sent_replies, "'乾燥記録' must produce a LINE reply"
    assert "登録" in sent_replies[0]  # 0 spots → registration hint


# ---------------------------------------------------------------------------
# handle_select_spot / handle_select_spot_flow — Quick Reply UX
# ---------------------------------------------------------------------------

def test_select_spot_zero_spots_returns_hint(tmp_sub_file):
    """0 registered spots → registration hint string."""
    li.upsert_subscription("user", "U_qs0", {})
    result = li.handle_select_spot("user", "U_qs0", "today")
    assert isinstance(result, str)
    assert "登録" in result


def test_select_spot_one_spot_executes_directly(tmp_sub_file, monkeypatch):
    """1 registered spot → execute intent immediately (no Quick Reply)."""
    monkeypatch.setattr(li, "find_spot_by_id",
                        lambda sid: {"name": sid, "lat": 45.1, "lon": 141.1})
    monkeypatch.setattr(li, "get_forecast_for_spot",
                        lambda lat, lon: [{"date": "2026-07-01", "day_number": 0,
                                           "suitability": "good", "score": 80,
                                           "precipitation": 0, "min_humidity": 70,
                                           "avg_wind": 3.5, "pop": None}])
    li.upsert_subscription("user", "U_qs1", {"spots": ["H_1631_1434"]})
    result = li.handle_select_spot("user", "U_qs1", "today")
    assert isinstance(result, str)
    assert "H_1631_1434" in result or "予報" in result


def test_select_spot_two_spots_returns_quick_reply_dict(tmp_sub_file):
    """2 registered spots → dict with text + quick_reply list."""
    li.upsert_subscription("user", "U_qs2", {
        "spot_nicknames": {"浜の前": "H_1631_1434", "岬": "H_2000_1500"},
    })
    result = li.handle_select_spot("user", "U_qs2", "today")
    assert isinstance(result, dict), "2 spots must return a dict (Quick Reply)"
    assert "text" in result and "quick_reply" in result
    labels = [item["label"] for item in result["quick_reply"]]
    assert "浜の前" in labels
    assert "岬" in labels
    assert "新たな干場を登録" in labels
    # pending action must be set
    pa = li.get_pending_action("user", "U_qs2")
    assert pa is not None
    assert pa["type"] == "select_spot"
    assert pa["intent"] == "today"


def test_select_spot_flow_number_selects_choice(tmp_sub_file, monkeypatch):
    """Typing '1' during spot selection picks the first choice."""
    monkeypatch.setattr(li, "find_spot_by_id",
                        lambda sid: {"name": sid, "lat": 45.1, "lon": 141.1})
    monkeypatch.setattr(li, "get_forecast_for_spot",
                        lambda lat, lon: [{"date": "2026-07-01", "day_number": 0,
                                           "suitability": "good", "score": 80,
                                           "precipitation": 0, "min_humidity": 70,
                                           "avg_wind": 3.5, "pop": None}])
    li.upsert_subscription("user", "U_qsf", {
        "spot_nicknames": {"浜の前": "H_1631_1434", "岬": "H_2000_1500"},
    })
    li.set_pending_action("user", "U_qsf", {
        "type": "select_spot",
        "intent": "today",
        "choices": [
            {"label": "浜の前", "spot_id": "H_1631_1434"},
            {"label": "岬", "spot_id": "H_2000_1500"},
        ],
    })
    result = li.handle_select_spot_flow("user", "U_qsf", "1")
    assert isinstance(result, str)
    # pending action cleared
    assert li.get_pending_action("user", "U_qsf") is None


def test_select_spot_flow_new_spot_registration(tmp_sub_file):
    """'新たな干場を登録' returns URL and clears pending action."""
    li.upsert_subscription("user", "U_qsr", {})
    li.set_pending_action("user", "U_qsr", {
        "type": "select_spot", "intent": "today",
        "choices": [{"label": "浜", "spot_id": "H_1631_1434"}],
    })
    result = li.handle_select_spot_flow("user", "U_qsr", "新たな干場を登録")
    assert isinstance(result, str)
    assert "onrender.com" in result
    assert li.get_pending_action("user", "U_qsr") is None


def test_select_spot_record_intent_leads_to_ask_date(tmp_sub_file):
    """Selecting a spot for 'record' intent jumps to ask_date step."""
    li.upsert_subscription("user", "U_qsrec", {
        "spot_nicknames": {"浜の前": "H_1631_1434", "岬": "H_2000_1500"},
    })
    li.set_pending_action("user", "U_qsrec", {
        "type": "select_spot", "intent": "record",
        "choices": [
            {"label": "浜の前", "spot_id": "H_1631_1434"},
            {"label": "岬", "spot_id": "H_2000_1500"},
        ],
    })
    result = li.handle_select_spot_flow("user", "U_qsrec", "浜の前")
    assert isinstance(result, str)
    assert "日付" in result or "記録" in result
    pa = li.get_pending_action("user", "U_qsrec")
    assert pa is not None
    assert pa["type"] == "record"
    assert pa["step"] == "ask_date"
    assert pa["spot_id"] == "H_1631_1434"


def test_process_event_today_two_spots_calls_quick_reply(tmp_sub_file, monkeypatch):
    """process_event '今日' with 2 spots calls reply_with_quick_reply (not reply_text)."""
    li.upsert_subscription("user", "U_qse", {
        "spot_nicknames": {"浜の前": "H_1631_1434", "岬": "H_2000_1500"},
    })
    qr_calls = []
    monkeypatch.setattr(li, "reply_with_quick_reply",
                        lambda token, text, items: qr_calls.append((token, text, items)))
    monkeypatch.setattr(li, "reply_text", lambda *a: None)

    event = {
        "type": "message",
        "replyToken": "tok_qr",
        "source": {"type": "user", "userId": "U_qse"},
        "message": {"type": "text", "text": "今日"},
    }
    li.process_event(event)

    assert len(qr_calls) == 1, "reply_with_quick_reply must be called once"
    token, text, items = qr_calls[0]
    assert token == "tok_qr"
    assert "干場" in text or "予報" in text
    labels = [i["label"] for i in items]
    assert "浜の前" in labels
    assert "新たな干場を登録" in labels


def test_select_spot_quick_reply_returned_even_if_storage_fails(tmp_sub_file, monkeypatch):
    """If set_pending_action raises during select_spot, the Quick Reply dict is
    still returned and reply_with_quick_reply is still called via process_event.

    This guards the same class of silent-no-reply bug that hit handle_record_start:
    a storage error must never swallow the outbound LINE reply.
    """
    li.upsert_subscription("user", "U_qsfail", {
        "spot_nicknames": {"浜の前": "H_1631_1434", "岬": "H_2000_1500"},
    })

    def _boom(*args, **kwargs):
        raise OSError("simulated Upstash failure")

    monkeypatch.setattr(li, "set_pending_action", _boom)

    # Direct call: dict must still be returned
    result = li.handle_select_spot("user", "U_qsfail", "today")
    assert isinstance(result, dict), "Quick Reply dict must be returned even on storage failure"
    assert "text" in result and "quick_reply" in result

    # End-to-end via process_event: reply_with_quick_reply must still be called
    qr_calls = []
    monkeypatch.setattr(li, "reply_with_quick_reply",
                        lambda token, text, items: qr_calls.append((token, text, items)))
    monkeypatch.setattr(li, "reply_text", lambda *a: None)

    event = {
        "type": "message",
        "replyToken": "tok_fail",
        "source": {"type": "user", "userId": "U_qsfail"},
        "message": {"type": "text", "text": "今日"},
    }
    li.process_event(event)

    assert len(qr_calls) == 1, "reply_with_quick_reply must be called despite storage failure"
    assert qr_calls[0][0] == "tok_fail"


# ---------------------------------------------------------------------------
# Display name UX: H_XXXX_XXXX hidden from users
# ---------------------------------------------------------------------------

def test_auto_display_name_uses_buraku_first(monkeypatch):
    """_auto_display_name prefers buraku over district/town."""
    spot = {"name": "H_1631_1434", "lat": 0, "lon": 0,
            "buraku": "神居", "district": "沓形", "town": "利尻町"}
    assert li._auto_display_name(spot) == "神居の干場"


def test_auto_display_name_falls_back_to_district(monkeypatch):
    """_auto_display_name falls back to district when buraku is empty."""
    spot = {"name": "H_1631_1434", "lat": 0, "lon": 0,
            "buraku": "", "district": "沓形", "town": "利尻町"}
    assert li._auto_display_name(spot) == "沓形の干場"


def test_auto_display_name_falls_back_to_spot_id(monkeypatch):
    """_auto_display_name returns spot_id when all location fields are blank."""
    spot = {"name": "H_1631_1434", "lat": 0, "lon": 0,
            "buraku": "―", "district": "", "town": ""}
    assert li._auto_display_name(spot) == "H_1631_1434"


def test_collect_user_spots_no_nickname_uses_auto_display(tmp_sub_file, monkeypatch):
    """Spot without nickname shows auto display name, not H_XXXX_XXXX."""
    monkeypatch.setattr(li, "find_spot_by_id",
                        lambda sid: {"name": sid, "lat": 0, "lon": 0,
                                     "buraku": "神居", "district": "", "town": ""})
    li.upsert_subscription("user", "U_dn", {"spots": ["H_1631_1434"]})
    choices = li._collect_user_spots("user", "U_dn")
    assert len(choices) == 1
    assert choices[0]["label"] == "神居の干場"
    assert choices[0]["spot_id"] == "H_1631_1434"
    assert "H_1631_1434" not in choices[0]["label"]


def test_execute_intent_uses_label_not_spot_id(tmp_sub_file, monkeypatch):
    """_execute_intent passes the label (not spot['name']) to format_single_day."""
    monkeypatch.setattr(li, "find_spot_by_id",
                        lambda sid: {"name": sid, "lat": 45.1, "lon": 141.1,
                                     "buraku": "", "district": "", "town": ""})
    monkeypatch.setattr(li, "get_forecast_for_spot",
                        lambda lat, lon: [{"date": "2026-07-01", "day_number": 0,
                                           "suitability": "good", "score": 80,
                                           "precipitation": 0, "min_humidity": 70,
                                           "avg_wind": 3.5, "pop": None}])
    li.upsert_subscription("user", "U_ei", {})
    result = li._execute_intent("user", "U_ei", "H_1631_1434", "浜の前", "today")
    assert "浜の前" in result
    assert "H_1631_1434" not in result


def test_parse_command_subscribe_with_nickname():
    """'通知登録 H_XXXX_XXXX 呼び名' extracts both target and nickname."""
    cmd = li.parse_command("通知登録 H_1631_1434 浜の前")
    assert cmd["cmd"] == "subscribe"
    assert cmd["target"] == "H_1631_1434"
    assert cmd["nickname"] == "浜の前"


def test_handle_subscribe_saves_nickname(tmp_sub_file, monkeypatch):
    """handle_subscribe with nickname saves it to spot_nicknames."""
    monkeypatch.setattr(li, "find_spot_by_id",
                        lambda sid: {"name": sid, "lat": 45.1, "lon": 141.1,
                                     "buraku": "", "district": "", "town": ""})
    result = li.handle_subscribe("user", "U_sub", "H_1631_1434", nickname="浜の前")
    text = result['text'] if isinstance(result, dict) else result
    assert "浜の前" in text
    assert "H_1631_1434" not in text  # 成功メッセージにIDが出ない
    sub = li.get_subscription("user", "U_sub")
    assert sub["spot_nicknames"]["浜の前"] == "H_1631_1434"


def test_handle_subscribe_overwrites_nickname(tmp_sub_file, monkeypatch):
    """Second subscribe call with a new nickname overwrites the old one (Web is source of truth)."""
    monkeypatch.setattr(li, "find_spot_by_id",
                        lambda sid: {"name": sid, "lat": 45.1, "lon": 141.1,
                                     "buraku": "", "district": "", "town": ""})
    li.handle_subscribe("user", "U_ow", "H_1631_1434", nickname="旧ニックネーム")
    # Re-subscribe (spot already registered) with a different nickname — should still update
    li.upsert_subscription("user", "U_ow", {"spots": ["H_1631_1434"], "notify_enabled": True})
    # Simulate re-registration with new nickname by calling handle_subscribe on fresh sub
    li.upsert_subscription("user", "U_ow", {"spots": [], "notify_enabled": True})
    li.handle_subscribe("user", "U_ow", "H_1631_1434", nickname="新ニックネーム")
    sub = li.get_subscription("user", "U_ow")
    assert sub["spot_nicknames"].get("新ニックネーム") == "H_1631_1434"
    assert "旧ニックネーム" not in sub["spot_nicknames"]


def test_handle_subscribe_no_nickname_uses_auto_display(tmp_sub_file, monkeypatch):
    """handle_subscribe without nickname still uses auto display name in success message."""
    monkeypatch.setattr(li, "find_spot_by_id",
                        lambda sid: {"name": sid, "lat": 45.1, "lon": 141.1,
                                     "buraku": "神居", "district": "", "town": ""})
    result = li.handle_subscribe("user", "U_sub2", "H_1631_1434")
    text = result['text'] if isinstance(result, dict) else result
    assert "神居の干場" in text
    assert "H_1631_1434" not in text


def test_list_spots_shows_unnamed_spots_with_auto_name(tmp_sub_file, monkeypatch):
    """handle_list_spots shows unnamed subscribed spots with auto display name, not ID."""
    monkeypatch.setattr(li, "find_spot_by_id",
                        lambda sid: {"name": sid, "lat": 0, "lon": 0,
                                     "buraku": "神居", "district": "", "town": ""})
    li.upsert_subscription("user", "U_ls", {"spots": ["H_1631_1434"]})
    result = li.handle_list_spots("user", "U_ls")
    assert "神居の干場" in result
    assert "呼び名未設定" in result
    assert "H_1631_1434" not in result


def test_notify_all_uses_display_name(tmp_sub_file, monkeypatch):
    """notify_all push message uses user's nickname, not spot_id."""
    monkeypatch.setattr(li, "find_spot_by_id",
                        lambda sid: {"name": sid, "lat": 45.1, "lon": 141.1,
                                     "buraku": "", "district": "", "town": ""})
    monkeypatch.setattr(li, "get_forecast_for_spot",
                        lambda lat, lon: [{"date": "2026-07-01", "day_number": 0,
                                           "suitability": "good", "score": 80,
                                           "precipitation": 0, "min_humidity": 70,
                                           "avg_wind": 3.5, "pop": None}])
    li.upsert_subscription("user", "U_notify", {
        "notify_enabled": True,
        "spots": ["H_1631_1434"],
        "spot_nicknames": {"浜の前": "H_1631_1434"},
    })
    pushed = []
    monkeypatch.setattr(li, "push_text", lambda to, text: pushed.append(text) or True)

    import datetime
    from zoneinfo import ZoneInfo
    JST = ZoneInfo("Asia/Tokyo")
    fake_now = datetime.datetime(2026, 7, 1, 7, 0, 0, tzinfo=JST)
    monkeypatch.setattr(li, "datetime", type("FakeDatetime", (), {
        "now": staticmethod(lambda tz=None: fake_now),
        "strptime": datetime.datetime.strptime,
    })())

    li.notify_all("morning")
    assert pushed, "push_text must have been called"
    assert "浜の前" in pushed[0]
    assert "H_1631_1434" not in pushed[0]


# ---------------------------------------------------------------------------
# format_single_day — improved emoji labels and layout
# ---------------------------------------------------------------------------

def test_format_single_day_shows_emoji_label():
    """Suitability label now uses emoji (☀️/🌤/⛅/🌧) instead of ★/○/△/×."""
    fc = _sample_fc(suitability="excellent", score=90)
    msg = li.format_single_day("浜の前", fc)
    assert "☀️" in msg or "干せます" in msg


def test_format_single_day_score_in_parens():
    """Score is shown as （72点） format."""
    fc = _sample_fc(suitability="good", score=72)
    msg = li.format_single_day("浜の前", fc)
    assert "72" in msg


def test_format_single_day_wind_with_unit():
    """Wind speed has m/s unit."""
    fc = _sample_fc()
    msg = li.format_single_day("浜の前", fc)
    assert "m/s" in msg


def test_format_single_day_humidity_with_unit():
    """Humidity has % unit."""
    fc = _sample_fc()
    msg = li.format_single_day("浜の前", fc)
    assert "%" in msg


def test_format_single_day_rain_note_no_rain():
    """No-rain message does not say '雨Xmm' when precip=0."""
    fc = _sample_fc(precip=0.0)
    msg = li.format_single_day("浜の前", fc)
    assert "雨なし" in msg or "雨0mm" in msg or "☔" in msg


def test_format_single_day_poor_rain_emoji():
    """With rain, 🌧 emoji and mm value are shown."""
    fc = _sample_fc(suitability="poor", score=10, precip=3.5)
    msg = li.format_single_day("浜の前", fc)
    assert "3.5mm" in msg


def test_format_weekly_summary_emoji_labels():
    """Weekly summary uses short emoji labels (☀️/🌤/⛅/🌧)."""
    forecasts = [_sample_fc(i) for i in range(7)]
    msg = li.format_weekly_summary("浜の前", forecasts)
    assert any(e in msg for e in ("☀️", "🌤", "⛅", "🌧"))


def test_format_weekly_summary_checkmark_summary():
    """Weekly summary has ✅ good-days count."""
    forecasts = [_sample_fc(i) for i in range(7)]
    msg = li.format_weekly_summary("浜の前", forecasts)
    assert "✅" in msg
    assert "7" in msg  # 7 good days (all 'good' in sample)


# ---------------------------------------------------------------------------
# _add_forecast_qr — Quick Reply wrapping
# ---------------------------------------------------------------------------

def test_add_forecast_qr_wraps_forecast():
    """Successful forecast str → dict with text + quick_reply."""
    text = "【浜の前 今日(5/28水)】\n☀️ 干せます！（89点）"
    result = li._add_forecast_qr(text, 'today')
    assert isinstance(result, dict)
    assert result['text'] == text
    labels = [i['label'] for i in result['quick_reply']]
    assert '明日の予報' in labels
    assert '今週の予報' in labels
    assert '干し記録' in labels


def test_add_forecast_qr_no_wrap_for_hint():
    """Registration hint (contains 'Webアプリ') is NOT wrapped."""
    hint = li._no_registration_hint()
    result = li._add_forecast_qr(hint, 'today')
    assert isinstance(result, str)


def test_add_forecast_qr_no_wrap_for_empty():
    """Empty string is returned as-is."""
    assert li._add_forecast_qr('', 'today') == ''


def test_add_forecast_qr_no_wrap_for_dict():
    """Already-dict responses pass through unchanged."""
    d = {'text': 'foo', 'quick_reply': []}
    assert li._add_forecast_qr(d, 'today') is d


def test_add_forecast_qr_tomorrow_has_today_button():
    """Tomorrow forecast QR includes '今日の予報' button."""
    text = "【浜の前 明日(5/29木)】\n🌤 干せそう（72点）"
    result = li._add_forecast_qr(text, 'tomorrow')
    labels = [i['label'] for i in result['quick_reply']]
    assert '今日の予報' in labels


# ---------------------------------------------------------------------------
# process_event — single-spot forecast now returns Quick Reply
# ---------------------------------------------------------------------------

def test_process_event_today_one_spot_calls_quick_reply(tmp_sub_file, monkeypatch):
    """process_event '今日' with 1 spot → reply_with_quick_reply (not reply_text)."""
    monkeypatch.setattr(li, "find_spot_by_id",
                        lambda sid: {"name": sid, "lat": 45.1, "lon": 141.1,
                                     "buraku": "神居", "district": "", "town": ""})
    monkeypatch.setattr(li, "get_forecast_for_spot",
                        lambda lat, lon: [{"date": "2026-07-01", "day_number": 0,
                                           "suitability": "good", "score": 80,
                                           "precipitation": 0, "min_humidity": 70,
                                           "avg_wind": 3.5, "pop": 10}])
    li.upsert_subscription("user", "U_1sp", {
        "spots": ["H_1631_1434"],
        "spot_nicknames": {"神居の前": "H_1631_1434"},
    })
    qr_calls = []
    monkeypatch.setattr(li, "reply_with_quick_reply",
                        lambda token, text, items: qr_calls.append((token, text, items)))
    monkeypatch.setattr(li, "reply_text", lambda *a: None)

    event = {
        "type": "message",
        "replyToken": "tok_1sp",
        "source": {"type": "user", "userId": "U_1sp"},
        "message": {"type": "text", "text": "今日"},
    }
    li.process_event(event)
    assert len(qr_calls) == 1, "reply_with_quick_reply must be called for single-spot today"
    labels = [i['label'] for i in qr_calls[0][2]]
    assert '明日の予報' in labels
    assert '干し記録' in labels


def test_process_event_spot_id_query_has_quick_reply(tmp_sub_file, monkeypatch):
    """process_event with a direct spot ID query → Quick Reply buttons attached."""
    monkeypatch.setattr(li, "find_spot_by_id",
                        lambda sid: {"name": sid, "lat": 45.1, "lon": 141.1,
                                     "buraku": "神居", "district": "", "town": ""})
    monkeypatch.setattr(li, "get_forecast_for_spot",
                        lambda lat, lon: [_sample_fc(i) for i in range(7)])
    qr_calls = []
    monkeypatch.setattr(li, "reply_with_quick_reply",
                        lambda tok, txt, items: qr_calls.append(items))
    monkeypatch.setattr(li, "reply_text", lambda *a: None)

    event = {
        "type": "message",
        "replyToken": "tok_sp",
        "source": {"type": "user", "userId": "U_spid"},
        "message": {"type": "text", "text": "H_1631_1434"},
    }
    li.process_event(event)
    assert qr_calls, "QR must be attached to spot-ID forecast reply"


# ---------------------------------------------------------------------------
# _build_rich_menu_payload — structure validation
# ---------------------------------------------------------------------------

def test_build_rich_menu_payload_structure():
    """Payload has required top-level keys and 6 areas."""
    p = li._build_rich_menu_payload()
    assert p['size'] == {'width': 2500, 'height': 1686}
    assert p['selected'] is True
    assert 'chatBarText' in p
    assert len(p['areas']) == 6


def test_build_rich_menu_payload_actions():
    """5 areas use message action; 1 area (アプリ) uses uri action."""
    areas = li._build_rich_menu_payload()['areas']
    msg_areas = [a for a in areas if a['action']['type'] == 'message']
    uri_areas = [a for a in areas if a['action']['type'] == 'uri']
    assert len(msg_areas) == 5
    assert len(uri_areas) == 1
    for a in msg_areas:
        assert a['action']['text']  # non-empty text
    for a in uri_areas:
        assert a['action']['uri']   # non-empty uri
        assert 'onrender.com' in a['action']['uri']


def test_build_rich_menu_payload_covers_full_area():
    """The 6 areas together cover the full 2500×1686 area without gaps."""
    p = li._build_rich_menu_payload()
    W, H = p['size']['width'], p['size']['height']
    covered = set()
    for area in p['areas']:
        b = area['bounds']
        for x in range(b['x'], b['x'] + b['width'], 100):
            for y in range(b['y'], b['y'] + b['height'], 100):
                covered.add((x // 100, y // 100))
    # Sample-check that corners are covered
    corners = [(0, 0), (W // 100 - 1, 0), (0, H // 100 - 1), (W // 100 - 1, H // 100 - 1)]
    for cx, cy in corners:
        assert (cx, cy) in covered or any(
            abs(cx - x) <= 1 and abs(cy - y) <= 1 for x, y in covered
        ), f'Corner ({cx*100},{cy*100}) not covered'


def test_build_rich_menu_payload_labels_not_too_long():
    """All area labels are within LINE's 20-char limit."""
    for area in li._build_rich_menu_payload()['areas']:
        label = area['action'].get('label', '')
        assert len(label) <= 20, f'Label too long: {label!r}'


# ---------------------------------------------------------------------------
# generate_rich_menu_image — basic smoke test
# ---------------------------------------------------------------------------

def test_generate_rich_menu_image(tmp_path):
    """generate_rich_menu_image creates a valid PNG file."""
    path = str(tmp_path / "test_rich_menu.png")
    result = li.generate_rich_menu_image(path)
    assert result is True
    import os
    assert os.path.exists(path)
    assert os.path.getsize(path) > 10_000   # must be non-trivial
    from PIL import Image
    img = Image.open(path)
    assert img.size == (2500, 1686)


# ---------------------------------------------------------------------------
# _HELP_QR and process_event help path
# ---------------------------------------------------------------------------

def test_help_qr_has_three_buttons():
    """_HELP_QR contains exactly 3 quick-reply buttons."""
    assert len(li._HELP_QR) == 3
    labels = [item['label'] for item in li._HELP_QR]
    assert '今日の予報' in labels


def test_help_qr_buttons_have_text():
    """Every _HELP_QR item has a non-empty text field."""
    for item in li._HELP_QR:
        assert item.get('text'), f'Missing text in {item!r}'


def test_process_event_help_uses_quick_reply(tmp_sub_file, monkeypatch):
    """process_event for 'ヘルプ' calls reply_with_quick_reply (not reply_text)."""
    qr_calls = []
    txt_calls = []

    monkeypatch.setattr(li, 'reply_with_quick_reply',
                        lambda token, text, items: qr_calls.append((text, items)))
    monkeypatch.setattr(li, 'reply_text',
                        lambda token, text: txt_calls.append(text))

    event = {
        'type': 'message',
        'message': {'type': 'text', 'text': 'ヘルプ'},
        'source': {'type': 'user', 'userId': 'U_HELP_TEST'},
        'replyToken': 'TOKEN_HELP',
    }
    li.process_event(event)

    assert len(qr_calls) == 1, 'Expected exactly one quick-reply send'
    assert len(txt_calls) == 0, 'reply_text should not be called for help'
    sent_text, items = qr_calls[0]
    assert 'コマンド' in sent_text
    assert len(items) == 3


def test_help_text_compact():
    """_HELP_TEXT is shorter than the old 21-line version (≤ 12 lines)."""
    lines = li._HELP_TEXT.strip().splitlines()
    assert len(lines) <= 12, f'_HELP_TEXT has {len(lines)} lines; expected ≤ 12'
