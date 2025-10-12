#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
2024年 vs 2025年 海面水温比較解析

年間変化・温暖化トレンドの検証:
- 同時期（6-8月）の日別SST比較
- 平均気温差の計算
- 温暖化の実態検証
- 昆布漁業への影響評価
"""

import xarray as xr
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime
import json

KUTSUGATA_LAT = 45.2422
KUTSUGATA_LON = 141.1088

def compare_sst_2024_vs_2025():
    """2024年と2025年のSST比較"""

    print("="*70)
    print("SST COMPARISON: 2024 vs 2025")
    print("="*70)

    # データ読み込み
    try:
        ds_2024 = xr.open_dataset('era5_rishiri_ocean_summer2024.nc')
        ds_2025 = xr.open_dataset('era5_rishiri_ocean_summer2025.nc')
        print("\nLoaded both datasets successfully")
    except FileNotFoundError as e:
        print(f"\nError: {e}")
        print("Please run fetch_era5_ocean_data_2024.py and fetch_era5_ocean_data_2025.py first")
        return

    # 変数名特定
    sst_var_2024 = 'sst' if 'sst' in ds_2024 else 'sea_surface_temperature'
    sst_var_2025 = 'sst' if 'sst' in ds_2025 else 'sea_surface_temperature'

    t2m_var_2024 = 't2m' if 't2m' in ds_2024 else '2m_temperature'
    t2m_var_2025 = 't2m' if 't2m' in ds_2025 else '2m_temperature'

    # データ抽出
    sst_2024 = ds_2024[sst_var_2024]
    sst_2025 = ds_2025[sst_var_2025]
    t2m_2024 = ds_2024[t2m_var_2024]
    t2m_2025 = ds_2025[t2m_var_2025]

    lat_2024 = ds_2024.latitude.values
    lon_2024 = ds_2024.longitude.values
    lat_2025 = ds_2025.latitude.values
    lon_2025 = ds_2025.longitude.values

    # 沓形地点
    lat_idx_2024 = np.abs(lat_2024 - KUTSUGATA_LAT).argmin()
    lon_idx_2024 = np.abs(lon_2024 - KUTSUGATA_LON).argmin()
    lat_idx_2025 = np.abs(lat_2025 - KUTSUGATA_LAT).argmin()
    lon_idx_2025 = np.abs(lon_2025 - KUTSUGATA_LON).argmin()

    print(f"\nAnalysis point: Kutsugata ({KUTSUGATA_LAT:.2f}N, {KUTSUGATA_LON:.2f}E)")

    # 時系列データ
    sst_2024_values = []
    sst_2025_values = []
    t2m_2024_values = []
    t2m_2025_values = []

    n_days = min(len(ds_2024.valid_time), len(ds_2025.valid_time))
    print(f"\nComparing {n_days} days")

    for t in range(n_days):
        sst_24 = sst_2024.isel(valid_time=t, latitude=lat_idx_2024, longitude=lon_idx_2024).values - 273.15
        sst_25 = sst_2025.isel(valid_time=t, latitude=lat_idx_2025, longitude=lon_idx_2025).values - 273.15
        t2m_24 = t2m_2024.isel(valid_time=t, latitude=lat_idx_2024, longitude=lon_idx_2024).values - 273.15
        t2m_25 = t2m_2025.isel(valid_time=t, latitude=lat_idx_2025, longitude=lon_idx_2025).values - 273.15

        sst_2024_values.append(sst_24)
        sst_2025_values.append(sst_25)
        t2m_2024_values.append(t2m_24)
        t2m_2025_values.append(t2m_25)

    sst_2024_values = np.array(sst_2024_values)
    sst_2025_values = np.array(sst_2025_values)
    t2m_2024_values = np.array(t2m_2024_values)
    t2m_2025_values = np.array(t2m_2025_values)

    # 差分計算
    sst_diff = sst_2025_values - sst_2024_values
    t2m_diff = t2m_2025_values - t2m_2024_values

    # 統計
    print(f"\n{'='*70}")
    print("STATISTICAL COMPARISON")
    print(f"{'='*70}")

    print(f"\n2024 SST:")
    print(f"  Mean:   {np.mean(sst_2024_values):.2f} C")
    print(f"  Std:    {np.std(sst_2024_values):.2f} C")
    print(f"  Min:    {np.min(sst_2024_values):.2f} C")
    print(f"  Max:    {np.max(sst_2024_values):.2f} C")

    print(f"\n2025 SST:")
    print(f"  Mean:   {np.mean(sst_2025_values):.2f} C")
    print(f"  Std:    {np.std(sst_2025_values):.2f} C")
    print(f"  Min:    {np.min(sst_2025_values):.2f} C")
    print(f"  Max:    {np.max(sst_2025_values):.2f} C")

    print(f"\nYear-over-Year Change (2025 - 2024):")
    print(f"  Mean SST difference:   {np.mean(sst_diff):+.2f} C")
    print(f"  Std of difference:     {np.std(sst_diff):.2f} C")
    print(f"  Max warming:           {np.max(sst_diff):+.2f} C")
    print(f"  Max cooling:           {np.min(sst_diff):+.2f} C")

    print(f"\n2m Air Temperature Change:")
    print(f"  Mean T2m difference:   {np.mean(t2m_diff):+.2f} C")

    # 月別比較
    print(f"\n{'='*70}")
    print("MONTHLY BREAKDOWN")
    print(f"{'='*70}")

    # June (days 0-29)
    june_sst_diff = np.mean(sst_diff[0:30])
    print(f"\nJune (30 days):")
    print(f"  Mean SST change: {june_sst_diff:+.2f} C")

    # July (days 30-60)
    july_sst_diff = np.mean(sst_diff[30:61])
    print(f"\nJuly (31 days):")
    print(f"  Mean SST change: {july_sst_diff:+.2f} C")

    # August (days 61-91)
    august_sst_diff = np.mean(sst_diff[61:])
    print(f"\nAugust (31 days):")
    print(f"  Mean SST change: {august_sst_diff:+.2f} C")

    # 評価
    print(f"\n{'='*70}")
    print("WARMING ASSESSMENT")
    print(f"{'='*70}")

    mean_warming = np.mean(sst_diff)

    if mean_warming > 2.0:
        print(f"\n[CRITICAL] Extreme warming detected: {mean_warming:+.2f} C")
        print("         This represents significant climate change impact")
    elif mean_warming > 1.0:
        print(f"\n[WARNING] Substantial warming detected: {mean_warming:+.2f} C")
        print("          Notable year-over-year increase")
    elif mean_warming > 0.5:
        print(f"\n[MODERATE] Moderate warming detected: {mean_warming:+.2f} C")
        print("           Consistent with regional warming trend")
    elif mean_warming > 0:
        print(f"\n[SLIGHT] Slight warming: {mean_warming:+.2f} C")
        print("         Within normal variability")
    else:
        print(f"\n[COOLING] Year-over-year cooling: {mean_warming:+.2f} C")

    # 可視化
    print(f"\n{'='*70}")
    print("GENERATING VISUALIZATIONS")
    print(f"{'='*70}")

    fig, axes = plt.subplots(3, 1, figsize=(14, 10), sharex=True)

    days = np.arange(len(sst_2024_values))

    # SST比較
    ax1 = axes[0]
    ax1.plot(days, sst_2024_values, 'b-', linewidth=2, label='2024 SST', alpha=0.7)
    ax1.plot(days, sst_2025_values, 'r-', linewidth=2, label='2025 SST', alpha=0.7)
    ax1.set_ylabel('SST (C)', fontsize=11)
    ax1.set_title('Sea Surface Temperature Comparison: 2024 vs 2025 (Kutsugata)',
                 fontsize=14, fontweight='bold')
    ax1.legend(loc='upper left', fontsize=10)
    ax1.grid(True, alpha=0.3)

    # 差分
    ax2 = axes[1]
    ax2.plot(days, sst_diff, 'purple', linewidth=2, label='SST Difference (2025 - 2024)')
    ax2.axhline(0, color='black', linestyle='--', alpha=0.5)
    ax2.axhline(np.mean(sst_diff), color='red', linestyle='--', linewidth=2,
               label=f'Mean: {np.mean(sst_diff):+.2f} C')
    ax2.set_ylabel('Temperature\nDifference (C)', fontsize=11)
    ax2.legend(loc='upper left', fontsize=10)
    ax2.grid(True, alpha=0.3)

    # 2m気温差分
    ax3 = axes[2]
    ax3.plot(days, t2m_diff, 'green', linewidth=2, label='Air Temp Difference (2025 - 2024)')
    ax3.axhline(0, color='black', linestyle='--', alpha=0.5)
    ax3.axhline(np.mean(t2m_diff), color='red', linestyle='--', linewidth=2,
               label=f'Mean: {np.mean(t2m_diff):+.2f} C')
    ax3.set_ylabel('Temperature\nDifference (C)', fontsize=11)
    ax3.set_xlabel('Days since June 1', fontsize=11)
    ax3.legend(loc='upper left', fontsize=10)
    ax3.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig('sst_comparison_2024_vs_2025.png', dpi=150, bbox_inches='tight')
    print("  Saved: sst_comparison_2024_vs_2025.png")
    plt.close()

    # 結果保存
    output = {
        'analysis_date': datetime.now().isoformat(),
        'comparison_period': 'June 1 - August 31',
        'n_days': int(n_days),
        'sst_2024_statistics': {
            'mean_C': float(np.mean(sst_2024_values)),
            'std_C': float(np.std(sst_2024_values)),
            'min_C': float(np.min(sst_2024_values)),
            'max_C': float(np.max(sst_2024_values))
        },
        'sst_2025_statistics': {
            'mean_C': float(np.mean(sst_2025_values)),
            'std_C': float(np.std(sst_2025_values)),
            'min_C': float(np.min(sst_2025_values)),
            'max_C': float(np.max(sst_2025_values))
        },
        'year_over_year_change': {
            'mean_sst_diff_C': float(np.mean(sst_diff)),
            'std_sst_diff_C': float(np.std(sst_diff)),
            'max_warming_C': float(np.max(sst_diff)),
            'max_cooling_C': float(np.min(sst_diff)),
            'june_mean_diff_C': float(june_sst_diff),
            'july_mean_diff_C': float(july_sst_diff),
            'august_mean_diff_C': float(august_sst_diff)
        },
        'conclusion': f"Year-over-year SST change: {np.mean(sst_diff):+.2f} C. " +
                     ("Significant warming detected." if mean_warming > 1.0 else
                      "Moderate warming trend." if mean_warming > 0.5 else
                      "Within normal variability.")
    }

    with open('sst_comparison_2024_vs_2025_results.json', 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print("  Saved: sst_comparison_2024_vs_2025_results.json")

    print(f"\n{'='*70}")
    print("ANALYSIS COMPLETE")
    print(f"{'='*70}")

    return output

if __name__ == '__main__':
    compare_sst_2024_vs_2025()
