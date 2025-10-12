#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ERA5海洋データ取得（2024年6-8月）

2024年と2025年のSST比較用に前年データを取得
"""

import cdsapi
from datetime import datetime

def fetch_era5_ocean_data_2024():
    """2024年夏季の海洋データ取得"""

    print("="*70)
    print("ERA5 OCEAN DATA RETRIEVAL - SUMMER 2024 (Jun-Aug)")
    print("="*70)

    c = cdsapi.Client()

    print("\nRequesting ERA5 single-level data (ocean & surface)...")
    print("Period: 2024-06-01 to 2024-08-31")
    print("Time: 09:00 UTC (18:00 JST)")

    try:
        c.retrieve(
            'reanalysis-era5-single-levels',
            {
                'product_type': 'reanalysis',
                'variable': [
                    'sea_surface_temperature',
                    '2m_temperature',
                    '2m_dewpoint_temperature',
                    '10m_u_component_of_wind',
                    '10m_v_component_of_wind',
                    'total_cloud_cover',
                ],
                'year': '2024',
                'month': ['06', '07', '08'],
                'day': [
                    '01', '02', '03', '04', '05', '06', '07', '08', '09', '10',
                    '11', '12', '13', '14', '15', '16', '17', '18', '19', '20',
                    '21', '22', '23', '24', '25', '26', '27', '28', '29', '30', '31'
                ],
                'time': '09:00',
                'area': [46, 140, 44, 143],
                'format': 'netcdf',
            },
            'era5_rishiri_ocean_summer2024.nc'
        )

        print("\n[SUCCESS] Data downloaded: era5_rishiri_ocean_summer2024.nc")

        import os
        file_size = os.path.getsize('era5_rishiri_ocean_summer2024.nc') / (1024*1024)
        print(f"File size: {file_size:.2f} MB")

    except Exception as e:
        print(f"\n[ERROR] Failed to retrieve data: {e}")
        return False

    return True

if __name__ == '__main__':
    fetch_era5_ocean_data_2024()
