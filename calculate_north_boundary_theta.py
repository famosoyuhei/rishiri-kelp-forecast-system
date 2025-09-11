#!/usr/bin/env python3
"""
Calculate theta for northern boundary line
北岸境界線の動径θを計算
"""

import math

# 利尻山の座標 (Rishiri-san coordinates)
RISHIRI_SAN_LAT = 45.1821
RISHIRI_SAN_LON = 141.2421

# 南岸境界線の座標 (Southern boundary coordinates)
SOUTH_BOUNDARY_LAT = 45.1007
SOUTH_BOUNDARY_LON = 141.2461

# 北岸境界線の座標 (Northern boundary coordinates)
NORTH_BOUNDARY_LAT = 45.2246
NORTH_BOUNDARY_LON = 141.1489

def calculate_theta_from_rishiri(lat, lon):
    """Calculate theta from Rishiri-san with south boundary as theta=0"""
    
    # Calculate relative coordinates from Rishiri-san
    delta_lat = lat - RISHIRI_SAN_LAT
    delta_lon = lon - RISHIRI_SAN_LON
    
    # Convert to approximate meters for angle calculation
    lat_factor = 111000
    lon_factor = 111000 * math.cos(math.radians(RISHIRI_SAN_LAT))
    
    delta_y = delta_lat * lat_factor  # North-South (positive = north)
    delta_x = delta_lon * lon_factor  # East-West (positive = east)
    
    # Calculate angle from east (standard polar coordinates)
    theta_from_east = math.degrees(math.atan2(delta_y, delta_x))
    
    # Calculate south boundary line angle from Rishiri-san
    south_delta_lat = SOUTH_BOUNDARY_LAT - RISHIRI_SAN_LAT
    south_delta_lon = SOUTH_BOUNDARY_LON - RISHIRI_SAN_LON
    south_delta_y = south_delta_lat * lat_factor
    south_delta_x = south_delta_lon * lon_factor
    south_boundary_angle = math.degrees(math.atan2(south_delta_y, south_delta_x))
    
    # Adjust angle so south boundary line becomes θ=0
    theta_adjusted = theta_from_east - south_boundary_angle
    
    # Normalize to 0-360 degrees
    while theta_adjusted < 0:
        theta_adjusted += 360
    while theta_adjusted >= 360:
        theta_adjusted -= 360
    
    return theta_adjusted, theta_from_east, south_boundary_angle

def main():
    print("Boundary Theta Calculation")
    print("=" * 40)
    print(f"Rishiri-san coordinates: ({RISHIRI_SAN_LAT}, {RISHIRI_SAN_LON})")
    print(f"South boundary coordinates: ({SOUTH_BOUNDARY_LAT}, {SOUTH_BOUNDARY_LON})")
    print(f"North boundary coordinates: ({NORTH_BOUNDARY_LAT}, {NORTH_BOUNDARY_LON})")
    print()
    
    # Calculate south boundary theta
    south_theta, south_from_east, south_ref = calculate_theta_from_rishiri(SOUTH_BOUNDARY_LAT, SOUTH_BOUNDARY_LON)
    print("South boundary line:")
    print(f"  Angle from east: {south_from_east:.1f}deg")
    print(f"  Theta (with south boundary as 0): {south_theta:.1f}deg")
    print()
    
    # Calculate north boundary theta
    north_theta, north_from_east, _ = calculate_theta_from_rishiri(NORTH_BOUNDARY_LAT, NORTH_BOUNDARY_LON)
    print("North boundary line:")
    print(f"  Angle from east: {north_from_east:.1f}deg")
    print(f"  Theta (with south boundary as 0): {north_theta:.1f}deg")
    print()
    
    # Calculate the angular difference
    angular_diff = north_theta - south_theta
    if angular_diff < 0:
        angular_diff += 360
    
    print("Boundary analysis:")
    print(f"  Angular difference: {angular_diff:.1f}deg")
    print(f"  South boundary: theta = 0deg (by definition)")
    print(f"  North boundary: theta = {north_theta:.1f}deg")
    print()
    
    # Suggest town classification ranges
    print("Suggested town classification (with boundary-based theta):")
    if north_theta > 180:
        print(f"  Rishiri Fuji Town: theta = 0deg to {180:.1f}deg")
        print(f"  Rishiri Town: theta = {180:.1f}deg to {north_theta:.1f}deg")
        print(f"  Rishiri Town: theta = {north_theta:.1f}deg to 360deg")
    else:
        print(f"  Rishiri Fuji Town: theta = 0deg to {north_theta:.1f}deg")
        print(f"  Rishiri Town: theta = {north_theta:.1f}deg to 360deg")
    
    print(f"\nNote: North boundary theta = {north_theta:.1f}deg")

if __name__ == "__main__":
    main()