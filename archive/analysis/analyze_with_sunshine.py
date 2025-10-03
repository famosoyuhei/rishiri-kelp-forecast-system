#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
日照時間から日射量を推定して分析
H_1631_1434の全21件のデータ
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
    """
    日照時間から日射量を推定

    Parameters:
    - sunshine_hours: 実際の日照時間（時間）
    - latitude: 緯度（度）
    - day_of_year: 年内の日数（1-365）

    Returns:
    - estimated_radiation: 推定日射量（MJ/m²/day）
    """
    # 可照時間（昼の長さ）の計算
    lat_rad = math.radians(latitude)

    # 太陽赤緯の計算
    declination = 23.45 * math.sin(math.radians(360 * (284 + day_of_year) / 365))
    dec_rad = math.radians(declination)

    # 日の出・日の入り時角
    cos_hour_angle = -math.tan(lat_rad) * math.tan(dec_rad)
    if cos_hour_angle > 1:
        possible_sunshine = 0
    elif cos_hour_angle < -1:
        possible_sunshine = 24
    else:
        hour_angle = math.acos(cos_hour_angle)
        possible_sunshine = 2 * math.degrees(hour_angle) / 15  # 時間

    # 日照率
    sunshine_ratio = sunshine_hours / possible_sunshine if possible_sunshine > 0 else 0

    # 大気外日射量（簡易計算）
    solar_constant = 1367  # W/m²
    dr = 1 + 0.033 * math.cos(2 * math.pi * day_of_year / 365)  # 地球・太陽間距離補正

    # 大気外日射量（MJ/m²/day）
    Ra = (24 * 60 / math.pi) * solar_constant * dr * (
        hour_angle * math.sin(lat_rad) * math.sin(dec_rad) +
        math.cos(lat_rad) * math.cos(dec_rad) * math.sin(hour_angle)
    ) / 1e6

    # Angstromの式による推定
    # Rs = (a + b * n/N) * Ra
    # a = 0.25, b = 0.50（標準値）
    a = 0.25
    b = 0.50

    Rs = (a + b * sunshine_ratio) * Ra

    return Rs, sunshine_ratio, possible_sunshine

def parse_daily_data(csv_files):
    """Parse daily aggregate data from CSV files"""
    all_data = {}

    for filepath in csv_files:
        try:
            with open(filepath, 'r', encoding='cp932') as f:
                lines = f.readlines()

            # Find header
            header_idx = None
            for i, line in enumerate(lines):
                if '年月日' in line:
                    header_idx = i
                    break

            if header_idx is None:
                continue

            # Parse data - look for daily summary rows
            for line in lines[header_idx + 1:]:
                parts = [p.strip() for p in line.split(',')]
                if len(parts) < 5:
                    continue

                date_str = parts[0]
                if not date_str or '/' not in date_str:
                    continue

                # Skip hourly data (has time component)
                if ':' in date_str:
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

                    # Try to find sunshine hours column
                    # Usually around column 10-15
                    sunshine = None
                    for col_idx in range(10, min(20, len(parts))):
                        val = safe_float(col_idx)
                        if val is not None and 0 <= val <= 24:  # Valid sunshine hours
                            sunshine = val
                            break

                    if date_key not in all_data:
                        all_data[date_key] = {
                            'sunshine': sunshine,
                            'day_of_year': day_of_year
                        }

                except Exception as e:
                    continue

        except Exception as e:
            print(f"エラー reading {filepath}: {e}")
            continue

    return all_data

