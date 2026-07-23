"""
Unit tests for the leeward (foehn-side) correction chain in start.py:
  - start.mountain_azimuth()               spot -> summit(R_1800_2392) bearing
  - start._compute_foehn_intensity_hours()  MeteoSwiss-style (Duerr 2008)
    potential-temperature-difference foehn intensity, gated by the 06:00
    wind angle relative to the summit
  - start._apply_leeward_solar_boost()      score-input solar correction
  - start._apply_local_risk_adjustments()   foehn score bonus (uses the same
    foehn_hours value)

Run from project root:
    python -m pytest tests/test_leeward_solar_boost.py -v
"""


# ---------------------------------------------------------------------------
# mountain_azimuth
# ---------------------------------------------------------------------------

def test_mountain_azimuth_kutsugata_points_roughly_east():
    import start
    # Kutsugata (沓形, SW coast) sits almost due west of the summit, so the
    # summit should bear almost due east (~90 deg) from it.
    az = start.mountain_azimuth(45.1783, 141.1383)
    assert 80 < az < 100


def test_mountain_azimuth_at_summit_is_defined():
    import start
    # Degenerate case (distance ~0) must not raise.
    az = start.mountain_azimuth(start.SUMMIT_LAT, start.SUMMIT_LON)
    assert isinstance(az, float)


# ---------------------------------------------------------------------------
# _compute_foehn_intensity_hours
# ---------------------------------------------------------------------------

def test_foehn_intensity_zero_when_windward():
    import start
    # angle_diff <= 90 (windward side) must gate to zero regardless of signal
    assert start._compute_foehn_intensity_hours(90, 5.0, 20.0, 10.0, -5.0, 13) == 0.0
    assert start._compute_foehn_intensity_hours(45, 5.0, 20.0, 10.0, -5.0, 13) == 0.0


def test_foehn_intensity_zero_when_missing_inputs():
    import start
    assert start._compute_foehn_intensity_hours(None, 5.0, 20.0, 10.0, -5.0, 13) == 0.0
    assert start._compute_foehn_intensity_hours(120, None, 20.0, 10.0, -5.0, 13) == 0.0
    assert start._compute_foehn_intensity_hours(120, 5.0, None, 10.0, -5.0, 13) == 0.0
    assert start._compute_foehn_intensity_hours(120, 5.0, 20.0, 10.0, None, 13) == 0.0


def test_foehn_intensity_zero_when_signal_at_or_below_low_threshold():
    import start
    # theta_spot far below theta_summit -> no foehn signal -> zero, even
    # though the angle gate (leeward) and wind speed are satisfied.
    result = start._compute_foehn_intensity_hours(
        angle_diff_0600=150, wind_speed_ms_0600=5.0,
        spot_temp_0600=-20.0, spot_elevation=10.0,
        summit_temp_0600=20.0, total_hours=13,
    )
    assert result == 0.0


def test_foehn_intensity_full_when_signal_at_or_above_high_threshold_and_strong_wind():
    import start
    # Construct spot/summit temps whose theta difference clearly exceeds
    # _FOEHN_SIGNAL_HIGH, with wind >= 3 m/s (full wind factor).
    result = start._compute_foehn_intensity_hours(
        angle_diff_0600=150, wind_speed_ms_0600=5.0,
        spot_temp_0600=25.0, spot_elevation=10.0,
        summit_temp_0600=-10.0, total_hours=13,
    )
    assert result == 13.0  # ratio clamped to 1.0 * wind_factor 1.0 * total_hours


def test_foehn_intensity_wind_factor_scales_below_3ms_no_hard_cutoff():
    import start
    kwargs = dict(
        angle_diff_0600=150, spot_temp_0600=25.0, spot_elevation=10.0,
        summit_temp_0600=-10.0, total_hours=13,
    )
    full_wind = start._compute_foehn_intensity_hours(wind_speed_ms_0600=3.0, **kwargs)
    half_wind = start._compute_foehn_intensity_hours(wind_speed_ms_0600=1.5, **kwargs)
    assert full_wind == 13.0
    assert abs(half_wind - 6.5) < 1e-6


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
    boosted = start._apply_leeward_solar_boost(300.0, 6.5, 13)
    assert abs(boosted - 300.0 * (1.0 + 0.50 * (6.5 / 13))) < 1e-6


# ---------------------------------------------------------------------------
# _apply_local_risk_adjustments — foehn bonus cap (15pt / 3pt-per-hour,
# unified with the stage_analysis path in get_forecast())
# ---------------------------------------------------------------------------

def test_local_risk_adjustments_foehn_bonus_formula():
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
