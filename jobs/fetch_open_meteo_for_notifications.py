#!/usr/bin/env python3
"""Prefetch raw Open-Meteo forecast JSON for LINE notifications.

This script is intended for GitHub Actions. It does not call Render and does
not perform any drying-score, foehn, or notification formatting logic.
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
import json
import os
from pathlib import Path
import sys
import time

import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from open_meteo_prefetch import (  # noqa: E402
    CANARY_SPOT_ELEVATIONS_M,
    ENHANCED_DAILY_VARS,
    ENHANCED_HOURLY_VARS,
    GITHUB_ACTIONS_CIRCUIT_KEY,
    MARINE_DAILY_VARS,
    MARINE_STALE_MAX_AGE_MINUTES,
    STALE_MAX_AGE_MINUTES,
    SUMMIT_HOURLY_VARS,
    SUMMIT_LAT,
    SUMMIT_LON,
    approximate_elevation_m,
    enhanced_forecast_request,
    iso_utc,
    line_forecast_request,
    make_prefetch_record,
    marine_forecast_request,
    parse_iso_utc,
    redis_get_json,
    redis_set_json,
    summit_forecast_request,
    utc_now,
    validate_forecast_response,
)

JST = timezone(timedelta(hours=9))
SUBSCRIPTIONS_KEY = "line_subscriptions"
SPOTS_CSV = ROOT / "hoshiba_spots.csv"
TTL_SECONDS = STALE_MAX_AGE_MINUTES * 60
MARINE_TTL_SECONDS = MARINE_STALE_MAX_AGE_MINUTES * 60
CANARY_SPOT_IDS_ENV = "LINE_WEB_FORECAST_CANARY_SPOT_IDS"


class RateLimited(Exception):
    def __init__(self, retry_after: str | None = None):
        self.retry_after = retry_after
        super().__init__("Open-Meteo returned 429")


def log_event(**fields) -> None:
    safe = {k: v for k, v in fields.items() if v is not None}
    print(json.dumps(safe, ensure_ascii=False, sort_keys=True))


def _parse_mmdd(value: str) -> tuple[int, int] | None:
    if not value or "-" not in value:
        return None
    try:
        m, d = value.split("-", 1)
        return int(m), int(d)
    except Exception:
        return None


def _mmdd_key(dt) -> str:
    return f"{dt.month:02d}-{dt.day:02d}"


def _load_spots() -> dict:
    spots = {}
    with SPOTS_CSV.open("r", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            name = (row.get("name") or "").strip()
            if not name:
                continue
            try:
                spots[name] = {"lat": float(row["lat"]), "lon": float(row["lon"])}
            except (KeyError, ValueError):
                continue
    return spots


def _target_date(kind: str, now_jst: datetime):
    if kind == "evening":
        return (now_jst + timedelta(days=1)).date()
    return now_jst.date()


def _subscription_active(sub: dict, target_date) -> bool:
    if not isinstance(sub, dict) or not sub.get("notify_enabled", False):
        return False
    target_mmdd = f"{target_date.month:02d}-{target_date.day:02d}"
    season_start = sub.get("season_start") or ""
    season_end = sub.get("season_end") or ""
    if season_start and target_mmdd < season_start:
        return False
    if season_end and target_mmdd > season_end:
        return False
    if target_date.strftime("%Y-%m-%d") in (sub.get("nogo_dates") or []):
        return False
    return True


def collect_target_spots(kind: str, now_jst: datetime | None = None) -> list[dict]:
    now = now_jst or datetime.now(JST)
    target_date = _target_date(kind, now)
    subs = redis_get_json(SUBSCRIPTIONS_KEY)
    if not isinstance(subs, dict):
        log_event(event="load_subscriptions", status="empty_or_unavailable")
        return []
    spot_rows = _load_spots()
    seen = set()
    targets = []
    for sub in subs.values():
        if not _subscription_active(sub, target_date):
            continue
        for sid in (sub.get("spots") or [])[:5]:
            if sid in seen or sid not in spot_rows:
                continue
            seen.add(sid)
            targets.append({"spot_id": sid, **spot_rows[sid]})
    return targets


def collect_canary_targets(kind: str, now_jst: datetime | None = None) -> list[dict]:
    """
    Spots that should get the enhanced (foehn/terrain-corrected) forecast
    prefetch: the static LINE_WEB_FORECAST_CANARY_SPOT_IDS allowlist UNIONed
    with every spot actively targeted for this run's LINE notification
    (collect_target_spots()) — so any spot a user has actually registered for
    gets this Open-Meteo-429 resilience automatically, without a manual env
    var update per registration. Expanding beyond currently-registered spots
    (e.g. to all 334) is a separate, deliberate decision left to
    LINE_WEB_FORECAST_CANARY_SPOT_IDS.
    """
    raw = os.environ.get(CANARY_SPOT_IDS_ENV, "")
    static_ids = [s.strip() for s in raw.split(",") if s.strip()]
    spot_rows = _load_spots()

    targets_by_id: dict[str, dict] = {}
    for sid in static_ids:
        if sid not in spot_rows:
            log_event(event="canary_target", spot_id=sid, status="not_found_in_spots_csv")
            continue
        targets_by_id[sid] = {"spot_id": sid, **spot_rows[sid]}

    for target in collect_target_spots(kind, now_jst):
        targets_by_id.setdefault(target["spot_id"], target)

    return list(targets_by_id.values())


def _canary_requests_for_target(target: dict):
    """
    Yield (PrefetchRequest, ttl_seconds, daily_vars, hourly_vars) tuples for
    one canary spot's enhanced-forecast and marine-SST prefetch. The summit
    reference point is shared across all canary spots and is fetched
    separately by the caller (once per run, not once per spot).

    Elevation comes from the manually-verified CANARY_SPOT_ELEVATIONS_M table
    when available, else a network-free approximation
    (approximate_elevation_m) — never a live Elevation API call. Elevation is
    not part of the enhanced-forecast prefetch cache identity, so an
    approximate value here is safe (see enhanced_forecast_request()).
    """
    spot_id = target["spot_id"]
    elevation = CANARY_SPOT_ELEVATIONS_M.get(spot_id)
    if elevation is None:
        elevation = approximate_elevation_m(target["lat"], target["lon"])
    req = enhanced_forecast_request(target["lat"], target["lon"], elevation)
    yield req, TTL_SECONDS, ENHANCED_DAILY_VARS, ENHANCED_HOURLY_VARS
    marine_req = marine_forecast_request(target["lat"], target["lon"])
    yield marine_req, MARINE_TTL_SECONDS, MARINE_DAILY_VARS, None


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


def fetch_one(target: dict, session=requests) -> tuple[bool, str]:
    req = line_forecast_request(target["lat"], target["lon"])
    started = time.perf_counter()
    log_event(event="request", api_type=req.api_type, status="start")
    resp = session.get(req.url(), timeout=20)
    elapsed_ms = int((time.perf_counter() - started) * 1000)
    if resp.status_code == 429:
        retry_after = resp.headers.get("Retry-After")
        _open_github_circuit(retry_after)
        log_event(
            event="rate_limited",
            api_type=req.api_type,
            status=429,
            elapsed_ms=elapsed_ms,
            retry_after=retry_after,
        )
        raise RateLimited(retry_after)
    if resp.status_code < 200 or resp.status_code >= 300:
        log_event(event="http_error", api_type=req.api_type, status=resp.status_code, elapsed_ms=elapsed_ms)
        return False, f"http_{resp.status_code}"
    try:
        data = resp.json()
    except Exception:
        log_event(event="invalid_json", api_type=req.api_type, elapsed_ms=elapsed_ms)
        return False, "invalid_json"
    ok, reason = validate_forecast_response(data)
    if not ok:
        log_event(event="invalid_response", api_type=req.api_type, status=reason, elapsed_ms=elapsed_ms)
        return False, reason
    record = make_prefetch_record(req, data, ttl_seconds=TTL_SECONDS)
    if not redis_set_json(req.redis_key, record, TTL_SECONDS):
        log_event(event="cache_write", api_type=req.api_type, status="failed", elapsed_ms=elapsed_ms)
        return False, "cache_write_failed"
    log_event(
        event="success",
        api_type=req.api_type,
        status="ok",
        elapsed_ms=elapsed_ms,
        cache_write_count=1,
        fetched_at=record["fetched_at"],
    )
    return True, "ok"


def fetch_request(req, *, ttl_seconds: int, daily_vars: str | None, hourly_vars: str | None,
                   session=requests) -> tuple[bool, str]:
    """
    Generic version of fetch_one() for the enhanced/summit/marine prefetch
    types, which use different variable lists (and, for summit/marine,
    validate only one of daily/hourly rather than both). fetch_one() itself
    is left untouched since it already has dedicated tests covering the
    simple-LINE-forecast path.
    """
    started = time.perf_counter()
    log_event(event="request", api_type=req.api_type, status="start")
    resp = session.get(req.url(), timeout=20)
    elapsed_ms = int((time.perf_counter() - started) * 1000)
    if resp.status_code == 429:
        retry_after = resp.headers.get("Retry-After")
        _open_github_circuit(retry_after)
        log_event(
            event="rate_limited",
            api_type=req.api_type,
            status=429,
            elapsed_ms=elapsed_ms,
            retry_after=retry_after,
        )
        raise RateLimited(retry_after)
    if resp.status_code < 200 or resp.status_code >= 300:
        log_event(event="http_error", api_type=req.api_type, status=resp.status_code, elapsed_ms=elapsed_ms)
        return False, f"http_{resp.status_code}"
    try:
        data = resp.json()
    except Exception:
        log_event(event="invalid_json", api_type=req.api_type, elapsed_ms=elapsed_ms)
        return False, "invalid_json"
    ok, reason = validate_forecast_response(data, daily_vars=daily_vars, hourly_vars=hourly_vars)
    if not ok:
        log_event(event="invalid_response", api_type=req.api_type, status=reason, elapsed_ms=elapsed_ms)
        return False, reason
    record = make_prefetch_record(req, data, ttl_seconds=ttl_seconds)
    if not redis_set_json(req.redis_key, record, ttl_seconds):
        log_event(event="cache_write", api_type=req.api_type, status="failed", elapsed_ms=elapsed_ms)
        return False, "cache_write_failed"
    log_event(
        event="success",
        api_type=req.api_type,
        status="ok",
        elapsed_ms=elapsed_ms,
        cache_write_count=1,
        fetched_at=record["fetched_at"],
    )
    return True, "ok"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--kind", choices=("morning", "evening"), required=True)
    parser.add_argument("--limit", type=int, default=0, help="Optional test limit; 0 means all targets.")
    args = parser.parse_args(argv)

    targets = collect_target_spots(args.kind)
    if args.limit and args.limit > 0:
        targets = targets[:args.limit]
    request_count = 0
    success_count = 0
    started = time.perf_counter()

    try:
        for target in targets:
            request_count += 1
            ok, _reason = fetch_one(target)
            if ok:
                success_count += 1

        canary_targets = collect_canary_targets(args.kind)
        if canary_targets:
            summit_req = summit_forecast_request(SUMMIT_LAT, SUMMIT_LON)
            request_count += 1
            ok, _reason = fetch_request(
                summit_req, ttl_seconds=TTL_SECONDS, daily_vars=None, hourly_vars=SUMMIT_HOURLY_VARS,
            )
            if ok:
                success_count += 1
            for target in canary_targets:
                for req, ttl, daily_vars, hourly_vars in _canary_requests_for_target(target):
                    request_count += 1
                    ok, _reason = fetch_request(
                        req, ttl_seconds=ttl, daily_vars=daily_vars, hourly_vars=hourly_vars,
                    )
                    if ok:
                        success_count += 1
    except RateLimited:
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        log_event(
            event="complete",
            status="rate_limited",
            request_count=request_count,
            success_count=success_count,
            elapsed_ms=elapsed_ms,
        )
        return 2

    elapsed_ms = int((time.perf_counter() - started) * 1000)
    log_event(
        event="complete",
        status="ok",
        request_count=request_count,
        success_count=success_count,
        cache_write_count=success_count,
        elapsed_ms=elapsed_ms,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
