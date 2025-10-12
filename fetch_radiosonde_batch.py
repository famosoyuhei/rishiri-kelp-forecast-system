#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
稚内ラジオゾンデデータ一括取得（最適化版）

2024年夏（6-8月）のデータを1週間ごとにバッチ取得
"""

import requests
from datetime import datetime, timedelta
import json
import time
import re

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
        response = requests.get(WYOMING_URL, params=params, timeout=30)
        response.raise_for_status()
        return response.text
    except Exception as e:
        return None

def parse_radiosonde(text):
    """ラジオゾンデHTMLテキストを解析"""
    if not text or "Can't get" in text or "No data" in text:
        return None

    lines = text.split('\n')

    # データ部分を抽出
    data = []
    in_data = False

    for line in lines:
        # データセクション開始
        if 'PRES' in line and 'HGHT' in line and 'TEMP' in line:
            in_data = True
            continue

        # データセクション終了
        if in_data and ('</PRE>' in line or 'Station information' in line):
            break

        if in_data and line.strip() and not line.strip().startswith('-'):
            parts = line.split()
            if len(parts) >= 11:
                try:
                    data.append({
                        'pres': float(parts[0]),
                        'hght': float(parts[1]),
                        'temp': float(parts[2]) if parts[2] != '' else None,
                        'dwpt': float(parts[3]) if parts[3] != '' else None,
                        'relh': float(parts[4]) if parts[4] != '' else None,
                        'mixr': float(parts[5]) if parts[5] != '' else None,
                        'drct': float(parts[6]) if parts[6] != '' else None,
                        'sknt': float(parts[7]) if parts[7] != '' else None,
                        'thta': float(parts[8]) if parts[8] != '' else None,
                        'thte': float(parts[9]) if parts[9] != '' else None,
                        'thtv': float(parts[10]) if parts[10] != '' else None
                    })
                except (ValueError, IndexError):
                    continue

    return data if data else None

def get_level(data, target_pres):
    """特定気圧面のデータを取得（補間）"""
    if not data:
        return None

    # 正確な気圧面を探す
    for level in data:
        if abs(level['pres'] - target_pres) < 5:
            return level

    # 補間
    lower = None
    upper = None

    for level in data:
        if level['pres'] > target_pres:
            if not lower or level['pres'] < lower['pres']:
                lower = level
        elif level['pres'] < target_pres:
            if not upper or level['pres'] > upper['pres']:
                upper = level

    if lower and upper:
        p1, p2 = lower['pres'], upper['pres']
        w = (target_pres - p1) / (p2 - p1)

        def interp(key):
            v1, v2 = lower.get(key), upper.get(key)
            return v1 + w * (v2 - v1) if v1 is not None and v2 is not None else None

        return {
            'pres': target_pres,
            'hght': interp('hght'),
            'temp': interp('temp'),
            'dwpt': interp('dwpt'),
            'drct': lower.get('drct') if lower.get('drct') else upper.get('drct'),
            'sknt': interp('sknt')
        }

    return None

def fetch_period(start_date, end_date):
    """期間のデータを取得"""
    results = []
    current = start_date

    while current <= end_date:
        date_str = current.strftime('%Y-%m-%d')
        print(f"{date_str}...", end=" ", flush=True)

        text = fetch_radiosonde(WAKKANAI_STATION, current.year, current.month, current.day, 0)
        data = parse_radiosonde(text) if text else None

        if data:
            lv500 = get_level(data, 500)
            lv700 = get_level(data, 700)
            lv850 = get_level(data, 850)

            results.append({
                'date': date_str,
                'time_utc': '00Z',
                'time_jst': '09:00',
                'levels': {
                    '500hPa': lv500,
                    '700hPa': lv700,
                    '850hPa': lv850
                }
            })
            print("OK")
        else:
            print("No data")

        current += timedelta(days=1)
        time.sleep(1.5)  # サーバー負荷軽減

    return results

def main():
    print("="*70)
    print("WAKKANAI RADIOSONDE BATCH FETCHER")
    print("="*70)

    # 2024年6-8月を週ごとに取得
    periods = [
        (datetime(2024, 6, 1), datetime(2024, 6, 30)),
        (datetime(2024, 7, 1), datetime(2024, 7, 31)),
        (datetime(2024, 8, 1), datetime(2024, 8, 31))
    ]

    all_results = []

    for start, end in periods:
        print(f"\nFetching {start.strftime('%Y-%m')}:")
        results = fetch_period(start, end)
        all_results.extend(results)
        print(f"  Collected: {len(results)} observations")

    # 統計
    print(f"\n{'='*70}")
    print("SUMMARY")
    print(f"{'='*70}")
    print(f"Total observations: {len(all_results)}")

    if all_results:
        import numpy as np

        temps_500 = [r['levels']['500hPa']['temp'] for r in all_results if r['levels']['500hPa'] and r['levels']['500hPa']['temp'] is not None]
        temps_700 = [r['levels']['700hPa']['temp'] for r in all_results if r['levels']['700hPa'] and r['levels']['700hPa']['temp'] is not None]

        winds_500 = [(r['levels']['500hPa']['drct'], r['levels']['500hPa']['sknt']) for r in all_results if r['levels']['500hPa'] and r['levels']['500hPa']['drct'] is not None]

        if temps_500:
            print(f"\n500hPa temperature:")
            print(f"  Mean: {np.mean(temps_500):.1f}C")
            print(f"  Range: [{np.min(temps_500):.1f}, {np.max(temps_500):.1f}]C")

        if temps_700:
            print(f"\n700hPa temperature:")
            print(f"  Mean: {np.mean(temps_700):.1f}C")
            print(f"  Range: [{np.min(temps_700):.1f}, {np.max(temps_700):.1f}]C")

        if winds_500:
            print(f"\n500hPa wind (n={len(winds_500)}):")
            dirs = [w[0] for w in winds_500]
            speeds = [w[1] * 0.514444 for w in winds_500]  # knots to m/s
            print(f"  Mean direction: {np.mean(dirs):.0f}deg")
            print(f"  Mean speed: {np.mean(speeds):.1f}m/s")

    # 保存
    output = {
        'metadata': {
            'station': 'Wakkanai',
            'station_id': '47401',
            'coordinates': {'lat': 45.41, 'lon': 141.68},
            'period': '2024-06 to 2024-08',
            'observation_time': '00Z (JST 09:00)',
            'total_observations': len(all_results)
        },
        'observations': all_results
    }

    output_file = 'wakkanai_radiosonde_summer2024.json'
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\nResults saved to: {output_file}")

if __name__ == '__main__':
    main()
