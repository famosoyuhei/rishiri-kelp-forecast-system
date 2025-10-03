#!/usr/bin/env python3
"""
Calculate theta for Nonaka-Minamihama boundary line
野中と南浜の境界線の動径θを計算
"""

import math
import csv

# 利尻山の座標 (Rishiri-san coordinates)
RISHIRI_SAN_LAT = 45.1821
RISHIRI_SAN_LON = 141.2421

# 南岸町境界線の座標 (Southern town boundary coordinates)
SOUTH_TOWN_BOUNDARY_LAT = 45.1007
SOUTH_TOWN_BOUNDARY_LON = 141.2461

# 野中・南浜境界線の座標 (Nonaka-Minamihama boundary coordinates)
NONAKA_MINAMIHAMA_BOUNDARY_LAT = 45.108
NONAKA_MINAMIHAMA_BOUNDARY_LON = 141.263

# 南浜・沼浦境界線の座標 (Minamihama-Numaura boundary coordinates)
MINAMIHAMA_NUMAURA_BOUNDARY_LAT = 45.109
MINAMIHAMA_NUMAURA_BOUNDARY_LON = 141.282

def calculate_boundary_based_theta(lat, lon):
    """Calculate theta with south town boundary as theta=0"""
    
    # Calculate relative coordinates from Rishiri-san
    delta_lat = lat - RISHIRI_SAN_LAT
    delta_lon = lon - RISHIRI_SAN_LON
    
    # Convert to approximate meters for angle calculation
    lat_factor = 111000
    lon_factor = 111000 * math.cos(math.radians(RISHIRI_SAN_LAT))
    
    delta_y = delta_lat * lat_factor
    delta_x = delta_lon * lon_factor
    
    # Calculate angle from east (standard polar coordinates)
    theta_from_east = math.degrees(math.atan2(delta_y, delta_x))
    
    # Calculate south town boundary line angle from Rishiri-san
    south_delta_lat = SOUTH_TOWN_BOUNDARY_LAT - RISHIRI_SAN_LAT
    south_delta_lon = SOUTH_TOWN_BOUNDARY_LON - RISHIRI_SAN_LON
    south_delta_y = south_delta_lat * lat_factor
    south_delta_x = south_delta_lon * lon_factor
    south_boundary_angle = math.degrees(math.atan2(south_delta_y, south_delta_x))
    
    # Adjust angle so south town boundary line becomes θ=0
    theta_adjusted = theta_from_east - south_boundary_angle
    
    # Normalize to 0-360 degrees
    while theta_adjusted < 0:
        theta_adjusted += 360
    while theta_adjusted >= 360:
        theta_adjusted -= 360
    
    return theta_adjusted

def analyze_boundary_points():
    """Analyze the Nonaka-Minamihama-Numaura boundary points and their theta values"""
    
    print("Oniwaki District Buraku Boundary Analysis")
    print("=" * 50)
    print(f"Rishiri-san coordinates: ({RISHIRI_SAN_LAT}, {RISHIRI_SAN_LON})")
    print(f"South town boundary: ({SOUTH_TOWN_BOUNDARY_LAT}, {SOUTH_TOWN_BOUNDARY_LON}) -> theta = 0deg")
    print(f"Nonaka-Minamihama boundary: ({NONAKA_MINAMIHAMA_BOUNDARY_LAT}, {NONAKA_MINAMIHAMA_BOUNDARY_LON})")
    print(f"Minamihama-Numaura boundary: ({MINAMIHAMA_NUMAURA_BOUNDARY_LAT}, {MINAMIHAMA_NUMAURA_BOUNDARY_LON})")
    print()
    
    # Calculate theta for both boundary points
    nonaka_minamihama_theta = calculate_boundary_based_theta(
        NONAKA_MINAMIHAMA_BOUNDARY_LAT, 
        NONAKA_MINAMIHAMA_BOUNDARY_LON
    )
    
    minamihama_numaura_theta = calculate_boundary_based_theta(
        MINAMIHAMA_NUMAURA_BOUNDARY_LAT,
        MINAMIHAMA_NUMAURA_BOUNDARY_LON
    )
    
    print(f"Nonaka-Minamihama boundary theta: {nonaka_minamihama_theta:.1f}deg")
    print(f"Minamihama-Numaura boundary theta: {minamihama_numaura_theta:.1f}deg")
    print()
    
    # Load current CSV to classify fields into three buraku
    print("Analyzing current Oniwaki district fields for Nonaka/Minamihama/Numaura classification...")
    
    nonaka_fields = []
    minamihama_fields = []
    numaura_fields = []
    
    with open('hoshiba_spots.csv', 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row['district'] == '鬼脇':  # Only analyze Oniwaki district fields
                lat = float(row['lat'])
                lon = float(row['lon'])
                theta = calculate_boundary_based_theta(lat, lon)
                
                # Classification by theta ranges:
                # Nonaka: theta < nonaka_minamihama_theta
                # Minamihama: nonaka_minamihama_theta <= theta < minamihama_numaura_theta  
                # Numaura: theta >= minamihama_numaura_theta
                if theta < nonaka_minamihama_theta:
                    nonaka_fields.append({
                        'name': row['name'],
                        'theta': theta,
                        'lat': lat,
                        'lon': lon
                    })
                elif theta < minamihama_numaura_theta:
                    minamihama_fields.append({
                        'name': row['name'],
                        'theta': theta,
                        'lat': lat,
                        'lon': lon
                    })
                else:
                    numaura_fields.append({
                        'name': row['name'],
                        'theta': theta,
                        'lat': lat,
                        'lon': lon
                    })
    
    print(f"Proposed Nonaka buraku: {len(nonaka_fields)} fields")
    print(f"Proposed Minamihama buraku: {len(minamihama_fields)} fields") 
    print(f"Proposed Numaura buraku: {len(numaura_fields)} fields")
    print()
    
    print("Nonaka buraku fields (theta < {:.1f}deg):".format(nonaka_minamihama_theta))
    for field in sorted(nonaka_fields, key=lambda x: x['theta']):
        print(f"  {field['name']}: theta = {field['theta']:.1f}deg")
    print()
    
    print("Minamihama buraku fields ({:.1f}deg <= theta < {:.1f}deg):".format(nonaka_minamihama_theta, minamihama_numaura_theta))
    for field in sorted(minamihama_fields, key=lambda x: x['theta'])[:10]:  # Show first 10
        print(f"  {field['name']}: theta = {field['theta']:.1f}deg")
    if len(minamihama_fields) > 10:
        print(f"  ... and {len(minamihama_fields) - 10} more")
    print()
    
    print("Numaura buraku fields (theta >= {:.1f}deg):".format(minamihama_numaura_theta))
    for field in sorted(numaura_fields, key=lambda x: x['theta'])[:10]:  # Show first 10
        print(f"  {field['name']}: theta = {field['theta']:.1f}deg")
    if len(numaura_fields) > 10:
        print(f"  ... and {len(numaura_fields) - 10} more")
    print()
    
    return nonaka_minamihama_theta, minamihama_numaura_theta, nonaka_fields, minamihama_fields, numaura_fields

if __name__ == "__main__":
    analyze_boundary_points()