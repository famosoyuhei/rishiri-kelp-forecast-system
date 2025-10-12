#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ERA5データ取得（2025年6-8月）

2025年夏季（昆布漁期）の気象データを取得:
- 期間: 2025年6月1日～8月31日
- 時刻: 09:00 UTC（日本時間18:00）のみ
- 気圧面: 850hPa（地形効果）、700hPa、500hPa
- 変数: 気温、風速、ジオポテンシャル高度、鉛直速度
- 範囲: 利尻島周辺（44-46N, 140-143E）
"""

import cdsapi
from datetime import datetime

def fetch_era5_summer_2025():
    """2025年夏季ERA5データの取得"""

    print("="*70)
    print("ERA5 DATA RETRIEVAL - SUMMER 2025 (Jun-Aug)")
    print("="*70)

    # CDSクライアント初期化
    c = cdsapi.Client()

    print("\nRequesting ERA5 reanalysis data...")
    print("Period: 2025-06-01 to 2025-08-31")
    print("Time: 09:00 UTC (18:00 JST)")
    print("Levels: 500hPa, 700hPa, 850hPa")
    print("Area: Rishiri Island region (44-46N, 140-143E)")

    # データ取得リクエスト
    try:
        c.retrieve(
            'reanalysis-era5-pressure-levels',
            {
                'product_type': 'reanalysis',
                'variable': [
                    'geopotential',
                    'temperature',
                    'u_component_of_wind',
                    'v_component_of_wind',
                    'vertical_velocity',
                    'specific_humidity'  # 相当温位計算用
                ],
                'pressure_level': ['500', '700', '850'],
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
            'era5_rishiri_summer2025.nc'
        )

        print("\n[SUCCESS] Data downloaded: era5_rishiri_summer2025.nc")

        # ファイルサイズ確認
        import os
        file_size = os.path.getsize('era5_rishiri_summer2025.nc') / (1024*1024)
        print(f"File size: {file_size:.2f} MB")

        print("\nData summary:")
        print("  - 92 days (Jun 1 - Aug 31)")
        print("  - 1 time per day (09:00 UTC)")
        print("  - 3 pressure levels (500, 700, 850 hPa)")
        print("  - 6 variables")
        print("  - Grid: ~9x13 points (0.25° resolution)")

    except Exception as e:
        print(f"\n[ERROR] Failed to retrieve data: {e}")
        print("\nPossible reasons:")
        print("  1. CDS API credentials not configured")
        print("  2. Data request too large (cost limits)")
        print("  3. Network connection issue")
        return False

    return True

if __name__ == '__main__':
    success = fetch_era5_summer_2025()

    if success:
        print("\n" + "="*70)
        print("NEXT STEPS")
        print("="*70)
        print("\n1. Analyze equivalent potential temperature (theta_e)")
        print("2. Detect air mass transitions")
        print("3. Correlate with kelp drying records")
        print("4. Identify '1-week good → 1-week bad' weather patterns")
