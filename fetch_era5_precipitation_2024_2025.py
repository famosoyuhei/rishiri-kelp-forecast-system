#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ERA5降水量データ取得（2024-2025年6-8月）

蝦夷梅雨の実態検証用に降水量データを取得:
- Total precipitation（総降水量）
- Convective precipitation（対流性降水）
- 2年分を比較して長雨パターンを抽出
"""

import cdsapi
from datetime import datetime

def fetch_era5_precipitation_both_years():
    """2024年と2025年の降水量データを取得"""

    print("="*70)
    print("ERA5 PRECIPITATION DATA RETRIEVAL - 2024 & 2025")
    print("="*70)

    c = cdsapi.Client()

    # 2024年データ
    print("\n[1/2] Requesting 2024 precipitation data...")
    try:
        c.retrieve(
            'reanalysis-era5-single-levels',
            {
                'product_type': 'reanalysis',
                'variable': [
                    'total_precipitation',
                    'convective_precipitation',
                ],
                'year': '2024',
                'month': ['06', '07', '08'],
                'day': [
                    '01', '02', '03', '04', '05', '06', '07', '08', '09', '10',
                    '11', '12', '13', '14', '15', '16', '17', '18', '19', '20',
                    '21', '22', '23', '24', '25', '26', '27', '28', '29', '30', '31'
                ],
                'time': [
                    '00:00', '03:00', '06:00', '09:00',
                    '12:00', '15:00', '18:00', '21:00'
                ],  # 全時刻（日積算用）
                'area': [46, 140, 44, 143],
                'format': 'netcdf',
            },
            'era5_rishiri_precipitation_summer2024.nc'
        )
        print("  [SUCCESS] 2024 data downloaded")
    except Exception as e:
        print(f"  [ERROR] 2024 download failed: {e}")
        return False

    # 2025年データ
    print("\n[2/2] Requesting 2025 precipitation data...")
    try:
        c.retrieve(
            'reanalysis-era5-single-levels',
            {
                'product_type': 'reanalysis',
                'variable': [
                    'total_precipitation',
                    'convective_precipitation',
                ],
                'year': '2025',
                'month': ['06', '07', '08'],
                'day': [
                    '01', '02', '03', '04', '05', '06', '07', '08', '09', '10',
                    '11', '12', '13', '14', '15', '16', '17', '18', '19', '20',
                    '21', '22', '23', '24', '25', '26', '27', '28', '29', '30', '31'
                ],
                'time': [
                    '00:00', '03:00', '06:00', '09:00',
                    '12:00', '15:00', '18:00', '21:00'
                ],
                'area': [46, 140, 44, 143],
                'format': 'netcdf',
            },
            'era5_rishiri_precipitation_summer2025.nc'
        )
        print("  [SUCCESS] 2025 data downloaded")
    except Exception as e:
        print(f"  [ERROR] 2025 download failed: {e}")
        return False

    print("\n" + "="*70)
    print("DOWNLOAD COMPLETE")
    print("="*70)
    print("\nNext: Analyze 'Ezo Tsuyu' (Hokkaido rainy season) patterns")

    return True

if __name__ == '__main__':
    fetch_era5_precipitation_both_years()
