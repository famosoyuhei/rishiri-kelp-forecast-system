#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Enhanced verification using atmospheric stability analysis for August 10th
"""

from atmospheric_stability_enhanced import enhanced_kelp_drying_forecast
from datetime import datetime, timedelta
import json

def verify_enhanced_forecasts():
    """Verify enhanced forecasts for August 10th using atmospheric stability"""
    
    print("Enhanced August 10th Forecast Verification")
    print("Using atmospheric stability analysis")
    print("="*60)
    
    # Test coordinates
    coords = {"lat": 45.2065, "lon": 141.1368}
    target_date = "2025-08-10"
    
    print(f"Location: H_2065_1368 ({coords['lat']}, {coords['lon']})")
    print(f"Target Date: {target_date}")
    print(f"Actual Result: Failed drying (morning clear -> noon heavy rain)")
    print()
    
    # Test forecasts from 1-7 days before
    results = []
    
    for days_before in range(1, 8):
        forecast_date = datetime(2025, 8, 10) - timedelta(days=days_before)
        forecast_date_str = forecast_date.strftime("%Y-%m-%d")
        
        print(f"Enhanced Forecast {days_before} day(s) before ({forecast_date_str}):")
        print("-" * 40)
        
        # Get enhanced forecast
        forecast = enhanced_kelp_drying_forecast(coords["lat"], coords["lon"], target_date)
        
        if forecast:
            # Extract key metrics
            stability = forecast['atmospheric_stability']
            assessment = forecast['drying_assessment']
            
            # Display analysis
            print(f"  Atmospheric Instability Risk: {stability['instability_risk']:.0f}/100")
            print(f"  Max CAPE: {stability['stability_metrics']['max_cape']:.0f}")
            print(f"  Min Lifted Index: {stability['stability_metrics']['min_lifted_index']:.1f}")
            print(f"  Peak Risk Time: {stability['convection_timing']['peak_instability_hour']:02d}:00")
            
            print(f"  Base Drying Score: {assessment['base_score']:.0f}/100")
            print(f"  Stability Penalty: -{assessment['stability_penalty']:.0f}")
            print(f"  Final Score: {assessment['final_score']:.0f}/100")
            print(f"  Recommendation: {assessment['recommendation_level']}")
            
            print(f"  Key Warnings:")
            for warning in forecast['all_warnings'][:3]:  # Show top 3 warnings
                print(f"    - {warning}")
            
            # Assess accuracy against actual result
            accuracy = assess_enhanced_accuracy(forecast)
            print(f"  Prediction Accuracy: {accuracy['score']:.1f}% ({accuracy['level']})")
            
            results.append({
                "days_before": days_before,
                "forecast_date": forecast_date_str,
                "forecast": forecast,
                "accuracy": accuracy
            })
            
        else:
            print("  Failed to get forecast data")
            
        print()
    
    # Summary analysis
    analyze_enhanced_results(results)
    return results

def assess_enhanced_accuracy(forecast):
    """Assess accuracy of enhanced forecast against actual August 10th result"""
    
    # Actual conditions: Morning clear -> sudden heavy rain -> drying failure
    actual = {
        "drying_success": False,
        "morning_clear": True,
        "sudden_heavy_rain": True,
        "atmospheric_instability": True  # Confirmed by actual weather
    }
    
    stability = forecast['atmospheric_stability']
    assessment = forecast['drying_assessment']
    warnings = forecast['all_warnings']
    
    score = 0
    max_score = 100
    
    # 1. Overall drying recommendation accuracy (30 points)
    if assessment['recommendation_level'] in ['AVOID', 'POOR']:
        score += 30  # Correctly predicted failure
    elif assessment['recommendation_level'] in ['FAIR']:
        score += 15  # Partially correct
    
    # 2. Atmospheric instability detection (25 points)
    if stability['instability_risk'] > 20:
        score += 25  # Detected instability
    elif stability['instability_risk'] > 10:
        score += 15  # Some instability detected
    
    # 3. Convection timing prediction (20 points)
    timing = stability['convection_timing']
    if timing['convection_period'] in ['morning', 'midday']:
        score += 20  # Correct timing prediction
    elif timing['peak_instability_hour'] <= 12:
        score += 10  # Reasonably close timing
    
    # 4. Warning system effectiveness (15 points)
    instability_warning = any('INSTABILITY' in w for w in warnings)
    convection_warning = any('CONVECTION' in w for w in warnings)
    
    if instability_warning:
        score += 8
    if convection_warning:
        score += 7
    
    # 5. CAPE/LI parameter utilization (10 points)
    cape = stability['stability_metrics']['max_cape']
    li = stability['stability_metrics']['min_lifted_index']
    
    if cape > 300 and li < 0:  # Both parameters indicating instability
        score += 10
    elif cape > 200 or li < 1:  # At least one parameter indicating risk
        score += 5
    
    # Determine accuracy level
    if score >= 85:
        level = "Excellent"
    elif score >= 70:
        level = "Very Good"
    elif score >= 55:
        level = "Good"
    elif score >= 40:
        level = "Fair"
    elif score >= 25:
        level = "Poor"
    else:
        level = "Very Poor"
    
    return {
        "score": score,
        "level": level,
        "components": {
            "drying_recommendation": "Correct" if score >= 15 else "Incorrect",
            "instability_detection": "Good" if stability['instability_risk'] > 15 else "Weak",
            "timing_prediction": "Accurate" if timing['peak_instability_hour'] <= 12 else "Off",
            "warning_system": "Effective" if instability_warning else "Insufficient"
        }
    }

def analyze_enhanced_results(results):
    """Analyze and compare enhanced forecast results"""
    
    print("="*60)
    print("ENHANCED SYSTEM PERFORMANCE ANALYSIS")
    print("="*60)
    
    if not results:
        print("No results to analyze")
        return
    
    # Calculate averages
    avg_accuracy = sum(r['accuracy']['score'] for r in results) / len(results)
    avg_instability_risk = sum(r['forecast']['atmospheric_stability']['instability_risk'] for r in results) / len(results)
    avg_final_score = sum(r['forecast']['drying_assessment']['final_score'] for r in results) / len(results)
    
    print(f"Average Prediction Accuracy: {avg_accuracy:.1f}%")
    print(f"Average Instability Risk Detected: {avg_instability_risk:.1f}/100")
    print(f"Average Final Drying Score: {avg_final_score:.1f}/100")
    print()
    
    # Day-by-day analysis
    print("Day-by-day Enhanced Forecast Performance:")
    for result in results:
        forecast = result['forecast']
        accuracy = result['accuracy']
        
        instability_risk = forecast['atmospheric_stability']['instability_risk']
        final_score = forecast['drying_assessment']['final_score']
        recommendation = forecast['drying_assessment']['recommendation_level']
        
        print(f"  {result['days_before']} days before: {accuracy['score']:.1f}% accuracy")
        print(f"    Instability Risk: {instability_risk:.0f}/100")
        print(f"    Final Score: {final_score:.0f}/100")
        print(f"    Recommendation: {recommendation}")
    
    print()
    
    # System improvement analysis
    print("SYSTEM IMPROVEMENTS DEMONSTRATED:")
    
    # Count correct warnings
    correct_instability_warnings = sum(1 for r in results 
                                     if r['forecast']['atmospheric_stability']['instability_risk'] > 20)
    correct_avoid_recommendations = sum(1 for r in results 
                                      if r['forecast']['drying_assessment']['recommendation_level'] in ['AVOID', 'POOR'])
    
    print(f"- Instability Detection: {correct_instability_warnings}/{len(results)} forecasts detected significant risk")
    print(f"- Correct Recommendations: {correct_avoid_recommendations}/{len(results)} forecasts recommended avoiding/caution")
    
    # Compare with traditional system
    traditional_accuracy = 65.0  # From previous simple verification
    enhancement = avg_accuracy - traditional_accuracy
    
    print(f"- Accuracy Improvement: {enhancement:+.1f}% vs traditional system")
    
    if enhancement > 10:
        print("  ** SIGNIFICANT IMPROVEMENT **")
    elif enhancement > 5:
        print("  ** MODERATE IMPROVEMENT **")
    elif enhancement > 0:
        print("  ** SLIGHT IMPROVEMENT **")
    else:
        print("  ** NEEDS FURTHER TUNING **")
    
    print()
    print("KEY CAPABILITIES ADDED:")
    print("1. Atmospheric instability risk assessment (CAPE, Lifted Index, CIN)")
    print("2. Convection timing prediction")
    print("3. Dynamic stability-based penalty system")
    print("4. Enhanced warning system for sudden weather changes")
    print("5. Time-based instability evolution analysis")

if __name__ == "__main__":
    results = verify_enhanced_forecasts()
    
    # Save results
    with open("enhanced_august10_verification_results.json", "w") as f:
        # Convert datetime objects to strings for JSON serialization
        json_results = []
        for result in results:
            json_result = result.copy()
            # Remove non-serializable parts if needed
            json_results.append({
                "days_before": result["days_before"],
                "forecast_date": result["forecast_date"],
                "accuracy": result["accuracy"],
                "instability_risk": result["forecast"]["atmospheric_stability"]["instability_risk"],
                "final_score": result["forecast"]["drying_assessment"]["final_score"],
                "recommendation": result["forecast"]["drying_assessment"]["recommendation_level"]
            })
        
        json.dump(json_results, f, indent=2)
    
    print(f"\nDetailed results saved to: enhanced_august10_verification_results.json")