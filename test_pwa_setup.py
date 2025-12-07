#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PWA設定の検証スクリプト

以下をチェック:
1. manifest.jsonの存在と内容
2. service-worker.jsの存在
3. アイコンファイルの存在
4. 必要なエンドポイントの設定
"""

import json
import os
import sys
import io

# Set UTF-8 encoding for output on Windows
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def test_pwa_setup():
    print("=" * 80)
    print("PWA設定検証テスト")
    print("=" * 80)
    print()

    results = {
        "passed": [],
        "failed": [],
        "warnings": []
    }

    # Test 1: manifest.json
    print("📋 Test 1: manifest.json")
    if os.path.exists('manifest.json'):
        try:
            with open('manifest.json', 'r', encoding='utf-8') as f:
                manifest = json.load(f)

            print(f"  ✅ manifest.json exists")
            print(f"     - Name: {manifest.get('name')}")
            print(f"     - Short name: {manifest.get('short_name')}")
            print(f"     - Theme color: {manifest.get('theme_color')}")
            print(f"     - Display: {manifest.get('display')}")
            print(f"     - Icons: {len(manifest.get('icons', []))} defined")

            results["passed"].append("manifest.json exists and is valid JSON")

            # Check required fields
            required = ['name', 'short_name', 'start_url', 'display', 'icons']
            missing = [f for f in required if f not in manifest]
            if missing:
                results["warnings"].append(f"manifest.json missing fields: {missing}")
                print(f"  ⚠️  Missing fields: {missing}")

        except json.JSONDecodeError as e:
            results["failed"].append(f"manifest.json is invalid JSON: {e}")
            print(f"  ❌ Invalid JSON: {e}")
    else:
        results["failed"].append("manifest.json not found")
        print("  ❌ manifest.json not found")
    print()

    # Test 2: service-worker.js
    print("⚙️  Test 2: service-worker.js")
    if os.path.exists('service-worker.js'):
        size = os.path.getsize('service-worker.js')
        print(f"  ✅ service-worker.js exists ({size} bytes)")
        results["passed"].append("service-worker.js exists")
    else:
        results["failed"].append("service-worker.js not found")
        print("  ❌ service-worker.js not found")
    print()

    # Test 3: Icon files
    print("🎨 Test 3: Icon files")
    icon_dir = 'static/icons'
    if os.path.exists(icon_dir):
        icons = os.listdir(icon_dir)
        print(f"  ✅ static/icons directory exists")
        print(f"     - Files: {', '.join(icons)}")

        if 'icon.svg' in icons:
            print(f"  ✅ SVG icon found")
            results["passed"].append("PWA icon (SVG) exists")
        else:
            results["warnings"].append("icon.svg not found in static/icons")
            print(f"  ⚠️  icon.svg not found")
    else:
        results["failed"].append("static/icons directory not found")
        print("  ❌ static/icons directory not found")
    print()

    # Test 4: HTML manifest link
    print("🔗 Test 4: HTML manifest link")
    if os.path.exists('kelp_drying_map.html'):
        with open('kelp_drying_map.html', 'r', encoding='utf-8') as f:
            html_content = f.read()

        if 'rel="manifest"' in html_content and 'href="/manifest.json"' in html_content:
            print("  ✅ manifest link found in HTML")
            results["passed"].append("HTML contains manifest link")
        else:
            results["failed"].append("HTML missing manifest link")
            print("  ❌ manifest link not found in HTML")

        if 'serviceWorker.register' in html_content:
            print("  ✅ Service Worker registration code found")
            results["passed"].append("HTML contains SW registration")
        else:
            results["failed"].append("HTML missing SW registration")
            print("  ❌ Service Worker registration not found")
    else:
        results["warnings"].append("kelp_drying_map.html not found")
        print("  ⚠️  kelp_drying_map.html not found")
    print()

    # Test 5: start.py endpoints
    print("🚀 Test 5: start.py endpoints")
    if os.path.exists('start.py'):
        with open('start.py', 'r', encoding='utf-8') as f:
            start_content = f.read()

        endpoints = {
            '/manifest.json': "route('/manifest.json')",
            '/service-worker.js': "route('/service-worker.js')",
            '/static/icons': "route('/static/icons"
        }

        for endpoint, pattern in endpoints.items():
            if pattern in start_content:
                print(f"  ✅ {endpoint} endpoint configured")
                results["passed"].append(f"Endpoint {endpoint} exists")
            else:
                results["failed"].append(f"Endpoint {endpoint} missing")
                print(f"  ❌ {endpoint} endpoint not found")
    else:
        results["warnings"].append("start.py not found")
        print("  ⚠️  start.py not found")
    print()

    # Summary
    print("=" * 80)
    print("テスト結果サマリー")
    print("=" * 80)
    print(f"✅ Passed: {len(results['passed'])}")
    for item in results['passed']:
        print(f"   - {item}")
    print()

    if results['warnings']:
        print(f"⚠️  Warnings: {len(results['warnings'])}")
        for item in results['warnings']:
            print(f"   - {item}")
        print()

    if results['failed']:
        print(f"❌ Failed: {len(results['failed'])}")
        for item in results['failed']:
            print(f"   - {item}")
        print()
        print("PWA設定に問題があります。修正が必要です。")
        return False
    else:
        print("🎉 All tests passed! PWA設定は完璧です。")
        return True

if __name__ == '__main__':
    success = test_pwa_setup()
    exit(0 if success else 1)
