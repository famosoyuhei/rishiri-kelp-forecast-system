#!/usr/bin/env python3
"""
Forecast Accuracy Verification System
Verify how accurately our app could predict July 29 weather from July 28
"""

import requests
import json
import sys
import os

# Add current directory to path to import our modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def get_forecast_from_july28():
    """Get forecast for July 29 as it would have been on July 28"""
    
    print("=== Forecast Accuracy Verification ===")
    print("Testing: How well could our app predict July 29 from July 28")
    print()
    
    # Test locations (same as actual verification)
    locations = {
        "Oshidomari": {"lat": 45.241667, "lon": 141.230833},
        "Kutsugata": {"lat": 45.118889, "lon": 141.176389}
    }
    
    forecasts = {}
    
    for location_name, coords in locations.items():
        print(f"Getting forecast for {location_name}...")
        
        # Simulate getting tomorrow's forecast (July 29) from July 28
        params = {
            "latitude": coords["lat"],
            "longitude": coords["lon"],
            "start_date": "2025-07-29",  # Target date
            "end_date": "2025-07-29",
            "hourly": "temperature_2m,relative_humidity_2m,precipitation,wind_speed_10m,wind_direction_10m,cloud_cover,weather_code",
            "timezone": "Asia/Tokyo"
        }
        
        try:
            response = requests.get("https://api.open-meteo.com/v1/forecast", params=params, timeout=10)
            
            if response.status_code == 200:
                api_data = response.json()
                
                # Apply our terrain corrections (simulating our app's processing)
                terrain_corrected_forecast = simulate_our_app_forecast(api_data, coords, location_name)
                forecasts[location_name] = terrain_corrected_forecast
                
                print(f"OK Forecast generated for {location_name}")
                
            else:
                print(f"Failed to get forecast for {location_name}")
                forecasts[location_name] = None
                
        except Exception as e:
            print(f"Error for {location_name}: {e}")
            forecasts[location_name] = None
    
    return forecasts

def simulate_our_app_forecast(api_data, coords, location_name):
    """Simulate how our app would process and present the forecast"""
    
    hourly = api_data["hourly"]
    lat, lon = coords["lat"], coords["lon"]
    
    # Simulate terrain info (as our app would calculate)
    terrain_info = simulate_terrain_calculation(lat, lon)
    
    # Apply terrain corrections (as our app does)
    corrected_forecast = apply_terrain_corrections_simulation(hourly, terrain_info)
    
    # Work hours analysis (4-16)
    work_slice = slice(4, 17)
    
    # Generate summary as our app would present
    forecast_summary = {
        "location": location_name,
        "coordinates": coords,
        "terrain_info": terrain_info,
        "weather_summary": {
            "cloud_cover_avg": sum(corrected_forecast["cloud_cover"][work_slice]) / 13,
            "wind_direction_avg": sum(corrected_forecast["wind_direction_10m"][work_slice]) / 13,
            "wind_speed_avg": sum(corrected_forecast["wind_speed_10m"][work_slice]) / 13,
            "humidity_avg": sum(corrected_forecast["relative_humidity_2m"][work_slice]) / 13,
            "temperature_avg": sum(corrected_forecast["temperature_2m"][work_slice]) / 13
        },
        "app_interpretation": {},
        "drying_recommendation": "",
        "warnings": []
    }
    
    # Add app's interpretation (as it would appear to user)
    cloud_cover = forecast_summary["weather_summary"]["cloud_cover_avg"]
    humidity = forecast_summary["weather_summary"]["humidity_avg"]
    wind_speed = forecast_summary["weather_summary"]["wind_speed_avg"]
    wind_direction = forecast_summary["weather_summary"]["wind_direction_avg"]
    
    # Weather interpretation
    if cloud_cover < 50:
        weather_condition = "Sunny"
        weather_score = 2
    elif cloud_cover < 75:
        weather_condition = "Cloudy"
        weather_score = 1
    else:
        weather_condition = "Overcast"
        weather_score = 0
    
    # Wind analysis
    wind_direction_text = analyze_wind_direction(wind_direction)
    yamase_risk = check_yamase_risk(wind_direction, humidity)
    
    # Terrain effects
    terrain_warnings = []
    if "森林" in terrain_info["land_use"]:
        terrain_warnings.append("Forest area - reduced wind speed")
        wind_speed *= 0.7  # Simulate forest wind reduction
    
    # Overall drying assessment
    drying_score = 0
    
    # Weather factor
    drying_score += weather_score
    
    # Wind factor
    if wind_speed >= 3:
        drying_score += 2
    elif wind_speed >= 1:
        drying_score += 1
    
    # Humidity factor
    if humidity < 60:
        drying_score += 2
    elif humidity < 75:
        drying_score += 1
    elif humidity > 85:
        drying_score -= 1
    
    # Yamase penalty
    if yamase_risk:
        drying_score -= 2
        terrain_warnings.append("Yamase (east wind) detected - high humidity risk")
    
    # Generate recommendation
    if drying_score >= 4:
        recommendation = "Excellent drying conditions"
    elif drying_score >= 2:
        recommendation = "Good drying conditions"
    elif drying_score >= 0:
        recommendation = "Fair conditions - monitor closely"
    else:
        recommendation = "Poor drying conditions"
    
    forecast_summary["app_interpretation"] = {
        "weather_condition": weather_condition,
        "wind_direction_text": wind_direction_text,
        "yamase_risk": yamase_risk,
        "drying_score": drying_score
    }
    forecast_summary["drying_recommendation"] = recommendation
    forecast_summary["warnings"] = terrain_warnings
    
    return forecast_summary

