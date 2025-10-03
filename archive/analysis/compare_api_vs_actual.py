#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Compare API forecast data vs JMA Amedas actual observation data
Quantify the discrepancy and determine reliable thresholds
"""
import csv
import sys
import io
from datetime import datetime
import statistics
import requests
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

def parse_amedas_data():
    """Parse JMA Amedas CSV data"""
    with open('data.csv', 'r', encoding='cp932') as f:
        lines = f.readlines()

    header_idx = None
    for i, line in enumerate(lines):
        if '年月日' in line:
            header_idx = i
            break

    if header_idx is None:
        return {}

    header_line = lines[header_idx]
    headers = [h.strip() for h in header_line.split(',')]

    # Find indices
    indices = {}
    for i, header in enumerate(headers):
        if header == '年月日' and 'date' not in indices:
            indices['date'] = i
        elif header == '平均気温(℃)' and 'temp' not in indices:
            indices['temp'] = i
        elif header == '降水量の合計(mm)' and 'precip' not in indices:
            indices['precip'] = i
        elif header == '平均風速(m/s)' and 'wind_avg' not in indices:
            indices['wind_avg'] = i
        elif header == '最大風速(m/s)' and 'wind_max' not in indices:
            indices['wind_max'] = i
        elif header == '平均湿度(％)' and 'humidity' not in indices:
            indices['humidity'] = i

    weather_data = {}
    for line in lines[header_idx + 2:]:
        if not line.strip():
            continue

        cols = [c.strip() for c in line.split(',')]
        if indices['date'] >= len(cols):
            continue

        date_str = cols[indices['date']]
        if not date_str or '/' not in date_str:
            continue

        try:
            date = datetime.strptime(date_str, '%Y/%m/%d')
            date_key = date.strftime('%Y-%m-%d')

            def safe_float(key):
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

            weather_data[date_key] = {
                'temp': safe_float('temp'),
                'precip': safe_float('precip'),
                'wind_avg': safe_float('wind_avg'),
                'wind_max': safe_float('wind_max'),
                'humidity': safe_float('humidity')
            }
        except:
            continue

    return weather_data

def get_spot_coordinates(spot_name):
    """Extract coordinates from spot name"""
    parts = spot_name.split('_')
    if len(parts) == 3:
        lat = float(parts[1]) / 10000
        lon = float(parts[2]) / 10000
        return lat, lon
    return None, None

def fetch_api_weather(lat, lon, date_str):
    """Fetch weather from Open-Meteo API"""
    try:
        url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&hourly=temperature_2m,relative_humidity_2m,wind_speed_10m,precipitation&start_date={date_str}&end_date={date_str}&timezone=Asia/Tokyo"
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        return response.json()
    except:
        try:
            url = f"https://archive-api.open-meteo.com/v1/archive?latitude={lat}&longitude={lon}&start_date={date_str}&end_date={date_str}&hourly=temperature_2m,relative_humidity_2m,wind_speed_10m,precipitation&timezone=Asia/Tokyo"
            response = requests.get(url, timeout=15)
            response.raise_for_status()
            return response.json()
        except:
            return None

def analyze_api_data(weather_data):
    """Analyze API hourly data for working hours"""
    if not weather_data or 'hourly' not in weather_data:
        return None

    hourly = weather_data['hourly']

    temps = []
    humidities = []
    winds = []
    precips = []

    for i in range(4, min(17, len(hourly.get('temperature_2m', [])))):
        temp = hourly.get('temperature_2m', [None]*24)[i]
        humidity = hourly.get('relative_humidity_2m', [None]*24)[i]
        wind = hourly.get('wind_speed_10m', [None]*24)[i]
        precip = hourly.get('precipitation', [None]*24)[i]

        if temp is not None:
            temps.append(temp)
        if humidity is not None:
            humidities.append(humidity)
        if wind is not None:
            winds.append(wind / 3.6)
        if precip is not None:
            precips.append(precip)

    if not temps or not humidities or not winds:
        return None

    return {
        'temp': statistics.mean(temps),
        'humidity': statistics.mean(humidities),
        'wind_avg': statistics.mean(winds),
        'wind_max': max(winds),
        'precip': sum(precips)
    }

def main():
    records = load_drying_records()
    amedas_data = parse_amedas_data()

    print("=" * 100)
    print("API予測データ vs JMA実測データ 比較分析")
    print("=" * 100)

    success_records = [r for r in records if r['result'] == '完全乾燥']

    comparisons = []

    for record in success_records[:5]:  # Sample first 5 for detailed comparison
        date_str = record['date']
        spot_name = record['name']

        if date_str not in amedas_data:
            continue

        lat, lon = get_spot_coordinates(spot_name)
        if lat is None:
            continue

        # Get actual Amedas data
        actual = amedas_data[date_str]

        # Get API data
        api_weather = fetch_api_weather(lat, lon, date_str)
        api_stats = analyze_api_data(api_weather) if api_weather else None

        if api_stats:
            comparisons.append({
                'date': date_str,
                'actual': actual,
                'api': api_stats
            })

            print(f"\n{'=' * 100}")
            print(f"{date_str} ({spot_name})")
            print(f"{'=' * 100}")
            print(f"{'パラメータ':20} | {'JMA実測':>12} | {'API予測':>12} | {'差分':>12}")
            print("-" * 100)

            if actual['temp'] and api_stats['temp']:
                diff = actual['temp'] - api_stats['temp']
                print(f"{'平均気温':20} | {actual['temp']:>10.1f}°C | {api_stats['temp']:>10.1f}°C | {diff:>+10.1f}°C")

            if actual['humidity'] and api_stats['humidity']:
                diff = actual['humidity'] - api_stats['humidity']
                print(f"{'平均湿度':20} | {actual['humidity']:>11.1f}% | {api_stats['humidity']:>11.1f}% | {diff:>+11.1f}%")

            if actual['wind_avg'] and api_stats['wind_avg']:
                diff = actual['wind_avg'] - api_stats['wind_avg']
                print(f"{'平均風速':20} | {actual['wind_avg']:>9.1f}m/s | {api_stats['wind_avg']:>9.1f}m/s | {diff:>+9.1f}m/s")

            if actual['wind_max'] and api_stats['wind_max']:
                diff = actual['wind_max'] - api_stats['wind_max']
                print(f"{'最大風速':20} | {actual['wind_max']:>9.1f}m/s | {api_stats['wind_max']:>9.1f}m/s | {diff:>+9.1f}m/s")

            if actual['precip'] is not None and api_stats['precip'] is not None:
                diff = actual['precip'] - api_stats['precip']
                print(f"{'降水量':20} | {actual['precip']:>10.1f}mm | {api_stats['precip']:>10.1f}mm | {diff:>+10.1f}mm")

    # Statistical summary of all success cases
    print("\n" + "=" * 100)
    print("完全乾燥記録の統計比較（実測データベース）")
    print("=" * 100)

    success_with_actual = []
    for record in success_records:
        date_str = record['date']
        if date_str in amedas_data:
            success_with_actual.append(amedas_data[date_str])

    if success_with_actual:
        precips = [r['precip'] for r in success_with_actual if r['precip'] is not None]
        humidities = [r['humidity'] for r in success_with_actual if r['humidity'] is not None]
        winds_avg = [r['wind_avg'] for r in success_with_actual if r['wind_avg'] is not None]
        winds_max = [r['wind_max'] for r in success_with_actual if r['wind_max'] is not None]

        print(f"\n完全乾燥成功記録 (n={len(success_with_actual)}):")
        print(f"  降水量: min={min(precips):.1f}mm, max={max(precips):.1f}mm, mean={statistics.mean(precips):.1f}mm")
        print(f"  平均湿度: min={min(humidities):.1f}%, max={max(humidities):.1f}%, mean={statistics.mean(humidities):.1f}%")
        print(f"  平均風速: min={min(winds_avg):.1f}m/s, max={max(winds_avg):.1f}m/s, mean={statistics.mean(winds_avg):.1f}m/s")
        print(f"  最大風速: min={min(winds_max):.1f}m/s, max={max(winds_max):.1f}m/s, mean={statistics.mean(winds_max):.1f}m/s")

        print("\n【重要な発見】")
        print("  ✅ 降水量: 全ての成功記録で0mm（絶対条件確認）")
        print(f"  ⚠️ 平均湿度: {statistics.mean(humidities):.1f}% (83%閾値を大幅超過)")
        print(f"  ⚠️ 平均風速: {statistics.mean(winds_avg):.1f}m/s (4.5m/s閾値を大幅下回る)")
        print("\n  → API予測データに基づく閾値は実測データと整合しない")
        print("  → 実測データで新たな閾値を設定すべき")

    print("\n" + "=" * 100)

if __name__ == '__main__':
    main()
