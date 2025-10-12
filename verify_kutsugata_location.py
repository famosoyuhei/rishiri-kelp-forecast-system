#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
沓形アメダス観測所の正確な位置を確認
泉町周辺の干場を検索
"""
import json
import sys
import io
import math
import re

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
    # Kutsugata Amedas station (from JMA official data)
    kutsugata_lat = 45.1342
    kutsugata_lon = 141.1144

    print("=" * 100)
    print("沓形アメダス観測所の位置確認")
    print("=" * 100)
    print(f"\nアメダス沓形: {kutsugata_lat}°N, {kutsugata_lon}°E")
    print("所在地: 北海道利尻郡利尻町沓形（気象庁公式データ）")

    # Load all_spots_array.js
    with open('all_spots_array.js', 'r', encoding='utf-8') as f:
        content = f.read()

    # Extract spot data using regex
    pattern = r'\{\s*name:\s*"([^"]+)",\s*lat:\s*([\d.]+),\s*lon:\s*([\d.]+),\s*town:\s*"([^"]*)",\s*district:\s*"([^"]*)",\s*buraku:\s*"([^"]*)"\s*\}'
    matches = re.findall(pattern, content)

    all_spots = []
    for match in matches:
        spot = {
            'name': match[0],
            'lat': float(match[1]),
            'lon': float(match[2]),
            'town': match[3],
            'district': match[4],
            'buraku': match[5]
        }
        spot['dist'] = calculate_distance(
            spot['lat'], spot['lon'],
            kutsugata_lat, kutsugata_lon
        )
        all_spots.append(spot)

    # Check all unique buraku names
    buraku_list = sorted(set(s['buraku'] for s in all_spots))
    print(f"\n全部落リスト ({len(buraku_list)}箇所):")
    for i, buraku in enumerate(buraku_list, 1):
        count = len([s for s in all_spots if s['buraku'] == buraku])
        print(f"  {i:2}. {buraku} ({count}箇所)")

    # Search for spots in 泉町 or similar
    print("\n" + "=" * 100)
    print("「泉」を含む部落の干場:")
    print("=" * 100)
    izumi_spots = [s for s in all_spots if '泉' in s['buraku']]
    if izumi_spots:
        izumi_spots.sort(key=lambda x: x['dist'])
        print(f"\n{'干場名':20} | {'緯度':>10} | {'経度':>10} | {'部落':>10} | {'距離':>8}")
        print("-" * 100)
        for spot in izumi_spots:
            print(f"{spot['name']:20} | {spot['lat']:>10.4f}N | {spot['lon']:>10.4f}E | {spot['buraku']:>10} | {spot['dist']:>7.2f}km")
    else:
        print("\n「泉」を含む部落は見つかりませんでした")

    # Show closest spots grouped by buraku
    print("\n" + "=" * 100)
    print("各部落の最近接干場（距離5km以内）:")
    print("=" * 100)

    close_spots = [s for s in all_spots if s['dist'] <= 5.0]
    close_spots.sort(key=lambda x: x['dist'])

    buraku_groups = {}
    for spot in close_spots:
        b = spot['buraku']
        if b not in buraku_groups:
            buraku_groups[b] = []
        buraku_groups[b].append(spot)

    for buraku in sorted(buraku_groups.keys()):
        spots = buraku_groups[buraku]
        closest = min(spots, key=lambda x: x['dist'])
        print(f"\n■ {buraku}: {len(spots)}箇所（最近接 {closest['dist']:.2f}km）")
        for spot in sorted(spots, key=lambda x: x['dist'])[:3]:
            print(f"   {spot['name']:20} {spot['lat']:.4f}N, {spot['lon']:.4f}E  距離{spot['dist']:.2f}km")

    # Absolute closest
    print("\n" + "=" * 100)
    print("【全331箇所の中で最も近い干場】")
    print("=" * 100)
    closest = min(all_spots, key=lambda x: x['dist'])
    print(f"\n干場名: {closest['name']}")
    print(f"座標: {closest['lat']:.4f}N, {closest['lon']:.4f}E")
    print(f"部落: {closest['buraku']}")
    print(f"距離: {closest['dist']:.3f}km")

    print("\n" + "=" * 100)

if __name__ == '__main__':
    main()