def simulate_terrain_calculation(lat, lon):
    """Simulate terrain calculation as our app does"""
    import math
    
    # Simulate terrain calculation (simplified version of our app's logic)
    center_lat, center_lon = 45.1821, 141.2421
    distance = math.sqrt((lat - center_lat)**2 + (lon - center_lon)**2) * 111000
    
    if distance < 5000:
        elevation = max(0, 200 - (distance - 2000) * 0.05)
        land_use = "森林（広葉樹）" if elevation > 100 else "草地"
    else:
        elevation = max(0, 50 - (distance - 5000) * 0.01)
        land_use = "農地"
    
    return {
        "elevation": elevation,
        "land_use": land_use,
        "distance_to_coast": distance / 1000
    }

def apply_terrain_corrections_simulation(hourly_data, terrain_info):
    """Simulate terrain corrections as our app applies them"""
    
    corrected = hourly_data.copy()
    
    # Apply corrections (simplified version of our app's logic)
    if "森林" in terrain_info["land_use"]:
        # Forest effects
        corrected["wind_speed_10m"] = [max(0, ws - 2.5) for ws in hourly_data["wind_speed_10m"]]
        corrected["relative_humidity_2m"] = [min(100, rh + 10) for rh in hourly_data["relative_humidity_2m"]]
    
    # Elevation effects
    elevation = terrain_info["elevation"]
    temp_correction = -elevation * 0.006
    corrected["temperature_2m"] = [t + temp_correction for t in hourly_data["temperature_2m"]]
    
    return corrected

def analyze_wind_direction(degrees):
    """Analyze wind direction"""
    if 67.5 <= degrees <= 112.5:
        return "East"
    elif 22.5 <= degrees < 67.5:
        return "Northeast"
    elif 112.5 < degrees <= 157.5:
        return "Southeast"
    elif 337.5 <= degrees or degrees < 22.5:
        return "North"
    elif 247.5 <= degrees < 292.5:
        return "West"
    else:
        return "Other"

def check_yamase_risk(wind_direction, humidity):
    """Check for Yamase risk"""
    east_wind = 45 <= wind_direction <= 120  # Northeast to Southeast
    high_humidity = humidity > 80
    return east_wind and high_humidity

