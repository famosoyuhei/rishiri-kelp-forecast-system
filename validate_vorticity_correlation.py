#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
500hPa相対渦度と風向-山角度差の相関検証

仮説: シノプティックスケールが支配的な東側では
     500hPa渦度との相関が強く、山岳効果との相関は弱い
"""

import json
import math
import numpy as np

def load_correlation_results():
    """風向-山角度差の相関結果を読み込み"""
    with open('wind_angle_omega_correlation.json', 'r', encoding='utf-8') as f:
        return json.load(f)

def calculate_mountain_azimuth(lat, lon):
    """山頂方位角を計算"""
    RISHIRI_SAN_LAT = 45.1821
    RISHIRI_SAN_LON = 141.2421
    delta_lat = RISHIRI_SAN_LAT - lat
    delta_lon = RISHIRI_SAN_LON - lon
    math_angle = math.degrees(math.atan2(delta_lat, delta_lon))
    mountain_azimuth = 90 - math_angle
    if mountain_azimuth < 0:
        mountain_azimuth += 360
    elif mountain_azimuth >= 360:
        mountain_azimuth -= 360
    return mountain_azimuth

def classify_spots_by_location(spots):
    """干場を位置で分類（東西南北）"""
    classified = {
        'east': [],      # 60-120°（本島側）
        'southeast': [], # 120-160°
        'south': [],     # 160-200°
        'southwest': [], # 200-240°
        'west': [],      # 240-300°
        'northwest': [], # 300-330°
        'north': []      # 330-360° & 0-60°
    }

    for spot_result in spots:
        name = spot_result['name']
        lat = float(name.split('_')[1][:4]) / 100
        lon = float(name.split('_')[2][:4]) / 100

        azimuth = calculate_mountain_azimuth(lat, lon)
        correlation = spot_result['correlation']

        spot_data = {
            'name': name,
            'azimuth': azimuth,
            'omega_corr': correlation
        }

        if 60 <= azimuth < 120:
            classified['east'].append(spot_data)
        elif 120 <= azimuth < 160:
            classified['southeast'].append(spot_data)
        elif 160 <= azimuth < 200:
            classified['south'].append(spot_data)
        elif 200 <= azimuth < 240:
            classified['southwest'].append(spot_data)
        elif 240 <= azimuth < 300:
            classified['west'].append(spot_data)
        elif 300 <= azimuth < 330:
            classified['northwest'].append(spot_data)
        else:  # 330-360 or 0-60
            classified['north'].append(spot_data)

    return classified

def analyze_by_region():
    """地域別の相関特性を分析"""
    results = load_correlation_results()
    spot_results = results['spot_results']

    # 地域別に分類
    classified = classify_spots_by_location(spot_results)

    region_stats = {}

    for region_name, spots in classified.items():
        if not spots:
            continue

        correlations = [s['omega_corr'] for s in spots]
        azimuths = [s['azimuth'] for s in spots]

        region_stats[region_name] = {
            'count': len(spots),
            'mean_corr': float(np.mean(correlations)),
            'std_corr': float(np.std(correlations)),
            'min_corr': float(np.min(correlations)),
            'max_corr': float(np.max(correlations)),
            'mean_azimuth': float(np.mean(azimuths)),
            'azimuth_range': [float(np.min(azimuths)), float(np.max(azimuths))]
        }

    east_corr = region_stats.get('east', {}).get('mean_corr', 0)
    west_corr = region_stats.get('west', {}).get('mean_corr', 0)
    southwest_corr = region_stats.get('southwest', {}).get('mean_corr', 0)

    # 結果を保存
    output = {
        'hypothesis': '東側はシノプティックスケール支配、西側はメソスケール支配',
        'region_statistics': region_stats,
        'conclusion': {
            'east_mean_correlation': east_corr,
            'west_mean_correlation': west_corr,
            'difference': east_corr - west_corr,
            'hypothesis_supported': east_corr > 0.3 and west_corr < -0.3
        }
    }

    with open('scale_analysis_results.json', 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

if __name__ == '__main__':
    analyze_by_region()
