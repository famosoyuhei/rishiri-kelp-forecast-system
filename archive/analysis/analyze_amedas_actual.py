#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Analyze kelp drying records using ACTUAL JMA Amedas observation data
Compare against previous API-based analysis to validate thresholds
"""
import csv
import sys
import io
from datetime import datetime
import statistics

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

    # Skip header lines (download time, location names)
    # Find the row with column headers
    header_idx = None
    for i, line in enumerate(lines):
        if '年月日' in line:
            header_idx = i
            break

    if header_idx is None:
        print("❌ ヘッダー行が見つかりません")
        return {}

    # Parse headers
    header_line = lines[header_idx]
    headers = [h.strip() for h in header_line.split(',')]

    # Find column indices for key parameters
    # Looking for: 年月日, 平均気温, 降水量の合計, 日照時間, 合計全天日射量, 平均風速, 最大風速, 最大風向, 平均湿度
    date_idx = None
    temp_avg_idx = None
    precip_idx = None
    sunshine_idx = None
    solar_idx = None
    wind_avg_idx = None
    wind_max_idx = None
    humidity_idx = None

    for i, header in enumerate(headers):
        if header == '年月日':
            date_idx = i
        elif header == '平均気温(℃)' and temp_avg_idx is None:
            temp_avg_idx = i
        elif header == '降水量の合計(mm)' and precip_idx is None:
            precip_idx = i
        elif header == '日照時間(時間)' and sunshine_idx is None:
            sunshine_idx = i
        elif header == '合計全天日射量(MJ/㎡)' and solar_idx is None:
            solar_idx = i
        elif header == '平均風速(m/s)' and wind_avg_idx is None:
            wind_avg_idx = i
        elif header == '最大風速(m/s)' and wind_max_idx is None:
            wind_max_idx = i
        elif header == '平均湿度(％)' and humidity_idx is None:
            humidity_idx = i

    print("=== カラム検出 ===")
    print(f"年月日: {date_idx}")
    print(f"平均気温: {temp_avg_idx}")
    print(f"降水量: {precip_idx}")
    print(f"日照時間: {sunshine_idx}")
    print(f"日射量: {solar_idx}")
    print(f"平均風速: {wind_avg_idx}")
    print(f"最大風速: {wind_max_idx}")
    print(f"平均湿度: {humidity_idx}")
    print()

    # Parse data rows (skip unit row after header)
    weather_data = {}
    for line in lines[header_idx + 2:]:
        if not line.strip():
            continue

        cols = [c.strip() for c in line.split(',')]

        if date_idx is None or date_idx >= len(cols):
            continue

        date_str = cols[date_idx]
        if not date_str or '/' not in date_str:
            continue

        try:
            # Parse date (format: YYYY/M/D)
            date = datetime.strptime(date_str, '%Y/%m/%d')
            date_key = date.strftime('%Y-%m-%d')

            def safe_float(idx):
                if idx is None or idx >= len(cols):
                    return None
                val = cols[idx]
                if val == '' or val == '--' or val == ')':
                    return None
                try:
                    # Remove any non-numeric characters except . and -
                    val = val.replace(')', '').replace(']', '').strip()
                    return float(val)
                except:
                    return None

            weather_data[date_key] = {
                'date': date_key,
                'temp_avg': safe_float(temp_avg_idx),
                'precip_total': safe_float(precip_idx),
                'sunshine_hours': safe_float(sunshine_idx),
                'solar_total': safe_float(solar_idx),
                'wind_avg': safe_float(wind_avg_idx),
                'wind_max': safe_float(wind_max_idx),
                'humidity_avg': safe_float(humidity_idx)
            }
        except Exception as e:
            continue

    print(f"✅ {len(weather_data)}日分のデータを読み込みました")
    return weather_data

def analyze_records_with_actual_data():
    """Analyze drying records using actual Amedas data"""
    records = load_drying_records()
    weather_data = parse_amedas_data()

    print("\n" + "=" * 100)
    print("実測データによる昆布干場記録分析")
    print("=" * 100)

    success_records = []
    partial_records = []
    cancelled_records = []

    for record in records:
        date_str = record['date']
        result = record['result']

        if date_str not in weather_data:
            continue

        weather = weather_data[date_str]

        record_with_weather = {
            'date': date_str,
            'spot': record['name'],
            'result': result,
            'weather': weather
        }

        if result == '完全乾燥':
            success_records.append(record_with_weather)
        elif result == '干したが完全には乾かせなかった（泣）':
            partial_records.append(record_with_weather)
        elif result == '中止':
            cancelled_records.append(record_with_weather)

    print(f"\n完全乾燥: {len(success_records)}件 (実測データあり)")
    print(f"部分乾燥: {len(partial_records)}件 (実測データあり)")
    print(f"中止: {len(cancelled_records)}件 (実測データあり)")

    # Statistical analysis
    def analyze_category(records, label):
        if not records:
            return

        temps = [r['weather']['temp_avg'] for r in records if r['weather']['temp_avg'] is not None]
        precips = [r['weather']['precip_total'] for r in records if r['weather']['precip_total'] is not None]
        winds_avg = [r['weather']['wind_avg'] for r in records if r['weather']['wind_avg'] is not None]
        winds_max = [r['weather']['wind_max'] for r in records if r['weather']['wind_max'] is not None]
        humidities = [r['weather']['humidity_avg'] for r in records if r['weather']['humidity_avg'] is not None]
        solars = [r['weather']['solar_total'] for r in records if r['weather']['solar_total'] is not None]

        print(f"\n{'=' * 100}")
        print(f"{label} (n={len(records)})")
        print(f"{'=' * 100}")

        if temps:
            print(f"平均気温: min={min(temps):.1f}°C, max={max(temps):.1f}°C, mean={statistics.mean(temps):.1f}°C")
        if precips:
            print(f"降水量: min={min(precips):.1f}mm, max={max(precips):.1f}mm, mean={statistics.mean(precips):.1f}mm")
        if winds_avg:
            print(f"平均風速: min={min(winds_avg):.1f}m/s, max={max(winds_avg):.1f}m/s, mean={statistics.mean(winds_avg):.1f}m/s")
        if winds_max:
            print(f"最大風速: min={min(winds_max):.1f}m/s, max={max(winds_max):.1f}m/s, mean={statistics.mean(winds_max):.1f}m/s")
        if humidities:
            print(f"平均湿度: min={min(humidities):.1f}%, max={max(humidities):.1f}%, mean={statistics.mean(humidities):.1f}%")
        if solars:
            print(f"全天日射: min={min(solars):.1f}MJ/㎡, max={max(solars):.1f}MJ/㎡, mean={statistics.mean(solars):.1f}MJ/㎡")

    analyze_category(success_records, "✅ 完全乾燥")
    analyze_category(partial_records, "⚠️ 部分乾燥")
    analyze_category(cancelled_records, "❌ 中止")

    # Detailed comparison
    print("\n" + "=" * 100)
    print("完全乾燥の詳細記録")
    print("=" * 100)
    print(f"{'日付':>10} | {'気温':>5} | {'降水':>5} | {'風速':>5} | {'最大':>5} | {'湿度':>5} | {'日射':>7}")
    print("-" * 100)

    for r in success_records:
        w = r['weather']
        temp = f"{w['temp_avg']:.1f}" if w['temp_avg'] is not None else "N/A"
        precip = f"{w['precip_total']:.1f}" if w['precip_total'] is not None else "N/A"
        wind_avg = f"{w['wind_avg']:.1f}" if w['wind_avg'] is not None else "N/A"
        wind_max = f"{w['wind_max']:.1f}" if w['wind_max'] is not None else "N/A"
        humidity = f"{w['humidity_avg']:.1f}" if w['humidity_avg'] is not None else "N/A"
        solar = f"{w['solar_total']:.1f}" if w['solar_total'] is not None else "N/A"

        print(f"{r['date']:>10} | {temp:>5}°C | {precip:>5}mm | {wind_avg:>5}m/s | {wind_max:>5}m/s | {humidity:>5}% | {solar:>7}MJ")

    # Threshold violation check using ACTUAL data
    print("\n" + "=" * 100)
    print("閾値検証（実測データ）")
    print("=" * 100)

    violations_count = 0
    for r in success_records:
        w = r['weather']
        violations = []

        if w['precip_total'] is not None and w['precip_total'] > 0:
            violations.append(f"降水{w['precip_total']:.1f}mm")
        if w['humidity_avg'] is not None and w['humidity_avg'] > 83:
            violations.append(f"湿度{w['humidity_avg']:.1f}%")
        if w['wind_avg'] is not None and w['wind_avg'] < 4.5:
            violations.append(f"風速{w['wind_avg']:.1f}m/s")
        if w['wind_max'] is not None and w['wind_max'] > 7.0:
            violations.append(f"最大風速{w['wind_max']:.1f}m/s")

        if violations:
            violations_count += 1
            print(f"{r['date']}: {', '.join(violations)}")

    print(f"\n閾値違反あり: {violations_count}/{len(success_records)}件")

    print("\n" + "=" * 100)

def main():
    analyze_records_with_actual_data()

if __name__ == '__main__':
    main()
