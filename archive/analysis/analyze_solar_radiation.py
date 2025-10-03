#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
日射量の判別力分析（実測データ）
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

    header_idx = None
    for i, line in enumerate(lines):
        if '年月日' in line:
            header_idx = i
            break

    if header_idx is None:
        return {}

    header_line = lines[header_idx]
    headers = [h.strip() for h in header_line.split(',')]

    indices = {}
    for i, header in enumerate(headers):
        if header == '年月日' and 'date' not in indices:
            indices['date'] = i
        elif header == '平均気温(℃)' and 'temp' not in indices:
            indices['temp'] = i
        elif header == '降水量の合計(mm)' and 'precip' not in indices:
            indices['precip'] = i
        elif header == '日照時間(時間)' and 'sunshine' not in indices:
            indices['sunshine'] = i
        elif header == '合計全天日射量(MJ/㎡)' and 'solar' not in indices:
            indices['solar'] = i
        elif header == '平均風速(m/s)' and 'wind_avg' not in indices:
            indices['wind_avg'] = i
        elif header == '最大風速(m/s)' and 'wind_max' not in indices:
            indices['wind_max'] = i
        elif header == '平均湿度(％)' and 'humidity' not in indices:
            indices['humidity'] = i

    weather_data = {}
    for line in lines[header_idx + 2:]:
        if not line.strip():
            continue

        cols = [c.strip() for c in line.split(',')]
        if indices['date'] >= len(cols):
            continue

        date_str = cols[indices['date']]
        if not date_str or '/' not in date_str:
            continue

        try:
            date = datetime.strptime(date_str, '%Y/%m/%d')
            date_key = date.strftime('%Y-%m-%d')

            def safe_float(key):
                if key not in indices or indices[key] >= len(cols):
                    return None
                val = cols[indices[key]]
                if val == '' or val == '--' or val == ')':
                    return None
                try:
                    val = val.replace(')', '').replace(']', '').strip()
                    return float(val)
                except:
                    return None

            weather_data[date_key] = {
                'temp': safe_float('temp'),
                'precip': safe_float('precip'),
                'sunshine': safe_float('sunshine'),
                'solar': safe_float('solar'),
                'wind_avg': safe_float('wind_avg'),
                'wind_max': safe_float('wind_max'),
                'humidity': safe_float('humidity')
            }
        except:
            continue

    return weather_data

def calculate_effect_size(group1_values, group2_values):
    """Calculate Cohen's d effect size"""
    if len(group1_values) < 2 or len(group2_values) < 2:
        return 0.0

    mean1 = statistics.mean(group1_values)
    mean2 = statistics.mean(group2_values)
    std1 = statistics.stdev(group1_values)
    std2 = statistics.stdev(group2_values)

    pooled_std = ((std1**2 + std2**2) / 2) ** 0.5
    if pooled_std == 0:
        return 0.0

    return abs(mean1 - mean2) / pooled_std

