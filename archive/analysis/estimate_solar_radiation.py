#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
日照時間から日射量を推定
"""
import csv
import sys
import io
from datetime import datetime
import statistics
import math

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def parse_amedas_data():
    """Parse JMA Amedas CSV data - check all available columns"""
    with open('data.csv', 'r', encoding='cp932') as f:
        lines = f.readlines()

    header_idx = None
    for i, line in enumerate(lines):
        if '年月日' in line:
            header_idx = i
            break

    if header_idx is None:
        return {}, []

    header_line = lines[header_idx]
    headers = [h.strip() for h in header_line.split(',')]

    print("=" * 100)
    print("利用可能なカラム（最初の50項目）")
    print("=" * 100)
    unique_headers = []
    for i, h in enumerate(headers[:50]):
        if h and h not in unique_headers:
            unique_headers.append(h)
            print(f"{i:3d}: {h}")

    # Find key indices
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

    print(f"\n検出されたインデックス:")
    for key, idx in indices.items():
        print(f"  {key}: {idx}")

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
                'humidity': safe_float('humidity')
            }
        except:
            continue

    return weather_data, unique_headers

def estimate_solar_from_sunshine(sunshine_hours, date_str):
    """
    日照時間から日射量を推定

    理論式：
    - 快晴時の日射量 = 可照時間 × 単位時間あたり日射量
    - 実際の日射量 = 快晴時日射量 × (日照時間/可照時間)

    利尻島（北緯45度）の夏季（6-8月）の推定：
    - 可照時間: 約16時間
    - 快晴時日射量: 約25-30 MJ/㎡/日
    """

    # Parse month from date
    try:
        month = int(date_str.split('-')[1])
    except:
        month = 7  # Default to July

    # Maximum possible sunshine hours (季節による変動)
    if month == 6:
        max_sunshine = 16.5  # June
        clear_sky_solar = 28.0  # MJ/㎡
    elif month == 7:
        max_sunshine = 16.0  # July
        clear_sky_solar = 27.0  # MJ/㎡
    elif month == 8:
        max_sunshine = 14.5  # August
        clear_sky_solar = 24.0  # MJ/㎡
    else:
        max_sunshine = 15.0
        clear_sky_solar = 26.0

    if sunshine_hours is None or sunshine_hours < 0:
        return None

    # 日照率から日射量を推定
    sunshine_ratio = min(sunshine_hours / max_sunshine, 1.0)

    # 経験式: 実際の日射量 = 快晴時 × (0.25 + 0.75 × 日照率)
    # これは一般的な推定式（Angstrom-Prescott式の簡易版）
    estimated_solar = clear_sky_solar * (0.25 + 0.75 * sunshine_ratio)

    return estimated_solar

def main():
    weather_data, headers = parse_amedas_data()

    print("\n" + "=" * 100)
    print("日照時間と日射量の関係分析")
    print("=" * 100)

    # Collect data with both sunshine and solar
    sunshine_solar_pairs = []
    sunshine_only = []

    for date, data in sorted(weather_data.items()):
        sunshine = data['sunshine']
        solar = data['solar']

        if sunshine is not None and solar is not None:
            sunshine_solar_pairs.append((date, sunshine, solar))
        elif sunshine is not None:
            sunshine_only.append((date, sunshine))

    print(f"\n日照時間と日射量の両方があるデータ: {len(sunshine_solar_pairs)}件")
    print(f"日照時間のみのデータ: {len(sunshine_only)}件")

    if sunshine_solar_pairs:
        print("\n" + "-" * 100)
        print("実測データの相関確認")
        print("-" * 100)
        print(f"{'日付':>10} | {'日照時間':>8} | {'実測日射量':>10}")
        print("-" * 100)

        for date, sunshine, solar in sunshine_solar_pairs[:10]:
            print(f"{date:>10} | {sunshine:>6.1f}h | {solar:>8.1f}MJ/㎡")

        if len(sunshine_solar_pairs) > 10:
            print(f"  ... 他 {len(sunshine_solar_pairs) - 10}件")

        # Calculate correlation if we have data
        sunshines = [s for _, s, _ in sunshine_solar_pairs]
        solars = [r for _, _, r in sunshine_solar_pairs]

        mean_sunshine = statistics.mean(sunshines)
        mean_solar = statistics.mean(solars)

        # Pearson correlation
        numerator = sum((s - mean_sunshine) * (r - mean_solar) for s, r in zip(sunshines, solars))
        denom_s = sum((s - mean_sunshine)**2 for s in sunshines) ** 0.5
        denom_r = sum((r - mean_solar)**2 for r in solars) ** 0.5

        if denom_s > 0 and denom_r > 0:
            correlation = numerator / (denom_s * denom_r)
            print(f"\n相関係数: {correlation:.3f}")

    # Estimate solar radiation from sunshine for dates without solar data
    print("\n" + "=" * 100)
    print("日照時間から日射量を推定")
    print("=" * 100)

    if sunshine_only:
        print(f"\n推定対象: {len(sunshine_only)}件")
        print(f"{'日付':>10} | {'日照時間':>8} | {'推定日射量':>10}")
        print("-" * 100)

        for date, sunshine in sunshine_only[:15]:
            estimated_solar = estimate_solar_from_sunshine(sunshine, date)
            if estimated_solar is not None:
                print(f"{date:>10} | {sunshine:>6.1f}h | {estimated_solar:>8.1f}MJ/㎡")

    # Validate estimation accuracy if we have actual data
    if sunshine_solar_pairs:
        print("\n" + "=" * 100)
        print("推定精度の検証")
        print("=" * 100)

        errors = []
        for date, sunshine, actual_solar in sunshine_solar_pairs:
            estimated_solar = estimate_solar_from_sunshine(sunshine, date)
            if estimated_solar is not None:
                error = abs(actual_solar - estimated_solar)
                rel_error = error / actual_solar * 100 if actual_solar > 0 else 0
                errors.append((error, rel_error))

        if errors:
            abs_errors = [e[0] for e in errors]
            rel_errors = [e[1] for e in errors]

            print(f"\n絶対誤差: mean={statistics.mean(abs_errors):.2f}MJ/㎡, median={statistics.median(abs_errors):.2f}MJ/㎡")
            print(f"相対誤差: mean={statistics.mean(rel_errors):.1f}%, median={statistics.median(rel_errors):.1f}%")

            print("\n推定式の精度:")
            if statistics.mean(rel_errors) < 10:
                print("  ✅ 優秀（相対誤差 < 10%）")
            elif statistics.mean(rel_errors) < 20:
                print("  ✅ 良好（相対誤差 < 20%）")
            elif statistics.mean(rel_errors) < 30:
                print("  ⚠️ 許容範囲（相対誤差 < 30%）")
            else:
                print("  ❌ 精度不足（相対誤差 ≥ 30%）")

    print("\n" + "=" * 100)

if __name__ == '__main__':
    main()
