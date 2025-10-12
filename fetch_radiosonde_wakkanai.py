#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
稚内ラジオゾンデデータ取得

データソース: University of Wyoming Upper Air Sounding
観測点: 稚内 (47401)
観測時刻: 00Z, 12Z (JST 09:00, 21:00)
"""

import requests
import re
from datetime import datetime, timedelta
import json
import time

WAKKANAI_STATION = "47401"
WYOMING_URL = "http://weather.uwyo.edu/cgi-bin/sounding"

def fetch_radiosonde(station, year, month, day, hour):
    """
    Wyoming大学からラジオゾンデデータを取得

    Args:
        station: 観測点番号（稚内=47401）
        year, month, day: 日付
        hour: 観測時刻（00 or 12 UTC）
    """
    params = {
        'region': 'np',  # North Pacific
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
        print(f"Error fetching radiosonde data: {e}")
        return None

def parse_radiosonde_text(text):
    """ラジオゾンデテキストデータを解析"""
    if not text or "Can't get" in text or "No data" in text:
        return None

    # データ部分を抽出（ヘッダーとフッターを除く）
    lines = text.split('\n')

    # データセクションを探す
    data_start = -1
    data_end = -1

    for i, line in enumerate(lines):
        if 'PRES' in line and 'HGHT' in line and 'TEMP' in line:
            data_start = i + 2  # ヘッダーの2行後からデータ開始
        elif data_start > 0 and line.strip().startswith('</PRE>'):
            data_end = i
            break

    if data_start < 0:
        return None

    # データを解析
    levels = []
    for i in range(data_start, data_end if data_end > 0 else len(lines)):
        line = lines[i].strip()
        if not line or line.startswith('<'):
            continue

        parts = line.split()
        if len(parts) < 11:
            continue

        try:
            level = {
                'pressure_hPa': float(parts[0]),
                'height_m': float(parts[1]),
                'temperature_C': float(parts[2]) if parts[2] != '' else None,
                'dewpoint_C': float(parts[3]) if parts[3] != '' else None,
                'wind_direction_deg': float(parts[6]) if parts[6] != '' else None,
                'wind_speed_knots': float(parts[7]) if parts[7] != '' else None,
            }
            levels.append(level)
        except (ValueError, IndexError):
            continue

    return levels

def get_level_data(levels, target_pressure):
    """特定気圧面のデータを取得（補間）"""
    if not levels:
        return None

    # 目標気圧に最も近いレベルを探す
    closest = min(levels, key=lambda x: abs(x['pressure_hPa'] - target_pressure))

    # 10hPa以内なら使用
    if abs(closest['pressure_hPa'] - target_pressure) < 10:
        return closest

    # 補間（簡易版）
    lower = None
    upper = None

    for level in levels:
        p = level['pressure_hPa']
        if p > target_pressure:
            if lower is None or p < lower['pressure_hPa']:
                lower = level
        elif p < target_pressure:
            if upper is None or p > upper['pressure_hPa']:
                upper = level

    if lower and upper:
        # 線形補間
        p1, p2 = lower['pressure_hPa'], upper['pressure_hPa']
        weight = (target_pressure - p1) / (p2 - p1)

        return {
            'pressure_hPa': target_pressure,
            'height_m': lower['height_m'] + weight * (upper['height_m'] - lower['height_m']),
            'temperature_C': lower['temperature_C'] + weight * (upper['temperature_C'] - lower['temperature_C']) if lower['temperature_C'] and upper['temperature_C'] else None,
            'wind_direction_deg': lower['wind_direction_deg'] if lower['wind_direction_deg'] else upper['wind_direction_deg'],
            'wind_speed_knots': lower['wind_speed_knots'] + weight * (upper['wind_speed_knots'] - lower['wind_speed_knots']) if lower['wind_speed_knots'] and upper['wind_speed_knots'] else None
        }

    return None

def calculate_vorticity_from_winds(levels, target_pressure=500):
    """風向・風速から相対渦度を推定"""
    target = get_level_data(levels, target_pressure)
    if not target or not target['wind_direction_deg'] or not target['wind_speed_knots']:
        return None

    # 風速をm/sに変換
    wind_speed_ms = target['wind_speed_knots'] * 0.514444

    # 簡易的な渦度推定（風向の変化から）
    # より正確には周囲の観測点が必要だが、ここでは単一点の風速シアーから推定

    # 上下の気圧面を取得
    upper_level = get_level_data(levels, target_pressure - 50)
    lower_level = get_level_data(levels, target_pressure + 50)

    if not upper_level or not lower_level:
        return None

    if not upper_level.get('wind_direction_deg') or not lower_level.get('wind_direction_deg'):
        return None

    # 風向の鉛直シアーから渦度を推定
    ddir = upper_level['wind_direction_deg'] - lower_level['wind_direction_deg']
    if ddir > 180:
        ddir -= 360
    elif ddir < -180:
        ddir += 360

    # 簡易渦度（10^-5 s^-1単位）
    # 正: サイクロン性（反時計回り）、負: アンチサイクロン性
    vorticity = ddir / 100.0  # 非常に簡易的な推定

    return vorticity

def fetch_multiple_dates(start_date, end_date, hour=0):
    """複数日のラジオゾンデデータを取得"""
    results = []
    current = start_date

    while current <= end_date:
        year = current.year
        month = current.month
        day = current.day

        print(f"Fetching {current.strftime('%Y-%m-%d')} {hour:02d}Z...", end=" ")

        text = fetch_radiosonde(WAKKANAI_STATION, year, month, day, hour)
        levels = parse_radiosonde_text(text) if text else None

        if levels:
            # 主要気圧面のデータを抽出
            data_500 = get_level_data(levels, 500)
            data_700 = get_level_data(levels, 700)
            data_850 = get_level_data(levels, 850)

            vorticity_500 = calculate_vorticity_from_winds(levels, 500)

            result = {
                'date': current.strftime('%Y-%m-%d'),
                'time_utc': f'{hour:02d}:00',
                'time_jst': f'{(hour + 9) % 24:02d}:00',
                'station': 'Wakkanai (47401)',
                'levels': {
                    '500hPa': data_500,
                    '700hPa': data_700,
                    '850hPa': data_850
                },
                'derived': {
                    'vorticity_500hPa': vorticity_500
                }
            }
            results.append(result)
            print(f"OK ({len(levels)} levels)")
        else:
            print("No data")

        current += timedelta(days=1)
        time.sleep(1)  # サーバー負荷軽減

    return results

def main():
    """メイン処理"""
    print("="*70)
    print("WAKKANAI RADIOSONDE DATA FETCHER")
    print("="*70)

    # 2024年6-8月のデータを取得（00Z = JST 09:00）
    start = datetime(2024, 6, 1)
    end = datetime(2024, 8, 31)

    print(f"\nFetching period: {start.strftime('%Y-%m-%d')} to {end.strftime('%Y-%m-%d')}")
    print(f"Observation time: 00Z (JST 09:00)")
    print(f"Station: Wakkanai (47401)\n")

    results = fetch_multiple_dates(start, end, hour=0)

    print(f"\n{'='*70}")
    print(f"SUMMARY")
    print(f"{'='*70}")
    print(f"Total observations: {len(results)}")

    if results:
        # 統計
        temps_500 = [r['levels']['500hPa']['temperature_C'] for r in results if r['levels']['500hPa'] and r['levels']['500hPa']['temperature_C']]
        vorticities = [r['derived']['vorticity_500hPa'] for r in results if r['derived']['vorticity_500hPa']]

        if temps_500:
            import numpy as np
            print(f"\n500hPa temperature:")
            print(f"  Mean: {np.mean(temps_500):.1f}C")
            print(f"  Range: [{np.min(temps_500):.1f}, {np.max(temps_500):.1f}]C")

        if vorticities:
            print(f"\n500hPa vorticity (estimated):")
            print(f"  Mean: {np.mean(vorticities):+.2f} x10^-5 s^-1")
            print(f"  Range: [{np.min(vorticities):+.2f}, {np.max(vorticities):+.2f}] x10^-5 s^-1")

    # 保存
    output_file = 'wakkanai_radiosonde_2024_summer.json'
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump({
            'metadata': {
                'station': 'Wakkanai',
                'station_id': '47401',
                'coordinates': {'lat': 45.42, 'lon': 141.68},
                'period': f"{start.strftime('%Y-%m-%d')} to {end.strftime('%Y-%m-%d')}",
                'observation_time': '00Z (JST 09:00)',
                'total_observations': len(results)
            },
            'observations': results
        }, f, ensure_ascii=False, indent=2)

    print(f"\nResults saved to: {output_file}")

if __name__ == '__main__':
    main()
