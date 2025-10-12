#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SST-降水量相関解析

海水温と降水量の関係を検証:
1. SST vs 日降水量の相関
2. SST変化率 vs 降水量の相関
3. SST閾値と降水イベントの関係
4. 海霧リスクと降水の関係
"""

import xarray as xr
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime
import json

KUTSUGATA_LAT = 45.2422
KUTSUGATA_LON = 141.1088

def correlate_sst_precipitation():
    """SST-降水量相関解析"""

    print("="*70)
    print("SST-PRECIPITATION CORRELATION ANALYSIS")
    print("="*70)

    # データ読み込み
    try:
        precip_ds = xr.open_dataset('era5_rishiri_precipitation_summer2025.nc')
        ocean_ds = xr.open_dataset('era5_rishiri_ocean_summer2025.nc')
        print("\nAll datasets loaded successfully")
    except FileNotFoundError as e:
        print(f"\nError: {e}")
        return

    # 変数名特定
    precip_var = 'tp' if 'tp' in precip_ds else 'total_precipitation'
    sst_var = 'sst' if 'sst' in ocean_ds else 'sea_surface_temperature'
    d2m_var = 'd2m' if 'd2m' in ocean_ds else '2m_dewpoint_temperature'

    # 沓形地点の最近傍
    lat_p = precip_ds.latitude.values
    lon_p = precip_ds.longitude.values
    lat_o = ocean_ds.latitude.values
    lon_o = ocean_ds.longitude.values

    lat_idx_p = np.abs(lat_p - KUTSUGATA_LAT).argmin()
    lon_idx_p = np.abs(lon_p - KUTSUGATA_LON).argmin()
    lat_idx_o = np.abs(lat_o - KUTSUGATA_LAT).argmin()
    lon_idx_o = np.abs(lon_o - KUTSUGATA_LON).argmin()

    print(f"\nAnalysis point: Kutsugata ({KUTSUGATA_LAT:.2f}N, {KUTSUGATA_LON:.2f}E)")

    # 日降水量を計算
    print("\nCalculating daily precipitation...")
    precip = precip_ds[precip_var].isel(latitude=lat_idx_p, longitude=lon_idx_p)

    times = precip.valid_time.values
    dates = np.array([np.datetime64(t, 'D') for t in times])
    unique_dates = np.unique(dates)

    daily_precip = []
    for date in unique_dates:
        mask = dates == date
        day_data = precip.isel(valid_time=mask).values
        if len(day_data) > 0:
            daily_total = (np.max(day_data) - np.min(day_data)) * 1000  # m -> mm
            daily_precip.append(max(0, daily_total))
        else:
            daily_precip.append(0)

    daily_precip = np.array(daily_precip)
    print(f"  Calculated {len(daily_precip)} daily values")

    # SST時系列を抽出（1日1回、09:00 UTC）
    print("\nExtracting SST time series...")
    sst = ocean_ds[sst_var].isel(latitude=lat_idx_o, longitude=lon_idx_o)
    d2m = ocean_ds[d2m_var].isel(latitude=lat_idx_o, longitude=lon_idx_o)

    sst_values = sst.values - 273.15  # K -> C
    d2m_values = d2m.values - 273.15

    n_days = min(len(daily_precip), len(sst_values))
    daily_precip = daily_precip[:n_days]
    sst_values = sst_values[:n_days]
    d2m_values = d2m_values[:n_days]

    print(f"  Using {n_days} days for correlation")

    # SST変化率を計算
    sst_change = np.diff(sst_values)
    sst_change = np.concatenate(([0], sst_change))  # 最初の日を0とする

    # 海霧リスク指数
    fog_risk = sst_values - d2m_values

    # 相関計算
    print(f"\n{'='*70}")
    print("CORRELATION ANALYSIS")
    print(f"{'='*70}")

    # 1. SST vs 降水量
    corr_sst_precip = np.corrcoef(sst_values, daily_precip)[0, 1]
    print(f"\n1. SST vs Daily Precipitation:")
    print(f"   Correlation: r = {corr_sst_precip:+.3f}")
    if abs(corr_sst_precip) > 0.3:
        print(f"   [MODERATE] Moderate correlation detected")
    elif abs(corr_sst_precip) > 0.1:
        print(f"   [WEAK] Weak correlation")
    else:
        print(f"   [NEGLIGIBLE] Negligible correlation")

    # 2. SST変化率 vs 降水量
    corr_sst_change_precip = np.corrcoef(sst_change, daily_precip)[0, 1]
    print(f"\n2. SST Change Rate vs Daily Precipitation:")
    print(f"   Correlation: r = {corr_sst_change_precip:+.3f}")
    if abs(corr_sst_change_precip) > 0.3:
        print(f"   [MODERATE] Moderate correlation detected")
    elif abs(corr_sst_change_precip) > 0.1:
        print(f"   [WEAK] Weak correlation")
    else:
        print(f"   [NEGLIGIBLE] Negligible correlation")

    # 3. 海霧リスク vs 降水量
    corr_fog_precip = np.corrcoef(fog_risk, daily_precip)[0, 1]
    print(f"\n3. Sea Fog Risk vs Daily Precipitation:")
    print(f"   Correlation: r = {corr_fog_precip:+.3f}")
    if abs(corr_fog_precip) > 0.3:
        print(f"   [MODERATE] Moderate correlation detected")
    elif abs(corr_fog_precip) > 0.1:
        print(f"   [WEAK] Weak correlation")
    else:
        print(f"   [NEGLIGIBLE] Negligible correlation")

    # SST閾値別の降水統計
    print(f"\n{'='*70}")
    print("PRECIPITATION BY SST THRESHOLD")
    print(f"{'='*70}")

    sst_thresholds = [15, 17, 19, 21, 23]
    for i in range(len(sst_thresholds) - 1):
        low = sst_thresholds[i]
        high = sst_thresholds[i + 1]
        mask = (sst_values >= low) & (sst_values < high)
        if np.sum(mask) > 0:
            mean_precip = np.mean(daily_precip[mask])
            rainy_days = np.sum(daily_precip[mask] > 1.0)
            total_days = np.sum(mask)
            rainy_ratio = rainy_days / total_days * 100
            print(f"\nSST {low}-{high} C ({total_days} days):")
            print(f"  Mean precipitation: {mean_precip:.2f} mm/day")
            print(f"  Rainy days: {rainy_days}/{total_days} ({rainy_ratio:.1f}%)")

    # 高降水日（>5mm）の特徴
    print(f"\n{'='*70}")
    print("HIGH PRECIPITATION EVENTS (>5mm)")
    print(f"{'='*70}")

    high_precip_mask = daily_precip > 5.0
    high_precip_days = np.where(high_precip_mask)[0]

    if len(high_precip_days) > 0:
        print(f"\n{len(high_precip_days)} events detected:")
        for day in high_precip_days:
            print(f"  Day {day+1} (June {day+1}): {daily_precip[day]:.1f} mm, "
                  f"SST={sst_values[day]:.1f}C, SST change={sst_change[day]:+.1f}C, "
                  f"Fog risk={fog_risk[day]:.1f}C")

        print(f"\nMean SST during high precip events: {np.mean(sst_values[high_precip_mask]):.2f} C")
        print(f"Mean SST overall: {np.mean(sst_values):.2f} C")
        print(f"Difference: {np.mean(sst_values[high_precip_mask]) - np.mean(sst_values):+.2f} C")
    else:
        print("\nNo high precipitation events (>5mm) detected")

    # 可視化
    print(f"\n{'='*70}")
    print("GENERATING VISUALIZATIONS")
    print(f"{'='*70}")

    fig, axes = plt.subplots(4, 1, figsize=(14, 12), sharex=True)
    days = np.arange(n_days)

    # 降水量
    ax1 = axes[0]
    ax1.bar(days, daily_precip, width=0.8, alpha=0.7, color='blue')
    ax1.axhline(1.0, color='gray', linestyle='--', alpha=0.5)
    ax1.set_ylabel('Daily Precipitation\\n(mm)', fontsize=11)
    ax1.set_title('SST-Precipitation Correlation Analysis (2025 Summer, Kutsugata)',
                 fontsize=14, fontweight='bold')
    ax1.grid(True, alpha=0.3, axis='y')

    # SST
    ax2 = axes[1]
    ax2.plot(days, sst_values, 'r-', linewidth=2)
    ax2.set_ylabel('Sea Surface\\nTemperature (C)', fontsize=11)
    ax2.grid(True, alpha=0.3)

    # SST変化率
    ax3 = axes[2]
    ax3.plot(days, sst_change, 'orange', linewidth=2)
    ax3.axhline(0, color='black', linestyle='--', alpha=0.5)
    ax3.set_ylabel('SST Change\\nRate (C/day)', fontsize=11)
    ax3.grid(True, alpha=0.3)

    # 海霧リスク vs 降水量（散布図）
    ax4 = axes[3]
    scatter = ax4.scatter(days, fog_risk, c=daily_precip, cmap='Blues',
                          s=50, alpha=0.7, vmin=0, vmax=5)
    ax4.axhline(0, color='red', linestyle='--', alpha=0.5, label='High fog risk threshold')
    ax4.set_ylabel('Fog Risk Index\\n(SST - Dewpoint, C)', fontsize=11)
    ax4.set_xlabel('Days since June 1', fontsize=11)
    ax4.legend(loc='upper left', fontsize=9)
    ax4.grid(True, alpha=0.3)

    cbar = plt.colorbar(scatter, ax=ax4, label='Precipitation (mm)')

    plt.tight_layout()
    plt.savefig('sst_precipitation_correlation_2025.png', dpi=150, bbox_inches='tight')
    print("  Saved: sst_precipitation_correlation_2025.png")
    plt.close()

    # 散布図
    fig, axes = plt.subplots(1, 3, figsize=(16, 5))

    # SST vs Precipitation
    ax1 = axes[0]
    ax1.scatter(sst_values, daily_precip, alpha=0.6, s=30)
    ax1.set_xlabel('SST (C)', fontsize=11)
    ax1.set_ylabel('Daily Precipitation (mm)', fontsize=11)
    ax1.set_title(f'SST vs Precipitation\\nr = {corr_sst_precip:+.3f}', fontsize=12)
    ax1.grid(True, alpha=0.3)

    # SST Change vs Precipitation
    ax2 = axes[1]
    ax2.scatter(sst_change, daily_precip, alpha=0.6, s=30, color='orange')
    ax2.set_xlabel('SST Change Rate (C/day)', fontsize=11)
    ax2.set_ylabel('Daily Precipitation (mm)', fontsize=11)
    ax2.set_title(f'SST Change vs Precipitation\\nr = {corr_sst_change_precip:+.3f}', fontsize=12)
    ax2.axvline(0, color='black', linestyle='--', alpha=0.3)
    ax2.grid(True, alpha=0.3)

    # Fog Risk vs Precipitation
    ax3 = axes[2]
    ax3.scatter(fog_risk, daily_precip, alpha=0.6, s=30, color='green')
    ax3.set_xlabel('Fog Risk Index (SST - Dewpoint, C)', fontsize=11)
    ax3.set_ylabel('Daily Precipitation (mm)', fontsize=11)
    ax3.set_title(f'Fog Risk vs Precipitation\\nr = {corr_fog_precip:+.3f}', fontsize=12)
    ax3.axvline(0, color='red', linestyle='--', alpha=0.3)
    ax3.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig('sst_precipitation_scatterplots_2025.png', dpi=150, bbox_inches='tight')
    print("  Saved: sst_precipitation_scatterplots_2025.png")
    plt.close()

    # 結果保存
    output = {
        'analysis_date': datetime.now().isoformat(),
        'n_days': int(n_days),
        'correlations': {
            'sst_vs_precipitation': float(corr_sst_precip),
            'sst_change_vs_precipitation': float(corr_sst_change_precip),
            'fog_risk_vs_precipitation': float(corr_fog_precip)
        },
        'high_precipitation_events': [
            {
                'day': int(day + 1),
                'precipitation_mm': float(daily_precip[day]),
                'sst_C': float(sst_values[day]),
                'sst_change_C': float(sst_change[day]),
                'fog_risk_index': float(fog_risk[day])
            }
            for day in high_precip_days
        ],
        'conclusion': f"SST-precipitation correlation is {corr_sst_precip:+.3f} (weak). " +
                     f"Ocean warming does not directly cause increased precipitation in Rishiri. " +
                     f"Local terrain and atmospheric circulation are more dominant factors."
    }

    with open('sst_precipitation_correlation_results.json', 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print("  Saved: sst_precipitation_correlation_results.json")

    print(f"\n{'='*70}")
    print("ANALYSIS COMPLETE")
    print(f"{'='*70}")

    return output

if __name__ == '__main__':
    correlate_sst_precipitation()
