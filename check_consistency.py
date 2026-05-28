#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Consistency checker for Rishiri Kelp Forecast System.
Based on CLAUDE.md "3 Consistency Prevention Rules".

Usage:
    python check_consistency.py

Exit code:
    0 ... All checks passed
    1 ... One or more ERRORs detected
"""
import io, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import re
import sys
from pathlib import Path

ROOT = Path(__file__).parent
ERRORS   = []
WARNINGS = []
PASSES   = []

def ok(msg):    PASSES.append(f"  OK  {msg}")
def warn(msg):  WARNINGS.append(f"  WARN {msg}")
def error(msg): ERRORS.append(f"  ERROR {msg}")


# ============================================================
# ルール1: スコア色閾値の整合性
# ============================================================
def check_score_color_thresholds():
    """Python _score_color() の閾値が JS の scoreColor() と一致するか確認する"""
    # Python側: start.py の _score_color()
    start_py = (ROOT / "start.py").read_text(encoding="utf-8")
    m = re.search(
        r'def _score_color\(score.*?\).*?if score >= (\d+).*?if score >= (\d+)',
        start_py, re.DOTALL
    )
    if not m:
        error("start.py: _score_color() の閾値を解析できませんでした")
        return
    py_upper, py_lower = int(m.group(1)), int(m.group(2))

    # JS側: kelp_drying_map.html の scoreColor (複数箇所)
    html = (ROOT / "kelp_drying_map.html").read_text(encoding="utf-8")
    js_matches = re.findall(
        r'scoreColor\s*=\s*(?:score|s)\s*=>\s*(?:score|s)\s*>=\s*(\d+).*?(?:score|s)\s*>=\s*(\d+)',
        html
    )
    if not js_matches:
        error("kelp_drying_map.html: scoreColor 関数の閾値を解析できませんでした")
        return

    for js_upper, js_lower in js_matches:
        js_upper, js_lower = int(js_upper), int(js_lower)
        if js_upper != py_upper or js_lower != py_lower:
            error(
                f"scoreColor 閾値の乖離: Python={py_upper}/{py_lower}点 ≠ JS={js_upper}/{js_lower}点\n"
                f"    → start.py _score_color() に合わせて kelp_drying_map.html を修正してください"
            )
        else:
            ok(f"scoreColor 閾値一致: Python/JS ともに {py_upper}/{py_lower}点")


# ============================================================
# ルール1: アイコンパスの整合性
# ============================================================
def check_icon_paths():
    """service-worker.js と kelp_drying_map.html のアイコンパスが一致するか確認する"""
    sw = (ROOT / "service-worker.js").read_text(encoding="utf-8")
    html = (ROOT / "kelp_drying_map.html").read_text(encoding="utf-8")

    sw_icons  = re.findall(r"(?:icon|badge):\s*'(/static/[^']+\.png)'", sw)
    html_icons = re.findall(r"(?:icon|badge):\s*'(/static/[^']+\.png)'", html)

    sw_set   = set(sw_icons)
    html_set = set(html_icons)

    only_in_sw   = sw_set - html_set
    only_in_html = html_set - sw_set

    if only_in_sw:
        warn(f"service-worker.js にあって kelp_drying_map.html にないアイコンパス: {only_in_sw}")
    if only_in_html:
        error(
            f"kelp_drying_map.html にあって service-worker.js にないアイコンパス: {only_in_html}\n"
            f"    → パスを揃えるか、service-worker.js に追記してください"
        )

    # 実ファイル存在チェック
    all_paths = sw_set | html_set
    for p in sorted(all_paths):
        full = ROOT / p.lstrip("/")
        if not full.exists():
            error(f"アイコンファイルが存在しない: {p}  (期待パス: {full})")
        else:
            ok(f"アイコンファイル存在: {p}")

    if not only_in_sw and not only_in_html:
        ok("アイコンパス: service-worker.js と kelp_drying_map.html で一致")


# ============================================================
# ルール1: valid_types の整合性
# ============================================================
def check_valid_types():
    """start.py の valid_types と kelp_drying_map.html の ALL_TYPES / _fieldLayers が一致するか確認する"""
    start_py = (ROOT / "start.py").read_text(encoding="utf-8")
    html     = (ROOT / "kelp_drying_map.html").read_text(encoding="utf-8")

    # Python: valid_types タプル
    m = re.search(r"valid_types\s*=\s*\(([^)]+)\)", start_py)
    if not m:
        error("start.py: valid_types タプルを解析できませんでした")
        return
    py_types = set(re.findall(r"'(\w+)'", m.group(1)))

    # JS: ALL_TYPES 配列
    m2 = re.search(r"ALL_TYPES\s*=\s*\[([^\]]+)\]", html)
    if not m2:
        error("kelp_drying_map.html: ALL_TYPES 配列を解析できませんでした")
        return
    js_types = set(re.findall(r"'(\w+)'", m2.group(1)))

    only_py = py_types - js_types
    only_js = js_types - py_types

    if only_py:
        error(
            f"valid_types 乖離: start.py にあって ALL_TYPES にない型: {only_py}\n"
            f"    → kelp_drying_map.html の ALL_TYPES に追加し、loadField{list(only_py)[0].capitalize()}() を実装してください"
        )
    if only_js:
        error(
            f"valid_types 乖離: ALL_TYPES にあって start.py にない型: {only_js}\n"
            f"    → start.py の valid_types と get_analysis_field() に追加してください"
        )
    if not only_py and not only_js:
        ok(f"valid_types 一致: {sorted(py_types)}")

    # JS: _fieldLayers オブジェクトのキー
    m3 = re.search(r"_fieldLayers\s*=\s*\{([^}]+)\}", html)
    if m3:
        fl_keys = set(re.findall(r"(\w+)\s*:", m3.group(1)))
        only_layers = py_types - fl_keys
        if only_layers:
            error(f"_fieldLayers にキーが不足: {only_layers}")
        else:
            ok(f"_fieldLayers キー一致: {sorted(fl_keys)}")


# ============================================================
# ルール2: SW キャッシュバージョンの一貫性
# ============================================================
def check_sw_cache_version():
    """service-worker.js の3つの CACHE_NAME がすべて同じバージョン文字列か確認する"""
    sw_text = (ROOT / "service-worker.js").read_text(encoding="utf-8")
    names = re.findall(r"const \w+CACHE\w*\s*=\s*'([^']+)'", sw_text)
    if not names:
        warn("service-worker.js: CACHE_NAME 定数が見つかりませんでした")
        return

    # バージョン番号を抽出（例: v2-6-1 → "v2-6-1"）
    versions = [re.search(r'v[\d-]+', n) for n in names]
    version_strs = [v.group() if v else None for v in versions]

    unique = set(v for v in version_strs if v)
    if len(unique) > 1:
        error(f"service-worker.js: CACHE_NAME のバージョンが不一致: {list(zip(names, version_strs))}")
    elif unique:
        ok(f"SW キャッシュバージョン統一: {unique.pop()} ({len(names)}定数)")
    else:
        warn("service-worker.js: バージョン番号を解析できませんでした")


# ============================================================
# ルール1: 必須静的ファイルの存在チェック
# ============================================================
def check_required_static_files():
    """manifest.json / PWAで必要なファイルが実在するか確認する"""
    required = [
        "static/icons/icon.svg",
        "static/icons/icon-192x192.png",
        "static/icons/badge-72x72.png",
        "static/img/logo.png",
        "service-worker.js",
        "manifest.json",
    ]
    for rel in required:
        p = ROOT / rel
        if not p.exists():
            error(f"必須ファイルが存在しない: {rel}")
        else:
            ok(f"必須ファイル存在: {rel}")


# ============================================================
# ルール3: チャットボット contour パターンに島内分布関連キーワードがあるか
# ============================================================
def check_chatbot_patterns():
    """
    チャットボット PATTERNS の contour に「島内分布」「降水量分布」などの
    最低限のキーワードが含まれているか確認する。
    （各レイヤー名は respondContour() の説明文に含まれていればOK）
    """
    html = (ROOT / "kelp_drying_map.html").read_text(encoding="utf-8")

    # contour パターンのキーワード配列を抽出
    m = re.search(r"\{\s*id:\s*'contour'.*?kw:\s*\[([^\]]+)\]", html)
    if not m:
        warn("chatbot PATTERNS に contour パターンが見つかりません")
        return
    kw_str = m.group(1)

    # 最低限必要なキーワードのチェック（全レイヤー名は不要）
    required_kw = ["島内分布", "分布図", "降水量"]
    for kw in required_kw:
        if kw not in kw_str:
            warn(f"contour PATTERNS に推奨キーワード '{kw}' がありません")
        else:
            ok(f"contour パターンにキーワード存在: '{kw}'")

    # respondContour() が全レイヤー名を説明文に含んでいるか確認
    m2 = re.search(r"function respondContour\(.*?\{(.*?)\}", html, re.DOTALL)
    if m2:
        func_body = m2.group(1)
        for layer_label in ["乾燥スコア", "風速", "湿度", "気温", "降水量"]:
            if layer_label not in func_body:
                warn(f"respondContour() の説明文に '{layer_label}' が含まれていません")
            else:
                ok(f"respondContour() に説明あり: '{layer_label}'")


# ============================================================
# メイン
# ============================================================
if __name__ == "__main__":
    print("=" * 60)
    print("  利尻昆布干場予報システム 整合性チェック")
    print("  (CLAUDE.md 整合性の3大予防ルール)")
    print("=" * 60)
    print()

    check_score_color_thresholds()
    check_icon_paths()
    check_valid_types()
    check_sw_cache_version()
    check_required_static_files()
    check_chatbot_patterns()

    print()
    print(f"[PASS]  {len(PASSES)} 件")
    for m in PASSES:
        print(m)

    print()
    if WARNINGS:
        print(f"[WARN]  {len(WARNINGS)} 件")
        for m in WARNINGS:
            print(m)

    print()
    if ERRORS:
        print(f"[ERROR] {len(ERRORS)} 件  ← 要修正")
        for m in ERRORS:
            print(m)
        print()
        print("結果: NG（ERRORあり）— デプロイ前に修正してください")
        sys.exit(1)
    else:
        print("結果: OK — 整合性チェック全通過")
        sys.exit(0)
