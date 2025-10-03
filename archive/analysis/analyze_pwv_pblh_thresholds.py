#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PWV and PBLH threshold analysis based on historical drying records
"""
import csv
import requests
from datetime import datetime, timedelta
import statistics
import sys
import io

# Set stdout to UTF-8
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Import calculation functions from start.py
sys.path.insert(0, '.')
from start import calculate_pwv_from_dewpoint, estimate_pblh_from_conditions

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

def fetch_historical_weather(lat, lon, date):
    """Fetch historical weather data for a specific date"""
    try:
        date_str = date.strftime('%Y-%m-%d')
        url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&hourly=temperature_2m,relative_humidity_2m,wind_speed_10m,wind_direction_10m,cloud_cover,direct_radiation,dewpoint_2m,surface_pressure&start_date={date_str}&end_date={date_str}&timezone=Asia/Tokyo"

        response = requests.get(url, timeout=15)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Error fetching weather for {date_str}: {e}")
        return None

def calculate_daily_pwv_pblh(weather_data):
    """Calculate daily average PWV and PBLH from hourly weather data"""
    if not weather_data or 'hourly' not in weather_data:
        return None, None

    hourly = weather_data['hourly']
    pwv_values = []
    pblh_values = []

    # Focus on working hours (4:00-16:00)
    for i in range(4, min(17, len(hourly.get('temperature_2m', [])))):
        temp = hourly['temperature_2m'][i]
        dewpoint = hourly.get('dewpoint_2m', [None]*24)[i]
        pressure = hourly.get('surface_pressure', [None]*24)[i]
        wind_speed = hourly.get('wind_speed_10m', [None]*24)[i]
        solar = hourly.get('direct_radiation', [None]*24)[i]
        cloud = hourly.get('cloud_cover', [None]*24)[i]

        if all(x is not None for x in [temp, dewpoint, pressure]):
            # Calculate PWV
            pwv = calculate_pwv_from_dewpoint(temp, dewpoint, pressure)
            if pwv is not None:
                pwv_values.append(pwv)

        if all(x is not None for x in [temp, wind_speed, solar, cloud]):
            # Estimate PBLH
            pblh = estimate_pblh_from_conditions(temp, wind_speed/3.6, solar, cloud, i)
            if pblh is not None:
                pblh_values.append(pblh)

    avg_pwv = statistics.mean(pwv_values) if pwv_values else None
    avg_pblh = statistics.mean(pblh_values) if pblh_values else None

    return avg_pwv, avg_pblh

def analyze_records(records_file):
    """Analyze PWV and PBLH thresholds from historical records"""
    records = load_records(records_file)

    success_pwv = []
    success_pblh = []
    partial_pwv = []
    partial_pblh = []
    cancelled_pwv = []
    cancelled_pblh = []

    print("Analyzing historical records...")
    print("=" * 80)

    for idx, record in enumerate(records):
        date_str = record['date']
        spot_name = record['name']
        result = record['result']

        # Parse date
        try:
            date = datetime.strptime(date_str, '%Y-%m-%d')
        except:
            continue

        # Get coordinates
        lat, lon = get_spot_coordinates(spot_name)
        if lat is None or lon is None:
            continue

        # Skip if date is in future
        if date > datetime.now():
            continue

        print(f"\n[{idx+1}/{len(records)}] {date_str} | {spot_name} | {result}")

        # Fetch weather data
        weather_data = fetch_historical_weather(lat, lon, date)
        if weather_data is None:
            print("  ⚠️ Weather data unavailable")
            continue

        # Calculate PWV and PBLH
        avg_pwv, avg_pblh = calculate_daily_pwv_pblh(weather_data)

        if avg_pwv is not None and avg_pblh is not None:
            print(f"  📊 PWV: {avg_pwv:.1f}mm | PBLH: {avg_pblh:.0f}m")

            # Categorize by result
            if result == '完全乾燥':
                success_pwv.append(avg_pwv)
                success_pblh.append(avg_pblh)
            elif result == '干したが完全には乾かせなかった（泣）':
                partial_pwv.append(avg_pwv)
                partial_pblh.append(avg_pblh)
            elif result == '中止':
                cancelled_pwv.append(avg_pwv)
                cancelled_pblh.append(avg_pblh)
        else:
            print("  ⚠️ Could not calculate PWV/PBLH")

    # Statistical analysis
    print("\n" + "=" * 80)
    print("STATISTICAL ANALYSIS")
    print("=" * 80)

    def print_stats(label, pwv_data, pblh_data):
        if pwv_data and pblh_data:
            print(f"\n{label} (n={len(pwv_data)})")
            print(f"  PWV:  min={min(pwv_data):.1f}mm, max={max(pwv_data):.1f}mm, mean={statistics.mean(pwv_data):.1f}mm, median={statistics.median(pwv_data):.1f}mm")
            print(f"  PBLH: min={min(pblh_data):.0f}m, max={max(pblh_data):.0f}m, mean={statistics.mean(pblh_data):.0f}m, median={statistics.median(pblh_data):.0f}m")

    print_stats("✅ 完全乾燥", success_pwv, success_pblh)
    print_stats("⚠️ 部分乾燥", partial_pwv, partial_pblh)
    print_stats("❌ 中止", cancelled_pwv, cancelled_pblh)

    # Threshold recommendations
    print("\n" + "=" * 80)
    print("THRESHOLD RECOMMENDATIONS")
    print("=" * 80)

    if success_pwv and partial_pwv:
        pwv_threshold_75 = statistics.quantiles(success_pwv, n=4)[2]  # 75th percentile
        pwv_threshold_25 = statistics.quantiles(partial_pwv, n=4)[0]  # 25th percentile
        print(f"\n💧 PWV Thresholds:")
        print(f"  Excellent (75th %ile of success): < {pwv_threshold_75:.1f}mm")
        print(f"  Marginal (25th %ile of partial): > {pwv_threshold_25:.1f}mm")

    if success_pblh and partial_pblh:
        pblh_threshold_25 = statistics.quantiles(success_pblh, n=4)[0]  # 25th percentile
        pblh_threshold_75 = statistics.quantiles(partial_pblh, n=4)[2]  # 75th percentile
        print(f"\n🌫️ PBLH Thresholds:")
        print(f"  Excellent (25th %ile of success): > {pblh_threshold_25:.0f}m")
        print(f"  Marginal (75th %ile of partial): < {pblh_threshold_75:.0f}m")

    print("\n" + "=" * 80)

if __name__ == '__main__':
    analyze_records('hoshiba_records.csv')
