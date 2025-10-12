#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ERA5データ等値線解析

500hPa高度場から空間微分により渦度を計算
700hPa鉛直p速度を取得
風向-山角度差との相関を再計算
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

def load_era5_data(filepath):
    """ERA5 NetCDFデータを読み込み"""
    print(f"Loading ERA5 data from {filepath}...")
    ds = xr.open_dataset(filepath)
    print(f"Dataset loaded successfully")
    print(f"\nDimensions: {dict(ds.dims)}")
    print(f"Variables: {list(ds.data_vars)}")
    return ds

def calculate_vorticity_spatial(u, v, lat, lon):
    """
    空間微分から相対渦度を計算

    ζ = ∂v/∂x - ∂u/∂y

    Args:
        u, v: 風速成分（m/s）
        lat, lon: 緯度・経度グリッド
    Returns:
        vorticity: 相対渦度（10^-5 s^-1）
    """
    # 地球半径
    R = 6371000  # m

    # 緯度・経度をラジアンに変換
    lat_rad = np.deg2rad(lat)
    lon_rad = np.deg2rad(lon)

    # dx, dy を計算（メートル）
    # dy = R * dφ （φ: latitude in radians）
    # dx = R * cos(φ) * dλ （λ: longitude in radians）

    # 中心差分で微分
    dv_dlon = np.gradient(v, axis=-1)  # ∂v/∂λ
    du_dlat = np.gradient(u, axis=-2)  # ∂u/∂φ

    # グリッド間隔
    dlon = np.gradient(lon_rad)
    dlat = np.gradient(lat_rad)

    # メッシュグリッド作成
    if len(lat.shape) == 1:
        lon_grid, lat_grid = np.meshgrid(lon, lat)
        lat_rad_grid = np.deg2rad(lat_grid)
    else:
        lat_rad_grid = lat_rad

    # dx, dy
    dx = R * np.cos(lat_rad_grid) * dlon[None, :]
    dy = R * dlat[:, None]

    # 相対渦度計算
    dv_dx = dv_dlon / dx
    du_dy = du_dlat / dy

    vorticity = dv_dx - du_dy

    # 10^-5 s^-1 単位に変換
    vorticity_scaled = vorticity * 1e5

    return vorticity_scaled

def extract_point_data(ds, lat_target, lon_target, pressure_level):
    """
    指定地点・気圧面のデータを抽出

    Args:
        ds: xarray Dataset
        lat_target, lon_target: 目標地点の座標
        pressure_level: 気圧面（hPa）
    """
    # 最近傍点を探す
    lat_idx = np.abs(ds.latitude.values - lat_target).argmin()
    lon_idx = np.abs(ds.longitude.values - lon_target).argmin()
    lev_idx = np.abs(ds.level.values - pressure_level).argmin()

    # データ抽出
    subset = ds.isel(latitude=lat_idx, longitude=lon_idx, level=lev_idx)

    return subset

