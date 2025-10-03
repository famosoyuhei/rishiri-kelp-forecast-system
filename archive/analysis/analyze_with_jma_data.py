#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Historical weather data analysis using JMA (Japan Meteorological Agency) data
Focus on all records including pre-July 15 data
"""
import csv
import requests
from datetime import datetime, timedelta
import statistics
import sys
import io
import time

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
    """Extract coordinates from spot name (format: H_LLLL_NNNN)"""
    parts = spot_name.split('_')
    if len(parts) == 3:
        lat = float(parts[1]) / 10000
        lon = float(parts[2]) / 10000
        return lat, lon
    return None, None

def fetch_jma_amedas_data(lat, lon, date):
    """
    Fetch JMA AMeDAS data for Rishiri Island
    Station: Rishiri (利尻) - Station ID: 44136
    """
    try:
        # JMA API endpoint for historical data
        # Note: This is a simplified approach. Real implementation may need different method.

        # For now, we'll use Open-Meteo's historical data endpoint which has more data
        # Open-Meteo Historical API (not forecast) has data going back to 1940
        date_str = date.strftime('%Y-%m-%d')

        # Try Open-Meteo Historical/Archive endpoint
        url = f"https://archive-api.open-meteo.com/v1/archive?latitude={lat}&longitude={lon}&start_date={date_str}&end_date={date_str}&hourly=temperature_2m,relative_humidity_2m,wind_speed_10m,direct_radiation,cloud_cover,precipitation&timezone=Asia/Tokyo"

        response = requests.get(url, timeout=15)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        # Fallback: try regular forecast API (works for recent data)
        try:
            url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&hourly=temperature_2m,relative_humidity_2m,wind_speed_10m,direct_radiation,cloud_cover,precipitation&start_date={date_str}&end_date={date_str}&timezone=Asia/Tokyo"
            response = requests.get(url, timeout=15)
            response.raise_for_status()
            return response.json()
        except:
            print(f"    ⚠️ データ取得失敗: {e}")
            return None

def calculate_working_hours_stats(weather_data):
    """Calculate statistics for working hours (4:00-16:00)"""
    if not weather_data or 'hourly' not in weather_data:
        return None

    hourly = weather_data['hourly']

    # Working hours data
    temps = []
    humidities = []
    wind_speeds = []
    solar_radiations = []
    cloud_covers = []
    precips = []

    # Focus on working hours (4:00-16:00)
    for i in range(4, min(17, len(hourly.get('temperature_2m', [])))):
        temp = hourly.get('temperature_2m', [None]*24)[i]
        humidity = hourly.get('relative_humidity_2m', [None]*24)[i]
        wind = hourly.get('wind_speed_10m', [None]*24)[i]
        solar = hourly.get('direct_radiation', [None]*24)[i]
        cloud = hourly.get('cloud_cover', [None]*24)[i]
        precip = hourly.get('precipitation', [None]*24)[i]

        if temp is not None:
            temps.append(temp)
        if humidity is not None:
            humidities.append(humidity)
        if wind is not None:
            wind_speeds.append(wind / 3.6)  # Convert km/h to m/s
        if solar is not None:
            solar_radiations.append(solar)
        if cloud is not None:
            cloud_covers.append(cloud)
        if precip is not None:
            precips.append(precip)

    if not temps or not humidities or not wind_speeds:
        return None

    return {
        'temp_avg': statistics.mean(temps),
        'temp_max': max(temps),
        'temp_min': min(temps),
        'humidity_avg': statistics.mean(humidities),
        'humidity_min': min(humidities),
        'humidity_max': max(humidities),
        'wind_avg': statistics.mean(wind_speeds),
        'wind_max': max(wind_speeds),
        'wind_min': min(wind_speeds),
        'solar_avg': statistics.mean(solar_radiations) if solar_radiations else 0,
        'solar_max': max(solar_radiations) if solar_radiations else 0,
        'solar_total': sum(solar_radiations) if solar_radiations else 0,
        'cloud_avg': statistics.mean(cloud_covers) if cloud_covers else None,
        'precip_total': sum(precips) if precips else 0
    }

def analyze_all_records(records_file):
    """Analyze ALL records including June and early July"""
    records = load_records(records_file)

    # Data storage by result type
    success_data = []
    partial_data = []
    cancelled_data = []

    print("=" * 80)
    print("全記録の気象データ分析（Open-Meteo Archive API使用）")
    print("=" * 80)
    print(f"総記録数: {len(records)}件\n")

    successful_fetches = 0
    failed_fetches = 0

    for idx, record in enumerate(records):
        date_str = record['date']
        spot_name = record['name']
        result = record['result']

        # Parse date
        try:
            date = datetime.strptime(date_str, '%Y-%m-%d')
        except:
            continue

        # Skip if date is in future
        if date > datetime.now():
            continue

        # Get coordinates
        lat, lon = get_spot_coordinates(spot_name)
        if lat is None or lon is None:
            continue

        print(f"[{idx+1}/{len(records)}] {date_str} | {result[:10]}...", end='')

        # Fetch weather data with retry
        weather_data = None
        for attempt in range(2):
            weather_data = fetch_jma_amedas_data(lat, lon, date)
            if weather_data:
                break
            time.sleep(1)

        if weather_data is None:
            print(" ❌ データなし")
            failed_fetches += 1
            continue

        # Calculate working hours statistics
        stats = calculate_working_hours_stats(weather_data)

        if stats is None:
            print(" ❌ 統計計算失敗")
            failed_fetches += 1
            continue

        successful_fetches += 1
        print(f" ✅ T:{stats['temp_avg']:.1f}°C H:{stats['humidity_avg']:.0f}% W:{stats['wind_avg']:.1f}m/s")

        # Categorize by result
        if result == '完全乾燥':
            success_data.append(stats)
        elif result == '干したが完全には乾かせなかった（泣）':
            partial_data.append(stats)
        elif result == '中止':
            cancelled_data.append(stats)

    # Report
    print("\n" + "=" * 80)
    print(f"データ取得結果: 成功 {successful_fetches}件 / 失敗 {failed_fetches}件")
    print("=" * 80)

    # Statistical analysis
    print("\n" + "=" * 80)
    print("統計分析結果")
    print("=" * 80)

    def print_stats(label, data):
        if data:
            print(f"\n{label} (n={len(data)})")

            params = [
                ('temp_avg', '平均気温', '°C'),
                ('temp_max', '最高気温', '°C'),
                ('humidity_avg', '平均湿度', '%'),
                ('humidity_min', '最低湿度', '%'),
                ('wind_avg', '平均風速', 'm/s'),
                ('wind_max', '最大風速', 'm/s'),
                ('solar_avg', '平均日射', 'W/m²'),
                ('solar_total', '積算日射', 'Wh/m²'),
                ('precip_total', '総降水量', 'mm')
            ]

            for param, label_jp, unit in params:
                values = [d[param] for d in data]
                print(f"  {label_jp:8}: min={min(values):6.1f}{unit:4} max={max(values):6.1f}{unit:4} "
                      f"mean={statistics.mean(values):6.1f}{unit:4} median={statistics.median(values):6.1f}{unit:4}")

    print_stats("✅ 完全乾燥", success_data)
    print_stats("⚠️ 部分乾燥", partial_data)
    print_stats("❌ 中止", cancelled_data)

    params = [
        ('temp_avg', '平均気温', '°C'),
        ('temp_max', '最高気温', '°C'),
        ('humidity_avg', '平均湿度', '%'),
        ('humidity_min', '最低湿度', '%'),
        ('wind_avg', '平均風速', 'm/s'),
        ('wind_max', '最大風速', 'm/s'),
        ('solar_avg', '平均日射', 'W/m²'),
        ('solar_total', '積算日射', 'Wh/m²'),
        ('precip_total', '総降水量', 'mm')
    ]

    # Discrimination analysis: Success vs Partial
    if success_data and partial_data:
        print("\n" + "=" * 80)
        print("判別力分析（完全乾燥 vs 部分乾燥）")
        print("=" * 80)

        effect_sizes = []

        for param, label_jp, unit in params:
            s_vals = [d[param] for d in success_data]
            p_vals = [d[param] for d in partial_data]

            s_mean = statistics.mean(s_vals)
            p_mean = statistics.mean(p_vals)
            s_std = statistics.stdev(s_vals) if len(s_vals) > 1 else 1
            p_std = statistics.stdev(p_vals) if len(p_vals) > 1 else 1

            pooled_std = ((s_std**2 + p_std**2) / 2) ** 0.5
            effect = abs(s_mean - p_mean) / pooled_std if pooled_std > 0 else 0

            effect_sizes.append((label_jp, s_mean, p_mean, effect, unit))

        print("\nパラメータ       | 成功平均  | 失敗平均  | 効果量 | 判別力")
        print("-" * 80)

        for label, s_mean, p_mean, effect, unit in effect_sizes:
            interpretation = (
                "⭐⭐⭐" if effect > 0.8 else
                "⭐⭐ " if effect > 0.5 else
                "⭐  " if effect > 0.2 else
                "❌ "
            )
            print(f"{label:12} | {s_mean:8.1f}{unit:3} | {p_mean:8.1f}{unit:3} | {effect:6.3f} | {interpretation}")

        print("\n" + "=" * 80)
        print("重要度ランキング")
        print("=" * 80)

        effect_sizes.sort(key=lambda x: x[3], reverse=True)
        for i, (label, s_mean, p_mean, effect, unit) in enumerate(effect_sizes, 1):
            print(f"{i}. {label:12} | 効果量: {effect:.3f}")

    # Discrimination analysis: Success vs Cancelled
    if success_data and cancelled_data:
        print("\n" + "=" * 80)
        print("判別力分析（完全乾燥 vs 中止）")
        print("=" * 80)

        effect_sizes_cancelled = []

        for param, label_jp, unit in params:
            s_vals = [d[param] for d in success_data]
            c_vals = [d[param] for d in cancelled_data]

            s_mean = statistics.mean(s_vals)
            c_mean = statistics.mean(c_vals)
            s_std = statistics.stdev(s_vals) if len(s_vals) > 1 else 1
            c_std = statistics.stdev(c_vals) if len(c_vals) > 1 else 1

            pooled_std = ((s_std**2 + c_std**2) / 2) ** 0.5
            effect = abs(s_mean - c_mean) / pooled_std if pooled_std > 0 else 0

            effect_sizes_cancelled.append((label_jp, s_mean, c_mean, effect, unit))

        print("\nパラメータ       | 成功平均  | 中止平均  | 効果量 | 判別力")
        print("-" * 80)

        for label, s_mean, c_mean, effect, unit in effect_sizes_cancelled:
            interpretation = (
                "⭐⭐⭐" if effect > 0.8 else
                "⭐⭐ " if effect > 0.5 else
                "⭐  " if effect > 0.2 else
                "❌ "
            )
            print(f"{label:12} | {s_mean:8.1f}{unit:3} | {c_mean:8.1f}{unit:3} | {effect:6.3f} | {interpretation}")

        print("\n" + "=" * 80)
        print("重要度ランキング（完全乾燥 vs 中止）")
        print("=" * 80)

        effect_sizes_cancelled.sort(key=lambda x: x[3], reverse=True)
        for i, (label, s_mean, c_mean, effect, unit) in enumerate(effect_sizes_cancelled, 1):
            print(f"{i}. {label:12} | 効果量: {effect:.3f}")

    # Discrimination analysis: Partial vs Cancelled
    if partial_data and cancelled_data:
        print("\n" + "=" * 80)
        print("判別力分析（部分乾燥 vs 中止）")
        print("=" * 80)

        effect_sizes_partial_cancelled = []

        for param, label_jp, unit in params:
            p_vals = [d[param] for d in partial_data]
            c_vals = [d[param] for d in cancelled_data]

            p_mean = statistics.mean(p_vals)
            c_mean = statistics.mean(c_vals)
            p_std = statistics.stdev(p_vals) if len(p_vals) > 1 else 1
            c_std = statistics.stdev(c_vals) if len(c_vals) > 1 else 1

            pooled_std = ((p_std**2 + c_std**2) / 2) ** 0.5
            effect = abs(p_mean - c_mean) / pooled_std if pooled_std > 0 else 0

            effect_sizes_partial_cancelled.append((label_jp, p_mean, c_mean, effect, unit))

        print("\nパラメータ       | 部分平均  | 中止平均  | 効果量 | 判別力")
        print("-" * 80)

        for label, p_mean, c_mean, effect, unit in effect_sizes_partial_cancelled:
            interpretation = (
                "⭐⭐⭐" if effect > 0.8 else
                "⭐⭐ " if effect > 0.5 else
                "⭐  " if effect > 0.2 else
                "❌ "
            )
            print(f"{label:12} | {p_mean:8.1f}{unit:3} | {c_mean:8.1f}{unit:3} | {effect:6.3f} | {interpretation}")

        print("\n" + "=" * 80)
        print("重要度ランキング（部分乾燥 vs 中止）")
        print("=" * 80)

        effect_sizes_partial_cancelled.sort(key=lambda x: x[3], reverse=True)
        for i, (label, p_mean, c_mean, effect, unit) in enumerate(effect_sizes_partial_cancelled, 1):
            print(f"{i}. {label:12} | 効果量: {effect:.3f}")

    print("\n" + "=" * 80)

if __name__ == '__main__':
    print("\n⚠️ 注意: Open-Meteo Archive APIを使用します")
    print("   無料版は制限があるため、すべてのデータが取得できない可能性があります\n")

    analyze_all_records('hoshiba_records.csv')
