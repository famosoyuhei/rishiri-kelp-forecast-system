#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
実測データと記録の矛盾点・異常値を検出
追加調査が必要なケースを特定
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
                'temp': safe_float('temp'),
                'precip': safe_float('precip'),
                'sunshine': safe_float('sunshine'),
                'wind_avg': safe_float('wind_avg'),
                'wind_max': safe_float('wind_max'),
                'humidity': safe_float('humidity')
            }
        except:
            continue

    return weather_data

def main():
    records = load_drying_records()
    weather_data = parse_amedas_data()

    print("=" * 100)
    print("実測データと記録の矛盾点・異常値検出")
    print("=" * 100)

    # Categorize records
    anomalies = []

    # Known thresholds from actual data analysis
    success_humidity_mean = 87.3
    success_humidity_max = 99.0
    success_wind_avg_min = 1.6
    success_sunshine_min = 0.3

    for record in records:
        date_str = record['date']
        result = record['result']

        if date_str not in weather_data:
            continue

        weather = weather_data[date_str]

        issues = []
        flags = []

        # Case 1: 完全乾燥だが条件が悪い
        if result == '完全乾燥':
            if weather['humidity'] and weather['humidity'] > 95:
                issues.append(f"湿度極めて高い({weather['humidity']:.0f}%)")
                flags.append('HIGH_HUMIDITY_SUCCESS')

            if weather['sunshine'] and weather['sunshine'] < 1.0:
                issues.append(f"日照極めて短い({weather['sunshine']:.1f}h)")
                flags.append('LOW_SUNSHINE_SUCCESS')

            if weather['wind_avg'] and weather['wind_avg'] < 2.0:
                issues.append(f"風速極めて弱い({weather['wind_avg']:.1f}m/s)")
                flags.append('LOW_WIND_SUCCESS')

        # Case 2: 中止/部分乾燥だが条件が良い
        elif result in ['中止', '干したが完全には乾かせなかった（泣）']:
            if weather['precip'] and weather['precip'] == 0:
                if weather['humidity'] and weather['humidity'] < 85:
                    if weather['sunshine'] and weather['sunshine'] > 8:
                        issues.append(f"好条件なのに失敗(湿度{weather['humidity']:.0f}%, 日照{weather['sunshine']:.1f}h)")
                        flags.append('GOOD_CONDITIONS_FAILURE')

        # Case 3: 降水0mmだが部分乾燥/中止
        if result in ['干したが完全には乾かせなかった（泣）', '中止']:
            if weather['precip'] and weather['precip'] == 0:
                issues.append(f"API降水0mmだが失敗 → 霧雨・通り雨の可能性")
                flags.append('ZERO_PRECIP_FAILURE')

        # Case 4: 同日に複数記録（結果が分かれている）
        same_day_records = [r for r in records if r['date'] == date_str]
        if len(same_day_records) > 1:
            results_set = set(r['result'] for r in same_day_records)
            if len(results_set) > 1:
                issues.append(f"同日に{len(same_day_records)}件記録、結果分散")
                flags.append('MULTI_SPOT_DIVERGENCE')

        # Case 5: 湿度データ欠損
        if weather['humidity'] is None:
            issues.append("湿度データなし")
            flags.append('MISSING_HUMIDITY')

        # Case 6: 極端な気象条件
        if weather['wind_max'] and weather['wind_max'] > 10:
            issues.append(f"強風({weather['wind_max']:.1f}m/s)")
            flags.append('STRONG_WIND')

        if weather['temp'] and weather['temp'] > 25:
            issues.append(f"高温({weather['temp']:.1f}°C)")
            flags.append('HIGH_TEMP')

        if issues:
            anomalies.append({
                'date': date_str,
                'spot': record['name'],
                'result': result,
                'weather': weather,
                'issues': issues,
                'flags': flags
            })

    # Report anomalies
    print(f"\n検出された異常・矛盾: {len(anomalies)}件")

    # Group by flag type
    flag_groups = {}
    for anomaly in anomalies:
        for flag in anomaly['flags']:
            if flag not in flag_groups:
                flag_groups[flag] = []
            flag_groups[flag].append(anomaly)

    print("\n" + "=" * 100)
    print("【カテゴリ別異常】")
    print("=" * 100)

    flag_descriptions = {
        'HIGH_HUMIDITY_SUCCESS': '湿度95%超でも完全乾燥成功',
        'LOW_SUNSHINE_SUCCESS': '日照1時間未満でも完全乾燥成功',
        'LOW_WIND_SUCCESS': '風速2m/s未満でも完全乾燥成功',
        'GOOD_CONDITIONS_FAILURE': '好条件なのに失敗',
        'ZERO_PRECIP_FAILURE': 'API降水0mmなのに失敗（霧雨・通り雨の可能性）',
        'MULTI_SPOT_DIVERGENCE': '同日複数地点で結果分散（局地気象差）',
        'MISSING_HUMIDITY': '湿度データ欠損',
        'STRONG_WIND': '強風（10m/s超）',
        'HIGH_TEMP': '高温（25°C超）'
    }

    for flag, desc in flag_descriptions.items():
        if flag in flag_groups:
            print(f"\n■ {desc} ({len(flag_groups[flag])}件)")
            print("-" * 100)

            for anomaly in flag_groups[flag][:5]:  # Show first 5
                w = anomaly['weather']
                print(f"\n  {anomaly['date']} | {anomaly['result']}")
                print(f"    降水: {w['precip']:.1f}mm" if w['precip'] is not None else "    降水: N/A")
                print(f"    湿度: {w['humidity']:.0f}%" if w['humidity'] is not None else "    湿度: N/A")
                print(f"    日照: {w['sunshine']:.1f}h" if w['sunshine'] is not None else "    日照: N/A")
                print(f"    風速: {w['wind_avg']:.1f}m/s" if w['wind_avg'] is not None else "    風速: N/A")
                print(f"    問題: {', '.join(anomaly['issues'])}")

            if len(flag_groups[flag]) > 5:
                print(f"\n  ... 他 {len(flag_groups[flag]) - 5}件")

    # Recommend additional data needs
    print("\n" + "=" * 100)
    print("【推奨される追加データ】")
    print("=" * 100)

    recommendations = []

    if 'ZERO_PRECIP_FAILURE' in flag_groups:
        recommendations.append({
            'priority': 'HIGH',
            'data': '1時間ごとの降水量データ',
            'reason': f'{len(flag_groups["ZERO_PRECIP_FAILURE"])}件でAPI日合計0mmだが失敗。霧雨・通り雨を検出するため',
            'source': '気象庁アメダス時別値（CSV手動ダウンロード）'
        })

    if 'MULTI_SPOT_DIVERGENCE' in flag_groups:
        recommendations.append({
            'priority': 'HIGH',
            'data': '本泊観測所の湿度データ',
            'reason': f'{len(flag_groups["MULTI_SPOT_DIVERGENCE"])}件で同日に結果分散。島内の気象差を把握するため',
            'source': '気象庁アメダス（本泊）または複数地点データ'
        })

    if 'HIGH_HUMIDITY_SUCCESS' in flag_groups:
        recommendations.append({
            'priority': 'MEDIUM',
            'data': 'ラジオゾンデ850hPa湿度',
            'reason': f'{len(flag_groups["HIGH_HUMIDITY_SUCCESS"])}件で高湿度でも成功。中層乾燥が影響か確認',
            'source': 'University of Wyoming (稚内47401)'
        })

    if 'LOW_WIND_SUCCESS' in flag_groups or 'LOW_SUNSHINE_SUCCESS' in flag_groups:
        recommendations.append({
            'priority': 'LOW',
            'data': '時別気温・湿度・風速',
            'reason': '弱風・低日照でも成功。作業時間帯（4-16時）の詳細条件を確認',
            'source': '気象庁アメダス時別値'
        })

    # Sort by priority
    priority_order = {'HIGH': 0, 'MEDIUM': 1, 'LOW': 2}
    recommendations.sort(key=lambda x: priority_order[x['priority']])

    for i, rec in enumerate(recommendations, 1):
        print(f"\n{i}. [{rec['priority']}] {rec['data']}")
        print(f"   理由: {rec['reason']}")
        print(f"   取得元: {rec['source']}")

    # Specific dates for further investigation
    print("\n" + "=" * 100)
    print("【詳細調査推奨日】")
    print("=" * 100)

    high_priority_dates = set()

    # Dates with multiple issues
    date_issue_count = {}
    for anomaly in anomalies:
        date = anomaly['date']
        if date not in date_issue_count:
            date_issue_count[date] = 0
        date_issue_count[date] += len(anomaly['flags'])

    for date, count in sorted(date_issue_count.items(), key=lambda x: -x[1])[:10]:
        date_anomalies = [a for a in anomalies if a['date'] == date]
        results = set(a['result'] for a in date_anomalies)

        print(f"\n{date}: {count}個の異常フラグ")
        print(f"  記録数: {len(date_anomalies)}件")
        print(f"  結果: {', '.join(results)}")

        # List flags
        all_flags = set()
        for a in date_anomalies:
            all_flags.update(a['flags'])
        print(f"  フラグ: {', '.join(all_flags)}")

    print("\n" + "=" * 100)

if __name__ == '__main__':
    main()
