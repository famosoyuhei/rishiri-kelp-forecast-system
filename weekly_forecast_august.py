#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
7-day Weather Forecast Script
Get forecast data for H_1631_1434 and H_2065_1368 from August 24-30
"""

import requests
import json
from datetime import datetime, timedelta
import pandas as pd
import sys

# Set UTF-8 encoding for Windows
if sys.platform.startswith('win'):
    import os
    os.system('chcp 65001 > nul')

# Location coordinates
locations = {
    'H_1631_1434': {'lat': 45.1631035, 'lon': 141.1434784, 'name': 'Kamui'},
    'H_2065_1368': {'lat': 45.2065164, 'lon': 141.1369002, 'name': 'Shinminato'}  # Using closest coordinates
}

def get_weather_forecast(lat, lon, start_date, end_date):
    """Get weather forecast data from Open-Meteo API"""
    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": start_date,
        "end_date": end_date,
        "hourly": "temperature_2m,relative_humidity_2m,wind_speed_10m,wind_direction_10m,shortwave_radiation,cloud_cover,precipitation,precipitation_probability",
        "daily": "temperature_2m_max,temperature_2m_min,wind_speed_10m_max,precipitation_sum,precipitation_probability_max",
        "timezone": "Asia/Tokyo"
    }
    
    try:
        response = requests.get("https://api.open-meteo.com/v1/forecast", params=params, timeout=10)
        if response.status_code == 200:
            return response.json()
        else:
            print(f"API Error: {response.status_code}")
            return None
    except Exception as e:
        print(f"Request Error: {e}")
        return None

def main():
    # 7 days from August 24 to 30
    start_date = "2025-08-24"
    end_date = "2025-08-30"
    
    print("=" * 80)
    print(f"7-day Weather Forecast Data ({start_date} - {end_date})")
    print(f"Retrieved at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)
    
    # Get forecast data for each location
    forecast_data = {}
    
    for location_id, coords in locations.items():
        print(f"\nFetching forecast data for {location_id} ({coords['name']})...")
        print(f"Latitude: {coords['lat']}, Longitude: {coords['lon']}")
        
        data = get_weather_forecast(coords['lat'], coords['lon'], start_date, end_date)
        
        if data and 'daily' in data:
            forecast_data[location_id] = {
                'coords': coords,
                'daily': data['daily'],
                'hourly': data['hourly']
            }
            print(f"Success: {location_id} data retrieved")
        else:
            print(f"Failed: {location_id} data not available")
    
    # Display results in table format
    print("\n" + "=" * 100)
    print("7-day Weather Forecast Data (Daily Summary)")
    print("=" * 100)
    
    if forecast_data:
        # Create date list
        dates = []
        base_date = datetime.strptime(start_date, "%Y-%m-%d")
        for i in range(7):
            dates.append((base_date + timedelta(days=i)).strftime("%m/%d"))
        
        print(f"{'Location':15} {'Date':>10} {'Max Temp':>8} {'Min Temp':>8} {'Max Wind':>8} {'Precip.':>8} {'Rain %':>8}")
        print("-" * 100)
        
        for location_id, data in forecast_data.items():
            coords = data['coords']
            daily = data['daily']
            
            for i, date_str in enumerate(dates):
                if i < len(daily['time']):
                    max_temp = daily['temperature_2m_max'][i] if daily['temperature_2m_max'][i] is not None else 0
                    min_temp = daily['temperature_2m_min'][i] if daily['temperature_2m_min'][i] is not None else 0
                    max_wind = daily['wind_speed_10m_max'][i] if daily['wind_speed_10m_max'][i] is not None else 0
                    precip = daily['precipitation_sum'][i] if daily['precipitation_sum'][i] is not None else 0
                    precip_prob = daily['precipitation_probability_max'][i] if daily['precipitation_probability_max'][i] is not None else 0
                    
                    location_name = f"{location_id}" if i == 0 else ""
                    
                    print(f"{location_name:15} {date_str:>10} {max_temp:>7.1f}C {min_temp:>7.1f}C {max_wind:>7.1f}m/s {precip:>7.1f}mm {precip_prob:>7.0f}%")
                else:
                    print(f"{location_id if i == 0 else '':15} {date_str:>10} {'No Data':>50}")
    
    # Save detailed hourly data to CSV
    print("\nSaving detailed hourly data to CSV file...")
    
    detailed_data = []
    for location_id, data in forecast_data.items():
        coords = data['coords']
        hourly = data['hourly']
        
        if 'time' in hourly:
            for i, time_str in enumerate(hourly['time']):
                try:
                    dt = datetime.fromisoformat(time_str.replace('T', ' '))
                    
                    detailed_data.append({
                        'LocationID': location_id,
                        'LocationName': coords['name'],
                        'Latitude': coords['lat'],
                        'Longitude': coords['lon'],
                        'DateTime': dt.strftime('%Y-%m-%d %H:%M'),
                        'Date': dt.strftime('%m/%d'),
                        'Time': dt.strftime('%H:%M'),
                        'Temperature': hourly['temperature_2m'][i] if i < len(hourly['temperature_2m']) else None,
                        'Humidity': hourly['relative_humidity_2m'][i] if i < len(hourly['relative_humidity_2m']) else None,
                        'WindSpeed': hourly['wind_speed_10m'][i] if i < len(hourly['wind_speed_10m']) else None,
                        'WindDirection': hourly['wind_direction_10m'][i] if i < len(hourly['wind_direction_10m']) else None,
                        'SolarRadiation': hourly['shortwave_radiation'][i] if i < len(hourly['shortwave_radiation']) else None,
                        'CloudCover': hourly['cloud_cover'][i] if i < len(hourly['cloud_cover']) else None,
                        'Precipitation': hourly['precipitation'][i] if i < len(hourly['precipitation']) else None,
                        'PrecipitationProbability': hourly['precipitation_probability'][i] if i < len(hourly['precipitation_probability']) else None
                    })
                except Exception as e:
                    print(f"Time data processing error: {e}")
                    continue
    
    if detailed_data:
        df = pd.DataFrame(detailed_data)
        csv_filename = f"forecast_data_august24-30_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
        df.to_csv(csv_filename, index=False, encoding='utf-8-sig')
        print(f"Success: Detailed data saved to {csv_filename}")
        
        # Analysis of conditions important for kelp drying
        print("\n" + "=" * 80)
        print("Kelp Drying Condition Analysis (1-week forecast at 4PM)")
        print("=" * 80)
        
        # Extract only 4 PM data (16:00)
        afternoon_data = df[df['Time'] == '16:00'].copy()
        
        if not afternoon_data.empty:
            print(f"{'Location':15} {'Date':>8} {'Temp':>6} {'Humid':>6} {'Wind':>8} {'Solar':>8} {'Cloud':>6} {'Rain':>6} {'Dry Rate':>10}")
            print("-" * 80)
            
            for index, row in afternoon_data.iterrows():
                # Kelp drying suitability evaluation
                temp = row['Temperature'] if pd.notna(row['Temperature']) else 0
                humidity = row['Humidity'] if pd.notna(row['Humidity']) else 100
                wind_speed = row['WindSpeed'] if pd.notna(row['WindSpeed']) else 0
                solar = row['SolarRadiation'] if pd.notna(row['SolarRadiation']) else 0
                rain = row['Precipitation'] if pd.notna(row['Precipitation']) else 0
                cloud = row['CloudCover'] if pd.notna(row['CloudCover']) else 0
                
                # Check for rain during drying hours (4AM-4PM) for the same day
                location_id = row['LocationID']
                date = row['Date']
                
                # Get all data for this location and date between 4AM-4PM
                daily_work_hours = df[
                    (df['LocationID'] == location_id) & 
                    (df['Date'] == date) & 
                    (df['Time'] >= '04:00') & 
                    (df['Time'] <= '16:00')
                ]
                
                # Check if there's any precipitation during working hours
                work_hours_rain = daily_work_hours['Precipitation'].sum() if not daily_work_hours.empty else 0
                
                # If rain during working hours, automatically mark as "Poor" regardless of other conditions
                if work_hours_rain > 0:
                    evaluation = "Poor"
                else:
                    # Calculate drying suitability score for non-rainy days
                    drying_score = 0
                    if temp > 15: drying_score += 1
                    if humidity < 70: drying_score += 1
                    if wind_speed > 3: drying_score += 1
                    if solar > 200: drying_score += 1
                    drying_score += 1  # No rain during working hours
                    
                    if drying_score >= 4:
                        evaluation = "Excellent"
                    elif drying_score >= 2:
                        evaluation = "Good"
                    else:
                        evaluation = "Poor"
                
                # Show location name only for the first row of each location
                current_location = row['LocationID']
                if index == 0:
                    location_display = current_location
                else:
                    prev_location = afternoon_data.iloc[afternoon_data.index.get_loc(index)-1]['LocationID']
                    location_display = current_location if current_location != prev_location else ""
                
                print(f"{location_display:15} {row['Date']:>8} {temp:>5.1f}C {humidity:>5.0f}% {wind_speed:>6.1f}m/s {solar:>7.0f}W/m2 {cloud:>5.0f}% {rain:>5.1f}mm {evaluation:>10}")
        
        print("\nDrying Evaluation Criteria:")
        print("Poor: Rain during working hours (4AM-4PM) - AUTOMATIC regardless of other conditions")
        print("Excellent: No rain + (Temp >=15C, Humidity <70%, Wind >=3m/s, Solar >=200W/m2) 4+ criteria")
        print("Good: No rain + 2-3 of above criteria")
        print("Poor: No rain but only 1 or fewer criteria")
    
    print(f"\nForecast data retrieval completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

if __name__ == "__main__":
    main()