#!/usr/bin/env python3
"""Test theta-e correction API endpoint"""
import requests
import json

# ローカルサーバーでテスト（または本番URLに変更）
# BASE_URL = "http://localhost:5000"
BASE_URL = "https://rishiri-kelp-forecast-system.onrender.com"

def test_emagram_without_correction():
    """補正なしでエマグラムを取得"""
    print("=" * 80)
    print("Test 1: Emagram without correction")
    print("=" * 80)

    url = f"{BASE_URL}/api/emagram"
    params = {
        'lat': 45.242,  # 鴛泊
        'lon': 141.242,
        'time': 0
    }

    response = requests.get(url, params=params, timeout=30)
    data = response.json()

    print(f"Status: {data['status']}")
    print(f"Correction applied: {data.get('correction_applied', False)}")
    print(f"Pressure levels: {len(data['data']['pressure'])}")
    print(f"Temperature (1000hPa): {data['data']['temperature'][0]:.2f}°C")
    print()

    return data

def test_emagram_with_correction():
    """補正ありでエマグラムを取得"""
    print("=" * 80)
    print("Test 2: Emagram WITH theta-e correction")
    print("=" * 80)

    url = f"{BASE_URL}/api/emagram"
    params = {
        'lat': 45.242,  # 鴛泊（風下）
        'lon': 141.242,
        'time': 0,
        'apply_theta_e_correction': 'true',
        'wind_direction': 270  # 西風
    }

    response = requests.get(url, params=params, timeout=30)
    data = response.json()

    print(f"Status: {data['status']}")
    print(f"Correction applied: {data.get('correction_applied', False)}")

    if 'correction_info' in data:
        info = data['correction_info']
        if 'error' in info:
            print(f"Correction error: {info['error']}")
        else:
            print(f"Windward spot: {info['windward_spot']['name']}")
            print(f"  Lat/Lon: {info['windward_spot']['lat']:.3f}, {info['windward_spot']['lon']:.3f}")
            print(f"Wind direction: {info['wind_direction']}°")
            print(f"Method: {info['method']}")

    print(f"\nPressure levels: {len(data['data']['pressure'])}")
    print(f"Temperature (1000hPa): {data['data']['temperature'][0]:.2f}°C")
    print(f"Dewpoint (1000hPa): {data['data']['dewpoint'][0]:.2f}°C")
    print()

    return data

def compare_results(data_no_corr, data_with_corr):
    """補正前後の比較"""
    print("=" * 80)
    print("Comparison: Before vs After Correction")
    print("=" * 80)
    print()

    print(f"{'Pressure':>8} | {'Before T':>9} {'After T':>9} {'Diff':>7} | {'Before Td':>9} {'After Td':>9} {'Diff':>7}")
    print("-" * 80)

    for i in range(min(len(data_no_corr['data']['pressure']), 8)):  # 最初の8層
        p = data_no_corr['data']['pressure'][i]
        t_before = data_no_corr['data']['temperature'][i]
        t_after = data_with_corr['data']['temperature'][i]
        td_before = data_no_corr['data']['dewpoint'][i]
        td_after = data_with_corr['data']['dewpoint'][i]

        t_diff = t_after - t_before
        td_diff = td_after - td_before

        print(f"{p:>8.0f} | {t_before:>9.2f} {t_after:>9.2f} {t_diff:>+7.2f} | "
              f"{td_before:>9.2f} {td_after:>9.2f} {td_diff:>+7.2f}")

    print()
    print("Expected effects:")
    print("  - Lower atmosphere (≥850hPa): T increases, Td decreases (foehn effect)")
    print("  - Upper atmosphere (<500hPa): Similar values (reference point)")
    print()

if __name__ == '__main__':
    try:
        # Test 1: Without correction
        data_no_corr = test_emagram_without_correction()

        # Test 2: With correction
        data_with_corr = test_emagram_with_correction()

        # Comparison
        if data_no_corr['status'] == 'success' and data_with_corr['status'] == 'success':
            compare_results(data_no_corr, data_with_corr)

        print("✓ All tests completed successfully")

    except Exception as e:
        print(f"✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
