#!/usr/bin/env python3
"""
Model Parameter Calibration System
Calibrate kelp drying model parameters using Rishiri Island historical data
"""

import pandas as pd
import requests
import json
import sys
import os
from datetime import datetime, timedelta
import numpy as np
from sklearn.metrics import accuracy_score, classification_report
import matplotlib.pyplot as plt

# Add current directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from kelp_drying_model import KelpDryingModel

class ModelParameterCalibrator:
    """昆布乾燥モデルのパラメータ較正システム"""
    
    def __init__(self):
        self.model = KelpDryingModel()
        self.historical_records = self.load_historical_records()
        self.location_coords = self.get_location_coordinates()
        
    def load_historical_records(self):
        """過去の乾燥記録を読み込み"""
        try:
            df = pd.read_csv('hoshiba_records.csv')
            # 成功/失敗のデータのみを抽出（中止は除く）
            df_filtered = df[df['result'].isin(['完全乾燥', '干したが完全には乾かせなかった（泣）'])].copy()
            df_filtered['success'] = df_filtered['result'] == '完全乾燥'
            return df_filtered
        except Exception as e:
            print(f"Error loading historical records: {e}")
            return pd.DataFrame()
    
    def get_location_coordinates(self):
        """干場の座標を推定（H_XXXX_YYYYから緯度経度を復元）"""
        coords = {}
        
        for _, record in self.historical_records.iterrows():
            name = record['name']
            if name.startswith('H_'):
                parts = name.split('_')
                if len(parts) == 3:
                    try:
                        lat_part = float(parts[1]) / 10000
                        lon_part = float(parts[2]) / 10000
                        lat = 45.0 + lat_part
                        lon = 141.0 + lon_part
                        coords[name] = {'lat': lat, 'lon': lon}
                    except ValueError:
                        # デフォルト座標（利尻島中心付近）
                        coords[name] = {'lat': 45.18, 'lon': 141.24}
                        
        return coords
    
    def get_historical_weather(self, date, location_coords):
        """指定日の気象データを取得"""
        params = {
            "latitude": location_coords["lat"],
            "longitude": location_coords["lon"],
            "start_date": date,
            "end_date": date,
            "hourly": "temperature_2m,relative_humidity_2m,wind_speed_10m,wind_direction_10m,cloud_cover",
            "timezone": "Asia/Tokyo"
        }
        
        try:
            response = requests.get("https://api.open-meteo.com/v1/forecast", params=params, timeout=10)
            if response.status_code == 200:
                return response.json()
        except Exception as e:
            print(f"Weather API error for {date}: {e}")
        return None
    
    def extract_work_hours_weather(self, weather_data):
        """作業時間（4-16時）の気象条件を抽出"""
        if not weather_data or 'hourly' not in weather_data:
            return None
            
        hourly = weather_data['hourly']
        work_slice = slice(4, 17)  # 4-16時
        
        try:
            work_weather = {
                'temperature_avg': np.mean(hourly['temperature_2m'][work_slice]),
                'humidity_avg': np.mean(hourly['relative_humidity_2m'][work_slice]),
                'wind_speed_avg': np.mean(hourly['wind_speed_10m'][work_slice]),
                'wind_direction_avg': np.mean(hourly['wind_direction_10m'][work_slice]),
                'cloud_cover_avg': np.mean(hourly['cloud_cover'][work_slice]),
                'hourly_data': []
            }
            
            # 時間別データ作成
            for i in range(12):  # 4-16時の12時間
                work_weather['hourly_data'].append({
                    'temperature': hourly['temperature_2m'][4+i],
                    'relative_humidity': hourly['relative_humidity_2m'][4+i],
                    'wind_speed': hourly['wind_speed_10m'][4+i],
                    'time_step': 3600
                })
            
            return work_weather
        except (IndexError, KeyError) as e:
            print(f"Error extracting work hours weather: {e}")
            return None
    
    def simulate_terrain_effects(self, location_name, base_weather):
        """地形効果のシミュレーション"""
        # 簡易地形判定（実際のterrain_database.pyと整合性を保つ）
        corrections = {
            'temperature_correction': 0,
            'humidity_correction': 0,
            'wind_speed_correction': 0,
            'is_forest': False,
            'elevation': 0
        }
        
        # 座標から地形を推定
        if location_name in self.location_coords:
            coords = self.location_coords[location_name]
            lat, lon = coords['lat'], coords['lon']
            
            # 利尻山からの距離で標高を推定
            center_lat, center_lon = 45.1821, 141.2421
            distance = ((lat - center_lat)**2 + (lon - center_lon)**2)**0.5 * 111000
            
            if distance < 5000:
                elevation = max(0, 200 - (distance - 2000) * 0.05)
                if elevation > 100:
                    corrections['is_forest'] = True
                    corrections['wind_speed_correction'] = -2.5
                    corrections['humidity_correction'] = 10
                corrections['elevation'] = elevation
                corrections['temperature_correction'] = -elevation * 0.006
        
        # 補正を適用
        corrected_weather = base_weather.copy()
        corrected_weather['temperature_avg'] += corrections['temperature_correction']
        corrected_weather['humidity_avg'] += corrections['humidity_correction']
        corrected_weather['wind_speed_avg'] = max(0, corrected_weather['wind_speed_avg'] + corrections['wind_speed_correction'])
        
        # 時間別データも補正
        for hour_data in corrected_weather['hourly_data']:
            hour_data['temperature'] += corrections['temperature_correction']
            hour_data['relative_humidity'] = min(100, hour_data['relative_humidity'] + corrections['humidity_correction'])
            hour_data['wind_speed'] = max(0, hour_data['wind_speed'] + corrections['wind_speed_correction'])
        
        return corrected_weather, corrections
    
    def calibrate_parameters(self):
        """実際のデータを使ってパラメータを較正"""
        
        print("=== Model Parameter Calibration ===")
        print(f"Historical records: {len(self.historical_records)} entries")
        print(f"Location coordinates: {len(self.location_coords)} sites")
        
        calibration_data = []
        
        # 成功/失敗のケースについて気象データを収集
        success_cases = []
        failure_cases = []
        
        for _, record in self.historical_records.iterrows():
            date = record['date']
            location = record['name']
            success = record['success']
            
            if location not in self.location_coords:
                continue
                
            print(f"\nProcessing: {date} at {location} ({'Success' if success else 'Failure'})")
            
            # 気象データ取得
            coords = self.location_coords[location]
            weather_data = self.get_historical_weather(date, coords)
            
            if weather_data is None:
                print(f"  No weather data available")
                continue
            
            # 作業時間の気象条件抽出
            work_weather = self.extract_work_hours_weather(weather_data)
            if work_weather is None:
                print(f"  Failed to extract work hours weather")
                continue
            
            # 地形補正適用
            corrected_weather, terrain_info = self.simulate_terrain_effects(location, work_weather)
            
            # 乾燥モデルで評価
            try:
                drying_evaluation = self.model.evaluate_drying_conditions(corrected_weather['hourly_data'])
                
                case_data = {
                    'date': date,
                    'location': location,
                    'actual_success': success,
                    'predicted_condition': drying_evaluation['condition'],
                    'predicted_score': drying_evaluation['score'],
                    'weather': corrected_weather,
                    'terrain': terrain_info,
                    'model_prediction': drying_evaluation
                }
                
                calibration_data.append(case_data)
                
                if success:
                    success_cases.append(case_data)
                else:
                    failure_cases.append(case_data)
                
                print(f"  Weather: T={corrected_weather['temperature_avg']:.1f}°C, "
                      f"H={corrected_weather['humidity_avg']:.1f}%, "
                      f"W={corrected_weather['wind_speed_avg']:.1f}m/s")
                print(f"  Terrain: {terrain_info}")
                print(f"  Model: {drying_evaluation['condition']} (Score: {drying_evaluation['score']})")
                print(f"  Actual: {'Success' if success else 'Failure'}")
                
            except Exception as e:
                print(f"  Model evaluation error: {e}")
                continue
        
        return self.analyze_calibration_results(calibration_data, success_cases, failure_cases)
    
    def analyze_calibration_results(self, all_data, success_cases, failure_cases):
        """較正結果の分析"""
        
        print(f"\n{'='*60}")
        print("CALIBRATION ANALYSIS RESULTS")
        print(f"{'='*60}")
        
        if not all_data:
            print("No valid calibration data available")
            return None
        
        print(f"Total cases analyzed: {len(all_data)}")
        print(f"Success cases: {len(success_cases)}")
        print(f"Failure cases: {len(failure_cases)}")
        
        # 予測精度の評価
        actual_results = [case['actual_success'] for case in all_data]
        
        # 現在のモデルでの予測（Good以上で成功と判定）
        predicted_results = [case['predicted_score'] >= 4 for case in all_data]
        
        accuracy = accuracy_score(actual_results, predicted_results)
        print(f"\nCurrent model accuracy: {accuracy*100:.1f}%")
        
        # 成功/失敗ケースの特徴分析
        print(f"\n--- SUCCESS CASES ANALYSIS ---")
        if success_cases:
            success_scores = [case['predicted_score'] for case in success_cases]
            success_temps = [case['weather']['temperature_avg'] for case in success_cases]
            success_humidity = [case['weather']['humidity_avg'] for case in success_cases]
            success_wind = [case['weather']['wind_speed_avg'] for case in success_cases]
            
            print(f"Average model score: {np.mean(success_scores):.2f}")
            print(f"Temperature range: {np.min(success_temps):.1f}-{np.max(success_temps):.1f}°C (avg: {np.mean(success_temps):.1f}°C)")
            print(f"Humidity range: {np.min(success_humidity):.1f}-{np.max(success_humidity):.1f}% (avg: {np.mean(success_humidity):.1f}%)")
            print(f"Wind speed range: {np.min(success_wind):.1f}-{np.max(success_wind):.1f}m/s (avg: {np.mean(success_wind):.1f}m/s)")
        
        print(f"\n--- FAILURE CASES ANALYSIS ---")
        if failure_cases:
            failure_scores = [case['predicted_score'] for case in failure_cases]
            failure_temps = [case['weather']['temperature_avg'] for case in failure_cases]
            failure_humidity = [case['weather']['humidity_avg'] for case in failure_cases]
            failure_wind = [case['weather']['wind_speed_avg'] for case in failure_cases]
            
            print(f"Average model score: {np.mean(failure_scores):.2f}")
            print(f"Temperature range: {np.min(failure_temps):.1f}-{np.max(failure_temps):.1f}°C (avg: {np.mean(failure_temps):.1f}°C)")
            print(f"Humidity range: {np.min(failure_humidity):.1f}-{np.max(failure_humidity):.1f}% (avg: {np.mean(failure_humidity):.1f}%)")
            print(f"Wind speed range: {np.min(failure_wind):.1f}-{np.max(failure_wind):.1f}m/s (avg: {np.mean(failure_wind):.1f}m/s)")
        
        # パラメータ調整提案
        print(f"\n--- PARAMETER ADJUSTMENT RECOMMENDATIONS ---")
        
        # 閾値の最適化
        optimal_threshold = self.find_optimal_threshold(all_data)
        print(f"Recommended score threshold: {optimal_threshold:.2f} (current: 4.0)")
        
        # 地形効果の検証
        forest_cases = [case for case in all_data if case['terrain']['is_forest']]
        non_forest_cases = [case for case in all_data if not case['terrain']['is_forest']]
        
        if forest_cases and non_forest_cases:
            forest_success_rate = sum(case['actual_success'] for case in forest_cases) / len(forest_cases)
            non_forest_success_rate = sum(case['actual_success'] for case in non_forest_cases) / len(non_forest_cases)
            
            print(f"Forest area success rate: {forest_success_rate*100:.1f}% ({len(forest_cases)} cases)")
            print(f"Non-forest success rate: {non_forest_success_rate*100:.1f}% ({len(non_forest_cases)} cases)")
            
            if forest_success_rate < non_forest_success_rate:
                print("CONFIRMED: Forest areas show reduced drying success (terrain correction working)")
            else:
                print("ATTENTION: Forest correction may need adjustment")
        
        # 詳細ケース分析の出力
        self.output_detailed_analysis(all_data)
        
        return {
            'total_cases': len(all_data),
            'accuracy': accuracy,
            'optimal_threshold': optimal_threshold,
            'success_cases': success_cases,
            'failure_cases': failure_cases,
            'calibration_data': all_data
        }
    
    def find_optimal_threshold(self, data):
        """最適なスコア閾値を求める"""
        scores = [case['predicted_score'] for case in data]
        actual = [case['actual_success'] for case in data]
        
        best_threshold = 4.0
        best_accuracy = 0
        
        for threshold in np.arange(0, 6, 0.1):
            predicted = [score >= threshold for score in scores]
            accuracy = accuracy_score(actual, predicted)
            
            if accuracy > best_accuracy:
                best_accuracy = accuracy
                best_threshold = threshold
        
        return best_threshold
    
    def output_detailed_analysis(self, data):
        """詳細分析結果をファイル出力"""
        
        output_file = "model_calibration_detailed_analysis.json"
        
        # JSON出力用にデータを整理
        output_data = {
            "calibration_date": datetime.now().isoformat(),
            "total_cases": len(data),
            "cases": []
        }
        
        for case in data:
            case_info = {
                "date": case['date'],
                "location": case['location'],
                "actual_success": case['actual_success'],
                "predicted_condition": case['predicted_condition'],
                "predicted_score": case['predicted_score'],
                "weather_conditions": {
                    "temperature_avg": round(case['weather']['temperature_avg'], 1),
                    "humidity_avg": round(case['weather']['humidity_avg'], 1),
                    "wind_speed_avg": round(case['weather']['wind_speed_avg'], 1),
                    "cloud_cover_avg": round(case['weather']['cloud_cover_avg'], 1)
                },
                "terrain_effects": case['terrain'],
                "prediction_correct": (case['predicted_score'] >= 4) == case['actual_success']
            }
            output_data["cases"].append(case_info)
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2)
        
        print(f"\nDetailed analysis saved to: {output_file}")

def main():
    """メイン実行"""
    calibrator = ModelParameterCalibrator()
    
    if calibrator.historical_records.empty:
        print("No historical records available for calibration")
        return
    
    results = calibrator.calibrate_parameters()
    
    if results:
        print(f"\n{'='*60}")
        print("CALIBRATION SUMMARY")
        print(f"{'='*60}")
        print(f"Total cases processed: {results['total_cases']}")
        print(f"Current model accuracy: {results['accuracy']*100:.1f}%")
        print(f"Recommended threshold: {results['optimal_threshold']:.2f}")
        
        if results['accuracy'] >= 0.8:
            print("EXCELLENT: Model shows high accuracy with current parameters")
        elif results['accuracy'] >= 0.6:
            print("GOOD: Model performance acceptable, minor adjustments recommended")
        else:
            print("NEEDS IMPROVEMENT: Significant parameter adjustments required")

if __name__ == "__main__":
    main()