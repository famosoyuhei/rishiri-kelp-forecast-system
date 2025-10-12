#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
正確な沓形アメダス座標で最近接干場を再計算
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
    # Kutsugata Amedas station - CORRECTED coordinates
    # Old: 45.1342, 141.1144
    # New: 45.178333, 141.138333 (from web search)
    kutsugata_lat = 45.178333
    kutsugata_lon = 141.138333

    print("=" * 100)
    print("沓形アメダス観測所の正確な座標で再計算")
    print("=" * 100)
    print(f"\n【訂正された座標】")
    print(f"旧座標: 45.1342°N, 141.1144°E")
    print(f"新座標: 45.178333°N, 141.138333°E (45°10.7'N, 141°08.3'E)")
    print(f"所在地: 利尻郡利尻町沓形泉町")
    print(f"標高: 14m")

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

    # Sort by distance
    all_spots.sort(key=lambda x: x['dist'])

    print("\n" + "=" * 100)
    print("【TOP 20 最近接干場】")
    print("=" * 100)
    print(f"\n{'順位':>4} | {'干場名':20} | {'緯度':>10} | {'経度':>10} | {'部落':>10} | {'距離':>8}")
    print("-" * 100)

    for i, spot in enumerate(all_spots[:20], 1):
        print(f"{i:>4} | {spot['name']:20} | {spot['lat']:>10.4f}N | {spot['lon']:>10.4f}E | {spot['buraku']:>10} | {spot['dist']:>7.2f}km")

    # Highlight the absolute closest
    closest = all_spots[0]
    print("\n" + "=" * 100)
    print("【最近接干場】")
    print("=" * 100)
    print(f"\n干場名: {closest['name']}")
    print(f"座標: {closest['lat']:.4f}N, {closest['lon']:.4f}E")
    print(f"部落: {closest['buraku']}")
    print(f"沓形アメダスからの距離: {closest['dist']:.3f}km ({closest['dist']*1000:.0f}m)")

    # Show izumicho spots
    print("\n" + "=" * 100)
    print("【泉町の干場】")
    print("=" * 100)
    izumi_spots = [s for s in all_spots if s['buraku'] == '泉町']
    izumi_spots.sort(key=lambda x: x['dist'])

    if izumi_spots:
        print(f"\n泉町の干場数: {len(izumi_spots)}箇所")
        print(f"\n{'干場名':20} | {'緯度':>10} | {'経度':>10} | {'距離':>8}")
        print("-" * 100)
        for spot in izumi_spots:
            print(f"{spot['name']:20} | {spot['lat']:>10.4f}N | {spot['lon']:>10.4f}E | {spot['dist']:>7.2f}km")

    print("\n" + "=" * 100)

if __name__ == '__main__':
    main()