def analyze_contours_and_correlation():
    """等値線解析と相関計算"""

    print("="*70)
    print("ERA5 CONTOUR ANALYSIS AND CORRELATION")
    print("="*70)

    # ERA5データ読み込み
    try:
        ds = load_era5_data('era5_rishiri_august2024.nc')
    except FileNotFoundError:
        print("\nError: era5_rishiri_august2024.nc not found")
        print("Please run fetch_era5_data.py first")
        return

    # 500hPa データ抽出
    print("\nExtracting 500hPa data...")
    ds_500 = ds.sel(pressure_level=500)

    # 変数名確認（ERA5では 'z' が geopotential）
    if 'z' in ds_500:
        z_500 = ds_500['z'] / 9.80665  # geopotential → geopotential height (m)
    elif 'geopotential' in ds_500:
        z_500 = ds_500['geopotential'] / 9.80665
    else:
        print(f"Error: Geopotential variable not found. Available: {list(ds_500.data_vars)}")
        return

    u_500 = ds_500['u']
    v_500 = ds_500['v']

    print(f"500hPa geopotential height shape: {z_500.shape}")

    # 700hPa omega（鉛直p速度）
    print("\nExtracting 700hPa omega...")
    ds_700 = ds.sel(pressure_level=700)
    omega_700 = ds_700['w']  # vertical velocity (Pa/s)

    # 時間平均でテスト（1日分）
    print("\nCalculating spatial vorticity for sample timestep...")
    time_idx = 0
    u_sample = u_500.isel(valid_time=time_idx).values
    v_sample = v_500.isel(valid_time=time_idx).values
    lat = ds_500.latitude.values
    lon = ds_500.longitude.values

    # 渦度計算（空間微分）
    vorticity_spatial = calculate_vorticity_spatial(u_sample, v_sample, lat, lon)

    print(f"Vorticity calculated: shape={vorticity_spatial.shape}")
    print(f"  Mean: {np.nanmean(vorticity_spatial):.3f} x10^-5 s^-1")
    print(f"  Std:  {np.nanstd(vorticity_spatial):.3f} x10^-5 s^-1")

    # 沓形地点のデータを時系列で抽出
    print(f"\nExtracting time series at Kutsugata ({KUTSUGATA_LAT:.2f}N, {KUTSUGATA_LON:.2f}E)...")

    mountain_azimuth = calculate_mountain_azimuth(KUTSUGATA_LAT, KUTSUGATA_LON)
    print(f"Mountain azimuth: {mountain_azimuth:.1f}deg")

    # 最近傍グリッド点
    lat_idx = np.abs(lat - KUTSUGATA_LAT).argmin()
    lon_idx = np.abs(lon - KUTSUGATA_LON).argmin()

    print(f"Nearest grid point: lat={lat[lat_idx]:.2f}, lon={lon[lon_idx]:.2f}")

    # 全時刻のデータ収集
    all_cos = []
    all_vorticity_spatial = []
    all_omega = []
    all_dates = []

    n_times = len(ds_500.valid_time)
    print(f"\nProcessing {n_times} timesteps...")

    for t in range(n_times):
        if t % 10 == 0:
            print(f"  Progress: {t}/{n_times}")

        # 500hPa風向
        u_t = u_500.isel(valid_time=t, latitude=lat_idx, longitude=lon_idx).values
        v_t = v_500.isel(valid_time=t, latitude=lat_idx, longitude=lon_idx).values

        wind_dir_500 = (np.degrees(np.arctan2(-u_t, -v_t)) + 360) % 360

        # 風向-山角度差のコサイン
        wind_toward = (wind_dir_500 + 180) % 360
        angle_diff = abs(wind_toward - mountain_azimuth)
        if angle_diff > 180:
            angle_diff = 360 - angle_diff
        cos_angle = math.cos(math.radians(angle_diff))

        # 空間微分による渦度（この時刻）
        u_grid = u_500.isel(valid_time=t).values
        v_grid = v_500.isel(valid_time=t).values
        vort_grid = calculate_vorticity_spatial(u_grid, v_grid, lat, lon)
        vort_point = vort_grid[lat_idx, lon_idx]

        # 700hPa omega
        omega_point = omega_700.isel(valid_time=t, latitude=lat_idx, longitude=lon_idx).values

        if not np.isnan(vort_point) and not np.isnan(omega_point):
            all_cos.append(cos_angle)
            all_vorticity_spatial.append(vort_point)
            all_omega.append(omega_point)
            all_dates.append(str(ds_500.valid_time.isel(valid_time=t).values))

    print(f"\nValid samples: {len(all_cos)}")

    # 相関計算
    cos_vals = np.array(all_cos)
    vort_vals = np.array(all_vorticity_spatial)
    omega_vals = np.array(all_omega)

    corr_cos_vort = np.corrcoef(cos_vals, vort_vals)[0, 1] if len(cos_vals) > 1 else 0
    corr_cos_omega = np.corrcoef(cos_vals, omega_vals)[0, 1] if len(cos_vals) > 1 else 0
    corr_vort_omega = np.corrcoef(vort_vals, omega_vals)[0, 1] if len(cos_vals) > 1 else 0

    # 結果表示
    print(f"\n{'='*70}")
    print("CORRELATION RESULTS (ERA5 SPATIAL ANALYSIS)")
    print(f"{'='*70}")

    print(f"\nCorrelation coefficients:")
    print(f"  cos(angle) vs vorticity_500hPa (spatial): r = {corr_cos_vort:+.3f}")
    print(f"  cos(angle) vs omega_700hPa:               r = {corr_cos_omega:+.3f}")
    print(f"  vorticity_500hPa vs omega_700hPa:         r = {corr_vort_omega:+.3f}")

    print(f"\nStatistics:")
    print(f"  cos(angle):       mean={np.mean(cos_vals):+.3f}, std={np.std(cos_vals):.3f}")
    print(f"  vorticity_500hPa: mean={np.mean(vort_vals):+.3f}, std={np.std(vort_vals):.3f} x10^-5 s^-1")
    print(f"  omega_700hPa:     mean={np.mean(omega_vals):+.6f}, std={np.std(omega_vals):.6f} Pa/s")

    # 比較
    print(f"\n{'='*70}")
    print("COMPARISON: FORECAST vs RADIOSONDE vs ERA5 SPATIAL")
    print(f"{'='*70}")

    try:
        # 予報データ
        with open('temporal_robustness_kutsugata.json', 'r') as f:
            fc_data = json.load(f)
        fc_vort = fc_data['forecast_data']['correlations']['cos_angle_vs_vorticity_500hPa']
        fc_omega = fc_data['forecast_data']['correlations']['cos_angle_vs_omega_700hPa']

        # ラジオゾンデ
        with open('radiosonde_correlation_results.json', 'r') as f:
            rs_data = json.load(f)
        rs_vort = rs_data['correlations']['cos_angle_vs_vorticity_500hPa']
        rs_omega = rs_data['correlations']['cos_angle_vs_omega_700hPa']

        print(f"\ncos(angle) vs vorticity_500hPa:")
        print(f"  Forecast (model):        r = {fc_vort:+.3f}")
        print(f"  Radiosonde (temporal):   r = {rs_vort:+.3f}")
        print(f"  ERA5 (spatial):          r = {corr_cos_vort:+.3f}")

        print(f"\ncos(angle) vs omega_700hPa:")
        print(f"  Forecast (model):        r = {fc_omega:+.3f}")
        print(f"  Radiosonde (temporal):   r = {rs_omega:+.3f}")
        print(f"  ERA5 (spatial):          r = {corr_cos_omega:+.3f}")

    except FileNotFoundError:
        pass

    # 結果保存
    results = {
        'timestamp': datetime.now().isoformat(),
        'method': 'ERA5 spatial derivative analysis',
        'location': 'Kutsugata (West side)',
        'n_samples': len(cos_vals),
        'correlations': {
            'cos_angle_vs_vorticity_500hPa_spatial': float(corr_cos_vort),
            'cos_angle_vs_omega_700hPa': float(corr_cos_omega),
            'vorticity_500hPa_vs_omega_700hPa': float(corr_vort_omega)
        },
        'statistics': {
            'cos_angle': {
                'mean': float(np.mean(cos_vals)),
                'std': float(np.std(cos_vals))
            },
            'vorticity_500hPa_spatial': {
                'mean': float(np.mean(vort_vals)),
                'std': float(np.std(vort_vals))
            },
            'omega_700hPa': {
                'mean': float(np.mean(omega_vals)),
                'std': float(np.std(omega_vals))
            }
        }
    }

    with open('era5_contour_correlation_results.json', 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"\nResults saved to: era5_contour_correlation_results.json")

    return ds, vorticity_spatial

if __name__ == '__main__':
    analyze_contours_and_correlation()
