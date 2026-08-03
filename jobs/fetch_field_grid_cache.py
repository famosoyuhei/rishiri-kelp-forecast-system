#!/usr/bin/env python3
"""Prefetch the 49-point island-distribution grid's raw Open-Meteo response.

This script is intended for GitHub Actions. It does not call Render and does
not compute drying scores, foehn adjustments, or any other domain logic --
just fetches and validates the raw multi-location Forecast API response and
stores it in Upstash Redis, mirroring
jobs/fetch_open_meteo_for_notifications.py's structure. See
docs/OPEN_METEO_TEMPORARY_PREFETCH.md for the wider prefetch mitigation this
is part of.
"""
from __future__ import annotations

from datetime import timedelta, timezone
from email.utils import parsedate_to_datetime
import json
from pathlib import Path
import sys
import time

import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from open_meteo_prefetch import (  # noqa: E402
    FIELD_GRID_STALE_MAX_AGE_MINUTES,
    GITHUB_ACTIONS_CIRCUIT_KEY,
    build_rishiri_grid,
    field_grid_request,
    iso_utc,
    make_prefetch_record,
    parse_iso_utc,
    redis_set_json,
    utc_now,
    validate_field_grid_response,
)

TTL_SECONDS = FIELD_GRID_STALE_MAX_AGE_MINUTES * 60


def log_event(**fields) -> None:
    safe = {k: v for k, v in fields.items() if v is not None}
    print(json.dumps(safe, ensure_ascii=False, sort_keys=True))


def _open_github_circuit(retry_after: str | None) -> None:
    now = utc_now()
    retry_at = None
    if retry_after:
        try:
            seconds = int(retry_after)
            retry_at = now + timedelta(seconds=max(0, seconds))
        except ValueError:
            try:
                parsed = parsedate_to_datetime(retry_after)
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=timezone.utc)
                retry_at = parsed.astimezone(timezone.utc)
            except Exception:
                retry_at = parse_iso_utc(retry_after)
    retry_at = (retry_at or (now + timedelta(minutes=30))) + timedelta(minutes=5)
    payload = {
        "opened_at": iso_utc(now),
        "retry_after_at": iso_utc(retry_at),
        "reason": "429",
        "source": "github_actions",
        "consecutive_429_count": 1,
    }
    ttl = max(1, int((retry_at - now).total_seconds()))
    redis_set_json(GITHUB_ACTIONS_CIRCUIT_KEY, payload, ttl)


def main(argv=None) -> int:
    req = field_grid_request()
    expected_points = len(build_rishiri_grid())
    started = time.perf_counter()
    log_event(event="request", api_type=req.api_type, status="start", points=expected_points)

    try:
        resp = requests.get(req.url(), timeout=30)
    except requests.exceptions.RequestException as e:
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        log_event(event="network_error", api_type=req.api_type, status=type(e).__name__, elapsed_ms=elapsed_ms)
        # A transient network error just means this run's data doesn't get
        # refreshed -- the previous prefetch stays valid until its own TTL
        # expires, and the next scheduled run tries again. Not worth a
        # "Run failed" email (same rationale as fetch_open_meteo_for_notifications.py).
        return 0

    elapsed_ms = int((time.perf_counter() - started) * 1000)
    if resp.status_code == 429:
        retry_after = resp.headers.get("Retry-After")
        _open_github_circuit(retry_after)
        log_event(
            event="rate_limited", api_type=req.api_type, status=429,
            elapsed_ms=elapsed_ms, retry_after=retry_after,
        )
        # A 429 is an expected, designed-for outcome (this prefetch exists
        # specifically to survive a sustained Open-Meteo 429) -- not a bug.
        return 0

    if resp.status_code < 200 or resp.status_code >= 300:
        log_event(event="http_error", api_type=req.api_type, status=resp.status_code, elapsed_ms=elapsed_ms)
        return 1

    try:
        data = resp.json()
    except Exception:
        log_event(event="invalid_json", api_type=req.api_type, elapsed_ms=elapsed_ms)
        return 1

    ok, reason = validate_field_grid_response(data, expected_points=expected_points)
    if not ok:
        log_event(event="invalid_response", api_type=req.api_type, status=reason, elapsed_ms=elapsed_ms)
        return 1

    record = make_prefetch_record(req, data, ttl_seconds=TTL_SECONDS)
    if not redis_set_json(req.redis_key, record, TTL_SECONDS):
        log_event(event="cache_write", api_type=req.api_type, status="failed", elapsed_ms=elapsed_ms)
        return 1

    log_event(
        event="success", api_type=req.api_type, status="ok",
        elapsed_ms=elapsed_ms, fetched_at=record["fetched_at"],
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
