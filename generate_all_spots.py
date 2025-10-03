#!/usr/bin/env python3
"""
hoshiba_spots.csvから全332箇所のJavaScript配列を生成
"""

import csv
import json

def generate_spots_array():
    spots = []

    with open('hoshiba_spots.csv', 'r', encoding='utf-8') as file:
        reader = csv.DictReader(file)
        for row in reader:
            spot = {
                'name': row['name'],
                'lat': float(row['lat']),
                'lon': float(row['lon']),
                'town': row['town'],
                'district': row['district'],
                'buraku': row['buraku']
            }
            spots.append(spot)

    # JavaScript配列形式で出力
    js_array = "const hoshibaSpots = [\n"
    for i, spot in enumerate(spots):
        js_array += f'    {{ name: "{spot["name"]}", lat: {spot["lat"]}, lon: {spot["lon"]}, town: "{spot["town"]}", district: "{spot["district"]}", buraku: "{spot["buraku"]}" }}'
        if i < len(spots) - 1:
            js_array += ","
        js_array += "\n"
    js_array += "];"

    return js_array, len(spots)

if __name__ == "__main__":
    array_str, count = generate_spots_array()
    print(f"Generated {count} spots")

    with open('all_spots_array.js', 'w', encoding='utf-8') as f:
        f.write(array_str)

    print("Saved to all_spots_array.js")