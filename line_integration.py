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
SPOTS_CSV = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), 'hoshiba_spots.csv'
)

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
        logger.warning('LINE_CHANNEL_SECRET is not set; signature verification skipped')
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


def load_subscriptions() -> dict:
    if not os.path.exists(SUBSCRIPTIONS_FILE):
        return {}
    try:
        with open(SUBSCRIPTIONS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error('Failed to load subscriptions: %s', e)
        return {}


def save_subscriptions(subs: dict) -> None:
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
    'excellent': '★良好',
    'good': '○良好',
    'fair': '△普通',
    'poor': '×不可',
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


def format_single_day(spot_name: str, fc: dict) -> str:
    """Format one day's forecast as a short LINE text."""
    label = _SUITABILITY_LABEL.get(fc['suitability'], fc['suitability'])
    date_lbl = _date_label(fc['date'], fc['day_number'])
    rain_note = f"雨{fc['precipitation']}mm" if fc['precipitation'] > 0 else '雨0mm'
    pop_note = f" 降水確率{fc['pop']}%" if fc.get('pop') is not None else ''
    lines = [
        f"【{spot_name} {date_lbl}の予報】",
        f"適性: {label}（スコア{fc['score']}）",
        f"{rain_note}{pop_note} / 最低湿度{fc['min_humidity']}% / 平均風{fc['avg_wind']}m/s",
        _LINE_DISCLAIMER,
    ]
    return '\n'.join(lines)


def format_weekly_summary(spot_name: str, forecasts: list) -> str:
    """Format 7-day summary for LINE."""
    lines = [f"【{spot_name} 今週の予報】"]
    for fc in forecasts:
        label = _SUITABILITY_LABEL.get(fc['suitability'], fc['suitability'])
        date_lbl = _date_label(fc['date'], fc['day_number'])
        rain = f"雨{fc['precipitation']}mm" if fc['precipitation'] > 0 else '雨なし'
        lines.append(f"{date_lbl} {label} {fc['score']}点 {rain}")
    good_days = [fc for fc in forecasts if fc['suitability'] in ('excellent', 'good')]
    lines.append(f"\n干せそうな日: {len(good_days)}/7日")
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

    # Subscribe: "通知登録 <target>"
    if text.startswith('通知登録') or text.startswith('通知 登録'):
        parts = text.split(None, 1)
        target = parts[1].strip() if len(parts) > 1 else ''
        return {'cmd': 'subscribe', 'target': target}

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
【利尻島昆布干場予報 コマンド一覧】
「今日」「明日」「今週」
　→ 登録済み干場の予報
「H_1631_1434」など干場ID
　→ その干場の予報
「沓形」「仙法志 明日」
　→ 地区・部落の予報
「通知登録 H_1631_1434」
　→ 毎日通知に登録
「通知解除」→ 通知をOFF
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
        '干場が登録されていません。\n'
        '「通知登録 H_1631_1434」のように入力して登録してください。\n'
        '干場IDはWebアプリで確認できます。'
    )


def handle_today(source_type: str, source_id: str) -> str:
    spots = _get_sub_spots(source_type, source_id)
    if not spots:
        return _no_registration_hint()
    msgs = []
    for spot in spots[:3]:  # limit to 3 spots per message
        forecasts = get_forecast_for_spot(spot['lat'], spot['lon'])
        if forecasts:
            msgs.append(format_single_day(spot['name'], forecasts[0]))
        else:
            msgs.append(f"{spot['name']}: 予報取得失敗")
    return '\n\n'.join(msgs)


def handle_tomorrow(source_type: str, source_id: str) -> str:
    spots = _get_sub_spots(source_type, source_id)
    if not spots:
        return _no_registration_hint()
    msgs = []
    for spot in spots[:3]:
        forecasts = get_forecast_for_spot(spot['lat'], spot['lon'])
        if len(forecasts) > 1:
            msgs.append(format_single_day(spot['name'], forecasts[1]))
        else:
            msgs.append(f"{spot['name']}: 予報取得失敗")
    return '\n\n'.join(msgs)


def handle_weekly(source_type: str, source_id: str) -> str:
    spots = _get_sub_spots(source_type, source_id)
    if not spots:
        return _no_registration_hint()
    msgs = []
    for spot in spots[:2]:  # weekly is longer, limit to 2
        forecasts = get_forecast_for_spot(spot['lat'], spot['lon'])
        if forecasts:
            msgs.append(format_weekly_summary(spot['name'], forecasts))
        else:
            msgs.append(f"{spot['name']}: 予報取得失敗")
    return '\n\n'.join(msgs)


def handle_spot_query(spot_id: str) -> str:
    spot = find_spot_by_id(spot_id)
    if not spot:
        return f'干場 {spot_id} が見つかりません。IDを確認してください。'
    forecasts = get_forecast_for_spot(spot['lat'], spot['lon'])
    if not forecasts:
        return f'{spot_id}: 予報データを取得できませんでした。'
    return format_weekly_summary(spot['name'], forecasts)


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


