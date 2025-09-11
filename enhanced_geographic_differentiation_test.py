#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Enhanced Geographic Differentiation Test
Test the system with more extreme coordinate differences to validate geographic sensitivity
"""

from atmospheric_stability_enhanced import enhanced_kelp_drying_forecast
from datetime import datetime, timedelta
import json

def test_extreme_geographic_differences():
    """Test system with more extreme geographic differences"""
    
    print("=" * 80)
    print("ENHANCED GEOGRAPHIC DIFFERENTIATION TEST")
    print("=" * 80)
    
    # Test with more extreme locations around Rishiri
    test_locations = [
        {
            "name": "North_Coast",
            "lat": 45.28,  # Northern tip
            "lon": 141.20,
            "description": "Northern coastal extreme"
        },
        {
            "name": "South_Coast", 
            "lat": 45.10,  # Southern area
            "lon": 141.24,
            "description": "Southern coastal area"
        },
        {
            "name": "East_Coast",
            "lat": 45.18,  # Eastern side
            "lon": 141.30,
            "description": "Eastern coastal area"
        },
        {
            "name": "West_Coast",
            "lat": 45.18,  # Western side
            "lon": 141.15,
            "description": "Western coastal area"
        },
        {
            "name": "Island_Center",
            "lat": 45.18,  # Near Rishiri mountain
            "lon": 141.24,
            "description": "Island center (near mountain)"
        }
    ]
    
    # Test for next 3 days
    test_dates = []
    for i in range(1, 4):
        date = datetime.now() + timedelta(days=i)
        test_dates.append(date.strftime("%Y-%m-%d"))
    
    results = {}
    
    print(f"Testing {len(test_locations)} locations across {len(test_dates)} days")
    print()
    
    for date in test_dates:
        print(f"TESTING DATE: {date}")
        print("-" * 60)
        
        date_results = []
        
        for location in test_locations:
            try:
                forecast = enhanced_kelp_drying_forecast(location['lat'], location['lon'], date)
                
                if forecast:
                    result = {
                        'location': location,
                        'recommendation_level': forecast['drying_assessment']['recommendation_level'],
                        'final_score': forecast['drying_assessment']['final_score'],
                        'base_score': forecast['drying_assessment']['base_score'],
                        'stability_penalty': forecast['drying_assessment']['stability_penalty'],
                        'instability_risk': forecast['atmospheric_stability']['instability_risk'],
                        'max_cape': forecast['atmospheric_stability']['stability_metrics']['max_cape'],
                        'min_lifted_index': forecast['atmospheric_stability']['stability_metrics']['min_lifted_index'],
                        'weather': forecast['traditional_weather']
                    }
                    
                    date_results.append(result)
                    
                    print(f"  {location['name']:<15} ({location['lat']:.2f}, {location['lon']:.2f})")
                    print(f"    Recommendation: {result['recommendation_level']:<12} Score: {result['final_score']:5.1f}")
                    print(f"    Weather: T={result['weather']['temperature']:.1f}°C, H={result['weather']['humidity']:.1f}%, W={result['weather']['wind_speed']:.1f}m/s")
                    print(f"    Stability: CAPE={result['max_cape']:.0f}, LI={result['min_lifted_index']:.1f}, Risk={result['instability_risk']:.0f}")
                    print()
                    
                else:
                    print(f"  {location['name']}: FORECAST FAILED")
                    
            except Exception as e:
                print(f"  {location['name']}: ERROR - {str(e)}")
        
        # Analyze differences for this date
        if len(date_results) > 1:
            scores = [r['final_score'] for r in date_results]
            temps = [r['weather']['temperature'] for r in date_results]
            winds = [r['weather']['wind_speed'] for r in date_results]
            capes = [r['max_cape'] for r in date_results]
            
            print(f"  DAILY ANALYSIS:")
            print(f"    Score range: {max(scores) - min(scores):.1f} points")
            print(f"    Temperature range: {max(temps) - min(temps):.1f}°C")
            print(f"    Wind range: {max(winds) - min(winds):.1f} m/s")
            print(f"    CAPE range: {max(capes) - min(capes):.0f}")
            
            # Check for different recommendations
            recommendations = set(r['recommendation_level'] for r in date_results)
            print(f"    Unique recommendations: {len(recommendations)} ({', '.join(recommendations)})")
            
            if max(scores) - min(scores) > 10:
                print(f"    ** SIGNIFICANT GEOGRAPHIC DIFFERENCES DETECTED **")
            elif len(recommendations) > 1:
                print(f"    ** MODERATE GEOGRAPHIC VARIATION **")
            else:
                print(f"    ** SIMILAR CONDITIONS ACROSS LOCATIONS **")
        
        results[date] = date_results
        print()
    
    # Overall analysis
    print("=" * 80)
    print("OVERALL GEOGRAPHIC DIFFERENTIATION ANALYSIS")
    print("=" * 80)
    
    all_score_ranges = []
    all_recommendations = set()
    total_significant_days = 0
    
    for date, date_results in results.items():
        if len(date_results) > 1:
            scores = [r['final_score'] for r in date_results]
            score_range = max(scores) - min(scores)
            all_score_ranges.append(score_range)
            
            recs = set(r['recommendation_level'] for r in date_results)
            all_recommendations.update(recs)
            
            if score_range > 10:
                total_significant_days += 1
    
    if all_score_ranges:
        avg_score_range = sum(all_score_ranges) / len(all_score_ranges)
        max_score_range = max(all_score_ranges)
        
        print(f"Average daily score range: {avg_score_range:.1f} points")
        print(f"Maximum daily score range: {max_score_range:.1f} points")
        print(f"Days with significant differences (>10 points): {total_significant_days}/{len(test_dates)}")
        print(f"Total unique recommendations: {len(all_recommendations)} ({', '.join(sorted(all_recommendations))})")
        
        # Enhanced validation
        geographic_validation = {
            "substantial_differences": max_score_range > 15,
            "consistent_variation": avg_score_range > 5,
            "recommendation_diversity": len(all_recommendations) > 2,
            "significant_days": total_significant_days > 0
        }
        
        print(f"\nENHANCED VALIDATION:")
        for criterion, passed in geographic_validation.items():
            status = "PASS" if passed else "FAIL"
            print(f"  {criterion.replace('_', ' ').title()}: {status}")
        
        validation_score = sum(geographic_validation.values()) / len(geographic_validation) * 100
        
        print(f"\nGeographic Differentiation Score: {validation_score:.1f}%")
        
        if validation_score >= 75:
            print("EXCELLENT: Strong geographic differentiation capability")
        elif validation_score >= 50:
            print("GOOD: Adequate geographic sensitivity")
        elif validation_score >= 25:
            print("FAIR: Some geographic awareness")
        else:
            print("POOR: Limited geographic differentiation")
    
    # Save results
    with open('enhanced_geographic_test_results.json', 'w') as f:
        json.dump(results, f, indent=2, default=str)
    
    print(f"\nDetailed results saved to: enhanced_geographic_test_results.json")
    
    return results

if __name__ == "__main__":
    try:
        results = test_extreme_geographic_differences()
        print("\nEnhanced geographic differentiation test completed!")
        
    except Exception as e:
        import traceback
        print(f"Test error: {str(e)}")
        print(f"Traceback: {traceback.format_exc()}")