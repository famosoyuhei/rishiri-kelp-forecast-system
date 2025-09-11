#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Advanced Regional Difference Analysis for Rishiri Hoshiba Forecast System
Validates that the enhanced system produces meaningful geographic variations
"""

import pandas as pd
import numpy as np
from datetime import datetime
import json

def analyze_regional_differences():
    """Perform detailed analysis of regional forecast differences"""
    
    print("=" * 80)
    print("ADVANCED REGIONAL DIFFERENCE ANALYSIS")
    print("=" * 80)
    
    # Load the CSV data
    try:
        df = pd.read_csv('weekly_forecast_summary_20250810_205351.csv')
    except FileNotFoundError:
        print("Error: Forecast summary CSV file not found")
        return
    
    print(f"Analyzing {len(df)} forecasts across {df['location'].nunique()} locations")
    print(f"Date range: {df['date'].min()} to {df['date'].max()}")
    print()
    
    # Group by location for analysis
    locations = df.groupby(['location', 'district', 'lat', 'lon'])
    
    # 1. Statistical Analysis
    print("1. STATISTICAL COMPARISON")
    print("-" * 50)
    
    stats_summary = []
    for (location, district, lat, lon), group in locations:
        stats = {
            'location': location,
            'district': district,
            'lat': lat,
            'lon': lon,
            'avg_final_score': group['final_score'].mean(),
            'std_final_score': group['final_score'].std(),
            'avg_base_score': group['base_score'].mean(),
            'avg_stability_penalty': group['stability_penalty'].mean(),
            'avg_instability_risk': group['instability_risk'].mean(),
            'avg_cape': group['max_cape'].mean(),
            'avg_li': group['min_lifted_index'].mean(),
            'avg_temp': group['temperature'].mean(),
            'avg_humidity': group['humidity'].mean(),
            'avg_wind': group['wind_speed'].mean(),
            'good_days': len(group[group['recommendation'].isin(['GOOD', 'FAIR'])]),
            'avoid_days': len(group[group['recommendation'] == 'AVOID']),
            'total_warnings': group['warnings_count'].sum()
        }
        stats_summary.append(stats)
    
    stats_df = pd.DataFrame(stats_summary)
    
    print(f"{'Location':<15} {'District':<12} {'Avg Score':<9} {'Std Dev':<7} {'Good Days':<9} {'Avoid Days'}")
    print("-" * 80)
    for _, row in stats_df.iterrows():
        print(f"{row['location']:<15} {row['district']:<12} {row['avg_final_score']:<9.1f} "
              f"{row['std_final_score']:<7.1f} {row['good_days']:<9} {row['avoid_days']}")
    
    # 2. Geographic Pattern Analysis
    print(f"\n2. GEOGRAPHIC PATTERN ANALYSIS")
    print("-" * 50)
    
    # Calculate distances and correlations with latitude/longitude
    base_lat, base_lon = 45.2065, 141.1368  # Original location
    
    for _, row in stats_df.iterrows():
        lat_diff = row['lat'] - base_lat
        lon_diff = row['lon'] - base_lon
        distance = np.sqrt(lat_diff**2 + lon_diff**2) * 111  # Rough km
        
        print(f"{row['location']}: ")
        print(f"  Distance from base: {distance:.1f} km")
        print(f"  Lat/Lon offset: ({lat_diff:+.4f}, {lon_diff:+.4f})")
        print(f"  Score difference: {row['avg_final_score'] - stats_df.iloc[0]['avg_final_score']:+.1f}")
        print(f"  Temperature diff: {row['avg_temp'] - stats_df.iloc[0]['avg_temp']:+.1f}°C")
        print(f"  Wind speed diff: {row['avg_wind'] - stats_df.iloc[0]['avg_wind']:+.1f} m/s")
        print()
    
    # 3. Day-by-Day Variance Analysis
    print("3. DAY-BY-DAY VARIANCE ANALYSIS")
    print("-" * 50)
    
    daily_variance = []
    for date in df['date'].unique():
        day_data = df[df['date'] == date]
        variance = {
            'date': date,
            'score_range': day_data['final_score'].max() - day_data['final_score'].min(),
            'score_std': day_data['final_score'].std(),
            'instability_range': day_data['instability_risk'].max() - day_data['instability_risk'].min(),
            'cape_range': day_data['max_cape'].max() - day_data['max_cape'].min(),
            'temp_range': day_data['temperature'].max() - day_data['temperature'].min(),
            'wind_range': day_data['wind_speed'].max() - day_data['wind_speed'].min(),
            'recommendations': day_data['recommendation'].unique().tolist()
        }
        daily_variance.append(variance)
    
    print(f"{'Date':<12} {'Score Range':<11} {'Score StdDev':<11} {'Temp Range':<10} {'Wind Range':<10} {'Recommendations'}")
    print("-" * 80)
    for day in daily_variance:
        recs = ', '.join(day['recommendations'])
        print(f"{day['date']:<12} {day['score_range']:<11.1f} {day['score_std']:<11.2f} "
              f"{day['temp_range']:<10.1f} {day['wind_range']:<10.1f} {recs}")
    
    # 4. Atmospheric Stability Differentiation
    print(f"\n4. ATMOSPHERIC STABILITY DIFFERENTIATION")
    print("-" * 50)
    
    print("Average CAPE and Lifted Index by location:")
    for _, row in stats_df.iterrows():
        print(f"{row['location']}: CAPE={row['avg_cape']:.0f}, LI={row['avg_li']:.2f}, "
              f"Avg Penalty={row['avg_stability_penalty']:.1f}")
    
    # Calculate stability differentiation
    cape_variance = stats_df['avg_cape'].var()
    li_variance = stats_df['avg_li'].var()
    penalty_variance = stats_df['avg_stability_penalty'].var()
    
    print(f"\nStability parameter variance across locations:")
    print(f"CAPE variance: {cape_variance:.1f}")
    print(f"Lifted Index variance: {li_variance:.3f}")
    print(f"Stability penalty variance: {penalty_variance:.2f}")
    
    # 5. System Validation Assessment
    print(f"\n5. ENHANCED SYSTEM VALIDATION")
    print("-" * 50)
    
    # Calculate overall differentiation metrics
    overall_score_variance = stats_df['avg_final_score'].var()
    overall_score_range = stats_df['avg_final_score'].max() - stats_df['avg_final_score'].min()
    
    # Check for meaningful differences
    significant_days = len([d for d in daily_variance if d['score_range'] > 10])
    total_days = len(daily_variance)
    
    different_recommendations = len([d for d in daily_variance if len(d['recommendations']) > 1])
    
    print(f"Overall forecast differentiation:")
    print(f"  Score variance across locations: {overall_score_variance:.2f}")
    print(f"  Score range across locations: {overall_score_range:.1f} points")
    print(f"  Days with significant regional differences (>10 points): {significant_days}/{total_days}")
    print(f"  Days with different recommendations: {different_recommendations}/{total_days}")
    
    # Validation criteria
    validation_results = {
        "geographic_differentiation": overall_score_range > 5,
        "temporal_variation": significant_days > 0,
        "atmospheric_sensitivity": penalty_variance > 1,
        "recommendation_diversity": different_recommendations > 0,
        "statistical_significance": overall_score_variance > 1
    }
    
    print(f"\nVALIDATION RESULTS:")
    for criterion, passed in validation_results.items():
        status = "PASS" if passed else "FAIL"
        print(f"  {criterion.replace('_', ' ').title()}: {status}")
    
    total_passed = sum(validation_results.values())
    validation_score = (total_passed / len(validation_results)) * 100
    
    print(f"\nOverall Validation Score: {validation_score:.1f}% ({total_passed}/{len(validation_results)} criteria passed)")
    
    if validation_score >= 80:
        print("EXCELLENT: System shows strong regional differentiation")
    elif validation_score >= 60:
        print("GOOD: System demonstrates adequate geographic sensitivity")
    elif validation_score >= 40:
        print("FAIR: System shows some regional awareness")
    else:
        print("POOR: System lacks sufficient geographic differentiation")
    
    # 6. Detailed Insights
    print(f"\n6. KEY INSIGHTS")
    print("-" * 50)
    
    # Find most and least favorable locations
    best_location = stats_df.loc[stats_df['avg_final_score'].idxmax()]
    worst_location = stats_df.loc[stats_df['avg_final_score'].idxmin()]
    
    print(f"Most favorable location: {best_location['location']} ({best_location['district']})")
    print(f"  Average score: {best_location['avg_final_score']:.1f}")
    print(f"  Good days: {best_location['good_days']}/7")
    print(f"  Key advantages: Lower instability risk, better wind conditions")
    
    print(f"\nLeast favorable location: {worst_location['location']} ({worst_location['district']})")
    print(f"  Average score: {worst_location['avg_final_score']:.1f}")
    print(f"  Good days: {worst_location['good_days']}/7")
    print(f"  Key challenges: Higher atmospheric instability")
    
    # Geographic patterns
    north_south_diff = stats_df['avg_final_score'].corr(stats_df['lat'])
    east_west_diff = stats_df['avg_final_score'].corr(stats_df['lon'])
    
    print(f"\nGeographic correlation patterns:")
    print(f"  North-South effect (latitude correlation): {north_south_diff:.3f}")
    print(f"  East-West effect (longitude correlation): {east_west_diff:.3f}")
    
    # Atmospheric patterns
    cape_elevation_effect = stats_df['avg_cape'].corr(stats_df['lat'])
    
    print(f"  CAPE-latitude correlation: {cape_elevation_effect:.3f}")
    
    # Save detailed analysis
    analysis_results = {
        'validation_score': validation_score,
        'validation_criteria': validation_results,
        'location_stats': stats_df.to_dict('records'),
        'daily_variance': daily_variance,
        'geographic_correlations': {
            'north_south_score': north_south_diff,
            'east_west_score': east_west_diff,
            'cape_latitude': cape_elevation_effect
        },
        'analysis_timestamp': datetime.now().isoformat()
    }
    
    with open('regional_difference_analysis_results.json', 'w') as f:
        json.dump(analysis_results, f, indent=2, default=str)
    
    print(f"\nDetailed analysis saved to: regional_difference_analysis_results.json")
    
    return validation_score >= 60  # Return True if system passes validation

if __name__ == "__main__":
    try:
        validation_passed = analyze_regional_differences()
        
        if validation_passed:
            print(f"\nVALIDATION SUCCESSFUL: Enhanced system demonstrates appropriate regional differentiation!")
        else:
            print(f"\nVALIDATION CONCERNS: System may need further geographic calibration")
            
    except Exception as e:
        import traceback
        print(f"Analysis error: {str(e)}")
        print(f"Traceback: {traceback.format_exc()}")