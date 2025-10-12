#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
等値線マップ可視化

500hPa高度場・渦度の等値線図を作成
"""

import xarray as xr
import numpy as np
import matplotlib.pyplot as plt
import cartopy.crs as ccrs
import cartopy.feature as cfeature
from datetime import datetime
import sys

# 日本語フォント設定（Windows）
plt.rcParams['font.sans-serif'] = ['MS Gothic', 'Yu Gothic', 'Meiryo']
plt.rcParams['axes.unicode_minus'] = False

# 利尻島周辺の重要地点
LOCATIONS = {
    'Rishiri-san': (45.1821, 141.2421),
    'Kutsugata': (45.2422, 141.1088),
    'Wakkanai': (45.41, 141.68)
}

def calculate_vorticity_spatial(u, v, lat, lon):
    """空間微分から相対渦度を計算"""
    R = 6371000
    lat_rad = np.deg2rad(lat)
    lon_rad = np.deg2rad(lon)

    dv_dlon = np.gradient(v, axis=-1)
    du_dlat = np.gradient(u, axis=-2)

    dlon = np.gradient(lon_rad)
    dlat = np.gradient(lat_rad)

    if len(lat.shape) == 1:
        lon_grid, lat_grid = np.meshgrid(lon, lat)
        lat_rad_grid = np.deg2rad(lat_grid)
    else:
        lat_rad_grid = lat_rad

    dx = R * np.cos(lat_rad_grid) * dlon[None, :]
    dy = R * dlat[:, None]

    dv_dx = dv_dlon / dx
    du_dy = du_dlat / dy

    vorticity = (dv_dx - du_dy) * 1e5

    return vorticity

def plot_500hpa_contour(ds, time_idx=0, save_path='contour_500hpa.png'):
    """500hPa高度場・渦度の等値線図を作成"""

    print(f"Creating 500hPa contour map for time index {time_idx}...")

    # データ抽出
    ds_500 = ds.sel(pressure_level=500).isel(valid_time=time_idx)

    if 'z' in ds_500:
        z_500 = ds_500['z'] / 9.80665
    elif 'geopotential' in ds_500:
        z_500 = ds_500['geopotential'] / 9.80665
    else:
        print("Error: Geopotential variable not found")
        return

    u_500 = ds_500['u'].values
    v_500 = ds_500['v'].values
    lat = ds_500.latitude.values
    lon = ds_500.longitude.values

    # 渦度計算
    vorticity = calculate_vorticity_spatial(u_500, v_500, lat, lon)

    # 時刻情報
    time_str = str(ds_500.valid_time.values)[:19]

    # プロット作成
    fig = plt.figure(figsize=(14, 10))
    ax = plt.axes(projection=ccrs.PlateCarree())

    # 地図範囲
    ax.set_extent([140, 143, 44, 46], crs=ccrs.PlateCarree())

    # 海岸線・陸地
    ax.add_feature(cfeature.COASTLINE, linewidth=0.5)
    ax.add_feature(cfeature.LAND, facecolor='lightgray', alpha=0.3)
    ax.add_feature(cfeature.OCEAN, facecolor='lightblue', alpha=0.2)

    # 緯度経度グリッド
    gl = ax.gridlines(draw_labels=True, linewidth=0.5, color='gray', alpha=0.5, linestyle='--')
    gl.top_labels = False
    gl.right_labels = False

    # 500hPa高度場（等値線）
    contour = ax.contour(lon, lat, z_500.values, levels=15, colors='black', linewidths=1.2,
                         transform=ccrs.PlateCarree())
    ax.clabel(contour, inline=True, fontsize=8, fmt='%d m')

    # 渦度（カラーマップ）
    vort_levels = np.linspace(-10, 10, 21)
    contourf = ax.contourf(lon, lat, vorticity, levels=vort_levels,
                           cmap='RdBu_r', alpha=0.6, extend='both',
                           transform=ccrs.PlateCarree())

    cbar = plt.colorbar(contourf, ax=ax, orientation='vertical', pad=0.05, shrink=0.8)
    cbar.set_label('Relative Vorticity (10^-5 s^-1)', fontsize=10)

    # 重要地点をマーク
    for name, (lat_pt, lon_pt) in LOCATIONS.items():
        ax.plot(lon_pt, lat_pt, 'ro', markersize=8, transform=ccrs.PlateCarree(), zorder=5)
        ax.text(lon_pt + 0.05, lat_pt + 0.05, name, fontsize=9, fontweight='bold',
                transform=ccrs.PlateCarree(), zorder=5,
                bbox=dict(boxstyle='round,pad=0.3', facecolor='white', alpha=0.7))

    # タイトル
    plt.title(f'500hPa Geopotential Height & Relative Vorticity\n{time_str} UTC',
              fontsize=14, fontweight='bold')

    # 保存
    plt.tight_layout()
    plt.savefig(save_path, dpi=150, bbox_inches='tight')
    print(f"Saved: {save_path}")
    plt.close()

def plot_700hpa_omega(ds, time_idx=0, save_path='contour_700hpa_omega.png'):
    """700hPa鉛直p速度の等値線図を作成"""

    print(f"Creating 700hPa omega map for time index {time_idx}...")

    # データ抽出
    ds_700 = ds.sel(pressure_level=700).isel(valid_time=time_idx)

    omega_700 = ds_700['w'].values
    if 'z' in ds_700:
        z_700 = ds_700['z'] / 9.80665
    elif 'geopotential' in ds_700:
        z_700 = ds_700['geopotential'] / 9.80665
    else:
        z_700 = None

    lat = ds_700.latitude.values
    lon = ds_700.longitude.values

    # 時刻情報
    time_str = str(ds_700.valid_time.values)[:19]

    # プロット作成
    fig = plt.figure(figsize=(14, 10))
    ax = plt.axes(projection=ccrs.PlateCarree())

    ax.set_extent([140, 143, 44, 46], crs=ccrs.PlateCarree())
    ax.add_feature(cfeature.COASTLINE, linewidth=0.5)
    ax.add_feature(cfeature.LAND, facecolor='lightgray', alpha=0.3)
    ax.add_feature(cfeature.OCEAN, facecolor='lightblue', alpha=0.2)

    gl = ax.gridlines(draw_labels=True, linewidth=0.5, color='gray', alpha=0.5, linestyle='--')
    gl.top_labels = False
    gl.right_labels = False

    # 700hPa高度場（等値線）
    if z_700 is not None:
        contour = ax.contour(lon, lat, z_700, levels=10, colors='black', linewidths=1.0,
                             transform=ccrs.PlateCarree())
        ax.clabel(contour, inline=True, fontsize=8, fmt='%d m')

    # 鉛直p速度（カラーマップ）
    # omega: 負=上昇、正=下降
    omega_levels = np.linspace(-0.5, 0.5, 21)
    contourf = ax.contourf(lon, lat, omega_700, levels=omega_levels,
                           cmap='PuOr_r', alpha=0.7, extend='both',
                           transform=ccrs.PlateCarree())

    cbar = plt.colorbar(contourf, ax=ax, orientation='vertical', pad=0.05, shrink=0.8)
    cbar.set_label('Vertical Velocity (Pa/s)\n(negative=upward)', fontsize=10)

    # 重要地点
    for name, (lat_pt, lon_pt) in LOCATIONS.items():
        ax.plot(lon_pt, lat_pt, 'ro', markersize=8, transform=ccrs.PlateCarree(), zorder=5)
        ax.text(lon_pt + 0.05, lat_pt + 0.05, name, fontsize=9, fontweight='bold',
                transform=ccrs.PlateCarree(), zorder=5,
                bbox=dict(boxstyle='round,pad=0.3', facecolor='white', alpha=0.7))

    plt.title(f'700hPa Geopotential Height & Vertical Velocity\n{time_str} UTC',
              fontsize=14, fontweight='bold')

    plt.tight_layout()
    plt.savefig(save_path, dpi=150, bbox_inches='tight')
    print(f"Saved: {save_path}")
    plt.close()

def create_sample_maps():
    """サンプル等値線マップを作成"""

    print("="*70)
    print("CONTOUR MAP VISUALIZATION")
    print("="*70)

    # ERA5データ読み込み
    try:
        ds = xr.open_dataset('era5_rishiri_august2024.nc')
        print(f"\nDataset loaded: {len(ds.valid_time)} timesteps")
    except FileNotFoundError:
        print("\nError: era5_rishiri_august2024.nc not found")
        print("Please run fetch_era5_data.py first")
        return

    # サンプル時刻を選択（複数）
    n_times = len(ds.valid_time)
    sample_indices = [0, n_times//3, 2*n_times//3, n_times-1] if n_times > 3 else [0, n_times-1]

    print(f"\nCreating maps for {len(sample_indices)} sample timesteps...")

    for i, time_idx in enumerate(sample_indices):
        print(f"\n[{i+1}/{len(sample_indices)}] Time index: {time_idx}")

        # 500hPa
        plot_500hpa_contour(ds, time_idx=time_idx,
                           save_path=f'contour_500hpa_t{time_idx:04d}.png')

        # 700hPa
        plot_700hpa_omega(ds, time_idx=time_idx,
                         save_path=f'contour_700hpa_omega_t{time_idx:04d}.png')

    print(f"\n{'='*70}")
    print("MAP CREATION COMPLETE")
    print(f"{'='*70}")
    print(f"\nCreated {len(sample_indices) * 2} contour maps")

if __name__ == '__main__':
    create_sample_maps()
