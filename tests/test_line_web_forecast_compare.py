from line_web_forecast_compare import compare_line_and_web_forecast
from line_web_forecast_compare import compare_line_and_web_forecasts
from line_web_forecast_compare import log_shadow_comparison
from line_web_forecast_compare import shadow_compare_enabled
from line_web_forecast_compare import shadow_comparison_summary
from line_web_forecast_compare import web_day_from_forecast_history


def test_compare_line_and_web_forecast_flags_foehn_score_gap():
    line_day = {
        "date": "2026-07-26",
        "day_number": 0,
        "score": 72,
        "suitability": "good",
        "precipitation": 0.0,
        "precipitation_0416": 0.0,
        "min_humidity": 88.0,
        "avg_wind": 2.5,
        "pop": 10,
        "wind_direction_period": "WSW->NNW",
    }
    web_day = {
        "date": "2026-07-26",
        "day_number": 0,
        "daily_summary": {
            "drying_score": 86,
            "suitability": "excellent",
            "precipitation": 0.0,
            "humidity": 72.0,
            "wind_speed": 4.0,
            "wind_direction": 292.0,
            "precipitation_probability": 5,
            "foehn_bonus": 12,
            "local_risk_adjustments": {"foehn_adjustment": 12},
        },
    }

    result = compare_line_and_web_forecast(line_day, web_day)

    assert result["date"] == "2026-07-26"
    assert result["line"]["score"] == 72
    assert result["web"]["score"] == 86
    assert result["diff"]["score_delta_web_minus_line"] == 14
    assert result["diff"]["suitability_changed"] is True
    assert result["diff"]["foehn_present_in_web"] is True


def test_compare_line_and_web_forecast_flags_daily_vs_working_precip_gap():
    line_day = {
        "date": "2026-07-26",
        "day_number": 0,
        "score": 10,
        "suitability": "poor",
        "precipitation": 6.0,
        "precipitation_0416": 0.0,
        "min_humidity": 82.0,
        "avg_wind": 3.2,
        "pop": 40,
    }
    web_summary = {
        "drying_score": 74,
        "suitability": "good",
        "precipitation": 0.0,
        "humidity": 82.0,
        "wind_speed": 3.2,
        "foehn_bonus": 0,
        "local_risk_adjustments": {"foehn_adjustment": 0},
    }

    result = compare_line_and_web_forecast(line_day, web_summary)

    assert result["diff"]["line_daily_precip_differs_from_0416"] is True
    assert result["diff"]["web_precip_differs_from_line_0416"] is False
    assert result["diff"]["score_abs_delta"] == 64
    assert result["diff"]["foehn_present_in_web"] is False


def test_web_day_from_forecast_history_accepts_only_web_forecast_records():
    record = {
        "logic_source": "web_forecast",
        "target_date": "2026-07-26",
        "day_number": 0,
        "max_temp": 23.5,
        "min_humidity": 72,
        "avg_wind": 4.2,
        "precipitation": 3.0,
        "precipitation_0416": 0.0,
        "drying_score": 88,
        "suitability": "excellent",
        "foehn_bonus": 12,
        "foehn_adjustment": 12,
    }

    web_day = web_day_from_forecast_history(record)

    assert web_day["date"] == "2026-07-26"
    assert web_day["daily_summary"]["precipitation"] == 0.0
    assert web_day["daily_summary"]["drying_score"] == 88
    assert web_day["daily_summary"]["local_risk_adjustments"]["foehn_adjustment"] == 12


def test_web_day_from_forecast_history_rejects_line_and_legacy_records():
    assert web_day_from_forecast_history({"logic_source": "line_simplified"}) is None
    assert web_day_from_forecast_history({"drying_score": 88}) is None


def test_compare_line_and_web_forecasts_matches_by_date_and_ignores_unmatched():
    line_days = [
        {"date": "2026-07-26", "score": 70, "suitability": "good"},
        {"date": "2026-07-27", "score": 80, "suitability": "excellent"},
    ]
    web_days = [
        {"date": "2026-07-26", "daily_summary": {"drying_score": 72, "suitability": "good"}},
    ]

    results = compare_line_and_web_forecasts(line_days, web_days)

    assert len(results) == 1
    assert results[0]["date"] == "2026-07-26"
    assert results[0]["diff"]["score_delta_web_minus_line"] == 2


def test_shadow_compare_flag_defaults_off():
    assert shadow_compare_enabled({}) is False
    assert shadow_compare_enabled({"LINE_WEB_FORECAST_SHADOW_COMPARE_ENABLED": "false"}) is False
    assert shadow_compare_enabled({"LINE_WEB_FORECAST_SHADOW_COMPARE_ENABLED": "true"}) is True


def test_shadow_comparison_summary_contains_only_safe_aggregates():
    comparisons = [
        {
            "diff": {
                "score_abs_delta": 14,
                "suitability_changed": True,
                "foehn_present_in_web": True,
                "line_daily_precip_differs_from_0416": False,
                "web_precip_differs_from_line_0416": False,
            }
        },
        {
            "diff": {
                "score_abs_delta": 3,
                "suitability_changed": False,
                "foehn_present_in_web": False,
                "line_daily_precip_differs_from_0416": True,
                "web_precip_differs_from_line_0416": False,
            }
        },
    ]

    summary = shadow_comparison_summary(comparisons, source="line")

    assert summary == {
        "source": "line",
        "event": "line_web_shadow_compare",
        "matched_days": 2,
        "max_score_abs_delta": 14,
        "suitability_changed_count": 1,
        "foehn_present_count": 1,
        "precip_window_mismatch_count": 1,
    }


class _Logger:
    def __init__(self):
        self.messages = []

    def info(self, template, message):
        self.messages.append((template, message))


def test_log_shadow_comparison_is_noop_when_disabled():
    logger = _Logger()

    result = log_shadow_comparison(logger, [], [], enabled=False)

    assert result is None
    assert logger.messages == []


def test_log_shadow_comparison_logs_safe_json_when_enabled():
    logger = _Logger()
    line_days = [{"date": "2026-07-26", "score": 70, "suitability": "good"}]
    web_days = [{"date": "2026-07-26", "daily_summary": {"drying_score": 85, "suitability": "excellent"}}]

    result = log_shadow_comparison(logger, line_days, web_days, enabled=True)

    assert result["matched_days"] == 1
    assert result["max_score_abs_delta"] == 15
    assert logger.messages
    assert "line_web_shadow_compare" in logger.messages[0][1]
    assert "2026-07-26" not in logger.messages[0][1]
    assert "coordinates" not in logger.messages[0][1]
