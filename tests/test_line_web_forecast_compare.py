from line_web_forecast_compare import compare_line_and_web_forecast


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
