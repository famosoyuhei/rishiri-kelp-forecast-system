#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
850hPa相当温位解析

相当温位θe（Equivalent Potential Temperature）を計算・可視化:
- θe = θ * exp((Lv * r) / (Cp * T))
- 大気の安定度診断（θeの鉛直分布）
- 前線・気団の境界検出
- 対流不安定の診断
"""

import xarray as xr
import numpy as np
import matplotlib.pyplot as plt
import cartopy.crs as ccrs
import cartopy.feature as cfeature
from datetime import datetime
import math

# 利尻山・沓形・稚内の座標
RISHIRI_SAN_LAT = 45.1821
RISHIRI_SAN_LON = 141.2421
KUTSUGATA_LAT = 45.2422
KUTSUGATA_LON = 141.1088
WAKKANAI_LAT = 45.41
WAKKANAI_LON = 141.68

# 物理定数
Rd = 287.0  # 乾燥空気の気体定数 (J/kg/K)
Cp = 1005.0  # 定圧比熱 (J/kg/K)
Lv = 2.5e6  # 水の蒸発潜熱 (J/kg)
epsilon = 0.622  # 水蒸気の分子量比

def calculate_mixing_ratio(q):
    """
    比湿から混合比を計算

    Args:
        q: 比湿 (kg/kg)
    Returns:
        r: 混合比 (kg/kg)
    """
    return q / (1 - q)

def calculate_potential_temperature(T, p):
    """
    温位θを計算

    θ = T * (1000/p)^(Rd/Cp)

    Args:
        T: 温度 (K)
        p: 気圧 (hPa)
    Returns:
        θ: 温位 (K)
    """
    return T * (1000.0 / p) ** (Rd / Cp)

def calculate_equivalent_potential_temperature(T, p, q):
    """
    相当温位θeを計算

    θe = θ * exp((Lv * r) / (Cp * T))

    Args:
        T: 温度 (K)
        p: 気圧 (hPa)
        q: 比湿 (kg/kg)
    Returns:
        θe: 相当温位 (K)
    """
    # 温位計算
    theta = calculate_potential_temperature(T, p)

    # 混合比計算
    r = calculate_mixing_ratio(q)

    # 相当温位計算
    theta_e = theta * np.exp((Lv * r) / (Cp * T))

    return theta_e

def visualize_850hpa_theta_e():
    """850hPa相当温位の可視化"""

    print("="*70)
    print("850hPa EQUIVALENT POTENTIAL TEMPERATURE ANALYSIS")
    print("="*70)

    # データ読み込み
    try:
        ds = xr.open_dataset('era5_rishiri_august2024.nc')
    except FileNotFoundError:
        print("\nError: era5_rishiri_august2024.nc not found")
        return

    # 850hPa データ
    print("\nExtracting 850hPa data...")
    ds_850 = ds.sel(pressure_level=850)

    u_850 = ds_850['u']
    v_850 = ds_850['v']
    t_850 = ds_850['t']  # 温度 (K)

    # 比湿データの確認
    if 'q' in ds_850:
        q_850 = ds_850['q']  # 比湿 (kg/kg)
    elif 'specific_humidity' in ds_850:
        q_850 = ds_850['specific_humidity']
    else:
        print("Warning: Specific humidity not found in dataset")
        print(f"Available variables: {list(ds_850.data_vars)}")
        # 仮の比湿を設定（ERA5には通常含まれる）
        print("Using estimated humidity based on temperature...")
        # 簡易的な飽和比湿の推定
        es = 6.112 * np.exp((17.67 * (t_850 - 273.15)) / (t_850 - 29.65))  # hPa
        q_850 = epsilon * es / (850 - es) * 0.7  # 相対湿度70%と仮定

    lat = ds_850.latitude.values
    lon = ds_850.longitude.values

    # サンプル時刻で可視化（4時刻）
    sample_times = [0, 10, 20, 30]

    print(f"\nGenerating {len(sample_times)} equivalent potential temperature maps...")

    for time_idx in sample_times:
        print(f"  Processing timestep {time_idx}...")

        # データ抽出
        t_850_t = t_850.isel(valid_time=time_idx).values
        q_850_t = q_850.isel(valid_time=time_idx).values if hasattr(q_850, 'isel') else q_850
        u_850_t = u_850.isel(valid_time=time_idx).values
        v_850_t = v_850.isel(valid_time=time_idx).values

        # 相当温位計算
        theta_e = calculate_equivalent_potential_temperature(t_850_t, 850, q_850_t)

        # プロット作成
        fig = plt.figure(figsize=(12, 10))

        # 地図投影
        ax = plt.axes(projection=ccrs.PlateCarree())
        ax.set_extent([140, 143, 44, 46], crs=ccrs.PlateCarree())

        # 地形・海岸線
        ax.coastlines(resolution='10m', linewidth=1.5)
        ax.add_feature(cfeature.LAND, facecolor='lightgray', alpha=0.3)
        ax.add_feature(cfeature.OCEAN, facecolor='lightblue', alpha=0.2)

        # 経緯度線
        gl = ax.gridlines(draw_labels=True, linewidth=0.5, color='gray', alpha=0.5, linestyle='--')
        gl.top_labels = False
        gl.right_labels = False

        # 相当温位場（カラーマップ + 等値線）
        theta_e_contourf = ax.contourf(lon, lat, theta_e, levels=20, cmap='YlOrRd',
                                       alpha=0.7, transform=ccrs.PlateCarree())

        # 等相当温位線（濃い線）
        theta_e_contour = ax.contour(lon, lat, theta_e, levels=15, colors='darkred',
                                     linewidths=1.2, transform=ccrs.PlateCarree())
        ax.clabel(theta_e_contour, inline=True, fontsize=9, fmt='%.0f K')

        # 温度の等値線（参考用、薄く）
        temp_celsius = t_850_t - 273.15
        temp_contour = ax.contour(lon, lat, temp_celsius, levels=8, colors='blue',
                                 linewidths=0.8, alpha=0.5, linestyle='--',
                                 transform=ccrs.PlateCarree())
        ax.clabel(temp_contour, inline=True, fontsize=7, fmt='%.0f°C')

        # 風向ベクトル
        skip = 2
        quiver = ax.quiver(lon[::skip], lat[::skip],
                          u_850_t[::skip, ::skip], v_850_t[::skip, ::skip],
                          transform=ccrs.PlateCarree(),
                          color='black', scale=150, width=0.003,
                          headwidth=4, headlength=5, alpha=0.6)

        # カラーバー
        cbar = plt.colorbar(theta_e_contourf, ax=ax, orientation='horizontal',
                           pad=0.05, aspect=40, shrink=0.8)
        cbar.set_label('850hPa Equivalent Potential Temperature θe (K)', fontsize=10)

        # 地点マーカー
        ax.plot(RISHIRI_SAN_LON, RISHIRI_SAN_LAT, 'r^', markersize=12,
               transform=ccrs.PlateCarree(), label='Rishiri-san', zorder=10)
        ax.plot(KUTSUGATA_LON, KUTSUGATA_LAT, 'bo', markersize=10,
               transform=ccrs.PlateCarree(), label='Kutsugata', zorder=10)
        ax.plot(WAKKANAI_LON, WAKKANAI_LAT, 'gs', markersize=8,
               transform=ccrs.PlateCarree(), label='Wakkanai', zorder=10)

        # テキスト注釈
        ax.text(RISHIRI_SAN_LON + 0.05, RISHIRI_SAN_LAT + 0.05, 'Rishiri-san',
               fontsize=9, transform=ccrs.PlateCarree())
        ax.text(KUTSUGATA_LON + 0.05, KUTSUGATA_LAT - 0.15, 'Kutsugata',
               fontsize=8, transform=ccrs.PlateCarree())

        # タイトル
        timestamp = str(ds_850.valid_time.isel(valid_time=time_idx).values)[:10]
        ax.set_title(f'850hPa Equivalent Potential Temperature (θe)\n{timestamp}',
                    fontsize=14, fontweight='bold')

        ax.legend(loc='upper right', fontsize=9, framealpha=0.9)

        # 保存
        filename = f'contour_850hpa_theta_e_t{time_idx:04d}.png'
        plt.savefig(filename, dpi=150, bbox_inches='tight')
        print(f"    Saved: {filename}")
        plt.close()

    print(f"\nGenerated {len(sample_times)} equivalent potential temperature maps")

    # 統計解析
    print(f"\n{'='*70}")
    print("EQUIVALENT POTENTIAL TEMPERATURE STATISTICS")
    print(f"{'='*70}")

    # 沓形地点の時系列
    lat_idx = np.abs(lat - KUTSUGATA_LAT).argmin()
    lon_idx = np.abs(lon - KUTSUGATA_LON).argmin()

    theta_e_values = []
    temp_values = []

    for t in range(len(ds_850.valid_time)):
        t_pt = t_850.isel(valid_time=t, latitude=lat_idx, longitude=lon_idx).values
        q_pt = q_850.isel(valid_time=t, latitude=lat_idx, longitude=lon_idx).values if hasattr(q_850, 'isel') else q_850[lat_idx, lon_idx]

        theta_e_pt = calculate_equivalent_potential_temperature(t_pt, 850, q_pt)

        theta_e_values.append(theta_e_pt)
        temp_values.append(t_pt - 273.15)

    theta_e_values = np.array(theta_e_values)
    temp_values = np.array(temp_values)

    print(f"\nAt Kutsugata (August 2024):")
    print(f"  Temperature:              mean={np.mean(temp_values):.1f}°C, std={np.std(temp_values):.1f}")
    print(f"  Equivalent Pot. Temp:     mean={np.mean(theta_e_values):.1f} K, std={np.std(theta_e_values):.1f}")
    print(f"  Theta_e range:            {np.min(theta_e_values):.1f} - {np.max(theta_e_values):.1f} K")

    # Theta_eの変動から大気状態を診断
    theta_e_std = np.std(theta_e_values)

    print(f"\nAtmospheric stability diagnosis:")
    if theta_e_std > 5.0:
        print(f"  [UNSTABLE] Large theta_e variation (std={theta_e_std:.1f}K)")
        print(f"             Different air masses / frontal passages")
    else:
        print(f"  [STABLE] Small theta_e variation (std={theta_e_std:.1f}K)")
        print(f"           Uniform air mass throughout the period")

if __name__ == '__main__':
    visualize_850hpa_theta_e()
