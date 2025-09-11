#!/usr/bin/env python3
"""
Cloud Formation Analysis for Rishiri Island
利尻島の雲形成分析システム

Analyzes cloud formation based on radial wind components causing forced ascent,
focusing on days with significant weather differences across the island.
風向の動径成分による強制上昇と雲形成の関係を分析し、
島内で大きく天気に差が出た日を中心に検証
"""

import math
import csv
import numpy as np
import pandas as pd
import json
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
import matplotlib.pyplot as plt

# Geographic constants
RISHIRI_SAN_LAT = 45.1821
RISHIRI_SAN_LON = 141.2421
RISHIRI_SAN_ELEVATION = 1721  # meters
SOUTH_TOWN_BOUNDARY_LAT = 45.1007
SOUTH_TOWN_BOUNDARY_LON = 141.2461

class CloudFormationAnalyzer:
    """
    Analyzes cloud formation patterns based on radial wind components
    動径風成分による雲形成パターンの分析
    """
    
    def __init__(self, csv_file='hoshiba_spots.csv'):
        self.csv_file = csv_file
        self.hoshiba_data = self.load_hoshiba_data()
        
    def load_hoshiba_data(self) -> pd.DataFrame:
        """Load hoshiba data with theta and distance from Rishiri-san"""
        print("Loading hoshiba data for cloud formation analysis...")
        
        df = pd.read_csv(self.csv_file, encoding='utf-8')
        
        # Calculate theta and distance for each field
        theta_values = []
        distances = []
        
        for _, row in df.iterrows():
            theta = self.calculate_boundary_based_theta(row['lat'], row['lon'])
            distance = self.calculate_distance_from_rishiri_san(row['lat'], row['lon'])
            theta_values.append(theta)
            distances.append(distance)
        
        df['theta'] = theta_values
        df['distance_from_rishiri_san'] = distances
        
        print(f"Loaded {len(df)} hoshiba fields with theta and distance calculations")
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
    
    def calculate_distance_from_rishiri_san(self, lat: float, lon: float) -> float:
        """Calculate distance from Rishiri-san in kilometers"""
        
        # Using haversine formula for accurate distance calculation
        R = 6371  # Earth radius in kilometers
        
        lat1, lon1 = math.radians(RISHIRI_SAN_LAT), math.radians(RISHIRI_SAN_LON)
        lat2, lon2 = math.radians(lat), math.radians(lon)
        
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        
        a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
        c = 2 * math.asin(math.sqrt(a))
        
        return R * c
    
    def calculate_radial_wind_component(self, wind_direction: float, wind_speed: float, 
                                      hoshiba_theta: float) -> float:
        """
        Calculate radial wind component towards/away from Rishiri-san
        利尻山に向かう/離れる動径風成分を計算
        
        Positive values: wind blowing towards Rishiri-san (convergence, uplift)
        Negative values: wind blowing away from Rishiri-san (divergence, subsidence)
        """
        
        # Convert to radians
        wind_dir_rad = math.radians(wind_direction)
        hoshiba_theta_rad = math.radians(hoshiba_theta)
        
        # Angle difference between wind direction and radial direction to Rishiri-san
        # Radial direction to Rishiri-san is opposite to hoshiba theta
        radial_to_rishiri = hoshiba_theta_rad + math.pi
        
        # Normalize to [0, 2π]
        while radial_to_rishiri >= 2 * math.pi:
            radial_to_rishiri -= 2 * math.pi
        
        # Calculate angle difference
        angle_diff = wind_dir_rad - radial_to_rishiri
        
        # Normalize to [-π, π]
        while angle_diff > math.pi:
            angle_diff -= 2 * math.pi
        while angle_diff < -math.pi:
            angle_diff += 2 * math.pi
        
        # Radial component (positive = towards Rishiri-san)
        radial_component = wind_speed * math.cos(angle_diff)
        
        return radial_component
    
    def estimate_orographic_lift(self, radial_wind_component: float, 
                                distance_from_mountain: float) -> float:
        """
        Estimate orographic lifting based on radial wind component and terrain
        地形による強制上昇の推定
        """
        
        if radial_wind_component <= 0:
            return 0.0  # No lifting if wind is not towards the mountain
        
        # Simple orographic lifting model
        # Stronger lifting closer to mountain and with stronger radial winds
        max_distance = 15.0  # km - maximum effective distance for orographic effects
        
        if distance_from_mountain > max_distance:
            return 0.0
        
        # Distance factor (stronger closer to mountain)
        distance_factor = (max_distance - distance_from_mountain) / max_distance
        
        # Lifting velocity estimation (m/s)
        # Based on simplified orographic lifting equations
        mountain_height = RISHIRI_SAN_ELEVATION  # meters
        characteristic_length = 10000  # meters (10 km)
        
        # Simplified Scorer parameter approach
        lifting_velocity = (radial_wind_component * mountain_height * distance_factor) / characteristic_length
        
        return max(0, lifting_velocity)
    
    def estimate_cloud_probability(self, lifting_velocity: float, 
                                 temperature: float, humidity: float, 
                                 pressure: float) -> float:
        """
        Estimate cloud formation probability based on lifting and atmospheric conditions
        大気条件と上昇流に基づく雲形成確率の推定
        """
        
        if lifting_velocity <= 0:
            return 0.0
        
        # Basic cloud formation model
        # Higher probability with:
        # - Stronger lifting
        # - Higher humidity
        # - Lower temperature (for condensation)
        # - Appropriate pressure levels
        
        # Lifting factor (0-1)
        max_lifting = 2.0  # m/s
        lifting_factor = min(1.0, lifting_velocity / max_lifting)
        
        # Humidity factor (0-1)
        humidity_threshold = 60.0  # %
        humidity_factor = max(0, (humidity - humidity_threshold) / (100 - humidity_threshold))
        
        # Temperature factor (higher probability at moderate temperatures)
        optimal_temp = 10.0  # °C for summer cloud formation
        temp_range = 15.0  # °C
        temp_factor = max(0, 1 - abs(temperature - optimal_temp) / temp_range)
        
        # Pressure factor (normalized around sea level)
        pressure_factor = min(1.0, pressure / 1013.25)
        
        # Combined probability (geometric mean for realistic behavior)
        cloud_probability = (lifting_factor * humidity_factor * temp_factor * pressure_factor) ** 0.25
        
        return cloud_probability
    
    def generate_weather_scenarios_with_contrasts(self, year: int = 2024) -> Dict:
        """
        Generate weather scenarios emphasizing days with significant island-wide contrasts
        島内で大きく天気差が出る日を重点的に含む気象シナリオ生成
        """
        print(f"Generating weather scenarios with significant contrasts for {year}...")
        
        # Create scenarios for the kelp season (June-September)
        start_date = datetime(year, 6, 1)
        end_date = datetime(year, 9, 30)
        current_date = start_date
        
        scenarios = {
            'location': {'lat': RISHIRI_SAN_LAT, 'lon': RISHIRI_SAN_LON},
            'scenarios': []
        }
        
        scenario_types = [
            'uniform_clear',      # 全島晴れ
            'uniform_cloudy',     # 全島曇り
            'windward_clouds',    # 風上側雲形成
            'lee_side_clear',     # 風下側晴れ
            'rotating_wind',      # 風向変化による雲の移動
            'strong_contrast'     # 強いコントラスト日
        ]
        
        while current_date <= end_date:
            day_of_year = current_date.timetuple().tm_yday
            
            # Determine scenario type (emphasize contrast days)
            if day_of_year % 7 == 0:  # Every 7th day is strong contrast
                scenario_type = 'strong_contrast'
            elif day_of_year % 5 == 0:  # Every 5th day has some contrast
                scenario_type = np.random.choice(['windward_clouds', 'lee_side_clear', 'rotating_wind'])
            else:
                scenario_type = np.random.choice(['uniform_clear', 'uniform_cloudy', 'windward_clouds'])
            
            # Generate weather based on scenario type
            weather_scenario = self.generate_daily_weather_scenario(current_date, scenario_type)
            scenarios['scenarios'].append(weather_scenario)
            
            current_date += timedelta(days=1)
        
        print(f"Generated {len(scenarios['scenarios'])} weather scenarios")
        return scenarios
    
    def generate_daily_weather_scenario(self, date: datetime, scenario_type: str) -> Dict:
        """Generate detailed weather scenario for a specific day and type"""
        
        day_of_year = date.timetuple().tm_yday
        base_temp = 15 + 8 * math.sin(2 * math.pi * (day_of_year - 150) / 365)
        
        if scenario_type == 'uniform_clear':
            wind_direction = np.random.uniform(0, 360)
            wind_speed = np.random.uniform(2, 6)
            cloud_cover = np.random.uniform(0, 20)
            humidity = np.random.uniform(40, 65)
            
        elif scenario_type == 'uniform_cloudy':
            wind_direction = np.random.uniform(0, 360)
            wind_speed = np.random.uniform(3, 8)
            cloud_cover = np.random.uniform(70, 100)
            humidity = np.random.uniform(75, 95)
            
        elif scenario_type == 'windward_clouds':
            # Strong wind from specific direction causing orographic clouds
            wind_direction = np.random.choice([45, 135, 225, 315])  # From cardinal directions
            wind_speed = np.random.uniform(8, 15)
            cloud_cover = np.random.uniform(60, 90)
            humidity = np.random.uniform(70, 90)
            
        elif scenario_type == 'lee_side_clear':
            # Wind creates clear conditions on lee side
            wind_direction = np.random.choice([0, 90, 180, 270])
            wind_speed = np.random.uniform(6, 12)
            cloud_cover = np.random.uniform(20, 50)
            humidity = np.random.uniform(45, 70)
            
        elif scenario_type == 'rotating_wind':
            # Wind direction changes during day
            base_direction = np.random.uniform(0, 360)
            wind_direction = (base_direction + 30 * math.sin(2 * math.pi * day_of_year / 10)) % 360
            wind_speed = np.random.uniform(5, 10)
            cloud_cover = np.random.uniform(30, 70)
            humidity = np.random.uniform(60, 80)
            
        elif scenario_type == 'strong_contrast':
            # Conditions that create maximum weather contrast across island
            wind_direction = np.random.choice([30, 60, 120, 150, 210, 240, 300, 330])
            wind_speed = np.random.uniform(10, 18)
            cloud_cover = np.random.uniform(40, 80)
            humidity = np.random.uniform(65, 85)
        
        else:
            # Default case
            wind_direction = np.random.uniform(0, 360)
            wind_speed = np.random.uniform(3, 8)
            cloud_cover = np.random.uniform(20, 80)
            humidity = np.random.uniform(50, 80)
        
        return {
            'date': date.strftime('%Y-%m-%d'),
            'scenario_type': scenario_type,
            'wind_direction': round(wind_direction, 1),
            'wind_speed': round(wind_speed, 2),
            'base_cloud_cover': round(cloud_cover, 1),
            'temperature': round(base_temp + np.random.normal(0, 3), 1),
            'humidity': round(humidity, 1),
            'pressure': round(1013 + np.random.normal(0, 10), 1),
            'vertical_pressure_velocity': round(np.random.normal(0, 0.02), 6)
        }
    
    def analyze_cloud_formation_by_location(self, weather_scenarios: Dict) -> pd.DataFrame:
        """
        Analyze cloud formation probability for each hoshiba location
        各干場位置での雲形成確率分析
        """
        print("Analyzing cloud formation patterns by hoshiba location...")
        
        results = []
        
        for scenario in weather_scenarios['scenarios']:
            date = scenario['date']
            scenario_type = scenario['scenario_type']
            wind_dir = scenario['wind_direction']
            wind_speed = scenario['wind_speed']
            base_cloud_cover = scenario['base_cloud_cover']
            temperature = scenario['temperature']
            humidity = scenario['humidity']
            pressure = scenario['pressure']
            
            for _, hoshiba in self.hoshiba_data.iterrows():
                # Calculate radial wind component
                radial_wind = self.calculate_radial_wind_component(
                    wind_dir, wind_speed, hoshiba['theta']
                )
                
                # Estimate orographic lifting
                lifting = self.estimate_orographic_lift(
                    radial_wind, hoshiba['distance_from_rishiri_san']
                )
                
                # Estimate cloud probability
                cloud_prob = self.estimate_cloud_probability(
                    lifting, temperature, humidity, pressure
                )
                
                # Calculate actual cloud cover (base + orographic enhancement)
                orographic_enhancement = lifting * 30  # Convert lifting to cloud cover enhancement
                actual_cloud_cover = min(100, base_cloud_cover + orographic_enhancement)
                
                result = {
                    'date': date,
                    'scenario_type': scenario_type,
                    'hoshiba_name': hoshiba['name'],
                    'town': hoshiba['town'],
                    'district': hoshiba['district'],
                    'buraku': hoshiba['buraku'],
                    'theta': hoshiba['theta'],
                    'distance_from_rishiri_san': hoshiba['distance_from_rishiri_san'],
                    'wind_direction': wind_dir,
                    'wind_speed': wind_speed,
                    'radial_wind_component': radial_wind,
                    'orographic_lifting': lifting,
                    'cloud_formation_probability': cloud_prob,
                    'base_cloud_cover': base_cloud_cover,
                    'actual_cloud_cover': actual_cloud_cover,
                    'temperature': temperature,
                    'humidity': humidity,
                    'pressure': pressure
                }
                
                results.append(result)
        
        df = pd.DataFrame(results)
        print(f"Analyzed {len(df)} cloud formation scenarios (hoshiba x days)")
        return df
    
    def identify_high_contrast_days(self, cloud_data: pd.DataFrame, 
                                  contrast_threshold: float = 30.0) -> pd.DataFrame:
        """
        Identify days with significant weather contrasts across the island
        島内で大きく天気差が出た日の特定
        """
        print(f"Identifying days with cloud cover contrast > {contrast_threshold}%...")
        
        # Calculate daily statistics
        daily_stats = cloud_data.groupby('date').agg({
            'actual_cloud_cover': ['min', 'max', 'mean', 'std'],
            'cloud_formation_probability': ['min', 'max', 'mean', 'std'],
            'radial_wind_component': ['min', 'max', 'mean', 'std'],
            'scenario_type': 'first',
            'wind_direction': 'first',
            'wind_speed': 'first'
        }).round(2)
        
        # Flatten column names
        daily_stats.columns = ['_'.join(col).strip() for col in daily_stats.columns]
        daily_stats = daily_stats.reset_index()
        
        # Calculate cloud cover contrast (max - min)
        daily_stats['cloud_cover_contrast'] = (
            daily_stats['actual_cloud_cover_max'] - daily_stats['actual_cloud_cover_min']
        )
        
        # Filter high contrast days
        high_contrast_days = daily_stats[
            daily_stats['cloud_cover_contrast'] >= contrast_threshold
        ].sort_values('cloud_cover_contrast', ascending=False)
        
        print(f"Found {len(high_contrast_days)} high contrast days")
        return high_contrast_days
    
    def analyze_contrast_patterns(self, cloud_data: pd.DataFrame, 
                                high_contrast_days: pd.DataFrame) -> Dict:
        """
        Analyze patterns in high contrast days
        高コントラスト日のパターン分析
        """
        print("Analyzing patterns in high contrast weather days...")
        
        patterns = {}
        
        # Filter data for high contrast days only
        contrast_dates = high_contrast_days['date'].tolist()
        contrast_data = cloud_data[cloud_data['date'].isin(contrast_dates)]
        
        # Analyze by wind direction
        wind_direction_analysis = {}
        for date in contrast_dates:
            day_data = contrast_data[contrast_data['date'] == date]
            wind_dir = day_data['wind_direction'].iloc[0]
            
            # Group by theta ranges to see spatial patterns
            day_data = day_data.copy()
            day_data['theta_range'] = pd.cut(day_data['theta'], 
                                           bins=[0, 90, 180, 270, 360], 
                                           labels=['0-90°', '90-180°', '180-270°', '270-360°'])
            
            theta_cloud_stats = day_data.groupby('theta_range', observed=True)['actual_cloud_cover'].agg(['mean', 'min', 'max'])
            
            wind_direction_analysis[date] = {
                'wind_direction': wind_dir,
                'theta_cloud_stats': theta_cloud_stats.to_dict()
            }
        
        patterns['wind_direction_analysis'] = wind_direction_analysis
        
        # Analyze by district
        district_patterns = contrast_data.groupby(['date', 'district']).agg({
            'actual_cloud_cover': ['mean', 'std'],
            'radial_wind_component': 'mean',
            'orographic_lifting': 'mean'
        }).round(3)
        
        # Convert to JSON-serializable format
        district_patterns_dict = {}
        for (date, district), values in district_patterns.iterrows():
            key = f"{date}_{district}"
            district_patterns_dict[key] = {
                'date': date,
                'district': district,
                'cloud_cover_mean': values[('actual_cloud_cover', 'mean')],
                'cloud_cover_std': values[('actual_cloud_cover', 'std')],
                'radial_wind_mean': values[('radial_wind_component', 'mean')],
                'orographic_lifting_mean': values[('orographic_lifting', 'mean')]
            }
        
        patterns['district_patterns'] = district_patterns_dict
        
        # Overall statistics
        patterns['overall_stats'] = {
            'total_high_contrast_days': len(high_contrast_days),
            'average_contrast': high_contrast_days['cloud_cover_contrast'].mean(),
            'max_contrast': high_contrast_days['cloud_cover_contrast'].max(),
            'most_common_scenario_types': high_contrast_days['scenario_type_first'].value_counts().to_dict()
        }
        
        return patterns
    
    def generate_cloud_analysis_report(self, cloud_data: pd.DataFrame, 
                                     high_contrast_days: pd.DataFrame,
                                     patterns: Dict) -> str:
        """Generate comprehensive cloud formation analysis report"""
        
        report = []
        report.append("=" * 80)
        report.append("RISHIRI ISLAND CLOUD FORMATION ANALYSIS REPORT")
        report.append("Cloud Formation Analysis Based on Radial Wind Components")
        report.append("=" * 80)
        report.append("")
        
        # Summary statistics
        report.append("SUMMARY STATISTICS")
        report.append("-" * 40)
        report.append(f"Total analysis days: {cloud_data['date'].nunique()}")
        report.append(f"Total hoshiba locations: {cloud_data['hoshiba_name'].nunique()}")
        report.append(f"High contrast days (>30% cloud difference): {len(high_contrast_days)}")
        report.append(f"Average island-wide cloud cover: {cloud_data['actual_cloud_cover'].mean():.1f}%")
        report.append(f"Maximum daily contrast: {high_contrast_days['cloud_cover_contrast'].max():.1f}%")
        report.append("")
        
        # High contrast day analysis
        report.append("HIGH CONTRAST DAYS ANALYSIS")
        report.append("-" * 40)
        
        top_contrast_days = high_contrast_days.head(5)
        report.append("Top 5 highest contrast days:")
        for _, day in top_contrast_days.iterrows():
            report.append(f"  {day['date']}: {day['cloud_cover_contrast']:.1f}% contrast")
            report.append(f"    Scenario: {day['scenario_type_first']}, Wind: {day['wind_direction_first']:.0f}deg at {day['wind_speed_first']:.1f}m/s")
        report.append("")
        
        # Scenario type analysis
        report.append("WEATHER SCENARIO EFFECTIVENESS")
        report.append("-" * 40)
        scenario_stats = cloud_data.groupby('scenario_type').agg({
            'actual_cloud_cover': ['mean', 'std'],
            'cloud_formation_probability': 'mean',
            'radial_wind_component': ['mean', 'std']
        }).round(2)
        
        for scenario in scenario_stats.index:
            cloud_mean = scenario_stats.loc[scenario, ('actual_cloud_cover', 'mean')]
            cloud_std = scenario_stats.loc[scenario, ('actual_cloud_cover', 'std')]
            report.append(f"{scenario}: {cloud_mean:.1f}% ± {cloud_std:.1f}% cloud cover")
        report.append("")
        
        # District-level analysis
        report.append("DISTRICT-LEVEL CLOUD PATTERNS")
        report.append("-" * 40)
        
        district_names = {"鬼脇": "Oniwaki", "鴛泊": "Oshidomari", "沓形": "Kutsugata", "仙法志": "Senposhi"}
        district_stats = cloud_data.groupby('district').agg({
            'actual_cloud_cover': 'mean',
            'orographic_lifting': 'mean',
            'radial_wind_component': 'mean'
        }).round(2)
        
        for district_jp, district_en in district_names.items():
            if district_jp in district_stats.index:
                stats = district_stats.loc[district_jp]
                report.append(f"{district_en} District:")
                report.append(f"  Average cloud cover: {stats['actual_cloud_cover']:.1f}%")
                report.append(f"  Average orographic lifting: {stats['orographic_lifting']:.3f} m/s")
                report.append(f"  Average radial wind component: {stats['radial_wind_component']:.2f} m/s")
                report.append("")
        
        # Key findings
        report.append("KEY FINDINGS")
        report.append("-" * 40)
        
        # Find district with strongest orographic effects
        max_lifting_district = district_stats['orographic_lifting'].idxmax()
        max_lifting_value = district_stats.loc[max_lifting_district, 'orographic_lifting']
        
        report.append(f"Strongest orographic lifting in {district_names.get(max_lifting_district, max_lifting_district)} district")
        report.append(f"Average lifting velocity: {max_lifting_value:.3f} m/s")
        report.append("")
        
        # Wind direction correlation
        wind_cloud_corr = cloud_data['wind_direction'].corr(cloud_data['actual_cloud_cover'])
        report.append(f"Wind direction vs cloud cover correlation: {wind_cloud_corr:.3f}")
        
        radial_cloud_corr = cloud_data['radial_wind_component'].corr(cloud_data['actual_cloud_cover'])
        report.append(f"Radial wind component vs cloud cover correlation: {radial_cloud_corr:.3f}")
        report.append("")
        
        # Recommendations
        report.append("RECOMMENDATIONS FOR KELP DRYING")
        report.append("-" * 40)
        report.append("• Monitor wind direction forecasts for orographic cloud prediction")
        report.append("• Fields with strong radial wind components may experience more clouds")
        report.append("• High contrast days offer opportunities for location-specific drying")
        report.append("• Consider district-specific drying strategies based on typical patterns")
        report.append("")
        
        return "\n".join(report)
    
    def save_cloud_analysis_results(self, cloud_data: pd.DataFrame, 
                                  high_contrast_days: pd.DataFrame,
                                  patterns: Dict, report: str,
                                  output_prefix: str = "cloud_formation_analysis"):
        """Save cloud formation analysis results"""
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Save detailed cloud data
        cloud_file = f"{output_prefix}_data_{timestamp}.csv"
        cloud_data.to_csv(cloud_file, index=False, encoding='utf-8')
        print(f"Saved cloud formation data to: {cloud_file}")
        
        # Save high contrast days
        contrast_file = f"{output_prefix}_high_contrast_days_{timestamp}.csv"
        high_contrast_days.to_csv(contrast_file, index=False, encoding='utf-8')
        print(f"Saved high contrast days to: {contrast_file}")
        
        # Save patterns analysis
        patterns_file = f"{output_prefix}_patterns_{timestamp}.json"
        with open(patterns_file, 'w', encoding='utf-8') as f:
            json.dump(patterns, f, indent=2, ensure_ascii=False, default=str)
        print(f"Saved pattern analysis to: {patterns_file}")
        
        # Save analysis report
        report_file = f"{output_prefix}_report_{timestamp}.txt"
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(report)
        print(f"Saved analysis report to: {report_file}")
        
        return cloud_file, contrast_file, patterns_file, report_file
    
    def run_complete_cloud_analysis(self, year: int = 2024) -> Tuple[pd.DataFrame, pd.DataFrame, Dict, str]:
        """Run complete cloud formation analysis"""
        
        print("Starting comprehensive cloud formation analysis for Rishiri Island...")
        print("=" * 80)
        
        # Generate weather scenarios with contrasts
        weather_scenarios = self.generate_weather_scenarios_with_contrasts(year)
        
        # Analyze cloud formation by location
        cloud_data = self.analyze_cloud_formation_by_location(weather_scenarios)
        
        # Identify high contrast days
        high_contrast_days = self.identify_high_contrast_days(cloud_data)
        
        # Analyze patterns
        patterns = self.analyze_contrast_patterns(cloud_data, high_contrast_days)
        
        # Generate report
        report = self.generate_cloud_analysis_report(cloud_data, high_contrast_days, patterns)
        
        # Save results
        files = self.save_cloud_analysis_results(cloud_data, high_contrast_days, patterns, report)
        
        print("=" * 80)
        print("CLOUD FORMATION ANALYSIS COMPLETE")
        print(f"Generated files: {files}")
        print("=" * 80)
        
        return cloud_data, high_contrast_days, patterns, report

def main():
    """Main execution function"""
    
    print("Rishiri Island Cloud Formation Analysis")
    print("Radial Wind Component and Orographic Cloud Analysis")
    print("=" * 60)
    print()
    
    analyzer = CloudFormationAnalyzer()
    
    # Run complete analysis
    cloud_data, high_contrast_days, patterns, report = analyzer.run_complete_cloud_analysis(2024)
    
    # Display report preview
    print()
    print("ANALYSIS REPORT PREVIEW:")
    print("-" * 50)
    report_lines = report.split('\n')
    for i, line in enumerate(report_lines[:25]):
        try:
            print(line)
        except UnicodeEncodeError:
            print(f"Line {i}: [Unicode content - see saved report file]")
    
    # Display sample high contrast days
    print("\nHIGH CONTRAST DAYS SAMPLE:")
    print("-" * 50)
    print(high_contrast_days.head(3)[['date', 'cloud_cover_contrast', 'scenario_type_first', 'wind_direction_first']].to_string(index=False))

if __name__ == "__main__":
    main()