"""
LINE Messaging API integration for Rishiri Kelp Forecast System.

Environment variables required:
    LINE_CHANNEL_ACCESS_TOKEN  - LINE Messaging API channel access token
    LINE_CHANNEL_SECRET        - LINE Messaging API channel secret
    LINE_ENABLED               - 'true' to activate (default: false)
    LINE_ADMIN_NOTIFY_SECRET   - Secret for /api/line/notify endpoint
    LINE_ADD_FRIEND_URL        - (optional) LINE友だち追加URL (e.g. https://lin.ee/xxx)
                                 Exposed via /api/line/status for the web UI banner.

NOTE on forecast accuracy:
    This module uses a *simplified* forecast (LINE簡易予報) that calls Open-Meteo
    directly with the validated thresholds (precip=0mm, min_hum≤94%, avg_wind≥2.0m/s).
    It does NOT apply the full terrain correction, onshore-wind bonus, stage analysis,
    or fog-risk scoring found in /api/forecast.  Scores may differ by ±10–15 points.
    See README.md "LINE通知連携" for details.

Subscription data is persisted in line_subscriptions.json (not mixed with
existing 4-file CSV sync system).
"""
import os
import json
import hmac
import hashlib
import base64
import logging
import re
import csv
from datetime import datetime, timezone, timedelta

import requests as _requests

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration helpers — read from environment at call time so that
# os.environ changes (tests, hot-reload) take effect without reimport.
# ---------------------------------------------------------------------------

def _cfg() -> dict:
    """Return current LINE config from environment variables."""
    return {
        'token':          os.environ.get('LINE_CHANNEL_ACCESS_TOKEN', ''),
        'secret':         os.environ.get('LINE_CHANNEL_SECRET', ''),
        'enabled':        os.environ.get('LINE_ENABLED', 'false').lower() == 'true',
        'admin_secret':   os.environ.get('LINE_ADMIN_NOTIFY_SECRET', ''),
        'add_friend_url': os.environ.get('LINE_ADD_FRIEND_URL', ''),
    }


# Module-level aliases kept for backwards compatibility with test monkeypatching.
# Prefer calling _cfg() inside functions.
LINE_CHANNEL_ACCESS_TOKEN = ''
LINE_CHANNEL_SECRET = ''
LINE_ENABLED = False
LINE_ADMIN_NOTIFY_SECRET = ''

JST = timezone(timedelta(hours=9))
LINE_MESSAGING_API = 'https://api.line.me/v2/bot/message'
SUBSCRIPTIONS_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), 'line_subscriptions.json'
)
_UPSTASH_REDIS_KEY = 'line_subscriptions'
SPOTS_CSV = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), 'hoshiba_spots.csv'
)
RECORDS_CSV = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), 'hoshiba_records.csv'
)

_LINE_RECORD_COLUMNS = [
    'date', 'name', 'result', 'stop_cause', 'did_dry',
    'collection_time', 'recorded_at', 'correction_count', 'correction_reason',
]
_VALID_RESULTS = ['完全乾燥', '概ね乾燥', '半乾燥', 'ほぼ乾燥なし']
_VALID_STOP_CAUSES = [
    '雨が降った',
    '霧が出た・昆布が湿り戻った',
    '飛散リスク・強風',
    '曇り続きで乾かなかった',
    '天候以外',
]
_PENDING_EXPIRY_MINUTES = 30

# ---------------------------------------------------------------------------
# Signature verification
# ---------------------------------------------------------------------------

def _mask_id(source_id: str) -> str:
    """Return a privacy-safe representation of a LINE source id for logging."""
    if len(source_id) <= 6:
        return '***'
    return source_id[:6] + '***'


def verify_line_signature(body_bytes: bytes, x_line_signature: str) -> bool:
    """Verify LINE webhook signature using HMAC-SHA256."""
    secret = _cfg()['secret']
    if not secret:
        # M-8: 本番環境では LINE_CHANNEL_SECRET 未設定を ERROR レベルで記録
        # （開発環境では CRITICAL にはしないが、明確な警告を出す）
        logger.error(
            'LINE_CHANNEL_SECRET is not set — webhook signature verification SKIPPED. '
            'Set the environment variable on Render before going live.'
        )
        return False
    digest = hmac.new(
        secret.encode('utf-8'),
        body_bytes,
        hashlib.sha256,
    ).digest()
    expected = base64.b64encode(digest).decode('utf-8')
    return hmac.compare_digest(expected, x_line_signature)

# ---------------------------------------------------------------------------
# Subscription management
# ---------------------------------------------------------------------------

def _sub_key(source_type: str, source_id: str) -> str:
    return f'{source_type}:{source_id}'


def _upstash_url() -> str:
    return os.environ.get('UPSTASH_REDIS_REST_URL', '').rstrip('/')


def _upstash_token() -> str:
    return os.environ.get('UPSTASH_REDIS_REST_TOKEN', '')


def _upstash_available() -> bool:
    return bool(_upstash_url() and _upstash_token())


def _upstash_get(key: str):
    """GET a value from Upstash Redis. Returns parsed JSON or None."""
    try:
        resp = _requests.get(
            f'{_upstash_url()}/get/{key}',
            headers={'Authorization': f'Bearer {_upstash_token()}'},
            timeout=5,
        )
        data = resp.json()
        raw = data.get('result')
        if raw is None:
            return None
        return json.loads(raw)
    except Exception as e:
        logger.error('Upstash GET failed: %s', e)
        return None


def _upstash_set(key: str, value) -> bool:
    """SET a value in Upstash Redis. Value is JSON-encoded."""
    try:
        resp = _requests.post(
            f'{_upstash_url()}/set/{key}',
            headers={
                'Authorization': f'Bearer {_upstash_token()}',
                'Content-Type': 'application/json',
            },
            json=json.dumps(value, ensure_ascii=False),
            timeout=5,
        )
        return resp.json().get('result') == 'OK'
    except Exception as e:
        logger.error('Upstash SET failed: %s', e)
        return False


