#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Validate evidence-based thresholds against actual success records
Check if any successful drying occurred under "risky" conditions
"""
import csv
import requests
from datetime import datetime
import statistics
import sys
import io
import math

# Set stdout to UTF-8
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def load_records(csv_file):
    """Load drying records from CSV"""
    records = []
    with open(csv_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            records.append(row)
    return records

def get_spot_coordinates(spot_name):
    """Extract coordinates from spot name"""
    parts = spot_name.split('_')
    if len(parts) == 3:
        lat = float(parts[1]) / 10000
        lon = float(parts[2]) / 10000
        return lat, lon
    return None, None

def fetch_historical_weather(lat, lon, date):
    """Fetch historical weather data"""
    try:
        date_str = date.strftime('%Y-%m-%d')
        url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&hourly=temperature_2m,relative_humidity_2m,wind_speed_10m,direct_radiation,precipitation,dewpoint_2m,surface_pressure&start_date={date_str}&end_date={date_str}&timezone=Asia/Tokyo"
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        return response.json()
    except:
        try:
            url = f"https://archive-api.open-meteo.com/v1/archive?latitude={lat}&longitude={lon}&start_date={date_str}&end_date={date_str}&hourly=temperature_2m,relative_humidity_2m,wind_speed_10m,direct_radiation,precipitation,dewpoint_2m,surface_pressure&timezone=Asia/Tokyo"
            response = requests.get(url, timeout=15)
            response.raise_for_status()
            return response.json()
        except:
            return None

def calculate_pwv(temperature_c, dewpoint_c, surface_pressure_hpa):
    """Calculate PWV"""
    try:
        es_dewpoint = 6.112 * math.exp(17.67 * dewpoint_c / (dewpoint_c + 243.5))
        pwv = 0.15 * es_dewpoint * ((temperature_c + 273.15) / 273.15)
        return pwv
    except:
        return None

def analyze_working_hours(weather_data):
    """Analyze working hours (4:00-16:00)"""
    if not weather_data or 'hourly' not in weather_data:
        return None

    hourly = weather_data['hourly']

    humidities = []
    winds = []
    precips = []
    pwv_values = []

    for i in range(4, min(17, len(hourly.get('temperature_2m', [])))):
        temp = hourly.get('temperature_2m', [None]*24)[i]
        humidity = hourly.get('relative_humidity_2m', [None]*24)[i]
        wind = hourly.get('wind_speed_10m', [None]*24)[i]
        precip = hourly.get('precipitation', [None]*24)[i]
        dewpoint = hourly.get('dewpoint_2m', [None]*24)[i]
        pressure = hourly.get('surface_pressure', [None]*24)[i]

        if humidity is not None:
            humidities.append(humidity)
        if wind is not None:
            winds.append(wind / 3.6)  # Convert to m/s
        if precip is not None:
            precips.append(precip)

        if temp is not None and dewpoint is not None and pressure is not None:
            pwv = calculate_pwv(temp, dewpoint, pressure)
            if pwv is not None:
                pwv_values.append(pwv)

    if not humidities or not winds:
        return None

    return {
        'min_humidity': min(humidities),
        'avg_humidity': statistics.mean(humidities),
        'max_wind': max(winds),
        'avg_wind': statistics.mean(winds),
        'total_precip': sum(precips),
        'avg_pwv': statistics.mean(pwv_values) if pwv_values else None
    }

def check_threshold_violations(stats):
    """Check which thresholds are violated"""
    violations = []

    # Threshold checks based on historical analysis
    if stats['total_precip'] > 0:
        violations.append(f"降水あり({stats['total_precip']:.1f}mm)")

    if stats['avg_pwv'] is not None and stats['avg_pwv'] > 4.1:
        violations.append(f"PWV高い({stats['avg_pwv']:.1f}mm > 4.1mm)")

    if stats['min_humidity'] > 80:
        violations.append(f"最低湿度高い({stats['min_humidity']:.1f}% > 80%)")

    if stats['avg_humidity'] > 83:
        violations.append(f"平均湿度高い({stats['avg_humidity']:.1f}% > 83%)")

    if stats['max_wind'] > 7.0:
        violations.append(f"最大風速強い({stats['max_wind']:.1f}m/s > 7.0m/s)")

    if stats['avg_wind'] < 4.5:
        violations.append(f"平均風速弱い({stats['avg_wind']:.1f}m/s < 4.5m/s)")

    return violations

def main():
    records = load_records('hoshiba_records.csv')

    print("=" * 100)
    print("閾値検証：完全乾燥記録の分析")
    print("=" * 100)
    print("\n【閾値基準】")
    print("  降水: 0mm (絶対条件)")
    print("  PWV: ≤ 4.1mm (降水リスク)")
    print("  最低湿度: ≤ 80% (乾燥可否)")
    print("  平均湿度: ≤ 83% (乾燥可否)")
    print("  平均風速: ≥ 4.5m/s (乾燥速度)")
    print("  最大風速: ≤ 7.0m/s (作業性)")
    print("\n" + "=" * 100)

    success_records = []
    violations_found = []

    for record in records:
        if record['result'] != '完全乾燥':
            continue

        date_str = record['date']
        spot_name = record['name']

        try:
            date = datetime.strptime(date_str, '%Y-%m-%d')
        except:
            continue

        if date > datetime.now():
            continue

        lat, lon = get_spot_coordinates(spot_name)
        if lat is None or lon is None:
            continue

        weather_data = fetch_historical_weather(lat, lon, date)
        if weather_data is None:
            continue

        stats = analyze_working_hours(weather_data)
        if stats is None:
            continue

        violations = check_threshold_violations(stats)

        success_records.append({
            'date': date_str,
            'spot': spot_name,
            'stats': stats,
            'violations': violations
        })

        if violations:
            violations_found.append({
                'date': date_str,
                'spot': spot_name,
                'stats': stats,
                'violations': violations
            })

    print(f"\n完全乾燥記録: {len(success_records)}件")
    print(f"閾値違反あり: {len(violations_found)}件")

    if violations_found:
        print("\n" + "=" * 100)
        print("⚠️ 閾値を超えても成功した記録（例外ケース）")
        print("=" * 100)

        for i, record in enumerate(violations_found, 1):
            print(f"\n【{i}】 {record['date']} | {record['spot']}")
            stats = record['stats']
            print(f"  降水量: {stats['total_precip']:.1f}mm")
            print(f"  PWV: {stats['avg_pwv']:.1f}mm" if stats['avg_pwv'] else "  PWV: N/A")
            print(f"  最低湿度: {stats['min_humidity']:.1f}%")
            print(f"  平均湿度: {stats['avg_humidity']:.1f}%")
            print(f"  平均風速: {stats['avg_wind']:.1f}m/s")
            print(f"  最大風速: {stats['max_wind']:.1f}m/s")
            print(f"  違反項目:")
            for v in record['violations']:
                print(f"    - {v}")
    else:
        print("\n✅ 全ての完全乾燥記録が閾値基準を満たしています")

    # Statistics on compliant records
    compliant_records = [r for r in success_records if not r['violations']]

    print("\n" + "=" * 100)
    print(f"基準適合記録の統計 (n={len(compliant_records)})")
    print("=" * 100)

    if compliant_records:
        pwv_vals = [r['stats']['avg_pwv'] for r in compliant_records if r['stats']['avg_pwv'] is not None]
        min_hum = [r['stats']['min_humidity'] for r in compliant_records]
        avg_hum = [r['stats']['avg_humidity'] for r in compliant_records]
        avg_wind = [r['stats']['avg_wind'] for r in compliant_records]
        max_wind = [r['stats']['max_wind'] for r in compliant_records]

        if pwv_vals:
            print(f"\nPWV: min={min(pwv_vals):.1f}mm, max={max(pwv_vals):.1f}mm, mean={statistics.mean(pwv_vals):.1f}mm")
        print(f"最低湿度: min={min(min_hum):.1f}%, max={max(min_hum):.1f}%, mean={statistics.mean(min_hum):.1f}%")
        print(f"平均湿度: min={min(avg_hum):.1f}%, max={max(avg_hum):.1f}%, mean={statistics.mean(avg_hum):.1f}%")
        print(f"平均風速: min={min(avg_wind):.1f}m/s, max={max(avg_wind):.1f}m/s, mean={statistics.mean(avg_wind):.1f}m/s")
        print(f"最大風速: min={min(max_wind):.1f}m/s, max={max(max_wind):.1f}m/s, mean={statistics.mean(max_wind):.1f}m/s")

    print("\n" + "=" * 100)

if __name__ == '__main__':
    main()
