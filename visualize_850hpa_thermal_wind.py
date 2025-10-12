#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
850hPa等値線マップ + 温度風解析

温度風の概念を取り入れた解析:
- 850hPa風向ベクトル場
- 850hPa温度場（等温線）
- 温度風（鉛直シアー）の計算: 850hPa-500hPa風速差
- 地形性循環の診断
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

def calculate_thermal_wind(u_lower, v_lower, u_upper, v_upper):
    """
    温度風（鉛直シアー）を計算

    温度風関係式: ∂V/∂p ∝ k × ∇T
    ここでは単純に上層-下層の風速差として計算

    Args:
        u_lower, v_lower: 下層（850hPa）風速成分
        u_upper, v_upper: 上層（500hPa）風速成分
    Returns:
        u_thermal, v_thermal: 温度風成分（鉛直シアー）
    """
    u_thermal = u_upper - u_lower
    v_thermal = v_upper - v_lower
    return u_thermal, v_thermal

def visualize_850hpa_thermal_wind():
    """850hPa風向場・温度場・温度風の可視化"""

    print("="*70)
    print("850hPa WIND FIELD & THERMAL WIND ANALYSIS")
    print("="*70)

    # データ読み込み
    try:
        ds = xr.open_dataset('era5_rishiri_august2024.nc')
    except FileNotFoundError:
        print("\nError: era5_rishiri_august2024.nc not found")
        return

    # 850hPa と 500hPa データ
    print("\nExtracting 850hPa and 500hPa data...")
    ds_850 = ds.sel(pressure_level=850)
    ds_500 = ds.sel(pressure_level=500)

    u_850 = ds_850['u']
    v_850 = ds_850['v']
    t_850 = ds_850['t']  # 温度 (K)

    u_500 = ds_500['u']
    v_500 = ds_500['v']

    lat = ds_850.latitude.values
    lon = ds_850.longitude.values

    # 高度場も取得（等高度線用）
    if 'z' in ds_850:
        z_850 = ds_850['z'] / 9.80665  # geopotential → height (m)
    else:
        z_850 = None

    # サンプル時刻で可視化（4時刻）
    sample_times = [0, 10, 20, 30]

    print(f"\nGenerating {len(sample_times)} contour maps with thermal wind...")

    for time_idx in sample_times:
        print(f"  Processing timestep {time_idx}...")

        # データ抽出
        u_850_t = u_850.isel(valid_time=time_idx).values
        v_850_t = v_850.isel(valid_time=time_idx).values
        t_850_t = t_850.isel(valid_time=time_idx).values - 273.15  # K → ℃

        u_500_t = u_500.isel(valid_time=time_idx).values
        v_500_t = v_500.isel(valid_time=time_idx).values

        # 温度風計算
        u_thermal, v_thermal = calculate_thermal_wind(u_850_t, v_850_t, u_500_t, v_500_t)
        thermal_wind_speed = np.sqrt(u_thermal**2 + v_thermal**2)

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

        # 850hPa 温度場（カラーマップ + 等温線）
        temp_contourf = ax.contourf(lon, lat, t_850_t, levels=15, cmap='RdYlBu_r',
                                     alpha=0.6, transform=ccrs.PlateCarree())
        temp_contour = ax.contour(lon, lat, t_850_t, levels=10, colors='black',
                                  linewidths=0.8, transform=ccrs.PlateCarree())
        ax.clabel(temp_contour, inline=True, fontsize=8, fmt='%.1f°C')

        # 850hPa 高度場（もしあれば）
        if z_850 is not None:
            z_850_t = z_850.isel(valid_time=time_idx).values
            height_contour = ax.contour(lon, lat, z_850_t, levels=10, colors='blue',
                                       linewidths=1.2, alpha=0.7, transform=ccrs.PlateCarree())
            ax.clabel(height_contour, inline=True, fontsize=7, fmt='%.0f m')

        # 850hPa 風向ベクトル（間引いて表示）
        skip = 2  # ベクトルを間引く
        quiver = ax.quiver(lon[::skip], lat[::skip],
                          u_850_t[::skip, ::skip], v_850_t[::skip, ::skip],
                          transform=ccrs.PlateCarree(),
                          color='green', scale=150, width=0.004,
                          headwidth=4, headlength=5, alpha=0.8,
                          label='850hPa Wind')

        # 温度風ベクトル（鉛直シアー）
        thermal_quiver = ax.quiver(lon[::skip], lat[::skip],
                                   u_thermal[::skip, ::skip], v_thermal[::skip, ::skip],
                                   transform=ccrs.PlateCarree(),
                                   color='red', scale=150, width=0.003,
                                   headwidth=3, headlength=4, alpha=0.6,
                                   label='Thermal Wind (850-500hPa shear)')

        # カラーバー
        cbar = plt.colorbar(temp_contourf, ax=ax, orientation='horizontal',
                           pad=0.05, aspect=40, shrink=0.8)
        cbar.set_label('850hPa Temperature (°C)', fontsize=10)

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
        ax.text(WAKKANAI_LON + 0.05, WAKKANAI_LAT + 0.05, 'Wakkanai',
               fontsize=8, transform=ccrs.PlateCarree())

        # タイトル
        timestamp = str(ds_850.valid_time.isel(valid_time=time_idx).values)[:10]
        ax.set_title(f'850hPa Temperature & Wind Field + Thermal Wind\n{timestamp}',
                    fontsize=14, fontweight='bold')

        # 凡例（ベクトルのみ）
        ax.legend(loc='upper right', fontsize=9, framealpha=0.9)

        # 保存
        filename = f'contour_850hpa_thermal_wind_t{time_idx:04d}.png'
        plt.savefig(filename, dpi=150, bbox_inches='tight')
        print(f"    Saved: {filename}")
        plt.close()

    print(f"\nGenerated {len(sample_times)} 850hPa thermal wind maps")

    # 温度風の統計解析
    print(f"\n{'='*70}")
    print("THERMAL WIND STATISTICS")
    print(f"{'='*70}")

    # 沓形地点の温度風を時系列で計算
    lat_idx = np.abs(lat - KUTSUGATA_LAT).argmin()
    lon_idx = np.abs(lon - KUTSUGATA_LON).argmin()

    thermal_wind_speeds = []
    wind_850_speeds = []
    temperatures = []

    for t in range(len(ds_850.valid_time)):
        u_850_pt = u_850.isel(valid_time=t, latitude=lat_idx, longitude=lon_idx).values
        v_850_pt = v_850.isel(valid_time=t, latitude=lat_idx, longitude=lon_idx).values
        u_500_pt = u_500.isel(valid_time=t, latitude=lat_idx, longitude=lon_idx).values
        v_500_pt = v_500.isel(valid_time=t, latitude=lat_idx, longitude=lon_idx).values
        t_850_pt = t_850.isel(valid_time=t, latitude=lat_idx, longitude=lon_idx).values

        u_th, v_th = calculate_thermal_wind(u_850_pt, v_850_pt, u_500_pt, v_500_pt)
        th_speed = np.sqrt(u_th**2 + v_th**2)
        ws_850 = np.sqrt(u_850_pt**2 + v_850_pt**2)

        thermal_wind_speeds.append(th_speed)
        wind_850_speeds.append(ws_850)
        temperatures.append(t_850_pt - 273.15)

    thermal_wind_speeds = np.array(thermal_wind_speeds)
    wind_850_speeds = np.array(wind_850_speeds)
    temperatures = np.array(temperatures)

    print(f"\nAt Kutsugata (August 2024):")
    print(f"  850hPa wind speed:        mean={np.mean(wind_850_speeds):.2f} m/s, std={np.std(wind_850_speeds):.2f}")
    print(f"  Thermal wind (shear):     mean={np.mean(thermal_wind_speeds):.2f} m/s, std={np.std(thermal_wind_speeds):.2f}")
    print(f"  850hPa temperature:       mean={np.mean(temperatures):.1f}°C, std={np.std(temperatures):.1f}")

    # 温度風と850hPa風速の比
    shear_ratio = np.mean(thermal_wind_speeds) / np.mean(wind_850_speeds)
    print(f"\nThermal wind / 850hPa wind ratio: {shear_ratio:.2f}")
    print(f"  -> Vertical shear is {shear_ratio*100:.0f}% of mean wind speed")

    if shear_ratio > 0.5:
        print(f"  [WARNING] Strong vertical shear detected")
        print(f"            850hPa wind may not represent surface wind")
    else:
        print(f"  [OK] Moderate vertical shear")
        print(f"       850hPa wind is representative of surface wind")

if __name__ == '__main__':
    visualize_850hpa_thermal_wind()
