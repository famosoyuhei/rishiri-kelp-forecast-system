#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Find spots near Kutsugata Amedas station with similar weather conditions
"""

import pandas as pd
import math
import json

# Kutsugata Amedas location
KUTSUGATA_LAT = 45.2194
KUTSUGATA_LON = 141.2133

# Rishiri mountain center
RISHIRI_CENTER = (45.178269, 141.228528)

def calc_distance(lat1, lon1, lat2, lon2):
    """Calculate distance between two points in km (Haversine formula)"""
    R = 6371
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)

    a = math.sin(delta_lat/2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    return R * c

def calc_theta(lat, lon):
    """Calculate angle (theta) from Rishiri mountain center"""
    center_lat, center_lon = RISHIRI_CENTER
    delta_lon = lon - center_lon
    delta_lat = lat - center_lat
    theta = math.degrees(math.atan2(delta_lon * math.cos(math.radians(center_lat)), delta_lat))
    theta = (theta + 360) % 360
    return theta

def theta_diff(theta1, theta2):
    """Calculate angle difference (0-180 degrees)"""
    diff = abs(theta1 - theta2)
    if diff > 180:
        diff = 360 - diff
    return diff

# Load spot data
spots = pd.read_csv('hoshiba_spots.csv')

# Calculate distance from Kutsugata
spots['distance_from_kutsugata'] = spots.apply(
    lambda row: calc_distance(KUTSUGATA_LAT, KUTSUGATA_LON, row['lat'], row['lon']),
    axis=1
)

# Calculate theta
spots['theta'] = spots.apply(lambda row: calc_theta(row['lat'], row['lon']), axis=1)

# Kutsugata theta
kutsugata_theta = calc_theta(KUTSUGATA_LAT, KUTSUGATA_LON)

# Calculate theta difference
spots['theta_diff'] = spots['theta'].apply(lambda t: theta_diff(t, kutsugata_theta))

print('=' * 100)
print('Amedas Kutsugata - Nearby Spots Analysis')
print('=' * 100)
print()
print(f'Kutsugata Amedas: Lat {KUTSUGATA_LAT}, Lon {KUTSUGATA_LON}')
print(f'Kutsugata theta (angle from Rishiri center): {kutsugata_theta:.1f} degrees')
print()

# Find nearby spots (within 10km)
nearby = spots[spots['distance_from_kutsugata'] <= 10.0].copy()
nearby = nearby.sort_values('distance_from_kutsugata')

print(f'Spots within 10km from Kutsugata: {len(nearby)} spots')
print()

# Display top 30
print('Top 30 by distance:')
print('-' * 100)
print(f'{"Rank":<6} {"Spot Name":<15} {"Dist(km)":<10} {"Theta":<10} {"Delta":<10} {"Town":<15} {"District":<12}')
print('-' * 100)

for i, (_, row) in enumerate(nearby.head(30).iterrows(), 1):
    print(f'{i:<6} {row["name"]:<15} {row["distance_from_kutsugata"]:<10.2f} {row["theta"]:<10.1f} {row["theta_diff"]:<10.1f} {row["town"]:<15} {row["district"]:<12}')

print()
print('=' * 100)
print('BEST MATCHES: Spots with most similar weather conditions to Kutsugata')
print('=' * 100)
print()

# Best matches: distance <= 3km AND theta_diff <= 20
best_matches = nearby[(nearby['distance_from_kutsugata'] <= 3.0) & (nearby['theta_diff'] <= 20)]
print(f'Criteria: Distance <= 3km AND Delta-theta <= 20 degrees => {len(best_matches)} spots')
print()

if len(best_matches) > 0:
    result_list = []
    for i, (_, row) in enumerate(best_matches.iterrows(), 1):
        spot_info = {
            'rank': i,
            'name': row['name'],
            'town': row['town'],
            'district': row['district'],
            'buraku': row['buraku'],
            'lat': row['lat'],
            'lon': row['lon'],
            'distance_km': round(row['distance_from_kutsugata'], 2),
            'theta': round(row['theta'], 1),
            'theta_diff': round(row['theta_diff'], 1)
        }
        result_list.append(spot_info)

        print(f'{i}. {row["name"]}')
        print(f'   Location: {row["town"]} {row["district"]} {row["buraku"]}')
        print(f'   Coordinates: Lat {row["lat"]:.4f}, Lon {row["lon"]:.4f}')
        print(f'   Distance from Kutsugata: {row["distance_from_kutsugata"]:.2f} km')
        print(f'   Theta: {row["theta"]:.1f} degrees (Delta = {row["theta_diff"]:.1f} degrees)')
        print()

    # Save to JSON
    with open('kutsugata_best_matches.json', 'w', encoding='utf-8') as f:
        json.dump(result_list, f, ensure_ascii=False, indent=2)
    print(f'Results saved to: kutsugata_best_matches.json')

else:
    print('No matches found - relaxing criteria...')
    best_matches = nearby[(nearby['distance_from_kutsugata'] <= 5.0) & (nearby['theta_diff'] <= 30)]
    print(f'Relaxed criteria: Distance <= 5km AND Delta-theta <= 30 degrees => {len(best_matches)} spots')
    print()

    result_list = []
    for i, (_, row) in enumerate(best_matches.head(10).iterrows(), 1):
        spot_info = {
            'rank': i,
            'name': row['name'],
            'distance_km': round(row['distance_from_kutsugata'], 2),
            'theta_diff': round(row['theta_diff'], 1)
        }
        result_list.append(spot_info)
        print(f'{i}. {row["name"]} - Distance: {row["distance_from_kutsugata"]:.2f}km, Delta-theta: {row["theta_diff"]:.1f} degrees')

    # Save to JSON
    with open('kutsugata_best_matches.json', 'w', encoding='utf-8') as f:
        json.dump(result_list, f, ensure_ascii=False, indent=2)

print()
print('=' * 100)
print('Analysis complete')
print('=' * 100)