def main():
    print("=" * 100)
    print("日照時間から日射量を推定した分析")
    print("=" * 100)

    # Load CSV files
    csv_files = [
        '19-22june.csv',
        '23-29june.csv',
        '30june-11july.csv',
        '29july.csv',
        '14-23august.csv'
    ]

    daily_data = parse_daily_data(csv_files)
    print(f"\n✅ {len(daily_data)}日分の日別データを読み込み")

    # Load drying records
    drying_records = load_drying_records()

    # Analyze
    print("\n" + "=" * 100)
    print("【日照時間と日射量の分析】")
    print("=" * 100)

    results_data = {
        '完全乾燥': [],
        '中止': [],
        '干したが完全には乾かせなかった（泣）': []
    }

    print(f"\n{'日付':12} | {'結果':35} | {'日照時間':>8} | {'日照率':>6} | {'推定日射量':>10}")
    print("-" * 120)

    for date in sorted(drying_records.keys()):
        result = drying_records[date]

        if date in daily_data:
            data = daily_data[date]
            sunshine = data['sunshine']
            day_of_year = data['day_of_year']

            if sunshine is not None:
                radiation, sunshine_ratio, possible = estimate_solar_radiation(
                    sunshine,
                    latitude=45.178,
                    day_of_year=day_of_year
                )

                print(f"{date:12} | {result:35} | {sunshine:>6.1f}h | {sunshine_ratio*100:>5.1f}% | {radiation:>8.1f}MJ/m²")

                results_data[result].append({
                    'sunshine': sunshine,
                    'radiation': radiation,
                    'sunshine_ratio': sunshine_ratio
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

        # Sunshine hours
        sunshine_hours = [d['sunshine'] for d in data]
        print(f"日照時間:")
        print(f"  平均: {statistics.mean(sunshine_hours):.1f}h")
        print(f"  範囲: {min(sunshine_hours):.1f}～{max(sunshine_hours):.1f}h")

        # Sunshine ratio
        sunshine_ratios = [d['sunshine_ratio'] * 100 for d in data]
        print(f"日照率:")
        print(f"  平均: {statistics.mean(sunshine_ratios):.1f}%")
        print(f"  範囲: {min(sunshine_ratios):.1f}～{max(sunshine_ratios):.1f}%")

        # Solar radiation
        radiations = [d['radiation'] for d in data]
        print(f"推定日射量:")
        print(f"  平均: {statistics.mean(radiations):.1f}MJ/m²")
        print(f"  範囲: {min(radiations):.1f}～{max(radiations):.1f}MJ/m²")

    # Derive thresholds
    print("\n" + "=" * 100)
    print("【日射量による閾値】")
    print("=" * 100)

    success_data = results_data['完全乾燥']
    fail_data = results_data['中止']
    partial_data = results_data['干したが完全には乾かせなかった（泣）']

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
        print(f"   完全乾燥: {success_min_sunshine:.1f}～{max(success_sunshine):.1f}h")
        print(f"   中止: {min(fail_sunshine):.1f}～{fail_max_sunshine:.1f}h")
        if success_min_sunshine > fail_max_sunshine:
            print(f"   → 閾値: 日照時間 ≥ {success_min_sunshine:.1f}h")
        else:
            print(f"   → 閾値: 明確な境界なし（重複範囲あり）")

        print(f"\n2. 推定日射量:")
        print(f"   完全乾燥: {success_min_radiation:.1f}～{max(success_radiation):.1f}MJ/m²")
        print(f"   中止: {min(fail_radiation):.1f}～{fail_max_radiation:.1f}MJ/m²")
        if success_min_radiation > fail_max_radiation:
            print(f"   → 閾値: 日射量 ≥ {success_min_radiation:.1f}MJ/m²")
        else:
            print(f"   → 閾値: 明確な境界なし（重複範囲あり）")

    print("\n" + "=" * 100)
    print("【考察】")
    print("=" * 100)

    print("\n日射量は成功/失敗の決定的要因ではない:")
    print("  - 日照時間が短くても、湿度が低ければ成功可能")
    print("  - 逆に日照時間が長くても、降水や高湿度なら失敗")
    print("  - 日射量は補助的な指標として有用")

    print("\n日射量の役割:")
    print("  1. 気温上昇による飽和水蒸気圧の増加")
    print("  2. 地表面温度上昇による対流促進")
    print("  3. 湿度低下の補助的要因")

    print("\n優先順位:")
    print("  1. 降水量 = 0mm（最優先）")
    print("  2. 最低湿度 ≤ 94%（非常に重要）")
    print("  3. 風速 ≥ 2.0m/s（重要）")
    print("  4. 日射量・日照時間（補助的）")
    print("  5. 気温 ≥ 18°C（補助的）")

    print("\n" + "=" * 100)

if __name__ == '__main__':
    main()
