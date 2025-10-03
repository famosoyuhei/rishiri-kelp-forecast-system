#!/usr/bin/env python3
"""
Kelp Drying Forecast System for Rishiri Island
利尻島昆布干し予報システム

Integrates two key correlation models:
1. Wind direction vs moisture content (fishermen's knowledge validation)
2. Radial wind components vs cloud formation (orographic effects)

Provides actionable forecasts for optimal kelp drying conditions.
"""

import math
import csv
import numpy as np
import pandas as pd
import json
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional

# Geographic constants
RISHIRI_SAN_LAT = 45.1821
RISHIRI_SAN_LON = 141.2421
RISHIRI_SAN_ELEVATION = 1721  # meters
SOUTH_TOWN_BOUNDARY_LAT = 45.1007
SOUTH_TOWN_BOUNDARY_LON = 141.2461

class KelpDryingForecastSystem:
    """
    Integrated forecast system for kelp drying conditions
    昆布干し条件の統合予報システム
    """
    
    def __init__(self, hoshiba_csv='hoshiba_spots.csv'):
        self.hoshiba_csv = hoshiba_csv
        self.hoshiba_data = self.load_hoshiba_data()
        
        # Model parameters from previous analyses
        self.moisture_model_params = self.load_moisture_model_params()
        self.cloud_model_params = self.load_cloud_model_params()
        
    def load_hoshiba_data(self) -> pd.DataFrame:
        """Load hoshiba locations with theta calculations"""
        df = pd.read_csv(self.hoshiba_csv, encoding='utf-8')
        
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
        
        R = 6371  # Earth radius in kilometers
        lat1, lon1 = math.radians(RISHIRI_SAN_LAT), math.radians(RISHIRI_SAN_LON)
        lat2, lon2 = math.radians(lat), math.radians(lon)
        
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        
        a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
        c = 2 * math.asin(math.sqrt(a))
        
        return R * c
    
    def load_moisture_model_params(self) -> Dict:
        """Load moisture model parameters from wind-direction analysis"""
        return {
            'sector_humidity': {
                'WNW': 58.7,    # Driest
                'SSW': 61.2,
                'W': 68.5,
                'SW': 71.1,
                'S': 74.0,
                'SE': 74.5,
                'WSW': 75.6,
                'SSE': 89.7     # Wettest
            },
            'optimal_humidity_threshold': 60.0,
            'poor_humidity_threshold': 75.0
        }
    
    def load_cloud_model_params(self) -> Dict:
        """Load cloud formation model parameters"""
        return {
            'district_lifting': {
                'Kutsugata': 0.250,      # Strongest orographic lifting
                'Oshidomari': 0.240,
                'Senposhi': 0.230,
                'Oniwaki': 0.200
            },
            'max_effective_distance': 15.0,  # km
            'characteristic_length': 10000   # meters
        }
    
    def get_wind_direction_sector(self, wind_direction: float) -> str:
        """Convert wind direction to compass sector"""
        
        wind_direction = wind_direction % 360
        
        sectors = [
            (0, 22.5, "N"), (22.5, 67.5, "NE"), (67.5, 112.5, "E"), (112.5, 157.5, "SE"),
            (157.5, 202.5, "S"), (202.5, 247.5, "SW"), (247.5, 292.5, "W"), (292.5, 337.5, "NW"),
            (337.5, 360, "N")
        ]
        
        for min_deg, max_deg, sector in sectors:
            if min_deg <= wind_direction < max_deg:
                return sector
        
        return "N"
    
    def get_detailed_wind_sector(self, wind_direction: float) -> str:
        """Convert wind direction to 16-sector compass direction"""
        
        wind_direction = wind_direction % 360
        
        sectors = [
            (0, 11.25, "N"), (11.25, 33.75, "NNE"), (33.75, 56.25, "NE"), (56.25, 78.75, "ENE"),
            (78.75, 101.25, "E"), (101.25, 123.75, "ESE"), (123.75, 146.25, "SE"), (146.25, 168.75, "SSE"),
            (168.75, 191.25, "S"), (191.25, 213.75, "SSW"), (213.75, 236.25, "SW"), (236.25, 258.75, "WSW"),
            (258.75, 281.25, "W"), (281.25, 303.75, "WNW"), (303.75, 326.25, "NW"), (326.25, 348.75, "NNW"),
            (348.75, 360, "N")
        ]
        
        for min_deg, max_deg, sector in sectors:
            if min_deg <= wind_direction < max_deg:
                return sector
        
        return "N"
    
    def calculate_absolute_humidity(self, temperature: float, relative_humidity: float) -> float:
        """Calculate absolute humidity using Magnus formula"""
        
        # Magnus formula constants
        a = 17.27
        b = 237.7
        
        # Saturation vapor pressure (hPa)
        es = 6.112 * math.exp((a * temperature) / (b + temperature))
        
        # Actual vapor pressure (hPa)
        e = (relative_humidity / 100.0) * es
        
        # Absolute humidity using ideal gas law
        R_v = 461.5  # J/(kg·K) for water vapor
        T_kelvin = temperature + 273.15
        e_pa = e * 100  # Convert to Pa
        
        # Absolute humidity in kg/m³, then convert to g/m³
        absolute_humidity = (e_pa / (R_v * T_kelvin)) * 1000
        
        return absolute_humidity
    
    def calculate_vapor_pressure_deficit(self, temperature: float, relative_humidity: float) -> float:
        """Calculate vapor pressure deficit (VPD)"""
        
        a = 17.27
        b = 237.7
        
        # Saturation vapor pressure (hPa)
        es = 6.112 * math.exp((a * temperature) / (b + temperature))
        
        # Actual vapor pressure (hPa)  
        e = (relative_humidity / 100.0) * es
        
        # VPD = saturation - actual
        vpd = es - e
        
        return vpd
    
    def predict_moisture_by_wind_direction(self, wind_direction: float, 
                                         base_humidity: float) -> Dict:
        """Predict moisture conditions based on wind direction"""
        
        detailed_sector = self.get_detailed_wind_sector(wind_direction)
        
        # Get expected humidity for this wind sector
        expected_humidity = self.moisture_model_params['sector_humidity'].get(detailed_sector, base_humidity)
        
        # Calculate adjustment factor
        humidity_adjustment = expected_humidity - 70.0  # Base reference humidity
        adjusted_humidity = max(20, min(95, base_humidity + humidity_adjustment))
        
        # Determine moisture condition
        if adjusted_humidity <= self.moisture_model_params['optimal_humidity_threshold']:
            moisture_condition = "Optimal"
            moisture_score = 1.0
        elif adjusted_humidity <= self.moisture_model_params['poor_humidity_threshold']:
            moisture_condition = "Moderate"
            moisture_score = 0.6
        else:
            moisture_condition = "Poor"
            moisture_score = 0.3
        
        return {
            'wind_sector': detailed_sector,
            'expected_humidity': adjusted_humidity,
            'moisture_condition': moisture_condition,
            'moisture_score': moisture_score,
            'fishermen_knowledge': f"Wind from {detailed_sector}: Expected humidity {adjusted_humidity:.1f}%"
        }
    
    def calculate_radial_wind_component(self, wind_direction: float, wind_speed: float, 
                                      hoshiba_theta: float) -> float:
        """Calculate radial wind component towards/away from Rishiri-san"""
        
        # Convert to radians
        wind_dir_rad = math.radians(wind_direction)
        hoshiba_theta_rad = math.radians(hoshiba_theta)
        
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
    
    def estimate_orographic_effects(self, wind_direction: float, wind_speed: float,
                                  hoshiba_location: Dict) -> Dict:
        """Estimate orographic cloud formation effects for a specific hoshiba location"""
        
        theta = hoshiba_location['theta']
        distance = hoshiba_location['distance_from_rishiri_san']
        district = hoshiba_location['district']
        
        # Calculate radial wind component
        radial_wind = self.calculate_radial_wind_component(wind_direction, wind_speed, theta)
        
        # Estimate orographic lifting
        if radial_wind <= 0:
            lifting_velocity = 0.0
        else:
            max_distance = self.cloud_model_params['max_effective_distance']
            if distance > max_distance:
                lifting_velocity = 0.0
            else:
                distance_factor = (max_distance - distance) / max_distance
                mountain_height = RISHIRI_SAN_ELEVATION
                char_length = self.cloud_model_params['characteristic_length']
                
                lifting_velocity = (radial_wind * mountain_height * distance_factor) / char_length
                lifting_velocity = max(0, lifting_velocity)
        
        # Estimate cloud enhancement
        base_cloud_enhancement = lifting_velocity * 30  # Convert to cloud cover percentage
        
        # Determine cloud condition
        if lifting_velocity <= 0.1:
            cloud_condition = "Clear"
            cloud_score = 1.0
        elif lifting_velocity <= 0.3:
            cloud_condition = "Partly Cloudy"
            cloud_score = 0.7
        else:
            cloud_condition = "Cloudy"
            cloud_score = 0.4
        
        return {
            'radial_wind_component': radial_wind,
            'orographic_lifting': lifting_velocity,
            'cloud_enhancement': base_cloud_enhancement,
            'cloud_condition': cloud_condition,
            'cloud_score': cloud_score,
            'orographic_explanation': f"Radial wind: {radial_wind:.1f}m/s {'toward' if radial_wind > 0 else 'away from'} mountain"
        }
    
    def calculate_comprehensive_drying_score(self, weather_data: Dict, 
                                           hoshiba_location: Dict) -> Dict:
        """Calculate comprehensive drying score combining both models"""
        
        # Extract weather parameters
        wind_direction = weather_data['wind_direction']
        wind_speed = weather_data['wind_speed']
        temperature = weather_data['temperature']
        base_humidity = weather_data['humidity']
        
        # Model 1: Moisture prediction based on wind direction
        moisture_prediction = self.predict_moisture_by_wind_direction(wind_direction, base_humidity)
        
        # Model 2: Orographic effects prediction
        orographic_prediction = self.estimate_orographic_effects(wind_direction, wind_speed, hoshiba_location)
        
        # Calculate VPD with adjusted humidity
        adjusted_humidity = moisture_prediction['expected_humidity']
        vpd = self.calculate_vapor_pressure_deficit(temperature, adjusted_humidity)
        
        # Additional factors
        wind_score = min(1.0, max(0.2, (wind_speed - 1) / 8))  # Optimal wind 3-9 m/s
        temp_score = min(1.0, max(0.2, (temperature - 5) / 20))  # Optimal temp 10-25°C
        vpd_score = min(1.0, vpd / 10)  # Higher VPD = better drying
        
        # Comprehensive score (weighted average)
        weights = {
            'moisture': 0.35,
            'cloud': 0.25,
            'wind': 0.15,
            'temperature': 0.15,
            'vpd': 0.10
        }
        
        comprehensive_score = (
            weights['moisture'] * moisture_prediction['moisture_score'] +
            weights['cloud'] * orographic_prediction['cloud_score'] +
            weights['wind'] * wind_score +
            weights['temperature'] * temp_score +
            weights['vpd'] * vpd_score
        )
        
        # Determine overall condition
        if comprehensive_score >= 0.8:
            overall_condition = "Excellent"
        elif comprehensive_score >= 0.6:
            overall_condition = "Good"
        elif comprehensive_score >= 0.4:
            overall_condition = "Fair"
        else:
            overall_condition = "Poor"
        
        return {
            'comprehensive_score': comprehensive_score,
            'overall_condition': overall_condition,
            'moisture_prediction': moisture_prediction,
            'orographic_prediction': orographic_prediction,
            'weather_factors': {
                'adjusted_humidity': adjusted_humidity,
                'vpd': vpd,
                'wind_score': wind_score,
                'temp_score': temp_score,
                'vpd_score': vpd_score
            },
            'recommendations': self.generate_recommendations(comprehensive_score, moisture_prediction, orographic_prediction)
        }
    
    def generate_recommendations(self, score: float, moisture_pred: Dict, 
                               orographic_pred: Dict) -> List[str]:
        """Generate actionable recommendations based on predictions"""
        
        recommendations = []
        
        if score >= 0.8:
            recommendations.append("Excellent drying conditions! Proceed with confidence.")
        elif score >= 0.6:
            recommendations.append("Good drying conditions. Monitor weather closely.")
        elif score >= 0.4:
            recommendations.append("Fair conditions. Consider alternative locations or timing.")
        else:
            recommendations.append("Poor conditions. Avoid drying today if possible.")
        
        # Wind-direction specific advice
        if moisture_pred['moisture_condition'] == "Poor":
            recommendations.append(f"High humidity expected from {moisture_pred['wind_sector']} wind. Consider postponing.")
        elif moisture_pred['moisture_condition'] == "Optimal":
            recommendations.append(f"Low humidity from {moisture_pred['wind_sector']} wind - excellent for drying!")
        
        # Orographic advice
        if orographic_pred['radial_wind_component'] > 5:
            recommendations.append("Strong winds toward mountain may create clouds. Monitor sky conditions.")
        elif orographic_pred['radial_wind_component'] < -3:
            recommendations.append("Winds away from mountain - expect clearer skies on this side.")
        
        return recommendations
    
    def generate_location_specific_forecast(self, weather_data: Dict, 
                                          location_filter: str = None) -> pd.DataFrame:
        """Generate location-specific forecasts for all or selected hoshiba fields"""
        
        forecasts = []
        
        # Filter locations if specified
        if location_filter:
            filtered_locations = self.hoshiba_data[
                (self.hoshiba_data['district'].str.contains(location_filter, case=False, na=False)) |
                (self.hoshiba_data['town'].str.contains(location_filter, case=False, na=False)) |
                (self.hoshiba_data['buraku'].str.contains(location_filter, case=False, na=False))
            ]
        else:
            filtered_locations = self.hoshiba_data
        
        for _, location in filtered_locations.iterrows():
            hoshiba_location = {
                'theta': location['theta'],
                'distance_from_rishiri_san': location['distance_from_rishiri_san'],
                'district': location['district']
            }
            
            prediction = self.calculate_comprehensive_drying_score(weather_data, hoshiba_location)
            
            forecast_record = {
                'hoshiba_name': location['name'],
                'town': location['town'],
                'district': location['district'],
                'buraku': location['buraku'],
                'comprehensive_score': prediction['comprehensive_score'],
                'overall_condition': prediction['overall_condition'],
                'expected_humidity': prediction['weather_factors']['adjusted_humidity'],
                'wind_sector': prediction['moisture_prediction']['wind_sector'],
                'moisture_condition': prediction['moisture_prediction']['moisture_condition'],
                'cloud_condition': prediction['orographic_prediction']['cloud_condition'],
                'radial_wind': prediction['orographic_prediction']['radial_wind_component'],
                'vpd': prediction['weather_factors']['vpd'],
                'primary_recommendation': prediction['recommendations'][0] if prediction['recommendations'] else "Monitor conditions"
            }
            
            forecasts.append(forecast_record)
        
        forecast_df = pd.DataFrame(forecasts)
        forecast_df = forecast_df.sort_values('comprehensive_score', ascending=False)
        
        return forecast_df
    
    def generate_daily_forecast_report(self, weather_data: Dict, 
                                     date_str: str = None) -> str:
        """Generate a comprehensive daily forecast report"""
        
        if date_str is None:
            date_str = datetime.now().strftime("%Y-%m-%d")
        
        # Generate forecasts for all locations
        all_forecasts = self.generate_location_specific_forecast(weather_data)
        
        # Statistical summary
        excellent_count = len(all_forecasts[all_forecasts['overall_condition'] == 'Excellent'])
        good_count = len(all_forecasts[all_forecasts['overall_condition'] == 'Good'])
        fair_count = len(all_forecasts[all_forecasts['overall_condition'] == 'Fair'])
        poor_count = len(all_forecasts[all_forecasts['overall_condition'] == 'Poor'])
        
        # Best and worst locations
        best_locations = all_forecasts.head(5)
        worst_locations = all_forecasts.tail(5)
        
        # District summary
        district_summary = all_forecasts.groupby('district').agg({
            'comprehensive_score': 'mean',
            'expected_humidity': 'mean',
            'overall_condition': lambda x: x.mode().iloc[0] if len(x.mode()) > 0 else 'Unknown'
        }).round(2)
        
        # Generate report
        report = []
        report.append("=" * 80)
        report.append("RISHIRI ISLAND KELP DRYING FORECAST")
        report.append(f"Date: {date_str}")
        report.append("=" * 80)
        report.append("")
        
        # Weather summary
        report.append("WEATHER CONDITIONS")
        report.append("-" * 40)
        report.append(f"Wind: {weather_data['wind_direction']:.0f}° at {weather_data['wind_speed']:.1f} m/s")
        report.append(f"Temperature: {weather_data['temperature']:.1f}°C")
        report.append(f"Base Humidity: {weather_data['humidity']:.1f}%")
        report.append("")
        
        # Overall island conditions
        report.append("ISLAND-WIDE DRYING CONDITIONS")
        report.append("-" * 40)
        report.append(f"Excellent: {excellent_count} locations ({excellent_count/len(all_forecasts)*100:.1f}%)")
        report.append(f"Good: {good_count} locations ({good_count/len(all_forecasts)*100:.1f}%)")
        report.append(f"Fair: {fair_count} locations ({fair_count/len(all_forecasts)*100:.1f}%)")
        report.append(f"Poor: {poor_count} locations ({poor_count/len(all_forecasts)*100:.1f}%)")
        report.append("")
        
        # Best locations
        report.append("TOP 5 RECOMMENDED LOCATIONS")
        report.append("-" * 40)
        for i, (_, loc) in enumerate(best_locations.iterrows(), 1):
            report.append(f"{i}. {loc['hoshiba_name']} ({loc['district']})")
            report.append(f"   Score: {loc['comprehensive_score']:.2f} | Condition: {loc['overall_condition']}")
            report.append(f"   Humidity: {loc['expected_humidity']:.1f}% | {loc['moisture_condition']} moisture")
            report.append(f"   {loc['primary_recommendation']}")
            report.append("")
        
        # District summary
        report.append("DISTRICT SUMMARY")
        report.append("-" * 40)
        district_names = {"鬼脇": "Oniwaki", "鴛泊": "Oshidomari", "沓形": "Kutsugata", "仙法志": "Senposhi"}
        
        for district_jp, district_en in district_names.items():
            if district_jp in district_summary.index:
                stats = district_summary.loc[district_jp]
                report.append(f"{district_en} District ({district_jp}):")
                report.append(f"  Average Score: {stats['comprehensive_score']:.2f}")
                report.append(f"  Expected Humidity: {stats['expected_humidity']:.1f}%")
                report.append(f"  Typical Condition: {stats['overall_condition']}")
                report.append("")
        
        # Wind analysis
        wind_sector = self.get_detailed_wind_sector(weather_data['wind_direction'])
        expected_humidity = self.moisture_model_params['sector_humidity'].get(wind_sector, weather_data['humidity'])
        
        report.append("WIND DIRECTION ANALYSIS")
        report.append("-" * 40)
        report.append(f"Wind from {wind_sector}: Expected humidity {expected_humidity:.1f}%")
        
        if expected_humidity <= 60:
            report.append("✓ Favorable wind direction - Low humidity expected")
        elif expected_humidity >= 75:
            report.append("⚠ Unfavorable wind direction - High humidity expected")
        else:
            report.append("◯ Moderate wind direction - Average humidity expected")
        
        report.append("")
        
        # Worst locations (warning)
        if poor_count > 0:
            report.append("LOCATIONS TO AVOID TODAY")
            report.append("-" * 40)
            poor_locations = all_forecasts[all_forecasts['overall_condition'] == 'Poor'].head(3)
            for i, (_, loc) in enumerate(poor_locations.iterrows(), 1):
                report.append(f"{i}. {loc['hoshiba_name']} ({loc['district']})")
                report.append(f"   Reason: {loc['moisture_condition']} moisture, {loc['cloud_condition']} sky")
            report.append("")
        
        # General recommendations
        report.append("GENERAL RECOMMENDATIONS")
        report.append("-" * 40)
        
        if excellent_count + good_count >= len(all_forecasts) * 0.6:
            report.append("• Good day for kelp drying across most of the island")
            report.append("• Focus on top-rated locations for best results")
        elif fair_count >= len(all_forecasts) * 0.5:
            report.append("• Mixed conditions - choose locations carefully")
            report.append("• Monitor weather changes throughout the day")
        else:
            report.append("• Generally unfavorable conditions for drying")
            report.append("• Consider postponing or using only the best locations")
        
        report.append("")
        report.append("This forecast combines traditional fishermen's knowledge with")
        report.append("modern meteorological analysis for optimal kelp drying guidance.")
        report.append("")
        
        return "\n".join(report)
    
    def save_forecast_results(self, forecasts_df: pd.DataFrame, report: str,
                            weather_data: Dict, output_prefix: str = "kelp_drying_forecast"):
        """Save forecast results to files"""
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Save detailed forecasts
        forecast_file = f"{output_prefix}_detailed_{timestamp}.csv"
        forecasts_df.to_csv(forecast_file, index=False, encoding='utf-8')
        print(f"Saved detailed forecasts to: {forecast_file}")
        
        # Save forecast report
        report_file = f"{output_prefix}_report_{timestamp}.txt"
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(report)
        print(f"Saved forecast report to: {report_file}")
        
        # Save weather input data
        weather_file = f"{output_prefix}_weather_input_{timestamp}.json"
        with open(weather_file, 'w', encoding='utf-8') as f:
            json.dump(weather_data, f, indent=2, ensure_ascii=False)
        print(f"Saved weather input to: {weather_file}")
        
        return forecast_file, report_file, weather_file

