#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ERA5再解析データ取得

利尻島周辺の500hPa/700hPa気圧面データを取得
"""

import cdsapi
import os
from datetime import datetime

def fetch_era5_rishiri_summer2024():
    """
    ERA5再解析データを取得

    領域: 利尻島周辺（44-46°N, 140-143°E）
    期間: 2024年6-8月
    気圧面: 500hPa, 700hPa, 850hPa
    """

    print("="*70)
    print("ERA5 REANALYSIS DATA FETCHER")
    print("="*70)
    print("\nTarget area: Rishiri Island region")
    print("  Latitude:  44-46°N")
    print("  Longitude: 140-143°E")
    print("\nPeriod: 2024-06 to 2024-08")
    print("Pressure levels: 500hPa, 700hPa, 850hPa")
    print("Variables: geopotential, temperature, u/v wind components")

    # CDS API クライアント初期化
    try:
        c = cdsapi.Client()
    except Exception as e:
        print(f"\nError: Failed to initialize CDS API client")
        print(f"Details: {e}")
        print("\nPlease configure CDS API:")
        print("1. Register at https://cds.climate.copernicus.eu/")
        print("2. Get API key from your profile")
        print("3. Create ~/.cdsapirc file:")
        print("   url: https://cds.climate.copernicus.eu/api/v2")
        print("   key: YOUR-UID:YOUR-API-KEY")
        return None

    output_file = 'era5_rishiri_august2024.nc'

    print(f"\nFetching data...")
    print(f"Output file: {output_file}")
    print("Note: Reduced to August 2024, 09:00 UTC only to avoid size limits")
    print("\nThis may take several minutes...\n")

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
                    'vertical_velocity'  # omega (Pa/s)
                ],
                'pressure_level': ['500', '700', '850'],
                'year': '2024',
                'month': ['08'],  # 8月のみに縮小
                'day': [
                    '01', '02', '03', '04', '05', '06', '07', '08', '09', '10',
                    '11', '12', '13', '14', '15', '16', '17', '18', '19', '20',
                    '21', '22', '23', '24', '25', '26', '27', '28', '29', '30', '31'
                ],
                'time': [
                    '09:00'  # 09:00 UTCのみ（ラジオゾンデと同時刻）
                ],
                'area': [
                    46, 140, 44, 143,  # North, West, South, East
                ],
                'format': 'netcdf'
            },
            output_file
        )

        print(f"\n{'='*70}")
        print("DOWNLOAD COMPLETE")
        print(f"{'='*70}")

        # ファイルサイズ確認
        if os.path.exists(output_file):
            file_size = os.path.getsize(output_file) / (1024 * 1024)  # MB
            print(f"\nFile: {output_file}")
            print(f"Size: {file_size:.2f} MB")
            print(f"\nData ready for analysis!")
            return output_file
        else:
            print(f"\nError: File not found after download")
            return None

    except Exception as e:
        print(f"\nError during download: {e}")
        return None

if __name__ == '__main__':
    result = fetch_era5_rishiri_summer2024()

    if result:
        print("\nNext steps:")
        print("1. Run: python analyze_era5_contours.py")
        print("2. This will generate contour maps and calculate vorticity")
    else:
        print("\nDownload failed. Please check CDS API configuration.")
