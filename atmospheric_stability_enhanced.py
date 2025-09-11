#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Enhanced Atmospheric Stability Analysis Module
Incorporates CAPE, Lifted Index, and Convective Inhibition for improved kelp drying forecasts
"""

import requests
import json
import math
from datetime import datetime, timedelta

class AtmosphericStabilityAnalyzer:
    """Analyzes atmospheric stability for kelp drying predictions"""
    
    def __init__(self):
        self.api_base = "https://api.open-meteo.com/v1/forecast"
        self.stability_params = [
            "cape", "lifted_index", "convective_inhibition",
            "temperature_2m", "relative_humidity_2m", "precipitation",
            "precipitation_probability", "wind_speed_10m", "wind_direction_10m",
            "cloud_cover", "weather_code", "pressure_msl"
        ]
    
    def get_enhanced_forecast(self, lat, lon, date):
        """Get forecast with atmospheric stability parameters"""
        
        params = {
            "latitude": lat,
            "longitude": lon,
            "start_date": date,
            "end_date": date,
            "hourly": ",".join(self.stability_params),
            "timezone": "Asia/Tokyo"
        }
        
        try:
            response = requests.get(self.api_base, params=params, timeout=15)
            
            if response.status_code == 200:
                return response.json()
            else:
                print(f"API Error: HTTP {response.status_code}")
                return None
                
        except Exception as e:
            print(f"Request Error: {e}")
            return None
    
    def analyze_stability_risk(self, hourly_data, work_hours_slice=slice(6, 17)):
        """Analyze atmospheric stability risk for kelp drying"""
        
        # Extract stability parameters for work hours
        cape_values = hourly_data["cape"][work_hours_slice]
        li_values = hourly_data["lifted_index"][work_hours_slice]
        cin_values = hourly_data["convective_inhibition"][work_hours_slice]
        precip_prob = hourly_data["precipitation_probability"][work_hours_slice]
        precipitation = hourly_data["precipitation"][work_hours_slice]
        
        # Calculate stability metrics
        max_cape = max(cape_values)
        min_li = min(li_values)
        min_cin = min(cin_values)
        avg_cape = sum(cape_values) / len(cape_values)
        
        # Time-based analysis
        morning_cape = sum(cape_values[:4]) / 4  # 6:00-9:00
        afternoon_cape = sum(cape_values[4:]) / len(cape_values[4:])  # 10:00-16:00
        
        morning_li = sum(li_values[:4]) / 4
        afternoon_li = sum(li_values[4:]) / len(li_values[4:])
        
        # Calculate instability risk scores
        instability_risk = self._calculate_instability_risk(
            max_cape, min_li, min_cin, morning_cape, afternoon_cape
        )
        
        # Analyze convection timing
        convection_timing = self._analyze_convection_timing(
            cape_values, li_values, cin_values, precip_prob
        )
        
        # Generate stability warnings
        warnings = self._generate_stability_warnings(
            max_cape, min_li, min_cin, convection_timing
        )
        
        return {
            "stability_metrics": {
                "max_cape": max_cape,
                "min_lifted_index": min_li,
                "min_cin": min_cin,
                "avg_cape": avg_cape,
                "morning_cape": morning_cape,
                "afternoon_cape": afternoon_cape,
                "morning_li": morning_li,
                "afternoon_li": afternoon_li
            },
            "instability_risk": instability_risk,
            "convection_timing": convection_timing,
            "stability_warnings": warnings,
            "recommendation": self._generate_stability_recommendation(instability_risk, warnings)
        }
    
    def _calculate_instability_risk(self, max_cape, min_li, min_cin, morning_cape, afternoon_cape):
        """Calculate overall atmospheric instability risk score (0-100)"""
        
        risk_score = 0
        
        # CAPE-based risk
        if max_cape > 2500:
            risk_score += 40  # Extreme instability
        elif max_cape > 1500:
            risk_score += 30  # High instability
        elif max_cape > 1000:
            risk_score += 20  # Moderate-high instability
        elif max_cape > 500:
            risk_score += 10  # Moderate instability
        elif max_cape > 250:
            risk_score += 5   # Low-moderate instability
        
        # Lifted Index-based risk
        if min_li < -6:
            risk_score += 25  # Extreme instability
        elif min_li < -4:
            risk_score += 20  # High instability
        elif min_li < -2:
            risk_score += 15  # Moderate instability
        elif min_li < 0:
            risk_score += 10  # Low instability
        elif min_li < 2:
            risk_score += 5   # Near neutral
        
        # CIN-based risk (lower CIN = higher risk)
        if abs(min_cin) < 25:
            risk_score += 15  # Low inhibition - easy convection
        elif abs(min_cin) < 50:
            risk_score += 10  # Moderate inhibition
        elif abs(min_cin) < 100:
            risk_score += 5   # High inhibition
        
        # Time evolution risk
        cape_increase = afternoon_cape - morning_cape
        if cape_increase > 200:
            risk_score += 20  # Rapid destabilization
        elif cape_increase > 100:
            risk_score += 10  # Moderate destabilization
        elif cape_increase > 50:
            risk_score += 5   # Some destabilization
        
        return min(100, risk_score)  # Cap at 100
    
    def _analyze_convection_timing(self, cape_values, li_values, cin_values, precip_prob):
        """Analyze when convection is most likely to occur"""
        
        # Find peak instability time
        max_instability_hour = 0
        max_instability_score = -1000
        
        for i, (cape, li, cin) in enumerate(zip(cape_values, li_values, cin_values)):
            # Simple instability score
            instability_score = cape - li * 100 - abs(cin) * 0.5
            if instability_score > max_instability_score:
                max_instability_score = instability_score
                max_instability_hour = i
        
        # Analyze precipitation probability trend
        early_precip = sum(precip_prob[:4]) / 4  # Morning average
        late_precip = sum(precip_prob[6:]) / len(precip_prob[6:])  # Afternoon average
        
        # Determine most likely convection period
        if max_instability_hour < 4:
            convection_period = "morning"
        elif max_instability_hour < 8:
            convection_period = "midday"
        else:
            convection_period = "afternoon"
        
        return {
            "peak_instability_hour": max_instability_hour + 6,  # Convert to actual hour
            "peak_instability_score": max_instability_score,
            "convection_period": convection_period,
            "early_precip_prob": early_precip,
            "late_precip_prob": late_precip,
            "precip_trend": "increasing" if late_precip > early_precip + 10 else "stable"
        }
    
    def _generate_stability_warnings(self, max_cape, min_li, min_cin, convection_timing):
        """Generate specific warnings based on atmospheric stability"""
        
        warnings = []
        
        # High instability warnings
        if max_cape > 1500 or min_li < -4:
            warnings.append("SEVERE INSTABILITY: High thunderstorm risk - avoid drying")
        elif max_cape > 1000 or min_li < -2:
            warnings.append("HIGH INSTABILITY: Thunderstorm possible - high risk")
        elif max_cape > 500 or min_li < 0:
            warnings.append("MODERATE INSTABILITY: Shower/thunder risk - monitor closely")
        elif max_cape > 250:
            warnings.append("LOW INSTABILITY: Some convection possible")
        
        # Convection inhibition warnings
        if abs(min_cin) < 25:
            warnings.append("LOW CIN: Convection easily triggered")
        elif abs(min_cin) < 50 and max_cape > 500:
            warnings.append("MODERATE CIN: Convection possible with heating")
        
        # Timing-specific warnings
        timing = convection_timing["convection_period"]
        if timing == "morning":
            warnings.append("MORNING CONVECTION RISK: Early thunderstorms possible")
        elif timing == "midday":
            warnings.append("MIDDAY CONVECTION RISK: Peak heating may trigger storms")
        elif timing == "afternoon":
            warnings.append("AFTERNOON CONVECTION RISK: Late-day storms likely")
        
        if convection_timing["precip_trend"] == "increasing":
            warnings.append("WORSENING CONDITIONS: Rain probability increases later")
        
        return warnings
    
    def _generate_stability_recommendation(self, risk_score, warnings):
        """Generate overall recommendation based on stability analysis"""
        
        severe_warnings = len([w for w in warnings if "SEVERE" in w or "HIGH" in w])
        moderate_warnings = len([w for w in warnings if "MODERATE" in w])
        
        if risk_score >= 70 or severe_warnings > 0:
            return {
                "level": "AVOID_DRYING",
                "message": "High atmospheric instability - do not attempt kelp drying",
                "confidence": "high"
            }
        elif risk_score >= 50 or moderate_warnings > 1:
            return {
                "level": "HIGH_RISK",
                "message": "Significant instability risk - drying strongly discouraged",
                "confidence": "high"
            }
        elif risk_score >= 30 or moderate_warnings > 0:
            return {
                "level": "MODERATE_RISK",
                "message": "Moderate instability - proceed with extreme caution and monitoring",
                "confidence": "medium"
            }
        elif risk_score >= 15:
            return {
                "level": "LOW_RISK",
                "message": "Some instability present - monitor weather closely",
                "confidence": "medium"
            }
        else:
            return {
                "level": "STABLE",
                "message": "Atmospheric conditions stable for drying",
                "confidence": "high"
            }

def enhanced_kelp_drying_forecast(lat, lon, date):
    """Generate enhanced kelp drying forecast with atmospheric stability"""
    
    analyzer = AtmosphericStabilityAnalyzer()
    
    # Get enhanced forecast data
    forecast_data = analyzer.get_enhanced_forecast(lat, lon, date)
    if not forecast_data:
        return None
    
    hourly = forecast_data["hourly"]
    
    # Analyze atmospheric stability
    stability_analysis = analyzer.analyze_stability_risk(hourly)
    
    # Traditional weather analysis
    work_hours = slice(6, 17)
    avg_temp = sum(hourly["temperature_2m"][work_hours]) / 11
    avg_humidity = sum(hourly["relative_humidity_2m"][work_hours]) / 11
    avg_wind = sum(hourly["wind_speed_10m"][work_hours]) / 11
    avg_cloud = sum(hourly["cloud_cover"][work_hours]) / 11
    max_precip_prob = max(hourly["precipitation_probability"][work_hours])
    total_precip = sum(hourly["precipitation"][work_hours])
    
    # Enhanced drying score incorporating stability
    base_drying_score = calculate_base_drying_score(
        avg_temp, avg_humidity, avg_wind, avg_cloud, max_precip_prob, total_precip
    )
    
    # Apply stability penalty
    instability_penalty = min(30, stability_analysis["instability_risk"] * 0.3)
    final_drying_score = max(0, base_drying_score - instability_penalty)
    
    # Generate comprehensive recommendation
    if stability_analysis["recommendation"]["level"] in ["AVOID_DRYING", "HIGH_RISK"]:
        final_recommendation = stability_analysis["recommendation"]["message"]
        recommendation_level = "AVOID"
    elif final_drying_score >= 70:
        final_recommendation = "Good drying conditions with stable atmosphere"
        recommendation_level = "GOOD"
    elif final_drying_score >= 50:
        final_recommendation = "Fair conditions but monitor atmospheric stability"
        recommendation_level = "FAIR"
    else:
        final_recommendation = "Poor conditions - atmospheric instability adds significant risk"
        recommendation_level = "POOR"
    
    return {
        "date": date,
        "location": {"lat": lat, "lon": lon},
        "traditional_weather": {
            "temperature": avg_temp,
            "humidity": avg_humidity,
            "wind_speed": avg_wind,
            "cloud_cover": avg_cloud,
            "precipitation_probability": max_precip_prob,
            "precipitation_total": total_precip
        },
        "atmospheric_stability": stability_analysis,
        "drying_assessment": {
            "base_score": base_drying_score,
            "stability_penalty": instability_penalty,
            "final_score": final_drying_score,
            "recommendation": final_recommendation,
            "recommendation_level": recommendation_level
        },
        "all_warnings": stability_analysis["stability_warnings"]
    }

def calculate_base_drying_score(temp, humidity, wind, cloud, precip_prob, precip_total):
    """Calculate base drying score from traditional weather parameters"""
    
    score = 0
    
    # Temperature factor
    if temp >= 20:
        score += 20
    elif temp >= 15:
        score += 15
    elif temp >= 10:
        score += 10
    
    # Humidity factor
    if humidity < 60:
        score += 25
    elif humidity < 75:
        score += 15
    elif humidity < 85:
        score += 5
    
    # Wind factor
    if wind >= 4:
        score += 20
    elif wind >= 2:
        score += 15
    elif wind >= 1:
        score += 10
    
    # Cloud cover factor
    if cloud < 30:
        score += 20
    elif cloud < 60:
        score += 15
    elif cloud < 80:
        score += 10
    
    # Precipitation penalty
    if precip_prob > 70:
        score -= 30
    elif precip_prob > 50:
        score -= 20
    elif precip_prob > 30:
        score -= 10
    
    if precip_total > 2:
        score -= 25
    elif precip_total > 0.5:
        score -= 15
    elif precip_total > 0.1:
        score -= 5
    
    return max(0, min(100, score))

if __name__ == "__main__":
    # Test with August 10th data
    result = enhanced_kelp_drying_forecast(45.2065, 141.1368, "2025-08-10")
    
    if result:
        print("Enhanced Kelp Drying Forecast")
        print("="*50)
        print(f"Date: {result['date']}")
        print(f"Location: {result['location']['lat']}, {result['location']['lon']}")
        print()
        
        print("Traditional Weather Metrics:")
        tw = result['traditional_weather']
        print(f"  Temperature: {tw['temperature']:.1f}°C")
        print(f"  Humidity: {tw['humidity']:.1f}%")
        print(f"  Wind Speed: {tw['wind_speed']:.1f} m/s")
        print(f"  Cloud Cover: {tw['cloud_cover']:.1f}%")
        print(f"  Precip Probability: {tw['precipitation_probability']:.0f}%")
        
        print("\nAtmospheric Stability Analysis:")
        stability = result['atmospheric_stability']
        print(f"  Max CAPE: {stability['stability_metrics']['max_cape']:.0f}")
        print(f"  Min Lifted Index: {stability['stability_metrics']['min_lifted_index']:.1f}")
        print(f"  Instability Risk: {stability['instability_risk']:.0f}/100")
        print(f"  Peak Risk Time: {stability['convection_timing']['peak_instability_hour']:02d}:00")
        
        print("\nWarnings:")
        for warning in result['all_warnings']:
            print(f"  WARNING: {warning}")
        
        print(f"\nFinal Assessment:")
        assessment = result['drying_assessment']
        print(f"  Base Score: {assessment['base_score']:.0f}/100")
        print(f"  Stability Penalty: -{assessment['stability_penalty']:.0f}")
        print(f"  Final Score: {assessment['final_score']:.0f}/100")
        print(f"  Recommendation: {assessment['recommendation']}")
    else:
        print("Failed to get forecast data")