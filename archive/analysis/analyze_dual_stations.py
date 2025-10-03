#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
沓形と本泊の2観測点データを使った分析
干場の位置に応じて最適な観測点を選択
"""
import csv
import sys
import io
from datetime import datetime
import statistics
import math

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def load_drying_records():
    """Load drying records from CSV"""
    records = []
    with open('hoshiba_records.csv', 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            records.append(row)
    return records

def parse_dual_station_data():
    """Parse both 沓形 and 本泊 data from CSV"""
    with open('data.csv', 'r', encoding='cp932') as f:
        lines = f.readlines()

    header_idx = None
    for i, line in enumerate(lines):
        if '年月日' in line:
            header_idx = i
            break

    if header_idx is None:
        return {}, {}

    # Location row (before header)
    location_line = lines[header_idx - 1]
    locations = [loc.strip() for loc in location_line.split(',')]

    header_line = lines[header_idx]
    headers = [h.strip() for h in header_line.split(',')]

    print("=" * 100)
    print("観測点の検出")
    print("=" * 100)

    # Find columns for each station
    kutsugata_indices = {}
    motodomari_indices = {}

    # First pass: identify date column
    date_idx = None
    for i, header in enumerate(headers):
        if header == '年月日':
            date_idx = i
            break

    # Second pass: identify parameters for each station
    for i, (loc, header) in enumerate(zip(locations, headers)):
        if i == date_idx:
            continue

        if loc == '沓形':
            if header == '平均気温(℃)' and 'temp' not in kutsugata_indices:
                kutsugata_indices['temp'] = i
            elif header == '降水量の合計(mm)' and 'precip' not in kutsugata_indices:
                kutsugata_indices['precip'] = i
            elif header == '日照時間(時間)' and 'sunshine' not in kutsugata_indices:
                kutsugata_indices['sunshine'] = i
            elif header == '平均風速(m/s)' and 'wind_avg' not in kutsugata_indices:
                kutsugata_indices['wind_avg'] = i
            elif header == '最大風速(m/s)' and 'wind_max' not in kutsugata_indices:
                kutsugata_indices['wind_max'] = i
            elif header == '平均湿度(％)' and 'humidity' not in kutsugata_indices:
                kutsugata_indices['humidity'] = i
        elif loc == '本泊':
            if header == '平均気温(℃)' and 'temp' not in motodomari_indices:
                motodomari_indices['temp'] = i
            elif header == '降水量の合計(mm)' and 'precip' not in motodomari_indices:
                motodomari_indices['precip'] = i
            elif header == '日照時間(時間)' and 'sunshine' not in motodomari_indices:
                motodomari_indices['sunshine'] = i
            elif header == '平均風速(m/s)' and 'wind_avg' not in motodomari_indices:
                motodomari_indices['wind_avg'] = i
            elif header == '最大風速(m/s)' and 'wind_max' not in motodomari_indices:
                motodomari_indices['wind_max'] = i
            elif header == '平均湿度(％)' and 'humidity' not in motodomari_indices:
                motodomari_indices['humidity'] = i

    print(f"\n沓形（西側）の列:")
    for key, idx in kutsugata_indices.items():
        print(f"  {key}: {idx}")

    print(f"\n本泊（東側）の列:")
    for key, idx in motodomari_indices.items():
        print(f"  {key}: {idx}")

    # Parse data
    kutsugata_data = {}
    motodomari_data = {}

    for line in lines[header_idx + 2:]:
        if not line.strip():
            continue

        cols = [c.strip() for c in line.split(',')]
        if date_idx >= len(cols):
            continue

        date_str = cols[date_idx]
        if not date_str or '/' not in date_str:
            continue

        try:
            date = datetime.strptime(date_str, '%Y/%m/%d')
            date_key = date.strftime('%Y-%m-%d')

            def safe_float(indices, key):
                if key not in indices or indices[key] >= len(cols):
                    return None
                val = cols[indices[key]]
                if val == '' or val == '--' or val == ')':
                    return None
                try:
                    val = val.replace(')', '').replace(']', '').strip()
                    return float(val)
                except:
                    return None

            kutsugata_data[date_key] = {
                'temp': safe_float(kutsugata_indices, 'temp'),
                'precip': safe_float(kutsugata_indices, 'precip'),
                'sunshine': safe_float(kutsugata_indices, 'sunshine'),
                'wind_avg': safe_float(kutsugata_indices, 'wind_avg'),
                'wind_max': safe_float(kutsugata_indices, 'wind_max'),
                'humidity': safe_float(kutsugata_indices, 'humidity')
            }

            motodomari_data[date_key] = {
                'temp': safe_float(motodomari_indices, 'temp'),
                'precip': safe_float(motodomari_indices, 'precip'),
                'sunshine': safe_float(motodomari_indices, 'sunshine'),
                'wind_avg': safe_float(motodomari_indices, 'wind_avg'),
                'wind_max': safe_float(motodomari_indices, 'wind_max'),
                'humidity': safe_float(motodomari_indices, 'humidity')
            }
        except:
            continue

    print(f"\n沓形データ: {len(kutsugata_data)}日分")
    print(f"本泊データ: {len(motodomari_data)}日分")

    return kutsugata_data, motodomari_data

def get_spot_coordinates(spot_name):
    """Extract coordinates from spot name"""
    parts = spot_name.split('_')
    if len(parts) == 3:
        lat = float(parts[1]) / 10000
        lon = float(parts[2]) / 10000
        return lat, lon
    return None, None

def select_optimal_station(lat, lon):
    """
    干場の位置に基づいて最適な観測点を選択

    沓形: 北緯45.1342°, 東経141.1144° (西側)
    本泊: 北緯45.2450°, 東経141.2089° (東側)
    利尻山: 北緯45.1794°, 東経141.2425° (中央)
    """
    kutsugata_lat, kutsugata_lon = 45.1342, 141.1144
    motodomari_lat, motodomari_lon = 45.2450, 141.2089

    # Calculate distance to each station
    def distance(lat1, lon1, lat2, lon2):
        return math.sqrt((lat1 - lat2)**2 + (lon1 - lon2)**2)

    dist_kutsugata = distance(lat, lon, kutsugata_lat, kutsugata_lon)
    dist_motodomari = distance(lat, lon, motodomari_lat, motodomari_lon)

    # Also consider longitude for east-west distinction
    # Longitude ~141.18 is roughly the dividing line
    if lon < 141.18:
        # Western side - prefer Kutsugata
        return 'kutsugata', dist_kutsugata, dist_motodomari
    else:
        # Eastern side - prefer Motodomari
        return 'motodomari', dist_kutsugata, dist_motodomari

def main():
    records = load_drying_records()
    kutsugata_data, motodomari_data = parse_dual_station_data()

    print("\n" + "=" * 100)
    print("干場ごとの最適観測点選択")
    print("=" * 100)

    # Analyze each record with optimal station
    results = []

    for record in records:
        date_str = record['date']
        spot_name = record['name']
        result = record['result']

        lat, lon = get_spot_coordinates(spot_name)
        if lat is None:
            continue

        station, dist_k, dist_m = select_optimal_station(lat, lon)

        kutsugata_weather = kutsugata_data.get(date_str, {})
        motodomari_weather = motodomari_data.get(date_str, {})

        selected_weather = kutsugata_weather if station == 'kutsugata' else motodomari_weather
        other_weather = motodomari_weather if station == 'kutsugata' else kutsugata_weather

        results.append({
            'date': date_str,
            'spot': spot_name,
            'lat': lat,
            'lon': lon,
            'result': result,
            'station': station,
            'selected_weather': selected_weather,
            'other_weather': other_weather,
            'dist_k': dist_k,
            'dist_m': dist_m
        })

    # Show 2025-07-29 specifically
    print("\n" + "=" * 100)
    print("2025-07-29の詳細（神居晴れ、鴛泊曇り）")
    print("=" * 100)

    july29_records = [r for r in results if r['date'] == '2025-07-29']

    for r in july29_records:
        print(f"\n干場: {r['spot']} ({r['lat']:.4f}N, {r['lon']:.4f}E)")
        print(f"結果: {r['result']}")
        print(f"選択観測点: {r['station']}")
        print(f"  沓形まで距離: {r['dist_k']:.4f}° / 本泊まで距離: {r['dist_m']:.4f}°")

        if r['selected_weather']:
            print(f"\n選択された観測点（{r['station']}）のデータ:")
            for key, val in r['selected_weather'].items():
                if val is not None:
                    unit = {'temp': '°C', 'precip': 'mm', 'sunshine': 'h', 'wind_avg': 'm/s', 'wind_max': 'm/s', 'humidity': '%'}.get(key, '')
                    print(f"  {key}: {val}{unit}")

        if r['other_weather']:
            other_name = '本泊' if r['station'] == 'kutsugata' else '沓形'
            print(f"\n参考: {other_name}のデータ:")
            for key, val in r['other_weather'].items():
                if val is not None:
                    unit = {'temp': '°C', 'precip': 'mm', 'sunshine': 'h', 'wind_avg': 'm/s', 'wind_max': 'm/s', 'humidity': '%'}.get(key, '')
                    print(f"  {key}: {val}{unit}")

    # Overall statistics with optimal station selection
    print("\n" + "=" * 100)
    print("最適観測点を使った統計（完全乾燥のみ）")
    print("=" * 100)

    success_records = [r for r in results if r['result'] == '完全乾燥' and r['selected_weather']]

    # Collect data
    precips = [r['selected_weather']['precip'] for r in success_records if r['selected_weather'].get('precip') is not None]
    humidities = [r['selected_weather']['humidity'] for r in success_records if r['selected_weather'].get('humidity') is not None]
    sunshines = [r['selected_weather']['sunshine'] for r in success_records if r['selected_weather'].get('sunshine') is not None]
    winds_avg = [r['selected_weather']['wind_avg'] for r in success_records if r['selected_weather'].get('wind_avg') is not None]

    print(f"\n完全乾燥記録 (n={len(success_records)}):")
    if precips:
        print(f"  降水量: min={min(precips):.1f}mm, max={max(precips):.1f}mm, mean={statistics.mean(precips):.1f}mm")
    if humidities:
        print(f"  湿度: min={min(humidities):.1f}%, max={max(humidities):.1f}%, mean={statistics.mean(humidities):.1f}%")
    if sunshines:
        print(f"  日照: min={min(sunshines):.1f}h, max={max(sunshines):.1f}h, mean={statistics.mean(sunshines):.1f}h")
    if winds_avg:
        print(f"  風速: min={min(winds_avg):.1f}m/s, max={max(winds_avg):.1f}m/s, mean={statistics.mean(winds_avg):.1f}m/s")

    # Station usage distribution
    kutsugata_count = sum(1 for r in success_records if r['station'] == 'kutsugata')
    motodomari_count = sum(1 for r in success_records if r['station'] == 'motodomari')

    print(f"\n使用観測点:")
    print(f"  沓形: {kutsugata_count}件")
    print(f"  本泊: {motodomari_count}件")

    print("\n" + "=" * 100)

if __name__ == '__main__':
    main()
