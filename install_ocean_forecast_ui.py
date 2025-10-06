#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
統合海洋予報UIの自動インストールスクリプト

kelp_drying_map.html に統合海洋予報セクションを自動追加します
"""

import re

def install_ocean_forecast_ui():
    """kelp_drying_map.html に統合海洋予報UIを追加"""

    print("="*70)
    print("OCEAN FORECAST UI INSTALLATION")
    print("="*70)

    # HTMLファイルを読み込み
    try:
        with open('kelp_drying_map.html', 'r', encoding='utf-8') as f:
            html_content = f.read()
        print("\n[OK] kelp_drying_map.html loaded")
    except FileNotFoundError:
        print("\n[ERROR] kelp_drying_map.html not found")
        return False

    # 既にインストール済みかチェック
    if 'oceanForecastContainer' in html_content:
        print("[INFO] Ocean forecast UI already installed")
        return True

    # HTMLセクションを追加（エリア絞り込みセクションの前）
    html_section = '''
    <!-- 統合海洋予報セクション -->
    <div class="ocean-forecast-section" style="margin: 20px 0; padding: 15px; background: white; border-radius: 10px; box-shadow: 0 2px 8px rgba(0,0,0,0.1);">
        <h3 style="color: #1e40af; border-bottom: 2px solid #3b82f6; padding-bottom: 10px;">
            🌊 統合海洋予報 - 連続作業可能時間
        </h3>
        <p style="color: #666; font-size: 14px; margin: 10px 0;">
            海水温・海霧・降水リスクを統合した実用的な作業時間予報
        </p>
        <div id="oceanForecastContainer">
            <p style="text-align: center; color: #999;">読み込み中...</p>
        </div>
    </div>

'''

    # エリア絞り込みセクションを検索
    filter_controls_pattern = r'(<div class="filter-controls">)'
    match = re.search(filter_controls_pattern, html_content)

    if not match:
        print("[ERROR] Could not find insertion point in HTML")
        return False

    # HTMLセクションを挿入
    html_content = html_content[:match.start()] + html_section + html_content[match.start():]
    print("[OK] HTML section inserted")

    # JavaScriptを追加（</body>の前）
    js_script = '''
    <!-- 統合海洋予報JavaScript -->
    <script src="/ocean_forecast_integration.js"></script>
'''

    body_end_pattern = r'(</body>)'
    match = re.search(body_end_pattern, html_content)

    if not match:
        print("[WARNING] Could not find </body> tag, adding script at end")
        html_content += js_script
    else:
        html_content = html_content[:match.start()] + js_script + html_content[match.start():]

    print("[OK] JavaScript reference added")

    # バックアップを作成
    try:
        with open('kelp_drying_map.html.bak', 'w', encoding='utf-8') as f:
            f.write(html_content)
        print("[OK] Backup created: kelp_drying_map.html.bak")
    except Exception as e:
        print(f"[WARNING] Could not create backup: {e}")

    # 更新されたHTMLを保存
    try:
        with open('kelp_drying_map.html', 'w', encoding='utf-8') as f:
            f.write(html_content)
        print("[OK] kelp_drying_map.html updated")
    except Exception as e:
        print(f"[ERROR] Could not save updated HTML: {e}")
        return False

    print("\n" + "="*70)
    print("INSTALLATION COMPLETE")
    print("="*70)
    print("\nNext steps:")
    print("1. Restart Flask server: python konbu_flask_final.py")
    print("2. Open browser: http://localhost:5000/kelp_drying_map.html")
    print("3. Check ocean forecast section below the header")

    return True

if __name__ == '__main__':
    success = install_ocean_forecast_ui()
    exit(0 if success else 1)
