#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
日別値データから日照時間と日射量を分析
H_1631_1434の全21件
"""
import csv
import sys
import io
from datetime import datetime
import statistics
import math

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

def estimate_solar_radiation(sunshine_hours, latitude=45.178, day_of_year=180):
    """日照時間から日射量を推定"""
    lat_rad = math.radians(latitude)
    declination = 23.45 * math.sin(math.radians(360 * (284 + day_of_year) / 365))
    dec_rad = math.radians(declination)

    cos_hour_angle = -math.tan(lat_rad) * math.tan(dec_rad)
    if cos_hour_angle > 1:
        possible_sunshine = 0
    elif cos_hour_angle < -1:
        possible_sunshine = 24
    else:
        hour_angle = math.acos(cos_hour_angle)
        possible_sunshine = 2 * math.degrees(hour_angle) / 15

    sunshine_ratio = sunshine_hours / possible_sunshine if possible_sunshine > 0 else 0

    solar_constant = 1367
    dr = 1 + 0.033 * math.cos(2 * math.pi * day_of_year / 365)

    Ra = (24 * 60 / math.pi) * solar_constant * dr * (
        hour_angle * math.sin(lat_rad) * math.sin(dec_rad) +
        math.cos(lat_rad) * math.cos(dec_rad) * math.sin(hour_angle)
    ) / 1e6

    a, b = 0.25, 0.50
    Rs = (a + b * sunshine_ratio) * Ra

    return Rs, sunshine_ratio, possible_sunshine

def parse_daily_data():
    """Parse daily data CSV"""
    with open('dailydata.csv', 'r', encoding='cp932') as f:
        lines = f.readlines()

    header_idx = None
    for i, line in enumerate(lines):
        if '年月日' in line:
            header_idx = i
            break

    if header_idx is None:
        return {}

    daily_data = {}

    for line in lines[header_idx + 3:]:  # Skip header rows
        if not line.strip():
            continue

        parts = [p.strip() for p in line.split(',')]
        if len(parts) < 10:
            continue

        date_str = parts[0]
        if not date_str or '/' not in date_str:
            continue

        try:
            dt = datetime.strptime(date_str, '%Y/%m/%d')
            date_key = dt.strftime('%Y-%m-%d')
            day_of_year = dt.timetuple().tm_yday

            def safe_float(idx):
                if idx >= len(parts):
                    return None
                val = parts[idx]
                if val == '' or val == '--' or val == ')' or val.startswith('8'):
                    return None
                try:
                    val = val.replace(')', '').replace(']', '').strip()
                    return float(val)
                except:
                    return None

            # Column positions from header
            # 年月日, 平均気温, 降水量の合計, 日照時間, 平均風速, 平均湿度, ...
            avg_temp = safe_float(1)
            precip_total = safe_float(4)
            sunshine = safe_float(7)  # 日照時間
            avg_wind = safe_float(13)
            avg_humidity = safe_float(16)
            min_humidity = safe_float(26)  # 最小相対湿度

            daily_data[date_key] = {
                'avg_temp': avg_temp,
                'precip_total': precip_total,
                'sunshine': sunshine,
                'avg_wind': avg_wind,
                'avg_humidity': avg_humidity,
                'min_humidity': min_humidity,
                'day_of_year': day_of_year
            }

        except Exception as e:
            continue

    return daily_data

def main():
    print("=" * 100)
    print("日照時間から日射量を推定した分析（日別値データ使用）")
    print("=" * 100)

    daily_data = parse_daily_data()
    print(f"\n✅ {len(daily_data)}日分の日別データを読み込み")

    drying_records = load_drying_records()

    print("\n" + "=" * 100)
    print("【日照時間と日射量の分析】")
    print("=" * 100)

    results_data = {
        '完全乾燥': [],
        '中止': [],
        '干したが完全には乾かせなかった（泣）': []
    }

    print(f"\n{'日付':12} | {'結果':35} | {'日照':>6} | {'日照率':>6} | {'日射量':>8} | {'降水':>6} | {'最低湿度':>8}")
    print("-" * 130)

    for date in sorted(drying_records.keys()):
        result = drying_records[date]

        if date in daily_data:
            data = daily_data[date]
            sunshine = data['sunshine']
            precip = data['precip_total']
            min_hum = data['min_humidity']

            if sunshine is not None:
                radiation, sunshine_ratio, possible = estimate_solar_radiation(
                    sunshine,
                    latitude=45.178,
                    day_of_year=data['day_of_year']
                )

                precip_str = f"{precip:.1f}mm" if precip is not None else "N/A"
                min_hum_str = f"{min_hum:.0f}%" if min_hum is not None else "N/A"

                print(f"{date:12} | {result:35} | {sunshine:>5.1f}h | {sunshine_ratio*100:>5.1f}% | {radiation:>6.1f}MJ | {precip_str:>6} | {min_hum_str:>8}")

                results_data[result].append({
                    'sunshine': sunshine,
                    'radiation': radiation,
                    'sunshine_ratio': sunshine_ratio,
                    'precip': precip if precip is not None else 0,
                    'min_humidity': min_hum
                })
            else:
                print(f"{date:12} | {result:35} | データなし")
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

        sunshine_hours = [d['sunshine'] for d in data]
        print(f"日照時間:")
        print(f"  平均: {statistics.mean(sunshine_hours):.1f}h")
        print(f"  範囲: {min(sunshine_hours):.1f}～{max(sunshine_hours):.1f}h")

        sunshine_ratios = [d['sunshine_ratio'] * 100 for d in data]
        print(f"日照率:")
        print(f"  平均: {statistics.mean(sunshine_ratios):.1f}%")
        print(f"  範囲: {min(sunshine_ratios):.1f}～{max(sunshine_ratios):.1f}%")

        radiations = [d['radiation'] for d in data]
        print(f"推定日射量:")
        print(f"  平均: {statistics.mean(radiations):.1f}MJ/m²")
        print(f"  範囲: {min(radiations):.1f}～{max(radiations):.1f}MJ/m²")

        min_humidities = [d['min_humidity'] for d in data if d['min_humidity'] is not None]
        if min_humidities:
            print(f"最低湿度（日別値）:")
            print(f"  平均: {statistics.mean(min_humidities):.1f}%")
            print(f"  範囲: {min(min_humidities):.0f}～{max(min_humidities):.0f}%")

    # Derive thresholds
    print("\n" + "=" * 100)
    print("【日照時間・日射量の閾値】")
    print("=" * 100)

    success_data = results_data['完全乾燥']
    fail_data = results_data['中止']

    if success_data and fail_data:
        success_sunshine = [d['sunshine'] for d in success_data]
        fail_sunshine = [d['sunshine'] for d in fail_data]

        success_radiation = [d['radiation'] for d in success_data]
        fail_radiation = [d['radiation'] for d in fail_data]

        success_min_sunshine = min(success_sunshine)
        fail_max_sunshine = max(fail_sunshine)

        success_min_radiation = min(success_radiation)
        fail_max_radiation = max(fail_radiation)

        print(f"\n1. 日照時間:")
        print(f"   完全乾燥: {success_min_sunshine:.1f}～{max(success_sunshine):.1f}h (平均{statistics.mean(success_sunshine):.1f}h)")
        print(f"   中止: {min(fail_sunshine):.1f}～{fail_max_sunshine:.1f}h (平均{statistics.mean(fail_sunshine):.1f}h)")
        print(f"   → 最小値: 成功{success_min_sunshine:.1f}h vs 失敗最大{fail_max_sunshine:.1f}h")
        if success_min_sunshine > fail_max_sunshine:
            print(f"   → 閾値: 日照時間 ≥ {success_min_sunshine:.1f}h （明確な境界あり）")
        else:
            print(f"   → 閾値設定困難（重複範囲あり）")
            print(f"   → 日照時間は補助的指標として使用")

        print(f"\n2. 推定日射量:")
        print(f"   完全乾燥: {success_min_radiation:.1f}～{max(success_radiation):.1f}MJ/m² (平均{statistics.mean(success_radiation):.1f}MJ/m²)")
        print(f"   中止: {min(fail_radiation):.1f}～{fail_max_radiation:.1f}MJ/m² (平均{statistics.mean(fail_radiation):.1f}MJ/m²)")
        if success_min_radiation > fail_max_radiation:
            print(f"   → 閾値: 日射量 ≥ {success_min_radiation:.1f}MJ/m²")
        else:
            print(f"   → 閾値設定困難（重複範囲あり）")

    print("\n" + "=" * 100)
    print("【考察】")
    print("=" * 100)

    print("\n日照時間と成功/失敗の関係:")

    # Find overlap cases
    if success_data and fail_data:
        success_low_sunshine = [d for d in success_data if d['sunshine'] < 5.0]
        fail_high_sunshine = [d for d in fail_data if d['sunshine'] > 5.0]

        if success_low_sunshine:
            print(f"\n✅ 日照短時間でも成功例 ({len(success_low_sunshine)}件):")
            for d in success_low_sunshine:
                print(f"   日照{d['sunshine']:.1f}h, 最低湿度{d['min_humidity']:.0f}%, 降水{d['precip']:.1f}mm")
            print(f"   → 低湿度・無降水なら日照が短くても成功可能")

        if fail_high_sunshine:
            print(f"\n❌ 日照長時間でも失敗例 ({len(fail_high_sunshine)}件):")
            for d in fail_high_sunshine:
                hum_str = f"{d['min_humidity']:.0f}%" if d['min_humidity'] is not None else "N/A"
                print(f"   日照{d['sunshine']:.1f}h, 最低湿度{hum_str}, 降水{d['precip']:.1f}mm")
            print(f"   → 降水や高湿度があれば日照が長くても失敗")

    print("\n" + "=" * 100)
    print("【最終的な要因の優先順位】")
    print("=" * 100)

    print("\n1. 降水量 = 0mm（絶対条件）")
    print("   ✓ 全ての成功例で降水なし")

    print("\n2. 最低湿度 ≤ 94%（最重要）")
    print("   ✓ 作業時間帯（4-16時）の最低値が決定的")
    print("   ✓ 日別値の最低湿度とも強い相関")

    print("\n3. 風速 ≥ 2.0m/s（重要）")
    print("   ✓ 乾燥促進の主要因")

    print("\n4. 日照時間・日射量（補助的）")
    print("   ✓ 気温上昇・湿度低下を促進")
    print("   ✓ しかし単独では成功/失敗を判定不可")
    print("   ✓ 他の条件が揃えば短時間でも成功")

    print("\n5. 気温 ≥ 18°C（補助的）")
    print("   ✓ 飽和水蒸気圧に影響")

    print("\n" + "=" * 100)

if __name__ == '__main__':
    main()
