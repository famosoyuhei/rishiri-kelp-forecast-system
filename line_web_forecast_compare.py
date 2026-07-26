"""Pure helpers for comparing LINE simplified forecasts with web forecasts.

This module is the first step toward moving LINE notifications to the same
foehn-aware drying judgment used by the web forecast.  It intentionally does
not fetch weather data, read Redis, send LINE messages, or change production
notification behavior.
"""
from __future__ import annotations

import json
import os
from typing import Any


def _num(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _round(value: float | None, digits: int = 1) -> float | None:
    return round(value, digits) if value is not None else None


def _web_summary(web_day: dict) -> dict:
    summary = web_day.get("daily_summary") if isinstance(web_day, dict) else None
    return summary if isinstance(summary, dict) else (web_day if isinstance(web_day, dict) else {})


def web_day_from_forecast_history(record: dict) -> dict | None:
    """Convert a saved forecast-history record into a web-day shape.

    Only records explicitly marked as ``logic_source=web_forecast`` are accepted.
    The 16:20 all-spot snapshot currently stores LINE simplified values, and
    older records have no provenance, so both must be skipped for shadow
    comparison.
    """
    if not isinstance(record, dict):
        return None
    if record.get("logic_source") != "web_forecast":
        return None
    return {
        "date": record.get("target_date"),
        "day_number": record.get("day_number"),
        "daily_summary": {
            "temperature_max": record.get("max_temp"),
            "humidity": record.get("min_humidity"),
            "wind_speed": record.get("avg_wind"),
            "precipitation": record.get("precipitation_0416", record.get("precipitation")),
            "drying_score": record.get("drying_score"),
            "suitability": record.get("suitability"),
            "foehn_bonus": record.get("foehn_bonus"),
            "local_risk_adjustments": {
                "foehn_adjustment": record.get("foehn_adjustment"),
            },
        },
    }


def compare_line_and_web_forecast(line_day: dict, web_day: dict) -> dict:
    """Return a serializable difference summary for one forecast day.

    ``line_day`` is a day entry returned by line_integration.get_forecast_for_spot().
    ``web_day`` can be either a full /api/forecast day entry or its
    ``daily_summary`` object.
    """
    web = _web_summary(web_day)
    line_score = _num(line_day.get("score"))
    web_score = _num(web.get("drying_score"))
    score_delta = None if line_score is None or web_score is None else web_score - line_score

    local_adj = web.get("local_risk_adjustments") if isinstance(web.get("local_risk_adjustments"), dict) else {}
    foehn_adjustment = _num(local_adj.get("foehn_adjustment"))
    foehn_bonus = _num(web.get("foehn_bonus"))
    foehn_present = any((value or 0) > 0 for value in (foehn_adjustment, foehn_bonus))

    line_precip = _num(line_day.get("precipitation"))
    line_precip_0416 = _num(line_day.get("precipitation_0416"))
    web_precip = _num(web.get("precipitation"))

    return {
        "date": line_day.get("date") or web_day.get("date"),
        "day_number": line_day.get("day_number") if line_day.get("day_number") is not None else web_day.get("day_number"),
        "line": {
            "score": _round(line_score),
            "suitability": line_day.get("suitability"),
            "precipitation": _round(line_precip),
            "precipitation_0416": _round(line_precip_0416),
            "min_humidity": _round(_num(line_day.get("min_humidity"))),
            "avg_wind": _round(_num(line_day.get("avg_wind"))),
            "pop": _round(_num(line_day.get("pop")), 0),
            "wind_direction_period": line_day.get("wind_direction_period"),
        },
        "web": {
            "score": _round(web_score),
            "suitability": web.get("suitability"),
            "precipitation": _round(web_precip),
            "humidity": _round(_num(web.get("humidity"))),
            "wind_speed": _round(_num(web.get("wind_speed"))),
            "wind_direction": _round(_num(web.get("wind_direction")), 0),
            "pop": _round(_num(web.get("precipitation_probability")), 0),
            "foehn_bonus": _round(foehn_bonus),
            "foehn_adjustment": _round(foehn_adjustment),
        },
        "diff": {
            "score_delta_web_minus_line": _round(score_delta),
            "score_abs_delta": _round(abs(score_delta)) if score_delta is not None else None,
            "suitability_changed": line_day.get("suitability") != web.get("suitability"),
            "foehn_present_in_web": foehn_present,
            "line_daily_precip_differs_from_0416": (
                line_precip is not None
                and line_precip_0416 is not None
                and round(line_precip, 2) != round(line_precip_0416, 2)
            ),
            "web_precip_differs_from_line_0416": (
                web_precip is not None
                and line_precip_0416 is not None
                and round(web_precip, 2) != round(line_precip_0416, 2)
            ),
        },
    }


def _index_days(days: list[dict]) -> dict:
    indexed = {}
    for day in days or []:
        if not isinstance(day, dict):
            continue
        key = day.get("date")
        if key is None:
            key = day.get("day_number")
        if key is not None:
            indexed[key] = day
    return indexed


def compare_line_and_web_forecasts(line_days: list[dict], web_days: list[dict]) -> list[dict]:
    """Compare all matching LINE and web forecast days.

    Matching prefers ``date`` and falls back to ``day_number`` when date is
    absent.  Unmatched days are ignored so callers can pass partial web output
    safely during shadow-mode experiments.
    """
    web_by_key = _index_days(web_days)
    results = []
    for line_day in line_days or []:
        if not isinstance(line_day, dict):
            continue
        key = line_day.get("date")
        if key is None:
            key = line_day.get("day_number")
        web_day = web_by_key.get(key)
        if web_day is not None:
            results.append(compare_line_and_web_forecast(line_day, web_day))
    return results


def shadow_compare_enabled(env: dict | None = None) -> bool:
    """Feature flag for future LINE-vs-web shadow comparison.

    The default is intentionally off.  Enabling this flag must not by itself
    fetch web forecasts; it only permits logging comparisons when both sides
    have already been supplied by the caller.
    """
    source = env if env is not None else os.environ
    return str(source.get("LINE_WEB_FORECAST_SHADOW_COMPARE_ENABLED", "false")).strip().lower() in (
        "1", "true", "yes", "on",
    )


def shadow_comparison_summary(comparisons: list[dict], *, source: str = "line") -> dict:
    """Return log-safe aggregate fields for shadow comparison output."""
    score_deltas = [
        _num(item.get("diff", {}).get("score_abs_delta"))
        for item in comparisons or []
        if isinstance(item, dict)
    ]
    score_deltas = [value for value in score_deltas if value is not None]
    return {
        "source": source,
        "event": "line_web_shadow_compare",
        "matched_days": len(comparisons or []),
        "max_score_abs_delta": _round(max(score_deltas), 1) if score_deltas else None,
        "suitability_changed_count": sum(
            1 for item in comparisons or []
            if isinstance(item, dict) and item.get("diff", {}).get("suitability_changed") is True
        ),
        "foehn_present_count": sum(
            1 for item in comparisons or []
            if isinstance(item, dict) and item.get("diff", {}).get("foehn_present_in_web") is True
        ),
        "precip_window_mismatch_count": sum(
            1 for item in comparisons or []
            if isinstance(item, dict)
            and (
                item.get("diff", {}).get("line_daily_precip_differs_from_0416") is True
                or item.get("diff", {}).get("web_precip_differs_from_line_0416") is True
            )
        ),
    }


def log_shadow_comparison(logger, line_days: list[dict], web_days: list[dict], *,
                          source: str = "line", enabled: bool | None = None) -> dict | None:
    """Log a safe aggregate LINE-vs-web comparison when explicitly enabled.

    This helper is intentionally side-effect-light: it performs no external
    requests and logs no coordinates, URLs, raw forecast payloads, Redis values,
    or LINE user identifiers.
    """
    if enabled is None:
        enabled = shadow_compare_enabled()
    if not enabled:
        return None
    comparisons = compare_line_and_web_forecasts(line_days, web_days)
    summary = shadow_comparison_summary(comparisons, source=source)
    logger.info("[line_web_shadow] %s", json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return summary
