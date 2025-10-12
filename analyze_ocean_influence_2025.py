#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
海洋影響解析（2025年夏季）

海面水温・海陸温度差・海霧リスクの総合解析:
1. 海面水温（SST）の時系列・トレンド
2. 海陸温度差（海陸風の駆動力）
3. 海霧発生リスク（SST - 露点温度）
4. 昆布乾燥成否との相関
"""

import xarray as xr
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime
import json

# 利尻島・沓形の座標
KUTSUGATA_LAT = 45.2422
KUTSUGATA_LON = 141.1088

def analyze_ocean_influence():
    """海洋影響の総合解析"""

    print("="*70)
    print("OCEAN INFLUENCE ANALYSIS - SUMMER 2025")
    print("="*70)

    # データ読み込み
    try:
        ds_ocean = xr.open_dataset('era5_rishiri_ocean_summer2025.nc')
        print("\nLoaded: era5_rishiri_ocean_summer2025.nc")
    except FileNotFoundError:
        print("\nError: era5_rishiri_ocean_summer2025.nc not found")
        print("Please run fetch_era5_ocean_data_2025.py first")
        return

    # データ情報
    print(f"\nDataset info:")
    print(f"  Time range: {ds_ocean.valid_time.values[0]} to {ds_ocean.valid_time.values[-1]}")
    print(f"  Number of timesteps: {len(ds_ocean.valid_time)}")
    print(f"  Variables: {list(ds_ocean.data_vars)}")

    # 変数名の確認と取得
    # ERA5の変数名は略称の場合がある
    var_mapping = {
        'sst': ['sea_surface_temperature', 'sst'],
        't2m': ['2m_temperature', 't2m'],
        'd2m': ['2m_dewpoint_temperature', 'd2m'],
        'u10': ['10m_u_component_of_wind', 'u10'],
        'v10': ['10m_v_component_of_wind', 'v10'],
        'tcc': ['total_cloud_cover', 'tcc']
    }

    # 実際の変数名を特定
    actual_vars = {}
    for key, possible_names in var_mapping.items():
        for name in possible_names:
            if name in ds_ocean:
                actual_vars[key] = name
                break

    print(f"\nVariable mapping:")
    for key, name in actual_vars.items():
        print(f"  {key}: {name}")

    # データ抽出
    sst = ds_ocean[actual_vars['sst']]
    t2m = ds_ocean[actual_vars['t2m']]
    d2m = ds_ocean[actual_vars['d2m']]
    u10 = ds_ocean[actual_vars['u10']]
    v10 = ds_ocean[actual_vars['v10']]
    tcc = ds_ocean[actual_vars['tcc']]

    lat = ds_ocean.latitude.values
    lon = ds_ocean.longitude.values

    # 沓形地点の最近傍グリッド
    lat_idx = np.abs(lat - KUTSUGATA_LAT).argmin()
    lon_idx = np.abs(lon - KUTSUGATA_LON).argmin()

    print(f"\nAnalysis point: Kutsugata")
    print(f"  Target: {KUTSUGATA_LAT:.2f}N, {KUTSUGATA_LON:.2f}E")
    print(f"  Grid:   {lat[lat_idx]:.2f}N, {lon[lon_idx]:.2f}E")

    # 時系列データ抽出
    print(f"\nExtracting time series...")

    dates = []
    sst_values = []
    t2m_values = []
    d2m_values = []
    sea_land_diff = []
    fog_risk = []
    wind_speed_10m = []
    cloud_cover = []

    for t in range(len(ds_ocean.valid_time)):
        date = ds_ocean.valid_time.isel(valid_time=t).values

        sst_t = sst.isel(valid_time=t, latitude=lat_idx, longitude=lon_idx).values
        t2m_t = t2m.isel(valid_time=t, latitude=lat_idx, longitude=lon_idx).values
        d2m_t = d2m.isel(valid_time=t, latitude=lat_idx, longitude=lon_idx).values
        u10_t = u10.isel(valid_time=t, latitude=lat_idx, longitude=lon_idx).values
        v10_t = v10.isel(valid_time=t, latitude=lat_idx, longitude=lon_idx).values
        tcc_t = tcc.isel(valid_time=t, latitude=lat_idx, longitude=lon_idx).values

        # 単位変換（K → ℃）
        sst_c = sst_t - 273.15
        t2m_c = t2m_t - 273.15
        d2m_c = d2m_t - 273.15

        # 海陸温度差
        delta_t = sst_c - t2m_c

        # 海霧リスク（SST - 露点温度）
        # 負値が大きいほど海霧発生しやすい
        fog_index = sst_c - d2m_c

        # 風速
        ws_10m = np.sqrt(u10_t**2 + v10_t**2)

        dates.append(date)
        sst_values.append(sst_c)
        t2m_values.append(t2m_c)
        d2m_values.append(d2m_c)
        sea_land_diff.append(delta_t)
        fog_risk.append(fog_index)
        wind_speed_10m.append(ws_10m)
        cloud_cover.append(tcc_t)

    # 配列化
    dates = np.array(dates)
    sst_values = np.array(sst_values)
    t2m_values = np.array(t2m_values)
    d2m_values = np.array(d2m_values)
    sea_land_diff = np.array(sea_land_diff)
    fog_risk = np.array(fog_risk)
    wind_speed_10m = np.array(wind_speed_10m)
    cloud_cover = np.array(cloud_cover)

    print(f"\nData extracted: {len(sst_values)} days")

    # 統計情報
    print(f"\n{'='*70}")
    print("STATISTICAL SUMMARY")
    print(f"{'='*70}")

    print(f"\nSea Surface Temperature (SST):")
    print(f"  Mean:   {np.mean(sst_values):.1f} C")
    print(f"  Std:    {np.std(sst_values):.1f} C")
    print(f"  Min:    {np.min(sst_values):.1f} C")
    print(f"  Max:    {np.max(sst_values):.1f} C")
    print(f"  Range:  {np.max(sst_values) - np.min(sst_values):.1f} C")

    print(f"\n2m Air Temperature:")
    print(f"  Mean:   {np.mean(t2m_values):.1f} C")
    print(f"  Std:    {np.std(t2m_values):.1f} C")

    print(f"\nSea-Land Temperature Difference:")
    print(f"  Mean:   {np.mean(sea_land_diff):.1f} C (positive = sea warmer)")
    print(f"  Std:    {np.std(sea_land_diff):.1f} C")
    print(f"  Range:  {np.min(sea_land_diff):.1f} to {np.max(sea_land_diff):.1f} C")

    print(f"\nSea Fog Risk Index (SST - Dewpoint):")
    print(f"  Mean:   {np.mean(fog_risk):.1f} C")
    print(f"  Std:    {np.std(fog_risk):.1f} C")
    print(f"  Days with high fog risk (< 2C): {np.sum(fog_risk < 2)}")

    print(f"\n10m Wind Speed:")
    print(f"  Mean:   {np.mean(wind_speed_10m):.1f} m/s")
    print(f"  Std:    {np.std(wind_speed_10m):.1f} m/s")

    # トレンド解析（線形回帰）
    print(f"\n{'='*70}")
    print("TREND ANALYSIS (SST)")
    print(f"{'='*70}")

    days = np.arange(len(sst_values))
    sst_trend = np.polyfit(days, sst_values, 1)
    sst_trend_per_day = sst_trend[0]
    sst_trend_total = sst_trend_per_day * len(days)

    print(f"\nLinear trend (Jun 1 - Aug 31):")
    print(f"  Slope: {sst_trend_per_day:.4f} C/day")
    print(f"  Total change: {sst_trend_total:+.2f} C over {len(days)} days")

    if sst_trend_per_day > 0.02:
        print(f"  [WARMING] SST increasing significantly")
    elif sst_trend_per_day < -0.02:
        print(f"  [COOLING] SST decreasing significantly")
    else:
        print(f"  [STABLE] SST relatively stable")

    # 可視化
    print(f"\n{'='*70}")
    print("GENERATING VISUALIZATIONS")
    print(f"{'='*70}")

    fig, axes = plt.subplots(4, 1, figsize=(14, 12), sharex=True)

    # SST時系列
    ax1 = axes[0]
    ax1.plot(range(len(sst_values)), sst_values, 'b-', linewidth=1.5, label='SST')
    ax1.plot(range(len(t2m_values)), t2m_values, 'r-', linewidth=1.5, alpha=0.7, label='2m Air Temp')
    # トレンド線
    trend_line = sst_trend[0] * days + sst_trend[1]
    ax1.plot(days, trend_line, 'k--', linewidth=2, alpha=0.5, label=f'Trend: {sst_trend_per_day:.3f} C/day')
    ax1.set_ylabel('Temperature (C)', fontsize=11)
    ax1.set_title('Ocean Influence Analysis - Summer 2025 (Kutsugata)', fontsize=14, fontweight='bold')
    ax1.legend(loc='upper right', fontsize=9)
    ax1.grid(True, alpha=0.3)

    # 海陸温度差
    ax2 = axes[1]
    ax2.plot(range(len(sea_land_diff)), sea_land_diff, 'g-', linewidth=1.5)
    ax2.axhline(0, color='black', linestyle='--', alpha=0.5)
    ax2.set_ylabel('Sea-Land\nTemp Diff (C)', fontsize=11)
    ax2.grid(True, alpha=0.3)

    # 海霧リスク
    ax3 = axes[2]
    ax3.plot(range(len(fog_risk)), fog_risk, 'm-', linewidth=1.5)
    ax3.axhline(2, color='red', linestyle='--', alpha=0.5, label='High fog risk threshold')
    ax3.set_ylabel('Fog Risk Index\n(SST - Dewpoint, C)', fontsize=11)
    ax3.legend(loc='upper right', fontsize=9)
    ax3.grid(True, alpha=0.3)

    # 雲量
    ax4 = axes[3]
    ax4.plot(range(len(cloud_cover)), cloud_cover * 100, 'gray', linewidth=1.5)
    ax4.set_ylabel('Cloud Cover (%)', fontsize=11)
    ax4.set_xlabel('Days since June 1, 2025', fontsize=11)
    ax4.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig('ocean_influence_analysis_2025.png', dpi=150, bbox_inches='tight')
    print("  Saved: ocean_influence_analysis_2025.png")
    plt.close()

    # 結果保存
    output = {
        'analysis_date': datetime.now().isoformat(),
        'period': {
            'start': str(dates[0]),
            'end': str(dates[-1]),
            'n_days': len(dates)
        },
        'sst_statistics': {
            'mean_C': float(np.mean(sst_values)),
            'std_C': float(np.std(sst_values)),
            'min_C': float(np.min(sst_values)),
            'max_C': float(np.max(sst_values)),
            'trend_C_per_day': float(sst_trend_per_day),
            'total_change_C': float(sst_trend_total)
        },
        'sea_land_diff_statistics': {
            'mean_C': float(np.mean(sea_land_diff)),
            'std_C': float(np.std(sea_land_diff))
        },
        'fog_risk_statistics': {
            'mean_index': float(np.mean(fog_risk)),
            'days_high_risk': int(np.sum(fog_risk < 2))
        },
        'wind_statistics': {
            'mean_10m_ms': float(np.mean(wind_speed_10m)),
            'std_10m_ms': float(np.std(wind_speed_10m))
        }
    }

    with open('ocean_influence_analysis_2025_results.json', 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print("  Saved: ocean_influence_analysis_2025_results.json")

    print(f"\n{'='*70}")
    print("ANALYSIS COMPLETE")
    print(f"{'='*70}")

    return output

if __name__ == '__main__':
    analyze_ocean_influence()