def load_subscriptions() -> dict:
    if _upstash_available():
        data = _upstash_get(_UPSTASH_REDIS_KEY)
        if data is not None:
            return data
        # Fall through to local file on cache miss
    if not os.path.exists(SUBSCRIPTIONS_FILE):
        return {}
    try:
        with open(SUBSCRIPTIONS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error('Failed to load subscriptions: %s', e)
        return {}


def save_subscriptions(subs: dict) -> None:
    if _upstash_available():
        ok = _upstash_set(_UPSTASH_REDIS_KEY, subs)
        if not ok:
            logger.error('Upstash save failed; falling back to local file')
        else:
            return
    try:
        with open(SUBSCRIPTIONS_FILE, 'w', encoding='utf-8') as f:
            json.dump(subs, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error('Failed to save subscriptions: %s', e)


def get_subscription(source_type: str, source_id: str) -> dict | None:
    subs = load_subscriptions()
    return subs.get(_sub_key(source_type, source_id))


def upsert_subscription(source_type: str, source_id: str, updates: dict) -> dict:
    """Create or update a subscription entry. Returns the updated entry."""
    subs = load_subscriptions()
    key = _sub_key(source_type, source_id)
    now = datetime.now(JST).isoformat()
    if key not in subs:
        subs[key] = {
            'source_id': source_id,
            'source_type': source_type,
            'spots': [],
            'areas': [],
            'notify_enabled': True,
            'created_at': now,
            'updated_at': now,
        }
    subs[key].update(updates)
    subs[key]['updated_at'] = now
    save_subscriptions(subs)
    return subs[key]

# ---------------------------------------------------------------------------
# Spots data helpers
# ---------------------------------------------------------------------------

def load_spots_data() -> list:
    """Load spots from hoshiba_spots.csv."""
    spots = []
    if not os.path.exists(SPOTS_CSV):
        return spots
    try:
        with open(SPOTS_CSV, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                spots.append({
                    'name': row['name'],
                    'lat': float(row['lat']),
                    'lon': float(row['lon']),
                    'town': row.get('town', ''),
                    'district': row.get('district', ''),
                    'buraku': row.get('buraku', ''),
                })
    except Exception as e:
        logger.error('Failed to load spots CSV: %s', e)
    return spots


def find_spot_by_id(spot_id: str) -> dict | None:
    """Find a spot by its name (H_XXXX_XXXX, A_XXXX_XXXX, R_XXXX_XXXX)."""
    for spot in load_spots_data():
        if spot['name'] == spot_id:
            return spot
    return None


def find_spots_by_area(area: str) -> list:
    """Find spots whose town, district, or buraku matches the given area name."""
    area = area.strip()
    results = []
    for spot in load_spots_data():
        if area in (spot['town'], spot['district'], spot['buraku']):
            results.append(spot)
    return results


# ---------------------------------------------------------------------------
# Forecast (lightweight, calls Open-Meteo directly)
# ---------------------------------------------------------------------------

_OPEN_METEO_DAILY = (
    'temperature_2m_max,temperature_2m_min,'
    'wind_speed_10m_max,relative_humidity_2m_mean,'
    'precipitation_sum,precipitation_probability_max'
)
_OPEN_METEO_HOURLY = 'relative_humidity_2m,wind_speed_10m'


def _simple_score(precip: float, min_humidity: float, avg_wind_ms: float) -> tuple:
    """
    Simplified drying score using validated thresholds from H_1631_1434 field data.
    Returns (score: int, suitability: str).
    """
    if precip > 0:
        return 10, 'poor'

    score = 50  # base

    # Humidity contribution (validated threshold: <=94%)
    if min_humidity <= 80:
        score += 30
    elif min_humidity <= 87:
        score += 20
    elif min_humidity <= 94:
        score += 10
    else:
        score -= 15

    # Wind contribution (validated threshold: >=2.0 m/s)
    if avg_wind_ms >= 3.0:
        score += 20
    elif avg_wind_ms >= 2.0:
        score += 12
    elif avg_wind_ms >= 1.0:
        score += 2
    else:
        score -= 10

    score = max(0, min(100, score))
    if score >= 80:
        return score, 'excellent'
    elif score >= 60:
        return score, 'good'
    elif score >= 40:
        return score, 'fair'
    return score, 'poor'


def get_forecast_for_spot(lat: float, lon: float, timeout: int = 10) -> list:
    """
    Fetch simplified 7-day drying forecast from Open-Meteo.
    Returns list of daily dicts with keys:
        date, day_number, precipitation, min_humidity, avg_wind, pop, score, suitability
    """
    url = (
        f'https://api.open-meteo.com/v1/forecast'
        f'?latitude={lat}&longitude={lon}'
        f'&daily={_OPEN_METEO_DAILY}'
        f'&hourly={_OPEN_METEO_HOURLY}'
        f'&timezone=Asia%2FTokyo&forecast_days=7'
    )
    try:
        resp = _requests.get(url, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        logger.error('Open-Meteo request failed for (%.4f, %.4f): %s', lat, lon, e)
        return []

    daily = data.get('daily', {})
    hourly = data.get('hourly', {})
    hourly_rh = hourly.get('relative_humidity_2m', [])
    hourly_ws = hourly.get('wind_speed_10m', [])  # km/h

    days = []
    for i in range(min(7, len(daily.get('time', [])))):
        precip = daily['precipitation_sum'][i] or 0.0
        wind_kmh = daily['wind_speed_10m_max'][i] or 0.0
        avg_wind_ms = wind_kmh / 3.6
        pop = (daily.get('precipitation_probability_max') or [None] * 7)[i]

        # Min humidity during working hours 04-16 JST
        start_h = i * 24 + 4
        end_h = start_h + 13
        work_rh = [
            hourly_rh[h]
            for h in range(start_h, min(end_h, len(hourly_rh)))
            if hourly_rh[h] is not None
        ]
        # Avg wind during working hours
        work_ws = [
            hourly_ws[h] / 3.6
            for h in range(start_h, min(end_h, len(hourly_ws)))
            if hourly_ws[h] is not None
        ]
        min_humidity = min(work_rh) if work_rh else (daily['relative_humidity_2m_mean'][i] or 100.0)
        avg_wind = sum(work_ws) / len(work_ws) if work_ws else avg_wind_ms

        score, suitability = _simple_score(precip, min_humidity, avg_wind)

        days.append({
            'date': daily['time'][i],
            'day_number': i,
            'precipitation': round(precip, 1),
            'min_humidity': round(min_humidity, 1),
            'avg_wind': round(avg_wind, 1),
            'pop': pop,
            'score': score,
            'suitability': suitability,
        })
    return days

# ---------------------------------------------------------------------------
# Message formatting helpers
# ---------------------------------------------------------------------------

_SUITABILITY_LABEL = {
    'excellent': '☀️ 干せます！',
    'good':      '🌤 干せそう',
    'fair':      '⛅ 微妙',
    'poor':      '🌧 干せません',
}

# 週間サマリー用短縮ラベル（1行に収める）
_SUITABILITY_SHORT = {
    'excellent': '☀️干せます',
    'good':      '🌤干せそう',
    'fair':      '⛅微妙',
    'poor':      '🌧不可',
}

_WEEKDAY_JA = ['月', '火', '水', '木', '金', '土', '日']

_DAY_NAMES = {0: '今日', 1: '明日', 2: '明後日'}


def _date_label(date_str: str, day_number: int) -> str:
    """Return e.g. '今日(5/18月)' or '5/22金'."""
    try:
        dt = datetime.strptime(date_str, '%Y-%m-%d')
        wd = _WEEKDAY_JA[dt.weekday()]
        md = f'{dt.month}/{dt.day}{wd}'
        prefix = _DAY_NAMES.get(day_number, '')
        return f'{prefix}({md})' if prefix else md
    except Exception:
        return date_str


_LINE_DISCLAIMER = '※LINE簡易予報（Webアプリと値が異なる場合あり）'

_NOTIFY_FOOTER = (
    '\n─────────────\n'
    '📅 沖止めは「沖止め」と返信\n'
    '⚙️「設定確認」で漁期・沖止め確認'
)

# ---------------------------------------------------------------------------
# Date parsing helpers
# ---------------------------------------------------------------------------

def _parse_date_arg(arg: str) -> 'str | None':
    """Parse '6/25', '06/25', '2026/6/25' → 'YYYY-MM-DD'. None on failure."""
    arg = arg.strip().replace('－', '/').replace('−', '/').replace('-', '/')
    now_jst = datetime.now(JST)
    year = now_jst.year
    try:
        parts = [p for p in arg.split('/') if p]
        if len(parts) == 2:
            m, d = int(parts[0]), int(parts[1])
        elif len(parts) == 3:
            year, m, d = int(parts[0]), int(parts[1]), int(parts[2])
        else:
            return None
        return datetime(year, m, d).strftime('%Y-%m-%d')
    except (ValueError, IndexError):
        return None


# ---------------------------------------------------------------------------
# Record helpers
# ---------------------------------------------------------------------------

def _parse_date_for_record(arg: str) -> 'str | None | str':
    """Parse a date for drying records. Returns YYYY-MM-DD, 'future', or None."""
    now_jst = datetime.now(JST)
    today = now_jst.date()
    arg = arg.strip()
    if arg in ('今日', '本日'):
        return today.strftime('%Y-%m-%d')
    if arg in ('昨日', 'きのう'):
        return (today - timedelta(days=1)).strftime('%Y-%m-%d')
    if arg in ('一昨日', 'おととい', '一昨日', 'おとつい'):
        return (today - timedelta(days=2)).strftime('%Y-%m-%d')
    date_str = _parse_date_arg(arg)
    if date_str is None:
        return None
    parsed = datetime.strptime(date_str, '%Y-%m-%d').date()
    if parsed > today:
        return 'future'
    return date_str


def read_existing_record(spot_id: str, date_str: str) -> 'dict | None':
    """Return existing record row for spot+date, or None if not found."""
    if not os.path.exists(RECORDS_CSV):
        return None
    try:
        with open(RECORDS_CSV, 'r', encoding='utf-8', newline='') as f:
            for row in csv.DictReader(f):
                if row.get('date') == date_str and row.get('name') == spot_id:
                    return dict(row)
    except Exception as e:
        logger.error('Failed to read records CSV: %s', e)
    return None


def write_line_record(spot_id: str, date_str: str, result: str,
                      stop_cause: str = '') -> bool:
    """Append or overwrite a record in hoshiba_records.csv."""
    now_jst = datetime.now(JST).strftime('%Y-%m-%dT%H:%M:%S+09:00')
    did_dry = '1' if result in ('完全乾燥', '概ね乾燥') else '0'
    new_row = {
        'date': date_str,
        'name': spot_id,
        'result': result,
        'stop_cause': stop_cause,
        'did_dry': did_dry,
        'collection_time': '',
        'recorded_at': now_jst,
        'correction_count': '0',
        'correction_reason': '',
    }
    try:
        existing = []
        if os.path.exists(RECORDS_CSV):
            with open(RECORDS_CSV, 'r', encoding='utf-8', newline='') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if row.get('date') == date_str and row.get('name') == spot_id:
                        continue  # overwrite existing same-day record
                    existing.append({c: row.get(c, '') for c in _LINE_RECORD_COLUMNS})
        existing.append(new_row)
        with open(RECORDS_CSV, 'w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=_LINE_RECORD_COLUMNS)
            writer.writeheader()
            writer.writerows(existing)
        return True
    except Exception as e:
        logger.error('Failed to write line record: %s', e)
        return False


# ---------------------------------------------------------------------------
# Pending action state machine (persisted in line_subscriptions.json)
# ---------------------------------------------------------------------------

def get_pending_action(source_type: str, source_id: str) -> 'dict | None':
    """Return non-expired pending_action for the subscriber, or None."""
    sub = get_subscription(source_type, source_id)
    if not sub:
        return None
    pa = sub.get('pending_action')
    if not pa:
        return None
    started = pa.get('started_at', '')
    try:
        dt = datetime.fromisoformat(started)
        if (datetime.now(JST) - dt).total_seconds() > _PENDING_EXPIRY_MINUTES * 60:
            clear_pending_action(source_type, source_id)
            return None
    except Exception:
        return None
    return pa


def set_pending_action(source_type: str, source_id: str, pa: dict) -> None:
    pa['started_at'] = pa.get('started_at', datetime.now(JST).isoformat())
    upsert_subscription(source_type, source_id, {'pending_action': pa})


def clear_pending_action(source_type: str, source_id: str) -> None:
    upsert_subscription(source_type, source_id, {'pending_action': None})


# ---------------------------------------------------------------------------
# Spot nickname management
# ---------------------------------------------------------------------------

def get_spot_nicknames(source_type: str, source_id: str) -> dict:
    """Return {nickname: spot_id} for subscriber."""
    sub = get_subscription(source_type, source_id)
    return sub.get('spot_nicknames', {}) if sub else {}


def resolve_spot_nickname(source_type: str, source_id: str, text: str) -> 'dict | None':
    """Resolve user text to a spot dict via nickname or spot_id. Returns None if not found."""
    # Direct spot ID
    if _SPOT_ID_RE.match(text):
        return find_spot_by_id(text)
    # Nickname lookup
    nicknames = get_spot_nicknames(source_type, source_id)
    spot_id = nicknames.get(text)
    if spot_id:
        return find_spot_by_id(spot_id)
    return None


# ---------------------------------------------------------------------------
# Record flow handlers
# ---------------------------------------------------------------------------

_RESULT_CHOICES = (
    '1. 完全乾燥\n2. 概ね乾燥\n3. 半乾燥\n4. ほぼ乾燥なし'
)
_STOP_CAUSE_CHOICES = (
    '1. 雨が降った\n2. 霧・湿り戻り\n3. 飛散リスク・強風\n4. 曇り続き\n5. 天候以外'
)
_RESULT_MAP = {'1': '完全乾燥', '2': '概ね乾燥', '3': '半乾燥', '4': 'ほぼ乾燥なし'}
_STOP_CAUSE_MAP = {
    '1': '雨が降った',
    '2': '霧が出た・昆布が湿り戻った',
    '3': '飛散リスク・強風',
    '4': '曇り続きで乾かなかった',
    '5': '天候以外',
}


def _needs_stop_cause(result: str) -> bool:
    return result in ('半乾燥', 'ほぼ乾燥なし')


def handle_record_start(source_type: str, source_id: str) -> str:
    """Initiate record flow: ask which spot.

    Reply is built before state is persisted so that a storage error
    (Upstash down, Render ephemeral write failure) never causes a silent
    no-reply.  If set_pending_action fails the user still sees the prompt;
    the next message they send will re-trigger parse_command instead of
    entering the flow, which is the safe degraded behaviour.
    """
    nicknames = get_spot_nicknames(source_type, source_id)
    sub = get_subscription(source_type, source_id)
    registered_spots = sub.get('spots', []) if sub else []

    # Build reply first — always returned regardless of storage outcome
    lines = ['📝 乾燥記録を入力します。\nどの干場の記録ですか？']
    if nicknames:
        lines.append('\n登録済み干場:')
        for nick, sid in list(nicknames.items())[:8]:
            lines.append(f'  {nick}（{sid}）')
    elif registered_spots:
        lines.append('\n通知登録済み干場:')
        for sid in registered_spots[:5]:
            lines.append(f'  {sid}')
    else:
        lines.append('\n干場IDを直接入力（例: H_1631_1434）または')
        lines.append('「干場登録 ニックネーム H_ID」で名前を登録できます。')
    lines.append('\n「キャンセル」で中止')

    try:
        set_pending_action(source_type, source_id, {
            'type': 'record', 'step': 'ask_spot',
            'nickname': None, 'spot_id': None, 'date': None,
            'result': None, 'stop_cause': None,
        })
    except Exception:
        logger.exception(
            'handle_record_start: set_pending_action failed for %s:%s '
            '— reply sent but flow state not saved',
            source_type, source_id,
        )

    return '\n'.join(lines)


def handle_record_flow(source_type: str, source_id: str, text: str) -> str:
    """Dispatch incoming text through the record state machine."""
    pa = get_pending_action(source_type, source_id)
    if not pa:
        return handle_unknown()

    if text in ('キャンセル', 'cancel', 'Cancel', 'やめる', '中止'):
        clear_pending_action(source_type, source_id)
        return '記録をキャンセルしました。'

    step = pa.get('step')

    # --- ask_spot ---
    if step == 'ask_spot':
        spot = resolve_spot_nickname(source_type, source_id, text)
        if not spot:
            return (
                f'「{text}」が見つかりませんでした。\n'
                '干場IDまたは登録済みのニックネームを入力してください。\n'
                '「キャンセル」で中止'
            )
        pa.update({'step': 'ask_date', 'nickname': text, 'spot_id': spot['name']})
        set_pending_action(source_type, source_id, pa)
        return (
            f'✓ 干場: {text}（{spot["name"]}）\n\n'
            '📅 何日の記録ですか？\n'
            '例: 今日、昨日、5/18\n（未来の日付は登録できません）\n'
            '「キャンセル」で中止'
        )

    # --- ask_date ---
    if step == 'ask_date':
        date_str = _parse_date_for_record(text)
        if date_str == 'future':
            return '未来の日付は記録できません。\n今日以前の日付を入力してください。\n「キャンセル」で中止'
        if date_str is None:
            return '日付が認識できませんでした。\n例: 今日、昨日、5/18\n「キャンセル」で中止'
        pa.update({'step': 'ask_result', 'date': date_str})
        set_pending_action(source_type, source_id, pa)
        dt = datetime.strptime(date_str, '%Y-%m-%d')
        return (
            f'✓ 日付: {dt.month}/{dt.day}（{_WEEKDAY_JA[dt.weekday()]}）\n\n'
            '🌿 乾燥結果を選んでください:\n'
            f'{_RESULT_CHOICES}\n\n'
            '番号または名前で入力 / 「キャンセル」で中止'
        )

    # --- ask_result ---
    if step == 'ask_result':
        result = _RESULT_MAP.get(text) or (text if text in _VALID_RESULTS else None)
        if result is None:
            return (
                '番号（1〜4）または名前で入力してください:\n'
                f'{_RESULT_CHOICES}\n「キャンセル」で中止'
            )
        pa.update({'result': result})
        if _needs_stop_cause(result):
            pa['step'] = 'ask_stop_cause'
            set_pending_action(source_type, source_id, pa)
            return (
                f'✓ 結果: {result}\n\n'
                '主な原因を選んでください:\n'
                f'{_STOP_CAUSE_CHOICES}\n\n'
                '番号または名前で入力 / 「キャンセル」で中止'
            )
        pa['step'] = 'confirm'
        set_pending_action(source_type, source_id, pa)
        return _format_confirm(pa)

    # --- ask_stop_cause ---
    if step == 'ask_stop_cause':
        cause = _STOP_CAUSE_MAP.get(text) or (text if text in _VALID_STOP_CAUSES else None)
        if cause is None:
            return (
                '番号（1〜5）または名前で入力してください:\n'
                f'{_STOP_CAUSE_CHOICES}\n「キャンセル」で中止'
            )
        pa.update({'stop_cause': cause, 'step': 'confirm'})
        set_pending_action(source_type, source_id, pa)
        return _format_confirm(pa)

    # --- confirm ---
    if step == 'confirm':
        if text in ('確定', 'OK', 'ok', 'はい', '保存'):
            spot_id = pa['spot_id']
            date_str = pa['date']
            result = pa['result']
            stop_cause = pa.get('stop_cause') or ''
            clear_pending_action(source_type, source_id)
            if write_line_record(spot_id, date_str, result, stop_cause):
                dt = datetime.strptime(date_str, '%Y-%m-%d')
                return (
                    f'✅ 記録しました。\n'
                    f'干場: {pa["nickname"]}\n'
                    f'日付: {dt.month}/{dt.day}\n'
                    f'結果: {result}'
                )
            return '⚠️ 記録の保存に失敗しました。もう一度お試しください。'
        if text in ('いいえ', 'キャンセル', 'やり直し', 'no'):
            clear_pending_action(source_type, source_id)
            return '記録をキャンセルしました。'
        return '「確定」で保存、「キャンセル」でやり直しを選んでください。'

    clear_pending_action(source_type, source_id)
    return handle_unknown()


def _format_confirm(pa: dict) -> str:
    dt = datetime.strptime(pa['date'], '%Y-%m-%d')
    lines = ['📋 以下の内容で記録しますか？']

    # Warn if a record already exists for this spot+date
    existing = read_existing_record(pa['spot_id'], pa['date'])
    if existing:
        lines.append(
            f'⚠️ この干場・日付には既に記録があります:\n'
            f'  結果: {existing.get("result", "不明")}'
            + (f'  原因: {existing["stop_cause"]}' if existing.get('stop_cause') else '')
            + '\n上書きされます。'
        )

    lines += [
        f'干場: {pa["nickname"]}（{pa["spot_id"]}）',
        f'日付: {dt.month}/{dt.day}（{_WEEKDAY_JA[dt.weekday()]}）',
        f'結果: {pa["result"]}',
    ]
    if pa.get('stop_cause'):
        lines.append(f'原因: {pa["stop_cause"]}')
    lines.append('\n「確定」で保存 / 「キャンセル」でやり直し')
    return '\n'.join(lines)


_REGISTER_QR = [
    {'label': '今日の予報', 'text': '今日'},
    {'label': '干場一覧',   'text': '干場一覧'},
]

_APP_URL = 'https://rishiri-kelp-forecast-system.onrender.com/'

# Quick Reply for registration guidance — URI button opens the web app directly
_REGISTER_GUIDANCE_QR = [
    {'label': 'Webアプリを開く', 'uri': _APP_URL},
]


def handle_register_guidance() -> dict:
    """Response for 「干場登録」 tapped alone (from rich menu)."""
    return {
        'text': (
            '🗺 干場の登録・呼び名設定\n\n'
            '① Webアプリで地図から干場をタップ\n'
            '② 呼び名を入力（例: 浜の前）\n'
            '③「LINEで通知登録」をタップ\n\n'
            '登録後は「今日」で予報が届きます。'
        ),
        'quick_reply': _REGISTER_GUIDANCE_QR,
    }


def handle_register_spot_nickname(source_type: str, source_id: str,
                                  nickname: str, spot_id: str):
    """Register a nickname → spot_id mapping AND add to notification list.

    Returns dict {text, quick_reply} on success, or str on error.
    """
    if not nickname or not spot_id:
        return '入力形式: 「干場登録 ニックネーム H_XXXX_XXXX」\n例: 干場登録 浜の前 H_1631_1434'
    if not _SPOT_ID_RE.match(spot_id):
        return f'干場IDの形式が正しくありません（例: H_1631_1434）\n入力: {spot_id}'
    spot = find_spot_by_id(spot_id)
    if not spot:
        return f'{spot_id} が見つかりません。IDを確認してください。'
    sub = get_subscription(source_type, source_id)
    nicknames = dict(sub.get('spot_nicknames', {})) if sub else {}
    existing_spots = sub.get('spots', []) if sub else []

    # Update nickname: remove old mapping for this spot_id, then save new one
    old_nick = next((k for k, v in nicknames.items() if v == spot_id and k != nickname), None)
    if old_nick:
        del nicknames[old_nick]
    nicknames[nickname] = spot_id
    upsert_subscription(source_type, source_id, {'spot_nicknames': nicknames})

    # Also add to notification list if not already subscribed
    newly_added = spot_id not in existing_spots
    if newly_added:
        upsert_subscription(source_type, source_id, {
            'spots': existing_spots + [spot_id],
            'notify_enabled': True,
        })

    if newly_added and old_nick:
        msg = (
            f'✓ 呼び名を「{old_nick}」→「{nickname}」に変更し、\n'
            '通知リストに追加しました！\n'
            '毎日16:00と01:30に乾燥予報をお届けします。'
        )
    elif newly_added:
        msg = (
            f'✓ 「{nickname}」を通知リストに追加しました！\n'
            '毎日16:00と01:30に乾燥予報をお届けします。'
        )
    elif old_nick:
        msg = f'✓ 呼び名を「{old_nick}」→「{nickname}」に変更しました。'
    else:
        msg = f'✓ 「{nickname}」の呼び名を登録しました。（通知登録済み）'

    return {'text': msg, 'quick_reply': _REGISTER_QR}


def handle_list_spots(source_type: str, source_id: str) -> str:
    """Show all registered spots with display names. H_XXXX_XXXX is not shown."""
    sub = get_subscription(source_type, source_id)
    nicknames = sub.get('spot_nicknames', {}) if sub else {}  # {nickname: spot_id}
    registered = sub.get('spots', []) if sub else []

    if not nicknames and not registered:
        return (
            '干場が登録されていません。\n'
            'Webアプリの「LINEで通知登録」ボタンから登録できます。\n'
            'https://rishiri-kelp-forecast-system.onrender.com/'
        )

    id_to_nick = {v: k for k, v in nicknames.items()}  # {spot_id: nickname}
    lines = ['【登録済み干場】']
    seen = set()
    for sid in registered:
        nick = id_to_nick.get(sid)
        if nick:
            lines.append(f'・{nick}')
        else:
            spot = find_spot_by_id(sid)
            auto = _auto_display_name(spot) if spot else sid
            lines.append(f'・{auto}（呼び名未設定）')
        seen.add(sid)
    # Nicknames for spots not in registered list (edge case)
    for nick, sid in nicknames.items():
        if sid not in seen:
            lines.append(f'・{nick}')
    lines.append('\n「記録」で乾燥記録を入力できます。')
    lines.append('呼び名設定: Webアプリから「LINEで通知登録」で自動設定')
    return '\n'.join(lines)


def format_single_day(spot_name: str, fc: dict) -> str:
    """Format one day's forecast as a short LINE text."""
    label = _SUITABILITY_LABEL.get(fc['suitability'], fc['suitability'])
    date_lbl = _date_label(fc['date'], fc['day_number'])
    pop_note = f'（確率{fc["pop"]}%）' if fc.get('pop') is not None else ''
    if fc['precipitation'] > 0:
        rain_line = f'🌧 雨: {fc["precipitation"]}mm{pop_note}'
    else:
        rain_line = f'☔ 雨なし{pop_note}'
    lines = [
        f'【{spot_name} {date_lbl}】',
        f'{label}（{fc["score"]}点）',
        '',
        rain_line,
        f'💨 風: {fc["avg_wind"]}m/s',
        f'💦 湿度: {fc["min_humidity"]}%（最低）',
        '',
        _LINE_DISCLAIMER,
    ]
    return '\n'.join(lines)


def format_weekly_summary(spot_name: str, forecasts: list) -> str:
    """Format 7-day summary for LINE."""
    lines = [f'【{spot_name} 今週の予報】']
    for fc in forecasts:
        label = _SUITABILITY_SHORT.get(fc['suitability'], fc['suitability'])
        date_lbl = _date_label(fc['date'], fc['day_number'])
        rain = f' 雨{fc["precipitation"]}mm' if fc['precipitation'] > 0 else ''
        lines.append(f'{date_lbl} {label} {fc["score"]}点{rain}')
    good_days = [fc for fc in forecasts if fc['suitability'] in ('excellent', 'good')]
    lines.append(f'\n✅ 干せそうな日: {len(good_days)}/{len(forecasts)}日')
    lines.append(_LINE_DISCLAIMER)
    return '\n'.join(lines)


def format_area_summary(area: str, day_number: int, spots_forecasts: list) -> str:
    """Format area-level summary for LINE."""
    day_name = _DAY_NAMES.get(day_number, f'{day_number}日後')
    lines = [f"【{area} {day_name}の予報】"]
    good = [sf for sf in spots_forecasts if sf['fc']['suitability'] in ('excellent', 'good')]
    lines.append(f"干せそう: {len(good)}/{len(spots_forecasts)}地点")
    if good:
        best = max(good, key=lambda sf: sf['fc']['score'])
        lines.append(f"最良: {best['spot']['name']} スコア{best['fc']['score']}")
    elif spots_forecasts:
        worst = max(spots_forecasts, key=lambda sf: sf['fc']['score'])
        lines.append(f"最良でも: {worst['spot']['name']} スコア{worst['fc']['score']}")
    lines.append(_LINE_DISCLAIMER)
    return '\n'.join(lines)

# ---------------------------------------------------------------------------
# LINE Messaging API calls
# ---------------------------------------------------------------------------

def _line_headers() -> dict:
    return {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {_cfg()["token"]}',
    }


def reply_text(reply_token: str, text: str) -> bool:
    """Send reply message to LINE. Returns True on success."""
    if not _cfg()['token']:
        logger.warning('LINE_CHANNEL_ACCESS_TOKEN not set; reply skipped')
        return False
    payload = {
        'replyToken': reply_token,
        'messages': [{'type': 'text', 'text': text[:5000]}],
    }
    try:
        resp = _requests.post(
            f'{LINE_MESSAGING_API}/reply',
            headers=_line_headers(),
            json=payload,
            timeout=10,
        )
        if resp.status_code != 200:
            logger.error('LINE reply failed %s: %s', resp.status_code, resp.text)
            return False
        return True
    except Exception as e:
        logger.error('LINE reply exception: %s', e)
        return False


def push_text(to: str, text: str) -> bool:
    """Push message to a user/group/room. Returns True on success."""
    if not _cfg()['token']:
        logger.warning('LINE_CHANNEL_ACCESS_TOKEN not set; push skipped')
        return False
    payload = {
        'to': to,
        'messages': [{'type': 'text', 'text': text[:5000]}],
    }
    masked = _mask_id(to)
    try:
        resp = _requests.post(
            f'{LINE_MESSAGING_API}/push',
            headers=_line_headers(),
            json=payload,
            timeout=10,
        )
        if resp.status_code != 200:
            logger.error('LINE push failed to %s: %s', masked, resp.status_code)
            return False
        return True
    except Exception as e:
        logger.error('LINE push exception to %s: %s', masked, e)
        return False


def reply_with_quick_reply(reply_token: str, text: str, items: list) -> bool:
    """Send reply with Quick Reply buttons.

    items: list of dicts, each either:
      {'label': str, 'text': str}  — message action (sends text on tap)
      {'label': str, 'uri': str}   — URI action (opens URL on tap)
    """
    if not _cfg()['token']:
        logger.warning('LINE_CHANNEL_ACCESS_TOKEN not set; quick reply skipped')
        return False

    def _to_qr_item(item: dict) -> dict:
        label = item['label'][:20]
        if 'uri' in item:
            return {'type': 'action', 'action': {'type': 'uri', 'label': label, 'uri': item['uri']}}
        return {'type': 'action', 'action': {'type': 'message', 'label': label, 'text': item['text']}}

    quick_reply_items = [_to_qr_item(i) for i in items[:13]]  # LINE max 13 Quick Reply items
    payload = {
        'replyToken': reply_token,
        'messages': [{
            'type': 'text',
            'text': text[:5000],
            'quickReply': {'items': quick_reply_items},
        }],
    }
    try:
        resp = _requests.post(
            f'{LINE_MESSAGING_API}/reply',
            headers=_line_headers(),
            json=payload,
            timeout=10,
        )
        if resp.status_code != 200:
            logger.error('LINE quick reply failed %s: %s', resp.status_code, resp.text)
            return False
        return True
    except Exception as e:
        logger.error('LINE quick reply exception: %s', e)
        return False

# ---------------------------------------------------------------------------
# Command parser (public for unit testing)
# ---------------------------------------------------------------------------

_SPOT_ID_RE = re.compile(r'^[HAR]_\d{4}_\d{4}$')
_DAY_KEYWORDS = {
    '今日': 0, '本日': 0,
    '明日': 1, 'あした': 1,
    '明後日': 2, 'あさって': 2,
    '今週': None, 'weekly': None,
}


def parse_command(text: str) -> dict:
    """
    Parse a LINE text message into a command dict.
    Returns one of:
        {'cmd': 'help'}
        {'cmd': 'today'}
        {'cmd': 'tomorrow'}
        {'cmd': 'weekly'}
        {'cmd': 'spot', 'spot_id': '...'}
        {'cmd': 'area', 'area': '...', 'day': int|None}
        {'cmd': 'subscribe', 'target': '...'}
        {'cmd': 'unsubscribe'}
        {'cmd': 'unknown'}
    """
    text = text.strip()

    # Help
    if text in ('ヘルプ', 'help', 'HELP', '?', '？', 'コマンド'):
        return {'cmd': 'help'}

    # Unsubscribe
    if text in ('通知解除', '通知OFF', '通知off', '解除'):
        return {'cmd': 'unsubscribe'}

    # Subscribe: "通知登録 <target> [nickname]"
    if text.startswith('通知登録') or text.startswith('通知 登録'):
        parts = text.split(None, 2)
        target = parts[1].strip() if len(parts) > 1 else ''
        nickname = parts[2].strip() if len(parts) > 2 else ''
        return {'cmd': 'subscribe', 'target': target, 'nickname': nickname}

    # Record flow trigger
    if text in ('記録', '乾燥記録', '記録する', '干し記録'):
        return {'cmd': 'record_start'}

    # Spot nickname registration: "干場登録 ニックネーム H_XXXX_XXXX"
    # "干場登録" alone (no args, e.g. from rich menu button) → show guidance
    if text in ('干場登録', '干場 登録', '干場　登録'):
        return {'cmd': 'register_guidance'}
    if text.startswith('干場登録') or text.startswith('干場 登録'):
        parts = text.split(None, 2)
        nickname = parts[1].strip() if len(parts) > 1 else ''
        spot_id = parts[2].strip() if len(parts) > 2 else ''
        return {'cmd': 'register_spot', 'nickname': nickname, 'spot_id': spot_id}

    # List registered spots
    if text in ('干場一覧', '登録干場', '干場リスト'):
        return {'cmd': 'list_spots'}

    # 沖止め解除 — must come before '沖止め' prefix check and area fallback
    if text in ('沖止め解除', '沖止めを解除'):
        return {'cmd': 'cancel_nogo'}

    # 沖止め設定: "沖止め" (→翌日) or "沖止め 6/25"
    if text == '沖止め':
        return {'cmd': 'set_nogo', 'date': None}
    if text.startswith('沖止め ') or text.startswith('沖止め　'):
        return {'cmd': 'set_nogo', 'date': text[3:].strip()}

    # 漁期設定
    if text.startswith('漁期開始'):
        return {'cmd': 'set_season_start', 'date': text[4:].strip()}
    if text.startswith('漁期終了'):
        return {'cmd': 'set_season_end', 'date': text[4:].strip()}

    # 設定確認
    if text in ('設定確認', '設定', '漁期確認'):
        return {'cmd': 'show_settings'}

    # Pure day keywords
    if text in _DAY_KEYWORDS:
        day = _DAY_KEYWORDS[text]
        if day is None:
            return {'cmd': 'weekly'}
        return {'cmd': 'today' if day == 0 else 'tomorrow' if day == 1 else 'day', 'day': day}

    # Spot ID (H_XXXX_XXXX / A_XXXX_XXXX / R_XXXX_XXXX)
    if _SPOT_ID_RE.match(text):
        return {'cmd': 'spot', 'spot_id': text}

    # Area + optional day: "沓形 明日", "仙法志", "沓形 今日"
    parts = text.split()
    if len(parts) == 2 and parts[1] in _DAY_KEYWORDS:
        day = _DAY_KEYWORDS[parts[1]]
        return {'cmd': 'area', 'area': parts[0], 'day': day if day is not None else 0}
    if len(parts) == 1:
        # Could be area name (non-keyword, non-spot-id)
        return {'cmd': 'area', 'area': text, 'day': None}

    return {'cmd': 'unknown'}

# ---------------------------------------------------------------------------
# Command handlers
# ---------------------------------------------------------------------------

_HELP_TEXT = """\
【コマンド早見表】
「今日」「明日」「今週」→ 干場の乾燥予報
「沓形」「鴛泊」など部落名 → その地区の予報
Webアプリ「LINEで通知登録」→ 毎日通知をON
「通知解除」→ 通知をOFF
「記録」→ 乾燥記録を入力
「沖止め」「沖止め 6/25」→ 沖止め日を登録（祭りなど事前禁漁日）
「漁期開始 6/15」「漁期終了 9/5」→ 通知期間の設定（デフォルト 6/1〜9/30）
「設定確認」→ 現在の設定一覧
「ヘルプ」→ このメッセージ"""


def handle_help() -> str:
    return _HELP_TEXT


def _get_sub_spots(source_type: str, source_id: str) -> list:
    """Return list of spot dicts registered for this source."""
    sub = get_subscription(source_type, source_id)
    if not sub or not sub.get('spots'):
        return []
    spots = []
    for sid in sub['spots']:
        s = find_spot_by_id(sid)
        if s:
            spots.append(s)
    return spots


def _no_registration_hint() -> str:
    return (
        '干場が登録されていません。\n\n'
        '【登録方法】\n'
        '① Webアプリで地図から干場を選択\n'
        '② 「LINEで通知登録」ボタンをタップ\n'
        'https://rishiri-kelp-forecast-system.onrender.com/'
    )


def _auto_display_name(spot: dict) -> str:
    """Generate human-readable display name from buraku→district→town, then spot_id."""
    for field in ('buraku', 'district', 'town'):
        val = (spot.get(field) or '').strip()
        if val and val != '―':
            return f'{val}の干場'
    return spot['name']


def _get_spot_label(source_type: str, source_id: str, spot_id: str) -> str:
    """Return user's nickname for a spot, or auto display name, or spot_id as last resort."""
    nicknames = get_spot_nicknames(source_type, source_id)  # {nickname: spot_id}
    for nick, sid in nicknames.items():
        if sid == spot_id:
            return nick
    spot = find_spot_by_id(spot_id)
    return _auto_display_name(spot) if spot else spot_id


def _collect_user_spots(source_type: str, source_id: str) -> list:
    """Return [{label, spot_id}] combining nicknames (preferred) and subscribed spots."""
    sub = get_subscription(source_type, source_id)
    if not sub:
        return []
    nicknames = sub.get('spot_nicknames', {})  # {nickname: spot_id}
    registered = sub.get('spots', [])
    result = []
    seen = set()
    for nick, sid in list(nicknames.items())[:10]:
        if sid not in seen:
            result.append({'label': nick, 'spot_id': sid})
            seen.add(sid)
    for sid in registered:
        if sid not in seen and len(result) < 10:
            spot = find_spot_by_id(sid)
            display = _auto_display_name(spot) if spot else sid
            result.append({'label': display, 'spot_id': sid})
            seen.add(sid)
    return result


def _execute_intent(source_type: str, source_id: str,
                    spot_id: str, label: str, intent: str) -> str:
    """Execute a forecast or record action for a specific spot."""
    if intent == 'record':
        pa = {
            'type': 'record', 'step': 'ask_date',
            'nickname': label, 'spot_id': spot_id,
            'date': None, 'result': None, 'stop_cause': None,
        }
        try:
            set_pending_action(source_type, source_id, pa)
        except Exception:
            logger.exception('_execute_intent: set_pending_action failed for record')
        return (
            f'✓ 干場: {label}（{spot_id}）\n\n'
            '📅 何日の記録ですか？\n'
            '例: 今日、昨日、5/18\n（未来の日付は登録できません）\n'
            '「キャンセル」で中止'
        )
    spot = find_spot_by_id(spot_id)
    if not spot:
        return f'{label}: 見つかりませんでした。'
    forecasts = get_forecast_for_spot(spot['lat'], spot['lon'])
    if intent == 'today':
        return format_single_day(label, forecasts[0]) if forecasts else f'{label}: 予報取得失敗'
    if intent == 'tomorrow':
        return format_single_day(label, forecasts[1]) if len(forecasts) > 1 else f'{label}: 予報取得失敗'
    if intent == 'weekly':
        return format_weekly_summary(label, forecasts) if forecasts else f'{label}: 予報取得失敗'
    return handle_unknown()


def handle_select_spot(source_type: str, source_id: str, intent: str):
    """Route based on registered spot count.

    Returns str for 0/1 spots, dict {text, quick_reply} for 2+ spots.
    """
    choices = _collect_user_spots(source_type, source_id)
    if not choices:
        return _no_registration_hint()
    if len(choices) == 1:
        return _execute_intent(source_type, source_id,
                               choices[0]['spot_id'], choices[0]['label'], intent)

    intent_label = {
        'today': '今日の予報',
        'tomorrow': '明日の予報',
        'weekly': '今週の予報',
        'record': '乾燥記録',
    }.get(intent, intent)

    lines = [f'📍 {intent_label}の干場を選んでください：']
    for i, c in enumerate(choices, 1):
        lines.append(f'{i}. {c["label"]}')
    lines.append('\n番号またはボタンで選択 / 「キャンセル」で中止')

    quick_items = [{'label': c['label'][:20], 'text': c['label']} for c in choices]
    quick_items.append({'label': '新たな干場を登録', 'text': '新たな干場を登録'})

    try:
        set_pending_action(source_type, source_id, {
            'type': 'select_spot',
            'intent': intent,
            'choices': choices,
        })
    except Exception:
        logger.exception('handle_select_spot: set_pending_action failed')

    return {'text': '\n'.join(lines), 'quick_reply': quick_items}


def handle_select_spot_flow(source_type: str, source_id: str, text: str):
    """Handle user reply during spot selection (select_spot pending action)."""
    pa = get_pending_action(source_type, source_id)
    if not pa or pa.get('type') != 'select_spot':
        return handle_unknown()

    if text in ('キャンセル', 'cancel', 'Cancel', 'やめる', '中止'):
        clear_pending_action(source_type, source_id)
        return '操作をキャンセルしました。'

    if text == '新たな干場を登録':
        clear_pending_action(source_type, source_id)
        return (
            '干場を登録するには:\n\n'
            '① Webアプリで地図から干場を選択\n'
            '② 「LINEで通知登録」ボタンをタップ\n'
            '呼び名も自動で登録されます。\n\n'
            'https://rishiri-kelp-forecast-system.onrender.com/'
        )

    choices = pa.get('choices', [])
    intent = pa.get('intent', 'today')

    if text.isdigit():
        idx = int(text) - 1
        if 0 <= idx < len(choices):
            c = choices[idx]
            clear_pending_action(source_type, source_id)
            return _execute_intent(source_type, source_id, c['spot_id'], c['label'], intent)
        return f'1〜{len(choices)}の番号で入力してください。\n「キャンセル」で中止'

    for c in choices:
        if text in (c['label'], c['spot_id']):
            clear_pending_action(source_type, source_id)
            return _execute_intent(source_type, source_id, c['spot_id'], c['label'], intent)

    return (
        f'「{text}」が見つかりませんでした。\n'
        f'番号（1〜{len(choices)}）またはボタンで選択してください。\n'
        '「キャンセル」で中止'
    )


def handle_today(source_type: str, source_id: str) -> str:
    spots = _get_sub_spots(source_type, source_id)
    if not spots:
        return _no_registration_hint()
    msgs = []
    for spot in spots[:3]:  # limit to 3 spots per message
        display = _get_spot_label(source_type, source_id, spot['name'])
        forecasts = get_forecast_for_spot(spot['lat'], spot['lon'])
        if forecasts:
            msgs.append(format_single_day(display, forecasts[0]))
        else:
            msgs.append(f'{display}: 予報取得失敗')
    return '\n\n'.join(msgs)


def handle_tomorrow(source_type: str, source_id: str) -> str:
    spots = _get_sub_spots(source_type, source_id)
    if not spots:
        return _no_registration_hint()
    msgs = []
    for spot in spots[:3]:
        display = _get_spot_label(source_type, source_id, spot['name'])
        forecasts = get_forecast_for_spot(spot['lat'], spot['lon'])
        if len(forecasts) > 1:
            msgs.append(format_single_day(display, forecasts[1]))
        else:
            msgs.append(f'{display}: 予報取得失敗')
    return '\n\n'.join(msgs)


def handle_weekly(source_type: str, source_id: str) -> str:
    spots = _get_sub_spots(source_type, source_id)
    if not spots:
        return _no_registration_hint()
    msgs = []
    for spot in spots[:2]:  # weekly is longer, limit to 2
        display = _get_spot_label(source_type, source_id, spot['name'])
        forecasts = get_forecast_for_spot(spot['lat'], spot['lon'])
        if forecasts:
            msgs.append(format_weekly_summary(display, forecasts))
        else:
            msgs.append(f'{display}: 予報取得失敗')
    return '\n\n'.join(msgs)


def handle_spot_query(spot_id: str) -> str:
    spot = find_spot_by_id(spot_id)
    if not spot:
        return f'干場 {spot_id} が見つかりません。IDを確認してください。'
    forecasts = get_forecast_for_spot(spot['lat'], spot['lon'])
    display = _auto_display_name(spot)
    if not forecasts:
        return f'{display}: 予報データを取得できませんでした。'
    return format_weekly_summary(display, forecasts)


def handle_area_query(area: str, day: int | None) -> str:
    spots = find_spots_by_area(area)
    if not spots:
        return (
            f'「{area}」に一致する地区・部落が見つかりません。\n'
            '町名・地区名・部落名で入力してください。\n例: 沓形、仙法志、鴛泊'
        )
    # Fetch forecast for up to 10 spots (avoid too many API calls)
    sample = spots[:10]
    target_day = day if day is not None else 0
    spots_forecasts = []
    for spot in sample:
        fcs = get_forecast_for_spot(spot['lat'], spot['lon'])
        if len(fcs) > target_day:
            spots_forecasts.append({'spot': spot, 'fc': fcs[target_day]})

    if not spots_forecasts:
        return f'{area}: 予報データを取得できませんでした。'

    if day is None:
        # Area summary (no specific day given): show today's overview
        all_good = sum(
            1 for sf in spots_forecasts
            if sf['fc']['suitability'] in ('excellent', 'good')
        )
        lines = [
            f"【{area} 今日の概況】",
            f"干せそう: {all_good}/{len(spots_forecasts)}地点",
        ]
        best_sf = max(spots_forecasts, key=lambda sf: sf['fc']['score'])
        lines.append(f"最良: {best_sf['spot']['name']} スコア{best_sf['fc']['score']}")
        lines.append('\n「今週」で週間予報も確認できます')
        lines.append(_LINE_DISCLAIMER)
        return '\n'.join(lines)

    return format_area_summary(area, target_day, spots_forecasts)


def handle_subscribe(source_type: str, source_id: str, target: str,
                     nickname: str = '') -> str:
    if not target:
        return (
            '部落名で登録: 「通知登録 沓形」\n'
            'またはWebアプリから「LINEで通知登録」\n'
            'https://rishiri-kelp-forecast-system.onrender.com/'
        )

    # Spot ID registration
    if _SPOT_ID_RE.match(target):
        spot = find_spot_by_id(target)
        if not spot:
            return f'{target} は見つかりません。干場IDを確認してください。'
        sub = get_subscription(source_type, source_id)
        existing = sub['spots'] if sub else []
        if target in existing:
            display = _get_spot_label(source_type, source_id, target)
            return f'「{display}」はすでに登録済みです。'
        upsert_subscription(source_type, source_id, {
            'spots': existing + [target],
            'notify_enabled': True,
        })
        # Always save/overwrite nickname when provided (Web app is source of truth)
        if nickname:
            sub_after = get_subscription(source_type, source_id)
            existing_nicks = sub_after.get('spot_nicknames', {}) if sub_after else {}
            # Remove any old entry mapping a different key to this spot_id first
            cleaned = {k: v for k, v in existing_nicks.items() if v != target}
            upsert_subscription(source_type, source_id, {
                'spot_nicknames': {**cleaned, nickname: target}
            })
        display = nickname or _auto_display_name(spot)
        return {
            'text': (
                f'✓ 「{display}」を通知リストに追加しました！\n'
                '毎日16:00と01:30に乾燥予報をお届けします。'
            ),
            'quick_reply': _REGISTER_QR,
        }

    # Area registration
    spots = find_spots_by_area(target)
    if not spots:
        return (
            f'「{target}」に一致する部落が見つかりません。\n'
            '正確な部落名で試してください（例: 通知登録 沓形）。\n'
            'またはWebアプリから「LINEで通知登録」。\n'
            'https://rishiri-kelp-forecast-system.onrender.com/'
        )
    spot_ids = [s['name'] for s in spots]
    sub = get_subscription(source_type, source_id)
    existing = sub['spots'] if sub else []
    new_ids = [sid for sid in spot_ids if sid not in existing]
    upsert_subscription(source_type, source_id, {
        'spots': existing + new_ids,
        'areas': ([target] + (sub['areas'] if sub else [])),
        'notify_enabled': True,
    })
    return {
        'text': (
            f'✓ {target}の{len(new_ids)}地点を通知リストに追加しました！\n'
            '毎日16:00と01:30に乾燥予報をお届けします。'
        ),
        'quick_reply': _REGISTER_QR,
    }


def handle_unsubscribe(source_type: str, source_id: str) -> str:
    sub = get_subscription(source_type, source_id)
    if not sub or not sub.get('notify_enabled'):
        return '通知はすでにOFFです。'
    upsert_subscription(source_type, source_id, {'notify_enabled': False})
    return (
        '通知をOFFにしました。\n'
        '再登録はWebアプリの「LINEで通知登録」ボタンからどうぞ。\n'
        'https://rishiri-kelp-forecast-system.onrender.com/'
    )


def _register_nogo_date(source_type: str, source_id: str, target: str) -> str:
    """Register *target* (YYYY-MM-DD) as a no-go date and return a confirmation message."""
    sub = get_subscription(source_type, source_id)
    today_str = datetime.now(JST).strftime('%Y-%m-%d')
    nogo = [d for d in (sub.get('nogo_dates', []) if sub else []) if d >= today_str]
    if target not in nogo:
        nogo.append(target)
    upsert_subscription(source_type, source_id, {'nogo_dates': sorted(nogo)})
    dt = datetime.strptime(target, '%Y-%m-%d')
    prev = dt - timedelta(days=1)
    return (
        f'✓ {dt.month}/{dt.day}（{_WEEKDAY_JA[dt.weekday()]}）を沖止め日に設定しました。\n\n'
        f'以下の通知をスキップします：\n'
        f'・{prev.month}/{prev.day} 16:00 翌日予報\n'
        f'・{dt.month}/{dt.day} 01:30 当日予報\n\n'
        '「設定確認」で一覧を確認できます。'
    )


def handle_set_nogo(source_type: str, source_id: str, date_arg: 'str | None') -> str:
    if date_arg is None:
        # No date given — ask the user which date to register
        try:
            set_pending_action(source_type, source_id, {'type': 'nogo_date'})
        except Exception:
            logger.exception('handle_set_nogo: set_pending_action failed for %s:%s',
                             source_type, source_id)
        return (
            '何日を沖止めにしますか？\n\n'
            '例: 「6/25」「6月25日」「2026/6/25」\n\n'
            '※沖止め日は通知がスキップされます。\n'
            '「キャンセル」で中止。'
        )
    target = _parse_date_arg(date_arg)
    if target is None:
        return '日付の形式が正しくありません。\n例: 「沖止め 6/25」「沖止め 2026/6/25」'
    return _register_nogo_date(source_type, source_id, target)


def handle_nogo_date_flow(source_type: str, source_id: str, text: str) -> str:
    """Process a date reply during the nogo_date pending flow."""
    if text in ('キャンセル', 'cancel', 'Cancel', 'やめる', '中止'):
        clear_pending_action(source_type, source_id)
        return '沖止め登録をキャンセルしました。'
    # Accept both "6/25" and "6月25日" formats
    normalized = text.strip().replace('月', '/').replace('日', '')
    target = _parse_date_arg(normalized)
    if target is None:
        return (
            '日付が認識できませんでした。\n'
            '例: 「6/25」「6月25日」「2026/6/25」\n'
            '「キャンセル」で中止。'
        )
    clear_pending_action(source_type, source_id)
    return _register_nogo_date(source_type, source_id, target)


def handle_cancel_nogo(source_type: str, source_id: str) -> str:
    sub = get_subscription(source_type, source_id)
    today_str = datetime.now(JST).strftime('%Y-%m-%d')
    nogo = sorted(d for d in (sub.get('nogo_dates', []) if sub else []) if d >= today_str)
    if not nogo:
        return '有効な沖止め日はありません。'
    nearest = nogo[0]
    nogo.remove(nearest)
    upsert_subscription(source_type, source_id, {'nogo_dates': nogo})
    dt = datetime.strptime(nearest, '%Y-%m-%d')
    return f'✓ {dt.month}/{dt.day}（{_WEEKDAY_JA[dt.weekday()]}）の沖止めを解除しました。'


def _validate_season_date(date_arg: str, label: str) -> 'tuple[datetime | None, str]':
    """
    Parse and validate a season date argument.

    Returns (dt, '') on success, or (None, error_message) on failure.
    Accepts "6/15", "6月15日", "2026/6/15".
    Rejects: unparseable input, months outside 6–9, dates in the past.
    """
    normalized = date_arg.strip().replace('月', '/').replace('日', '')
    date_str = _parse_date_arg(normalized)
    if date_str is None:
        return None, f'日付の形式が正しくありません。\n例: 「{label} 6/15」'
    dt = datetime.strptime(date_str, '%Y-%m-%d')
    if dt.month < 6 or dt.month > 9:
        return None, '漁期は6〜9月の範囲で設定してください。'
    today = datetime.now(JST).date()
    if dt.date() < today:
        return None, f'すでに過去の日付（{dt.month}/{dt.day}）は設定できません。\n今日以降の日付を入力してください。'
    return dt, ''


def handle_set_season_start(source_type: str, source_id: str, date_arg: str) -> str:
    if not date_arg:
        return '開始日を入力してください。\n例: 「漁期開始 6/15」「漁期開始 6月15日」'
    dt, err = _validate_season_date(date_arg, '漁期開始')
    if err:
        return err
    upsert_subscription(source_type, source_id, {'season_start': f'{dt.month:02d}-{dt.day:02d}'})
    prev = dt - timedelta(days=1)
    return (
        f'✓ 漁期開始日を {dt.month}/{dt.day} に設定しました。\n\n'
        f'前日（{prev.month}/{prev.day}）16:00 の翌日予報から\n'
        f'通知が始まります。\n'
        f'（{prev.month}/{prev.day} 以前の通知はスキップ）\n\n'
        '「設定確認」で確認できます。'
    )


def handle_set_season_end(source_type: str, source_id: str, date_arg: str) -> str:
    if not date_arg:
        return '終了日を入力してください。\n例: 「漁期終了 9/5」「漁期終了 9月5日」'
    dt, err = _validate_season_date(date_arg, '漁期終了')
    if err:
        return err
    upsert_subscription(source_type, source_id, {'season_end': f'{dt.month:02d}-{dt.day:02d}'})
    return (
        f'✓ 漁期終了日を {dt.month}/{dt.day} に設定しました。\n\n'
        f'当日（{dt.month}/{dt.day}）01:30 の早朝予報が\n'
        f'最後の通知になります。\n'
        f'（{dt.month}/{dt.day} 翌日以降の通知はスキップ）\n\n'
        '「設定確認」で確認できます。'
    )


def handle_show_settings(source_type: str, source_id: str) -> str:
    sub = get_subscription(source_type, source_id)
    if not sub:
        return (
            '【現在の設定】\n'
            '通知: 未登録\n'
            '登録干場: なし\n'
            '─────────────\n'
            '干場を登録するには:\n'
            '① Webアプリで地図から干場を選択\n'
            '② 「LINEで通知登録」ボタンをタップ\n'
            'https://rishiri-kelp-forecast-system.onrender.com/'
        )
    lines = ['【現在の設定】']
    lines.append('通知: ' + ('✅ ON' if sub.get('notify_enabled') else '❌ OFF'))
    spots = sub.get('spots', [])
    if spots:
        nicknames = sub.get('spot_nicknames', {})
        spot_labels = [nicknames.get(s, s) for s in spots[:5]]
        spot_display = ', '.join(spot_labels)
    else:
        spot_display = 'なし（Webアプリから登録できます）'
    lines.append('登録干場: ' + spot_display)
    s = sub.get('season_start', '').replace('-', '/')
    e = sub.get('season_end', '').replace('-', '/')
    lines.append(f'漁期: {s or "6/1"}〜{e or "9/30"}')
    today_str = datetime.now(JST).strftime('%Y-%m-%d')
    nogo = sorted(d for d in sub.get('nogo_dates', []) if d >= today_str)
    if nogo:
        nogo_labels = [
            f'{datetime.strptime(d, "%Y-%m-%d").month}/{datetime.strptime(d, "%Y-%m-%d").day}'
            for d in nogo[:5]
        ]
        lines.append('沖止め: ' + ', '.join(nogo_labels))
    else:
        lines.append('沖止め: なし')
    lines.append('─────────────')
    lines.append('変更: 「沖止め 6/25」「漁期開始 6/15」等')
    return '\n'.join(lines)


def handle_unknown() -> str:
    return (
        '入力内容が認識できませんでした。\n'
        '「ヘルプ」でコマンド一覧を確認できます。'
    )

# ---------------------------------------------------------------------------
# Notification broadcast
# ---------------------------------------------------------------------------

def notify_all(kind: str) -> dict:
    """
    Push forecast notifications to all enabled subscribers.

    Args:
        kind: 'evening' (翌日予報) or 'morning' (当日予報)

    Returns:
        dict with sent_count, failed_count, skipped_count
    """
    if kind not in ('evening', 'morning'):
        return {'error': 'kind must be evening or morning'}

    # Season check: only notify during kelp drying season (June–September JST)
    JST = timezone(timedelta(hours=9))
    now_jst = datetime.now(JST)
    if not (6 <= now_jst.month <= 9):
        logger.info('notify_all skipped: out of kelp season (month=%d JST)', now_jst.month)
        return {'sent': 0, 'failed': 0, 'skipped': 0, 'kind': kind, 'reason': 'out_of_season'}

    day_number = 1 if kind == 'evening' else 0
    day_name = '翌日' if kind == 'evening' else '当日'
    kind_label = '夕方（16:00）' if kind == 'evening' else '早朝（01:30）'

    # Target date for this notification (the date whose forecast we send)
    target_date = now_jst.date() + timedelta(days=day_number)
    target_date_str = target_date.strftime('%Y-%m-%d')
    target_mm_dd = f'{target_date.month:02d}-{target_date.day:02d}'

    subs = load_subscriptions()
    sent, failed, skipped = 0, 0, 0

    for key, sub in subs.items():
        if not sub.get('notify_enabled', False):
            skipped += 1
            continue
        spot_ids = sub.get('spots', [])
        if not spot_ids:
            skipped += 1
            continue

        # Per-subscriber personal season check (MM-DD comparison)
        season_start = sub.get('season_start', '')  # e.g. "06-15"
        season_end = sub.get('season_end', '')       # e.g. "09-05"
        if season_start and target_mm_dd < season_start:
            logger.info(
                'Notify skipped for %s: before personal season start %s',
                _mask_id(sub['source_id']), season_start,
            )
            skipped += 1
            continue
        if season_end and target_mm_dd > season_end:
            logger.info(
                'Notify skipped for %s: after personal season end %s',
                _mask_id(sub['source_id']), season_end,
            )
            skipped += 1
            continue

        # Per-subscriber nogo date check
        if target_date_str in sub.get('nogo_dates', []):
            logger.info(
                'Notify skipped for %s: nogo date %s',
                _mask_id(sub['source_id']), target_date_str,
            )
            skipped += 1
            continue

        source_id = sub['source_id']
        source_type_sub = sub.get('source_type', 'user')
        msgs = []
        for sid in spot_ids[:3]:  # max 3 spots per push to keep message short
            spot = find_spot_by_id(sid)
            if not spot:
                continue
            display = _get_spot_label(source_type_sub, source_id, sid)
            fcs = get_forecast_for_spot(spot['lat'], spot['lon'])
            if len(fcs) > day_number:
                msgs.append(format_single_day(display, fcs[day_number]))

        if not msgs:
            skipped += 1
            continue

        header = f'【{day_name}の乾燥予報】{kind_label}\n\n'
        full_msg = header + '\n\n'.join(msgs) + _NOTIFY_FOOTER

        if push_text(source_id, full_msg):
            sent += 1
            logger.info('Notified %s (%s spots)', _mask_id(source_id), len(msgs))
        else:
            failed += 1

    logger.info(
        'notify_all kind=%s sent=%d failed=%d skipped=%d',
        kind, sent, failed, skipped,
    )
    return {'sent': sent, 'failed': failed, 'skipped': skipped, 'kind': kind}

# ---------------------------------------------------------------------------
# Forecast Quick Reply — buttons shown after every forecast response
# ---------------------------------------------------------------------------

_FORECAST_QR: dict = {
    'today': [
        {'label': '明日の予報', 'text': '明日'},
        {'label': '今週の予報', 'text': '今週'},
        {'label': '干し記録',   'text': '記録'},
    ],
    'tomorrow': [
        {'label': '今日の予報', 'text': '今日'},
        {'label': '今週の予報', 'text': '今週'},
        {'label': '干し記録',   'text': '記録'},
    ],
    'weekly': [
        {'label': '今日の予報', 'text': '今日'},
        {'label': '干し記録',   'text': '記録'},
    ],
    'day': [
        {'label': '今日の予報', 'text': '今日'},
        {'label': '今週の予報', 'text': '今週'},
        {'label': '干し記録',   'text': '記録'},
    ],
    'area': [
        {'label': '今日の予報', 'text': '今日'},
        {'label': '今週の予報', 'text': '今週'},
        {'label': '干し記録',   'text': '記録'},
    ],
    'spot': [
        {'label': '今日の予報', 'text': '今日'},
        {'label': '干し記録',   'text': '記録'},
    ],
}

# Messages containing these strings are hint/error texts — QR should not be attached.
# NOTE: '登録されていません' covers _no_registration_hint(); '取得失敗' covers fetch errors.
# Do NOT include 'Webアプリ' here — the disclaimer _LINE_DISCLAIMER also contains it.
_FORECAST_QR_SKIP_KW = ('登録されていません', '見つかりません', '取得失敗', 'LINEで通知登録')

# Help Quick Reply — shown after ヘルプ to let users jump to common actions
_HELP_QR = [
    {'label': '今日の予報', 'text': '今日'},
    {'label': '記録する',   'text': '記録'},
]


def _add_forecast_qr(response, cmd: str):
    """
    Wrap a plain-text forecast response with Quick Reply buttons for easier navigation.
    Returns dict {text, quick_reply} or the original response if QR is not applicable
    (e.g. for error/hint strings, dict responses already carrying QR, or unknown cmd).
    """
    if not isinstance(response, str) or not response:
        return response
    if any(kw in response for kw in _FORECAST_QR_SKIP_KW):
        return response
    items = _FORECAST_QR.get(cmd)
    if not items:
        return response
    return {'text': response, 'quick_reply': items}


# ---------------------------------------------------------------------------
# Webhook event processor
# ---------------------------------------------------------------------------

def _get_source(event: dict) -> tuple:
    """Return (source_type, source_id) from a LINE event."""
    src = event.get('source', {})
    src_type = src.get('type', 'user')
    if src_type == 'user':
        return 'user', src.get('userId', '')
    elif src_type == 'group':
        return 'group', src.get('groupId', '')
    elif src_type == 'room':
        return 'room', src.get('roomId', '')
    return 'user', src.get('userId', '')


def process_event(event: dict) -> None:
    """Dispatch a single LINE webhook event."""
    event_type = event.get('type')
    reply_token = event.get('replyToken')
    source_type, source_id = _get_source(event)

    if not source_id:
        logger.warning('Event with empty source_id, skipping')
        return

    if event_type == 'follow':
        # User added the official account
        upsert_subscription(source_type, source_id, {'notify_enabled': True})
        if reply_token:
            reply_with_quick_reply(reply_token, _HELP_TEXT, _HELP_QR)
        return

    if event_type == 'join':
        # Bot joined a group/room
        upsert_subscription(source_type, source_id, {'notify_enabled': True})
        if reply_token:
            reply_with_quick_reply(reply_token, _HELP_TEXT, _HELP_QR)
        return

    if event_type == 'leave':
        upsert_subscription(source_type, source_id, {'notify_enabled': False})
        return

    if event_type != 'message':
        return

    msg = event.get('message', {})
    if msg.get('type') != 'text':
        # Non-text messages (stickers, images, etc.) → help hint
        if reply_token:
            reply_text(reply_token, '「ヘルプ」でコマンド一覧を確認できます。')
        return

    text = msg.get('text', '').strip()
    if not text:
        return

    # If there is an active pending action, route all text through the flow.
    # Exception: 'ヘルプ' still shows help (with cancel hint appended).
    pa = get_pending_action(source_type, source_id)
    if pa:
        if text in ('ヘルプ', 'help', 'HELP', '?', '？', 'コマンド'):
            response = handle_help() + '\n\n「キャンセル」で現在の操作を中止できます。'
        elif pa.get('type') == 'select_spot':
            response = handle_select_spot_flow(source_type, source_id, text)
        elif pa.get('type') == 'nogo_date':
            response = handle_nogo_date_flow(source_type, source_id, text)
        else:
            response = handle_record_flow(source_type, source_id, text)
        if reply_token and response:
            if isinstance(response, dict):
                reply_with_quick_reply(reply_token, response['text'], response['quick_reply'])
            else:
                reply_text(reply_token, response)
        return

    cmd = parse_command(text)

    if cmd['cmd'] == 'help':
        response = {'text': handle_help(), 'quick_reply': _HELP_QR}
    elif cmd['cmd'] == 'today':
        response = handle_select_spot(source_type, source_id, 'today')
    elif cmd['cmd'] == 'tomorrow':
        response = handle_select_spot(source_type, source_id, 'tomorrow')
    elif cmd['cmd'] in ('weekly', 'day') and cmd.get('day') is None:
        response = handle_select_spot(source_type, source_id, 'weekly')
    elif cmd['cmd'] == 'day':
        # "明後日" etc. — treat as area-less day query
        spots = _get_sub_spots(source_type, source_id)
        if not spots:
            response = _no_registration_hint()
        else:
            msgs = []
            for spot in spots[:3]:
                display = _get_spot_label(source_type, source_id, spot['name'])
                fcs = get_forecast_for_spot(spot['lat'], spot['lon'])
                d = cmd.get('day', 0)
                if len(fcs) > d:
                    msgs.append(format_single_day(display, fcs[d]))
            response = '\n\n'.join(msgs) if msgs else '予報取得失敗'
    elif cmd['cmd'] == 'spot':
        response = handle_spot_query(cmd['spot_id'])
    elif cmd['cmd'] == 'area':
        response = handle_area_query(cmd['area'], cmd.get('day'))
    elif cmd['cmd'] == 'subscribe':
        response = handle_subscribe(source_type, source_id, cmd['target'],
                                    cmd.get('nickname', ''))
    elif cmd['cmd'] == 'unsubscribe':
        response = handle_unsubscribe(source_type, source_id)
    elif cmd['cmd'] == 'record_start':
        response = handle_select_spot(source_type, source_id, 'record')
    elif cmd['cmd'] == 'register_guidance':
        response = handle_register_guidance()
    elif cmd['cmd'] == 'register_spot':
        response = handle_register_spot_nickname(
            source_type, source_id, cmd.get('nickname', ''), cmd.get('spot_id', ''))
    elif cmd['cmd'] == 'list_spots':
        response = handle_list_spots(source_type, source_id)
    elif cmd['cmd'] == 'set_nogo':
        response = handle_set_nogo(source_type, source_id, cmd.get('date'))
    elif cmd['cmd'] == 'cancel_nogo':
        response = handle_cancel_nogo(source_type, source_id)
    elif cmd['cmd'] == 'set_season_start':
        response = handle_set_season_start(source_type, source_id, cmd.get('date', ''))
    elif cmd['cmd'] == 'set_season_end':
        response = handle_set_season_end(source_type, source_id, cmd.get('date', ''))
    elif cmd['cmd'] == 'show_settings':
        response = handle_show_settings(source_type, source_id)
    else:
        response = handle_unknown()

    # Attach Quick Reply navigation buttons to successful forecast responses
    if cmd['cmd'] in _FORECAST_QR:
        response = _add_forecast_qr(response, cmd['cmd'])

    if reply_token and response:
        if isinstance(response, dict):
            reply_with_quick_reply(reply_token, response['text'], response['quick_reply'])
        else:
            reply_text(reply_token, response)

# ---------------------------------------------------------------------------
# Flask endpoint helpers (called from start.py routes)
# ---------------------------------------------------------------------------

def handle_webhook():
    """Process LINE Webhook POST. Returns Flask response tuple."""
    from flask import request, jsonify  # noqa: PLC0415 — lazy import

    if not _cfg()['enabled']:
        return jsonify({'status': 'LINE integration disabled'}), 503

    body_bytes = request.get_data()
    signature = request.headers.get('X-Line-Signature', '')

    if not verify_line_signature(body_bytes, signature):
        logger.warning('Invalid LINE signature from %s', request.remote_addr)
        return jsonify({'status': 'invalid signature'}), 403

    try:
        payload = json.loads(body_bytes)
    except json.JSONDecodeError:
        return jsonify({'status': 'bad json'}), 400

    events = payload.get('events', [])
    for event in events:
        try:
            process_event(event)
        except Exception as e:
            logger.error('Error processing LINE event: %s', e, exc_info=True)

    return jsonify({'status': 'ok'}), 200


def get_status():
    """Return LINE integration status (no secrets exposed)."""
    from flask import jsonify  # noqa: PLC0415

    cfg = _cfg()
    subs = load_subscriptions()
    enabled_count = sum(1 for s in subs.values() if s.get('notify_enabled'))

    return jsonify({
        'line_enabled': cfg['enabled'],
        'channel_secret_set': bool(cfg['secret']),
        'access_token_set': bool(cfg['token']),
        'admin_secret_set': bool(cfg['admin_secret']),
        # LINE_ADD_FRIEND_URL is not a secret — expose it for the web banner
        'line_add_friend_url': cfg['add_friend_url'],
        'total_subscriptions': len(subs),
        'active_subscriptions': enabled_count,
        'status': 'ok' if cfg['enabled'] else 'disabled',
    })


def handle_notify():
    """Handle /api/line/notify POST from Render Cron or admin."""
    from flask import request, jsonify  # noqa: PLC0415

    cfg = _cfg()
    if not cfg['enabled']:
        return jsonify({'status': 'LINE integration disabled'}), 503

    # Authenticate: secret in JSON body or X-Notify-Secret header
    data = request.get_json(silent=True) or {}
    secret = data.get('secret') or request.headers.get('X-Notify-Secret', '')

    if not cfg['admin_secret']:
        return jsonify({'status': 'LINE_ADMIN_NOTIFY_SECRET not configured'}), 503

    if not hmac.compare_digest(secret, cfg['admin_secret']):
        return jsonify({'status': 'unauthorized'}), 403

    kind = data.get('kind', '')
    if kind not in ('evening', 'morning'):
        return jsonify({'status': 'kind must be evening or morning'}), 400

    result = notify_all(kind)
    return jsonify({'status': 'ok', **result})


# ---------------------------------------------------------------------------
# Rich Menu API
# ---------------------------------------------------------------------------

_RICH_MENU_W = 2500
_RICH_MENU_H = 1686   # 2 rows × 3 cols
_RICH_MENU_NAME = '利尻昆布予報メニュー'
_RICH_MENU_CHAT_BAR = '予報メニュー'

# LINE Messaging API data endpoint (image upload uses api-data.line.me)
_LINE_DATA_API = 'https://api-data.line.me/v2/bot'


def _build_rich_menu_payload() -> dict:
    """
    Build the rich menu JSON payload (2 rows × 3 cols = 6 buttons).

    Button layout:
      Row 1: ☀️ 今日の予報 | 📅 明日の予報 | 📊 今週の予報
      Row 2: 📝 干し記録   | 📍 干場登録   | 🌐 アプリを開く (URI)
    """
    W, H = _RICH_MENU_W, _RICH_MENU_H
    BW, BH = W // 3, H // 2

    def _bounds(col: int, row: int) -> dict:
        return {'x': col * BW, 'y': row * BH, 'width': BW, 'height': BH}

    def _btn(col: int, row: int, label: str, text: str) -> dict:
        return {
            'bounds': _bounds(col, row),
            'action': {
                'type': 'message',
                'label': label[:20],   # LINE max 20 chars
                'text': text,
            },
        }

    def _btn_uri(col: int, row: int, label: str, uri: str) -> dict:
        return {
            'bounds': _bounds(col, row),
            'action': {
                'type': 'uri',
                'label': label[:20],
                'uri': uri,
            },
        }

    return {
        'size': {'width': W, 'height': H},
        'selected': True,
        'name': _RICH_MENU_NAME,
        'chatBarText': _RICH_MENU_CHAT_BAR,
        'areas': [
            # Row 1
            _btn(0, 0, '今日の予報', '今日'),
            _btn(1, 0, '明日の予報', '明日'),
            _btn(2, 0, '今週の予報', '今週'),
            # Row 2
            _btn(0, 1, '干し記録',   '記録'),
            _btn(1, 1, '干場登録',   '干場登録'),
            _btn_uri(2, 1, 'アプリを開く',
                     'https://rishiri-kelp-forecast-system.onrender.com/'),
        ],
    }


def generate_rich_menu_image(path: str) -> bool:
    """
    Generate a 2500×1686 rich menu PNG with 6 colored button areas.

    Renders Japanese labels only (no emoji) for maximum compatibility.
    Font search order:
      1. Windows Japanese fonts (local dev)
      2. Linux Noto Sans CJK (Render/Debian — installed via apt-get)
      3. Pillow built-in bitmap fallback (ASCII short labels)

    Returns True on success.
    """
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        logger.error('Pillow not installed; cannot generate rich menu image')
        return False

    W, H = _RICH_MENU_W, _RICH_MENU_H
    BW, BH = W // 3, H // 2
    BORDER = 8

    # Button definitions: (col, row, bg_color, line1, line2)
    # Two-line layout: short top line (大) + detail bottom line (小)
    # 絵文字は除外 — Pillow on Linux ではカラー絵文字フォントが不安定
    BTNS = [
        (0, 0, '#1d4ed8', '今日',     '予報'),
        (1, 0, '#0369a1', '明日',     '予報'),
        (2, 0, '#0e7490', '今週',     '予報'),
        (0, 1, '#15803d', '干し',     '記録'),
        (1, 1, '#7c3aed', '干場',     '登録'),
        (2, 1, '#0d9488', 'アプリ',   'を開く'),
    ]

    # Font search paths — Japanese first, ASCII fallback last
    _FONT_PATHS = [
        'C:/Windows/Fonts/meiryo.ttc',
        'C:/Windows/Fonts/msgothic.ttc',
        'C:/Windows/Fonts/YuGothB.ttc',
        '/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc',
        '/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc',
        '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc',
        '/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc',
        '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
    ]

    def _try_font(size: int):
        for fp in _FONT_PATHS:
            try:
                f = ImageFont.truetype(fp, size)
                logger.debug('Rich menu font loaded: %s @ %d', fp, size)
                return f
            except Exception:
                continue
        try:
            return ImageFont.load_default(size=size)
        except Exception:
            return ImageFont.load_default()

    font_large = _try_font(160)   # top line (大)
    font_small = _try_font(90)    # bottom line (小)

    img = Image.new('RGB', (W, H), '#0f172a')
    draw = ImageDraw.Draw(img)

    def _draw_centered(text: str, font, cx: int, cy: int) -> None:
        """Draw *text* centered at (cx, cy)."""
        try:
            bbox = draw.textbbox((0, 0), text, font=font)
            tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
            draw.text((cx - tw // 2, cy - th // 2), text,
                      fill='#ffffff', font=font)
        except Exception as exc:
            logger.debug('_draw_centered failed for %r: %s', text, exc)

    for col, row, color, line1, line2 in BTNS:
        x1 = col * BW + BORDER
        y1 = row * BH + BORDER
        x2 = (col + 1) * BW - BORDER
        y2 = (row + 1) * BH - BORDER
        cx = (x1 + x2) // 2
        cy = (y1 + y2) // 2

        # Button background
        try:
            draw.rounded_rectangle([x1, y1, x2, y2], radius=24,
                                   fill=color, outline='#e2e8f0', width=4)
        except AttributeError:
            draw.rectangle([x1, y1, x2, y2], fill=color, outline='#e2e8f0', width=4)

        # Two-line text: line1 upper, line2 lower
        gap = 20   # pixels between the two lines
        _draw_centered(line1, font_large, cx, cy - 60)
        _draw_centered(line2, font_small,  cx, cy + 80)

    import os as _os
    _os.makedirs(_os.path.dirname(path), exist_ok=True)
    try:
        img.save(path, 'PNG', optimize=True)
        logger.info('generate_rich_menu_image saved to %s', path)
        return True
    except Exception as e:
        logger.error('generate_rich_menu_image save failed: %s', e)
        return False


def create_rich_menu() -> dict:
    """
    Create (or replace) the LINE rich menu and set it as default for all users.

    Steps:
      1. POST /v2/bot/richmenu         — create menu structure
      2. POST rich menu image           — upload 2500×1686 PNG
      3. POST /v2/bot/user/all/richmenu — set as default

    Returns dict with 'richMenuId' and 'status', or 'error' on failure.
    """
    cfg = _cfg()
    if not cfg['token']:
        return {'error': 'LINE_CHANNEL_ACCESS_TOKEN not set'}

    # ── Step 1: create rich menu structure ──────────────────────────────────
    payload = _build_rich_menu_payload()
    try:
        resp = _requests.post(
            'https://api.line.me/v2/bot/richmenu',
            headers=_line_headers(),
            json=payload,
            timeout=15,
        )
        if resp.status_code != 200:
            return {'error': f'create rich menu failed {resp.status_code}: {resp.text[:200]}'}
        rich_menu_id = resp.json().get('richMenuId', '')
        if not rich_menu_id:
            return {'error': 'LINE API did not return richMenuId'}
    except Exception as e:
        return {'error': f'create rich menu exception: {e}'}

    logger.info('Rich menu created: %s', rich_menu_id)

    # ── Step 2: generate + upload image ─────────────────────────────────────
    import os as _os
    image_path = _os.path.join(
        _os.path.dirname(_os.path.abspath(__file__)),
        'static', 'icons', 'rich_menu.png',
    )
    image_uploaded = False

    if generate_rich_menu_image(image_path):
        try:
            with open(image_path, 'rb') as f:
                img_data = f.read()
            img_resp = _requests.post(
                f'{_LINE_DATA_API}/richmenu/{rich_menu_id}/content',
                headers={
                    'Authorization': f'Bearer {cfg["token"]}',
                    'Content-Type': 'image/png',
                },
                data=img_data,
                timeout=30,
            )
            if img_resp.status_code == 200:
                image_uploaded = True
                logger.info('Rich menu image uploaded (%d bytes)', len(img_data))
            else:
                logger.warning('Rich menu image upload failed %s: %s',
                               img_resp.status_code, img_resp.text[:200])
        except Exception as e:
            logger.error('Rich menu image upload exception: %s', e)
    else:
        logger.warning('Rich menu image generation failed; menu created without image')

    # ── Step 3: set as default for all users ────────────────────────────────
    try:
        default_resp = _requests.post(
            f'https://api.line.me/v2/bot/user/all/richmenu/{rich_menu_id}',
            headers=_line_headers(),
            timeout=15,
        )
        if default_resp.status_code not in (200, 204):
            logger.warning('Set default rich menu failed %s: %s',
                           default_resp.status_code, default_resp.text[:100])
    except Exception as e:
        logger.error('Set default rich menu exception: %s', e)

    return {
        'richMenuId': rich_menu_id,
        'image_uploaded': image_uploaded,
        'status': 'created',
    }


def handle_setup_rich_menu():
    """
    Handle POST /api/line/setup-richmenu.

    Requires LINE_ADMIN_NOTIFY_SECRET in the request body or
    X-Notify-Secret header. Creates the rich menu and uploads
    the auto-generated image to LINE.
    """
    from flask import request, jsonify  # noqa: PLC0415

    cfg = _cfg()
    if not cfg['enabled']:
        return jsonify({'status': 'LINE integration disabled'}), 503

    data = request.get_json(silent=True) or {}
    secret = data.get('secret') or request.headers.get('X-Notify-Secret', '')

    if not cfg['admin_secret']:
        return jsonify({'status': 'LINE_ADMIN_NOTIFY_SECRET not configured'}), 503

    if not hmac.compare_digest(secret, cfg['admin_secret']):
        return jsonify({'status': 'unauthorized'}), 403

    result = create_rich_menu()
    if 'error' in result:
        return jsonify({'status': 'error', **result}), 500
    return jsonify({'status': 'ok', **result})
