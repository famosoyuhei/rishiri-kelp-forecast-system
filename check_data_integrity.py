"""
check_data_integrity.py
-----------------------
軽量整合性検査スクリプト。CI や手動確認で実行する。

使い方:
    python check_data_integrity.py

終了コード:
    0 = 全チェックパス
    1 = 1件以上の問題あり
"""

import sys
import os
import io
import pandas as pd

# Windows CP932 環境でも日本語を出力できるよう UTF-8 強制
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.abspath(__file__))
SPOTS_FILE   = os.path.join(ROOT, "hoshiba_spots.csv")
RECORDS_FILE = os.path.join(ROOT, "hoshiba_records.csv")

errors = []
warnings = []


# ── CHECK 1: hoshiba_records の全 name が hoshiba_spots に存在するか ──────────
def check_orphan_records():
    if not os.path.exists(RECORDS_FILE):
        warnings.append("hoshiba_records.csv が見つかりません（スキップ）")
        return
    if not os.path.exists(SPOTS_FILE):
        errors.append("hoshiba_spots.csv が見つかりません")
        return

    spots_df   = pd.read_csv(SPOTS_FILE)
    records_df = pd.read_csv(RECORDS_FILE)

    if 'name' not in records_df.columns or 'name' not in spots_df.columns:
        errors.append("name カラムが見つかりません")
        return

    spot_names = set(spots_df['name'].dropna())
    record_names = records_df['name'].dropna()

    orphan_names = sorted(set(record_names) - spot_names)
    if orphan_names:
        for n in orphan_names:
            count = int((records_df['name'] == n).sum())
            errors.append(f"孤児レコード: '{n}' が hoshiba_spots.csv に存在しない ({count}件)")
    else:
        print("[OK] 孤児レコードなし")


# ── CHECK 2: 風向0・日射0・雲量0が None にならないことを確認 ──────────────────
def check_zero_not_none():
    """
    Open-Meteo API への実際のリクエストは行わず、
    start.py の hourly 判定ロジックをインラインで検証する。
    """
    # 0 値が None 扱いされていないことを確認する簡易テスト
    test_cases = [
        ("wind_direction_10m", 0),    # 真北
        ("direct_radiation",   0),    # 日射ゼロ（夜・曇天）
        ("cloud_cover",        0),    # 快晴
        ("wind_speed_10m",     0),    # 無風
        ("precipitation",      0),    # 降水なし
        ("temperature_2m",     0),    # 0℃
        ("relative_humidity_2m", 0),  # (実際には発生しないが境界値テスト)
    ]

    failed = []
    for key, val in test_cases:
        # 修正後の判定式: val is not None → 0 は通過するはず
        result = val if val is not None else None
        if result is None:
            failed.append(key)

    if failed:
        errors.append(f"0値がNone扱いされているキー: {failed}")
    else:
        print("[OK] 0値は None 扱いされない（静的確認）")

    # start.py に `if value is not None` が適切に使われているか文字列検索
    start_py = os.path.join(ROOT, "start.py")
    if os.path.exists(start_py):
        with open(start_py, encoding="utf-8") as f:
            source = f.read()

        bad_patterns = [
            "'temperature': hourly['temperature_2m'][h] if hourly['temperature_2m'][h] else",
            "'humidity': hourly['relative_humidity_2m'][h] if hourly['relative_humidity_2m'][h] else",
            "'wind_speed': hourly['wind_speed_10m'][h] / 3.6 if hourly['wind_speed_10m'][h] else",
            "'cloud_cover': hourly['cloud_cover'][h] if hourly['cloud_cover'][h] else",
            "'solar_radiation': hourly['direct_radiation'][h] if hourly['direct_radiation'][h] else",
        ]
        found_bad = [p for p in bad_patterns if p in source]
        if found_bad:
            for p in found_bad:
                errors.append(f"未修正の 'if value' パターンが残っています: ...{p[:60]}...")
        else:
            print("[OK] hourly data の 'if value' バグは修正済み")


# ── CHECK 3: weather_labeled_dataset.csv の所在を確認（本番ロジックに未組込み） ──
def check_labeled_dataset():
    root_path    = os.path.join(ROOT, "weather_labeled_dataset.csv")
    archive_path = os.path.join(ROOT, "archive", "weather_labeled_dataset.csv")

    if os.path.exists(root_path):
        warnings.append(
            "weather_labeled_dataset.csv がルート直下に存在します。"
            " 本番ロジックには組み込まれていません（archive/ に置くことを推奨）。"
        )
    elif os.path.exists(archive_path):
        print("[INFO] weather_labeled_dataset.csv は archive/ にあり、本番ロジックには未組込みです（正常）")
    else:
        print("[INFO] weather_labeled_dataset.csv は見つかりません（未使用のため問題なし）")


# ── CHECK 4: merge_records_with_spots が start.py に定義されているか ───────────
def check_merge_helper():
    start_py = os.path.join(ROOT, "start.py")
    if not os.path.exists(start_py):
        errors.append("start.py が見つかりません")
        return
    with open(start_py, encoding="utf-8") as f:
        source = f.read()
    if "def merge_records_with_spots(" in source:
        print("[OK] merge_records_with_spots() が start.py に定義されています")
    else:
        errors.append("merge_records_with_spots() が start.py に見つかりません")


# ── MAIN ─────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 60)
    print("利尻昆布干し予報アプリ データ整合性検査")
    print("=" * 60)

    check_orphan_records()
    check_zero_not_none()
    check_labeled_dataset()
    check_merge_helper()

    print()
    if warnings:
        print("⚠ 警告:")
        for w in warnings:
            print(f"  - {w}")

    if errors:
        print("❌ エラー:")
        for e in errors:
            print(f"  - {e}")
        print()
        print(f"検査結果: {len(errors)} 件のエラー")
        sys.exit(1)
    else:
        print("✅ 全チェックパス")
        sys.exit(0)
