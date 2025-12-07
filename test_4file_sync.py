#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
4ファイル同期機能のテストスクリプト

このスクリプトは以下をテストします:
1. sync_kml_file() - CSV→KML同期
2. sync_js_array_file() - CSV→JS配列同期
3. sync_all_files_from_csv() - 全ファイル同期
"""

import sys
import io
import pandas as pd

# UTF-8 encoding
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Import sync functions from start.py
sys.path.insert(0, '.')
from start import sync_kml_file, sync_js_array_file, sync_all_files_from_csv

def test_sync_functions():
    """同期関数のテスト"""

    print("=" * 80)
    print("4ファイル同期機能テスト")
    print("=" * 80)
    print()

    # Test 1: Read CSV
    print("Test 1: CSV読み込み")
    print("-" * 80)
    try:
        df = pd.read_csv('hoshiba_spots.csv')
        print(f"✓ CSV読み込み成功: {len(df)}件")
        print(f"  列: {list(df.columns)}")
        print()
    except Exception as e:
        print(f"✗ CSV読み込みエラー: {e}")
        return

    # Test 2: KML sync
    print("Test 2: KML同期")
    print("-" * 80)
    kml_success = sync_kml_file(df)
    if kml_success:
        print("✓ KML同期成功")
        # Count Placemarks
        with open('hoshiba_spots_named.kml', 'r', encoding='utf-8') as f:
            kml_content = f.read()
            placemark_count = kml_content.count('<Placemark>')
        print(f"  Placemark数: {placemark_count}")

        if placemark_count == len(df):
            print(f"  ✓ 整合性OK: CSV {len(df)}件 = KML {placemark_count}件")
        else:
            print(f"  ✗ 整合性エラー: CSV {len(df)}件 ≠ KML {placemark_count}件")
    else:
        print("✗ KML同期失敗")
    print()

    # Test 3: JS array sync
    print("Test 3: JavaScript配列同期")
    print("-" * 80)
    js_success = sync_js_array_file(df)
    if js_success:
        print("✓ JS配列同期成功")
        # Count entries
        with open('all_spots_array.js', 'r', encoding='utf-8') as f:
            js_content = f.read()
            entry_count = js_content.count('{ name:')
        print(f"  エントリ数: {entry_count}")

        if entry_count == len(df):
            print(f"  ✓ 整合性OK: CSV {len(df)}件 = JS {entry_count}件")
        else:
            print(f"  ✗ 整合性エラー: CSV {len(df)}件 ≠ JS {entry_count}件")
    else:
        print("✗ JS配列同期失敗")
    print()

    # Test 4: Full sync
    print("Test 4: 全ファイル同期")
    print("-" * 80)
    sync_result = sync_all_files_from_csv()
    print(f"同期結果: {sync_result}")

    if sync_result.get('csv') and sync_result.get('kml') and sync_result.get('js'):
        print("✓ 全ファイル同期成功")
    else:
        print("✗ 一部のファイル同期失敗")
    print()

    # Summary
    print("=" * 80)
    print("テストサマリー")
    print("=" * 80)
    print(f"CSV: {len(df)}件")

    with open('hoshiba_spots_named.kml', 'r', encoding='utf-8') as f:
        kml_count = f.read().count('<Placemark>')
    print(f"KML: {kml_count}件")

    with open('all_spots_array.js', 'r', encoding='utf-8') as f:
        js_count = f.read().count('{ name:')
    print(f"JS:  {js_count}件")

    with open('hoshiba_records.csv', 'r', encoding='utf-8') as f:
        record_count = len(f.readlines()) - 1  # Exclude header
    print(f"Records: {record_count}件")
    print()

    if len(df) == kml_count == js_count:
        print("✓ 全ファイル整合性OK")
    else:
        print("✗ ファイル間で不整合あり")

if __name__ == '__main__':
    test_sync_functions()
