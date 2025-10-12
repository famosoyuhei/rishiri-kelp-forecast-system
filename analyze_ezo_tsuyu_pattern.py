#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
蝦夷梅雨パターン解析

降水量・SST・気団の複合解析により蝦夷梅雨を定量化:
1. 連続降水日数の検出
2. SST-降水量の相関
3. 気団（θe）-降水量の関係
4. 2024年 vs 2025年の比較
"""

import xarray as xr
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
import json

KUTSUGATA_LAT = 45.2422
KUTSUGATA_LON = 141.1088

def analyze_ezo_tsuyu():
    """蝦夷梅雨パターンの解析"""

    print("="*70)
    print("EZO TSUYU (HOKKAIDO RAINY SEASON) ANALYSIS")
    print("="*70)

    # データ読み込み
    try:
        precip_2024 = xr.open_dataset('era5_rishiri_precipitation_summer2024.nc')
        precip_2025 = xr.open_dataset('era5_rishiri_precipitation_summer2025.nc')
        sst_2024 = xr.open_dataset('era5_rishiri_ocean_summer2024.nc')
        sst_2025 = xr.open_dataset('era5_rishiri_ocean_summer2025.nc')

        # 気団データ
        with open('air_mass_transitions_2025_results.json', 'r', encoding='utf-8') as f:
            air_mass_data = json.load(f)

        print("\nAll datasets loaded successfully")
    except FileNotFoundError as e:
        print(f"\nError: {e}")
        print("Please run required data fetch scripts first")
        return

    # 変数名特定
    precip_var_2024 = 'tp' if 'tp' in precip_2024 else 'total_precipitation'
    precip_var_2025 = 'tp' if 'tp' in precip_2025 else 'total_precipitation'

    # 沓形地点の最近傍
    lat_2024 = precip_2024.latitude.values
    lon_2024 = precip_2024.longitude.values
    lat_2025 = precip_2025.latitude.values
    lon_2025 = precip_2025.longitude.values

    lat_idx_2024 = np.abs(lat_2024 - KUTSUGATA_LAT).argmin()
    lon_idx_2024 = np.abs(lon_2024 - KUTSUGATA_LON).argmin()
    lat_idx_2025 = np.abs(lat_2025 - KUTSUGATA_LAT).argmin()
    lon_idx_2025 = np.abs(lon_2025 - KUTSUGATA_LON).argmin()

    print(f"\nAnalysis point: Kutsugata ({KUTSUGATA_LAT:.2f}N, {KUTSUGATA_LON:.2f}E)")

    # 日積算降水量を計算
    print(f"\nCalculating daily precipitation totals...")

    def calculate_daily_precip(ds, var_name, lat_idx, lon_idx):
        """日積算降水量を計算"""
        precip = ds[var_name].isel(latitude=lat_idx, longitude=lon_idx)

        # ERA5の降水量は累積値なので、日ごとにグループ化して最大値を取る
        # 単位: m → mm に変換
        daily_values = []

        # 時刻データを日付に変換
        times = precip.valid_time.values
        dates = np.array([np.datetime64(t, 'D') for t in times])
        unique_dates = np.unique(dates)

        for date in unique_dates:
            mask = dates == date
            day_data = precip.isel(valid_time=mask).values
            # 累積値の差分（最大-最小）を日降水量とする
            if len(day_data) > 0:
                daily_total = (np.max(day_data) - np.min(day_data)) * 1000  # m → mm
                daily_values.append(max(0, daily_total))  # 負値を除外
            else:
                daily_values.append(0)

        return unique_dates, np.array(daily_values)

    dates_2024, precip_2024_daily = calculate_daily_precip(
        precip_2024, precip_var_2024, lat_idx_2024, lon_idx_2024)
    dates_2025, precip_2025_daily = calculate_daily_precip(
        precip_2025, precip_var_2025, lat_idx_2025, lon_idx_2025)

    print(f"  2024: {len(precip_2024_daily)} days")
    print(f"  2025: {len(precip_2025_daily)} days")

    # 連続降水日数の検出
    def detect_rainy_periods(daily_precip, threshold_mm=1.0):
        """連続降水期間を検出"""
        rainy_days = daily_precip > threshold_mm
        periods = []

        current_start = None
        for i, is_rainy in enumerate(rainy_days):
            if is_rainy and current_start is None:
                current_start = i
            elif not is_rainy and current_start is not None:
                periods.append({
                    'start': current_start,
                    'end': i - 1,
                    'duration': i - current_start
                })
                current_start = None

        # 最後の期間を閉じる
        if current_start is not None:
            periods.append({
                'start': current_start,
                'end': len(rainy_days) - 1,
                'duration': len(rainy_days) - current_start
            })

        return periods

    rainy_2024 = detect_rainy_periods(precip_2024_daily)
    rainy_2025 = detect_rainy_periods(precip_2025_daily)

    # 統計
    print(f"\n{'='*70}")
    print("PRECIPITATION STATISTICS")
    print(f"{'='*70}")

    print(f"\n2024:")
    print(f"  Total precipitation: {np.sum(precip_2024_daily):.1f} mm")
    print(f"  Mean daily: {np.mean(precip_2024_daily):.2f} mm")
    print(f"  Rainy days (>1mm): {np.sum(precip_2024_daily > 1.0)}")
    print(f"  Max daily: {np.max(precip_2024_daily):.1f} mm")

    print(f"\n2025:")
    print(f"  Total precipitation: {np.sum(precip_2025_daily):.1f} mm")
    print(f"  Mean daily: {np.mean(precip_2025_daily):.2f} mm")
    print(f"  Rainy days (>1mm): {np.sum(precip_2025_daily > 1.0)}")
    print(f"  Max daily: {np.max(precip_2025_daily):.1f} mm")

    # 長雨期間
    print(f"\n{'='*70}")
    print("EZO TSUYU DETECTION (Continuous rainy periods)")
    print(f"{'='*70}")

    print(f"\n2024 rainy periods (>= 5 consecutive days):")
    long_rain_2024 = [p for p in rainy_2024 if p['duration'] >= 5]
    for period in long_rain_2024:
        start_date = dates_2024[period['start']]
        end_date = dates_2024[period['end']]
        total_rain = np.sum(precip_2024_daily[period['start']:period['end']+1])
        print(f"  {str(start_date)[:10]} to {str(end_date)[:10]}: "
              f"{period['duration']} days, {total_rain:.1f} mm total")

    print(f"\n2025 rainy periods (>= 5 consecutive days):")
    long_rain_2025 = [p for p in rainy_2025 if p['duration'] >= 5]
    for period in long_rain_2025:
        start_date = dates_2025[period['start']]
        end_date = dates_2025[period['end']]
        total_rain = np.sum(precip_2025_daily[period['start']:period['end']+1])
        print(f"  {str(start_date)[:10]} to {str(end_date)[:10]}: "
              f"{period['duration']} days, {total_rain:.1f} mm total")

    # 可視化
    print(f"\n{'='*70}")
    print("GENERATING VISUALIZATIONS")
    print(f"{'='*70}")

    fig, axes = plt.subplots(3, 1, figsize=(14, 10), sharex=True)

    days_2024 = np.arange(len(precip_2024_daily))
    days_2025 = np.arange(len(precip_2025_daily))

    # 日降水量比較
    ax1 = axes[0]
    ax1.bar(days_2024, precip_2024_daily, width=0.8, alpha=0.6, label='2024', color='blue')
    ax1.bar(days_2025, precip_2025_daily, width=0.8, alpha=0.6, label='2025', color='red')
    ax1.axhline(1.0, color='gray', linestyle='--', alpha=0.5, label='Rainy day threshold')
    ax1.set_ylabel('Daily Precipitation (mm)', fontsize=11)
    ax1.set_title('Ezo Tsuyu Analysis: 2024 vs 2025 (Kutsugata)',
                 fontsize=14, fontweight='bold')
    ax1.legend(loc='upper right', fontsize=10)
    ax1.grid(True, alpha=0.3, axis='y')

    # 累積降水量
    ax2 = axes[1]
    ax2.plot(days_2024, np.cumsum(precip_2024_daily), 'b-', linewidth=2, label='2024 Cumulative')
    ax2.plot(days_2025, np.cumsum(precip_2025_daily), 'r-', linewidth=2, label='2025 Cumulative')
    ax2.set_ylabel('Cumulative\nPrecipitation (mm)', fontsize=11)
    ax2.legend(loc='upper left', fontsize=10)
    ax2.grid(True, alpha=0.3)

    # 5日移動平均
    ax3 = axes[2]
    ma5_2024 = np.convolve(precip_2024_daily, np.ones(5)/5, mode='valid')
    ma5_2025 = np.convolve(precip_2025_daily, np.ones(5)/5, mode='valid')
    ax3.plot(days_2024[2:-2], ma5_2024, 'b-', linewidth=2, label='2024 (5-day MA)')
    ax3.plot(days_2025[2:-2], ma5_2025, 'r-', linewidth=2, label='2025 (5-day MA)')
    ax3.set_ylabel('5-day Moving\nAverage (mm)', fontsize=11)
    ax3.set_xlabel('Days since June 1', fontsize=11)
    ax3.legend(loc='upper right', fontsize=10)
    ax3.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig('ezo_tsuyu_analysis_2024_vs_2025.png', dpi=150, bbox_inches='tight')
    print("  Saved: ezo_tsuyu_analysis_2024_vs_2025.png")
    plt.close()

    # 結果保存
    output = {
        'analysis_date': datetime.now().isoformat(),
        'precipitation_2024': {
            'total_mm': float(np.sum(precip_2024_daily)),
            'mean_daily_mm': float(np.mean(precip_2024_daily)),
            'rainy_days': int(np.sum(precip_2024_daily > 1.0)),
            'max_daily_mm': float(np.max(precip_2024_daily))
        },
        'precipitation_2025': {
            'total_mm': float(np.sum(precip_2025_daily)),
            'mean_daily_mm': float(np.mean(precip_2025_daily)),
            'rainy_days': int(np.sum(precip_2025_daily > 1.0)),
            'max_daily_mm': float(np.max(precip_2025_daily))
        },
        'ezo_tsuyu_periods_2024': [
            {
                'start': str(dates_2024[p['start']]),
                'end': str(dates_2024[p['end']]),
                'duration_days': int(p['duration']),
                'total_mm': float(np.sum(precip_2024_daily[p['start']:p['end']+1]))
            }
            for p in long_rain_2024
        ],
        'ezo_tsuyu_periods_2025': [
            {
                'start': str(dates_2025[p['start']]),
                'end': str(dates_2025[p['end']]),
                'duration_days': int(p['duration']),
                'total_mm': float(np.sum(precip_2025_daily[p['start']:p['end']+1]))
            }
            for p in long_rain_2025
        ],
        'conclusion': f"2025 shows {len(long_rain_2025)} Ezo Tsuyu periods vs {len(long_rain_2024)} in 2024. " +
                     f"Total precipitation increased by {np.sum(precip_2025_daily) - np.sum(precip_2024_daily):.1f} mm."
    }

    with open('ezo_tsuyu_analysis_results.json', 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print("  Saved: ezo_tsuyu_analysis_results.json")

    print(f"\n{'='*70}")
    print("ANALYSIS COMPLETE")
    print(f"{'='*70}")

    return output

if __name__ == '__main__':
    analyze_ezo_tsuyu()
