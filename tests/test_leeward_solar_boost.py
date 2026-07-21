"""
Unit tests for start._apply_leeward_solar_boost() — the leeward (foehn-side)
solar radiation correction used to score-adjust for mountain-shadow clearing
that Open-Meteo's 5km mesh cannot resolve.

Run from project root:
    python -m pytest tests/test_leeward_solar_boost.py -v
"""


def test_no_boost_when_no_foehn_hours():
    import start
    assert start._apply_leeward_solar_boost(300.0, 0, 13) == 300.0


def test_no_boost_when_avg_solar_is_none():
    import start
    assert start._apply_leeward_solar_boost(None, 5, 13) is None


def test_no_boost_when_total_hours_is_zero():
    import start
    assert start._apply_leeward_solar_boost(300.0, 5, 0) == 300.0


def test_full_day_foehn_applies_max_30_percent_boost():
    import start
    boosted = start._apply_leeward_solar_boost(300.0, 13, 13)
    assert boosted == 300.0 * 1.30


def test_partial_foehn_scales_proportionally():
    import start
    # foehn covers half the working hours -> +15%
    boosted = start._apply_leeward_solar_boost(300.0, 6, 12)
    assert abs(boosted - 300.0 * 1.15) < 1e-6


def test_boost_is_capped_at_ceiling():
    import start
    boosted = start._apply_leeward_solar_boost(800.0, 13, 13)
    assert boosted == 900.0


def test_foehn_hours_exceeding_total_hours_still_capped_at_max_boost():
    import start
    # defensive: fraction should clamp to 1.0, never boost beyond +30%
    boosted = start._apply_leeward_solar_boost(300.0, 20, 13)
    assert boosted == 300.0 * 1.30
