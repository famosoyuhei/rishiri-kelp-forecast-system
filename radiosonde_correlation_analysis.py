#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
稚内ラジオゾンデ実測データを用いた相関分析

目的: 予報データではなく実測データで500hPa渦度・700hPa鉛直p速度と
     風向-山角度差の相関を検証
"""

import json
import math
import numpy as np
from datetime import datetime

RISHIRI_SAN_LAT = 45.1821
RISHIRI_SAN_LON = 141.2421

# 沓形の座標（西側代表点）
KUTSUGATA_LAT = 45.2422
KUTSUGATA_LON = 141.1088

# 稚内の座標
WAKKANAI_LAT = 45.41
WAKKANAI_LON = 141.68

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

def load_radiosonde_data(filepath):
    """ラジオゾンデデータを読み込み"""
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)

def calculate_vorticity_500hpa(obs_list, index):
    """500hPa相対渦度を計算（時間微分から）"""
    if index < 1 or index >= len(obs_list) - 1:
        return None

    obs_prev = obs_list[index - 1]
    obs_next = obs_list[index + 1]

    # 500hPa高度
    h_prev = obs_prev['levels']['500hPa']
    h_next = obs_next['levels']['500hPa']

    if not h_prev or not h_next:
        return None

    hght_prev = h_prev.get('hght')
    hght_next = h_next.get('hght')

    if hght_prev is None or hght_next is None:
        return None

    # 時間差（日数→秒）
    dt = 2 * 24 * 3600  # 2日

    # 高度変化
    dh = hght_next - hght_prev

    # コリオリパラメータ
    f = 2 * 7.292e-5 * math.sin(math.radians(WAKKANAI_LAT))

    # 渦度推定（10^-5 s^-1）
    vorticity = -dh / dt * f * 1e5

    return vorticity

def calculate_omega_700hpa(obs_list, index):
    """700hPa鉛直p速度を計算（温度変化から）"""
    if index < 1 or index >= len(obs_list) - 1:
        return None

    obs_prev = obs_list[index - 1]
    obs_next = obs_list[index + 1]

    t_prev = obs_prev['levels']['700hPa']
    t_next = obs_next['levels']['700hPa']

    if not t_prev or not t_next:
        return None

    temp_prev = t_prev.get('temp')
    temp_next = t_next.get('temp')

    if temp_prev is None or temp_next is None:
        return None

    # 時間差（日数→秒）
    dt = 2 * 24 * 3600  # 2日

    # 温度変化
    dT = temp_next - temp_prev

    # 鉛直p速度（Pa/s）
    omega = -dT / dt * 100

    return omega

def analyze_radiosonde_correlation():
    """ラジオゾンデデータで相関分析"""

    print("="*70)
    print("RADIOSONDE-BASED CORRELATION ANALYSIS")
    print("="*70)

    # ラジオゾンデデータを読み込み
    try:
        rs_data = load_radiosonde_data('wakkanai_radiosonde_summer2024.json')
    except FileNotFoundError:
        print("Error: wakkanai_radiosonde_summer2024.json not found")
        print("Please run fetch_radiosonde_batch.py first")
        return

    observations = rs_data['observations']
    print(f"\nTotal observations: {len(observations)}")

    # 沓形の山頂方位角
    mountain_azimuth_kutsugata = calculate_mountain_azimuth(KUTSUGATA_LAT, KUTSUGATA_LON)
    print(f"Kutsugata mountain azimuth: {mountain_azimuth_kutsugata:.1f}deg")

    # データ収集
    all_cos = []
    all_omega = []
    all_vorticity = []
    all_dates = []

    for i in range(1, len(observations) - 1):
        obs = observations[i]

        # 500hPa風向を使用
        lv500 = obs['levels']['500hPa']
        if not lv500 or lv500.get('drct') is None:
            continue

        wind_dir_500 = lv500['drct']

        # 風向-山角度差のコサイン
        wind_toward = (wind_dir_500 + 180) % 360
        angle_diff = abs(wind_toward - mountain_azimuth_kutsugata)
        if angle_diff > 180:
            angle_diff = 360 - angle_diff
        cos_angle = math.cos(math.radians(angle_diff))

        # 700hPa鉛直p速度
        omega = calculate_omega_700hpa(observations, i)

        # 500hPa相対渦度
        vorticity = calculate_vorticity_500hpa(observations, i)

        if omega is not None and vorticity is not None:
            all_cos.append(cos_angle)
            all_omega.append(omega)
            all_vorticity.append(vorticity)
            all_dates.append(obs['date'])

    print(f"Valid samples: {len(all_cos)}")

    if len(all_cos) < 3:
        print("Insufficient data for correlation analysis")
        return

    # 配列化
    cos_vals = np.array(all_cos)
    omega_vals = np.array(all_omega)
    vort_vals = np.array(all_vorticity)

    # 相関係数を計算
    corr_cos_omega = np.corrcoef(cos_vals, omega_vals)[0, 1] if len(cos_vals) > 1 else 0
    corr_cos_vort = np.corrcoef(cos_vals, vort_vals)[0, 1] if len(cos_vals) > 1 else 0
    corr_omega_vort = np.corrcoef(omega_vals, vort_vals)[0, 1] if len(omega_vals) > 1 else 0

    # 結果表示
    print(f"\n{'='*70}")
    print("CORRELATION RESULTS (RADIOSONDE OBSERVATIONS)")
    print(f"{'='*70}")

    print(f"\nCorrelation coefficients:")
    print(f"  cos(angle) vs omega_700hPa:        r = {corr_cos_omega:+.3f}")
    print(f"  cos(angle) vs vorticity_500hPa:    r = {corr_cos_vort:+.3f}")
    print(f"  omega_700hPa vs vorticity_500hPa:  r = {corr_omega_vort:+.3f}")

    print(f"\nStatistics:")
    print(f"  cos(angle):       mean={np.mean(cos_vals):+.3f}, std={np.std(cos_vals):.3f}")
    print(f"  omega_700hPa:     mean={np.mean(omega_vals):+.6f}, std={np.std(omega_vals):.6f} Pa/s")
    print(f"  vorticity_500hPa: mean={np.mean(vort_vals):+.6f}, std={np.std(vort_vals):.6f} x10^-5 s^-1")

    # 解釈
    print(f"\n{'='*70}")
    print("INTERPRETATION")
    print(f"{'='*70}")

    if abs(corr_cos_vort) > 0.5:
        print("\n[STRONG] cos(angle) vs vorticity_500hPa correlation")
        if corr_cos_vort > 0:
            print("  -> SYNOPTIC SCALE DOMINATED")
            print("  -> Large-scale pressure systems drive wind-mountain alignment")
        else:
            print("  -> Synoptic cyclonic flow opposes mountain effect")
    elif abs(corr_cos_vort) > 0.3:
        print("\n[MODERATE] cos(angle) vs vorticity_500hPa correlation")
        print("  -> Synoptic scale influence present but not dominant")
    else:
        print("\n[WEAK] cos(angle) vs vorticity_500hPa correlation")
        print("  -> Wind-mountain relationship independent of synoptic scale")

    if abs(corr_cos_omega) > 0.5:
        print("\n[STRONG] cos(angle) vs omega_700hPa correlation")
        if corr_cos_omega > 0:
            print("  -> MESOSCALE DOMINATED")
            print("  -> Mountain-induced vertical motion controls weather")
        else:
            print("  -> Wind toward mountain = downward motion")
    elif abs(corr_cos_omega) > 0.3:
        print("\n[MODERATE] cos(angle) vs omega_700hPa correlation")
        print("  -> Mesoscale influence present")
    else:
        print("\n[WEAK] cos(angle) vs omega_700hPa correlation")
        print("  -> Weak mesoscale-synoptic coupling")

    # 比較のため、予報データの結果も読み込み
    try:
        with open('temporal_robustness_kutsugata.json', 'r', encoding='utf-8') as f:
            forecast_results = json.load(f)

        fc_corr_vort = forecast_results['forecast_data']['correlations']['cos_angle_vs_vorticity_500hPa']
        fc_corr_omega = forecast_results['forecast_data']['correlations']['cos_angle_vs_omega_700hPa']

        print(f"\n{'='*70}")
        print("COMPARISON WITH FORECAST DATA")
        print(f"{'='*70}")
        print(f"\nRadiosonde (observed):")
        print(f"  cos vs vorticity_500hPa: r = {corr_cos_vort:+.3f}")
        print(f"  cos vs omega_700hPa:     r = {corr_cos_omega:+.3f}")
        print(f"\nForecast (model):")
        print(f"  cos vs vorticity_500hPa: r = {fc_corr_vort:+.3f}")
        print(f"  cos vs omega_700hPa:     r = {fc_corr_omega:+.3f}")
        print(f"\nDifference:")
        print(f"  vorticity: {abs(corr_cos_vort - fc_corr_vort):.3f}")
        print(f"  omega:     {abs(corr_cos_omega - fc_corr_omega):.3f}")

    except FileNotFoundError:
        pass

    # 結果を保存
    results = {
        'timestamp': datetime.now().isoformat(),
        'data_source': 'Wakkanai Radiosonde (observed)',
        'location_analyzed': 'Kutsugata (West side)',
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
                'min': float(np.min(cos_vals)),
                'max': float(np.max(cos_vals))
            },
            'omega_700hPa': {
                'mean': float(np.mean(omega_vals)),
                'std': float(np.std(omega_vals)),
                'min': float(np.min(omega_vals)),
                'max': float(np.max(omega_vals))
            },
            'vorticity_500hPa': {
                'mean': float(np.mean(vort_vals)),
                'std': float(np.std(vort_vals)),
                'min': float(np.min(vort_vals)),
                'max': float(np.max(vort_vals))
            }
        },
        'interpretation': {
            'dominant_scale': 'synoptic' if abs(corr_cos_vort) > 0.5 else 'mesoscale' if abs(corr_cos_omega) > 0.5 else 'mixed',
            'vorticity_correlation_strength': 'strong' if abs(corr_cos_vort) > 0.5 else 'moderate' if abs(corr_cos_vort) > 0.3 else 'weak',
            'omega_correlation_strength': 'strong' if abs(corr_cos_omega) > 0.5 else 'moderate' if abs(corr_cos_omega) > 0.3 else 'weak'
        }
    }

    with open('radiosonde_correlation_results.json', 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"\nResults saved to: radiosonde_correlation_results.json")

if __name__ == '__main__':
    analyze_radiosonde_correlation()
