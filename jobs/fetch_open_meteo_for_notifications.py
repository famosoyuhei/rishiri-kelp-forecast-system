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
    GITHUB_ACTIONS_CIRCUIT_KEY,
    STALE_MAX_AGE_MINUTES,
    iso_utc,
    line_forecast_request,
    make_prefetch_record,
    parse_iso_utc,
    redis_get_json,
    redis_set_json,
    utc_now,
    validate_forecast_response,
)

JST = timezone(timedelta(hours=9))
SUBSCRIPTIONS_KEY = "line_subscriptions"
SPOTS_CSV = ROOT / "hoshiba_spots.csv"
TTL_SECONDS = STALE_MAX_AGE_MINUTES * 60


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
