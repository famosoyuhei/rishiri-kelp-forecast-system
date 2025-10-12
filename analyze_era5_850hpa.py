#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ERA5 850hPa解析

地形性効果が顕著な850hPa（約1500m、利尻山直下）の解析:
- 風向・風速との相関
- 温度場（海陸温度差）
- 利尻山周辺の気流パターン
"""

import xarray as xr
import numpy as np
import matplotlib.pyplot as plt
import cartopy.crs as ccrs
import cartopy.feature as cfeature
from datetime import datetime
import json
import math

# 利尻山・沓形の座標
RISHIRI_SAN_LAT = 45.1821
RISHIRI_SAN_LON = 141.2421
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

def analyze_850hpa():
    """850hPa解析メイン"""

    print("="*70)
    print("ERA5 850hPa ANALYSIS - TERRAIN EFFECTS")
    print("="*70)

    # データ読み込み
    try:
        ds = xr.open_dataset('era5_rishiri_august2024.nc')
    except FileNotFoundError:
        print("\nError: era5_rishiri_august2024.nc not found")
        return

    # 850hPa抽出
    print("\nExtracting 850hPa data...")
    ds_850 = ds.sel(pressure_level=850)

    u_850 = ds_850['u']
    v_850 = ds_850['v']
    t_850 = ds_850['t']  # 温度

    lat = ds_850.latitude.values
    lon = ds_850.longitude.values

    # 沓形地点データ
    mountain_azimuth = calculate_mountain_azimuth(KUTSUGATA_LAT, KUTSUGATA_LON)
    print(f"\nKutsugata location: {KUTSUGATA_LAT:.2f}N, {KUTSUGATA_LON:.2f}E")
    print(f"Mountain azimuth: {mountain_azimuth:.1f}deg")

    # 最近傍グリッド
    lat_idx = np.abs(lat - KUTSUGATA_LAT).argmin()
    lon_idx = np.abs(lon - KUTSUGATA_LON).argmin()

    print(f"Nearest grid: lat={lat[lat_idx]:.2f}, lon={lon[lon_idx]:.2f}")

    # 時系列データ収集
    all_cos = []
    all_wind_speed = []
    all_temperature = []
    all_u = []
    all_v = []

    n_times = len(ds_850.valid_time)
    print(f"\nProcessing {n_times} timesteps...")

    for t in range(n_times):
        # 850hPa風速成分
        u_t = u_850.isel(valid_time=t, latitude=lat_idx, longitude=lon_idx).values
        v_t = v_850.isel(valid_time=t, latitude=lat_idx, longitude=lon_idx).values
        temp_t = t_850.isel(valid_time=t, latitude=lat_idx, longitude=lon_idx).values

        # 風向計算（気象風向）
        wind_dir = (np.degrees(np.arctan2(-u_t, -v_t)) + 360) % 360
        wind_speed = np.sqrt(u_t**2 + v_t**2)

        # 風向-山角度差
        wind_toward = (wind_dir + 180) % 360
        angle_diff = abs(wind_toward - mountain_azimuth)
        if angle_diff > 180:
            angle_diff = 360 - angle_diff
        cos_angle = math.cos(math.radians(angle_diff))

        all_cos.append(cos_angle)
        all_wind_speed.append(wind_speed)
        all_temperature.append(temp_t - 273.15)  # K→℃
        all_u.append(u_t)
        all_v.append(v_t)

    # 配列化
    cos_vals = np.array(all_cos)
    ws_vals = np.array(all_wind_speed)
    temp_vals = np.array(all_temperature)
    u_vals = np.array(all_u)
    v_vals = np.array(all_v)

    # 相関計算
    corr_cos_ws = np.corrcoef(cos_vals, ws_vals)[0, 1]
    corr_cos_temp = np.corrcoef(cos_vals, temp_vals)[0, 1]

    # 結果表示
    print(f"\n{'='*70}")
    print("850hPa CORRELATION RESULTS")
    print(f"{'='*70}")

    print(f"\nCorrelation with cos(angle):")
    print(f"  Wind Speed:   r = {corr_cos_ws:+.3f}")
    print(f"  Temperature:  r = {corr_cos_temp:+.3f}")

    print(f"\nStatistics:")
    print(f"  cos(angle):    mean={np.mean(cos_vals):+.3f}, std={np.std(cos_vals):.3f}")
    print(f"  Wind Speed:    mean={np.mean(ws_vals):.2f} m/s, std={np.std(ws_vals):.2f}")
    print(f"  Temperature:   mean={np.mean(temp_vals):.1f}°C, std={np.std(temp_vals):.1f}")

    # 比較用：500hPa, 700hPa結果を読み込み
    try:
        with open('era5_contour_correlation_results.json', 'r', encoding='utf-8') as f:
            era5_results = json.load(f)

        print(f"\n{'='*70}")
        print("COMPARISON: 850hPa vs 500/700hPa")
        print(f"{'='*70}")

        print(f"\nCorrelation with cos(angle):")
        print(f"  850hPa Wind Speed:  r = {corr_cos_ws:+.3f}")
        print(f"  500hPa Vorticity:   r = {era5_results['correlations']['cos_angle_vs_vorticity_500hPa_spatial']:+.3f}")
        print(f"  700hPa Omega:       r = {era5_results['correlations']['cos_angle_vs_omega_700hPa']:+.3f}")

    except:
        pass

    # 結果保存
    output = {
        'timestamp': datetime.now().isoformat(),
        'method': 'ERA5 850hPa terrain analysis',
        'location': 'Kutsugata (West side)',
        'n_samples': len(cos_vals),
        'correlations': {
            'cos_angle_vs_wind_speed_850hPa': float(corr_cos_ws),
            'cos_angle_vs_temperature_850hPa': float(corr_cos_temp)
        },
        'statistics': {
            'cos_angle': {
                'mean': float(np.mean(cos_vals)),
                'std': float(np.std(cos_vals))
            },
            'wind_speed_850hPa': {
                'mean': float(np.mean(ws_vals)),
                'std': float(np.std(ws_vals))
            },
            'temperature_850hPa': {
                'mean': float(np.mean(temp_vals)),
                'std': float(np.std(temp_vals))
            }
        }
    }

    with open('era5_850hpa_correlation_results.json', 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\nResults saved to: era5_850hpa_correlation_results.json")

    return output

if __name__ == '__main__':
    analyze_850hpa()
