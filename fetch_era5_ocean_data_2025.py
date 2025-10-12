#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ERA5海洋関連データ取得（2025年6-8月）

海洋の影響を評価するため追加データを取得:
- 海面水温 (SST)
- 地表気温 (2m temperature)
- 露点温度 (2m dewpoint) → 海霧リスク
- 10m風速 (海上風)

これにより以下を診断:
1. 海陸温度差（海陸風の強さ）
2. 海霧発生リスク（SST - 露点温度）
3. 海水温5度上昇の検証
4. 暖流・冷流の影響
"""

import cdsapi
from datetime import datetime

def fetch_era5_ocean_data_2025():
    """2025年夏季の海洋関連データ取得"""

    print("="*70)
    print("ERA5 OCEAN DATA RETRIEVAL - SUMMER 2025 (Jun-Aug)")
    print("="*70)

    # CDSクライアント初期化
    c = cdsapi.Client()

    print("\nRequesting ERA5 single-level data (ocean & surface)...")
    print("Period: 2025-06-01 to 2025-08-31")
    print("Time: 09:00 UTC (18:00 JST)")
    print("Variables:")
    print("  - Sea Surface Temperature (SST)")
    print("  - 2m Air Temperature")
    print("  - 2m Dewpoint Temperature")
    print("  - 10m Wind (U/V components)")
    print("Area: Rishiri Island region (44-46N, 140-143E)")

    # データ取得リクエスト
    try:
        c.retrieve(
            'reanalysis-era5-single-levels',  # 単一気圧面データ
            {
                'product_type': 'reanalysis',
                'variable': [
                    'sea_surface_temperature',
                    '2m_temperature',
                    '2m_dewpoint_temperature',
                    '10m_u_component_of_wind',
                    '10m_v_component_of_wind',
                    'total_cloud_cover',  # 雲量（海霧検出用）
                ],
                'year': '2025',
                'month': ['06', '07', '08'],
                'day': [
                    '01', '02', '03', '04', '05', '06', '07', '08', '09', '10',
                    '11', '12', '13', '14', '15', '16', '17', '18', '19', '20',
                    '21', '22', '23', '24', '25', '26', '27', '28', '29', '30', '31'
                ],
                'time': '09:00',  # 09:00 UTC = 18:00 JST
                'area': [
                    46, 140, 44, 143,  # North, West, South, East
                ],
                'format': 'netcdf',
            },
            'era5_rishiri_ocean_summer2025.nc'
        )

        print("\n[SUCCESS] Data downloaded: era5_rishiri_ocean_summer2025.nc")

        # ファイルサイズ確認
        import os
        file_size = os.path.getsize('era5_rishiri_ocean_summer2025.nc') / (1024*1024)
        print(f"File size: {file_size:.2f} MB")

        print("\nData summary:")
        print("  - 92 days (Jun 1 - Aug 31)")
        print("  - 1 time per day (09:00 UTC)")
        print("  - 6 variables (SST, T2m, Td2m, U10m, V10m, cloud)")
        print("  - Grid: ~9x13 points (0.25 deg resolution)")

    except Exception as e:
        print(f"\n[ERROR] Failed to retrieve data: {e}")
        print("\nPossible reasons:")
        print("  1. CDS API credentials not configured")
        print("  2. Data request too large (cost limits)")
        print("  3. Network connection issue")
        return False

    return True

if __name__ == '__main__':
    success = fetch_era5_ocean_data_2025()

    if success:
        print("\n" + "="*70)
        print("NEXT STEPS")
        print("="*70)
        print("\n1. Calculate sea-land temperature difference")
        print("2. Detect sea fog risk (SST - dewpoint)")
        print("3. Analyze SST trends (5 degree warming?)")
        print("4. Correlate ocean conditions with kelp drying success")
