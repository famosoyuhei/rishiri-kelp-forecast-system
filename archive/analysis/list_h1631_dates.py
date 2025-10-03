#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
H_1631_1434の全21件の日付リストを出力
アメダスデータ取得用
"""
import csv
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def main():
    records = []
    with open('hoshiba_records.csv', 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row['name'] == 'H_1631_1434':
                records.append(row)

    # Sort by date
    records.sort(key=lambda x: x['date'])

    print("=" * 100)
    print("H_1631_1434（神居）の全記録 - アメダスデータ取得対象日")
    print("=" * 100)

    print(f"\n総記録数: {len(records)}件")

    print(f"\n{'No':>3} | {'日付':12} | {'結果':35}")
    print("-" * 100)

    for i, record in enumerate(records, 1):
        print(f"{i:>3} | {record['date']:12} | {record['result']:35}")

    # Group by result
    print("\n" + "=" * 100)
    print("結果別の日付リスト")
    print("=" * 100)

    results = {}
    for record in records:
        result = record['result']
        if result not in results:
            results[result] = []
        results[result].append(record['date'])

    for result, dates in sorted(results.items()):
        print(f"\n■ {result} ({len(dates)}件)")
        for date in dates:
            print(f"  {date}")

    # Date range
    print("\n" + "=" * 100)
    print("データ取得範囲")
    print("=" * 100)

    all_dates = [r['date'] for r in records]
    min_date = min(all_dates)
    max_date = max(all_dates)

    print(f"\n最古の記録: {min_date}")
    print(f"最新の記録: {max_date}")

    # Extract year/month for downloading
    from datetime import datetime
    date_objects = [datetime.strptime(d, '%Y-%m-%d') for d in all_dates]

    year_months = set((d.year, d.month) for d in date_objects)
    year_months = sorted(year_months)

    print(f"\n必要な月次データ:")
    for year, month in year_months:
        print(f"  {year}年{month}月")

    print("\n" + "=" * 100)
    print("アメダスデータ取得方法")
    print("=" * 100)

    print("\n1. 気象庁 過去の気象データ検索")
    print("   https://www.data.jma.go.jp/obd/stats/etrn/view/hourly_s1.php")
    print("\n2. 設定:")
    print("   - 地点: 沓形（利尻）")
    print("   - 表示形式: 時別値")
    print("   - 年月日: 上記リストの各日付")
    print("\n3. CSVダウンロードして data_h1631.csv として保存")

    print("\n4. 取得データ:")
    print("   - 気温（時別値）")
    print("   - 降水量（時別値）※霧雨検出用")
    print("   - 風速（時別値）")
    print("   - 湿度（時別値）※4-16時の最低値が重要")
    print("   - 日照時間")

    print("\n" + "=" * 100)
    print("期待される成果")
    print("=" * 100)

    print("\n✅ 21件全ての実測データで閾値を再計算")
    print("   → API予報値のバイアスを排除")
    print("\n✅ 成功9件 vs 失敗10件 vs 部分2件の明確な分離")
    print("   → 精密な閾値設定が可能")
    print("\n✅ 時別値から「午後の最低湿度」を特定")
    print("   → 日平均湿度99%でも成功する理由を解明")
    print("\n✅ 霧雨・通り雨の検出")
    print("   → 降水0mmでも失敗する原因を解明")

    print("\n" + "=" * 100)

if __name__ == '__main__':
    main()
