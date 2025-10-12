#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
風向-山角度差と700hPa鉛直p速度の相関検証

理論的予測:
- 山向き風（角度差小）→ 上昇気流 → omega < 0
- 山背風（角度差大）→ 下降気流 → omega > 0
- cos(角度差) と omega の負の相関を期待
"""

import json
import math
import requests
import numpy as np
from datetime import datetime

# 利尻山の座標
RISHIRI_SAN_LAT = 45.1821
RISHIRI_SAN_LON = 141.2421

def calculate_mountain_azimuth(lat, lon):
    """山頂方位角を計算"""
    delta_lat = RISHIRI_SAN_LAT - lat
    delta_lon = RISHIRI_SAN_LON - lon
    math_angle = math.degrees(math.atan2(delta_lat, delta_lon))
    mountain_azimuth = 90 - math_angle
    if mountain_azimuth < 0:
        mountain_azimuth += 360
    elif mountain_azimuth >= 360:
        mountain_azimuth -= 360
    return mountain_azimuth

def load_spots():
    """干場データを読み込み"""
    try:
        with open('spots.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading spots: {e}")
        return []

def fetch_forecast_data(lat, lon):
    """予報データを取得"""
    url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&hourly=temperature_2m,wind_speed_10m,wind_direction_10m,temperature_700hPa&timezone=Asia/Tokyo&forecast_days=3"
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Error fetching data: {e}")
        return None

def calculate_vertical_p_velocity(hourly_data, hour_index):
    """700hPa鉛直p速度を簡易計算"""
    try:
        if hour_index < 1 or hour_index >= len(hourly_data.get('temperature_700hPa', [])) - 1:
            return None

        temp_prev = hourly_data['temperature_700hPa'][hour_index - 1]
        temp_next = hourly_data['temperature_700hPa'][hour_index + 1]

        if temp_prev is None or temp_next is None:
            return None

        # 簡易的な鉛直p速度推定（温度変化率から）
        dt = 2 * 3600  # 2時間（秒）
        dT = temp_next - temp_prev

        # 断熱減率を仮定した鉛直p速度推定
        # omega ≈ -dT/dt * (適当な係数)
        omega = -dT / dt * 100  # Pa/s単位に調整

        return omega
    except Exception as e:
        return None

def analyze_correlation():
    """相関分析を実行"""
    spots = load_spots()
    if not spots:
        print("No spots data found")
        return

    print(f"Analyzing {len(spots)} spots...\n")

    all_cos_values = []
    all_omega_values = []
    spot_results = []

    total_spots = len(spots)
    for i, spot in enumerate(spots):  # 全干場を解析
        name = spot.get('name', 'Unknown')
        lat = spot['lat']
        lon = spot['lon']

        print(f"[{i+1}/{total_spots}] {name} ({lat:.4f}, {lon:.4f})")

        mountain_azimuth = calculate_mountain_azimuth(lat, lon)
        print(f"  Mountain azimuth: {mountain_azimuth:.1f}°")

        forecast_data = fetch_forecast_data(lat, lon)
        if not forecast_data or 'hourly' not in forecast_data:
            print(f"  Failed to fetch data\n")
            continue

        hourly = forecast_data['hourly']
        spot_cos = []
        spot_omega = []

        # 4時〜16時のデータを解析
        for h in range(4, 17):
            if h >= len(hourly.get('wind_direction_10m', [])):
                continue

            wind_dir = hourly['wind_direction_10m'][h]
            if wind_dir is None:
                continue

            # 風が向かう方向
            wind_toward = (wind_dir + 180) % 360

            # 角度差
            angle_diff = abs(wind_toward - mountain_azimuth)
            if angle_diff > 180:
                angle_diff = 360 - angle_diff

            # コサイン値
            cos_value = math.cos(math.radians(angle_diff))

            # 鉛直p速度
            omega = calculate_vertical_p_velocity(hourly, h)

            if omega is not None:
                spot_cos.append(cos_value)
                spot_omega.append(omega)
                all_cos_values.append(cos_value)
                all_omega_values.append(omega)

        if spot_cos:
            spot_corr = np.corrcoef(spot_cos, spot_omega)[0, 1]
            print(f"  Data points: {len(spot_cos)}")
            print(f"  Correlation: {spot_corr:.3f}")
            spot_results.append({
                'name': name,
                'correlation': spot_corr,
                'n': len(spot_cos)
            })

        print()

    # 全体の相関係数
    if all_cos_values and all_omega_values:
        print("="*60)
        print("OVERALL RESULTS")
        print("="*60)
        print(f"Total data points: {len(all_cos_values)}")

        overall_corr = np.corrcoef(all_cos_values, all_omega_values)[0, 1]
        print(f"Overall correlation: {overall_corr:.4f}")

        # 統計情報
        print(f"\ncos(angle_diff) statistics:")
        print(f"  Mean: {np.mean(all_cos_values):.3f}")
        print(f"  Std: {np.std(all_cos_values):.3f}")
        print(f"  Range: [{np.min(all_cos_values):.3f}, {np.max(all_cos_values):.3f}]")

        print(f"\nOmega (Pa/s) statistics:")
        print(f"  Mean: {np.mean(all_omega_values):.6f}")
        print(f"  Std: {np.std(all_omega_values):.6f}")
        print(f"  Range: [{np.min(all_omega_values):.6f}, {np.max(all_omega_values):.6f}]")

        # 結果を保存（先に保存）
        output = {
            'timestamp': datetime.now().isoformat(),
            'overall_correlation': overall_corr,
            'total_points': len(all_cos_values),
            'cos_stats': {
                'mean': float(np.mean(all_cos_values)),
                'std': float(np.std(all_cos_values)),
                'min': float(np.min(all_cos_values)),
                'max': float(np.max(all_cos_values))
            },
            'omega_stats': {
                'mean': float(np.mean(all_omega_values)),
                'std': float(np.std(all_omega_values)),
                'min': float(np.min(all_omega_values)),
                'max': float(np.max(all_omega_values))
            },
            'spot_results': spot_results
        }

        with open('wind_angle_omega_correlation.json', 'w', encoding='utf-8') as f:
            json.dump(output, f, ensure_ascii=False, indent=2)

        print(f"\nResults saved to: wind_angle_omega_correlation.json")

        # 個別干場の結果（上位/下位10件ずつ）
        print(f"\nTop 10 negative correlations (theory-supporting):")
        sorted_results = sorted(spot_results, key=lambda x: x['correlation'])
        for result in sorted_results[:10]:
            print(f"  {result['name']}: {result['correlation']:+.3f} (n={result['n']})")

        print(f"\nTop 10 positive correlations (theory-contradicting):")
        for result in sorted_results[-10:]:
            print(f"  {result['name']}: {result['correlation']:+.3f} (n={result['n']})")

        # 結果の解釈
        print(f"\n{'='*60}")
        print("INTERPRETATION")
        print("="*60)
        if overall_corr < -0.2:
            print("NEGATIVE correlation detected!")
            print("  Mountain-ward wind -> upward motion (omega < 0)")
            print("  Mountain-lee wind -> downward motion (omega > 0)")
            print("  Theory is SUPPORTED by data.")
        elif overall_corr > 0.2:
            print("POSITIVE correlation detected (unexpected)")
            print("  Theory is NOT supported by data.")
        else:
            print("Weak correlation (-0.2 < r < 0.2)")
            print("  Signal may be weak or masked by other factors.")
            print("  Possible reasons:")
            print("  - Synoptic-scale effects dominate")
            print("  - Mountain effect varies by location")
            print("  - Time averaging smooths out signal")

if __name__ == '__main__':
    analyze_correlation()
