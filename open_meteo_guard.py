"""Small Open-Meteo rate-limit guard shared by production entry points.

This module deliberately logs only route-level metadata. It must not log
coordinates, full URLs, forecast payloads, Redis values, or user identifiers.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
import json
import os
import time

import requests


CIRCUIT_KEY = "om:circuit:v1"
_MEM_CIRCUIT: dict | None = None


@dataclass
class OpenMeteoRateLimitError(Exception):
    http_status: int
    retry_after_raw: str | None
    retry_after_at: str
    source: str
    occurred_at: str
    body_excerpt: str
    consecutive_429_count: int

    def __str__(self) -> str:
        return f"Open-Meteo 429 source={self.source} retry_after_at={self.retry_after_at}"


class OpenMeteoCircuitOpenError(Exception):
    def __init__(self, source: str, retry_after_at: str | None = None):
        self.source = source
        self.retry_after_at = retry_after_at
        super().__init__(f"Open-Meteo circuit open source={source} retry_after_at={retry_after_at}")


def is_enabled() -> bool:
    return os.environ.get("OPEN_METEO_CIRCUIT_BREAKER_ENABLED", "true").strip().lower() not in (
        "0", "false", "no", "off"
    )


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso_utc(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_retry_after(value: str | None, now: datetime | None = None) -> datetime | None:
    if not value:
        return None
    now = now or utc_now()
    raw = str(value).strip()
    if not raw:
        return None
    try:
        seconds = int(raw)
        if seconds < 0:
            return None
        return now + timedelta(seconds=seconds)
    except ValueError:
        pass
    try:
        parsed = parsedate_to_datetime(raw)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except Exception:
        return None


def _fallback_seconds(consecutive_count: int) -> int:
    if consecutive_count <= 1:
        return 30 * 60
    if consecutive_count == 2:
        return 60 * 60
    if consecutive_count == 3:
        return 2 * 60 * 60
    return 6 * 60 * 60


def _redis_url() -> str:
    url = os.environ.get("UPSTASH_REDIS_REST_URL", "").strip().rstrip("/")
    if url and not url.startswith("http"):
        url = "https://" + url
    return url


def _redis_token() -> str:
    return os.environ.get("UPSTASH_REDIS_REST_TOKEN", "")


def _redis_get(key: str):
    if not _redis_url() or not _redis_token():
        return None
    try:
        resp = requests.get(
            f"{_redis_url()}/get/{key}",
            headers={"Authorization": f"Bearer {_redis_token()}"},
            timeout=2,
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


def _redis_set(key: str, value: dict, ttl: int) -> bool:
    if not _redis_url() or not _redis_token():
        return False
    try:
        resp = requests.post(
            _redis_url(),
            headers={"Authorization": f"Bearer {_redis_token()}", "Content-Type": "application/json"},
            json=["SET", key, json.dumps(value, ensure_ascii=False), "EX", str(max(1, int(ttl)))],
            timeout=2,
        )
        return resp.status_code == 200 and resp.json().get("result") == "OK"
    except Exception:
        return False


def _redis_del(key: str) -> bool:
    if not _redis_url() or not _redis_token():
        return False
    try:
        resp = requests.post(
            _redis_url(),
            headers={"Authorization": f"Bearer {_redis_token()}", "Content-Type": "application/json"},
            json=["DEL", key],
            timeout=2,
        )
        return resp.status_code == 200
    except Exception:
        return False


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
    except Exception:
        return None


def get_circuit() -> dict | None:
    global _MEM_CIRCUIT
    if not is_enabled():
        return None
    data = _redis_get(CIRCUIT_KEY)
    if not isinstance(data, dict):
        data = _MEM_CIRCUIT
    if not isinstance(data, dict):
        return None
    retry_at = _parse_iso(data.get("retry_after_at"))
    if retry_at and retry_at > utc_now():
        return data
    return None


def is_circuit_open() -> bool:
    return get_circuit() is not None


def _safe_body_excerpt(response) -> str:
    try:
        text = response.text or ""
    except Exception:
        return ""
    return text[:240].replace("\n", " ").replace("\r", " ")


def _log(logger, **fields) -> None:
    if not logger:
        return
    safe = {k: v for k, v in fields.items() if v is not None}
    logger.info("[open_meteo] %s", json.dumps(safe, ensure_ascii=False, sort_keys=True))


def open_circuit(source: str, retry_after_raw: str | None, response=None, logger=None) -> OpenMeteoRateLimitError:
    global _MEM_CIRCUIT
    now = utc_now()
    previous = get_circuit()
    count = int(previous.get("consecutive_429_count", 0)) + 1 if previous else 1
    retry_dt = parse_retry_after(retry_after_raw, now=now)
    if retry_dt is not None:
        retry_dt = retry_dt + timedelta(minutes=5)
    else:
        retry_dt = now + timedelta(seconds=_fallback_seconds(count))
    ttl = max(1, int((retry_dt - now).total_seconds()))
    payload = {
        "opened_at": iso_utc(now),
        "retry_after_at": iso_utc(retry_dt),
        "reason": "429",
        "source": source,
        "consecutive_429_count": count,
    }
    _MEM_CIRCUIT = payload
    _redis_set(CIRCUIT_KEY, payload, ttl)
    err = OpenMeteoRateLimitError(
        http_status=429,
        retry_after_raw=retry_after_raw,
        retry_after_at=payload["retry_after_at"],
        source=source,
        occurred_at=payload["opened_at"],
        body_excerpt=_safe_body_excerpt(response) if response is not None else "",
        consecutive_429_count=count,
    )
    _log(
        logger,
        source=source,
        event="rate_limited",
        http_status=429,
        retry_after_at=payload["retry_after_at"],
        consecutive_429_count=count,
    )
    return err


def close_circuit(source: str, logger=None) -> None:
    global _MEM_CIRCUIT
    if not is_enabled():
        return
    had_open = get_circuit() is not None or _MEM_CIRCUIT is not None
    _MEM_CIRCUIT = None
    _redis_del(CIRCUIT_KEY)
    if had_open:
        _log(logger, source=source, event="circuit_closed", consecutive_429_count=0)


def ensure_request_allowed(source: str, logger=None, processed_count=None, remaining_count=None) -> None:
    circuit = get_circuit()
    if not circuit:
        return
    _log(
        logger,
        source=source,
        event="circuit_open",
        retry_after_at=circuit.get("retry_after_at"),
        consecutive_429_count=circuit.get("consecutive_429_count"),
        processed_count=processed_count,
        remaining_count=remaining_count,
    )
    raise OpenMeteoCircuitOpenError(source, circuit.get("retry_after_at"))


def guarded_get(url: str, *, source: str, logger=None, requests_module=requests, **kwargs):
    if not is_enabled():
        return requests_module.get(url, **kwargs)
    ensure_request_allowed(source, logger=logger)
    started = time.perf_counter()
    _log(logger, source=source, event="request", cache="miss")
    resp = requests_module.get(url, **kwargs)
    elapsed_ms = int((time.perf_counter() - started) * 1000)
    if getattr(resp, "status_code", None) == 429:
        retry_after_raw = resp.headers.get("Retry-After") if hasattr(resp, "headers") else None
        err = open_circuit(source, retry_after_raw, response=resp, logger=logger)
        err.elapsed_ms = elapsed_ms
        raise err
    resp.raise_for_status()
    close_circuit(source, logger=logger)
    _log(logger, source=source, event="success", cache="miss", http_status=resp.status_code, elapsed_ms=elapsed_ms)
    return resp