def main():
    """Demonstration of the integrated forecast system"""
    
    print("Rishiri Island Kelp Drying Forecast System")
    print("Integration of Wind-Moisture and Orographic Cloud Models")
    print("=" * 70)
    print()
    
    # Initialize forecast system
    forecast_system = KelpDryingForecastSystem()
    
    # Example weather scenarios
    weather_scenarios = [
        {
            'name': "Optimal Conditions",
            'wind_direction': 295,  # WNW - dry wind
            'wind_speed': 6.5,
            'temperature': 18.0,
            'humidity': 55.0
        },
        {
            'name': "Poor Conditions",
            'wind_direction': 165,  # SSE - humid wind
            'wind_speed': 8.0,
            'temperature': 15.0,
            'humidity': 78.0
        },
        {
            'name': "Mixed Conditions",
            'wind_direction': 220,  # SW - moderate
            'wind_speed': 7.2,
            'temperature': 16.5,
            'humidity': 68.0
        }
    ]
    
    # Run forecasts for different scenarios
    for scenario in weather_scenarios:
        print(f"\nSCENARIO: {scenario['name']}")
        print("-" * 50)
        
        # Generate forecasts
        forecasts = forecast_system.generate_location_specific_forecast(scenario)
        
        # Generate report
        report = forecast_system.generate_daily_forecast_report(scenario, 
                                                              datetime.now().strftime("%Y-%m-%d"))
        
        # Display summary
        excellent_count = len(forecasts[forecasts['overall_condition'] == 'Excellent'])
        good_count = len(forecasts[forecasts['overall_condition'] == 'Good'])
        
        print(f"Weather: {scenario['wind_direction']:.0f}° at {scenario['wind_speed']:.1f}m/s, "
              f"{scenario['temperature']:.1f}°C, {scenario['humidity']:.1f}% RH")
        print(f"Results: {excellent_count} excellent, {good_count} good locations")
        
        # Show top 3 locations
        top_locations = forecasts.head(3)
        print("Top 3 locations:")
        for i, (_, loc) in enumerate(top_locations.iterrows(), 1):
            district_en = {"鬼脇": "Oniwaki", "鴛泊": "Oshidomari", "沓形": "Kutsugata", "仙法志": "Senposhi"}
            district_display = district_en.get(loc['district'], loc['district'])
            print(f"  {i}. {loc['hoshiba_name']} ({district_display}) - "
                  f"Score: {loc['comprehensive_score']:.2f}")
        
        # Save results for the optimal scenario
        if scenario['name'] == "Optimal Conditions":
            files = forecast_system.save_forecast_results(forecasts, report, scenario)
            print(f"\nSaved forecast files: {files}")

if __name__ == "__main__":
    main()