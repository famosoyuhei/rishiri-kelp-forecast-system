#!/usr/bin/env python3
"""
Auto-classification system for new hoshiba (drying field) additions
新規干場追加時の自動分類システム
"""

import math
import csv
import os
from datetime import datetime

# 利尻山の座標 (Rishiri-san coordinates)
RISHIRI_SAN_LAT = 45.1821
RISHIRI_SAN_LON = 141.2421

# 南岸町境界線の座標 (Southern town boundary coordinates)
SOUTH_TOWN_BOUNDARY_LAT = 45.1007
SOUTH_TOWN_BOUNDARY_LON = 141.2461

# 全地区の境界線定義 (All district boundary definitions)
ONIWAKI_BOUNDARIES = [9.3, 19.1, 28.4, 40.9, 46.2, 55.4, 69.4, 87.3, 105.7]
OSHIDOMARI_BOUNDARIES = [147.9, 159.4, 187.6, 188.2, 189.9, 192.1, 198.5, 202.5, 210.0]
KUTSUGATA_BOUNDARIES = [246.2, 253.8, 261.6, 267.2, 272.6, 286.4]
SENPOSHI_BOUNDARIES = [311.4, 324.8, 335.6, 341.9, 346.4, 350.5]

# 部落名定義 (Buraku name definitions)
BURAKU_NAMES = {
    "oniwaki": ["野中", "南浜", "沼浦", "金崎", "鬼脇", "清川", "二石", "石崎", "旭浜", "鰊泊"],
    "oshidomari": ["雄忠志内", "野塚", "湾内", "港町", "本町", "栄町", "富士野", "富士岬", "本泊", "大磯"],
    "kutsugata": ["栄浜", "新湊", "種富町", "富野・日出町・緑町・本町・富士見町", "泉町", "神居", "蘭泊"],
    "senposhi": ["久連", "長浜", "神磯", "政泊", "本町", "元村", "御崎"]
}

