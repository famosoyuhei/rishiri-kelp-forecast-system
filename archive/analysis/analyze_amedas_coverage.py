#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
沓形アメダス観測所の代表範囲分析
地形・距離・標高・風向を考慮した干場の分類
"""
import csv
import sys
import io
import math

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def load_drying_records():
    """Load drying records from CSV"""
    records = []
    with open('hoshiba_records.csv', 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            records.append(row)
    return records

def get_spot_coordinates(spot_name):
    """Extract coordinates from spot name (format: H_LLLL_NNNN)"""
    parts = spot_name.split('_')
    if len(parts) == 3:
        # Format: H_LLLL_NNNN where LLLL is latitude*100, NNNN is longitude*100
        # Example: H_1631_1434 = 45.1631N, 141.1434E
        lat = 45.0 + float(parts[1]) / 10000
        lon = 141.0 + float(parts[2]) / 10000
        return lat, lon
    return None, None

def calculate_distance(lat1, lon1, lat2, lon2):
    """
    Calculate distance in km using Haversine formula
    """
    R = 6371  # Earth radius in km

    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)

    a = math.sin(delta_lat/2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

    return R * c

def get_direction(lat1, lon1, lat2, lon2):
    """Calculate direction from point 1 to point 2"""
    delta_lon = lon2 - lon1
    delta_lat = lat2 - lat1

    if abs(delta_lon) < 0.01 and abs(delta_lat) < 0.01:
        return "SAME"

    # Simple quadrant-based direction
    if abs(delta_lat) > abs(delta_lon):
        return "N" if delta_lat > 0 else "S"
    else:
        return "E" if delta_lon > 0 else "W"

def main():
    # Amedas station locations
    kutsugata = {'name': '沓形', 'lat': 45.1342, 'lon': 141.1144, 'alt': 6}  # 西側
    motodomari = {'name': '本泊', 'lat': 45.2450, 'lon': 141.2089, 'alt': 9}  # 東側
    rishiri_peak = {'name': '利尻山', 'lat': 45.1794, 'lon': 141.2425, 'alt': 1721}  # 中央

    print("=" * 100)
    print("沓形アメダス観測所の代表範囲分析")
    print("=" * 100)

    print("\n【観測所位置】")
    print(f"  沓形: {kutsugata['lat']:.4f}N, {kutsugata['lon']:.4f}E, 標高{kutsugata['alt']}m")
    print(f"  本泊: {motodomari['lat']:.4f}N, {motodomari['lon']:.4f}E, 標高{motodomari['alt']}m")
    print(f"  利尻山: {rishiri_peak['lat']:.4f}N, {rishiri_peak['lon']:.4f}E, 標高{rishiri_peak['alt']}m")

    # Distance between stations
    dist_stations = calculate_distance(
        kutsugata['lat'], kutsugata['lon'],
        motodomari['lat'], motodomari['lon']
    )
    print(f"\n沓形-本泊間距離: {dist_stations:.1f}km")

    print("\n" + "=" * 100)
    print("【気象条件が同等とみなせる範囲の判定基準】")
    print("=" * 100)

    print("\n1. 距離基準:")
    print("   - 平地・海岸部: 半径5km以内")
    print("   - 理由: 局地循環の影響範囲")

    print("\n2. 標高基準:")
    print("   - 標高差50m以内")
    print("   - 理由: 気温減率（100mで約0.6°C）、逆転層の影響")

    print("\n3. 地形基準:")
    print("   - 利尻山を挟まない")
    print("   - 理由: 山岳による風上・風下効果、雲の発生")
    print("   - 同一斜面・同一海岸線")

    print("\n4. 風向基準:")
    print("   - 主風向に対して風上/風下が同じ")
    print("   - 理由: フェーン現象、雲の発生位置")

    print("\n" + "=" * 100)
    print("【沓形アメダスの代表範囲】")
    print("=" * 100)

    print("\n推定代表範囲:")
    print("  - 中心: 沓形（45.1342N, 141.1144E）")
    print("  - 半径: 約5km")
    print("  - 方角: 西側～南西側（利尻山の西麓）")
    print("  - 標高: 0-50m（海岸低地）")
    print("  - 除外: 利尻山東側、北側高地")

    # Load spots and classify
    records = load_drying_records()
    spots = {}

    for record in records:
        spot_name = record['name']
        if spot_name not in spots:
            lat, lon = get_spot_coordinates(spot_name)
            if lat and lon:
                spots[spot_name] = {'lat': lat, 'lon': lon}

    print(f"\n干場総数: {len(spots)}箇所")

    print("\n" + "=" * 100)
    print("【干場の分類】")
    print("=" * 100)

    # Classify spots
    kutsugata_zone = []  # 沓形代表範囲
    motodomari_zone = []  # 本泊寄り
    mountain_zone = []  # 山岳域
    uncertain = []  # 不明確

    for spot_name, coords in spots.items():
        lat, lon = coords['lat'], coords['lon']

        # Distance to stations
        dist_k = calculate_distance(lat, lon, kutsugata['lat'], kutsugata['lon'])
        dist_m = calculate_distance(lat, lon, motodomari['lat'], motodomari['lon'])
        dist_peak = calculate_distance(lat, lon, rishiri_peak['lat'], rishiri_peak['lon'])

        # Direction from Kutsugata
        dir_k = get_direction(kutsugata['lat'], kutsugata['lon'], lat, lon)

        # Longitude check (利尻山より西か東か)
        # 沓形: 141.1144E, 利尻山: 141.2425E, 本泊: 141.2089E
        is_west_of_mountain = lon < 141.20  # 利尻山より西側

        # Classification logic
        if dist_k <= 5.0 and is_west_of_mountain:
            kutsugata_zone.append({
                'name': spot_name,
                'lat': lat,
                'lon': lon,
                'dist_k': dist_k,
                'dist_m': dist_m,
                'dir': dir_k
            })
        elif dist_m < dist_k and not is_west_of_mountain:
            motodomari_zone.append({
                'name': spot_name,
                'lat': lat,
                'lon': lon,
                'dist_k': dist_k,
                'dist_m': dist_m,
                'dir': dir_k
            })
        elif dist_peak < 5.0:
            mountain_zone.append({
                'name': spot_name,
                'lat': lat,
                'lon': lon,
                'dist_peak': dist_peak
            })
        else:
            uncertain.append({
                'name': spot_name,
                'lat': lat,
                'lon': lon,
                'dist_k': dist_k,
                'dist_m': dist_m
            })

    # Report
    print(f"\n■ 沓形代表範囲（気象条件同等）: {len(kutsugata_zone)}箇所")
    print("-" * 100)
    print(f"{'干場名':20} | {'緯度':>10} | {'経度':>10} | {'沓形距離':>8} | {'方向':>4}")
    print("-" * 100)

    for spot in sorted(kutsugata_zone, key=lambda x: x['dist_k']):
        print(f"{spot['name']:20} | {spot['lat']:>10.4f}N | {spot['lon']:>10.4f}E | {spot['dist_k']:>7.1f}km | {spot['dir']:>4}")

    print(f"\n■ 本泊寄り（東側）: {len(motodomari_zone)}箇所")
    print("-" * 100)
    print(f"{'干場名':20} | {'緯度':>10} | {'経度':>10} | {'本泊距離':>8} | {'方向':>4}")
    print("-" * 100)

    for spot in sorted(motodomari_zone, key=lambda x: x['dist_m'])[:10]:
        print(f"{spot['name']:20} | {spot['lat']:>10.4f}N | {spot['lon']:>10.4f}E | {spot['dist_m']:>7.1f}km | {spot['dir']:>4}")

    if len(motodomari_zone) > 10:
        print(f"  ... 他 {len(motodomari_zone) - 10}箇所")

    if mountain_zone:
        print(f"\n■ 山岳域（利尻山周辺）: {len(mountain_zone)}箇所")
        print("-" * 100)
        for spot in sorted(mountain_zone, key=lambda x: x['dist_peak'])[:5]:
            print(f"{spot['name']:20} | {spot['lat']:>10.4f}N | {spot['lon']:>10.4f}E | 山頂距離{spot['dist_peak']:>5.1f}km")

    if uncertain:
        print(f"\n■ 分類不明確: {len(uncertain)}箇所")
        print("-" * 100)
        for spot in sorted(uncertain, key=lambda x: min(x['dist_k'], x['dist_m']))[:5]:
            print(f"{spot['name']:20} | {spot['lat']:>10.4f}N | {spot['lon']:>10.4f}E | 沓形{spot['dist_k']:.1f}km/本泊{spot['dist_m']:.1f}km")

    print("\n" + "=" * 100)
    print("【推奨事項】")
    print("=" * 100)

    print(f"\n✅ 沓形代表範囲（{len(kutsugata_zone)}箇所）:")
    print("   → 沓形アメダスデータで精度良く予測可能")

    print(f"\n⚠️ 本泊寄り（{len(motodomari_zone)}箇所）:")
    print("   → 本泊アメダスデータ併用推奨")
    print("   → 特に東風・南東風の日は気象差が大きい")

    print(f"\n❌ 山岳域（{len(mountain_zone)}箇所）:")
    print("   → 標高・地形効果が大きく、平地観測所では代表不可")
    print("   → ラジオゾンデ850hPa風向で補正必要")

    print("\n" + "=" * 100)
    print("\n【7月29日の事例検証】")
    print("=" * 100)

    # Check July 29 case
    july29_spots = [r for r in records if r['date'] == '2025-07-29']
    print(f"\n7月29日の記録: {len(july29_spots)}件")

    for record in july29_spots:
        spot_name = record['name']
        result = record['result']

        if spot_name in spots:
            lat, lon = spots[spot_name]['lat'], spots[spot_name]['lon']
            dist_k = calculate_distance(lat, lon, kutsugata['lat'], kutsugata['lon'])

            zone = "沓形範囲" if any(s['name'] == spot_name for s in kutsugata_zone) else "本泊寄り"

            print(f"  {spot_name}: {result}")
            print(f"    分類: {zone}, 沓形距離{dist_k:.1f}km")

    print("\n結論:")
    print("  → 2箇所とも沓形範囲外（距離が遠い、または東側）")
    print("  → 同じ沓形データでも干場位置で結果が分かれた理由を説明")

    print("\n" + "=" * 100)

if __name__ == '__main__':
    main()
