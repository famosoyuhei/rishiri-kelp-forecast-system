#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Weekly Forecast Simulation for 4 Different Hoshiba Locations
Comprehensive analysis of enhanced atmospheric stability system across regions
"""

from atmospheric_stability_enhanced import enhanced_kelp_drying_forecast
from datetime import datetime, timedelta
import json
import pandas as pd

def run_weekly_forecast_simulation():
    """Run 1-week forecast simulation for 4 different locations"""
    
    # Selected locations from different districts
    locations = [
        {
            "name": "H_2065_1368",
            "lat": 45.2065,
            "lon": 141.1368,
            "district": "Original",
            "description": "Original test location"
        },
        {
            "name": "H_2321_2696", 
            "lat": 45.2321,
            "lon": 141.2696,
            "district": "Oshidomari",
            "description": "Northern coastal area"
        },
        {
            "name": "H_1109_2745",
            "lat": 45.1109,
            "lon": 141.2746,
            "district": "Oniwaki", 
            "description": "Western coastal area"
        },
        {
            "name": "H_0988_2398",
            "lat": 45.0988,
            "lon": 141.2399,
            "district": "Senposhi",
            "description": "Southern area"
        }
    ]
    
    print("=" * 80)
    print("WEEKLY FORECAST SIMULATION FOR 4 RISHIRI HOSHIBA LOCATIONS")
    print("=" * 80)
    print(f"Analysis Period: {datetime.now().strftime('%Y-%m-%d')} to {(datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d')}")
    print(f"Enhanced System: Atmospheric Stability Analysis Enabled")
    print()
    
    # Generate forecasts for next 7 days
    forecast_dates = []
    for i in range(1, 8):  # Days 1-7 from today
        date = datetime.now() + timedelta(days=i)
        forecast_dates.append(date.strftime("%Y-%m-%d"))
    
    all_results = {}
    
    # Process each location
    for location in locations:
        print(f"Processing {location['name']} - {location['district']} District")
        print(f"Location: {location['description']} ({location['lat']:.4f}, {location['lon']:.4f})")
        print("-" * 60)
        
        location_results = []
        
        for date in forecast_dates:
            print(f"  Forecasting for {date}...")
            
            try:
                # Get enhanced forecast
                forecast = enhanced_kelp_drying_forecast(location['lat'], location['lon'], date)
                
                if forecast:
                    # Extract key metrics
                    result = {
                        "date": date,
                        "recommendation_level": forecast['drying_assessment']['recommendation_level'],
                        "final_score": forecast['drying_assessment']['final_score'],
                        "base_score": forecast['drying_assessment']['base_score'],
                        "stability_penalty": forecast['drying_assessment']['stability_penalty'],
                        "instability_risk": forecast['atmospheric_stability']['instability_risk'],
                        "max_cape": forecast['atmospheric_stability']['stability_metrics']['max_cape'],
                        "min_lifted_index": forecast['atmospheric_stability']['stability_metrics']['min_lifted_index'],
                        "warnings_count": len(forecast['all_warnings']),
                        "key_warnings": forecast['all_warnings'][:3] if forecast['all_warnings'] else [],
                        "weather": {
                            "temperature": forecast['traditional_weather']['temperature'],
                            "humidity": forecast['traditional_weather']['humidity'],
                            "wind_speed": forecast['traditional_weather']['wind_speed'],
                            "precipitation_prob": forecast['traditional_weather']['precipitation_probability']
                        },
                        "convection_period": forecast['atmospheric_stability']['convection_timing']['convection_period']
                    }
                    
                    location_results.append(result)
                    
                    # Display summary
                    print(f"    {result['recommendation_level']:12} | Score: {result['final_score']:3.0f} | Instability: {result['instability_risk']:2.0f} | Warnings: {result['warnings_count']}")
                    
                else:
                    print(f"    Failed to get forecast for {date}")
                    location_results.append({"date": date, "error": "Forecast failed"})
                    
            except Exception as e:
                print(f"    Error for {date}: {str(e)}")
                location_results.append({"date": date, "error": str(e)})
        
        all_results[location['name']] = {
            "location_info": location,
            "forecasts": location_results
        }
        
        print()
    
    # Analyze results
    analyze_weekly_results(all_results)
    
    # Save detailed results
    save_results(all_results)
    
    return all_results

def analyze_weekly_results(all_results):
    """Analyze and compare weekly forecast results across locations"""
    
    print("=" * 80)
    print("WEEKLY FORECAST ANALYSIS")
    print("=" * 80)
    
    # Extract data for analysis
    locations = list(all_results.keys())
    
    print("DAILY COMPARISON ACROSS LOCATIONS")
    print("=" * 80)
    
    # Get all forecast dates
    dates = []
    if locations and all_results[locations[0]]['forecasts']:
        dates = [f['date'] for f in all_results[locations[0]]['forecasts'] if 'date' in f and 'error' not in f]
    
    # Day-by-day comparison
    for date in dates:
        print(f"\n{date}:")
        print(f"{'Location':<15} {'Recommendation':<12} {'Score':<5} {'Instability':<11} {'CAPE':<6} {'LI':<6} {'Warnings'}")
        print("-" * 80)
        
        for location_name in locations:
            forecasts = all_results[location_name]['forecasts']
            day_forecast = next((f for f in forecasts if f.get('date') == date), None)
            
            if day_forecast and 'error' not in day_forecast:
                print(f"{location_name:<15} {day_forecast['recommendation_level']:<12} "
                      f"{day_forecast['final_score']:<5.0f} {day_forecast['instability_risk']:<11.0f} "
                      f"{day_forecast['max_cape']:<6.0f} {day_forecast['min_lifted_index']:<6.1f} "
                      f"{day_forecast['warnings_count']}")
            else:
                print(f"{location_name:<15} {'ERROR':<12} {'N/A':<5} {'N/A':<11} {'N/A':<6} {'N/A':<6} {'0'}")
    
    print("\n" + "=" * 80)
    print("LOCATION-SPECIFIC ANALYSIS")
    print("=" * 80)
    
    for location_name, data in all_results.items():
        location_info = data['location_info']
        forecasts = [f for f in data['forecasts'] if 'error' not in f]
        
        if not forecasts:
            continue
        
        print(f"\n{location_name} - {location_info['district']} District")
        print(f"({location_info['lat']:.4f}, {location_info['lon']:.4f})")
        print("-" * 50)
        
        # Calculate statistics
        good_days = len([f for f in forecasts if f['recommendation_level'] in ['GOOD', 'FAIR']])
        poor_days = len([f for f in forecasts if f['recommendation_level'] in ['POOR', 'AVOID']])
        
        avg_score = sum(f['final_score'] for f in forecasts) / len(forecasts)
        avg_instability = sum(f['instability_risk'] for f in forecasts) / len(forecasts)
        avg_cape = sum(f['max_cape'] for f in forecasts) / len(forecasts)
        avg_li = sum(f['min_lifted_index'] for f in forecasts) / len(forecasts)
        
        total_warnings = sum(f['warnings_count'] for f in forecasts)
        
        print(f"Suitable days: {good_days}/7 ({good_days/7*100:.1f}%)")
        print(f"Poor/Avoid days: {poor_days}/7 ({poor_days/7*100:.1f}%)")
        print(f"Average final score: {avg_score:.1f}")
        print(f"Average instability risk: {avg_instability:.1f}")
        print(f"Average CAPE: {avg_cape:.0f}")
        print(f"Average Lifted Index: {avg_li:.1f}")
        print(f"Total warnings this week: {total_warnings}")
        
        # Most common convection period
        convection_periods = [f['convection_period'] for f in forecasts if 'convection_period' in f]
        if convection_periods:
            from collections import Counter
            most_common_period = Counter(convection_periods).most_common(1)[0]
            print(f"Most common convection period: {most_common_period[0]} ({most_common_period[1]}/7 days)")
    
    print("\n" + "=" * 80)
    print("REGIONAL DIFFERENCES ANALYSIS")
    print("=" * 80)
    
    # Compare districts
    districts = {}
    for location_name, data in all_results.items():
        district = data['location_info']['district']
        forecasts = [f for f in data['forecasts'] if 'error' not in f]
        
        if forecasts:
            districts[district] = {
                "location": location_name,
                "avg_score": sum(f['final_score'] for f in forecasts) / len(forecasts),
                "avg_instability": sum(f['instability_risk'] for f in forecasts) / len(forecasts),
                "good_days": len([f for f in forecasts if f['recommendation_level'] in ['GOOD', 'FAIR']]),
                "avg_temp": sum(f['weather']['temperature'] for f in forecasts) / len(forecasts),
                "avg_humidity": sum(f['weather']['humidity'] for f in forecasts) / len(forecasts),
                "avg_wind": sum(f['weather']['wind_speed'] for f in forecasts) / len(forecasts)
            }
    
    print(f"{'District':<12} {'Location':<15} {'Avg Score':<9} {'Good Days':<9} {'Avg Temp':<8} {'Avg Humid':<9} {'Avg Wind'}")
    print("-" * 80)
    
    for district, stats in districts.items():
        print(f"{district:<12} {stats['location']:<15} {stats['avg_score']:<9.1f} "
              f"{stats['good_days']}/7{'':<5} {stats['avg_temp']:<8.1f} "
              f"{stats['avg_humidity']:<9.1f} {stats['avg_wind']:<8.1f}")
    
    # Find best and worst locations
    if districts:
        best_district = max(districts.items(), key=lambda x: x[1]['avg_score'])
        worst_district = min(districts.items(), key=lambda x: x[1]['avg_score'])
        
        print(f"\nBest location this week: {best_district[0]} ({best_district[1]['location']}) - Score: {best_district[1]['avg_score']:.1f}")
        print(f"Worst location this week: {worst_district[0]} ({worst_district[1]['location']}) - Score: {worst_district[1]['avg_score']:.1f}")
        
        score_difference = best_district[1]['avg_score'] - worst_district[1]['avg_score']
        print(f"Regional score difference: {score_difference:.1f} points")
        
        if score_difference > 20:
            print("** SIGNIFICANT REGIONAL DIFFERENCES DETECTED **")
        elif score_difference > 10:
            print("** MODERATE REGIONAL DIFFERENCES **")
        else:
            print("** SIMILAR CONDITIONS ACROSS REGIONS **")

def save_results(all_results):
    """Save detailed results to files"""
    
    # Save JSON results
    json_filename = f"weekly_forecast_simulation_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(json_filename, 'w', encoding='utf-8') as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2, default=str)
    
    # Create summary CSV
    csv_data = []
    for location_name, data in all_results.items():
        location_info = data['location_info']
        for forecast in data['forecasts']:
            if 'error' not in forecast:
                row = {
                    'location': location_name,
                    'district': location_info['district'],
                    'lat': location_info['lat'],
                    'lon': location_info['lon'],
                    'date': forecast['date'],
                    'recommendation': forecast['recommendation_level'],
                    'final_score': forecast['final_score'],
                    'base_score': forecast['base_score'],
                    'stability_penalty': forecast['stability_penalty'],
                    'instability_risk': forecast['instability_risk'],
                    'max_cape': forecast['max_cape'],
                    'min_lifted_index': forecast['min_lifted_index'],
                    'warnings_count': forecast['warnings_count'],
                    'temperature': forecast['weather']['temperature'],
                    'humidity': forecast['weather']['humidity'],
                    'wind_speed': forecast['weather']['wind_speed'],
                    'precipitation_prob': forecast['weather']['precipitation_prob']
                }
                csv_data.append(row)
    
    if csv_data:
        df = pd.DataFrame(csv_data)
        csv_filename = f"weekly_forecast_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        df.to_csv(csv_filename, index=False, encoding='utf-8')
        
        print(f"\nResults saved:")
        print(f"- Detailed JSON: {json_filename}")
        print(f"- Summary CSV: {csv_filename}")

if __name__ == "__main__":
    try:
        results = run_weekly_forecast_simulation()
        print("\nWeekly forecast simulation completed successfully!")
        
    except Exception as e:
        import traceback
        print(f"Simulation error: {str(e)}")
        print(f"Traceback: {traceback.format_exc()}")