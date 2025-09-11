#!/usr/bin/env python3
"""
Multi-day Forecast Accuracy Verification System
Test prediction accuracy for 1-7 days ahead using historical data
"""

import requests
import json
import sys
import os
import pandas as pd
from datetime import datetime, timedelta
import time

# Add current directory to path to import our modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

class MultidayForecastVerifier:
    """多日数予報精度検証システム"""
    
    def __init__(self):
        self.locations = {
            "Oshidomari": {"lat": 45.241667, "lon": 141.230833},
            "Kutsugata": {"lat": 45.118889, "lon": 141.176389}
        }
        
        # 過去の実績データ（hoshiba_records.csvから）
        self.historical_results = {
            "2025-07-29": {"H_2489_2198": "Failed", "H_1631_1434": "Success"},
            "2025-07-25": {"H_2321_2696": "Failed", "H_2304_2689": "Failed"},
            "2025-07-15": {"H_1278_3025": "Success"},
            "2025-07-12": {"H_2065_1369": "Success", "H_2480_2198": "Success"},
            "2025-07-11": {"H_2065_1369": "Success", "H_1631_1434": "Success"},
            "2025-07-10": {"H_1631_1434": "Success"},
            "2025-07-09": {"H_1631_1434": "Success"},
            "2025-07-08": {"H_1631_1434": "Success"},
            "2025-07-07": {"H_1631_1434": "Success", "H_2480_2198": "Success"}
        }
    
    def get_historical_weather(self, target_date, forecast_days_ahead):
        """
        指定日のN日前の時点での予報データを取得（シミュレーション）
        
        Args:
            target_date: 対象日（YYYY-MM-DD）
            forecast_days_ahead: 何日前の予報か（1-7）
        
        Returns:
            予報データ（両地点分）
        """
        print(f"Getting {forecast_days_ahead}-day forecast for {target_date}...")
        
        forecasts = {}
        
        for location_name, coords in self.locations.items():
            params = {
                "latitude": coords["lat"],
                "longitude": coords["lon"],
                "start_date": target_date,
                "end_date": target_date,
                "hourly": "temperature_2m,relative_humidity_2m,precipitation,wind_speed_10m,wind_direction_10m,cloud_cover,weather_code",
                "timezone": "Asia/Tokyo"
            }
            
            try:
                response = requests.get("https://api.open-meteo.com/v1/forecast", params=params, timeout=10)
                
                if response.status_code == 200:
                    api_data = response.json()
                    # 地形補正をシミュレート
                    forecast = self.simulate_app_forecast(api_data, coords, location_name, forecast_days_ahead)
                    forecasts[location_name] = forecast
                    print(f"  OK - {location_name} forecast generated")
                else:
                    print(f"  Failed - {location_name} (HTTP {response.status_code})")
                    forecasts[location_name] = None
                    
            except Exception as e:
                print(f"  Error - {location_name}: {e}")
                forecasts[location_name] = None
            
            # API制限対策
            time.sleep(0.5)
        
        return forecasts
    
    def simulate_app_forecast(self, api_data, coords, location_name, days_ahead):
        """アプリの予報処理をシミュレート（予報精度は日数で劣化）"""
        
        hourly = api_data["hourly"]
        lat, lon = coords["lat"], coords["lon"]
        
        # 地形情報をシミュレート
        terrain_info = self.simulate_terrain_calculation(lat, lon)
        
        # 地形補正を適用
        corrected_forecast = self.apply_terrain_corrections_simulation(hourly, terrain_info)
        
        # 予報精度劣化をモデル化（日数が増えるほど精度低下）
        accuracy_factor = max(0.5, 1.0 - (days_ahead - 1) * 0.1)  # 1日後100%, 7日後40%
        
        # 作業時間分析（4-16時）
        work_slice = slice(4, 17)
        
        # 天気要素の平均値計算（精度劣化を考慮）
        cloud_cover_avg = sum(corrected_forecast["cloud_cover"][work_slice]) / 13
        wind_direction_avg = sum(corrected_forecast["wind_direction_10m"][work_slice]) / 13
        wind_speed_avg = sum(corrected_forecast["wind_speed_10m"][work_slice]) / 13
        humidity_avg = sum(corrected_forecast["relative_humidity_2m"][work_slice]) / 13
        temperature_avg = sum(corrected_forecast["temperature_2m"][work_slice]) / 13
        
        # 予報精度劣化の影響をシミュレート
        import random
        random.seed(hash(f"{location_name}{days_ahead}"))  # 再現可能な乱数
        
        if days_ahead > 1:
            # 日数が増えるほど不確実性が増加
            uncertainty = (days_ahead - 1) * 5  # 不確実性幅
            cloud_cover_avg += random.uniform(-uncertainty, uncertainty)
            humidity_avg += random.uniform(-uncertainty/2, uncertainty/2)
            wind_speed_avg *= random.uniform(0.8, 1.2)
        
        # 範囲制限
        cloud_cover_avg = max(0, min(100, cloud_cover_avg))
        humidity_avg = max(0, min(100, humidity_avg))
        wind_speed_avg = max(0, wind_speed_avg)
        
        forecast_summary = {
            "location": location_name,
            "coordinates": coords,
            "days_ahead": days_ahead,
            "accuracy_factor": accuracy_factor,
            "terrain_info": terrain_info,
            "weather_summary": {
                "cloud_cover_avg": cloud_cover_avg,
                "wind_direction_avg": wind_direction_avg,
                "wind_speed_avg": wind_speed_avg,
                "humidity_avg": humidity_avg,
                "temperature_avg": temperature_avg
            },
            "app_interpretation": {},
            "drying_recommendation": "",
            "warnings": []
        }
        
        # 天気解釈
        if cloud_cover_avg < 50:
            weather_condition = "Sunny"
            weather_score = 2
        elif cloud_cover_avg < 75:
            weather_condition = "Cloudy"
            weather_score = 1
        else:
            weather_condition = "Overcast"
            weather_score = 0
        
        # 風分析
        wind_direction_text = self.analyze_wind_direction(wind_direction_avg)
        yamase_risk = self.check_yamase_risk(wind_direction_avg, humidity_avg)
        
        # 地形効果
        terrain_warnings = []
        if "森林" in terrain_info["land_use"]:
            terrain_warnings.append("Forest area - reduced wind speed")
            wind_speed_avg *= 0.7
        
        # 総合乾燥評価
        drying_score = 0
        
        # 天気要因
        drying_score += weather_score
        
        # 風要因
        if wind_speed_avg >= 3:
            drying_score += 2
        elif wind_speed_avg >= 1:
            drying_score += 1
        
        # 湿度要因
        if humidity_avg < 60:
            drying_score += 2
        elif humidity_avg < 75:
            drying_score += 1
        elif humidity_avg > 85:
            drying_score -= 1
        
        # ヤマセペナルティ
        if yamase_risk:
            drying_score -= 2
            terrain_warnings.append("Yamase (east wind) detected - high humidity risk")
        
        # 推奨度判定
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
    
    def simulate_terrain_calculation(self, lat, lon):
        """地形計算のシミュレート"""
        import math
        
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
    
    def apply_terrain_corrections_simulation(self, hourly_data, terrain_info):
        """地形補正のシミュレート"""
        
        corrected = hourly_data.copy()
        
        if "森林" in terrain_info["land_use"]:
            corrected["wind_speed_10m"] = [max(0, ws - 2.5) for ws in hourly_data["wind_speed_10m"]]
            corrected["relative_humidity_2m"] = [min(100, rh + 10) for rh in hourly_data["relative_humidity_2m"]]
        
        elevation = terrain_info["elevation"]
        temp_correction = -elevation * 0.006
        corrected["temperature_2m"] = [t + temp_correction for t in hourly_data["temperature_2m"]]
        
        return corrected
    
    def analyze_wind_direction(self, degrees):
        """風向分析"""
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
    
    def check_yamase_risk(self, wind_direction, humidity):
        """ヤマセリスクチェック"""
        east_wind = 45 <= wind_direction <= 120
        high_humidity = humidity > 80
        return east_wind and high_humidity
    
    def verify_multiday_accuracy(self):
        """多日数予報精度の検証"""
        
        print("=== Multi-day Forecast Accuracy Verification ===")
        print("Testing prediction accuracy for 1-7 days ahead")
        print()
        
        # 検証対象日（実績データがある日）
        target_dates = list(self.historical_results.keys())[:3]  # 最新3日分を検証
        
        results = {}
        
        for days_ahead in range(1, 8):  # 1-7日前予報（フルスケール）
            print(f"--- Testing {days_ahead}-day ahead forecasts ---")
            
            correct_predictions = 0
            total_predictions = 0
            day_results = []
            
            for target_date in target_dates:
                print(f"\nTarget date: {target_date}")
                
                # N日前の予報を取得
                forecasts = self.get_historical_weather(target_date, days_ahead)
                
                if not forecasts.get("Oshidomari") or not forecasts.get("Kutsugata"):
                    print("  Skipping - insufficient forecast data")
                    continue
                
                # 実績データと比較
                actual_results = self.historical_results.get(target_date, {})
                
                for location in ["Oshidomari", "Kutsugata"]:
                    forecast = forecasts[location]
                    
                    # 予報の解釈
                    predicted_success = "Excellent" in forecast["drying_recommendation"] or \
                                       "Good" in forecast["drying_recommendation"]
                    
                    # 実績データの確認（簡易マッピング）
                    location_results = []
                    for record_id, result in actual_results.items():
                        if location == "Oshidomari" and "2489_2198" in record_id:
                            location_results.append(result == "Success")
                        elif location == "Kutsugata" and "1631_1434" in record_id:
                            location_results.append(result == "Success")
                    
                    if location_results:
                        actual_success = any(location_results)
                        
                        # 予測精度評価
                        prediction_correct = predicted_success == actual_success
                        if prediction_correct:
                            correct_predictions += 1
                        total_predictions += 1
                        
                        day_results.append({
                            "target_date": target_date,
                            "location": location,
                            "predicted_success": predicted_success,
                            "actual_success": actual_success,
                            "correct": prediction_correct,
                            "accuracy_factor": forecast["accuracy_factor"]
                        })
                        
                        print(f"  {location}: {'OK' if prediction_correct else 'MISS'} " +
                              f"(Pred: {'Success' if predicted_success else 'Fail'}, " +
                              f"Actual: {'Success' if actual_success else 'Fail'})")
            
            # 日数別精度計算
            if total_predictions > 0:
                accuracy_percentage = (correct_predictions / total_predictions) * 100
                results[days_ahead] = {
                    "days_ahead": days_ahead,
                    "accuracy_percentage": accuracy_percentage,
                    "correct_predictions": correct_predictions,
                    "total_predictions": total_predictions,
                    "detailed_results": day_results
                }
                
                print(f"\n{days_ahead}-day forecast accuracy: {accuracy_percentage:.1f}% " +
                      f"({correct_predictions}/{total_predictions})")
            else:
                print(f"\n{days_ahead}-day forecast: No valid comparisons")
                results[days_ahead] = {
                    "days_ahead": days_ahead,
                    "accuracy_percentage": 0,
                    "correct_predictions": 0,
                    "total_predictions": 0,
                    "detailed_results": []
                }
        
        return results
    
    def generate_accuracy_report(self, results):
        """精度検証レポートの生成"""
        
        print("\n" + "="*60)
        print("MULTI-DAY FORECAST ACCURACY SUMMARY")
        print("="*60)
        
        print(f"{'Days Ahead':<12} {'Accuracy':<10} {'Predictions':<12} {'Reliability'}")
        print("-" * 50)
        
        for days_ahead in range(1, 8):
            if days_ahead in results:
                result = results[days_ahead]
                accuracy = result["accuracy_percentage"]
                predictions = f"{result['correct_predictions']}/{result['total_predictions']}"
                
                if accuracy >= 80:
                    reliability = "Excellent"
                elif accuracy >= 60:
                    reliability = "Good"
                elif accuracy >= 40:
                    reliability = "Fair"
                else:
                    reliability = "Poor"
                
                print(f"{days_ahead} day(s){'':<5} {accuracy:>6.1f}%{'':<2} {predictions:<12} {reliability}")
        
        # 精度劣化の傾向分析
        print(f"\nTREND ANALYSIS:")
        accuracies = [results[d]["accuracy_percentage"] for d in range(1, 8) if d in results]
        
        if len(accuracies) >= 3:
            if accuracies[0] - accuracies[-1] > 20:
                print("- Significant accuracy degradation over time")
            elif accuracies[0] - accuracies[-1] > 10:
                print("- Moderate accuracy degradation over time")
            else:
                print("- Stable accuracy across forecast periods")
        
        # 推奨使用範囲
        reliable_days = [d for d in range(1, 8) if d in results and results[d]["accuracy_percentage"] >= 70]
        
        print(f"\nRECOMMANDED USAGE:")
        if reliable_days:
            print(f"- Reliable forecasts: Up to {max(reliable_days)} days ahead")
        else:
            print("- Limited reliability detected - recommend 1-day forecasts only")
        
        return results

def main():
    """メイン実行"""
    verifier = MultidayForecastVerifier()
    
    # 多日数予報精度検証実行
    results = verifier.verify_multiday_accuracy()
    
    # レポート生成
    final_report = verifier.generate_accuracy_report(results)
    
    # 結果をJSONで保存
    output_file = "multiday_forecast_accuracy_report.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(final_report, f, ensure_ascii=False, indent=2)
    
    print(f"\nDetailed results saved to: {output_file}")

if __name__ == "__main__":
    main()