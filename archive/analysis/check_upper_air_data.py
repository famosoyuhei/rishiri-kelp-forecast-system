#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ラジオゾンデ・レーウィンデータの取得可能性調査
"""
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def main():
    print("=" * 100)
    print("高層気象観測データの取得方法")
    print("=" * 100)

    print("\n【1. 気象庁ラジオゾンデ観測】")
    print("-" * 100)
    print("日本のラジオゾンデ観測点:")
    print("  - 稚内: 47412 (北海道最北)")
    print("  - 札幌: 47412 (北海道)")
    print("  - 釧路: 47418 (北海道)")
    print("  - 秋田: 47582")
    print("  - 輪島: 47600")
    print("  - 潮岬: 47778")
    print("  - 福岡: 47807")
    print("  - 鹿児島: 47827")
    print("  - 南大東島: 47945")
    print("  - 石垣島: 47918")
    print("  - 南鳥島: 47991")
    print("  - 昭和基地: 89532 (南極)")

    print("\n利尻島に最も近い観測点:")
    print("  → 稚内 (約50km北)")
    print("  → 札幌 (約250km南)")

    print("\n観測要素:")
    print("  - 気圧高度（標準気圧面: 1000, 925, 850, 700, 500, 300, 250, 200, 150, 100hPa等）")
    print("  - 気温")
    print("  - 湿度（相対湿度、露点温度）")
    print("  - 風向・風速")
    print("  - 位置エネルギー高度")

    print("\n観測時刻:")
    print("  - 09:00 JST (00 UTC)")
    print("  - 21:00 JST (12 UTC)")
    print("  ※1日2回")

    print("\n" + "=" * 100)
    print("【2. データ取得方法】")
    print("=" * 100)

    print("\n■ 方法1: 気象庁過去の気象データ")
    print("  URL: https://www.data.jma.go.jp/obd/stats/etrn/upper/index.php")
    print("  - Web UI: ブラウザから手動ダウンロード")
    print("  - CSV形式で取得可能")
    print("  - 過去数十年分のデータあり")
    print("  - APIなし（スクレイピング必要）")

    print("\n■ 方法2: University of Wyoming Upper Air Archive")
    print("  URL: http://weather.uwyo.edu/upperair/sounding.html")
    print("  - 全世界のラジオゾンデデータ")
    print("  - テキスト形式")
    print("  - 1973年以降のデータ")
    print("  - 簡易的なAPIあり（URLパラメータ指定）")

    print("\n■ 方法3: NOAA Integrated Global Radiosonde Archive (IGRA)")
    print("  URL: https://www.ncei.noaa.gov/products/weather-balloon/integrated-global-radiosonde-archive")
    print("  - 全世界の高層気象データ")
    print("  - 1905年以降")
    print("  - データ形式: テキスト (固定長)")

    print("\n■ 方法4: Open-Meteo (圧力レベルデータ)")
    print("  URL: https://open-meteo.com")
    print("  - 圧力レベル予報データ")
    print("  - 850hPa, 700hPa, 500hPa等")
    print("  - 無料API")
    print("  - ただし過去データは予報値（実測ではない）")

    print("\n" + "=" * 100)
    print("【3. 利尻島昆布乾燥への応用】")
    print("=" * 100)

    print("\n有用な高層データ:")
    print("  1. 850hPa高度（約1500m）:")
    print("     - 気温: 地上気温との差から逆転層の有無")
    print("     - 湿度: 中層の水蒸気量")
    print("     - 風向風速: 地上風との比較")

    print("\n  2. 700hPa高度（約3000m）:")
    print("     - 中層の気流パターン")
    print("     - 前線の接近")

    print("\n  3. 500hPa高度（約5500m）:")
    print("     - 上層トラフ・リッジ")
    print("     - 気圧配置の変化予測")

    print("\n応用例:")
    print("  - 地上湿度が高くても、850hPa湿度が低ければ日中の晴天で乾燥可能")
    print("  - 逆転層（地上＜850hPa気温）があれば霧・層雲発生で乾燥困難")
    print("  - 中層風向と地上風向の違いから局地循環（海陸風等）の判別")

    print("\n" + "=" * 100)
    print("【4. 推奨取得方法】")
    print("=" * 100)

    print("\n稚内のラジオゾンデデータを取得する場合:")
    print("  1. University of Wyoming (最も簡単)")
    print("     URL形式:")
    print("     http://weather.uwyo.edu/cgi-bin/sounding?")
    print("     region=np&TYPE=TEXT:LIST&YEAR=2025&MONTH=07&FROM=2912&TO=2912&STNM=47412")
    print("     ")
    print("     パラメータ:")
    print("     - region: np (北太平洋)")
    print("     - YEAR: 2025")
    print("     - MONTH: 07")
    print("     - FROM: 2912 (29日12UTC)")
    print("     - TO: 2912")
    print("     - STNM: 47412 (稚内)")

    print("\n  2. 気象庁（日本語、公式）")
    print("     - ブラウザアクセス必要")
    print("     - CSV直接ダウンロード")

    print("\n実装の優先順位:")
    print("  1. まず Wyoming のデータで試験的に分析")
    print("  2. 効果が確認できたら気象庁データで詳細分析")
    print("  3. Open-Meteo圧力レベルデータで予報に組み込み")

    print("\n" + "=" * 100)
    print("\n次のステップ:")
    print("  1. Wyoming APIで稚内の過去データ取得スクリプト作成")
    print("  2. 850hPa湿度・風向と地上の関係を分析")
    print("  3. 昆布乾燥成功/失敗との相関を評価")

    print("\n" + "=" * 100)

if __name__ == '__main__':
    main()
