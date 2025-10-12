#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
稚内ラジオゾンデデータ取得テスト（1日分）
"""

import requests
from datetime import datetime
import json

WAKKANAI_STATION = "47401"
WYOMING_URL = "http://weather.uwyo.edu/cgi-bin/sounding"

def fetch_radiosonde(station, year, month, day, hour):
    """Wyoming大学からラジオゾンデデータを取得"""
    params = {
        'region': 'np',
        'TYPE': 'TEXT:LIST',
        'YEAR': year,
        'MONTH': f'{month:02d}',
        'FROM': f'{day:02d}{hour:02d}',
        'TO': f'{day:02d}{hour:02d}',
        'STNM': station
    }

    try:
        print(f"Fetching: {WYOMING_URL}")
        print(f"Params: {params}")
        response = requests.get(WYOMING_URL, params=params, timeout=30)
        response.raise_for_status()
        return response.text
    except Exception as e:
        print(f"Error: {e}")
        return None

# テスト: 2024年8月1日 00Z（JST 09:00）
text = fetch_radiosonde(WAKKANAI_STATION, 2024, 8, 1, 0)

if text:
    print(f"\nReceived {len(text)} characters")
    print("\nFirst 2000 characters:")
    print("="*70)
    print(text[:2000])
    print("="*70)

    # データファイルに保存
    with open('radiosonde_sample.txt', 'w', encoding='utf-8') as f:
        f.write(text)
    print("\nSaved to: radiosonde_sample.txt")
else:
    print("Failed to fetch data")
