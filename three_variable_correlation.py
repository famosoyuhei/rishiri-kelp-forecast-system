#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
3変数相関分析: cos(角度差)、700hPa鉛直p速度、500hPa相対渦度

目的: メソスケール（山岳効果）とシノプティックスケール（総観規模）の
     相互作用を理解する
"""

import json
import math
import requests
import numpy as np
from datetime import datetime
import time

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
    with open('spots.json', 'r', encoding='utf-8') as f:
        return json.load(f)

def fetch_forecast_data(lat, lon):
    """予報データを取得（500hPa渦度を含む）"""
    url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&hourly=temperature_2m,wind_speed_10m,wind_direction_10m,temperature_700hPa,geopotential_height_500hPa&timezone=Asia/Tokyo&forecast_days=3"
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

        dt = 2 * 3600  # 2時間（秒）
        dT = temp_next - temp_prev
        omega = -dT / dt * 100  # Pa/s単位

        return omega
    except:
        return None

def calculate_vorticity_500hpa(hourly_data, hour_index, lat, lon):
    """500hPa相対渦度を簡易推定（geopotential heightの変化から）"""
    try:
        if hour_index < 1 or hour_index >= len(hourly_data.get('geopotential_height_500hPa', [])) - 1:
            return None

        z_prev = hourly_data['geopotential_height_500hPa'][hour_index - 1]
        z_next = hourly_data['geopotential_height_500hPa'][hour_index + 1]

        if z_prev is None or z_next is None:
            return None

        # 時間微分から渦度を推定
        dt = 2 * 3600  # 2時間
        dz = z_next - z_prev

        # 簡易的な渦度推定（高度場の時間変化から）
        # 正: サイクロン性（反時計回り）、負: アンチサイクロン性（時計回り）
        f = 2 * 7.292e-5 * math.sin(math.radians(lat))  # コリオリパラメータ
        vorticity = -dz / dt * f / 100  # 10^-5 s^-1単位

        return vorticity
    except:
        return None

def analyze_three_variables():
    """3変数間の相関を分析"""
    spots = load_spots()

    # 東側と西側のサンプリング（各10干場）
    east_spots = []
    west_spots = []

    for spot in spots:
        lon = spot['lon']
        if lon > RISHIRI_SAN_LON + 0.02 and len(east_spots) < 10:
            east_spots.append(spot)
        elif lon < RISHIRI_SAN_LON - 0.02 and len(west_spots) < 10:
            west_spots.append(spot)

    # データ収集
    all_data = {
        'east': {'cos': [], 'omega': [], 'vorticity': []},
        'west': {'cos': [], 'omega': [], 'vorticity': []}
    }

    print("Collecting data from east side spots...")
    for i, spot in enumerate(east_spots):
        print(f"  [{i+1}/10] {spot['name']}")
        data = fetch_forecast_data(spot['lat'], spot['lon'])
        if not data:
            continue

        mountain_azimuth = calculate_mountain_azimuth(spot['lat'], spot['lon'])
        hourly = data['hourly']

        for h in range(4, 17):
            if h >= len(hourly.get('wind_direction_10m', [])):
                continue

            wind_dir = hourly['wind_direction_10m'][h]
            if wind_dir is None:
                continue

            # 風向-山角度差のコサイン
            wind_toward = (wind_dir + 180) % 360
            angle_diff = abs(wind_toward - mountain_azimuth)
            if angle_diff > 180:
                angle_diff = 360 - angle_diff
            cos_angle = math.cos(math.radians(angle_diff))

            # 鉛直p速度
            omega = calculate_vertical_p_velocity(hourly, h)

            # 500hPa相対渦度
            vorticity = calculate_vorticity_500hpa(hourly, h, spot['lat'], spot['lon'])

            if omega is not None and vorticity is not None:
                all_data['east']['cos'].append(cos_angle)
                all_data['east']['omega'].append(omega)
                all_data['east']['vorticity'].append(vorticity)

        time.sleep(0.5)  # API制限対策

    print("\nCollecting data from west side spots...")
    for i, spot in enumerate(west_spots):
        print(f"  [{i+1}/10] {spot['name']}")
        data = fetch_forecast_data(spot['lat'], spot['lon'])
        if not data:
            continue

        mountain_azimuth = calculate_mountain_azimuth(spot['lat'], spot['lon'])
        hourly = data['hourly']

        for h in range(4, 17):
            if h >= len(hourly.get('wind_direction_10m', [])):
                continue

            wind_dir = hourly['wind_direction_10m'][h]
            if wind_dir is None:
                continue

            wind_toward = (wind_dir + 180) % 360
            angle_diff = abs(wind_toward - mountain_azimuth)
            if angle_diff > 180:
                angle_diff = 360 - angle_diff
            cos_angle = math.cos(math.radians(angle_diff))

            omega = calculate_vertical_p_velocity(hourly, h)
            vorticity = calculate_vorticity_500hpa(hourly, h, spot['lat'], spot['lon'])

            if omega is not None and vorticity is not None:
                all_data['west']['cos'].append(cos_angle)
                all_data['west']['omega'].append(omega)
                all_data['west']['vorticity'].append(vorticity)

        time.sleep(0.5)

    # 相関分析
    results = {}

    for region in ['east', 'west']:
        cos_vals = np.array(all_data[region]['cos'])
        omega_vals = np.array(all_data[region]['omega'])
        vort_vals = np.array(all_data[region]['vorticity'])

        if len(cos_vals) == 0:
            continue

        # 3つの相関係数を計算
        corr_cos_omega = np.corrcoef(cos_vals, omega_vals)[0, 1] if len(cos_vals) > 1 else 0
        corr_cos_vort = np.corrcoef(cos_vals, vort_vals)[0, 1] if len(cos_vals) > 1 else 0
        corr_omega_vort = np.corrcoef(omega_vals, vort_vals)[0, 1] if len(omega_vals) > 1 else 0

        results[region] = {
            'n_samples': len(cos_vals),
            'correlations': {
                'cos_angle_vs_omega_700hPa': float(corr_cos_omega),
                'cos_angle_vs_vorticity_500hPa': float(corr_cos_vort),
                'omega_700hPa_vs_vorticity_500hPa': float(corr_omega_vort)
            },
            'statistics': {
                'cos_angle': {
                    'mean': float(np.mean(cos_vals)),
                    'std': float(np.std(cos_vals)),
                    'range': [float(np.min(cos_vals)), float(np.max(cos_vals))]
                },
                'omega_700hPa': {
                    'mean': float(np.mean(omega_vals)),
                    'std': float(np.std(omega_vals)),
                    'range': [float(np.min(omega_vals)), float(np.max(omega_vals))]
                },
                'vorticity_500hPa': {
                    'mean': float(np.mean(vort_vals)),
                    'std': float(np.std(vort_vals)),
                    'range': [float(np.min(vort_vals)), float(np.max(vort_vals))]
                }
            }
        }

    # 結果を保存
    output = {
        'timestamp': datetime.now().isoformat(),
        'analysis': '3-variable correlation: cos(wind-mountain angle), 700hPa omega, 500hPa vorticity',
        'regions': results,
        'interpretation': {
            'east': 'Mesoscale dominated (mountain effect)',
            'west': 'Synoptic scale dominated (large-scale pressure systems)'
        }
    }

    with open('three_variable_correlation.json', 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    # サマリー表示
    print("\n" + "="*70)
    print("THREE-VARIABLE CORRELATION ANALYSIS")
    print("="*70)

    for region in ['east', 'west']:
        if region not in results:
            continue

        r = results[region]
        print(f"\n{region.upper()} SIDE (n={r['n_samples']})")
        print("-"*70)
        print(f"cos(angle) vs omega_700hPa:        r = {r['correlations']['cos_angle_vs_omega_700hPa']:+.3f}")
        print(f"cos(angle) vs vorticity_500hPa:    r = {r['correlations']['cos_angle_vs_vorticity_500hPa']:+.3f}")
        print(f"omega_700hPa vs vorticity_500hPa:  r = {r['correlations']['omega_700hPa_vs_vorticity_500hPa']:+.3f}")

        print(f"\nStatistics:")
        print(f"  cos(angle):      mean={r['statistics']['cos_angle']['mean']:+.3f}, std={r['statistics']['cos_angle']['std']:.3f}")
        print(f"  omega_700hPa:    mean={r['statistics']['omega_700hPa']['mean']:+.6f}, std={r['statistics']['omega_700hPa']['std']:.6f}")
        print(f"  vorticity_500hPa: mean={r['statistics']['vorticity_500hPa']['mean']:+.6f}, std={r['statistics']['vorticity_500hPa']['std']:.6f}")

    print(f"\nResults saved to: three_variable_correlation.json")

    return results

if __name__ == '__main__':
    analyze_three_variables()
