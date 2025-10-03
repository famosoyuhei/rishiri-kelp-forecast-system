#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
H_1631_1434の記録日のうち、6/23-29以外の日付を抽出
追加取得が必要な日付のリスト
"""
import csv
import sys
import io
from datetime import datetime, timedelta

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def main():
    # Load records for H_1631_1434
    records = []
    with open('hoshiba_records.csv', 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row['name'] == 'H_1631_1434':
                records.append(row)

    # Already have data for 6/23-29
    already_have = set()
    start_date = datetime(2025, 6, 23)
    for i in range(7):  # 6/23 to 6/29 (7 days)
        date = start_date + timedelta(days=i)
        already_have.add(date.strftime('%Y-%m-%d'))

    print("=" * 100)
    print("追加取得が必要な日付リスト（H_1631_1434の記録日）")
    print("=" * 100)

    print(f"\n【既に取得済みの期間】")
    print(f"2025年6月23日～6月29日（7日間）")
    for date in sorted(already_have):
        print(f"  {date}")

    # Extract dates we need
    all_dates = set(r['date'] for r in records)
    missing_dates = all_dates - already_have

    print(f"\n" + "=" * 100)
    print(f"【追加取得が必要な日付】")
    print(f"=" * 100)
    print(f"\n総数: {len(missing_dates)}日")

    # Sort and categorize by result
    records_dict = {r['date']: r['result'] for r in records}

    missing_list = []
    for date in missing_dates:
        result = records_dict.get(date, '不明')
        missing_list.append((date, result))

    missing_list.sort()

    print(f"\n{'No':>3} | {'日付':12} | {'結果':35}")
    print("-" * 100)

    for i, (date, result) in enumerate(missing_list, 1):
        print(f"{i:>3} | {date:12} | {result:35}")

    # Group by month
    print(f"\n" + "=" * 100)
    print(f"【月別の内訳】")
    print(f"=" * 100)

    by_month = {}
    for date, result in missing_list:
        month = date[:7]  # YYYY-MM
        if month not in by_month:
            by_month[month] = []
        by_month[month].append((date, result))

    for month in sorted(by_month.keys()):
        dates = by_month[month]
        print(f"\n■ {month} ({len(dates)}日)")
        for date, result in dates:
            print(f"  {date}: {result}")

    # Group by result type
    print(f"\n" + "=" * 100)
    print(f"【結果別の内訳】")
    print(f"=" * 100)

    by_result = {}
    for date, result in missing_list:
        if result not in by_result:
            by_result[result] = []
        by_result[result].append(date)

    for result in sorted(by_result.keys()):
        dates = by_result[result]
        print(f"\n■ {result} ({len(dates)}日)")
        for date in dates:
            print(f"  {date}")

    # Summary
    print(f"\n" + "=" * 100)
    print(f"【データ取得の優先順位】")
    print(f"=" * 100)

    print(f"\n【高優先度】完全乾燥の日（成功事例の気象条件を特定）")
    if '完全乾燥' in by_result:
        for date in by_result['完全乾燥']:
            print(f"  {date}")

    print(f"\n【高優先度】中止の日（失敗事例の気象条件を特定）")
    if '中止' in by_result:
        for date in by_result['中止']:
            print(f"  {date}")

    print(f"\n【最高優先度】部分乾燥の日（境界条件を特定）")
    if '干したが完全には乾かせなかった（泣）' in by_result:
        for date in by_result['干したが完全には乾かせなかった（泣）']:
            print(f"  {date}")

    # Check if any dates in already_have period exist
    print(f"\n" + "=" * 100)
    print(f"【既存データとの重複確認】")
    print(f"=" * 100)

    overlap = all_dates & already_have
    if overlap:
        print(f"\n6/23-29期間に{len(overlap)}件の記録あり:")
        for date in sorted(overlap):
            result = records_dict[date]
            print(f"  {date}: {result}")
    else:
        print(f"\n6/23-29期間には記録なし")

    print(f"\n" + "=" * 100)
    print(f"【データ取得方法】")
    print(f"=" * 100)

    print(f"\n1. 気象庁サイト:")
    print(f"   https://www.data.jma.go.jp/obd/stats/etrn/view/hourly_s1.php")
    print(f"\n2. 設定:")
    print(f"   - 地点: 沓形")
    print(f"   - 年月日: 上記{len(missing_dates)}日分を個別に取得")
    print(f"   - または月単位で取得（2025年6月、7月、8月）")
    print(f"\n3. 推奨:")
    print(f"   月単位でまとめて取得し、該当日のみ抽出する方が効率的")

    print(f"\n" + "=" * 100)

if __name__ == '__main__':
    main()
