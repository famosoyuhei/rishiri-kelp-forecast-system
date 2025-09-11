#!/usr/bin/env python3
"""
Weather Verification for July 29, 2025
Verify fisherman testimony: Oshidomari cloudy, Kutsugata sunny, east wind
"""

import requests
import json

def get_weather_data(lat, lon, location_name):
    """Get weather data for specific location"""
    
    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": "2025-07-29",
        "end_date": "2025-07-29",
        "hourly": "temperature_2m,relative_humidity_2m,precipitation,wind_speed_10m,wind_direction_10m,cloud_cover,weather_code",
        "timezone": "Asia/Tokyo"
    }
    
    try:
        response = requests.get("https://api.open-meteo.com/v1/forecast", params=params, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            hourly = data["hourly"]
            
            # Work hours analysis (4-16)
            work_slice = slice(4, 17)
            
            return {
                "location": location_name,
                "cloud_cover_avg": sum(hourly["cloud_cover"][work_slice]) / 13,
                "wind_direction_avg": sum(hourly["wind_direction_10m"][work_slice]) / 13,
                "wind_speed_avg": sum(hourly["wind_speed_10m"][work_slice]) / 13,
                "humidity_avg": sum(hourly["relative_humidity_2m"][work_slice]) / 13,
                "hourly_data": hourly
            }
        else:
            print(f"Error {response.status_code} for {location_name}")
            return None
            
    except Exception as e:
        print(f"Error for {location_name}: {e}")
        return None

def analyze_wind_direction(degrees):
    """Convert wind direction to compass"""
    if 67.5 <= degrees <= 112.5:
        return "East"
    elif 22.5 <= degrees < 67.5:
        return "Northeast"  
    elif 112.5 < degrees <= 157.5:
        return "Southeast"
    else:
        return "Other"

def verify_testimony():
    """Verify fisherman testimony"""
    
    print("=== Weather Verification for July 29, 2025 ===")
    print("Testimony: Oshidomari cloudy, Kutsugata sunny, east wind")
    print()
    
    # Get weather data
    oshidomari = get_weather_data(45.241667, 141.230833, "Oshidomari")
    kutsugata = get_weather_data(45.118889, 141.176389, "Kutsugata")
    
    if not oshidomari or not kutsugata:
        print("Failed to get weather data")
        return
    
    print("WEATHER DATA RESULTS:")
    print("-" * 40)
    
    # Cloud cover analysis
    oshi_cloud = oshidomari["cloud_cover_avg"]
    kutsu_cloud = kutsugata["cloud_cover_avg"]
    
    print(f"Oshidomari: {oshi_cloud:.1f}% cloud cover")
    print(f"Kutsugata: {kutsu_cloud:.1f}% cloud cover")
    
    # Weather interpretation
    oshi_weather = "Cloudy" if oshi_cloud >= 50 else "Sunny"
    kutsu_weather = "Cloudy" if kutsu_cloud >= 50 else "Sunny"
    
    print(f"Oshidomari: {oshi_weather}")
    print(f"Kutsugata: {kutsu_weather}")
    
    # Wind analysis
    oshi_wind_dir = analyze_wind_direction(oshidomari["wind_direction_avg"])
    kutsu_wind_dir = analyze_wind_direction(kutsugata["wind_direction_avg"])
    
    print(f"Oshidomari wind: {oshi_wind_dir} ({oshidomari['wind_direction_avg']:.1f}°)")
    print(f"Kutsugata wind: {kutsu_wind_dir} ({kutsugata['wind_direction_avg']:.1f}°)")
    
    print("\nVERIFICATION RESULTS:")
    print("-" * 30)
    
    # Verify testimony
    testimony_weather = (oshi_weather == "Cloudy" and kutsu_weather == "Sunny")
    east_wind_detected = (oshi_wind_dir == "East" or kutsu_wind_dir == "East")
    
    print(f"Oshidomari cloudy: {'YES' if oshi_weather == 'Cloudy' else 'NO'}")
    print(f"Kutsugata sunny: {'YES' if kutsu_weather == 'Sunny' else 'NO'}")
    print(f"East wind detected: {'YES' if east_wind_detected else 'NO'}")
    
    verified_count = sum([
        oshi_weather == "Cloudy",
        kutsu_weather == "Sunny", 
        east_wind_detected
    ])
    
    print(f"\nTESTIMONY ACCURACY: {verified_count}/3 ({verified_count/3*100:.1f}%)")
    
    if verified_count >= 2:
        print("HIGH RELIABILITY - Fisherman testimony is largely accurate")
    elif verified_count == 1:
        print("MODERATE RELIABILITY - Fisherman testimony is partially accurate")
    else:
        print("LOW RELIABILITY - Fisherman testimony differs from weather data")
    
    # Additional analysis
    print(f"\nADDITIONAL ANALYSIS:")
    print(f"Oshidomari humidity: {oshidomari['humidity_avg']:.1f}%")
    print(f"Kutsugata humidity: {kutsugata['humidity_avg']:.1f}%")
    
    if east_wind_detected and max(oshidomari['humidity_avg'], kutsugata['humidity_avg']) > 75:
        print("YAMASE EFFECT CONFIRMED: East wind + high humidity")
        print("This would negatively impact kelp drying conditions")

if __name__ == "__main__":
    verify_testimony()