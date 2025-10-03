#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
部分乾燥で降水がなかった記録の詳細分析
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
        url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&hourly=temperature_2m,relative_humidity_2m,wind_speed_10m,direct_radiation,cloud_cover,precipitation,dewpoint_2m,surface_pressure&start_date={date_str}&end_date={date_str}&timezone=Asia/Tokyo"

        response = requests.get(url, timeout=15)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        # Try archive API
        try:
            url = f"https://archive-api.open-meteo.com/v1/archive?latitude={lat}&longitude={lon}&start_date={date_str}&end_date={date_str}&hourly=temperature_2m,relative_humidity_2m,wind_speed_10m,direct_radiation,cloud_cover,precipitation,dewpoint_2m,surface_pressure&timezone=Asia/Tokyo"
            response = requests.get(url, timeout=15)
            response.raise_for_status()
            return response.json()
        except:
            return None

def calculate_pwv_from_dewpoint(temperature_c, dewpoint_c, surface_pressure_hpa):
    """Calculate PWV from dewpoint and surface pressure"""
    import math
    try:
        # Saturation vapor pressure at dewpoint (hPa)
        es_dewpoint = 6.112 * math.exp(17.67 * dewpoint_c / (dewpoint_c + 243.5))
        # Mixing ratio (kg/kg)
        mixing_ratio = 0.622 * es_dewpoint / (surface_pressure_hpa - es_dewpoint)
        # Specific humidity (kg/kg)
        specific_humidity = mixing_ratio / (1 + mixing_ratio)

        # PWV (mm) using proper scale height
        # PWV = (q * P) / (ρ_water * g)
        # where q is in kg/kg, P in Pa, result in meters
        # Convert to mm: multiply by 1000

        g = 9.81  # m/s²
        rho_water = 1000  # kg/m³
        pressure_pa = surface_pressure_hpa * 100  # Convert hPa to Pa

        # Empirical PWV formula from surface vapor pressure
        # PWV (mm) ≈ 0.15 * e_s (hPa) * (T/273.15)
        # This accounts for exponential moisture decay
        pwv = 0.15 * es_dewpoint * ((temperature_c + 273.15) / 273.15)
        return pwv
    except:
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
    pwv_values = []

    # Focus on working hours (4:00-16:00)
    for i in range(4, min(17, len(hourly.get('temperature_2m', [])))):
        temp = hourly.get('temperature_2m', [None]*24)[i]
        humidity = hourly.get('relative_humidity_2m', [None]*24)[i]
        wind = hourly.get('wind_speed_10m', [None]*24)[i]
        solar = hourly.get('direct_radiation', [None]*24)[i]
        cloud = hourly.get('cloud_cover', [None]*24)[i]
        precip = hourly.get('precipitation', [None]*24)[i]
        dewpoint = hourly.get('dewpoint_2m', [None]*24)[i]
        pressure = hourly.get('surface_pressure', [None]*24)[i]

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

        # Calculate PWV
        if temp is not None and dewpoint is not None and pressure is not None:
            pwv = calculate_pwv_from_dewpoint(temp, dewpoint, pressure)
            if pwv is not None:
                pwv_values.append(pwv)

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
        'precip_total': sum(precips) if precips else 0,
        'pwv_avg': statistics.mean(pwv_values) if pwv_values else None,
        'pwv_max': max(pwv_values) if pwv_values else None,
        'pwv_min': min(pwv_values) if pwv_values else None
    }

