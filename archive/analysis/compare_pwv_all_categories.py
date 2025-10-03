#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PWV comparison across all categories (Success, Partial, Cancelled)
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
        url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&hourly=temperature_2m,relative_humidity_2m,dewpoint_2m,surface_pressure&start_date={date_str}&end_date={date_str}&timezone=Asia/Tokyo"

        response = requests.get(url, timeout=15)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        # Try archive API
        try:
            url = f"https://archive-api.open-meteo.com/v1/archive?latitude={lat}&longitude={lon}&start_date={date_str}&end_date={date_str}&hourly=temperature_2m,relative_humidity_2m,dewpoint_2m,surface_pressure&timezone=Asia/Tokyo"
            response = requests.get(url, timeout=15)
            response.raise_for_status()
            return response.json()
        except:
            return None

def calculate_pwv_from_dewpoint(temperature_c, dewpoint_c, surface_pressure_hpa):
    """Calculate PWV from dewpoint and surface pressure using empirical formula"""
    try:
        # Saturation vapor pressure at dewpoint (hPa) - Magnus formula
        es_dewpoint = 6.112 * math.exp(17.67 * dewpoint_c / (dewpoint_c + 243.5))

        # Empirical PWV formula from surface vapor pressure
        # PWV (mm) ≈ 0.15 * e_s (hPa) * (T/273.15)
        pwv = 0.15 * es_dewpoint * ((temperature_c + 273.15) / 273.15)

        return pwv
    except:
        return None

def calculate_pwv_stats(weather_data):
    """Calculate PWV statistics for working hours (4:00-16:00)"""
    if not weather_data or 'hourly' not in weather_data:
        return None

    hourly = weather_data['hourly']
    pwv_values = []

    # Focus on working hours (4:00-16:00)
    for i in range(4, min(17, len(hourly.get('temperature_2m', [])))):
        temp = hourly.get('temperature_2m', [None]*24)[i]
        dewpoint = hourly.get('dewpoint_2m', [None]*24)[i]
        pressure = hourly.get('surface_pressure', [None]*24)[i]

        if temp is not None and dewpoint is not None and pressure is not None:
            pwv = calculate_pwv_from_dewpoint(temp, dewpoint, pressure)
            if pwv is not None:
                pwv_values.append(pwv)

    if not pwv_values:
        return None

    return {
        'pwv_avg': statistics.mean(pwv_values),
        'pwv_max': max(pwv_values),
        'pwv_min': min(pwv_values)
    }

def analyze_all_records():
    """Compare PWV across all categories"""
    records = load_records('hoshiba_records.csv')

    success_pwv = []
    partial_pwv = []
    cancelled_pwv = []

    print("=" * 80)
    print("PWV分析（全記録）")
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

        # Skip if date is in future
        if date > datetime.now():
            continue

        # Get coordinates
        lat, lon = get_spot_coordinates(spot_name)
        if lat is None or lon is None:
            continue

        print(f"[{idx+1}/{len(records)}] {date_str} | {result[:10]}...", end='')

        # Fetch weather data
        weather_data = fetch_historical_weather(lat, lon, date)
        if weather_data is None:
            print(" ❌")
            continue

        # Calculate PWV
        pwv_stats = calculate_pwv_stats(weather_data)
        if pwv_stats is None:
            print(" ❌")
            continue

        print(f" ✅ PWV:{pwv_stats['pwv_avg']:.1f}mm")

        # Categorize by result
        if result == '完全乾燥':
            success_pwv.append(pwv_stats['pwv_avg'])
        elif result == '干したが完全には乾かせなかった（泣）':
            partial_pwv.append(pwv_stats['pwv_avg'])
        elif result == '中止':
            cancelled_pwv.append(pwv_stats['pwv_avg'])

    # Statistical analysis
    print("\n" + "=" * 80)
    print("PWV統計分析")
    print("=" * 80)

    def print_pwv_stats(label, pwv_data):
        if pwv_data:
            print(f"\n{label} (n={len(pwv_data)})")
            print(f"  PWV: min={min(pwv_data):.1f}mm, max={max(pwv_data):.1f}mm, mean={statistics.mean(pwv_data):.1f}mm, median={statistics.median(pwv_data):.1f}mm")

    print_pwv_stats("✅ 完全乾燥", success_pwv)
    print_pwv_stats("⚠️ 部分乾燥", partial_pwv)
    print_pwv_stats("❌ 中止", cancelled_pwv)

    # Discrimination analysis
    if success_pwv and partial_pwv:
        print("\n" + "=" * 80)
        print("判別力分析（完全乾燥 vs 部分乾燥）")
        print("=" * 80)

        s_mean = statistics.mean(success_pwv)
        p_mean = statistics.mean(partial_pwv)
        s_std = statistics.stdev(success_pwv) if len(success_pwv) > 1 else 1
        p_std = statistics.stdev(partial_pwv) if len(partial_pwv) > 1 else 1

        pooled_std = ((s_std**2 + p_std**2) / 2) ** 0.5
        effect = abs(s_mean - p_mean) / pooled_std if pooled_std > 0 else 0

        print(f"\n完全乾燥 PWV平均: {s_mean:.1f}mm")
        print(f"部分乾燥 PWV平均: {p_mean:.1f}mm")
        print(f"効果量 (Cohen's d): {effect:.3f}")

        interpretation = (
            "⭐⭐⭐ (Large)" if effect > 0.8 else
            "⭐⭐ (Medium)" if effect > 0.5 else
            "⭐ (Small)" if effect > 0.2 else
            "❌ (Negligible)"
        )
        print(f"判別力: {interpretation}")

    if success_pwv and cancelled_pwv:
        print("\n" + "=" * 80)
        print("判別力分析（完全乾燥 vs 中止）")
        print("=" * 80)

        s_mean = statistics.mean(success_pwv)
        c_mean = statistics.mean(cancelled_pwv)
        s_std = statistics.stdev(success_pwv) if len(success_pwv) > 1 else 1
        c_std = statistics.stdev(cancelled_pwv) if len(cancelled_pwv) > 1 else 1

        pooled_std = ((s_std**2 + c_std**2) / 2) ** 0.5
        effect = abs(s_mean - c_mean) / pooled_std if pooled_std > 0 else 0

        print(f"\n完全乾燥 PWV平均: {s_mean:.1f}mm")
        print(f"中止 PWV平均: {c_mean:.1f}mm")
        print(f"効果量 (Cohen's d): {effect:.3f}")

        interpretation = (
            "⭐⭐⭐ (Large)" if effect > 0.8 else
            "⭐⭐ (Medium)" if effect > 0.5 else
            "⭐ (Small)" if effect > 0.2 else
            "❌ (Negligible)"
        )
        print(f"判別力: {interpretation}")

    print("\n" + "=" * 80)

if __name__ == '__main__':
    analyze_all_records()
