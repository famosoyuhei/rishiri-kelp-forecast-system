#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
アメダス沓形データによる時間的ロバスト性テスト

目的：実測データで異なる日付・時間帯をサンプリングし、
     西側（日本海側）の風向-山角度差の一貫性を検証
"""

import json
import math
import numpy as np
from datetime import datetime, timedelta
import random
import requests
import time

RISHIRI_SAN_LAT = 45.1821
RISHIRI_SAN_LON = 141.2421

# アメダス沓形の座標
KUTSUGATA_LAT = 45.2422
KUTSUGATA_LON = 141.1088

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

def generate_random_dates(n_dates=20):
    """2024年6-8月からランダムに日付を生成"""
    start_date = datetime(2024, 6, 1)
    end_date = datetime(2024, 8, 31)

    date_range = (end_date - start_date).days
    random_dates = []

    for _ in range(n_dates):
        random_day = random.randint(0, date_range)
        random_date = start_date + timedelta(days=random_day)
        random_dates.append(random_date.strftime('%Y-%m-%d'))

    return sorted(set(random_dates))  # 重複を除去してソート

def fetch_historical_data(lat, lon, date_str):
    """Open-Meteo Archive APIから過去データを取得（地上データのみ）"""
    url = f"https://archive-api.open-meteo.com/v1/archive"
    params = {
        'latitude': lat,
        'longitude': lon,
        'start_date': date_str,
        'end_date': date_str,
        'hourly': 'wind_speed_10m,wind_direction_10m',
        'timezone': 'Asia/Tokyo'
    }

    try:
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Error fetching data for {date_str}: {e}")
        return None

def fetch_forecast_for_correlation(lat, lon):
    """予報データから上層データを取得（3変数相関用）"""
    url = f"https://api.open-meteo.com/v1/forecast"
    params = {
        'latitude': lat,
        'longitude': lon,
        'hourly': 'wind_speed_10m,wind_direction_10m,temperature_700hPa,geopotential_height_500hPa',
        'timezone': 'Asia/Tokyo',
        'forecast_days': 3
    }

    try:
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Error fetching forecast data: {e}")
        return None

def calculate_vertical_p_velocity(hourly_data, hour_index):
    """700hPa鉛直p速度を簡易計算"""
    try:
        temps = hourly_data.get('temperature_700hPa', [])
        if hour_index < 1 or hour_index >= len(temps) - 1:
            return None

        temp_prev = temps[hour_index - 1]
        temp_next = temps[hour_index + 1]

        if temp_prev is None or temp_next is None:
            return None

        dt = 2 * 3600  # 2時間（秒）
        dT = temp_next - temp_prev
        omega = -dT / dt * 100  # Pa/s単位

        return omega
    except:
        return None

def calculate_vorticity_500hpa(hourly_data, hour_index, lat):
    """500hPa相対渦度を簡易推定"""
    try:
        heights = hourly_data.get('geopotential_height_500hPa', [])
        if hour_index < 1 or hour_index >= len(heights) - 1:
            return None

        z_prev = heights[hour_index - 1]
        z_next = heights[hour_index + 1]

        if z_prev is None or z_next is None:
            return None

        dt = 2 * 3600  # 2時間
        dz = z_next - z_prev

        # コリオリパラメータ
        f = 2 * 7.292e-5 * math.sin(math.radians(lat))
        vorticity = -dz / dt * f / 100  # 10^-5 s^-1単位

        return vorticity
    except:
        return None

def analyze_kutsugata_temporal_robustness():
    """沓形座標での時間的ロバスト性を分析"""

    mountain_azimuth = calculate_mountain_azimuth(KUTSUGATA_LAT, KUTSUGATA_LON)
    print(f"="*70)
    print("PART 1: TEMPORAL ROBUSTNESS TEST (HISTORICAL DATA)")
    print(f"="*70)
    print(f"\nKutsugata (West side)")
    print(f"  Coordinates: lat={KUTSUGATA_LAT:.4f}, lon={KUTSUGATA_LON:.4f}")
    print(f"  Mountain azimuth: {mountain_azimuth:.1f}deg")

    # ランダムに日付を生成
    random_dates = generate_random_dates(n_dates=20)
    print(f"\nRandomly sampling {len(random_dates)} dates from Jun-Aug 2024:")
    for date in random_dates[:5]:
        print(f"  {date}")
    if len(random_dates) > 5:
        print(f"  ... and {len(random_dates) - 5} more dates")

    # 過去データ収集（地上風向のみ）
    all_cos_hist = []
    all_wind_dirs_hist = []
    all_wind_speeds_hist = []
    date_hour_pairs_hist = []

    for i, date_str in enumerate(random_dates):
        print(f"[{i+1}/{len(random_dates)}] Fetching {date_str}...", end=" ")

        data = fetch_historical_data(KUTSUGATA_LAT, KUTSUGATA_LON, date_str)
        if not data or 'hourly' not in data:
            print("No data")
            continue

        hourly = data['hourly']
        times = hourly.get('time', [])
        wind_dirs = hourly.get('wind_direction_10m', [])
        wind_speeds = hourly.get('wind_speed_10m', [])

        # 4-16時の時間帯を抽出
        available_indices = []
        for idx, time_str in enumerate(times):
            hour = int(time_str.split('T')[1].split(':')[0])
            if 4 <= hour <= 16 and wind_dirs[idx] is not None:
                available_indices.append(idx)

        # ランダムに3-5時間分をサンプリング
        if len(available_indices) > 0:
            n_sample = min(random.randint(3, 5), len(available_indices))
            sampled_indices = random.sample(available_indices, n_sample)

            for idx in sampled_indices:
                wind_dir = wind_dirs[idx]
                wind_speed = wind_speeds[idx]
                time_str = times[idx]
                hour_str = time_str.split('T')[1]

                if wind_dir is None:
                    continue

                # 風向-山角度差のコサイン
                wind_toward = (wind_dir + 180) % 360
                angle_diff = abs(wind_toward - mountain_azimuth)
                if angle_diff > 180:
                    angle_diff = 360 - angle_diff
                cos_angle = math.cos(math.radians(angle_diff))

                all_cos_hist.append(cos_angle)
                all_wind_dirs_hist.append(wind_dir)
                if wind_speed is not None:
                    all_wind_speeds_hist.append(wind_speed)
                date_hour_pairs_hist.append((date_str, hour_str))

            print(f"OK ({len(sampled_indices)} samples)")
        else:
            print("No valid hours")

        # API制限対策
        time.sleep(0.5)

    # 統計分析（過去データ）
    if len(all_cos_hist) == 0:
        print("\nNo historical data collected!")
        return

    cos_vals_hist = np.array(all_cos_hist)
    wind_dirs_hist = np.array(all_wind_dirs_hist)

    print("\n" + "="*70)
    print("HISTORICAL DATA RESULTS")
    print("="*70)
    print(f"\nTotal samples: {len(cos_vals_hist)}")
    print(f"Unique dates: {len(set([d for d, h in date_hour_pairs_hist]))}")
    print(f"Unique hours: {len(set([h for d, h in date_hour_pairs_hist]))}")

    print(f"\ncos(wind-mountain angle) statistics:")
    print(f"  Mean:   {np.mean(cos_vals_hist):+.3f}")
    print(f"  Std:    {np.std(cos_vals_hist):.3f}")
    print(f"  Median: {np.median(cos_vals_hist):+.3f}")
    print(f"  Range:  [{np.min(cos_vals_hist):+.3f}, {np.max(cos_vals_hist):+.3f}]")

    # 風向の分布
    print(f"\nWind direction statistics:")
    print(f"  Mean:   {np.mean(wind_dirs_hist):.1f}deg")
    print(f"  Median: {np.median(wind_dirs_hist):.1f}deg")
    print(f"  Range:  [{np.min(wind_dirs_hist):.1f}deg, {np.max(wind_dirs_hist):.1f}deg]")

    mean_cos_hist = np.mean(cos_vals_hist)
    std_cos_hist = np.std(cos_vals_hist)

    print("\n" + "="*70)
    print("TEMPORAL ROBUSTNESS INTERPRETATION")
    print("="*70)

    # 風向-山角度の傾向
    if abs(mean_cos_hist) > 0.5:
        if mean_cos_hist > 0:
            print("[OK] Consistently wind TOWARD mountain")
            print("  -> Strong mesoscale (mountain) effect")
        else:
            print("[OK] Consistently wind FROM mountain")
            print("  -> Strong lee-side/downslope effect")
    else:
        print("[--] Variable wind directions")
        print("  -> Synoptic scale dominated")

    if std_cos_hist < 0.3:
        print(f"\n[OK] Low variability (std={std_cos_hist:.3f})")
        print("  -> Consistent wind-mountain relationship across time")
        print("  -> Temporally ROBUST")
    else:
        print(f"\n[--] High variability (std={std_cos_hist:.3f})")
        print("  -> Variable relationship across time")
        print("  -> NOT temporally robust")

    # ヒストグラム
    print(f"\ncos(angle) distribution (historical):")
    bins = np.linspace(-1, 1, 11)
    hist, _ = np.histogram(cos_vals_hist, bins=bins)
    for i in range(len(hist)):
        bin_start = bins[i]
        bin_end = bins[i+1]
        bar = '#' * int(hist[i] / max(hist) * 50) if max(hist) > 0 else ''
        print(f"  [{bin_start:+.1f}, {bin_end:+.1f}): {bar} ({hist[i]})")

    # Part 2: 予報データで3変数相関分析
    print(f"\n\n" + "="*70)
    print("PART 2: THREE-VARIABLE CORRELATION (FORECAST DATA)")
    print("="*70)
    print(f"\nFetching current forecast data for Kutsugata...")

    forecast_data = fetch_forecast_for_correlation(KUTSUGATA_LAT, KUTSUGATA_LON)
    if not forecast_data or 'hourly' not in forecast_data:
        print("Failed to fetch forecast data")
        return

    hourly_fc = forecast_data['hourly']

    # 予報データから相関を計算
    all_cos_fc = []
    all_omega_fc = []
    all_vort_fc = []

    for h in range(4, min(17, len(hourly_fc.get('wind_direction_10m', [])))):
        wind_dir = hourly_fc.get('wind_direction_10m', [])[h]
        if wind_dir is None:
            continue

        # cos(angle)
        wind_toward = (wind_dir + 180) % 360
        angle_diff = abs(wind_toward - mountain_azimuth)
        if angle_diff > 180:
            angle_diff = 360 - angle_diff
        cos_angle = math.cos(math.radians(angle_diff))

        # omega
        omega = calculate_vertical_p_velocity(hourly_fc, h)

        # vorticity
        vorticity = calculate_vorticity_500hpa(hourly_fc, h, KUTSUGATA_LAT)

        if omega is not None and vorticity is not None:
            all_cos_fc.append(cos_angle)
            all_omega_fc.append(omega)
            all_vort_fc.append(vorticity)

    if len(all_cos_fc) == 0:
        print("No forecast data with upper-air variables")
        return

    cos_fc = np.array(all_cos_fc)
    omega_fc = np.array(all_omega_fc)
    vort_fc = np.array(all_vort_fc)

    corr_cos_omega = np.corrcoef(cos_fc, omega_fc)[0, 1] if len(cos_fc) > 1 else 0
    corr_cos_vort = np.corrcoef(cos_fc, vort_fc)[0, 1] if len(cos_fc) > 1 else 0
    corr_omega_vort = np.corrcoef(omega_fc, vort_fc)[0, 1] if len(omega_fc) > 1 else 0

    print(f"\nSamples: {len(cos_fc)}")
    print(f"\nCorrelation coefficients:")
    print(f"  cos(angle) vs omega_700hPa:        r = {corr_cos_omega:+.3f}")
    print(f"  cos(angle) vs vorticity_500hPa:    r = {corr_cos_vort:+.3f}")
    print(f"  omega_700hPa vs vorticity_500hPa:  r = {corr_omega_vort:+.3f}")

    # 相関の解釈
    print(f"\n" + "="*70)
    print("CORRELATION INTERPRETATION")
    print("="*70)

    if abs(corr_cos_omega) > 0.3:
        print(f"[MODERATE+] cos(angle) vs omega_700hPa: r={corr_cos_omega:+.3f}")
        if corr_cos_omega > 0:
            print("  -> Wind toward mountain = upward motion (orographic lift)")
        else:
            print("  -> Wind toward mountain = downward motion")
    else:
        print(f"[WEAK] cos(angle) vs omega_700hPa: r={corr_cos_omega:+.3f}")
        print("  -> Weak mesoscale-synoptic coupling")

    if abs(corr_cos_vort) > 0.3:
        print(f"\n[MODERATE+] cos(angle) vs vorticity_500hPa: r={corr_cos_vort:+.3f}")
        if corr_cos_vort > 0:
            print("  -> Synoptic scale DRIVES wind-mountain alignment")
        else:
            print("  -> Synoptic cyclonic flow OPPOSES mountain effect")
    else:
        print(f"\n[WEAK] cos(angle) vs vorticity_500hPa: r={corr_cos_vort:+.3f}")
        print("  -> Wind-mountain relationship independent of synoptic scale")

    # 総合判定
    print(f"\nOverall assessment:")
    if abs(corr_cos_vort) > 0.5:
        print("  SYNOPTIC SCALE DOMINATED")
        print("  -> Large-scale pressure systems control local wind direction")
    elif abs(corr_cos_omega) > 0.5:
        print("  MESOSCALE DOMINATED")
        print("  -> Mountain-induced vertical motion controls local weather")
    else:
        print("  MIXED SCALE INFLUENCE")
        print("  -> Both synoptic and mesoscale factors contribute")

    # 結果を保存
    results = {
        'timestamp': datetime.now().isoformat(),
        'location': 'Kutsugata AMeDAS (West side)',
        'coordinates': {'lat': KUTSUGATA_LAT, 'lon': KUTSUGATA_LON},
        'mountain_azimuth': mountain_azimuth,
        'historical_data': {
            'sampling': {
                'total_samples': len(cos_vals_hist),
                'n_dates': len(set([d for d, h in date_hour_pairs_hist])),
                'n_hours': len(set([h for d, h in date_hour_pairs_hist])),
                'sampled_date_hours': [f"{d}_{h}" for d, h in date_hour_pairs_hist[:20]]
            },
            'statistics': {
                'cos_angle': {
                    'mean': float(np.mean(cos_vals_hist)),
                    'std': float(np.std(cos_vals_hist)),
                    'median': float(np.median(cos_vals_hist)),
                    'min': float(np.min(cos_vals_hist)),
                    'max': float(np.max(cos_vals_hist))
                },
                'wind_direction': {
                    'mean': float(np.mean(wind_dirs_hist)),
                    'median': float(np.median(wind_dirs_hist)),
                    'min': float(np.min(wind_dirs_hist)),
                    'max': float(np.max(wind_dirs_hist))
                }
            },
            'temporal_robustness': 'high' if std_cos_hist < 0.3 else 'medium' if std_cos_hist < 0.5 else 'low'
        },
        'forecast_data': {
            'n_samples': len(cos_fc),
            'correlations': {
                'cos_angle_vs_omega_700hPa': float(corr_cos_omega),
                'cos_angle_vs_vorticity_500hPa': float(corr_cos_vort),
                'omega_700hPa_vs_vorticity_500hPa': float(corr_omega_vort)
            },
            'dominant_scale': 'synoptic' if abs(corr_cos_vort) > 0.5 else 'mesoscale' if abs(corr_cos_omega) > 0.5 else 'mixed'
        },
        'interpretation': {
            'temporal_consistency': 'consistent' if std_cos_hist < 0.3 else 'variable',
            'dominant_scale': 'synoptic' if abs(corr_cos_vort) > 0.5 else 'mesoscale' if abs(corr_cos_omega) > 0.5 else 'mixed',
            'mountain_effect': 'toward' if mean_cos_hist > 0.5 else 'from' if mean_cos_hist < -0.5 else 'variable'
        }
    }

    with open('temporal_robustness_kutsugata.json', 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"\nResults saved to: temporal_robustness_kutsugata.json")

    return results

if __name__ == '__main__':
    analyze_kutsugata_temporal_robustness()
