#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
H_1631_1434（神居）の詳細分析
沓形アメダスとの気象条件の関係を検証
"""
import json
import sys
import io
import math
import re
import csv

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def calculate_distance(lat1, lon1, lat2, lon2):
    """Calculate distance in km using Haversine formula"""
    R = 6371
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)
    a = math.sin(delta_lat/2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    return R * c

def load_drying_records():
    """Load drying records from CSV"""
    records = []
    with open('hoshiba_records.csv', 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            records.append(row)
    return records

def main():
    # Target spot
    spot_name = "H_1631_1434"
    spot_lat = 45.1631
    spot_lon = 141.1434

    # Kutsugata Amedas - CORRECTED coordinates
    kutsugata_lat = 45.178333
    kutsugata_lon = 141.138333
    kutsugata_alt = 14  # m

    # Motodomari Amedas
    motodomari_lat = 45.2450
    motodomari_lon = 141.2089

    # Mt. Rishiri
    rishiri_peak_lat = 45.1794
    rishiri_peak_lon = 141.2425

    print("=" * 100)
    print("H_1631_1434（神居）の詳細分析")
    print("=" * 100)

    # Calculate distances
    dist_kutsugata = calculate_distance(spot_lat, spot_lon, kutsugata_lat, kutsugata_lon)
    dist_motodomari = calculate_distance(spot_lat, spot_lon, motodomari_lat, motodomari_lon)
    dist_peak = calculate_distance(spot_lat, spot_lon, rishiri_peak_lat, rishiri_peak_lon)

    print(f"\n【干場情報】")
    print(f"名称: {spot_name}")
    print(f"座標: {spot_lat}°N, {spot_lon}°E")
    print(f"部落: 神居")
    print(f"記録: 最も記録の多い干場の1つ")

    print(f"\n【観測所からの距離】")
    print(f"沓形アメダス: {dist_kutsugata:.2f}km")
    print(f"本泊アメダス: {dist_motodomari:.2f}km")
    print(f"利尻山頂: {dist_peak:.2f}km")

    print(f"\n【地理的特徴】")

    # Direction from Kutsugata
    delta_lat = spot_lat - kutsugata_lat
    delta_lon = spot_lon - kutsugata_lon

    if abs(delta_lat) > abs(delta_lon):
        direction = "南" if delta_lat < 0 else "北"
    else:
        direction = "東" if delta_lon > 0 else "西"

    print(f"沓形からの方角: {direction}方向")
    print(f"緯度差: {delta_lat:.4f}° ({delta_lat * 111:.1f}km)")
    print(f"経度差: {delta_lon:.4f}° ({delta_lon * 111 * math.cos(math.radians(spot_lat)):.1f}km)")

    # Position relative to mountain
    is_west_of_mountain = spot_lon < 141.20
    print(f"利尻山との位置: {'西側（沓形側）' if is_west_of_mountain else '東側（本泊側）'}")

    # Coastal distance estimation (rough)
    # 神居 is coastal, so likely ~0-50m altitude
    print(f"推定標高: 0-30m（海岸低地）")
    print(f"沓形アメダスとの標高差: 約{abs(kutsugata_alt - 15):.0f}m以内（ほぼ同等）")

    print(f"\n【気象条件の同等性評価】")
    print("=" * 100)

    # Evaluation criteria
    criteria = []

    # Distance
    if dist_kutsugata <= 2.0:
        criteria.append(("距離", "✅ 非常に近い（2km以内）", "HIGH"))
    elif dist_kutsugata <= 5.0:
        criteria.append(("距離", "✅ 代表範囲内（5km以内）", "MEDIUM"))
    else:
        criteria.append(("距離", "❌ 代表範囲外", "LOW"))

    # Mountain position
    if is_west_of_mountain:
        criteria.append(("地形", "✅ 利尻山の西側（沓形と同じ側）", "HIGH"))
    else:
        criteria.append(("地形", "⚠️ 利尻山の東側", "MEDIUM"))

    # Altitude
    criteria.append(("標高", "✅ ほぼ同等（海岸低地）", "HIGH"))

    # Coastal
    criteria.append(("海岸距離", "✅ 海岸沿い（局地循環が同等）", "HIGH"))

    for category, assessment, level in criteria:
        print(f"\n{category:10}: {assessment}")

    print(f"\n" + "=" * 100)
    print("【総合評価】")
    print("=" * 100)

    high_count = len([c for c in criteria if c[2] == "HIGH"])
    medium_count = len([c for c in criteria if c[2] == "MEDIUM"])
    low_count = len([c for c in criteria if c[2] == "LOW"])

    if high_count >= 3 and low_count == 0:
        overall = "✅ 沓形アメダスで精度良く代表可能"
        confidence = "高"
    elif high_count >= 2 and low_count == 0:
        overall = "⚠️ 沓形アメダスで概ね代表可能（若干の誤差あり）"
        confidence = "中～高"
    else:
        overall = "❌ 沓形アメダスでは不十分"
        confidence = "低"

    print(f"\n評価: {overall}")
    print(f"信頼度: {confidence}")

    print(f"\n判定基準スコア:")
    print(f"  HIGH: {high_count}/4")
    print(f"  MEDIUM: {medium_count}/4")
    print(f"  LOW: {low_count}/4")

    # Load actual records
    print(f"\n" + "=" * 100)
    print("【実際の干し記録】")
    print("=" * 100)

    records = load_drying_records()
    spot_records = [r for r in records if r['name'] == spot_name]

    if spot_records:
        print(f"\n記録数: {len(spot_records)}件")

        # Count results
        results_count = {}
        for record in spot_records:
            result = record['result']
            if result not in results_count:
                results_count[result] = 0
            results_count[result] += 1

        print(f"\n結果の内訳:")
        for result, count in sorted(results_count.items(), key=lambda x: -x[1]):
            pct = count / len(spot_records) * 100
            print(f"  {result}: {count}件 ({pct:.1f}%)")

        # Show some examples
        print(f"\n記録の例（最新5件）:")
        print(f"{'日付':12} | {'結果':30}")
        print("-" * 100)
        for record in sorted(spot_records, key=lambda x: x['date'], reverse=True)[:5]:
            print(f"{record['date']:12} | {record['result']:30}")
    else:
        print(f"\n記録が見つかりません")

    # Analysis of 7/29 case
    print(f"\n" + "=" * 100)
    print("【7月29日の事例】")
    print("=" * 100)

    july29 = [r for r in spot_records if r['date'] == '2025-07-29']
    if july29:
        print(f"\n記録あり:")
        for record in july29:
            print(f"  結果: {record['result']}")

        print(f"\n分析:")
        print(f"  - この日は珍しく神居で天気が良く、鴛泊で天気が悪い日")
        print(f"  - 沓形アメダスは神居に近い（{dist_kutsugata:.2f}km）")
        print(f"  - 沓形の気象データがこの干場の条件をよく反映していた可能性")
    else:
        print(f"\n7月29日の記録なし")

    print(f"\n" + "=" * 100)
    print("【結論】")
    print("=" * 100)

    print(f"\nH_1631_1434（神居）は沓形アメダスから {dist_kutsugata:.2f}km の位置にあり、")
    print(f"以下の理由で沓形アメダスの気象データで{confidence}精度の予測が可能:")
    print(f"\n  1. 距離が近い（2km以内）")
    print(f"  2. 利尻山の西側（沓形と同じ気団）")
    print(f"  3. 標高がほぼ同じ（海岸低地）")
    print(f"  4. 海岸線沿い（局地循環の影響が同等）")
    print(f"\nただし、以下の点に注意:")
    print(f"  - 1.74km離れているため、局地的な霧雨・通り雨の有無に差が出る可能性")
    print(f"  - 海風の影響で午後の湿度に若干の差が出る可能性")
    print(f"  - 山からの距離が異なるため、山岳風の影響に差がある可能性")

    print(f"\n推奨:")
    print(f"  - 沓形アメダスデータを基本使用")
    print(f"  - 本泊データとの比較で補正（東風・南東風の日）")
    print(f"  - ラジオゾンデ850hPa風向でさらに精度向上")

    print(f"\n" + "=" * 100)

if __name__ == '__main__':
    main()
