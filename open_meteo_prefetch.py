"""Open-Meteo raw-response prefetch helpers.

Temporary mitigation for Render egress 429s: GitHub Actions can fetch the
raw Open-Meteo response and store it in Upstash Redis, while Render reads the
same raw shape and keeps the existing domain logic in-process.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from urllib.parse import urlencode

import requests

from open_meteo_guard import om_apikey_suffix, om_host


SCHEMA_VERSION = 1
SOURCE = "github_actions_prefetch"
KEY_PREFIX = "om:prefetch:v1"
GITHUB_ACTIONS_CIRCUIT_KEY = "om:circuit:v1:github_actions"

LINE_DAILY_VARS = (
    "temperature_2m_max,temperature_2m_min,"
    "wind_speed_10m_max,relative_humidity_2m_mean,"
    "precipitation_sum,precipitation_probability_max"
)
LINE_HOURLY_VARS = "relative_humidity_2m,wind_speed_10m,wind_direction_10m,precipitation"
LINE_TIMEZONE = "Asia/Tokyo"
LINE_FORECAST_DAYS = 7

# Enhanced (foehn/terrain-corrected) forecast prefetch — mirrors start.py's
# get_forecast() main Open-Meteo query exactly (start.py ~line 1184), so a
# canary spot's corrected LINE forecast can be served from this prefetch
# instead of a live Render->Open-Meteo call under a sustained 429.
ENHANCED_DAILY_VARS = LINE_DAILY_VARS
ENHANCED_HOURLY_VARS = (
    "temperature_2m,relative_humidity_2m,wind_speed_10m,wind_direction_10m,"
    "cloud_cover,shortwave_radiation,direct_radiation,pressure_msl,"
    "precipitation,precipitation_probability,cape,"
    "temperature_700hPa,relative_humidity_700hPa,wind_speed_700hPa,wind_direction_700hPa,"
    "temperature_850hPa,relative_humidity_850hPa,wind_speed_850hPa,wind_direction_850hPa,"
    "dewpoint_2m,surface_pressure"
)

# Summit reference point (foehn baseline) — mirrors start.py's
# _get_summit_hourly_temps() (temperature_2m only, no `daily` param at all).
SUMMIT_HOURLY_VARS = "temperature_2m"

# JMA official summit coordinates (45°10'43"N 141°14'31"E, South Peak, 1721m).
# This module is the canonical source (Flask/pandas-independent, importable
# from the lightweight GitHub Actions job) — start.py imports SUMMIT_LAT/
# SUMMIT_LON from here rather than defining its own copy (2026-08-04, as part
# of moving build_rishiri_grid() here too — see below).
SUMMIT_LAT = 45.1786
SUMMIT_LON = 141.2419


def build_rishiri_grid() -> list[dict]:
    """利尻島の島内分布グリッドを生成。

    【構成: 利尻山頂 + 二重リング = 49点】
    - 利尻山頂 1点 (中心) ── 山頂の気象を基準として可視化
    - 内リング 24点: 方位 0°/15°/.../345° (15°刻み) ── 半径は方位別に異なる（下記）
    - 外リング 24点: r=8km, 方位 7.5°/22.5°/.../352.5° (内リングと7.5°ずれで千鳥配置)

    【内リング半径の方位別設計】
    利尻山頂（JMA公式座標 SUMMIT_LAT/SUMMIT_LON、旧丸め座標45.1800N/141.2392Eから
    約260m補正済み。2026-08-04、FOEHN_VARIABLE_CONSISTENCY_AUDIT_20260804.md参照）
    は島の「東寄り」に位置する。このため、北東・東方向の海岸は5.8〜7.5km
    （山頂に近い）、西・北西・南方向の海岸は7.1〜9.4km（遠い）と非対称になる。
    実測データ（331干場）に基づく各方向の平均沿岸距離と内リング半径の割り当ては
    旧丸め座標を基準に算出されたものだが、約260mのシフトはリング半径6〜9kmに
    対して小さいため再較正はしていない:
      北:6.9km / 北東:6.2km / 東:6.6km          → r=6km  (i=0〜8,  0°〜120°)
      南東:7.7km / 南2,3:8.3km / 南西:7.4km / 西1,2:8.0km → r=7km  (i=9〜11, i=13〜19, 135°〜285°)
      真南:8.3km(max 9.1km)                     → r=9km  (i=12, 180°)
      西3:8.0km / 北西:8.8km(max 9.4km)         → r=9km  (i=20〜23, 300°〜345°)

    座標計算
    ----------
    中心: 利尻山頂（SUMMIT_LAT/SUMMIT_LON） — mountain_azimuth()・
          _compute_foehn_intensity_hours()の山頂リファレンスと同一の基準点。
          旧実装はこの関数だけ45.1800N/141.2392Eという別の丸め座標を使っており、
          _compute_score_field()側のフェーン温位差計算に系統誤差（概算+1.67℃）が
          混入していた（PR#19で他経路は統一したがこの関数の更新が漏れていた）。
    LAT_D = 1/111.0 °/km
    LON_D = 1/(111.0×cos(SUMMIT_LAT°)) °/km
    方位: 北=0°、時計回り（気象学的方位角と同一）

    ラベル規則 (8方位 × 3サブ = 24点/リング)
    ----------
    内リング: 内北1 / 内北2 / 内北3 / 内北東1 ... 内北西3  (半径はラベルに反映しない)
    外リング: 外北1 / 外北2 / 外北3 / 外北東1 ... 外北西3
    山頂:     利尻山頂

    2026-08-04: start.py の _build_rishiri_grid() から移設（このモジュールが
    正規定義元）。start.py・GitHub Actionsのfield_grid prefetchジョブの両方が
    同じ49点を得るための単一ソース。start.py側は
    `from open_meteo_prefetch import build_rishiri_grid as _build_rishiri_grid`
    として再エクスポートしている。
    """
    import math as _m

    _CLAT  = SUMMIT_LAT
    _CLON  = SUMMIT_LON
    _LAT_D = 1.0 / 111.0
    _LON_D = 1.0 / (111.0 * _m.cos(_m.radians(_CLAT)))

    _C8 = ['北', '北東', '東', '南東', '南', '南西', '西', '北西']

    def _pt(bearing_deg, radius_km, label):
        _brad = _m.radians(bearing_deg)
        return {
            'lat':     round(_CLAT + radius_km * _LAT_D * _m.cos(_brad), 4),
            'lon':     round(_CLON + radius_km * _LON_D * _m.sin(_brad), 4),
            'bearing': bearing_deg,
            'radius':  radius_km,
            'label':   label,
        }

    _grid = [
        # ── 山頂 (中心) ─────────────────────────────────────────────────────
        {'lat': _CLAT, 'lon': _CLON, 'bearing': None, 'radius': 0, 'label': '利尻山頂'},
    ]

    # ── 内リング: 方位別半径 ────────────────────────────────────────────────
    # r=6km: i=0〜7  (0°〜105°, 北/北東/東1-2) — 東寄り海岸線(avg 6.2〜6.9km)に合わせる
    # r=9km: i=12   (180°, 真南)              — 南avg 8.3km, max 9.1km
    # r=9km: i=20〜23 (300°〜345°, 内西3〜北西) — 北西avg 8.8km, max 9.4km
    # r=7km: それ以外 (内東3=120°/南東/南2,3/南西/西) — i=8(120°)は南東境界のため7kmに戻す
    for _i in range(24):
        _bdeg = 15.0 * _i
        if _i <= 7:
            _r = 6.0                       # 北/北東/東1-2(0°〜105°): 東寄り近い海岸
        elif _i == 12 or _i >= 20:
            _r = 9.0                       # 真南(180°)・北西〜北北西(300°〜345°): 遠い海岸
        else:
            _r = 7.0                       # 内東3(120°)含む南東〜西: 中間帯
        _lbl  = f'内{_C8[_i // 3]}{(_i % 3) + 1}'
        _grid.append(_pt(_bdeg, _r, _lbl))

    # ── 外リング: 方位別半径, 7.5°, 22.5°, ..., 352.5° ──────────────────────
    # r=7km: i=0〜6 (7.5°〜97.5°, 外北1〜外東1) — N/NE/E海岸はavg6.2〜6.9km,max6.6〜7.5km
    #                                              8kmは沖合に出すぎのため7kmへ
    # r=8km: それ以外 — 南/西/北西は海岸が遠い(avg7.4〜8.8km)
    for _i in range(24):
        _bdeg = 15.0 * _i + 7.5
        _r    = 7.0 if _i <= 6 else 8.0
        _lbl  = f'外{_C8[_i // 3]}{(_i % 3) + 1}'
        _grid.append(_pt(_bdeg, _r, _lbl))

    return _grid

# Static, manually-verified elevations (meters) for spots that participate in
# the enhanced-forecast prefetch (currently the LINE_WEB_FORECAST_CANARY_SPOT_IDS
# canary list). Elevation is fixed per spot, so a live Open-Meteo Elevation API
# call is unnecessary for these spots — one fewer external dependency to
# protect during a sustained 429.
#
# H_2088_1443 (45.2088707, 141.1443995): 26.0m, from Open-Meteo's Elevation API
# (Copernicus GLO-90 DEM), confirmed 2026-07-27. A spot not listed here still
# gets prefetch coverage — callers use approximate_elevation_m() below instead
# of a manually-verified value, since elevation is not part of the prefetch
# cache identity (see enhanced_forecast_request()) and only nudges Open-Meteo's
# own lapse-rate-adjusted temperature.
CANARY_SPOT_ELEVATIONS_M: dict[str, float] = {
    "H_2088_1443": 26.0,
}

# Legacy "island center" coordinate used only by this rough elevation
# estimate — intentionally NOT SUMMIT_LAT/SUMMIT_LON (the JMA-corrected true
# summit used for foehn calculations above). Mirrors start.py's pre-existing
# get_elevation() live-fetch-fallback formula exactly; duplicated here (not
# imported) to keep this module Flask/pandas-independent.
_ELEVATION_APPROX_CENTER_LAT = 45.1821
_ELEVATION_APPROX_CENTER_LON = 141.2421


def approximate_elevation_m(lat: float, lon: float) -> float:
    """
    Rough, network-free elevation estimate (decay with distance from the
    island's approximate center) for spots without a manually-verified
    CANARY_SPOT_ELEVATIONS_M entry — lets GitHub Actions still fetch enhanced-
    forecast prefetch data for any newly-registered spot with zero Open-Meteo
    Elevation API calls. Safe because elevation isn't part of the prefetch
    cache identity, so an approximate value here never causes a cache-key
    mismatch against a more precise value used elsewhere.
    """
    distance = ((lat - _ELEVATION_APPROX_CENTER_LAT) ** 2 + (lon - _ELEVATION_APPROX_CENTER_LON) ** 2) ** 0.5
    return max(0.0, 200 - distance * 10000)

# Marine SST — mirrors start.py's get_sea_surface_temperature(). Separate
# endpoint (Marine API, not the Forecast API) and no `daily` section at all --
# sea_surface_temperature is an hourly-only variable there; requesting it via
# `&daily=` 400s ("Cannot initialize ForecastVariableDaily from invalid
# String value sea_surface_temperature"), a bug present since this was first
# added and only caught 2026-08-04 while debugging why the LINE canary bundle
# never had usable marine prefetch data (its generic except-clause silently
# degraded to [None]*7 on every call, so nothing ever surfaced the 400).
MARINE_HOURLY_VARS = "sea_surface_temperature"
# SST changes slowly day to day; a missed daily prefetch run shouldn't
# immediately go stale the way a fast-moving hourly forecast would.
MARINE_FRESH_MAX_AGE_MINUTES = 20 * 60   # 20h
MARINE_STALE_MAX_AGE_MINUTES = 48 * 60   # 48h

FRESH_MAX_AGE_MINUTES = 6 * 60
STALE_MAX_AGE_MINUTES = 12 * 60

# Island-distribution grid prefetch (/api/analysis/field's 49-point grid) —
# mirrors start.py's _fetch_open_meteo_multi() call from _compute_score_field()
# exactly, which already requests the superset of hourly variables every one
# of the 6 field types (score/wind/humidity/temperature/solar/precipitation)
# needs — so this ONE multi-location request's cached response can serve all
# 6 types, not just score. It also already requests FIELD_GRID_FORECAST_DAYS
# in one shot, covering every `day` (0-6) the frontend might request — unlike
# the per-spot prefetch types above, widening which (type, day) combination is
# *allowed* to consume this prefetch (start.py's _field_prefetch_allowed())
# never requires a new prefetch entry, only a gating change.
FIELD_GRID_HOURLY_VARS = (
    "temperature_2m,relative_humidity_2m,wind_speed_10m,"
    "precipitation,precipitation_probability,shortwave_radiation,"
    "dewpoint_2m,cape,wind_direction_10m"
)
FIELD_GRID_FORECAST_DAYS = 8
FIELD_GRID_MODELS = "jma_seamless"
# Mirrors start.py's _FIELD_CACHE_TTL (60min fresh) / _FIELD_CACHE_STALE_TTL
# (12h stale fallback) so the prefetch and the in-process field cache expire
# on comparable schedules.
FIELD_GRID_FRESH_MAX_AGE_MINUTES = 60
FIELD_GRID_STALE_MAX_AGE_MINUTES = 12 * 60


@dataclass(frozen=True)
class PrefetchRequest:
    api_type: str
    lat: float
    lon: float
    endpoint: str
    params: dict
    identity: str
    fingerprint: str
    redis_key: str

    def url(self) -> str:
        # apikey is appended here (not in `params`) so it never enters
        # identity/fingerprint hashing -- a rotated key must not invalidate
        # every cached prefetch entry, and the key should never end up
        # embedded in a Redis key name or a fingerprint log line.
        return f"{self.endpoint}?{urlencode(self.params)}{om_apikey_suffix()}"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso_utc(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_iso_utc(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
    except Exception:
        return None


def bool_env(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def _split_vars(value: str | None) -> list[str]:
    if not value:
        return []
    return sorted(v.strip() for v in value.split(",") if v.strip())


def _hash_obj(obj) -> str:
    raw = json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def _identity_payload(api_type: str, lat: float, lon: float, params: dict) -> dict:
    return {
        "api_type": api_type,
        "lat": round(float(lat), 5),
        "lon": round(float(lon), 5),
        "models": params.get("models"),
        "timezone": params.get("timezone"),
        "forecast_days": str(params.get("forecast_days", "")),
        "hourly": _split_vars(params.get("hourly")),
        "daily": _split_vars(params.get("daily")),
        "temperature_unit": params.get("temperature_unit"),
        "wind_speed_unit": params.get("wind_speed_unit"),
        "precipitation_unit": params.get("precipitation_unit"),
        "start_date": params.get("start_date"),
        "end_date": params.get("end_date"),
    }


def line_forecast_request(lat: float, lon: float, base_url: str | None = None) -> PrefetchRequest:
    endpoint = (base_url or os.environ.get("OPEN_METEO_BASE_URL") or f"{om_host('api')}/v1/forecast").rstrip("/")
    params = {
        "latitude": f"{float(lat):.5f}",
        "longitude": f"{float(lon):.5f}",
        "daily": LINE_DAILY_VARS,
        "hourly": LINE_HOURLY_VARS,
        "timezone": LINE_TIMEZONE,
        "forecast_days": str(LINE_FORECAST_DAYS),
    }
    identity_payload = _identity_payload("forecast", lat, lon, params)
    identity = _hash_obj(identity_payload)
    fingerprint = _hash_obj({"endpoint": endpoint, "identity": identity_payload})
    return PrefetchRequest(
        api_type="forecast",
        lat=float(lat),
        lon=float(lon),
        endpoint=endpoint,
        params=params,
        identity=identity,
        fingerprint=fingerprint,
        redis_key=f"{KEY_PREFIX}:forecast:{identity}",
    )


def enhanced_forecast_request(lat: float, lon: float, elevation: float,
                              base_url: str | None = None) -> PrefetchRequest:
    """
    Build a prefetch request for the *enhanced* (foehn/terrain-corrected)
    forecast that start.py's get_forecast() uses for /api/forecast — same
    hourly/daily variable list and `elevation` query param. Distinct
    api_type/redis_key namespace so this never collides with
    line_forecast_request()'s simple-LINE-forecast cache entries.

    `elevation` is not part of the identity hash (see _identity_payload) —
    that's fine because elevation is a fixed, spot-specific value, not
    something that varies request-to-request for the same coordinates.
    """
    endpoint = (base_url or os.environ.get("OPEN_METEO_BASE_URL") or f"{om_host('api')}/v1/forecast").rstrip("/")
    params = {
        "latitude": f"{float(lat):.5f}",
        "longitude": f"{float(lon):.5f}",
        "elevation": str(elevation),
        "daily": ENHANCED_DAILY_VARS,
        "hourly": ENHANCED_HOURLY_VARS,
        "timezone": LINE_TIMEZONE,
        "forecast_days": str(LINE_FORECAST_DAYS),
    }
    identity_payload = _identity_payload("enhanced_forecast", lat, lon, params)
    identity = _hash_obj(identity_payload)
    fingerprint = _hash_obj({"endpoint": endpoint, "identity": identity_payload})
    return PrefetchRequest(
        api_type="enhanced_forecast",
        lat=float(lat),
        lon=float(lon),
        endpoint=endpoint,
        params=params,
        identity=identity,
        fingerprint=fingerprint,
        redis_key=f"{KEY_PREFIX}:enhanced_forecast:{identity}",
    )


def summit_forecast_request(lat: float, lon: float, base_url: str | None = None) -> PrefetchRequest:
    """
    Build a prefetch request for the summit reference point's hourly
    temperature — mirrors start.py's _get_summit_hourly_temps() exactly
    (temperature_2m only, no `daily` param). Caller passes the summit's
    lat/lon explicitly; this module stays independent of start.py and does
    not hardcode or import SUMMIT_LAT/SUMMIT_LON.
    """
    endpoint = (base_url or os.environ.get("OPEN_METEO_BASE_URL") or f"{om_host('api')}/v1/forecast").rstrip("/")
    params = {
        "latitude": f"{float(lat):.5f}",
        "longitude": f"{float(lon):.5f}",
        "hourly": SUMMIT_HOURLY_VARS,
        "timezone": LINE_TIMEZONE,
        "forecast_days": str(LINE_FORECAST_DAYS),
    }
    identity_payload = _identity_payload("summit_forecast", lat, lon, params)
    identity = _hash_obj(identity_payload)
    fingerprint = _hash_obj({"endpoint": endpoint, "identity": identity_payload})
    return PrefetchRequest(
        api_type="summit_forecast",
        lat=float(lat),
        lon=float(lon),
        endpoint=endpoint,
        params=params,
        identity=identity,
        fingerprint=fingerprint,
        redis_key=f"{KEY_PREFIX}:summit_forecast:{identity}",
    )


def marine_forecast_request(lat: float, lon: float, base_url: str | None = None) -> PrefetchRequest:
    """
    Build a prefetch request for marine sea-surface-temperature data —
    mirrors start.py's get_sea_surface_temperature(). Uses the Marine API
    endpoint (distinct from the main Forecast API used by the other
    builders here) and has no `daily` section in its response at all --
    sea_surface_temperature is hourly-only (see MARINE_HOURLY_VARS comment).
    """
    endpoint = (base_url or os.environ.get("OPEN_METEO_MARINE_BASE_URL") or f"{om_host('marine-api')}/v1/marine").rstrip("/")
    params = {
        "latitude": f"{float(lat):.5f}",
        "longitude": f"{float(lon):.5f}",
        "hourly": MARINE_HOURLY_VARS,
        "timezone": LINE_TIMEZONE,
        "forecast_days": str(LINE_FORECAST_DAYS),
    }
    identity_payload = _identity_payload("marine", lat, lon, params)
    identity = _hash_obj(identity_payload)
    fingerprint = _hash_obj({"endpoint": endpoint, "identity": identity_payload})
    return PrefetchRequest(
        api_type="marine",
        lat=float(lat),
        lon=float(lon),
        endpoint=endpoint,
        params=params,
        identity=identity,
        fingerprint=fingerprint,
        redis_key=f"{KEY_PREFIX}:marine:{identity}",
    )


def field_grid_request(base_url: str | None = None) -> PrefetchRequest:
    """
    Build a prefetch request for the 49-point island-distribution grid — ONE
    multi-location Forecast API call (comma-separated lat/lon, matching
    start.py's _fetch_open_meteo_multi()) instead of one request per grid
    point or per (type, day) combination. The grid itself (build_rishiri_grid())
    is fixed/deterministic, so this request never varies — no lat/lon
    parameters on this function, unlike the single-point builders above.
    """
    grid = build_rishiri_grid()
    lats = [g["lat"] for g in grid]
    lons = [g["lon"] for g in grid]
    endpoint = (base_url or os.environ.get("OPEN_METEO_BASE_URL") or f"{om_host('api')}/v1/forecast").rstrip("/")
    params = {
        "latitude": ",".join(f"{lat:.4f}" for lat in lats),
        "longitude": ",".join(f"{lon:.4f}" for lon in lons),
        "hourly": FIELD_GRID_HOURLY_VARS,
        "timezone": LINE_TIMEZONE,
        "forecast_days": str(FIELD_GRID_FORECAST_DAYS),
        "models": FIELD_GRID_MODELS,
    }
    # The grid is fixed, so identity doesn't need a per-point lat/lon hash —
    # just the point count (as a drift guard) and the request shape.
    identity_payload = {
        "api_type": "field_grid",
        "grid_size": len(grid),
        "hourly": _split_vars(params["hourly"]),
        "timezone": params["timezone"],
        "forecast_days": params["forecast_days"],
        "models": params["models"],
    }
    identity = _hash_obj(identity_payload)
    fingerprint = _hash_obj({"endpoint": endpoint, "identity": identity_payload})
    return PrefetchRequest(
        api_type="field_grid",
        lat=SUMMIT_LAT,
        lon=SUMMIT_LON,
        endpoint=endpoint,
        params=params,
        identity=identity,
        fingerprint=fingerprint,
        redis_key=f"{KEY_PREFIX}:field_grid:{identity}",
    )


def validate_forecast_response(data: dict, *, daily_vars: str | None = LINE_DAILY_VARS,
                               hourly_vars: str | None = LINE_HOURLY_VARS) -> tuple[bool, str]:
    """
    Structural validation only (array lengths / expected keys) — no
    meteorological interpretation.

    daily_vars/hourly_vars default to the simple-LINE-forecast lists for
    backward compatibility with existing callers. Pass `None` for either
    to skip that section entirely (e.g. hourly_vars=None for marine
    responses, which have no "hourly" key at all; daily_vars=None for the
    summit request, which has no "daily" key since it omits `&daily=`).
    """
    if not isinstance(data, dict):
        return False, "not_json_object"
    if "error" in data:
        return False, "error_json"
    if daily_vars is not None:
        daily = data.get("daily")
        if not isinstance(daily, dict):
            return False, "missing_daily"
        daily_time = daily.get("time")
        if not isinstance(daily_time, list) or not daily_time:
            return False, "missing_daily_time"
        for var in _split_vars(daily_vars):
            values = daily.get(var)
            if not isinstance(values, list) or len(values) != len(daily_time):
                return False, f"bad_daily_length:{var}"
    if hourly_vars is not None:
        hourly = data.get("hourly")
        if not isinstance(hourly, dict):
            return False, "missing_hourly"
        hourly_time = hourly.get("time")
        if not isinstance(hourly_time, list) or not hourly_time:
            return False, "missing_hourly_time"
        for var in _split_vars(hourly_vars):
            values = hourly.get(var)
            if not isinstance(values, list) or len(values) != len(hourly_time):
                return False, f"bad_hourly_length:{var}"
    return True, "ok"


def validate_field_grid_response(data, *, expected_points: int,
                                 hourly_vars: str = FIELD_GRID_HOURLY_VARS) -> tuple[bool, str]:
    """
    Structural validation for field_grid_request()'s multi-location response
    — a JSON array of `expected_points` per-location objects (no `daily`
    section requested), unlike validate_forecast_response()'s single-object
    shape. Each element is validated with validate_forecast_response()
    (daily_vars=None since field_grid_request() never requests `&daily=`).
    """
    if not isinstance(data, list):
        return False, "not_json_array"
    if len(data) != expected_points:
        return False, "point_count_mismatch"
    for i, point in enumerate(data):
        ok, reason = validate_forecast_response(point, daily_vars=None, hourly_vars=hourly_vars)
        if not ok:
            return False, f"point_{i}:{reason}"
    return True, "ok"


# Per-api_type validation spec used by load_prefetch() to pick the right
# expected variable lists automatically. Falls back to the LINE defaults
# for any unrecognized/legacy api_type.
_VALIDATION_SPECS: dict[str, tuple[str | None, str | None]] = {
    "forecast": (LINE_DAILY_VARS, LINE_HOURLY_VARS),
    "enhanced_forecast": (ENHANCED_DAILY_VARS, ENHANCED_HOURLY_VARS),
    "summit_forecast": (None, SUMMIT_HOURLY_VARS),
    "marine": (None, MARINE_HOURLY_VARS),
}


def make_prefetch_record(req: PrefetchRequest, data: dict, fetched_at: datetime | None = None,
                         ttl_seconds: int = STALE_MAX_AGE_MINUTES * 60) -> dict:
    fetched = fetched_at or utc_now()
    return {
        "schema_version": SCHEMA_VERSION,
        "source": SOURCE,
        "api_type": req.api_type,
        "fetched_at": iso_utc(fetched),
        "valid_until": iso_utc(fetched + timedelta(seconds=ttl_seconds)),
        "request_fingerprint": req.fingerprint,
        "data": data,
    }


def _redis_url() -> str:
    url = os.environ.get("UPSTASH_REDIS_REST_URL", "").strip().rstrip("/")
    if url and not url.startswith("http"):
        url = "https://" + url
    return url


def _redis_token() -> str:
    return os.environ.get("UPSTASH_REDIS_REST_TOKEN", "")


def redis_get_json(key: str, requests_module=requests):
    if not _redis_url() or not _redis_token():
        return None
    try:
        resp = requests_module.get(
            f"{_redis_url()}/get/{key}",
            headers={"Authorization": f"Bearer {_redis_token()}"},
            timeout=5,
        )
        if resp.status_code != 200:
            return None
        raw = resp.json().get("result")
        if raw is None:
            return None
        if isinstance(raw, dict):
            return raw
        return json.loads(raw)
    except Exception:
        return None


def redis_set_json(key: str, value: dict, ttl_seconds: int, requests_module=requests) -> bool:
    if not _redis_url() or not _redis_token():
        return False
    try:
        resp = requests_module.post(
            _redis_url(),
            headers={"Authorization": f"Bearer {_redis_token()}", "Content-Type": "application/json"},
            json=["SET", key, json.dumps(value, ensure_ascii=False), "EX", str(max(1, int(ttl_seconds)))],
            timeout=5,
        )
        return resp.status_code == 200 and resp.json().get("result") == "OK"
    except Exception:
        return False


# Same Redis key line_integration.py (_UPSTASH_REDIS_KEY) and the GitHub
# Actions job (SUBSCRIPTIONS_KEY) already use for LINE subscription data.
# Defined here too so start.py and line_integration.py can both determine
# "which spots are currently registered for LINE notifications" without
# either importing the other (this module has neither Flask nor LINE SDK
# dependencies, and both sides already import it).
SUBSCRIPTIONS_KEY = "line_subscriptions"
_REGISTERED_SPOTS_CACHE_TTL_SECONDS = 300  # 5 minutes
_registered_spots_cache: dict = {"ids": None, "expires_at": 0.0}


def registered_spot_ids(requests_module=requests, now: float | None = None) -> set:
    """
    All spot IDs that appear in any LINE subscription's `spots` list,
    regardless of season/date-window state (unlike
    jobs/fetch_open_meteo_for_notifications.py's collect_target_spots(),
    which is scoped to "will be notified in this specific run").

    Used to widen the enhanced-forecast (foehn-corrected) canary rollout to
    automatically cover every spot a user has actually registered for,
    without needing a manual LINE_WEB_FORECAST_CANARY_SPOT_IDS env var update
    per registration.

    Cached in-process for _REGISTERED_SPOTS_CACHE_TTL_SECONDS since this is
    consulted on every single forecast fetch (both LINE's batch notify runs
    and ad-hoc bot/web queries), not just twice-daily batch jobs. A Redis
    outage degrades to an empty set (cached briefly) rather than raising —
    callers then fall back to whatever their static allowlist already covers.
    """
    import time as _time
    current = now if now is not None else _time.time()
    if _registered_spots_cache["ids"] is not None and _registered_spots_cache["expires_at"] > current:
        return _registered_spots_cache["ids"]
    subs = redis_get_json(SUBSCRIPTIONS_KEY, requests_module=requests_module)
    ids = set()
    if isinstance(subs, dict):
        for sub in subs.values():
            if isinstance(sub, dict):
                ids.update(sub.get("spots") or [])
    _registered_spots_cache["ids"] = ids
    _registered_spots_cache["expires_at"] = current + _REGISTERED_SPOTS_CACHE_TTL_SECONDS
    return ids


def _load_prefetch_generic(req: PrefetchRequest, *, validate_data_fn, allow_stale: bool,
                           now: datetime | None, requests_module,
                           fresh_max_age_minutes: int, stale_max_age_minutes: int):
    """
    Shared Redis-lookup + schema/fingerprint/freshness logic behind
    load_prefetch() (single-location dict responses) and
    load_field_grid_prefetch() (multi-location array responses) — the two
    differ only in how they validate `record["data"]`'s shape, which is why
    that step is a caller-supplied callback rather than baked in here.
    """
    meta = {"prefetched": False, "stale": False, "age_minutes": None, "reason": "miss"}
    record = redis_get_json(req.redis_key, requests_module=requests_module)
    if not isinstance(record, dict):
        return None, meta
    if record.get("schema_version") != SCHEMA_VERSION:
        meta["reason"] = "schema_mismatch"
        return None, meta
    if record.get("request_fingerprint") != req.fingerprint:
        meta["reason"] = "fingerprint_mismatch"
        return None, meta
    if record.get("api_type") != req.api_type or record.get("source") != SOURCE:
        meta["reason"] = "source_mismatch"
        return None, meta
    ok, reason = validate_data_fn(record.get("data"))
    if not ok:
        meta["reason"] = reason
        return None, meta
    fetched = parse_iso_utc(record.get("fetched_at"))
    if fetched is None:
        meta["reason"] = "bad_fetched_at"
        return None, meta
    current = now or utc_now()
    age_minutes = max(0, int((current - fetched).total_seconds() // 60))
    meta.update({
        "prefetched": True,
        "fetched_at": record.get("fetched_at"),
        "age_minutes": age_minutes,
        "reason": "hit",
    })
    if age_minutes <= fresh_max_age_minutes:
        return record["data"], meta
    if allow_stale and age_minutes <= stale_max_age_minutes:
        meta["stale"] = True
        meta["reason"] = "stale_hit"
        return record["data"], meta
    meta["prefetched"] = False
    meta["reason"] = "stale_expired"
    return None, meta


def load_prefetch(req: PrefetchRequest, *, allow_stale: bool = True,
                  now: datetime | None = None, requests_module=requests,
                  fresh_max_age_minutes: int = FRESH_MAX_AGE_MINUTES,
                  stale_max_age_minutes: int = STALE_MAX_AGE_MINUTES) -> tuple[dict | None, dict]:
    """
    fresh_max_age_minutes/stale_max_age_minutes default to the simple-LINE-
    forecast windows for backward compatibility. Pass MARINE_FRESH_MAX_AGE_MINUTES/
    MARINE_STALE_MAX_AGE_MINUTES (or similar) for slower-changing data types.
    """
    daily_vars, hourly_vars = _VALIDATION_SPECS.get(
        req.api_type, (LINE_DAILY_VARS, LINE_HOURLY_VARS)
    )
    return _load_prefetch_generic(
        req,
        validate_data_fn=lambda data: validate_forecast_response(
            data, daily_vars=daily_vars, hourly_vars=hourly_vars
        ),
        allow_stale=allow_stale, now=now, requests_module=requests_module,
        fresh_max_age_minutes=fresh_max_age_minutes, stale_max_age_minutes=stale_max_age_minutes,
    )


def load_field_grid_prefetch(req: PrefetchRequest, *, allow_stale: bool = True,
                             now: datetime | None = None, requests_module=requests,
                             fresh_max_age_minutes: int = FIELD_GRID_FRESH_MAX_AGE_MINUTES,
                             stale_max_age_minutes: int = FIELD_GRID_STALE_MAX_AGE_MINUTES
                             ) -> tuple[list | None, dict]:
    """
    Same freshness/staleness semantics as load_prefetch(), but validates the
    array-of-49-points response shape produced by field_grid_request()
    instead of load_prefetch()'s single-location dict shape.
    """
    expected_points = len(build_rishiri_grid())
    return _load_prefetch_generic(
        req,
        validate_data_fn=lambda data: validate_field_grid_response(data, expected_points=expected_points),
        allow_stale=allow_stale, now=now, requests_module=requests_module,
        fresh_max_age_minutes=fresh_max_age_minutes, stale_max_age_minutes=stale_max_age_minutes,
    )
