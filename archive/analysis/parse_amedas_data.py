#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Parse JMA Amedas data.csv and analyze against drying records
"""
import csv
import sys
import io
from datetime import datetime

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def parse_amedas_csv():
    """Parse JMA Amedas CSV with proper encoding detection"""
    encodings = ['cp932', 'shift_jis', 'utf-8', 'latin1']

    for encoding in encodings:
        try:
            with open('data.csv', 'r', encoding=encoding) as f:
                # Read first few lines to check structure
                lines = [f.readline() for _ in range(5)]
                print(f"=== Trying encoding: {encoding} ===")
                for i, line in enumerate(lines):
                    print(f"Line {i}: {line.strip()[:100]}")

                # Reset and parse full file
                f.seek(0)
                content = f.read()
                print(f"\n✅ Successfully read with {encoding}")
                print(f"File size: {len(content)} characters")
                return encoding, content
        except Exception as e:
            print(f"❌ {encoding} failed: {e}")
            continue

    return None, None

def main():
    print("=" * 100)
    print("JMAアメダスデータ解析")
    print("=" * 100)

    encoding, content = parse_amedas_csv()

    if encoding:
        print(f"\n正常に読み込み完了: {encoding}")

        # Show first 500 chars
        print("\n" + "=" * 100)
        print("ファイル先頭500文字:")
        print("=" * 100)
        print(content[:500])
    else:
        print("\n❌ 全てのエンコーディングで失敗")

if __name__ == '__main__':
    main()
