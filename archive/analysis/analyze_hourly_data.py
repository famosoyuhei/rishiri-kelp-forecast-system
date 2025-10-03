#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
時別値データ（1時間ごと）の解析
6月23-29日の詳細分析
"""
import csv
import sys
import io
from datetime import datetime
import statistics

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def parse_hourly_data():
    """Parse hourly Amedas data"""
    with open('data.csv', 'r', encoding='cp932') as f:
        lines = f.readlines()

    # Skip download time line
    # Find header
    header_idx = None
    for i, line in enumerate(lines):
        if '年月日' in line or '気温' in line:
            header_idx = i
            break

    if header_idx is None:
        print("ヘッダーが見つかりません")
        return {}

    # Parse first data line to understand structure
    print("=" * 100)
    print("データ構造の確認")
    print("=" * 100)

    # Read headers
    headers = [h.strip() for h in lines[header_idx].split(',')]

    # Find date/time column (first column)
    print(f"最初の列: {headers[0]}")

    # Show first few data lines
    print("\nデータサンプル（最初の3行）:")
    for i in range(header_idx + 4, min(header_idx + 7, len(lines))):
        parts = lines[i].split(',')
        if len(parts) > 0:
            print(f"  {parts[0][:30]}...")

    # Parse data
    hourly_data = {}

    for line in lines[header_idx + 4:]:  # Skip header rows
        if not line.strip():
            continue

        parts = [p.strip() for p in line.split(',')]
        if len(parts) < 10:
            continue

        # First column is date/time
        datetime_str = parts[0]
        if not datetime_str or '/' not in datetime_str:
            continue

        try:
            # Parse datetime (format: 2025/6/23 1:00:00)
            dt = datetime.strptime(datetime_str, '%Y/%m/%d %H:%M:%S')
            date_key = dt.strftime('%Y-%m-%d')
            hour = dt.hour

            # Extract values (need to identify column positions)
            # Columns appear to be: datetime, temp, quality, quality_code, precip, ...
            # Let's extract what we can

            def safe_float(idx):
                if idx >= len(parts):
                    return None
                val = parts[idx]
                if val == '' or val == ']' or val.startswith('8'):  # Quality flags
                    return None
                try:
                    return float(val)
                except:
                    return None

            temp = safe_float(1)  # Column 1: temperature
            precip = safe_float(4)  # Column 4: precipitation
            wind = safe_float(13)  # Column 13: wind speed (guess)
            humidity = safe_float(18)  # Column 18: humidity (guess)

            if date_key not in hourly_data:
                hourly_data[date_key] = {}

            hourly_data[date_key][hour] = {
                'temp': temp,
                'precip': precip,
                'wind': wind,
                'humidity': humidity
            }

        except Exception as e:
            continue

    print(f"\n✅ {len(hourly_data)}日分のデータを読み込みました")

    # Show sample
    for date in sorted(hourly_data.keys())[:2]:
        print(f"\n{date}: {len(hourly_data[date])}時間分")
        hours = sorted(hourly_data[date].keys())[:3]
        for h in hours:
            data = hourly_data[date][h]
            print(f"  {h:02d}:00 - 気温:{data['temp']}°C, 降水:{data['precip']}mm, 風速:{data['wind']}m/s, 湿度:{data['humidity']}%")

    return hourly_data

def analyze_working_hours(hourly_data, date_str):
    """Analyze working hours 4:00-16:00"""
    if date_str not in hourly_data:
        return None

    day_data = hourly_data[date_str]

    temps = []
    precips = []
    winds = []
    humidities = []

    for hour in range(4, 17):  # 4:00-16:00
        if hour not in day_data:
            continue

        h = day_data[hour]
        if h['temp'] is not None:
            temps.append(h['temp'])
        if h['precip'] is not None:
            precips.append(h['precip'])
        if h['wind'] is not None:
            winds.append(h['wind'])
        if h['humidity'] is not None:
            humidities.append(h['humidity'])

    if not temps:
        return None

    return {
        'temp_avg': statistics.mean(temps),
        'temp_min': min(temps),
        'temp_max': max(temps),
        'precip_total': sum(precips),
        'precip_max': max(precips) if precips else 0,
        'wind_avg': statistics.mean(winds) if winds else None,
        'wind_max': max(winds) if winds else None,
        'humidity_avg': statistics.mean(humidities) if humidities else None,
        'humidity_min': min(humidities) if humidities else None,
        'humidity_max': max(humidities) if humidities else None,
    }

def main():
    hourly_data = parse_hourly_data()

    print("\n" + "=" * 100)
    print("作業時間帯（4:00-16:00）の詳細分析")
    print("=" * 100)

    # Target dates with anomalies
    target_dates = ['2025-06-23', '2025-06-29']

    for date in target_dates:
        print(f"\n{'=' * 100}")
        print(f"{date}の詳細")
        print(f"{'=' * 100}")

        analysis = analyze_working_hours(hourly_data, date)

        if analysis:
            print(f"\n作業時間帯サマリー:")
            print(f"  気温: {analysis['temp_min']:.1f}～{analysis['temp_max']:.1f}°C (平均{analysis['temp_avg']:.1f}°C)")
            print(f"  降水: 総計{analysis['precip_total']:.1f}mm (最大{analysis['precip_max']:.1f}mm/h)")
            if analysis['wind_avg']:
                print(f"  風速: 平均{analysis['wind_avg']:.1f}m/s, 最大{analysis['wind_max']:.1f}m/s")
            if analysis['humidity_avg']:
                print(f"  湿度: {analysis['humidity_min']:.0f}～{analysis['humidity_max']:.0f}% (平均{analysis['humidity_avg']:.0f}%)")

        # Hourly detail
        if date in hourly_data:
            print(f"\n時刻別詳細:")
            print(f"{'時刻':>5} | {'気温':>5} | {'降水':>5} | {'風速':>5} | {'湿度':>5}")
            print("-" * 50)

            for hour in range(4, 17):
                if hour in hourly_data[date]:
                    h = hourly_data[date][hour]
                    temp_str = f"{h['temp']:.1f}" if h['temp'] is not None else "N/A"
                    prec_str = f"{h['precip']:.1f}" if h['precip'] is not None else "N/A"
                    wind_str = f"{h['wind']:.1f}" if h['wind'] is not None else "N/A"
                    hum_str = f"{h['humidity']:.0f}" if h['humidity'] is not None else "N/A"

                    print(f"{hour:02d}:00 | {temp_str:>5}°C | {prec_str:>5}mm | {wind_str:>5}m/s | {hum_str:>4}%")

    print("\n" + "=" * 100)

if __name__ == '__main__':
    main()
