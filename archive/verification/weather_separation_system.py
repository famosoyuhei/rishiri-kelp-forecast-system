#!/usr/bin/env python3
"""
Weather Separation System
Separate storm conditions from normal kelp drying conditions
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from recalibrated_rishiri_model import RecalibratedRishiriModel
import json

class WeatherSeparationSystem:
    """嵐天候と通常天候の分離システム"""
    
    def __init__(self):
        self.normal_model = RecalibratedRishiriModel()
        
        # 天候分類閾値
        self.separation_thresholds = {
            "storm_wind_avg": 20.0,      # 嵐判定平均風速 (m/s)
            "storm_wind_max": 30.0,      # 嵐判定最大風速 (m/s)
            "storm_gust": 40.0,          # 嵐判定突風 (m/s)
            "severe_weather_hours": 3,   # 嵐判定悪天候時間 (hours)
            "normal_wind_max": 20.0,     # 通常作業最大風速 (m/s)
            "marginal_wind_min": 15.0    # 注意作業最低風速 (m/s)
        }
        
        # 分離された予測システム
        self.prediction_systems = {
            "normal": {
                "name": "Normal Kelp Drying Model",
                "description": "Optimized for typical working conditions (3-20 m/s wind)",
                "use_cases": ["Daily kelp drying forecasts", "Work planning", "Optimal timing prediction"]
            },
            "marginal": {
                "name": "Marginal Conditions Model", 
                "description": "For borderline conditions requiring careful monitoring",
                "use_cases": ["Risk assessment", "Experience-based decisions", "Backup day planning"]
            },
            "storm": {
                "name": "Storm Warning System",
                "description": "Extreme weather detection (>20 m/s wind, hurricanes)",
                "use_cases": ["Safety alerts", "Work suspension", "Equipment protection"]
            }
        }
    
    def classify_weather_conditions(self, weather_data):
        """
        天候条件の分類
        
        Args:
            weather_data: 天候データ
        
        Returns:
            分類結果
        """
        
        wind_avg = weather_data.get('wind_speed_avg', 0)
        wind_max = weather_data.get('wind_speed_max', wind_avg * 1.3)
        wind_gust = weather_data.get('wind_gust_max', wind_max * 1.5)
        severe_hours = weather_data.get('severe_weather_hours', 0)
        
        # 嵐条件判定
        if (wind_avg >= self.separation_thresholds["storm_wind_avg"] or
            wind_max >= self.separation_thresholds["storm_wind_max"] or 
            wind_gust >= self.separation_thresholds["storm_gust"] or
            severe_hours >= self.separation_thresholds["severe_weather_hours"]):
            
            category = "storm"
            risk_level = "extreme"
            work_recommendation = "Suspend all kelp drying operations"
            
        # 限界条件判定
        elif wind_avg >= self.separation_thresholds["marginal_wind_min"]:
            category = "marginal"
            risk_level = "moderate"
            work_recommendation = "Monitor closely - experienced operators only"
            
        # 通常条件
        else:
            category = "normal"
            risk_level = "low"
            work_recommendation = "Normal kelp drying operations possible"
        
        return {
            "category": category,
            "risk_level": risk_level,
            "work_recommendation": work_recommendation,
            "classification_reasons": self.get_classification_reasons(wind_avg, wind_max, wind_gust, severe_hours),
            "applicable_model": self.prediction_systems[category]["name"],
            "wind_metrics": {
                "average": wind_avg,
                "maximum": wind_max, 
                "gust": wind_gust,
                "severe_hours": severe_hours
            }
        }
    
    def get_classification_reasons(self, wind_avg, wind_max, wind_gust, severe_hours):
        """分類理由の生成"""
        reasons = []
        
        if wind_avg >= 20:
            reasons.append(f"Average wind {wind_avg:.1f} m/s exceeds safe working limit")
        if wind_max >= 30:
            reasons.append(f"Maximum wind {wind_max:.1f} m/s indicates storm conditions")
        if wind_gust >= 40:
            reasons.append(f"Wind gusts {wind_gust:.1f} m/s pose safety risks")
        if severe_hours >= 3:
            reasons.append(f"Extended severe weather ({severe_hours}h) disrupts operations")
        if 15 <= wind_avg < 20:
            reasons.append(f"Strong winds ({wind_avg:.1f} m/s) require experienced handling")
        if wind_avg < 15 and wind_max < 20:
            reasons.append(f"Moderate winds ({wind_avg:.1f} m/s) suitable for normal operations")
        
        return reasons
    
    def generate_separated_forecast(self, weather_data):
        """
        分離された予報システムでの予測
        
        Args:
            weather_data: 天候データ
        
        Returns:
            天候分類別予報
        """
        
        classification = self.classify_weather_conditions(weather_data)
        
        if classification["category"] == "storm":
            return self.generate_storm_warning(weather_data, classification)
        elif classification["category"] == "marginal":
            return self.generate_marginal_forecast(weather_data, classification)
        else:
            return self.generate_normal_forecast(weather_data, classification)
    
    def generate_storm_warning(self, weather_data, classification):
        """嵐警報の生成"""
        
        wind_metrics = classification["wind_metrics"]
        
        # 嵐強度分類
        if wind_metrics["average"] >= 32.7:
            storm_intensity = "Hurricane"
            danger_level = "Extreme"
        elif wind_metrics["average"] >= 28.5:
            storm_intensity = "Violent Storm"
            danger_level = "Severe"
        elif wind_metrics["average"] >= 24.5:
            storm_intensity = "Storm"
            danger_level = "High"
        else:
            storm_intensity = "Strong Gale"
            danger_level = "Moderate"
        
        return {
            "forecast_type": "storm_warning",
            "classification": classification,
            "storm_details": {
                "intensity": storm_intensity,
                "danger_level": danger_level,
                "wind_description": f"Average {wind_metrics['average']:.1f} m/s, gusts up to {wind_metrics['gust']:.1f} m/s"
            },
            "recommendations": [
                "DO NOT attempt kelp drying operations",
                "Secure all equipment and materials",
                "Monitor weather updates frequently",
                "Wait for conditions to improve below 20 m/s average wind"
            ],
            "safety_alerts": [
                "Extreme wind conditions present",
                "Risk of equipment damage",
                "Personnel safety priority"
            ],
            "estimated_duration": self.estimate_storm_duration(weather_data)
        }
    
    def generate_marginal_forecast(self, weather_data, classification):
        """限界条件予報の生成"""
        
        # 通常モデルを使用するが注意事項を追加
        base_evaluation = self.normal_model.evaluate_realistic_drying_conditions(weather_data)
        
        return {
            "forecast_type": "marginal_conditions",
            "classification": classification,
            "drying_evaluation": base_evaluation,
            "special_considerations": [
                "Strong wind conditions - experienced operators recommended",
                "Monitor wind speed changes throughout the day",
                "Have backup indoor drying ready",
                "Check equipment security frequently"
            ],
            "timing_recommendations": [
                "Start early when winds are typically calmer",
                "Complete critical phases before peak wind hours",
                "Be prepared to suspend operations if winds increase"
            ],
            "risk_factors": [
                f"Wind speeds {weather_data.get('wind_speed_avg', 15):.1f} m/s approach upper limits",
                "Conditions may deteriorate rapidly",
                "Equipment stress from strong winds"
            ]
        }
    
    def generate_normal_forecast(self, weather_data, classification):
        """通常条件予報の生成"""
        
        # 再校正モデルで評価
        evaluation = self.normal_model.evaluate_realistic_drying_conditions(weather_data)
        
        return {
            "forecast_type": "normal_conditions",
            "classification": classification,
            "drying_evaluation": evaluation,
            "optimal_timing": self.suggest_optimal_timing(weather_data),
            "work_recommendations": [
                "Normal kelp drying operations recommended",
                "Follow standard procedures",
                "Monitor conditions as usual"
            ],
            "efficiency_notes": [
                f"Wind conditions ({weather_data.get('wind_speed_avg', 10):.1f} m/s) support good drying",
                "Standard work schedule applicable",
                "Good conditions for quality kelp production"
            ]
        }
    
    def suggest_optimal_timing(self, weather_data):
        """最適タイミングの提案"""
        
        wind_speed = weather_data.get('wind_speed_avg', 10)
        humidity = weather_data.get('humidity_avg', 80)
        
        if wind_speed >= 12 and humidity <= 80:
            return "Excellent timing - start early for full day drying"
        elif wind_speed >= 8:
            return "Good timing - normal work schedule recommended"
        else:
            return "Fair timing - monitor wind pickup during day"
    
    def estimate_storm_duration(self, weather_data):
        """嵐継続時間の推定"""
        
        severe_hours = weather_data.get('severe_weather_hours', 0)
        wind_avg = weather_data.get('wind_speed_avg', 25)
        
        if wind_avg >= 35:
            return "12-24 hours (major storm system)"
        elif wind_avg >= 30:
            return "6-12 hours (significant storm)"
        else:
            return "3-6 hours (passing storm)"
    
    def test_separation_system(self):
        """分離システムのテスト"""
        
        print("=== Weather Separation System Test ===")
        print("Testing classification and forecasting for different weather conditions")
        print()
        
        # テストケース
        test_cases = [
            {
                "name": "Normal Summer Day",
                "weather": {"wind_speed_avg": 12.5, "humidity_avg": 78, "temperature_avg": 20},
                "expected_category": "normal"
            },
            {
                "name": "Strong Wind Day", 
                "weather": {"wind_speed_avg": 17.2, "humidity_avg": 75, "temperature_avg": 18},
                "expected_category": "marginal"
            },
            {
                "name": "Storm Conditions",
                "weather": {"wind_speed_avg": 28.5, "wind_speed_max": 35.2, "wind_gust_max": 45.8, "severe_weather_hours": 4},
                "expected_category": "storm"
            },
            {
                "name": "Hurricane Conditions",
                "weather": {"wind_speed_avg": 42.1, "wind_speed_max": 48.7, "wind_gust_max": 67.3, "severe_weather_hours": 8},
                "expected_category": "storm"
            }
        ]
        
        test_results = []
        
        for test_case in test_cases:
            print(f"Testing: {test_case['name']}")
            
            forecast = self.generate_separated_forecast(test_case['weather'])
            classification = forecast['classification']
            
            print(f"  Category: {classification['category'].upper()}")
            print(f"  Risk Level: {classification['risk_level']}")
            print(f"  Model: {classification['applicable_model']}")
            print(f"  Recommendation: {classification['work_recommendation']}")
            
            # 予測精度チェック
            correct_classification = classification['category'] == test_case['expected_category']
            print(f"  Classification: {'CORRECT' if correct_classification else 'INCORRECT'}")
            
            test_results.append({
                "test_case": test_case['name'],
                "weather_data": test_case['weather'],
                "forecast": forecast,
                "correct_classification": correct_classification
            })
            
            print()
        
        return self.generate_test_report(test_results)
    
    def generate_test_report(self, test_results):
        """テストレポート生成"""
        
        print("=" * 60)
        print("WEATHER SEPARATION SYSTEM TEST REPORT")
        print("=" * 60)
        
        total_tests = len(test_results)
        correct_classifications = sum(1 for result in test_results if result['correct_classification'])
        accuracy = (correct_classifications / total_tests * 100) if total_tests > 0 else 0
        
        print(f"Total test cases: {total_tests}")
        print(f"Correct classifications: {correct_classifications}")
        print(f"Classification accuracy: {accuracy:.1f}%")
        print()
        
        # カテゴリ別分析
        categories = {}
        for result in test_results:
            category = result['forecast']['classification']['category']
            categories[category] = categories.get(category, 0) + 1
        
        print("CATEGORY DISTRIBUTION:")
        for category, count in categories.items():
            print(f"  {category.capitalize()}: {count} cases")
        
        print()
        print("SYSTEM BENEFITS:")
        print("- Separates impossible storm conditions from workable weather")
        print("- Provides appropriate models for each weather type")
        print("- Improves safety through clear storm warnings")
        print("- Maintains accuracy for realistic kelp drying conditions")
        print("- Eliminates confusion from hurricane-level predictions")
        
        return {
            "total_tests": total_tests,
            "correct_classifications": correct_classifications,
            "accuracy_percentage": accuracy,
            "category_distribution": categories,
            "detailed_results": test_results
        }

def main():
    """メイン実行"""
    separation_system = WeatherSeparationSystem()
    
    # 分離システムテスト実行
    results = separation_system.test_separation_system()
    
    # 結果をJSONで保存
    output_file = "weather_separation_system_results.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    print(f"\nDetailed test results saved to: {output_file}")

if __name__ == "__main__":
    main()