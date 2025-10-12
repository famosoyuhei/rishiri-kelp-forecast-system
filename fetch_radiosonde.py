#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
稚内ラジオゾンデデータ取得と分析
University of Wyoming Upper Air Archive API使用
"""
import requests
import sys
import io
from datetime import datetime
import re

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def fetch_sounding(year, month, day, hour):
    """
    稚内のラジオゾンデデータを取得

    Parameters:
    - year: 年
    - month: 月
    - day: 日
    - hour: 00 or 12 (UTC)
    """
    # Wyoming URL format
    # FROM/TO format: DDHH (day + hour in UTC)
    from_to = f"{day:02d}{hour:02d}"

    # Station numbers:
    # 47401 = Wakkanai (稚内)
    # 47412 = Sapporo (札幌)
    url = (
        f"http://weather.uwyo.edu/cgi-bin/sounding?"
        f"region=np&TYPE=TEXT:LIST&YEAR={year}&MONTH={month:02d}"
        f"&FROM={from_to}&TO={from_to}&STNM=47401"
    )

    print(f"取得URL: {url}")

    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        return response.text
    except Exception as e:
        print(f"エラー: {e}")
        return None

def parse_sounding(text):
    """Parse Wyoming sounding text format"""
    if not text or "Can't get" in text or "No data" in text:
        return None

    lines = text.split('\n')

    # Find data section (starts after header with PRES HGHT TEMP...)
    data_start = None
    for i, line in enumerate(lines):
        if 'PRES' in line and 'HGHT' in line and 'TEMP' in line:
            data_start = i + 2  # Skip header and unit line
            break

    if data_start is None:
        return None

    # Parse data
    levels = []
    for line in lines[data_start:]:
        if not line.strip() or line.startswith('Station'):
            continue

        # Stop at indices or other sections
        if 'Station information' in line or 'Indices' in line:
            break

        parts = line.split()
        if len(parts) < 6:
            continue

        try:
            # Data columns: PRES HGHT TEMP DWPT RELH MIXR DRCT SKNT THTA THTE THTV
            pres = float(parts[0]) if parts[0] != '' else None  # hPa
            hght = float(parts[1]) if parts[1] != '' else None  # m
            temp = float(parts[2]) if parts[2] != '' else None  # °C
            dwpt = float(parts[3]) if parts[3] != '' else None  # °C (dewpoint)
            relh = float(parts[4]) if parts[4] != '' else None  # %

            # Wind data (column 6 is DRCT, column 7 is SKNT)
            if len(parts) >= 8:
                wdir_str = parts[6].strip()
                wspd_str = parts[7].strip()
                wdir = float(wdir_str) if wdir_str and wdir_str != '' else None  # degrees
                wspd = float(wspd_str) if wspd_str and wspd_str != '' else None  # knots
            else:
                wdir = None
                wspd = None

            # Skip invalid entries
            if pres is None or temp is None:
                continue

            levels.append({
                'pressure': pres,
                'height': hght,
                'temp': temp,
                'dewpoint': dwpt,
                'rh': relh,
                'wind_dir': wdir,
                'wind_speed': wspd
            })
        except ValueError:
            continue

    return levels

def analyze_sounding(levels, date_str):
    """Analyze sounding data for kelp drying conditions"""
    if not levels:
        return None

    print("\n" + "=" * 100)
    print(f"稚内ラジオゾンデ解析: {date_str}")
    print("=" * 100)

    # Find key levels
    surface = None
    level_850 = None
    level_700 = None
    level_500 = None

    for level in levels:
        pres = level['pressure']
        if pres >= 1000:
            surface = level
        if 845 <= pres <= 855:
            level_850 = level
        if 695 <= pres <= 705:
            level_700 = level
        if 495 <= pres <= 505:
            level_500 = level

    # Display key levels
    print(f"\n{'気圧':>8} | {'高度':>6} | {'気温':>6} | {'露点':>6} | {'湿度':>5} | {'風向':>5} | {'風速':>6}")
    print("-" * 100)

    for label, level in [('地上', surface), ('850hPa', level_850), ('700hPa', level_700), ('500hPa', level_500)]:
        if level:
            pres = level['pressure']
            hght = level['height']
            temp = level['temp']
            dwpt = level['dewpoint']
            relh = level['rh'] if level['rh'] is not None else 0
            wdir = level['wind_dir'] if level['wind_dir'] is not None else 0
            wspd = level['wind_speed'] if level['wind_speed'] is not None else 0
            wspd_ms = wspd * 0.514444  # knots to m/s

            def deg_to_compass(deg):
                if deg is None or deg == 0:
                    return "N/A"
                dirs = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
                       "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]
                idx = int((deg + 11.25) / 22.5) % 16
                return dirs[idx]

            wdir_compass = deg_to_compass(wdir)

            print(f"{label:>8} | {hght:>5.0f}m | {temp:>5.1f}°C | {dwpt:>5.1f}°C | {relh:>4.0f}% | {wdir_compass:>5} | {wspd_ms:>5.1f}m/s")

    # Analysis
    print("\n" + "=" * 100)
    print("気象解析")
    print("=" * 100)

    if surface and level_850:
        # Temperature inversion check
        temp_diff = level_850['temp'] - surface['temp']
        print(f"\n【気温逆転層】")
        print(f"  地上気温: {surface['temp']:.1f}°C")
        print(f"  850hPa気温: {level_850['temp']:.1f}°C")
        print(f"  気温差: {temp_diff:+.1f}°C")

        if temp_diff > 0:
            print(f"  → ⚠️ 逆転層あり（霧・層雲発生しやすい）")
        else:
            print(f"  → ✅ 正常な気温減率（対流活発、晴れやすい）")

        # Humidity analysis
        print(f"\n【湿度】")
        print(f"  地上湿度: {surface['rh']:.0f}%" if surface['rh'] else "  地上湿度: N/A")
        print(f"  850hPa湿度: {level_850['rh']:.0f}%" if level_850['rh'] else "  850hPa湿度: N/A")

        if surface['rh'] and level_850['rh']:
            if surface['rh'] > 90 and level_850['rh'] < 70:
                print(f"  → ✅ 中層乾燥: 日中の昇温で地上湿度低下の可能性")
            elif surface['rh'] > 90 and level_850['rh'] > 80:
                print(f"  → ❌ 全層湿潤: 乾燥困難")

        # Wind shear
        print(f"\n【風向鉛直シア】")
        surf_wdir = surface['wind_dir'] if surface['wind_dir'] else 0
        e850_wdir = level_850['wind_dir'] if level_850['wind_dir'] else 0

        if surf_wdir and e850_wdir:
            shear = abs(e850_wdir - surf_wdir)
            if shear > 180:
                shear = 360 - shear

            print(f"  地上風向: {surf_wdir:.0f}°")
            print(f"  850hPa風向: {e850_wdir:.0f}°")
            print(f"  シア: {shear:.0f}°")

            if shear < 30:
                print(f"  → 同一気流（大規模循環が卓越）")
            elif shear > 90:
                print(f"  → 局地循環あり（海陸風、山谷風等）")

    print("\n" + "=" * 100)

    return {
        'surface': surface,
        'level_850': level_850,
        'level_700': level_700,
        'level_500': level_500
    }

def main():
    print("=" * 100)
    print("稚内ラジオゾンデデータ取得")
    print("=" * 100)

    # Test case: 2025-07-29 09:00 JST = 2025-07-29 00:00 UTC
    test_date = datetime(2025, 7, 29, 0, 0)  # UTC

    print(f"\n取得対象: {test_date.strftime('%Y-%m-%d %H:%M UTC')} (JST 09:00)")

    # Fetch data
    text = fetch_sounding(
        year=test_date.year,
        month=test_date.month,
        day=test_date.day,
        hour=test_date.hour
    )

    if text:
        # Parse
        levels = parse_sounding(text)

        if levels:
            print(f"\n✅ {len(levels)}層のデータを取得")

            # Analyze
            analysis = analyze_sounding(levels, "2025-07-29 09:00 JST")

            # Also try 21:00 JST (12:00 UTC)
            print("\n\n" + "=" * 100)
            print("2回目の観測（21:00 JST）")
            print("=" * 100)

            text2 = fetch_sounding(
                year=test_date.year,
                month=test_date.month,
                day=test_date.day,
                hour=12
            )

            if text2:
                levels2 = parse_sounding(text2)
                if levels2:
                    print(f"\n✅ {len(levels2)}層のデータを取得")
                    analysis2 = analyze_sounding(levels2, "2025-07-29 21:00 JST")
        else:
            print("❌ データ解析失敗")
    else:
        print("❌ データ取得失敗")

    print("\n" + "=" * 100)

if __name__ == '__main__':
    main()
