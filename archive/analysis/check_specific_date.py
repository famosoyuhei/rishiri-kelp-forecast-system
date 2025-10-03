#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Check detailed weather data for specific date (2025-06-27)
Verify if API data matches synoptic conditions
"""
import requests
from datetime import datetime
import sys
import io
import math

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def fetch_detailed_weather(lat, lon, date_str):
    """Fetch detailed hourly weather data"""
    try:
        url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&hourly=temperature_2m,relative_humidity_2m,wind_speed_10m,wind_direction_10m,precipitation,pressure_msl,cloud_cover,direct_radiation,dewpoint_2m,surface_pressure&start_date={date_str}&end_date={date_str}&timezone=Asia/Tokyo"
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        return response.json()
    except:
        try:
            url = f"https://archive-api.open-meteo.com/v1/archive?latitude={lat}&longitude={lon}&start_date={date_str}&end_date={date_str}&hourly=temperature_2m,relative_humidity_2m,wind_speed_10m,wind_direction_10m,precipitation,pressure_msl,cloud_cover,direct_radiation,dewpoint_2m,surface_pressure&timezone=Asia/Tokyo"
            response = requests.get(url, timeout=15)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"Error: {e}")
            return None

def main():
    # Rishiri Island coordinates
    lat = 45.1631
    lon = 141.1434
    date_str = "2025-06-27"

    print("=" * 100)
    print(f"詳細気象データ検証: {date_str}")
    print(f"地点: 北緯{lat}° 東経{lon}° (利尻島)")
    print("=" * 100)
    print("\n【天気図情報】")
    print("  温帯低気圧: 北緯44° 東経150° 付近")
    print("  利尻島: 低気圧後面（寒冷前線通過後）")
    print("  予想: 北西風、降水、気圧変化")
    print("\n" + "=" * 100)

    weather_data = fetch_detailed_weather(lat, lon, date_str)

    if not weather_data or 'hourly' not in weather_data:
        print("データ取得失敗")
        return

    hourly = weather_data['hourly']
    times = hourly.get('time', [])

    print("\n時刻別データ:")
    print("-" * 100)
    print(f"{'時刻':>5} | {'気温':>5} | {'湿度':>5} | {'風速':>7} | {'風向':>5} | {'気圧':>7} | {'降水':>6} | {'雲量':>5} | {'日射':>7}")
    print("-" * 100)

    for i in range(len(times)):
        time = times[i].split('T')[1] if 'T' in times[i] else times[i]
        temp = hourly.get('temperature_2m', [None]*24)[i]
        humid = hourly.get('relative_humidity_2m', [None]*24)[i]
        wind = hourly.get('wind_speed_10m', [None]*24)[i]
        wind_dir = hourly.get('wind_direction_10m', [None]*24)[i]
        pressure = hourly.get('pressure_msl', [None]*24)[i]
        precip = hourly.get('precipitation', [None]*24)[i]
        cloud = hourly.get('cloud_cover', [None]*24)[i]
        solar = hourly.get('direct_radiation', [None]*24)[i]

        # Convert wind direction to compass
        def deg_to_compass(deg):
            if deg is None:
                return "N/A"
            dirs = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
                   "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]
            idx = int((deg + 11.25) / 22.5) % 16
            return dirs[idx]

        wind_compass = deg_to_compass(wind_dir)
        wind_ms = wind / 3.6 if wind is not None else None

        print(f"{time:>5} | {temp:5.1f}°C | {humid:4.0f}% | {wind_ms:5.1f}m/s | {wind_compass:>5} | {pressure:6.1f}hPa | {precip:5.1f}mm | {cloud:4.0f}% | {solar:6.0f}W/m²" if all(x is not None for x in [temp, humid, wind_ms, pressure, precip, cloud, solar]) else f"{time:>5} | データ不足")

    # Working hours summary (4:00-16:00)
    print("\n" + "=" * 100)
    print("作業時間帯サマリー (4:00-16:00)")
    print("=" * 100)

    working_temps = []
    working_humid = []
    working_wind = []
    working_wind_dir = []
    working_precip = []
    working_pressure = []

    for i in range(4, min(17, len(times))):
        temp = hourly.get('temperature_2m', [None]*24)[i]
        humid = hourly.get('relative_humidity_2m', [None]*24)[i]
        wind = hourly.get('wind_speed_10m', [None]*24)[i]
        wind_dir = hourly.get('wind_direction_10m', [None]*24)[i]
        precip = hourly.get('precipitation', [None]*24)[i]
        pressure = hourly.get('pressure_msl', [None]*24)[i]

        if temp is not None:
            working_temps.append(temp)
        if humid is not None:
            working_humid.append(humid)
        if wind is not None:
            working_wind.append(wind / 3.6)
        if wind_dir is not None:
            working_wind_dir.append(wind_dir)
        if precip is not None:
            working_precip.append(precip)
        if pressure is not None:
            working_pressure.append(pressure)

    if working_temps:
        print(f"\n気温: {min(working_temps):.1f}～{max(working_temps):.1f}°C (平均 {sum(working_temps)/len(working_temps):.1f}°C)")
    if working_humid:
        print(f"湿度: {min(working_humid):.0f}～{max(working_humid):.0f}% (平均 {sum(working_humid)/len(working_humid):.0f}%)")
    if working_wind:
        print(f"風速: {min(working_wind):.1f}～{max(working_wind):.1f}m/s (平均 {sum(working_wind)/len(working_wind):.1f}m/s)")
    if working_wind_dir:
        avg_dir = sum(working_wind_dir) / len(working_wind_dir)
        print(f"風向: {avg_dir:.0f}° (平均)")
    if working_precip:
        print(f"降水: 総計 {sum(working_precip):.1f}mm")
    if working_pressure:
        print(f"気圧: {min(working_pressure):.1f}～{max(working_pressure):.1f}hPa (変化 {max(working_pressure)-min(working_pressure):.1f}hPa)")

    print("\n" + "=" * 100)
    print("【天気図との整合性チェック】")
    print("=" * 100)

    # Check consistency with synoptic situation
    if working_wind_dir:
        avg_dir = sum(working_wind_dir) / len(working_wind_dir)
        # Low pressure at 44N 150E, Rishiri at 45N 141E
        # Behind the low: should have NW to N winds
        expected_dir_range = (270, 360)  # W to N

        if 270 <= avg_dir <= 360 or 0 <= avg_dir <= 45:
            print(f"✅ 風向: {avg_dir:.0f}° → 北西～北風 (低気圧後面に整合)")
        else:
            print(f"⚠️ 風向: {avg_dir:.0f}° → 天気図と不一致の可能性")

    if working_precip:
        total_precip = sum(working_precip)
        if total_precip > 0:
            print(f"✅ 降水: {total_precip:.1f}mm → 寒冷前線通過後の降水に整合")
        else:
            print(f"⚠️ 降水: なし → 天気図から予想される降水がない")

    if working_pressure:
        pressure_change = max(working_pressure) - min(working_pressure)
        if pressure_change > 2:
            print(f"✅ 気圧変化: {pressure_change:.1f}hPa → 前線通過に伴う変化")
        else:
            print(f"⚠️ 気圧変化: {pressure_change:.1f}hPa → 小さい（前線通過の影響が弱い？）")

    print("\n" + "=" * 100)

if __name__ == '__main__':
    main()
