#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
雲量と日照時間の相関分析
雲量を使った日射量推定の精度向上
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
        elif header == '日照時間(時間)' and 'sunshine' not in indices:
            indices['sunshine'] = i
        elif header == '合計全天日射量(MJ/㎡)' and 'solar' not in indices:
            indices['solar'] = i
        elif header == '降水量の合計(mm)' and 'precip' not in indices:
            indices['precip'] = i
        elif header == '平均雲量(10分比)' and 'cloud' not in indices:
            indices['cloud'] = i
        elif header == '平均湿度(％)' and 'humidity' not in indices:
            indices['humidity'] = i
        elif header == '平均気温(℃)' and 'temp' not in indices:
            indices['temp'] = i

    weather_data = {}
    for line in lines[header_idx + 2:]:
        if not line.strip():
            continue

        cols = [c.strip() for c in line.split(',')]
        if 'date' not in indices or indices['date'] >= len(cols):
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
                'sunshine': safe_float('sunshine'),
                'solar': safe_float('solar'),
                'precip': safe_float('precip'),
                'cloud': safe_float('cloud'),
                'humidity': safe_float('humidity'),
                'temp': safe_float('temp')
            }
        except:
            continue

    return weather_data

def estimate_solar_improved(sunshine_hours, cloud_cover, date_str):
    """
    雲量と日照時間を組み合わせた日射量推定

    パラメータ:
    - sunshine_hours: 日照時間（時間）
    - cloud_cover: 平均雲量（10分比、0-10）
    - date_str: 日付（月による補正）
    """
    try:
        month = int(date_str.split('-')[1])
    except:
        month = 7

    # 季節による快晴時日射量と可照時間
    if month == 6:
        max_sunshine = 16.5
        clear_sky_solar = 28.0
    elif month == 7:
        max_sunshine = 16.0
        clear_sky_solar = 27.0
    elif month == 8:
        max_sunshine = 14.5
        clear_sky_solar = 24.0
    else:
        max_sunshine = 15.0
        clear_sky_solar = 26.0

    # 方法1: 日照時間のみ（Angstrom-Prescott式）
    if sunshine_hours is not None:
        sunshine_ratio = min(sunshine_hours / max_sunshine, 1.0)
        solar_from_sunshine = clear_sky_solar * (0.25 + 0.75 * sunshine_ratio)
    else:
        solar_from_sunshine = None

    # 方法2: 雲量のみ
    if cloud_cover is not None:
        # 雲量が多いほど日射量が減少
        # 経験式: 日射量 = 快晴時 × (1 - 0.75 × 雲量/10)
        cloud_fraction = cloud_cover / 10.0
        solar_from_cloud = clear_sky_solar * (1 - 0.65 * cloud_fraction)
    else:
        solar_from_cloud = None

    # 方法3: 日照時間と雲量の組み合わせ
    if sunshine_hours is not None and cloud_cover is not None:
        # 日照時間の重みを0.6、雲量の重みを0.4として組み合わせ
        solar_combined = 0.6 * solar_from_sunshine + 0.4 * solar_from_cloud
        return {
            'sunshine_based': solar_from_sunshine,
            'cloud_based': solar_from_cloud,
            'combined': solar_combined
        }
    elif sunshine_hours is not None:
        return {
            'sunshine_based': solar_from_sunshine,
            'cloud_based': None,
            'combined': solar_from_sunshine
        }
    elif cloud_cover is not None:
        return {
            'sunshine_based': None,
            'cloud_based': solar_from_cloud,
            'combined': solar_from_cloud
        }
    else:
        return None

