#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
2025年夏季 気団交代パターン解析

等相当温位θeの時系列解析により:
- 気団の種類判別（暖湿/冷乾）
- 気団交代タイミングの検出
- 天候パターンの抽出（好天期/悪天期）
- 干場実績との対応付け
"""

import xarray as xr
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
import json
import math

# 利尻山・沓形の座標
RISHIRI_SAN_LAT = 45.1821
RISHIRI_SAN_LON = 141.2421
KUTSUGATA_LAT = 45.2422
KUTSUGATA_LON = 141.1088

# 物理定数
Rd = 287.0  # 乾燥空気の気体定数 (J/kg/K)
Cp = 1005.0  # 定圧比熱 (J/kg/K)
Lv = 2.5e6  # 水の蒸発潜熱 (J/kg)
epsilon = 0.622  # 水蒸気の分子量比

def calculate_equivalent_potential_temperature(T, p, q):
    """
    相当温位θeを計算

    Args:
        T: 温度 (K)
        p: 気圧 (hPa)
        q: 比湿 (kg/kg)
    Returns:
        θe: 相当温位 (K)
    """
    # 温位計算
    theta = T * (1000.0 / p) ** (Rd / Cp)

    # 混合比計算
    r = q / (1 - q)

    # 相当温位計算
    theta_e = theta * np.exp((Lv * r) / (Cp * T))

    return theta_e

def classify_air_mass(theta_e):
    """
    相当温位から気団を分類

    Args:
        theta_e: 相当温位 (K)
    Returns:
        air_mass_type: 気団種類
    """
    if theta_e > 335:
        return "Very Warm & Humid (Pacific High)"
    elif theta_e > 330:
        return "Warm & Humid (Maritime Tropical)"
    elif theta_e > 325:
        return "Moderate (Transition)"
    elif theta_e > 320:
        return "Cool & Dry (Maritime Polar)"
    else:
        return "Very Cool & Dry (Okhotsk High)"

def detect_transitions(theta_e_series, threshold=3.0):
    """
    気団交代を検出

    Args:
        theta_e_series: 相当温位時系列
        threshold: 変化閾値 (K)
    Returns:
        transitions: 交代タイミングのインデックス
    """
    transitions = []
    diff = np.diff(theta_e_series)

    for i in range(len(diff)):
        if abs(diff[i]) > threshold:
            transitions.append({
                'index': i,
                'date_index': i,
                'change': diff[i],
                'type': 'warming' if diff[i] > 0 else 'cooling'
            })

    return transitions

def moving_average(data, window=7):
    """
    移動平均を計算

    Args:
        data: 時系列データ
        window: 窓幅（日数）
    Returns:
        ma: 移動平均
    """
    return np.convolve(data, np.ones(window)/window, mode='valid')

def analyze_air_mass_transitions():
    """気団交代パターンの解析メイン"""

    print("="*70)
    print("AIR MASS TRANSITION ANALYSIS - SUMMER 2025")
    print("="*70)

    # データ読み込み
    try:
        ds = xr.open_dataset('era5_rishiri_summer2025.nc')
        print("\nLoaded: era5_rishiri_summer2025.nc")
    except FileNotFoundError:
        print("\nError: era5_rishiri_summer2025.nc not found")
        print("Please run fetch_era5_summer2025.py first")
        return

    # データ情報表示
    print(f"\nDataset info:")
    print(f"  Time range: {ds.valid_time.values[0]} to {ds.valid_time.values[-1]}")
    print(f"  Number of timesteps: {len(ds.valid_time)}")
    print(f"  Pressure levels: {ds.pressure_level.values} hPa")

    # 850hPa データ抽出
    ds_850 = ds.sel(pressure_level=850)

    t_850 = ds_850['t']  # 温度 (K)
    q_850 = ds_850['q']  # 比湿 (kg/kg)
    u_850 = ds_850['u']
    v_850 = ds_850['v']

    lat = ds_850.latitude.values
    lon = ds_850.longitude.values

    # 沓形地点の最近傍グリッド
    lat_idx = np.abs(lat - KUTSUGATA_LAT).argmin()
    lon_idx = np.abs(lon - KUTSUGATA_LON).argmin()

    print(f"\nAnalysis point: Kutsugata")
    print(f"  Target: {KUTSUGATA_LAT:.2f}N, {KUTSUGATA_LON:.2f}E")
    print(f"  Grid:   {lat[lat_idx]:.2f}N, {lon[lon_idx]:.2f}E")

    # 時系列データ抽出
    print(f"\nExtracting time series data...")

    dates = []
    theta_e_values = []
    temp_values = []
    wind_speed_values = []
    air_mass_types = []

    for t in range(len(ds_850.valid_time)):
        date = ds_850.valid_time.isel(valid_time=t).values

        t_pt = t_850.isel(valid_time=t, latitude=lat_idx, longitude=lon_idx).values
        q_pt = q_850.isel(valid_time=t, latitude=lat_idx, longitude=lon_idx).values
        u_pt = u_850.isel(valid_time=t, latitude=lat_idx, longitude=lon_idx).values
        v_pt = v_850.isel(valid_time=t, latitude=lat_idx, longitude=lon_idx).values

        # 相当温位計算
        theta_e = calculate_equivalent_potential_temperature(t_pt, 850, q_pt)

        # 風速計算
        wind_speed = np.sqrt(u_pt**2 + v_pt**2)

        # 気団分類
        air_mass = classify_air_mass(theta_e)

        dates.append(date)
        theta_e_values.append(theta_e)
        temp_values.append(t_pt - 273.15)  # K → ℃
        wind_speed_values.append(wind_speed)
        air_mass_types.append(air_mass)

    # 配列化
    dates = np.array(dates)
    theta_e_values = np.array(theta_e_values)
    temp_values = np.array(temp_values)
    wind_speed_values = np.array(wind_speed_values)

    print(f"\nData extracted: {len(theta_e_values)} days")

    # 統計情報
    print(f"\n{'='*70}")
    print("STATISTICAL SUMMARY")
    print(f"{'='*70}")

    print(f"\nEquivalent Potential Temperature (theta_e):")
    print(f"  Mean:   {np.mean(theta_e_values):.1f} K")
    print(f"  Std:    {np.std(theta_e_values):.1f} K")
    print(f"  Min:    {np.min(theta_e_values):.1f} K")
    print(f"  Max:    {np.max(theta_e_values):.1f} K")
    print(f"  Range:  {np.max(theta_e_values) - np.min(theta_e_values):.1f} K")

    print(f"\nTemperature:")
    print(f"  Mean:   {np.mean(temp_values):.1f} C")
    print(f"  Std:    {np.std(temp_values):.1f} C")

    print(f"\nWind Speed:")
    print(f"  Mean:   {np.mean(wind_speed_values):.1f} m/s")
    print(f"  Std:    {np.std(wind_speed_values):.1f} m/s")

    # 気団交代検出
    print(f"\n{'='*70}")
    print("AIR MASS TRANSITION DETECTION")
    print(f"{'='*70}")

    transitions = detect_transitions(theta_e_values, threshold=3.0)

    print(f"\nDetected {len(transitions)} significant transitions (>3K change)")

    for i, trans in enumerate(transitions[:10], 1):  # 最初の10個表示
        idx = trans['index']
        date_str = str(dates[idx])[:10]
        print(f"  {i}. {date_str}: {trans['change']:+.1f}K ({trans['type']})")
        if i < len(transitions):
            print(f"     {air_mass_types[idx]} -> {air_mass_types[idx+1]}")

    if len(transitions) > 10:
        print(f"  ... and {len(transitions)-10} more transitions")

    # 7日間移動平均
    theta_e_ma7 = moving_average(theta_e_values, window=7)

    # 好天期・悪天期の検出（簡易版）
    # 高θe期（>330K）を好天、低θe期（<325K）を悪天と仮定
    good_weather_periods = []
    bad_weather_periods = []

    current_good = None
    current_bad = None

    for i, theta_e in enumerate(theta_e_values):
        if theta_e > 330:
            if current_good is None:
                current_good = {'start': i, 'start_date': dates[i]}
            if current_bad is not None:
                current_bad['end'] = i - 1
                current_bad['end_date'] = dates[i-1]
                current_bad['duration'] = current_bad['end'] - current_bad['start'] + 1
                bad_weather_periods.append(current_bad)
                current_bad = None
        elif theta_e < 325:
            if current_bad is None:
                current_bad = {'start': i, 'start_date': dates[i]}
            if current_good is not None:
                current_good['end'] = i - 1
                current_good['end_date'] = dates[i-1]
                current_good['duration'] = current_good['end'] - current_good['start'] + 1
                good_weather_periods.append(current_good)
                current_good = None

    # 最後の期間を閉じる
    if current_good is not None:
        current_good['end'] = len(theta_e_values) - 1
        current_good['end_date'] = dates[-1]
        current_good['duration'] = current_good['end'] - current_good['start'] + 1
        good_weather_periods.append(current_good)

    if current_bad is not None:
        current_bad['end'] = len(theta_e_values) - 1
        current_bad['end_date'] = dates[-1]
        current_bad['duration'] = current_bad['end'] - current_bad['start'] + 1
        bad_weather_periods.append(current_bad)

    print(f"\n{'='*70}")
    print("WEATHER PERIOD CLASSIFICATION")
    print(f"{'='*70}")

    print(f"\nGood weather periods (theta_e > 330K):")
    for i, period in enumerate(good_weather_periods, 1):
        start = str(period['start_date'])[:10]
        end = str(period['end_date'])[:10]
        print(f"  {i}. {start} to {end} ({period['duration']} days)")

    print(f"\nBad weather periods (theta_e < 325K):")
    for i, period in enumerate(bad_weather_periods, 1):
        start = str(period['start_date'])[:10]
        end = str(period['end_date'])[:10]
        print(f"  {i}. {start} to {end} ({period['duration']} days)")

    # 可視化
    print(f"\n{'='*70}")
    print("GENERATING VISUALIZATIONS")
    print(f"{'='*70}")

    # 図1: 相当温位時系列
    fig, axes = plt.subplots(3, 1, figsize=(14, 10), sharex=True)

    # θe時系列
    ax1 = axes[0]
    ax1.plot(range(len(theta_e_values)), theta_e_values, 'b-', linewidth=1.5, label='Daily theta_e')
    if len(theta_e_ma7) > 0:
        ax1.plot(range(3, 3+len(theta_e_ma7)), theta_e_ma7, 'r-', linewidth=2.5, label='7-day moving average')
    ax1.axhline(330, color='green', linestyle='--', alpha=0.5, label='Good weather threshold')
    ax1.axhline(325, color='orange', linestyle='--', alpha=0.5, label='Bad weather threshold')
    ax1.set_ylabel('Equivalent Potential\nTemperature (K)', fontsize=11)
    ax1.set_title('Air Mass Transitions - Summer 2025 (Kutsugata)', fontsize=14, fontweight='bold')
    ax1.legend(loc='upper right', fontsize=9)
    ax1.grid(True, alpha=0.3)

    # 気温
    ax2 = axes[1]
    ax2.plot(range(len(temp_values)), temp_values, 'r-', linewidth=1.5)
    ax2.set_ylabel('Temperature (C)', fontsize=11)
    ax2.grid(True, alpha=0.3)

    # 風速
    ax3 = axes[2]
    ax3.plot(range(len(wind_speed_values)), wind_speed_values, 'g-', linewidth=1.5)
    ax3.set_ylabel('Wind Speed (m/s)', fontsize=11)
    ax3.set_xlabel('Days since June 1, 2025', fontsize=11)
    ax3.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig('air_mass_transitions_2025_timeseries.png', dpi=150, bbox_inches='tight')
    print("  Saved: air_mass_transitions_2025_timeseries.png")
    plt.close()

    # 結果保存
    output = {
        'analysis_date': datetime.now().isoformat(),
        'period': {
            'start': str(dates[0]),
            'end': str(dates[-1]),
            'n_days': len(dates)
        },
        'statistics': {
            'theta_e_mean': float(np.mean(theta_e_values)),
            'theta_e_std': float(np.std(theta_e_values)),
            'theta_e_min': float(np.min(theta_e_values)),
            'theta_e_max': float(np.max(theta_e_values)),
            'temperature_mean': float(np.mean(temp_values)),
            'wind_speed_mean': float(np.mean(wind_speed_values))
        },
        'transitions': [
            {
                'date': str(dates[t['index']]),
                'change_K': float(t['change']),
                'type': t['type']
            }
            for t in transitions
        ],
        'good_weather_periods': [
            {
                'start': str(p['start_date']),
                'end': str(p['end_date']),
                'duration_days': int(p['duration'])
            }
            for p in good_weather_periods
        ],
        'bad_weather_periods': [
            {
                'start': str(p['start_date']),
                'end': str(p['end_date']),
                'duration_days': int(p['duration'])
            }
            for p in bad_weather_periods
        ]
    }

    with open('air_mass_transitions_2025_results.json', 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print("  Saved: air_mass_transitions_2025_results.json")

    print(f"\n{'='*70}")
    print("ANALYSIS COMPLETE")
    print(f"{'='*70}")

    return output

if __name__ == '__main__':
    analyze_air_mass_transitions()
