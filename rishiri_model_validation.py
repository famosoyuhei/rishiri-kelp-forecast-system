#!/usr/bin/env python3
"""
Rishiri Model Validation System
Validate the Rishiri-specific model against historical data
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from model_parameter_calibration import ModelParameterCalibrator
from rishiri_kelp_model import RishiriKelpDryingModel

class RishiriModelValidator:
    """利尻島特化モデルの検証システム"""
    
    def __init__(self):
        self.calibrator = ModelParameterCalibrator()
        self.rishiri_model = RishiriKelpDryingModel()
    
    def validate_rishiri_model(self):
        """利尻島特化モデルで実際のデータを再評価"""
        
        print("=== Rishiri Model Validation ===")
        print("Testing Rishiri-specific model against historical data")
        print()
        
        # 過去の較正データを再利用
        calibration_data = []
        
        for _, record in self.calibrator.historical_records.iterrows():
            date = record['date']
            location = record['name']
            success = record['success']
            
            if location not in self.calibrator.location_coords:
                continue
                
            print(f"Processing: {date} at {location} ({'Success' if success else 'Failure'})")
            
            # 気象データ取得
            coords = self.calibrator.location_coords[location]
            weather_data = self.calibrator.get_historical_weather(date, coords)
            
            if weather_data is None:
                continue
            
            # 作業時間の気象条件抽出
            work_weather = self.calibrator.extract_work_hours_weather(weather_data)
            if work_weather is None:
                continue
            
            # 地形補正適用
            corrected_weather, terrain_info = self.calibrator.simulate_terrain_effects(location, work_weather)
            
            # 利尻島特化モデルで評価
            try:
                rishiri_evaluation = self.rishiri_model.evaluate_drying_conditions(corrected_weather, terrain_info)
                
                case_data = {
                    'date': date,
                    'location': location,
                    'actual_success': success,
                    'rishiri_score': rishiri_evaluation['score'],
                    'rishiri_condition': rishiri_evaluation['condition'],
                    'weather': corrected_weather,
                    'terrain': terrain_info
                }
                
                calibration_data.append(case_data)
                
                print(f"  Weather: T={corrected_weather['temperature_avg']:.1f}°C, "
                      f"H={corrected_weather['humidity_avg']:.1f}%, "
                      f"W={corrected_weather['wind_speed_avg']:.1f}m/s")
                print(f"  Rishiri Model: {rishiri_evaluation['condition']} (Score: {rishiri_evaluation['score']:.1f})")
                print(f"  Actual: {'Success' if success else 'Failure'}")
                print()
                
            except Exception as e:
                print(f"  Rishiri model evaluation error: {e}")
                continue
        
        return self.analyze_rishiri_validation(calibration_data)
    
    def analyze_rishiri_validation(self, data):
        """利尻島モデルの検証結果分析"""
        
        print(f"{'='*60}")
        print("RISHIRI MODEL VALIDATION RESULTS")
        print(f"{'='*60}")
        
        if not data:
            print("No validation data available")
            return None
        
        # 予測精度の評価（複数の閾値で試行）
        thresholds = [3.0, 3.5, 4.0, 4.5, 5.0]
        best_threshold = 4.0
        best_accuracy = 0
        
        print(f"Testing different score thresholds:")
        print(f"{'Threshold':<10} {'Accuracy':<10} {'TP':<4} {'TN':<4} {'FP':<4} {'FN':<4}")
        print("-" * 50)
        
        for threshold in thresholds:
            tp = tn = fp = fn = 0
            
            for case in data:
                actual = case['actual_success']
                predicted = case['rishiri_score'] >= threshold
                
                if actual and predicted:
                    tp += 1
                elif not actual and not predicted:
                    tn += 1
                elif not actual and predicted:
                    fp += 1
                else:
                    fn += 1
            
            accuracy = (tp + tn) / len(data) if data else 0
            
            print(f"{threshold:<10.1f} {accuracy*100:<9.1f}% {tp:<4} {tn:<4} {fp:<4} {fn:<4}")
            
            if accuracy > best_accuracy:
                best_accuracy = accuracy
                best_threshold = threshold
        
        print(f"\nBest threshold: {best_threshold} (Accuracy: {best_accuracy*100:.1f}%)")
        
        # 最適閾値での詳細分析
        correct_predictions = []
        incorrect_predictions = []
        
        for case in data:
            predicted_success = case['rishiri_score'] >= best_threshold
            if predicted_success == case['actual_success']:
                correct_predictions.append(case)
            else:
                incorrect_predictions.append(case)
        
        print(f"\n--- CORRECT PREDICTIONS ({len(correct_predictions)}) ---")
        success_correct = [c for c in correct_predictions if c['actual_success']]
        failure_correct = [c for c in correct_predictions if not c['actual_success']]
        
        if success_correct:
            success_scores = [c['rishiri_score'] for c in success_correct]
            print(f"Success cases correctly predicted: {len(success_correct)}")
            print(f"  Score range: {min(success_scores):.1f}-{max(success_scores):.1f}")
            print(f"  Average score: {sum(success_scores)/len(success_scores):.1f}")
        
        if failure_correct:
            failure_scores = [c['rishiri_score'] for c in failure_correct]
            print(f"Failure cases correctly predicted: {len(failure_correct)}")
            print(f"  Score range: {min(failure_scores):.1f}-{max(failure_scores):.1f}")
            print(f"  Average score: {sum(failure_scores)/len(failure_scores):.1f}")
        
        print(f"\n--- INCORRECT PREDICTIONS ({len(incorrect_predictions)}) ---")
        for case in incorrect_predictions:
            actual_str = "Success" if case['actual_success'] else "Failure"
            predicted_str = "Success" if case['rishiri_score'] >= best_threshold else "Failure"
            print(f"{case['date']} {case['location']}: Actual={actual_str}, "
                  f"Predicted={predicted_str} (Score: {case['rishiri_score']:.1f})")
        
        # 気象条件の分析
        print(f"\n--- WEATHER CONDITION ANALYSIS ---")
        
        success_cases = [c for c in data if c['actual_success']]
        failure_cases = [c for c in data if not c['actual_success']]
        
        if success_cases:
            success_temps = [c['weather']['temperature_avg'] for c in success_cases]
            success_humidity = [c['weather']['humidity_avg'] for c in success_cases]
            success_wind = [c['weather']['wind_speed_avg'] for c in success_cases]
            success_scores = [c['rishiri_score'] for c in success_cases]
            
            print(f"Success cases ({len(success_cases)}):")
            print(f"  Temperature: {min(success_temps):.1f}-{max(success_temps):.1f}°C (avg: {sum(success_temps)/len(success_temps):.1f}°C)")
            print(f"  Humidity: {min(success_humidity):.1f}-{max(success_humidity):.1f}% (avg: {sum(success_humidity)/len(success_humidity):.1f}%)")
            print(f"  Wind: {min(success_wind):.1f}-{max(success_wind):.1f}m/s (avg: {sum(success_wind)/len(success_wind):.1f}m/s)")
            print(f"  Rishiri Score: {min(success_scores):.1f}-{max(success_scores):.1f} (avg: {sum(success_scores)/len(success_scores):.1f})")
        
        if failure_cases:
            failure_temps = [c['weather']['temperature_avg'] for c in failure_cases]
            failure_humidity = [c['weather']['humidity_avg'] for c in failure_cases]
            failure_wind = [c['weather']['wind_speed_avg'] for c in failure_cases]
            failure_scores = [c['rishiri_score'] for c in failure_cases]
            
            print(f"\nFailure cases ({len(failure_cases)}):")
            print(f"  Temperature: {min(failure_temps):.1f}-{max(failure_temps):.1f}°C (avg: {sum(failure_temps)/len(failure_temps):.1f}°C)")
            print(f"  Humidity: {min(failure_humidity):.1f}-{max(failure_humidity):.1f}% (avg: {sum(failure_humidity)/len(failure_humidity):.1f}%)")
            print(f"  Wind: {min(failure_wind):.1f}-{max(failure_wind):.1f}m/s (avg: {sum(failure_wind)/len(failure_wind):.1f}m/s)")
            print(f"  Rishiri Score: {min(failure_scores):.1f}-{max(failure_scores):.1f} (avg: {sum(failure_scores)/len(failure_scores):.1f})")
        
        return {
            'total_cases': len(data),
            'best_accuracy': best_accuracy,
            'best_threshold': best_threshold,
            'correct_predictions': len(correct_predictions),
            'incorrect_predictions': len(incorrect_predictions),
            'validation_data': data
        }

def main():
    """メイン実行"""
    validator = RishiriModelValidator()
    
    if validator.calibrator.historical_records.empty:
        print("No historical records available for validation")
        return
    
    results = validator.validate_rishiri_model()
    
    if results:
        print(f"\n{'='*60}")
        print("VALIDATION SUMMARY")
        print(f"{'='*60}")
        print(f"Total cases: {results['total_cases']}")
        print(f"Best accuracy: {results['best_accuracy']*100:.1f}%")
        print(f"Optimal threshold: {results['best_threshold']}")
        print(f"Correct predictions: {results['correct_predictions']}")
        print(f"Incorrect predictions: {results['incorrect_predictions']}")
        
        if results['best_accuracy'] >= 0.8:
            print("\nEXCELLENT: Rishiri-specific model shows high accuracy!")
        elif results['best_accuracy'] >= 0.6:
            print("\nGOOD: Rishiri model performance is acceptable")
        else:
            print("\nNEEDS IMPROVEMENT: Further calibration required")

if __name__ == "__main__":
    main()