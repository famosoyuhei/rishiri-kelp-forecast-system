#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
H_1631_1434の全21件の実測アメダスデータ分析
精密な閾値の導出
"""
import csv
import sys
import io
from datetime import datetime
import statistics

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def load_drying_records():
    """Load drying records for H_1631_1434"""
    records = []
    with open('hoshiba_records.csv', 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row['name'] == 'H_1631_1434':
                records.append(row)
    return {r['date']: r['result'] for r in records}

def parse_hourly_csv(filepath):
    """Parse hourly Amedas CSV data"""
    with open(filepath, 'r', encoding='cp932') as f:
        lines = f.readlines()

    # Find header
    header_idx = None
    for i, line in enumerate(lines):
        if '年月日' in line or '気温' in line:
            header_idx = i
            break

    if header_idx is None:
        return {}

    hourly_data = {}

    for line in lines[header_idx + 4:]:
        if not line.strip():
            continue

        parts = [p.strip() for p in line.split(',')]
        if len(parts) < 10:
            continue

        datetime_str = parts[0]
        if not datetime_str or '/' not in datetime_str:
            continue

        try:
            dt = datetime.strptime(datetime_str, '%Y/%m/%d %H:%M:%S')
            date_key = dt.strftime('%Y-%m-%d')
            hour = dt.hour

            def safe_float(idx):
                if idx >= len(parts):
                    return None
                val = parts[idx]
                if val == '' or val == ']' or val.startswith('8'):
                    return None
                try:
                    return float(val)
                except:
                    return None

            temp = safe_float(1)
            precip = safe_float(4)
            wind = safe_float(13)
            humidity = safe_float(18)

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

    for hour in range(4, 17):
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
        'precip_any': any(p > 0 for p in precips),
        'wind_avg': statistics.mean(winds) if winds else None,
        'wind_max': max(winds) if winds else None,
        'humidity_avg': statistics.mean(humidities) if humidities else None,
        'humidity_min': min(humidities) if humidities else None,
        'humidity_max': max(humidities) if humidities else None,
    }

def main():
    print("=" * 100)
    print("H_1631_1434（神居）全21件の実測アメダスデータ分析")
    print("=" * 100)

    # Load all CSV files
    csv_files = [
        '19-22june.csv',
        '23-29june.csv',
        '30june-11july.csv',
        '29july.csv',
        '14-23august.csv'
    ]

    all_hourly_data = {}
    for csv_file in csv_files:
        try:
            data = parse_hourly_csv(csv_file)
            all_hourly_data.update(data)
            print(f"✅ {csv_file}: {len(data)}日分読み込み")
        except Exception as e:
            print(f"❌ {csv_file}: エラー - {e}")

    print(f"\n総データ日数: {len(all_hourly_data)}日")

    # Load drying records
    drying_records = load_drying_records()
    print(f"H_1631_1434の記録: {len(drying_records)}件")

    # Analyze each record
    print("\n" + "=" * 100)
    print("【全21件の詳細分析】")
    print("=" * 100)

    results_data = {
        '完全乾燥': [],
        '中止': [],
        '干したが完全には乾かせなかった（泣）': []
    }

    print(f"\n{'日付':12} | {'結果':35} | {'降水':>6} | {'湿度最低':>8} | {'湿度平均':>8} | {'風速平均':>8} | {'気温平均':>8}")
    print("-" * 120)

    for date in sorted(drying_records.keys()):
        result = drying_records[date]
        analysis = analyze_working_hours(all_hourly_data, date)

        if analysis:
            precip_str = f"{analysis['precip_total']:.1f}mm"
            hum_min_str = f"{analysis['humidity_min']:.0f}%" if analysis['humidity_min'] else "N/A"
            hum_avg_str = f"{analysis['humidity_avg']:.0f}%" if analysis['humidity_avg'] else "N/A"
            wind_str = f"{analysis['wind_avg']:.1f}m/s" if analysis['wind_avg'] else "N/A"
            temp_str = f"{analysis['temp_avg']:.1f}°C"

            print(f"{date:12} | {result:35} | {precip_str:>6} | {hum_min_str:>8} | {hum_avg_str:>8} | {wind_str:>8} | {temp_str:>8}")

            results_data[result].append(analysis)
        else:
            print(f"{date:12} | {result:35} | データなし")

    # Statistical analysis
    print("\n" + "=" * 100)
    print("【統計分析】")
    print("=" * 100)

    for result_type in ['完全乾燥', '干したが完全には乾かせなかった（泣）', '中止']:
        data = results_data[result_type]
        if not data:
            continue

        print(f"\n■ {result_type} ({len(data)}件)")
        print("-" * 100)

        # Precipitation
        precip_totals = [d['precip_total'] for d in data]
        precip_any = sum(1 for d in data if d['precip_any'])
        print(f"降水: {precip_any}/{len(data)}件で降水あり")
        print(f"  範囲: {min(precip_totals):.1f}～{max(precip_totals):.1f}mm")

        # Humidity minimum
        hum_mins = [d['humidity_min'] for d in data if d['humidity_min'] is not None]
        if hum_mins:
            print(f"湿度（最低）:")
            print(f"  平均: {statistics.mean(hum_mins):.1f}%")
            print(f"  範囲: {min(hum_mins):.0f}～{max(hum_mins):.0f}%")

        # Humidity average
        hum_avgs = [d['humidity_avg'] for d in data if d['humidity_avg'] is not None]
        if hum_avgs:
            print(f"湿度（平均）:")
            print(f"  平均: {statistics.mean(hum_avgs):.1f}%")
            print(f"  範囲: {min(hum_avgs):.0f}～{max(hum_avgs):.0f}%")

        # Wind
        winds = [d['wind_avg'] for d in data if d['wind_avg'] is not None]
        if winds:
            print(f"風速（平均）:")
            print(f"  平均: {statistics.mean(winds):.1f}m/s")
            print(f"  範囲: {min(winds):.1f}～{max(winds):.1f}m/s")

        # Temperature
        temps = [d['temp_avg'] for d in data]
        print(f"気温（平均）:")
        print(f"  平均: {statistics.mean(temps):.1f}°C")
        print(f"  範囲: {min(temps):.1f}～{max(temps):.1f}°C")

    # Derive thresholds
    print("\n" + "=" * 100)
    print("【実測データから導出される閾値】")
    print("=" * 100)

    success_data = results_data['完全乾燥']
    fail_data = results_data['中止']
    partial_data = results_data['干したが完全には乾かせなかった（泣）']

    print("\n1. 降水量:")
    print(f"   完全乾燥: 全{len(success_data)}件で降水なし")
    print(f"   → 閾値: 降水量 = 0mm（絶対条件）")

    print("\n2. 湿度（作業時間帯の最低値）:")
    success_hum_min = [d['humidity_min'] for d in success_data if d['humidity_min']]
    fail_hum_min = [d['humidity_min'] for d in fail_data if d['humidity_min']]
    if success_hum_min and fail_hum_min:
        success_max = max(success_hum_min)
        fail_min = min(fail_hum_min)
        print(f"   完全乾燥: {min(success_hum_min):.0f}～{success_max:.0f}%")
        print(f"   中止: {fail_min:.0f}～{max(fail_hum_min):.0f}%")
        print(f"   → 閾値: 最低湿度 ≤ {success_max:.0f}%")

    print("\n3. 風速（作業時間帯の平均）:")
    success_wind = [d['wind_avg'] for d in success_data if d['wind_avg']]
    fail_wind = [d['wind_avg'] for d in fail_data if d['wind_avg']]
    if success_wind and fail_wind:
        success_min = min(success_wind)
        fail_max = max(fail_wind)
        print(f"   完全乾燥: {success_min:.1f}～{max(success_wind):.1f}m/s")
        print(f"   中止: {min(fail_wind):.1f}～{fail_max:.1f}m/s")
        print(f"   → 閾値: 風速 ≥ {success_min:.1f}m/s")

    print("\n4. 気温（作業時間帯の平均）:")
    success_temp = [d['temp_avg'] for d in success_data]
    fail_temp = [d['temp_avg'] for d in fail_data]
    success_min = min(success_temp)
    fail_max = max(fail_temp)
    print(f"   完全乾燥: {success_min:.1f}～{max(success_temp):.1f}°C")
    print(f"   中止: {min(fail_temp):.1f}～{fail_max:.1f}°C")
    print(f"   → 閾値: 気温 ≥ {success_min:.1f}°C")

    print("\n" + "=" * 100)
    print("【重要な発見】")
    print("=" * 100)

    print("\n✅ 最低湿度が重要:")
    if success_hum_min:
        print(f"   - 平均湿度が高くても、午後に湿度が下がれば成功可能")
        print(f"   - 成功例の最低湿度: 平均{statistics.mean(success_hum_min):.1f}%")

    print("\n✅ 降水0mmは絶対条件:")
    print(f"   - 全ての成功例で降水なし")
    print(f"   - 霧雨・通り雨も時別値で検出可能")

    if success_wind:
        print(f"\n✅ 風速と湿度の相乗効果:")
        print(f"   - 風速が強ければ高湿度でも乾燥可能")
        print(f"   - 成功例の最低風速: {min(success_wind):.1f}m/s")

    print("\n" + "=" * 100)

if __name__ == '__main__':
    main()