class HoshibaClassifier:
    """Automatic classification system for hoshiba fields"""
    
    def __init__(self, csv_file='hoshiba_spots.csv'):
        self.csv_file = csv_file
        self.ensure_csv_exists()
    
    def ensure_csv_exists(self):
        """Ensure CSV file exists with proper headers"""
        if not os.path.exists(self.csv_file):
            with open(self.csv_file, 'w', encoding='utf-8', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['name', 'lat', 'lon', 'town', 'district', 'buraku'])
            print(f"Created new CSV file: {self.csv_file}")
    
    def calculate_boundary_based_theta(self, lat, lon):
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
    
    def classify_town_by_theta(self, theta):
        """Classify town based on boundary-referenced theta"""
        NORTH_BOUNDARY_THETA = 235.1
        
        if 0 <= theta <= NORTH_BOUNDARY_THETA:
            return "利尻富士町"
        else:
            return "利尻町"
    
    def classify_district_by_theta(self, theta, town):
        """Classify district within town based on theta"""
        
        if town == "利尻富士町":
            FUJI_DISTRICT_BOUNDARY_THETA = 122.0
            if 0 <= theta <= FUJI_DISTRICT_BOUNDARY_THETA:
                return "鬼脇"
            else:
                return "鴛泊"
        
        elif town == "利尻町":
            RISHIRI_DISTRICT_BOUNDARY_THETA = 296.8
            if 235.1 <= theta <= RISHIRI_DISTRICT_BOUNDARY_THETA:
                return "沓形"
            else:
                return "仙法志"
        
        return "未分類"
    
    def classify_buraku_by_theta(self, theta, district):
        """Classify buraku within district based on theta"""
        
        if district == "鬼脇":
            boundaries = ONIWAKI_BOUNDARIES
            buraku_names = BURAKU_NAMES["oniwaki"]
        elif district == "鴛泊":
            boundaries = OSHIDOMARI_BOUNDARIES
            buraku_names = BURAKU_NAMES["oshidomari"]
        elif district == "沓形":
            boundaries = KUTSUGATA_BOUNDARIES
            buraku_names = BURAKU_NAMES["kutsugata"]
        elif district == "仙法志":
            boundaries = SENPOSHI_BOUNDARIES
            buraku_names = BURAKU_NAMES["senposhi"]
        else:
            return "未分類"
        
        for i, boundary_theta in enumerate(boundaries):
            if theta < boundary_theta:
                return buraku_names[i]
        return buraku_names[-1]
    
    def classify_coordinates(self, lat, lon):
        """Complete classification for given coordinates"""
        theta = self.calculate_boundary_based_theta(lat, lon)
        town = self.classify_town_by_theta(theta)
        district = self.classify_district_by_theta(theta, town)
        buraku = self.classify_buraku_by_theta(theta, district)
        
        return {
            'theta': theta,
            'town': town,
            'district': district,
            'buraku': buraku
        }
    
    def add_new_hoshiba(self, name, lat, lon, auto_save=True):
        """Add new hoshiba with automatic classification"""
        
        # Validate coordinates are within reasonable range for Rishiri Island
        if not (45.0 <= lat <= 45.3 and 141.0 <= lon <= 141.4):
            raise ValueError(f"Coordinates ({lat}, {lon}) are outside Rishiri Island range")
        
        # Check if name already exists
        existing_names = set()
        if os.path.exists(self.csv_file):
            with open(self.csv_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                existing_names = {row['name'] for row in reader}
        
        if name in existing_names:
            raise ValueError(f"Hoshiba name '{name}' already exists")
        
        # Classify the new coordinates
        classification = self.classify_coordinates(lat, lon)
        
        # Prepare new row
        new_row = {
            'name': name,
            'lat': lat,
            'lon': lon,
            'town': classification['town'],
            'district': classification['district'],
            'buraku': classification['buraku']
        }
        
        if auto_save:
            self._append_to_csv(new_row)
        
        # Log the addition
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}] Added new hoshiba:")
        print(f"  Name: {name}")
        print(f"  Location: ({lat:.6f}, {lon:.6f})")
        print(f"  Theta: {classification['theta']:.1f}°")
        print(f"  Classification: {classification['town']} > {classification['district']} > {classification['buraku']}")
        
        return new_row
    
    def _append_to_csv(self, row_data):
        """Append new row to CSV file"""
        with open(self.csv_file, 'a', encoding='utf-8', newline='') as f:
            fieldnames = ['name', 'lat', 'lon', 'town', 'district', 'buraku']
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writerow(row_data)
    
    def add_multiple_hoshiba(self, hoshiba_list):
        """Add multiple hoshiba fields at once"""
        results = []
        for name, lat, lon in hoshiba_list:
            try:
                result = self.add_new_hoshiba(name, lat, lon, auto_save=False)
                results.append(result)
            except ValueError as e:
                print(f"Error adding {name}: {e}")
                continue
        
        # Save all at once
        if results:
            for result in results:
                self._append_to_csv(result)
            print(f"\nSuccessfully added {len(results)} new hoshiba fields")
        
        return results
    
    def get_classification_for_coordinates(self, lat, lon):
        """Get classification without saving (for preview)"""
        return self.classify_coordinates(lat, lon)

def main():
    """Example usage of the auto-classification system"""
    classifier = HoshibaClassifier()
    
    print("Rishiri Island Hoshiba Auto-Classification System")
    print("=" * 55)
    print()
    
    # Example: Add a new hoshiba field
    try:
        # Example coordinates within Rishiri Island
        example_name = "H_TEST_2024"
        example_lat = 45.15
        example_lon = 141.20
        
        print("Testing classification for example coordinates:")
        classification = classifier.get_classification_for_coordinates(example_lat, example_lon)
        print(f"Location: ({example_lat}, {example_lon})")
        print(f"Theta: {classification['theta']:.1f}°")
        print(f"Classification: {classification['town']} > {classification['district']} > {classification['buraku']}")
        print()
        
        # Uncomment to actually add the test field:
        # classifier.add_new_hoshiba(example_name, example_lat, example_lon)
        
    except ValueError as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()