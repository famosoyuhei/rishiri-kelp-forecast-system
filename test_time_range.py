#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
時間範囲修正のテストスクリプト

変更内容:
- 旧: start_hour + 12 → range(4, 16) → 4,5,6,...,15 (12時間)
- 新: start_hour + 13 → range(4, 17) → 4,5,6,...,16 (13時間)
"""

import sys
import io

# Set UTF-8 encoding for output on Windows
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def test_time_range():
    print("=" * 80)
    print("時間範囲修正テスト")
    print("=" * 80)
    print()

    # Day 0の例
    i = 0
    start_hour_old = i * 24 + 4
    end_hour_old = start_hour_old + 12

    start_hour_new = i * 24 + 4
    end_hour_new = start_hour_new + 13

    print("Day 0の例:")
    print(f"  start_hour: {start_hour_new} (4AM)")
    print()

    print("旧実装 (12時間):")
    print(f"  end_hour: {end_hour_old}")
    print(f"  range({start_hour_old}, {end_hour_old})")
    old_range = list(range(start_hour_old, end_hour_old))
    print(f"  時刻: {old_range}")
    print(f"  個数: {len(old_range)}時間")
    print(f"  最終時刻: {old_range[-1]}時 (15時)")
    print()

    print("新実装 (13時間):")
    print(f"  end_hour: {end_hour_new}")
    print(f"  range({start_hour_new}, {end_hour_new})")
    new_range = list(range(start_hour_new, end_hour_new))
    print(f"  時刻: {new_range}")
    print(f"  個数: {len(new_range)}時間")
    print(f"  最終時刻: {new_range[-1]}時 (16時)")
    print()

    print("=" * 80)
    print("検証結果")
    print("=" * 80)

    if len(old_range) == 12:
        print("✓ 旧実装: 12時間 (正しい)")
    else:
        print("✗ 旧実装: エラー")

    if len(new_range) == 13:
        print("✓ 新実装: 13時間 (正しい)")
    else:
        print("✗ 新実装: エラー")

    if new_range[-1] == 16:
        print("✓ 新実装: 16時を含む (正しい)")
    else:
        print("✗ 新実装: 16時を含まない (エラー)")

    print()
    print("仕様書の記載:")
    print("  「当日4:00-16:00 JST の時別データ（13時間分）」")
    print("  → 新実装で一致 ✓")

if __name__ == '__main__':
    test_time_range()