def compare_with_actual_results():
    """Compare forecast with actual results"""
    
    # Get our app's forecast
    app_forecasts = get_forecast_from_july28()
    
    if not app_forecasts.get("Oshidomari") or not app_forecasts.get("Kutsugata"):
        print("Failed to generate forecasts")
        return
    
    # Actual results from previous verification
    actual_results = {
        "Oshidomari": {"cloudy": True, "humidity": 90.9, "drying_result": "Failed"},
        "Kutsugata": {"cloudy": False, "humidity": 89.0, "drying_result": "Success"}
    }
    
    print("\n" + "="*60)
    print("FORECAST ACCURACY COMPARISON")
    print("="*60)
    
    correct_predictions = 0
    total_predictions = 0
    
    for location in ["Oshidomari", "Kutsugata"]:
        forecast = app_forecasts[location]
        actual = actual_results[location]
        
        print(f"\n{location.upper()}:")
        print("-" * 30)
        
        # Weather prediction accuracy
        predicted_cloudy = forecast["weather_summary"]["cloud_cover_avg"] >= 50
        actual_cloudy = actual["cloudy"]
        
        weather_correct = predicted_cloudy == actual_cloudy
        if weather_correct:
            correct_predictions += 1
        total_predictions += 1
        
        print(f"Weather prediction: {'OK' if weather_correct else 'MISS'}")
        print(f"  Predicted: {'Cloudy' if predicted_cloudy else 'Sunny'} ({forecast['weather_summary']['cloud_cover_avg']:.1f}% cloud)")
        print(f"  Actual: {'Cloudy' if actual_cloudy else 'Sunny'}")
        
        # Humidity prediction accuracy
        predicted_humidity = forecast["weather_summary"]["humidity_avg"]
        actual_humidity = actual["humidity"]
        humidity_error = abs(predicted_humidity - actual_humidity)
        
        humidity_accurate = humidity_error < 10  # Within 10%
        if humidity_accurate:
            correct_predictions += 1
        total_predictions += 1
        
        print(f"Humidity prediction: {'OK' if humidity_accurate else 'MISS'}")
        print(f"  Predicted: {predicted_humidity:.1f}%")
        print(f"  Actual: {actual_humidity:.1f}% (Error: {humidity_error:.1f}%)")
        
        # Drying recommendation accuracy
        recommendation = forecast["drying_recommendation"]
        actual_result = actual["drying_result"]
        
        # Interpret recommendation accuracy
        rec_success_predicted = "Excellent" in recommendation or "Good" in recommendation
        actual_success = actual_result == "Success"
        
        drying_correct = rec_success_predicted == actual_success
        if drying_correct:
            correct_predictions += 1
        total_predictions += 1
        
        print(f"Drying recommendation: {'OK' if drying_correct else 'MISS'}")
        print(f"  Predicted: {recommendation}")
        print(f"  Actual result: {actual_result}")
        
        # Yamase detection
        yamase_detected = forecast["app_interpretation"]["yamase_risk"]
        high_humidity_actual = actual_humidity > 85
        
        print(f"Yamase risk detection: {'OK' if yamase_detected and high_humidity_actual else 'MISS'}")
        print(f"  App detected Yamase: {yamase_detected}")
        print(f"  High humidity occurred: {high_humidity_actual}")
        
        # Terrain warnings
        warnings = forecast["warnings"]
        print(f"Terrain warnings: {len(warnings)} warnings")
        for warning in warnings:
            print(f"  - {warning}")
    
    # Overall accuracy
    accuracy_percentage = (correct_predictions / total_predictions) * 100
    
    print(f"\n{'='*60}")
    print("OVERALL FORECAST ACCURACY")
    print(f"{'='*60}")
    print(f"Correct predictions: {correct_predictions}/{total_predictions}")
    print(f"Accuracy rate: {accuracy_percentage:.1f}%")
    
    if accuracy_percentage >= 80:
        print("EXCELLENT ACCURACY - App forecasts are highly reliable")
    elif accuracy_percentage >= 60:
        print("GOOD ACCURACY - App forecasts are generally reliable")
    else:
        print("NEEDS IMPROVEMENT - App forecasts need enhancement")
    
    # Specific insights
    print(f"\nKEY INSIGHTS:")
    print("- Weather pattern prediction (cloudy/sunny)")
    print("- Humidity level forecasting") 
    print("- Drying condition assessment")
    print("- Terrain effect modeling")
    print("- Yamase risk detection")
    
    return {
        "accuracy_rate": accuracy_percentage,
        "correct_predictions": correct_predictions,
        "total_predictions": total_predictions,
        "forecasts": app_forecasts
    }

if __name__ == "__main__":
    results = compare_with_actual_results()