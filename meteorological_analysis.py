#!/usr/bin/env python3
"""
Meteorological Analysis for Rishiri Island Kelp Drying Fields
利尻島昆布干場の気象学的分析システム

Analyzes cosine relationships between hoshiba theta values and wind direction
with vertical pressure velocity and other meteorological parameters.
"""

import math
import csv
import numpy as np
import pandas as pd
import requests
import json
from datetime import datetime, timedelta
import time
from typing import Dict, List, Tuple, Optional

# Geographic constants
RISHIRI_SAN_LAT = 45.1821
RISHIRI_SAN_LON = 141.2421
SOUTH_TOWN_BOUNDARY_LAT = 45.1007
SOUTH_TOWN_BOUNDARY_LON = 141.2461

class KelpSeasonMeteoAnalyzer:
    """
    Meteorological analyzer for kelp season (June-September) at Rishiri Island
    昆布シーズン（6-9月）の利尻島気象分析
    """
    
    def __init__(self, csv_file='hoshiba_spots.csv'):
        self.csv_file = csv_file
        self.hoshiba_data = self.load_hoshiba_data()
        self.weather_data = {}
        
    def load_hoshiba_data(self) -> pd.DataFrame:
        """Load hoshiba spots with theta calculations"""
        print("Loading hoshiba data with theta calculations...")
        
        df = pd.read_csv(self.csv_file, encoding='utf-8')
        
        # Calculate theta for each field
        theta_values = []
        for _, row in df.iterrows():
            theta = self.calculate_boundary_based_theta(row['lat'], row['lon'])
            theta_values.append(theta)
        
        df['theta'] = theta_values
        print(f"Loaded {len(df)} hoshiba fields with theta calculations")
        return df
    
    def calculate_boundary_based_theta(self, lat: float, lon: float) -> float:
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
    
    def get_sample_weather_data(self, year: int = 2024) -> Dict:
        """
        Get sample weather data structure for analysis demonstration
        実際のAPIデータを模倣したサンプル気象データ
        """
        print(f"Generating sample weather data for kelp season {year}...")
        
        # Sample data structure similar to ECMWF/GFS format
        sample_data = {
            'location': {'lat': RISHIRI_SAN_LAT, 'lon': RISHIRI_SAN_LON},
            'kelp_season_months': [6, 7, 8, 9],
            'daily_data': []
        }
        
        # Generate sample daily data for June-September
        start_date = datetime(year, 6, 1)
        end_date = datetime(year, 9, 30)
        current_date = start_date
        
        while current_date <= end_date:
            # Simulate realistic weather patterns for Rishiri Island
            day_of_year = current_date.timetuple().tm_yday
            
            # Seasonal wind direction patterns (degrees from north)
            base_wind_dir = 180 + 60 * math.sin(2 * math.pi * day_of_year / 365)
            wind_direction = (base_wind_dir + np.random.normal(0, 30)) % 360
            
            # Wind speed (m/s)
            wind_speed = 3 + 5 * abs(math.sin(2 * math.pi * day_of_year / 365)) + np.random.normal(0, 2)
            wind_speed = max(0, wind_speed)
            
            # Vertical pressure velocity (Pa/s) - typical range for mid-latitudes
            omega = np.random.normal(0, 0.02)  # Pa/s
            
            # Temperature (°C) - summer temperatures for Rishiri
            temp_base = 15 + 8 * math.sin(2 * math.pi * (day_of_year - 150) / 365)
            temperature = temp_base + np.random.normal(0, 3)
            
            # Pressure (hPa)
            pressure = 1013 + np.random.normal(0, 10)
            
            # Humidity (%)
            humidity = 70 + 20 * abs(math.sin(2 * math.pi * day_of_year / 365)) + np.random.normal(0, 10)
            humidity = max(0, min(100, humidity))
            
            daily_record = {
                'date': current_date.strftime('%Y-%m-%d'),
                'wind_direction': round(wind_direction, 1),
                'wind_speed': round(wind_speed, 2),
                'vertical_pressure_velocity': round(omega, 6),
                'temperature': round(temperature, 1),
                'pressure': round(pressure, 1),
                'humidity': round(humidity, 1)
            }
            
            sample_data['daily_data'].append(daily_record)
            current_date += timedelta(days=1)
        
        print(f"Generated {len(sample_data['daily_data'])} days of sample weather data")
        return sample_data
    
    def calculate_cosine_wind_theta_relationships(self, weather_data: Dict) -> pd.DataFrame:
        """
        Calculate cosine of (theta - wind_direction) for each hoshiba field
        各干場のθと風向の差のコサイン計算
        """
        print("Calculating cosine relationships between hoshiba theta and wind direction...")
        
        results = []
        
        for daily_data in weather_data['daily_data']:
            date = daily_data['date']
            wind_dir = daily_data['wind_direction']
            wind_speed = daily_data['wind_speed']
            omega = daily_data['vertical_pressure_velocity']
            temperature = daily_data['temperature']
            pressure = daily_data['pressure']
            humidity = daily_data['humidity']
            
            # Calculate cosine relationships for each hoshiba field
            for _, hoshiba in self.hoshiba_data.iterrows():
                theta = hoshiba['theta']
                
                # Calculate angle difference
                angle_diff = theta - wind_dir
                
                # Normalize angle difference to [-180, 180]
                while angle_diff > 180:
                    angle_diff -= 360
                while angle_diff < -180:
                    angle_diff += 360
                
                # Calculate cosine of the difference
                cos_theta_wind = math.cos(math.radians(angle_diff))
                
                result = {
                    'date': date,
                    'hoshiba_name': hoshiba['name'],
                    'town': hoshiba['town'],
                    'district': hoshiba['district'],
                    'buraku': hoshiba['buraku'],
                    'hoshiba_theta': theta,
                    'wind_direction': wind_dir,
                    'wind_speed': wind_speed,
                    'angle_difference': angle_diff,
                    'cos_theta_wind': cos_theta_wind,
                    'vertical_pressure_velocity': omega,
                    'temperature': temperature,
                    'pressure': pressure,
                    'humidity': humidity
                }
                
                results.append(result)
        
        df = pd.DataFrame(results)
        print(f"Calculated {len(df)} cosine relationships (hoshiba x days)")
        return df
    
    def analyze_correlations(self, cosine_data: pd.DataFrame) -> Dict:
        """
        Analyze correlations between cosine values and meteorological parameters
        コサイン値と気象パラメータの相関分析
        """
        print("Analyzing correlations between cosine values and meteorological parameters...")
        
        # Group by hoshiba field for individual analysis
        correlations = {}
        
        # Overall correlation analysis
        overall_corr = {
            'cos_theta_wind_vs_omega': cosine_data['cos_theta_wind'].corr(cosine_data['vertical_pressure_velocity']),
            'cos_theta_wind_vs_wind_speed': cosine_data['cos_theta_wind'].corr(cosine_data['wind_speed']),
            'cos_theta_wind_vs_temperature': cosine_data['cos_theta_wind'].corr(cosine_data['temperature']),
            'cos_theta_wind_vs_pressure': cosine_data['cos_theta_wind'].corr(cosine_data['pressure']),
            'cos_theta_wind_vs_humidity': cosine_data['cos_theta_wind'].corr(cosine_data['humidity'])
        }
        
        correlations['overall'] = overall_corr
        
        # District-level analysis
        district_correlations = {}
        for district in cosine_data['district'].unique():
            district_data = cosine_data[cosine_data['district'] == district]
            
            district_corr = {
                'cos_theta_wind_vs_omega': district_data['cos_theta_wind'].corr(district_data['vertical_pressure_velocity']),
                'cos_theta_wind_vs_wind_speed': district_data['cos_theta_wind'].corr(district_data['wind_speed']),
                'cos_theta_wind_vs_temperature': district_data['cos_theta_wind'].corr(district_data['temperature']),
                'cos_theta_wind_vs_pressure': district_data['cos_theta_wind'].corr(district_data['pressure']),
                'cos_theta_wind_vs_humidity': district_data['cos_theta_wind'].corr(district_data['humidity'])
            }
            
            district_correlations[district] = district_corr
        
        correlations['by_district'] = district_correlations
        
        # Seasonal analysis (by month)
        cosine_data['month'] = pd.to_datetime(cosine_data['date']).dt.month
        monthly_correlations = {}
        
        for month in [6, 7, 8, 9]:  # Kelp season months
            month_data = cosine_data[cosine_data['month'] == month]
            if len(month_data) > 0:
                month_corr = {
                    'cos_theta_wind_vs_omega': month_data['cos_theta_wind'].corr(month_data['vertical_pressure_velocity']),
                    'cos_theta_wind_vs_wind_speed': month_data['cos_theta_wind'].corr(month_data['wind_speed']),
                    'cos_theta_wind_vs_temperature': month_data['cos_theta_wind'].corr(month_data['temperature']),
                    'cos_theta_wind_vs_pressure': month_data['cos_theta_wind'].corr(month_data['pressure']),
                    'cos_theta_wind_vs_humidity': month_data['cos_theta_wind'].corr(month_data['humidity'])
                }
                monthly_correlations[month] = month_corr
        
        correlations['by_month'] = monthly_correlations
        
        return correlations
    
    def generate_analysis_report(self, correlations: Dict, cosine_data: pd.DataFrame) -> str:
        """Generate comprehensive analysis report"""
        
        report = []
        report.append("=" * 80)
        report.append("RISHIRI ISLAND KELP SEASON METEOROLOGICAL ANALYSIS REPORT")
        report.append("Rishiri Island Kelp Season Meteorological Analysis Report")
        report.append("=" * 80)
        report.append("")
        
        # Summary statistics
        report.append("SUMMARY STATISTICS")
        report.append("-" * 40)
        report.append(f"Analysis period: June-September kelp season")
        report.append(f"Total hoshiba fields analyzed: {cosine_data['hoshiba_name'].nunique()}")
        report.append(f"Total daily records: {len(cosine_data)}")
        report.append(f"Districts covered: {', '.join(cosine_data['district'].unique())}")
        report.append("")
        
        # Overall correlations
        report.append("OVERALL CORRELATIONS")
        report.append("-" * 40)
        overall = correlations['overall']
        
        report.append("Cosine(θ-wind_direction) correlations with meteorological parameters:")
        report.append(f"  vs Vertical Pressure Velocity (ω): {overall['cos_theta_wind_vs_omega']:.4f}")
        report.append(f"  vs Wind Speed: {overall['cos_theta_wind_vs_wind_speed']:.4f}")
        report.append(f"  vs Temperature: {overall['cos_theta_wind_vs_temperature']:.4f}")
        report.append(f"  vs Pressure: {overall['cos_theta_wind_vs_pressure']:.4f}")
        report.append(f"  vs Humidity: {overall['cos_theta_wind_vs_humidity']:.4f}")
        report.append("")
        
        # District-level analysis
        report.append("DISTRICT-LEVEL ANALYSIS")
        report.append("-" * 40)
        
        district_names = {"鬼脇": "Oniwaki", "鴛泊": "Oshidomari", "沓形": "Kutsugata", "仙法志": "Senposhi"}
        
        for district_jp, district_en in district_names.items():
            if district_jp in correlations['by_district']:
                district_corr = correlations['by_district'][district_jp]
                report.append(f"{district_en} District:")
                report.append(f"  Cosine vs Vertical Pressure Velocity: {district_corr['cos_theta_wind_vs_omega']:.4f}")
                report.append(f"  Cosine vs Wind Speed: {district_corr['cos_theta_wind_vs_wind_speed']:.4f}")
                report.append(f"  Cosine vs Temperature: {district_corr['cos_theta_wind_vs_temperature']:.4f}")
                report.append("")
        
        # Monthly analysis
        report.append("SEASONAL ANALYSIS")
        report.append("-" * 40)
        
        month_names = {6: "June", 7: "July", 8: "August", 9: "September"}
        
        for month_num, month_name in month_names.items():
            if month_num in correlations['by_month']:
                month_corr = correlations['by_month'][month_num]
                report.append(f"{month_name}:")
                report.append(f"  Cosine vs Vertical Pressure Velocity: {month_corr['cos_theta_wind_vs_omega']:.4f}")
                report.append(f"  Cosine vs Wind Speed: {month_corr['cos_theta_wind_vs_wind_speed']:.4f}")
                report.append("")
        
        # Key findings
        report.append("KEY FINDINGS")
        report.append("-" * 40)
        
        strongest_omega_corr = max(correlations['by_district'].items(), 
                                 key=lambda x: abs(x[1]['cos_theta_wind_vs_omega']) if not pd.isna(x[1]['cos_theta_wind_vs_omega']) else 0)
        
        report.append(f"Strongest cosine-omega correlation found in {district_names.get(strongest_omega_corr[0], strongest_omega_corr[0])} district")
        report.append(f"Correlation coefficient: {strongest_omega_corr[1]['cos_theta_wind_vs_omega']:.4f}")
        report.append("")
        
        # Statistical significance note
        report.append("NOTES")
        report.append("-" * 40)
        report.append("• This analysis uses sample meteorological data for demonstration")
        report.append("• For production use, integrate with actual ECMWF/GFS API data")
        report.append("• Correlations > 0.3 or < -0.3 may indicate significant relationships")
        report.append("• Consider statistical significance testing for robust conclusions")
        report.append("")
        
        return "\n".join(report)
    
    def save_analysis_results(self, cosine_data: pd.DataFrame, correlations: Dict, 
                            report: str, output_prefix: str = "kelp_meteo_analysis"):
        """Save analysis results to files"""
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Save detailed cosine data
        cosine_file = f"{output_prefix}_cosine_data_{timestamp}.csv"
        cosine_data.to_csv(cosine_file, index=False, encoding='utf-8')
        print(f"Saved cosine relationship data to: {cosine_file}")
        
        # Save correlations as JSON
        correlations_file = f"{output_prefix}_correlations_{timestamp}.json"
        with open(correlations_file, 'w', encoding='utf-8') as f:
            json.dump(correlations, f, indent=2, ensure_ascii=False)
        print(f"Saved correlation analysis to: {correlations_file}")
        
        # Save analysis report
        report_file = f"{output_prefix}_report_{timestamp}.txt"
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(report)
        print(f"Saved analysis report to: {report_file}")
        
        return cosine_file, correlations_file, report_file
    
    def run_complete_analysis(self, year: int = 2024) -> Tuple[pd.DataFrame, Dict, str]:
        """Run complete meteorological analysis for kelp season"""
        
        print("Starting comprehensive meteorological analysis for Rishiri Island kelp season...")
        print("=" * 80)
        
        # Get weather data (sample for demonstration)
        weather_data = self.get_sample_weather_data(year)
        
        # Calculate cosine relationships
        cosine_data = self.calculate_cosine_wind_theta_relationships(weather_data)
        
        # Analyze correlations
        correlations = self.analyze_correlations(cosine_data)
        
        # Generate report
        report = self.generate_analysis_report(correlations, cosine_data)
        
        # Save results
        files = self.save_analysis_results(cosine_data, correlations, report)
        
        print("=" * 80)
        print("ANALYSIS COMPLETE")
        print(f"Generated files: {files}")
        print("=" * 80)
        
        return cosine_data, correlations, report

def main():
    """Main execution function"""
    
    print("Rishiri Island Kelp Season Meteorological Analysis")
    print("Kelp Season Meteorological Analysis for Rishiri Island")
    print("=" * 60)
    print()
    
    analyzer = KelpSeasonMeteoAnalyzer()
    
    # Run complete analysis
    cosine_data, correlations, report = analyzer.run_complete_analysis(2024)
    
    # Display report (first 20 lines to avoid Unicode issues)
    print()
    print("ANALYSIS REPORT PREVIEW (first 20 lines):")
    print("-" * 50)
    report_lines = report.split('\n')
    for i, line in enumerate(report_lines[:20]):
        try:
            print(line)
        except UnicodeEncodeError:
            print(f"Line {i}: [Unicode content - see saved report file]")
    
    # Display sample of cosine data
    print("\nSAMPLE COSINE RELATIONSHIP DATA:")
    print("-" * 50)
    sample_data = cosine_data.head(10)[['date', 'hoshiba_name', 'district', 'hoshiba_theta', 
                                      'wind_direction', 'cos_theta_wind', 'vertical_pressure_velocity']]
    print(sample_data.to_string(index=False))

if __name__ == "__main__":
    main()