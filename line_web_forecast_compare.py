"""Pure helpers for comparing LINE simplified forecasts with web forecasts.

This module is the first step toward moving LINE notifications to the same
foehn-aware drying judgment used by the web forecast.  It intentionally does
not fetch weather data, read Redis, send LINE messages, or change production
notification behavior.
"""
from __future__ import annotations

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