def main():
    records = load_drying_records()
    amedas_data = parse_amedas_data()

    print("=" * 100)
    print("日射量分析（実測データ）")
    print("=" * 100)

    # Categorize records
    success = []
    partial = []
    cancelled = []

    for record in records:
        date_str = record['date']
        if date_str not in amedas_data:
            continue

        weather = amedas_data[date_str]
        result = record['result']

        if result == '完全乾燥':
            success.append({'date': date_str, 'weather': weather})
        elif result == '干したが完全には乾かせなかった（泣）':
            partial.append({'date': date_str, 'weather': weather})
        elif result == '中止':
            cancelled.append({'date': date_str, 'weather': weather})

    print(f"\nデータ数:")
    print(f"  完全乾燥: {len(success)}件")
    print(f"  部分乾燥: {len(partial)}件")
    print(f"  中止: {len(cancelled)}件")

    # Extract solar radiation data
    success_solar = [r['weather']['solar'] for r in success if r['weather']['solar'] is not None]
    partial_solar = [r['weather']['solar'] for r in partial if r['weather']['solar'] is not None]
    cancelled_solar = [r['weather']['solar'] for r in cancelled if r['weather']['solar'] is not None]

    success_sunshine = [r['weather']['sunshine'] for r in success if r['weather']['sunshine'] is not None]
    partial_sunshine = [r['weather']['sunshine'] for r in partial if r['weather']['sunshine'] is not None]
    cancelled_sunshine = [r['weather']['sunshine'] for r in cancelled if r['weather']['sunshine'] is not None]

    print("\n" + "=" * 100)
    print("日射量統計")
    print("=" * 100)

    print(f"\n✅ 完全乾燥 (n={len(success_solar)}):")
    if success_solar:
        print(f"  合計全天日射量: min={min(success_solar):.1f}MJ/㎡, max={max(success_solar):.1f}MJ/㎡, mean={statistics.mean(success_solar):.1f}MJ/㎡")
    if success_sunshine:
        print(f"  日照時間: min={min(success_sunshine):.1f}時間, max={max(success_sunshine):.1f}時間, mean={statistics.mean(success_sunshine):.1f}時間")

    print(f"\n⚠️ 部分乾燥 (n={len(partial_solar)}):")
    if partial_solar:
        print(f"  合計全天日射量: min={min(partial_solar):.1f}MJ/㎡, max={max(partial_solar):.1f}MJ/㎡, mean={statistics.mean(partial_solar):.1f}MJ/㎡")
    if partial_sunshine:
        print(f"  日照時間: min={min(partial_sunshine):.1f}時間, max={max(partial_sunshine):.1f}時間, mean={statistics.mean(partial_sunshine):.1f}時間")

    print(f"\n❌ 中止 (n={len(cancelled_solar)}):")
    if cancelled_solar:
        print(f"  合計全天日射量: min={min(cancelled_solar):.1f}MJ/㎡, max={max(cancelled_solar):.1f}MJ/㎡, mean={statistics.mean(cancelled_solar):.1f}MJ/㎡")
    if cancelled_sunshine:
        print(f"  日照時間: min={min(cancelled_sunshine):.1f}時間, max={max(cancelled_sunshine):.1f}時間, mean={statistics.mean(cancelled_sunshine):.1f}時間")

    # Effect size analysis
    print("\n" + "=" * 100)
    print("判別力分析（Cohen's d 効果量）")
    print("=" * 100)

    # Solar radiation analysis
    if success_solar and partial_solar:
        effect = calculate_effect_size(success_solar, partial_solar)
        s_mean = statistics.mean(success_solar)
        p_mean = statistics.mean(partial_solar)
        print(f"\n完全乾燥 vs 部分乾燥:")
        print(f"  合計全天日射量: {s_mean:.1f}MJ/㎡ vs {p_mean:.1f}MJ/㎡")
        print(f"  効果量: {effect:.3f} {'⭐⭐⭐ (Large)' if effect > 0.8 else '⭐⭐ (Medium)' if effect > 0.5 else '⭐ (Small)' if effect > 0.2 else '❌ (Negligible)'}")

    if success_solar and cancelled_solar:
        effect = calculate_effect_size(success_solar, cancelled_solar)
        s_mean = statistics.mean(success_solar)
        c_mean = statistics.mean(cancelled_solar)
        print(f"\n完全乾燥 vs 中止:")
        print(f"  合計全天日射量: {s_mean:.1f}MJ/㎡ vs {c_mean:.1f}MJ/㎡")
        print(f"  効果量: {effect:.3f} {'⭐⭐⭐ (Large)' if effect > 0.8 else '⭐⭐ (Medium)' if effect > 0.5 else '⭐ (Small)' if effect > 0.2 else '❌ (Negligible)'}")

    if partial_solar and cancelled_solar:
        effect = calculate_effect_size(partial_solar, cancelled_solar)
        p_mean = statistics.mean(partial_solar)
        c_mean = statistics.mean(cancelled_solar)
        print(f"\n部分乾燥 vs 中止:")
        print(f"  合計全天日射量: {p_mean:.1f}MJ/㎡ vs {c_mean:.1f}MJ/㎡")
        print(f"  効果量: {effect:.3f} {'⭐⭐⭐ (Large)' if effect > 0.8 else '⭐⭐ (Medium)' if effect > 0.5 else '⭐ (Small)' if effect > 0.2 else '❌ (Negligible)'}")

    # Sunshine hours analysis
    print("\n" + "-" * 100)
    print("【日照時間】")
    print("-" * 100)

    if success_sunshine and partial_sunshine:
        effect = calculate_effect_size(success_sunshine, partial_sunshine)
        s_mean = statistics.mean(success_sunshine)
        p_mean = statistics.mean(partial_sunshine)
        print(f"\n完全乾燥 vs 部分乾燥:")
        print(f"  日照時間: {s_mean:.1f}時間 vs {p_mean:.1f}時間")
        print(f"  効果量: {effect:.3f} {'⭐⭐⭐ (Large)' if effect > 0.8 else '⭐⭐ (Medium)' if effect > 0.5 else '⭐ (Small)' if effect > 0.2 else '❌ (Negligible)'}")

    if success_sunshine and cancelled_sunshine:
        effect = calculate_effect_size(success_sunshine, cancelled_sunshine)
        s_mean = statistics.mean(success_sunshine)
        c_mean = statistics.mean(cancelled_sunshine)
        print(f"\n完全乾燥 vs 中止:")
        print(f"  日照時間: {s_mean:.1f}時間 vs {c_mean:.1f}時間")
        print(f"  効果量: {effect:.3f} {'⭐⭐⭐ (Large)' if effect > 0.8 else '⭐⭐ (Medium)' if effect > 0.5 else '⭐ (Small)' if effect > 0.2 else '❌ (Negligible)'}")

    if partial_sunshine and cancelled_sunshine:
        effect = calculate_effect_size(partial_sunshine, cancelled_sunshine)
        p_mean = statistics.mean(partial_sunshine)
        c_mean = statistics.mean(cancelled_sunshine)
        print(f"\n部分乾燥 vs 中止:")
        print(f"  日照時間: {p_mean:.1f}時間 vs {c_mean:.1f}時間")
        print(f"  効果量: {effect:.3f} {'⭐⭐⭐ (Large)' if effect > 0.8 else '⭐⭐ (Medium)' if effect > 0.5 else '⭐ (Small)' if effect > 0.2 else '❌ (Negligible)'}")

    # Detailed records comparison
    print("\n" + "=" * 100)
    print("詳細記録（日射量あり）")
    print("=" * 100)
    print(f"{'日付':>10} | {'結果':12} | {'日射量':>8} | {'日照':>6} | {'湿度':>5} | {'降水':>5}")
    print("-" * 100)

    all_records = []
    all_records.extend([('完全乾燥', r) for r in success])
    all_records.extend([('部分乾燥', r) for r in partial])
    all_records.extend([('中止', r) for r in cancelled])

    all_records.sort(key=lambda x: x[1]['date'])

    for result, record in all_records:
        w = record['weather']
        if w['solar'] is None:
            continue

        solar = f"{w['solar']:.1f}" if w['solar'] is not None else "N/A"
        sunshine = f"{w['sunshine']:.1f}" if w['sunshine'] is not None else "N/A"
        humidity = f"{w['humidity']:.0f}" if w['humidity'] is not None else "N/A"
        precip = f"{w['precip']:.1f}" if w['precip'] is not None else "N/A"

        print(f"{record['date']:>10} | {result:12} | {solar:>6}MJ/㎡ | {sunshine:>4}h | {humidity:>4}% | {precip:>4}mm")

    # Threshold recommendation
    print("\n" + "=" * 100)
    print("日照時間閾値の検討")
    print("=" * 100)

    if success_sunshine:
        success_min = min(success_sunshine)
        success_mean = statistics.mean(success_sunshine)

        print(f"\n完全乾燥の日照時間:")
        print(f"  最小: {success_min:.1f}時間")
        print(f"  平均: {success_mean:.1f}時間")

        if partial_sunshine:
            partial_mean = statistics.mean(partial_sunshine)
            print(f"\n部分乾燥の日照時間:")
            print(f"  平均: {partial_mean:.1f}時間")

            if cancelled_sunshine:
                cancelled_mean = statistics.mean(cancelled_sunshine)
                print(f"\n中止の日照時間:")
                print(f"  平均: {cancelled_mean:.1f}時間")

            if success_mean > partial_mean:
                print(f"\n→ 完全乾燥の方が日照時間が長い（{success_mean:.1f} > {partial_mean:.1f}時間）")
                print(f"  推奨閾値: ≥ {success_min:.1f}時間 (成功の最小値)")
                print(f"  理想値: ≥ {success_mean:.1f}時間 (成功の平均値)")
            else:
                print(f"\n⚠️ 部分乾燥の方が日照時間が長い（{partial_mean:.1f} > {success_mean:.1f}時間）")
                print("  → 日照が長くても他の要因（降水・湿度）で失敗")
                print("  → 日照時間は判別に有効でない可能性")

    print("\n" + "=" * 100)

if __name__ == '__main__':
    main()