def handle_subscribe(source_type: str, source_id: str, target: str) -> str:
    if not target:
        return '登録する干場IDまたは地区名を入力してください。\n例: 通知登録 H_1631_1434'

    # Spot ID registration
    if _SPOT_ID_RE.match(target):
        spot = find_spot_by_id(target)
        if not spot:
            return f'{target} は見つかりません。干場IDを確認してください。'
        sub = get_subscription(source_type, source_id)
        existing = sub['spots'] if sub else []
        if target in existing:
            return f'{target} はすでに登録済みです。'
        upsert_subscription(source_type, source_id, {
            'spots': existing + [target],
            'notify_enabled': True,
        })
        return (
            f'✓ {target} を通知登録しました。\n'
            '毎日16:00と01:30に予報をお届けします。\n'
            '「通知解除」で解除できます。'
        )

    # Area registration
    spots = find_spots_by_area(target)
    if not spots:
        return (
            f'「{target}」に一致する地区・部落が見つかりません。\n'
            '干場IDまたは正確な部落名を入力してください。\n例: 通知登録 H_1631_1434'
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
    return (
        f'✓ {target}の{len(new_ids)}地点を通知登録しました。\n'
        '毎日16:00と01:30に予報をお届けします。\n'
        '「通知解除」で解除できます。'
    )


def handle_unsubscribe(source_type: str, source_id: str) -> str:
    sub = get_subscription(source_type, source_id)
    if not sub or not sub.get('notify_enabled'):
        return '通知はすでにOFFです。'
    upsert_subscription(source_type, source_id, {'notify_enabled': False})
    return '通知をOFFにしました。再登録は「通知登録 <干場ID>」で行えます。'


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

    day_number = 1 if kind == 'evening' else 0
    day_name = '翌日' if kind == 'evening' else '当日'
    kind_label = '夕方（16:00）' if kind == 'evening' else '早朝（01:30）'

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

        source_id = sub['source_id']
        msgs = []
        for sid in spot_ids[:3]:  # max 3 spots per push to keep message short
            spot = find_spot_by_id(sid)
            if not spot:
                continue
            fcs = get_forecast_for_spot(spot['lat'], spot['lon'])
            if len(fcs) > day_number:
                msgs.append(format_single_day(spot['name'], fcs[day_number]))

        if not msgs:
            skipped += 1
            continue

        header = f'【{day_name}の乾燥予報】{kind_label}\n\n'
        # TODO: Respect 沖止め日 and season range settings once server-side
        #       configuration is implemented (currently only in localStorage).
        full_msg = header + '\n\n'.join(msgs)

        if push_text(source_id, full_msg):
            sent += 1
            logger.info('Notified %s (%s spots)', source_id[:8] + '...', len(msgs))
        else:
            failed += 1

    logger.info(
        'notify_all kind=%s sent=%d failed=%d skipped=%d',
        kind, sent, failed, skipped,
    )
    return {'sent': sent, 'failed': failed, 'skipped': skipped, 'kind': kind}

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
            reply_text(reply_token, _HELP_TEXT)
        return

    if event_type == 'join':
        # Bot joined a group/room
        upsert_subscription(source_type, source_id, {'notify_enabled': True})
        if reply_token:
            reply_text(reply_token, _HELP_TEXT)
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

    cmd = parse_command(text)

    if cmd['cmd'] == 'help':
        response = handle_help()
    elif cmd['cmd'] == 'today':
        response = handle_today(source_type, source_id)
    elif cmd['cmd'] == 'tomorrow':
        response = handle_tomorrow(source_type, source_id)
    elif cmd['cmd'] in ('weekly', 'day') and cmd.get('day') is None:
        response = handle_weekly(source_type, source_id)
    elif cmd['cmd'] == 'day':
        # "明後日" etc. — treat as area-less day query
        spots = _get_sub_spots(source_type, source_id)
        if not spots:
            response = _no_registration_hint()
        else:
            msgs = []
            for spot in spots[:3]:
                fcs = get_forecast_for_spot(spot['lat'], spot['lon'])
                d = cmd.get('day', 0)
                if len(fcs) > d:
                    msgs.append(format_single_day(spot['name'], fcs[d]))
            response = '\n\n'.join(msgs) if msgs else '予報取得失敗'
    elif cmd['cmd'] == 'spot':
        response = handle_spot_query(cmd['spot_id'])
    elif cmd['cmd'] == 'area':
        response = handle_area_query(cmd['area'], cmd.get('day'))
    elif cmd['cmd'] == 'subscribe':
        response = handle_subscribe(source_type, source_id, cmd['target'])
    elif cmd['cmd'] == 'unsubscribe':
        response = handle_unsubscribe(source_type, source_id)
    else:
        response = handle_unknown()

    if reply_token and response:
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
