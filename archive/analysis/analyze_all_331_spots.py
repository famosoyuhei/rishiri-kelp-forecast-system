#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
全331箇所の干場を対象にアメダス代表範囲を分析
沓形・本泊の観測範囲と推奨観測所を決定
"""
import json
import sys
import io
import math

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

def main():
    # Load all_spots_array.js and parse manually
    import re

    with open('all_spots_array.js', 'r', encoding='utf-8') as f:
        content = f.read()

    # Extract spot data using regex
    pattern = r'\{\s*name:\s*"([^"]+)",\s*lat:\s*([\d.]+),\s*lon:\s*([\d.]+),\s*town:\s*"([^"]*)",\s*district:\s*"([^"]*)",\s*buraku:\s*"([^"]*)"\s*\}'
    matches = re.findall(pattern, content)

    spots = []
    for match in matches:
        spots.append({
            'name': match[0],
            'lat': float(match[1]),
            'lon': float(match[2]),
            'town': match[3],
            'district': match[4],
            'buraku': match[5]
        })

    # Amedas stations
    kutsugata = {'name': '沓形', 'lat': 45.1342, 'lon': 141.1144}
    motodomari = {'name': '本泊', 'lat': 45.2450, 'lon': 141.2089}
    rishiri_peak = {'lat': 45.1794, 'lon': 141.2425}

    print("=" * 100)
    print("全331箇所の干場に対するアメダス代表範囲分析")
    print("=" * 100)

    print(f"\n干場総数: {len(spots)}箇所")

    # Classification criteria
    KUTSUGATA_RADIUS = 5.0  # km
    MOUNTAIN_LON_THRESHOLD = 141.20  # 利尻山より西か東か

    kutsugata_zone = []
    motodomari_zone = []
    mixed_zone = []
    far_zone = []

    for spot in spots:
        lat, lon = spot['lat'], spot['lon']
        name = spot['name']
        town = spot.get('town', '')
        district = spot.get('district', '')
        buraku = spot.get('buraku', '')

        # Calculate distances
        dist_k = calculate_distance(lat, lon, kutsugata['lat'], kutsugata['lon'])
        dist_m = calculate_distance(lat, lon, motodomari['lat'], motodomari['lon'])
        dist_peak = calculate_distance(lat, lon, rishiri_peak['lat'], rishiri_peak['lon'])

        # Classify
        is_west = lon < MOUNTAIN_LON_THRESHOLD

        spot_info = {
            'name': name,
            'lat': lat,
            'lon': lon,
            'town': town,
            'district': district,
            'buraku': buraku,
            'dist_k': dist_k,
            'dist_m': dist_m,
            'dist_peak': dist_peak
        }

        if dist_k <= KUTSUGATA_RADIUS and is_west:
            kutsugata_zone.append(spot_info)
        elif dist_m <= KUTSUGATA_RADIUS and not is_west:
            motodomari_zone.append(spot_info)
        elif dist_k <= 10 and dist_m <= 10:
            mixed_zone.append(spot_info)
        else:
            far_zone.append(spot_info)

    print("\n" + "=" * 100)
    print("【分類結果】")
    print("=" * 100)

    print(f"\n✅ 沓形代表範囲（5km以内、利尻山西側）: {len(kutsugata_zone)}箇所")
    print(f"⚠️ 本泊代表範囲（5km以内、利尻山東側）: {len(motodomari_zone)}箇所")
    print(f"📊 中間域（両観測所から10km以内）: {len(mixed_zone)}箇所")
    print(f"❌ 遠隔地（両観測所から10km超）: {len(far_zone)}箇所")

    # Detailed report
    print("\n" + "=" * 100)
    print("【沓形代表範囲】詳細")
    print("=" * 100)

    if kutsugata_zone:
        # Group by buraku
        buraku_groups = {}
        for spot in kutsugata_zone:
            b = spot['buraku']
            if b not in buraku_groups:
                buraku_groups[b] = []
            buraku_groups[b].append(spot)

        for buraku, spots_list in sorted(buraku_groups.items()):
            print(f"\n■ {buraku} ({len(spots_list)}箇所)")
            for spot in sorted(spots_list, key=lambda x: x['dist_k'])[:10]:
                print(f"  {spot['name']:20} | {spot['lat']:.4f}N, {spot['lon']:.4f}E | 沓形{spot['dist_k']:.1f}km")
            if len(spots_list) > 10:
                print(f"  ... 他 {len(spots_list) - 10}箇所")
    else:
        print("\n該当なし")

    print("\n" + "=" * 100)
    print("【本泊代表範囲】詳細")
    print("=" * 100)

    if motodomari_zone:
        buraku_groups = {}
        for spot in motodomari_zone:
            b = spot['buraku']
            if b not in buraku_groups:
                buraku_groups[b] = []
            buraku_groups[b].append(spot)

        for buraku, spots_list in sorted(buraku_groups.items()):
            print(f"\n■ {buraku} ({len(spots_list)}箇所)")
            for spot in sorted(spots_list, key=lambda x: x['dist_m'])[:10]:
                print(f"  {spot['name']:20} | {spot['lat']:.4f}N, {spot['lon']:.4f}E | 本泊{spot['dist_m']:.1f}km")
            if len(spots_list) > 10:
                print(f"  ... 他 {len(spots_list) - 10}箇所")
    else:
        print("\n該当なし")

    print("\n" + "=" * 100)
    print("【中間域】サマリー")
    print("=" * 100)

    if mixed_zone:
        print(f"\n該当: {len(mixed_zone)}箇所")
        print("推奨: 沓形・本泊の両データを使った補間、またはラジオゾンデ補正")

        buraku_groups = {}
        for spot in mixed_zone:
            b = spot['buraku']
            if b not in buraku_groups:
                buraku_groups[b] = 0
            buraku_groups[b] += 1

        print("\n部落別内訳:")
        for buraku, count in sorted(buraku_groups.items(), key=lambda x: -x[1])[:10]:
            print(f"  {buraku}: {count}箇所")

    print("\n" + "=" * 100)
    print("【観測所カバー率】")
    print("=" * 100)

    total = len(spots)
    kutsugata_pct = len(kutsugata_zone) / total * 100
    motodomari_pct = len(motodomari_zone) / total * 100
    mixed_pct = len(mixed_zone) / total * 100
    far_pct = len(far_zone) / total * 100

    print(f"\n沓形単独で代表可能: {len(kutsugata_zone)}箇所 ({kutsugata_pct:.1f}%)")
    print(f"本泊単独で代表可能: {len(motodomari_zone)}箇所 ({motodomari_pct:.1f}%)")
    print(f"両観測所必要（中間域）: {len(mixed_zone)}箇所 ({mixed_pct:.1f}%)")
    print(f"追加データ必要（遠隔地）: {len(far_zone)}箇所 ({far_pct:.1f}%)")

    covered = len(kutsugata_zone) + len(motodomari_zone)
    covered_pct = covered / total * 100
    print(f"\n→ 既存2観測所でカバー: {covered}箇所 ({covered_pct:.1f}%)")
    print(f"→ 追加対策必要: {len(mixed_zone) + len(far_zone)}箇所 ({mixed_pct + far_pct:.1f}%)")

    print("\n" + "=" * 100)
    print("【推奨運用】")
    print("=" * 100)

    print(f"\n1. 沓形範囲（{len(kutsugata_zone)}箇所）:")
    print("   - 沓形アメダス時別値を使用")
    print("   - 精度: 高")

    print(f"\n2. 本泊範囲（{len(motodomari_zone)}箇所）:")
    print("   - 本泊アメダス時別値を使用")
    print("   - 精度: 高")

    print(f"\n3. 中間域（{len(mixed_zone)}箇所）:")
    print("   - 両観測所データの距離加重平均")
    print("   - または干場に近い方の観測所を優先")
    print("   - 精度: 中")

    print(f"\n4. 遠隔地（{len(far_zone)}箇所）:")
    print("   - Open-Meteo API（干場の座標で直接取得）")
    print("   - ラジオゾンデ850hPa風向で地形補正")
    print("   - 精度: 中～低")

    # Export classification
    print("\n" + "=" * 100)
    print("【分類データの保存】")
    print("=" * 100)

    classification = {
        'kutsugata': [s['name'] for s in kutsugata_zone],
        'motodomari': [s['name'] for s in motodomari_zone],
        'mixed': [s['name'] for s in mixed_zone],
        'far': [s['name'] for s in far_zone]
    }

    with open('spot_classification.json', 'w', encoding='utf-8') as f:
        json.dump(classification, f, ensure_ascii=False, indent=2)

    print("\n✅ spot_classification.json に保存しました")
    print(f"  - 沓形範囲: {len(classification['kutsugata'])}箇所")
    print(f"  - 本泊範囲: {len(classification['motodomari'])}箇所")
    print(f"  - 中間域: {len(classification['mixed'])}箇所")
    print(f"  - 遠隔地: {len(classification['far'])}箇所")

    print("\n" + "=" * 100)

if __name__ == '__main__':
    main()