def main():
    weather_data = parse_amedas_data()
    records = load_drying_records()

    print("=" * 100)
    print("雲量と日照時間の相関分析")
    print("=" * 100)

    # Collect pairs
    cloud_sunshine_pairs = []
    for date, data in sorted(weather_data.items()):
        if data['cloud'] is not None and data['sunshine'] is not None:
            cloud_sunshine_pairs.append((date, data['cloud'], data['sunshine']))

    print(f"\n雲量と日照時間の両方があるデータ: {len(cloud_sunshine_pairs)}件")

    if cloud_sunshine_pairs:
        print("\n" + "-" * 100)
        print(f"{'日付':>10} | {'雲量':>6} | {'日照時間':>8} | {'降水':>5}")
        print("-" * 100)

        for date, cloud, sunshine in cloud_sunshine_pairs[:20]:
            precip = weather_data[date]['precip']
            precip_str = f"{precip:.1f}" if precip is not None else "N/A"
            print(f"{date:>10} | {cloud:>4.1f}/10 | {sunshine:>6.1f}h | {precip:>4}mm")

        # Calculate correlation
        clouds = [c for _, c, _ in cloud_sunshine_pairs]
        sunshines = [s for _, _, s in cloud_sunshine_pairs]

        mean_cloud = statistics.mean(clouds)
        mean_sunshine = statistics.mean(sunshines)

        numerator = sum((c - mean_cloud) * (s - mean_sunshine) for c, s in zip(clouds, sunshines))
        denom_c = sum((c - mean_cloud)**2 for c in clouds) ** 0.5
        denom_s = sum((s - mean_sunshine)**2 for s in sunshines) ** 0.5

        if denom_c > 0 and denom_s > 0:
            correlation = numerator / (denom_c * denom_s)
            print(f"\n雲量と日照時間の相関係数: {correlation:.3f}")
            if correlation < -0.7:
                print("  → 強い負の相関（雲が多いほど日照が少ない）✅")
            elif correlation < -0.5:
                print("  → 中程度の負の相関")
            else:
                print("  → 弱い相関")

    # Analyze drying records with cloud and sunshine data
    print("\n" + "=" * 100)
    print("昆布干場記録の雲量・日照分析")
    print("=" * 100)

    success = []
    partial = []
    cancelled = []

    for record in records:
        date_str = record['date']
        if date_str not in weather_data:
            continue

        data = weather_data[date_str]
        result = record['result']

        if data['cloud'] is not None or data['sunshine'] is not None:
            record_data = {
                'date': date_str,
                'result': result,
                'cloud': data['cloud'],
                'sunshine': data['sunshine'],
                'humidity': data['humidity'],
                'precip': data['precip']
            }

            if result == '完全乾燥':
                success.append(record_data)
            elif result == '干したが完全には乾かせなかった（泣）':
                partial.append(record_data)
            elif result == '中止':
                cancelled.append(record_data)

    def print_category_stats(label, records):
        if not records:
            return

        clouds = [r['cloud'] for r in records if r['cloud'] is not None]
        sunshines = [r['sunshine'] for r in records if r['sunshine'] is not None]

        print(f"\n{label} (n={len(records)}):")
        if clouds:
            print(f"  雲量: min={min(clouds):.1f}/10, max={max(clouds):.1f}/10, mean={statistics.mean(clouds):.1f}/10")
        if sunshines:
            print(f"  日照: min={min(sunshines):.1f}h, max={max(sunshines):.1f}h, mean={statistics.mean(sunshines):.1f}h")

    print_category_stats("✅ 完全乾燥", success)
    print_category_stats("⚠️ 部分乾燥", partial)
    print_category_stats("❌ 中止", cancelled)

    # Effect size for cloud cover
    print("\n" + "=" * 100)
    print("雲量の判別力分析")
    print("=" * 100)

    def calculate_effect_size(group1, group2):
        if len(group1) < 2 or len(group2) < 2:
            return 0.0
        mean1 = statistics.mean(group1)
        mean2 = statistics.mean(group2)
        std1 = statistics.stdev(group1)
        std2 = statistics.stdev(group2)
        pooled_std = ((std1**2 + std2**2) / 2) ** 0.5
        if pooled_std == 0:
            return 0.0
        return abs(mean1 - mean2) / pooled_std

    success_cloud = [r['cloud'] for r in success if r['cloud'] is not None]
    partial_cloud = [r['cloud'] for r in partial if r['cloud'] is not None]
    cancelled_cloud = [r['cloud'] for r in cancelled if r['cloud'] is not None]

    if success_cloud and partial_cloud:
        effect = calculate_effect_size(success_cloud, partial_cloud)
        print(f"\n完全乾燥 vs 部分乾燥:")
        print(f"  雲量: {statistics.mean(success_cloud):.1f}/10 vs {statistics.mean(partial_cloud):.1f}/10")
        print(f"  効果量: {effect:.3f} {'⭐⭐⭐ (Large)' if effect > 0.8 else '⭐⭐ (Medium)' if effect > 0.5 else '⭐ (Small)' if effect > 0.2 else '❌ (Negligible)'}")

    if success_cloud and cancelled_cloud:
        effect = calculate_effect_size(success_cloud, cancelled_cloud)
        print(f"\n完全乾燥 vs 中止:")
        print(f"  雲量: {statistics.mean(success_cloud):.1f}/10 vs {statistics.mean(cancelled_cloud):.1f}/10")
        print(f"  効果量: {effect:.3f} {'⭐⭐⭐ (Large)' if effect > 0.8 else '⭐⭐ (Medium)' if effect > 0.5 else '⭐ (Small)' if effect > 0.2 else '❌ (Negligible)'}")

    # Solar radiation estimation comparison
    print("\n" + "=" * 100)
    print("日射量推定の比較（日照時間のみ vs 雲量併用）")
    print("=" * 100)

    print(f"\n{'日付':>10} | {'結果':12} | {'雲量':>6} | {'日照':>6} | {'日照ベース':>10} | {'雲量ベース':>10} | {'併用':>10}")
    print("-" * 100)

    for record in success[:10] + partial[:5]:
        date = record['date']
        result = record['result']
        cloud = record['cloud']
        sunshine = record['sunshine']

        if sunshine is not None:
            solar_est = estimate_solar_improved(sunshine, cloud, date)
            if solar_est:
                cloud_str = f"{cloud:.1f}" if cloud is not None else "N/A"
                sunshine_str = f"{sunshine:.1f}" if sunshine is not None else "N/A"
                sun_based = f"{solar_est['sunshine_based']:.1f}" if solar_est['sunshine_based'] is not None else "N/A"
                cloud_based = f"{solar_est['cloud_based']:.1f}" if solar_est['cloud_based'] is not None else "N/A"
                combined = f"{solar_est['combined']:.1f}" if solar_est['combined'] is not None else "N/A"

                print(f"{date:>10} | {result:12} | {cloud_str:>4}/10 | {sunshine_str:>4}h | {sun_based:>8}MJ/㎡ | {cloud_based:>8}MJ/㎡ | {combined:>8}MJ/㎡")

    print("\n" + "=" * 100)

if __name__ == '__main__':
    main()
