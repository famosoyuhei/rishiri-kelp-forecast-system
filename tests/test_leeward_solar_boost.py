"""
Unit tests for the leeward (foehn-side) correction chain in start.py:
  - start._leeward_intensity()      the shared per-hour windward/leeward formula
  - start._compute_foehn_hours()    sums per-hour intensity into "effective hours"
  - start._apply_leeward_solar_boost() score-input solar correction
  - start._apply_local_risk_adjustments() foehn score bonus (uses the same
    foehn_hours value)

Run from project root:
    python -m pytest tests/test_leeward_solar_boost.py -v
"""


# ---------------------------------------------------------------------------
# _leeward_intensity
# ---------------------------------------------------------------------------

def test_leeward_intensity_zero_when_windward():
    import start
    assert start._leeward_intensity(45, 5.0) == 0.0
    assert start._leeward_intensity(90, 5.0) == 0.0


def test_leeward_intensity_zero_when_missing_inputs():
    import start
    assert start._leeward_intensity(None, 5.0) == 0.0
    assert start._leeward_intensity(120, None) == 0.0


def test_leeward_intensity_ramps_linearly_with_angle():
    import start
    # 90 -> 0.0, 135 -> 0.5, 180 -> 1.0 (at full wind speed)
    assert start._leeward_intensity(90, 5.0) == 0.0
    assert abs(start._leeward_intensity(135, 5.0) - 0.5) < 1e-9
    assert start._leeward_intensity(180, 5.0) == 1.0


def test_leeward_intensity_scales_with_wind_speed_no_hard_cutoff():
    import start
    # below 3 m/s: proportional decay, not zeroed out
    full = start._leeward_intensity(180, 3.0)
    half_wind = start._leeward_intensity(180, 1.5)
    assert full == 1.0
    assert abs(half_wind - 0.5) < 1e-9
    assert start._leeward_intensity(180, 0.0) == 0.0


def test_leeward_intensity_wind_factor_caps_at_one():
    import start
    assert start._leeward_intensity(180, 10.0) == 1.0


# ---------------------------------------------------------------------------
# _compute_foehn_hours — noise-tolerant regression case
# ---------------------------------------------------------------------------

def test_compute_foehn_hours_detects_noisy_but_leeward_day():
    """
    Regression test for the 2026-07-21 backtest finding: a day whose
    circular-mean wind direction is clearly leeward (angle_diff ~150°) but
    whose individual hours never simultaneously crossed the old strict
    "angle_diff>150 AND wind>3m/s" gate must still register nonzero
    effective foehn hours under the continuous formula.
    """
    import start
    # Hourly wind directions/speeds modeled on H_1064_2209 on 2026-06-15
    # (mountain_az ~ 194 for this spot), which the old boolean gate scored
    # as foehn_hours=0 despite a day-mean angle_diff of 150.5.
    wind_dir_raw = [344, 2, 31, 41, 29, 90, 228, 243, 265, 277, 324, 356, 9]
    wind_spd_kmh_raw = [6.6, 5.6, 4.6, 5.0, 5.2, 1.4, 2.7, 4.8, 4.5, 2.9, 4.0, 5.4, 6.7]
    mountain_az = 194.0

    result = start._compute_foehn_hours(wind_dir_raw, wind_spd_kmh_raw, mountain_az)
    assert result > 0.0, "continuous formula should detect leeward exposure the old AND-gate missed"


def test_compute_foehn_hours_zero_for_all_windward_day():
    import start
    wind_dir_raw = [10] * 13   # constant wind, always windward relative to mountain_az
    wind_spd_kmh_raw = [10.0] * 13
    mountain_az = 190.0  # wind_toward = 190 (10+180), angle_diff = 0 -> windward
    result = start._compute_foehn_hours(wind_dir_raw, wind_spd_kmh_raw, mountain_az)
    assert result == 0.0


# ---------------------------------------------------------------------------
# _apply_leeward_solar_boost (0.50 multiplier / 900 ceiling)
# ---------------------------------------------------------------------------

def test_no_boost_when_no_foehn_hours():
    import start
    assert start._apply_leeward_solar_boost(300.0, 0, 13) == 300.0


def test_no_boost_when_avg_solar_is_none():
    import start
    assert start._apply_leeward_solar_boost(None, 5, 13) is None


def test_no_boost_when_total_hours_is_zero():
    import start
    assert start._apply_leeward_solar_boost(300.0, 5, 0) == 300.0


def test_full_day_foehn_applies_max_50_percent_boost():
    import start
    boosted = start._apply_leeward_solar_boost(300.0, 13, 13)
    assert boosted == 300.0 * 1.50


def test_partial_foehn_scales_proportionally():
    import start
    # foehn covers half the working hours -> +25%
    boosted = start._apply_leeward_solar_boost(300.0, 6, 12)
    assert abs(boosted - 300.0 * 1.25) < 1e-6


def test_boost_is_capped_at_ceiling():
    import start
    boosted = start._apply_leeward_solar_boost(800.0, 13, 13)
    assert boosted == 900.0


def test_foehn_hours_exceeding_total_hours_still_capped_at_max_boost():
    import start
    # defensive: fraction should clamp to 1.0, never boost beyond +50%
    boosted = start._apply_leeward_solar_boost(300.0, 20, 13)
    assert boosted == 300.0 * 1.50


def test_boost_accepts_fractional_foehn_hours():
    import start
    # foehn_hours is now a float (sum of per-hour intensities)
    boosted = start._apply_leeward_solar_boost(300.0, 6.5, 13)
    assert abs(boosted - 300.0 * (1.0 + 0.50 * (6.5 / 13))) < 1e-6


# ---------------------------------------------------------------------------
# _apply_local_risk_adjustments — foehn bonus cap (8/2pt -> 15/3pt, unified
# with the stage_analysis path in get_forecast())
# ---------------------------------------------------------------------------

def test_local_risk_adjustments_foehn_bonus_matches_stage_analysis_formula():
    import start
    cape_risk = {'risk': 'none', 'score_penalty': 0, 'warning': None}
    score, adj = start._apply_local_risk_adjustments(
        50,
        cape_risk=cape_risk,
        fog_summary='low',
        foehn_hours=4.0,
        sst_fog_risk='low',
    )
    assert adj['foehn_adjustment'] == 12  # min(15, 4.0*3)
    assert score == 62


def test_local_risk_adjustments_foehn_bonus_caps_at_15():
    import start
    cape_risk = {'risk': 'none', 'score_penalty': 0, 'warning': None}
    score, adj = start._apply_local_risk_adjustments(
        50,
        cape_risk=cape_risk,
        fog_summary='low',
        foehn_hours=13.0,
        sst_fog_risk='low',
    )
    assert adj['foehn_adjustment'] == 15
