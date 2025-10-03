#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Surface meteorological parameters analysis for kelp drying
Focus on direct factors: temperature, humidity, wind speed, solar radiation
"""
import csv
import requests
from datetime import datetime
import statistics
import sys
import io

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
        url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&hourly=temperature_2m,relative_humidity_2m,wind_speed_10m,direct_radiation,cloud_cover,precipitation&start_date={date_str}&end_date={date_str}&timezone=Asia/Tokyo"

        response = requests.get(url, timeout=15)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"  ⚠️ Weather data error: {e}")
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

    # Focus on working hours (4:00-16:00) - indices 4 to 16
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

    if not temps or not humidities or not wind_speeds or not solar_radiations:
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
        'solar_avg': statistics.mean(solar_radiations),
        'solar_max': max(solar_radiations),
        'solar_total': sum(solar_radiations),
        'cloud_avg': statistics.mean(cloud_covers) if cloud_covers else None,
        'precip_total': sum(precips) if precips else 0
    }

def analyze_records(records_file):
    """Analyze surface meteorological parameters from historical records"""
    records = load_records(records_file)

    # Data storage by result type
    success_data = []
    partial_data = []
    cancelled_data = []

    print("Analyzing surface meteorological parameters...")
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

        print(f"\n[{idx+1}/{len(records)}] {date_str} | {spot_name[:12]}... | {result}")

        # Fetch weather data
        weather_data = fetch_historical_weather(lat, lon, date)
        if weather_data is None:
            continue

        # Calculate working hours statistics
        stats = calculate_working_hours_stats(weather_data)

        if stats is None:
            print("  ⚠️ Could not calculate statistics")
            continue

        # Display key parameters
        print(f"  🌡️  Temp: {stats['temp_avg']:.1f}°C (max {stats['temp_max']:.1f}°C)")
        print(f"  💧 Humid: {stats['humidity_avg']:.0f}% (min {stats['humidity_min']:.0f}%)")
        print(f"  🌬️  Wind: {stats['wind_avg']:.1f}m/s (max {stats['wind_max']:.1f}m/s)")
        print(f"  ☀️  Solar: {stats['solar_avg']:.0f}W/m² (max {stats['solar_max']:.0f}W/m²)")

        # Categorize by result
        if result == '完全乾燥':
            success_data.append(stats)
        elif result == '干したが完全には乾かせなかった（泣）':
            partial_data.append(stats)
        elif result == '中止':
            cancelled_data.append(stats)

    # Statistical analysis
    print("\n" + "=" * 80)
    print("STATISTICAL ANALYSIS - SURFACE PARAMETERS")
    print("=" * 80)

    def print_param_stats(label, data, param_name, unit):
        if data:
            values = [d[param_name] for d in data]
            print(f"  {label}: min={min(values):.1f}{unit}, max={max(values):.1f}{unit}, "
                  f"mean={statistics.mean(values):.1f}{unit}, median={statistics.median(values):.1f}{unit}")

    def print_category_stats(label, data):
        if data:
            print(f"\n{label} (n={len(data)})")
            print_param_stats("Temperature Avg", data, 'temp_avg', '°C')
            print_param_stats("Temperature Max", data, 'temp_max', '°C')
            print_param_stats("Humidity Avg", data, 'humidity_avg', '%')
            print_param_stats("Humidity Min", data, 'humidity_min', '%')
            print_param_stats("Wind Avg", data, 'wind_avg', 'm/s')
            print_param_stats("Wind Max", data, 'wind_max', 'm/s')
            print_param_stats("Solar Avg", data, 'solar_avg', 'W/m²')
            print_param_stats("Solar Max", data, 'solar_max', 'W/m²')
            print_param_stats("Precipitation Total", data, 'precip_total', 'mm')

    print_category_stats("✅ 完全乾燥", success_data)
    print_category_stats("⚠️ 部分乾燥", partial_data)
    print_category_stats("❌ 中止", cancelled_data)

    # Threshold recommendations
    print("\n" + "=" * 80)
    print("THRESHOLD RECOMMENDATIONS - BASED ON ACTUAL DATA")
    print("=" * 80)

    def calculate_thresholds(success_data, partial_data, param_name, higher_is_better):
        if not success_data or not partial_data:
            return None, None

        success_values = [d[param_name] for d in success_data]
        partial_values = [d[param_name] for d in partial_data]

        if higher_is_better:
            # For parameters where higher is better (temp, wind, solar)
            success_25th = statistics.quantiles(success_values, n=4)[0]  # 25th percentile
            partial_75th = statistics.quantiles(partial_values, n=4)[2]  # 75th percentile
            return success_25th, partial_75th
        else:
            # For parameters where lower is better (humidity)
            success_75th = statistics.quantiles(success_values, n=4)[2]  # 75th percentile
            partial_25th = statistics.quantiles(partial_values, n=4)[0]  # 25th percentile
            return success_75th, partial_25th

    if success_data and partial_data:
        print("\n🌡️ TEMPERATURE (higher is better)")
        temp_good, temp_marginal = calculate_thresholds(success_data, partial_data, 'temp_avg', True)
        if temp_good and temp_marginal:
            print(f"  Excellent (25th %ile of success): > {temp_good:.1f}°C")
            print(f"  Marginal (75th %ile of partial): < {temp_marginal:.1f}°C")

        print("\n💧 HUMIDITY (lower is better)")
        humid_good, humid_marginal = calculate_thresholds(success_data, partial_data, 'humidity_avg', False)
        if humid_good and humid_marginal:
            print(f"  Excellent (75th %ile of success): < {humid_good:.0f}%")
            print(f"  Marginal (25th %ile of partial): > {humid_marginal:.0f}%")

        print("\n🌬️ WIND SPEED (higher is better)")
        wind_good, wind_marginal = calculate_thresholds(success_data, partial_data, 'wind_avg', True)
        if wind_good and wind_marginal:
            print(f"  Excellent (25th %ile of success): > {wind_good:.2f}m/s")
            print(f"  Marginal (75th %ile of partial): < {wind_marginal:.2f}m/s")

        wind_max_good, wind_max_marginal = calculate_thresholds(success_data, partial_data, 'wind_max', True)
        if wind_max_good and wind_max_marginal:
            print(f"  Max Wind - Excellent: > {wind_max_good:.2f}m/s")
            print(f"  Max Wind - Marginal: < {wind_max_marginal:.2f}m/s")

        print("\n☀️ SOLAR RADIATION (higher is better)")
        solar_good, solar_marginal = calculate_thresholds(success_data, partial_data, 'solar_avg', True)
        if solar_good and solar_marginal:
            print(f"  Excellent (25th %ile of success): > {solar_good:.0f}W/m²")
            print(f"  Marginal (75th %ile of partial): < {solar_marginal:.0f}W/m²")

    # Correlation analysis
    print("\n" + "=" * 80)
    print("DISCRIMINATION POWER (Success vs Partial)")
    print("=" * 80)

    if success_data and partial_data:
        def calc_separation(success_data, partial_data, param):
            s_mean = statistics.mean([d[param] for d in success_data])
            p_mean = statistics.mean([d[param] for d in partial_data])
            s_std = statistics.stdev([d[param] for d in success_data]) if len(success_data) > 1 else 1
            p_std = statistics.stdev([d[param] for d in partial_data]) if len(partial_data) > 1 else 1
            # Effect size (Cohen's d)
            pooled_std = ((s_std**2 + p_std**2) / 2) ** 0.5
            if pooled_std > 0:
                effect_size = abs(s_mean - p_mean) / pooled_std
            else:
                effect_size = 0
            return s_mean, p_mean, effect_size

        params = [
            ('temp_avg', 'Temperature Avg', '°C'),
            ('temp_max', 'Temperature Max', '°C'),
            ('humidity_avg', 'Humidity Avg', '%'),
            ('humidity_min', 'Humidity Min', '%'),
            ('wind_avg', 'Wind Avg', 'm/s'),
            ('wind_max', 'Wind Max', 'm/s'),
            ('solar_avg', 'Solar Avg', 'W/m²'),
            ('solar_max', 'Solar Max', 'W/m²'),
            ('precip_total', 'Precipitation', 'mm')
        ]

        print("\nParameter | Success Mean | Partial Mean | Effect Size (Cohen's d)")
        print("-" * 80)

        effect_sizes = []
        for param, label, unit in params:
            s_mean, p_mean, effect = calc_separation(success_data, partial_data, param)
            effect_sizes.append((label, effect))
            print(f"{label:20} | {s_mean:8.2f}{unit:4} | {p_mean:8.2f}{unit:4} | {effect:6.3f}")

        print("\n" + "=" * 80)
        print("RANKED BY DISCRIMINATION POWER")
        print("=" * 80)
        effect_sizes.sort(key=lambda x: x[1], reverse=True)
        for i, (label, effect) in enumerate(effect_sizes, 1):
            interpretation = (
                "Large (>0.8)" if effect > 0.8 else
                "Medium (0.5-0.8)" if effect > 0.5 else
                "Small (0.2-0.5)" if effect > 0.2 else
                "Negligible (<0.2)"
            )
            print(f"{i}. {label:20} | Effect Size: {effect:.3f} | {interpretation}")

    print("\n" + "=" * 80)

if __name__ == '__main__':
    analyze_records('hoshiba_records.csv')