def analyze_partial_no_rain():
    """部分乾燥で降水がなかった記録を抽出"""
    records = load_records('hoshiba_records.csv')

    partial_no_rain = []

    print("=" * 80)
    print("部分乾燥記録の降水量分析")
    print("=" * 80)

    for record in records:
        date_str = record['date']
        spot_name = record['name']
        result = record['result']

        # Only analyze partial drying
        if result != '干したが完全には乾かせなかった（泣）':
            continue

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

        # Fetch weather data
        weather_data = fetch_historical_weather(lat, lon, date)
        if weather_data is None:
            continue

        # Calculate working hours statistics
        stats = calculate_working_hours_stats(weather_data)

        if stats is None:
            continue

        # Check if no precipitation
        if stats['precip_total'] == 0.0:
            partial_no_rain.append({
                'date': date_str,
                'spot': spot_name,
                'stats': stats
            })

    # Display results
    print(f"\n降水量0mmの部分乾燥: {len(partial_no_rain)}件\n")
    print("=" * 80)

    for i, record in enumerate(partial_no_rain, 1):
        stats = record['stats']
        print(f"\n【{i}】 {record['date']} | {record['spot'][:20]}")
        print(f"  🌡️  気温: 平均 {stats['temp_avg']:.1f}°C (最高 {stats['temp_max']:.1f}°C, 最低 {stats['temp_min']:.1f}°C)")
        print(f"  💧 湿度: 平均 {stats['humidity_avg']:.1f}% (最低 {stats['humidity_min']:.1f}%, 最高 {stats['humidity_max']:.1f}%)")
        print(f"  🌬️  風速: 平均 {stats['wind_avg']:.2f}m/s (最大 {stats['wind_max']:.2f}m/s, 最小 {stats['wind_min']:.2f}m/s)")
        print(f"  ☀️  日射: 平均 {stats['solar_avg']:.1f}W/m² (最大 {stats['solar_max']:.1f}W/m², 積算 {stats['solar_total']:.1f}Wh/m²)")
        print(f"  ☁️  雲量: 平均 {stats['cloud_avg']:.1f}%" if stats['cloud_avg'] is not None else "")
        print(f"  💧 降水: {stats['precip_total']:.1f}mm")
        if stats['pwv_avg'] is not None:
            print(f"  🌊 PWV: 平均 {stats['pwv_avg']:.1f}mm (最大 {stats['pwv_max']:.1f}mm, 最小 {stats['pwv_min']:.1f}mm)")

    # Statistical summary
    if partial_no_rain:
        print("\n" + "=" * 80)
        print("統計サマリー（降水0mmの部分乾燥）")
        print("=" * 80)

        temps = [r['stats']['temp_avg'] for r in partial_no_rain]
        humidities = [r['stats']['humidity_avg'] for r in partial_no_rain]
        humidity_mins = [r['stats']['humidity_min'] for r in partial_no_rain]
        winds = [r['stats']['wind_avg'] for r in partial_no_rain]
        wind_maxs = [r['stats']['wind_max'] for r in partial_no_rain]
        solars = [r['stats']['solar_avg'] for r in partial_no_rain]
        solar_totals = [r['stats']['solar_total'] for r in partial_no_rain]
        pwv_values = [r['stats']['pwv_avg'] for r in partial_no_rain if r['stats']['pwv_avg'] is not None]

        print(f"\n平均気温:   min={min(temps):.1f}°C, max={max(temps):.1f}°C, mean={statistics.mean(temps):.1f}°C")
        print(f"平均湿度:   min={min(humidities):.1f}%, max={max(humidities):.1f}%, mean={statistics.mean(humidities):.1f}%")
        print(f"最低湿度:   min={min(humidity_mins):.1f}%, max={max(humidity_mins):.1f}%, mean={statistics.mean(humidity_mins):.1f}%")
        print(f"平均風速:   min={min(winds):.2f}m/s, max={max(winds):.2f}m/s, mean={statistics.mean(winds):.2f}m/s")
        print(f"最大風速:   min={min(wind_maxs):.2f}m/s, max={max(wind_maxs):.2f}m/s, mean={statistics.mean(wind_maxs):.2f}m/s")
        print(f"平均日射:   min={min(solars):.1f}W/m², max={max(solars):.1f}W/m², mean={statistics.mean(solars):.1f}W/m²")
        print(f"積算日射:   min={min(solar_totals):.1f}Wh/m², max={max(solar_totals):.1f}Wh/m², mean={statistics.mean(solar_totals):.1f}Wh/m²")

        if pwv_values:
            print(f"平均PWV:    min={min(pwv_values):.1f}mm, max={max(pwv_values):.1f}mm, mean={statistics.mean(pwv_values):.1f}mm")

    print("\n" + "=" * 80)

if __name__ == '__main__':
    analyze_partial_no_rain()
