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

FRESH_MAX_AGE_MINUTES = 6 * 60
STALE_MAX_AGE_MINUTES = 12 * 60


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
        return f"{self.endpoint}?{urlencode(self.params)}"


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
    endpoint = (base_url or os.environ.get("OPEN_METEO_BASE_URL") or "https://api.open-meteo.com/v1/forecast").rstrip("/")
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


def validate_forecast_response(data: dict) -> tuple[bool, str]:
    if not isinstance(data, dict):
        return False, "not_json_object"
    if "error" in data:
        return False, "error_json"
    daily = data.get("daily")
    hourly = data.get("hourly")
    if not isinstance(daily, dict) or not isinstance(hourly, dict):
        return False, "missing_daily_or_hourly"
    daily_time = daily.get("time")
    hourly_time = hourly.get("time")
    if not isinstance(daily_time, list) or not daily_time:
        return False, "missing_daily_time"
    if not isinstance(hourly_time, list) or not hourly_time:
        return False, "missing_hourly_time"
    for var in _split_vars(LINE_DAILY_VARS):
        values = daily.get(var)
        if not isinstance(values, list) or len(values) != len(daily_time):
            return False, f"bad_daily_length:{var}"
    for var in _split_vars(LINE_HOURLY_VARS):
        values = hourly.get(var)
        if not isinstance(values, list) or len(values) != len(hourly_time):
            return False, f"bad_hourly_length:{var}"
    return True, "ok"


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


def load_prefetch(req: PrefetchRequest, *, allow_stale: bool = True,
                  now: datetime | None = None, requests_module=requests) -> tuple[dict | None, dict]:
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
    ok, reason = validate_forecast_response(record.get("data"))
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
    if age_minutes <= FRESH_MAX_AGE_MINUTES:
        return record["data"], meta
    if allow_stale and age_minutes <= STALE_MAX_AGE_MINUTES:
        meta["stale"] = True
        meta["reason"] = "stale_hit"
        return record["data"], meta
    meta["prefetched"] = False
    meta["reason"] = "stale_expired"
    return None, meta
