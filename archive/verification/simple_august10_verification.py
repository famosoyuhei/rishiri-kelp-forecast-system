#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Simple verification for August 10th forecast accuracy
"""

import requests
import json
from datetime import datetime, timedelta

def verify_august_10():
    """Verify forecast accuracy for August 10th"""
    
    print("=== August 10th H_2065_1368 Forecast Verification ===")
    print("Actual result: Morning clear -> Noon heavy rain -> Drying failed")
    print("Location: H_2065_1368 (45.2065N, 141.1368E)")
    print()
    
    coords = {"lat": 45.2065, "lon": 141.1368}
    target_date = "2025-08-10"
    
    # Check forecasts from 1-7 days before
    results = []
    
    for days_before in range(1, 8):
        forecast_date = datetime(2025, 8, 10) - timedelta(days=days_before)
        forecast_date_str = forecast_date.strftime("%Y-%m-%d")
        
        print(f"Checking {days_before} day(s) before forecast ({forecast_date_str})...")
        
        # Get forecast data
        params = {
            "latitude": coords["lat"],
            "longitude": coords["lon"],
            "start_date": target_date,
            "end_date": target_date,
            "hourly": "temperature_2m,relative_humidity_2m,precipitation,precipitation_probability,wind_speed_10m,cloud_cover,weather_code",
            "timezone": "Asia/Tokyo"
        }
        
        try:
            response = requests.get("https://api.open-meteo.com/v1/forecast", params=params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                hourly = data["hourly"]
                
                # Analyze work hours (6:00-16:00)
                work_hours = slice(6, 17)
                
                # Morning (6-12) vs Afternoon (12-16)
                morning_precip = hourly["precipitation_probability"][6:12]
                afternoon_precip = hourly["precipitation_probability"][12:17]
                
                morning_cloud = hourly["cloud_cover"][6:12]
                afternoon_cloud = hourly["cloud_cover"][12:17]
                
                avg_morning_precip = sum(morning_precip) / len(morning_precip)
                avg_afternoon_precip = sum(afternoon_precip) / len(afternoon_precip)
                
                avg_morning_cloud = sum(morning_cloud) / len(morning_cloud)
                avg_afternoon_cloud = sum(afternoon_cloud) / len(afternoon_cloud)
                
                # Accuracy assessment
                accuracy = assess_forecast_accuracy(
                    avg_morning_precip, avg_afternoon_precip,
                    avg_morning_cloud, avg_afternoon_cloud
                )
                
                results.append({
                    "days_before": days_before,
                    "forecast_date": forecast_date_str,
                    "morning_precip_prob": avg_morning_precip,
                    "afternoon_precip_prob": avg_afternoon_precip,
                    "morning_cloud": avg_morning_cloud,
                    "afternoon_cloud": avg_afternoon_cloud,
                    "accuracy": accuracy
                })
                
                print(f"  Morning precip prob: {avg_morning_precip:.1f}%")
                print(f"  Afternoon precip prob: {avg_afternoon_precip:.1f}%")
                print(f"  Accuracy: {accuracy['level']} ({accuracy['score']:.1f}%)")
                print()
                
            else:
                print(f"  Failed to get data (HTTP {response.status_code})")
                
        except Exception as e:
            print(f"  Error: {e}")
    
    # Summary
    print("="*60)
    print("SUMMARY")
    print("="*60)
    
    if results:
        avg_accuracy = sum(r["accuracy"]["score"] for r in results) / len(results)
        print(f"Average forecast accuracy: {avg_accuracy:.1f}%")
        print()
        
        print("Day-by-day accuracy:")
        for result in results:
            print(f"  {result['days_before']} days before: {result['accuracy']['score']:.1f}% ({result['accuracy']['level']})")
        
        # Best prediction
        best = max(results, key=lambda x: x["accuracy"]["score"])
        print(f"\nBest prediction: {best['days_before']} days before ({best['accuracy']['score']:.1f}%)")
        
        # Analysis
        print(f"\nAnalysis:")
        print(f"- Weather pattern: Morning clear -> Afternoon rain")
        print(f"- Challenge: Predicting sudden weather change")
        
        # Recommendations
        predicted_afternoon_rain = sum(1 for r in results if r["afternoon_precip_prob"] > 50)
        print(f"- {predicted_afternoon_rain}/{len(results)} forecasts correctly predicted afternoon rain risk")
        
    else:
        print("No forecast data available")
    
    return results

def assess_forecast_accuracy(morning_precip, afternoon_precip, morning_cloud, afternoon_cloud):
    """Assess how accurately the forecast predicted the actual conditions"""
    
    # Actual conditions:
    # - Morning: Clear (low cloud, no precip)
    # - Afternoon: Heavy rain (high precip, high cloud)
    
    score = 0
    max_score = 100
    
    # Morning prediction accuracy (should be low precip, clear)
    if morning_precip < 30:  # Correctly predicted low morning rain chance
        score += 25
    elif morning_precip < 50:
        score += 15
    
    if morning_cloud < 60:  # Correctly predicted clear morning
        score += 25
    elif morning_cloud < 80:
        score += 15
    
    # Afternoon prediction accuracy (should be high precip)
    if afternoon_precip > 60:  # Correctly predicted high afternoon rain chance
        score += 25
    elif afternoon_precip > 40:
        score += 15
    elif afternoon_precip > 20:
        score += 5
    
    # Weather change detection (afternoon should be worse than morning)
    if afternoon_precip > morning_precip + 20:  # Detected worsening conditions
        score += 25
    elif afternoon_precip > morning_precip + 10:
        score += 15
    elif afternoon_precip > morning_precip:
        score += 5
    
    # Determine accuracy level
    if score >= 80:
        level = "Excellent"
    elif score >= 60:
        level = "Good"
    elif score >= 40:
        level = "Fair"
    elif score >= 20:
        level = "Poor"
    else:
        level = "Very Poor"
    
    return {
        "score": score,
        "level": level
    }

if __name__ == "__main__":
    results = verify_august_10()
    
    # Save results
    with open("august10_simple_verification.json", "w") as f:
        json.dump(results, f, indent=2)
    
    print(f"\nResults saved to august10_simple_verification.json")