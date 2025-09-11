#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
利尻島昆布干し予報精度評価システム
Rishiri Konbu Drying Forecast Accuracy Evaluation System

過去の実績データと前日予報の整合性をチェックし、現在の予報システムの精度を評価する
"""

import pandas as pd
import requests
import json
import time
from datetime import datetime, timedelta
import numpy as np
from typing import Dict, List, Tuple, Optional

class ForecastAccuracyEvaluator:
    """予報精度評価クラス"""
    
    def __init__(self):
        self.api_base = "http://127.0.0.1:8001"
        self.records_file = "hoshiba_records.csv"
        self.spots_file = "hoshiba_spots.csv"
        
        # 結果マッピング
        self.result_mapping = {
            "完全乾燥": "success",
            "干したが完全には乾かせなかった（泣）": "partial",
            "中止": "cancelled"
        }
        
        # 予報結果の判定基準
        self.forecast_categories = {
            "good": ["Good", "Excellent", "Perfect"],
            "marginal": ["Marginal", "Caution"],
            "poor": ["Poor", "High Risk", "Dangerous"]
        }
        
    def load_records(self) -> pd.DataFrame:
        """実績データを読み込み"""
        try:
            records = pd.read_csv(self.records_file)
            records['date'] = pd.to_datetime(records['date'])
            return records
        except Exception as e:
            print(f"Records loading error: {e}")
            return pd.DataFrame()
    
    def load_spots(self) -> pd.DataFrame:
        """干場データを読み込み"""
        try:
            spots = pd.read_csv(self.spots_file)
            return spots
        except Exception as e:
            print(f"Spots loading error: {e}")
            return pd.DataFrame()
    
    def get_spot_coordinates(self, spot_name: str, spots_df: pd.DataFrame) -> Optional[Tuple[float, float]]:
        """干場名から座標を取得"""
        try:
            spot_data = spots_df[spots_df['name'] == spot_name]
            if not spot_data.empty:
                lat = float(spot_data.iloc[0]['lat'])
                lon = float(spot_data.iloc[0]['lon'])
                return lat, lon
        except Exception as e:
            print(f"Coordinate extraction error for {spot_name}: {e}")
        return None
    
    def generate_historical_forecast(self, lat: float, lon: float, target_date: str) -> Optional[Dict]:
        """過去の日付に対する予報を生成（現在のシステムで再現）"""
        try:
            response = requests.get(
                f"{self.api_base}/forecast",
                params={
                    "lat": lat,
                    "lon": lon,
                    "start_date": target_date
                },
                timeout=10
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                print(f"API error for {target_date}: {response.status_code}")
                return None
                
        except Exception as e:
            print(f"Forecast generation error for {target_date}: {e}")
            return None
    
    def classify_forecast_result(self, forecast_data: Dict) -> str:
        """予報結果を分類"""
        if not forecast_data:
            return "unknown"
            
        prediction = forecast_data.get("prediction", "").lower()
        confidence = forecast_data.get("confidence", 0)
        
        # 予報内容による分類
        if any(good_word in prediction for good_word in ["good", "excellent", "perfect"]):
            if confidence >= 80:
                return "good_high"
            else:
                return "good_low"
        elif any(marginal_word in prediction for marginal_word in ["marginal", "caution"]):
            return "marginal"
        elif any(poor_word in prediction for poor_word in ["poor", "risk", "dangerous"]):
            return "poor"
        else:
            # 風速・湿度による分類
            wind = forecast_data.get("wind", 0)
            humidity = forecast_data.get("humidity", 0)
            
            if wind >= 3 and humidity <= 80:
                return "good_conditions"
            elif wind >= 2 and humidity <= 85:
                return "marginal_conditions"
            else:
                return "poor_conditions"
    
    def evaluate_forecast_accuracy(self, forecast_result: str, actual_result: str) -> Dict:
        """予報と実績の整合性を評価"""
        
        # 実績結果の重み付け
        actual_weights = {
            "success": 1.0,    # 完全乾燥
            "partial": 0.6,    # 部分乾燥
            "cancelled": 0.0   # 中止
        }
        
        # 予報結果の期待値
        forecast_expectations = {
            "good_high": 0.9,
            "good_low": 0.8,
            "good_conditions": 0.85,
            "marginal": 0.6,
            "marginal_conditions": 0.65,
            "poor": 0.3,
            "poor_conditions": 0.2,
            "unknown": 0.5
        }
        
        actual_score = actual_weights.get(actual_result, 0)
        expected_score = forecast_expectations.get(forecast_result, 0.5)
        
        # 精度計算
        accuracy_score = 1.0 - abs(actual_score - expected_score)
        
        # 詳細評価
        if actual_result == "success":
            if forecast_result in ["good_high", "good_low", "good_conditions"]:
                evaluation = "correct_positive"
            elif forecast_result in ["marginal", "marginal_conditions"]:
                evaluation = "conservative_correct"
            else:
                evaluation = "false_negative"
        elif actual_result == "partial":
            if forecast_result in ["marginal", "marginal_conditions"]:
                evaluation = "correct_marginal"
            elif forecast_result in ["good_high", "good_low", "good_conditions"]:
                evaluation = "overoptimistic"
            else:
                evaluation = "correct_negative"
        else:  # cancelled
            if forecast_result in ["poor", "poor_conditions"]:
                evaluation = "correct_negative"
            else:
                evaluation = "false_positive"
        
        return {
            "accuracy_score": accuracy_score,
            "evaluation": evaluation,
            "actual_score": actual_score,
            "expected_score": expected_score
        }
    
    def run_evaluation(self) -> Dict:
        """精度評価を実行"""
        print("=== Rishiri Konbu Drying Forecast Accuracy Evaluation ===")
        print(f"Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print()
        
        # データ読み込み
        records_df = self.load_records()
        spots_df = self.load_spots()
        
        if records_df.empty or spots_df.empty:
            return {"error": "Could not load required data files"}
        
        print(f"Loaded {len(records_df)} records and {len(spots_df)} spots")
        
        # 評価対象データの抽出（中止以外の実働日）
        working_records = records_df[records_df['result'] != '中止'].copy()
        print(f"Working days (non-cancelled): {len(working_records)} records")
        
        evaluation_results = []
        successful_evaluations = 0
        
        # 各記録について前日予報と比較
        for idx, record in working_records.iterrows():
            date = record['date']
            spot_name = record['name']
            actual_result = self.result_mapping.get(record['result'], 'unknown')
            
            print(f"\nEvaluating: {spot_name} on {date.strftime('%Y-%m-%d')} (actual: {actual_result})")
            
            # 座標取得
            coordinates = self.get_spot_coordinates(spot_name, spots_df)
            if not coordinates:
                print(f"  Skipped: No coordinates found for {spot_name}")
                continue
            
            lat, lon = coordinates
            print(f"  Coordinates: {lat:.4f}, {lon:.4f}")
            
            # 前日予報を再現（現在のシステムで）
            target_date = date.strftime('%Y-%m-%d')
            forecast_data = self.generate_historical_forecast(lat, lon, target_date)
            
            if not forecast_data:
                print(f"  Skipped: Could not generate forecast")
                continue
            
            # 予報結果の分類
            forecast_result = self.classify_forecast_result(forecast_data)
            print(f"  Forecast classification: {forecast_result}")
            print(f"  Forecast details: {forecast_data.get('prediction', 'N/A')} (confidence: {forecast_data.get('confidence', 'N/A')}%)")
            
            # 精度評価
            accuracy = self.evaluate_forecast_accuracy(forecast_result, actual_result)
            print(f"  Accuracy score: {accuracy['accuracy_score']:.2f}")
            print(f"  Evaluation: {accuracy['evaluation']}")
            
            evaluation_results.append({
                'date': date,
                'spot_name': spot_name,
                'actual_result': actual_result,
                'forecast_result': forecast_result,
                'forecast_prediction': forecast_data.get('prediction', 'N/A'),
                'forecast_confidence': forecast_data.get('confidence', 0),
                'forecast_wind': forecast_data.get('wind', 0),
                'forecast_humidity': forecast_data.get('humidity', 0),
                'accuracy_score': accuracy['accuracy_score'],
                'evaluation_type': accuracy['evaluation'],
                'actual_score': accuracy['actual_score'],
                'expected_score': accuracy['expected_score']
            })
            
            successful_evaluations += 1
            
            # レート制限
            time.sleep(0.5)
        
        # 統計分析
        if not evaluation_results:
            return {"error": "No successful evaluations completed"}
        
        results_df = pd.DataFrame(evaluation_results)
        
        # 総合統計
        overall_accuracy = results_df['accuracy_score'].mean()
        accuracy_std = results_df['accuracy_score'].std()
        
        # 評価タイプ別統計
        evaluation_counts = results_df['evaluation_type'].value_counts().to_dict()
        
        # 実績別統計
        actual_result_stats = {}
        for result_type in ['success', 'partial']:
            subset = results_df[results_df['actual_result'] == result_type]
            if not subset.empty:
                actual_result_stats[result_type] = {
                    'count': len(subset),
                    'avg_accuracy': subset['accuracy_score'].mean(),
                    'avg_confidence': subset['forecast_confidence'].mean()
                }
        
        # 時系列分析
        results_df['month'] = results_df['date'].dt.month
        monthly_accuracy = results_df.groupby('month')['accuracy_score'].mean().to_dict()
        
        summary = {
            'total_evaluations': successful_evaluations,
            'overall_accuracy': overall_accuracy,
            'accuracy_std': accuracy_std,
            'evaluation_counts': evaluation_counts,
            'actual_result_stats': actual_result_stats,
            'monthly_accuracy': monthly_accuracy,
            'detailed_results': evaluation_results
        }
        
        print(f"\n=== Evaluation Summary ===")
        print(f"Total evaluations: {successful_evaluations}")
        print(f"Overall accuracy: {overall_accuracy:.3f} ± {accuracy_std:.3f}")
        print(f"Evaluation types: {evaluation_counts}")
        
        return summary
    
    def save_results(self, results: Dict, filename: str = None):
        """結果をファイルに保存"""
        if not filename:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"forecast_accuracy_evaluation_{timestamp}.json"
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2, default=str)
        
        print(f"Results saved to: {filename}")
        return filename

def main():
    """メイン実行関数"""
    evaluator = ForecastAccuracyEvaluator()
    results = evaluator.run_evaluation()
    
    if 'error' in results:
        print(f"Evaluation failed: {results['error']}")
        return
    
    # 結果保存
    filename = evaluator.save_results(results)
    
    # CSV出力（詳細結果）
    if 'detailed_results' in results:
        csv_filename = filename.replace('.json', '.csv')
        results_df = pd.DataFrame(results['detailed_results'])
        results_df.to_csv(csv_filename, index=False, encoding='utf-8-sig')
        print(f"Detailed results CSV saved to: {csv_filename}")
    
    print("\n=== Final Accuracy Assessment ===")
    accuracy = results.get('overall_accuracy', 0)
    
    if accuracy >= 0.8:
        print("✅ EXCELLENT: Forecast system shows high accuracy")
    elif accuracy >= 0.7:
        print("✅ GOOD: Forecast system shows good accuracy")
    elif accuracy >= 0.6:
        print("⚠️  MODERATE: Forecast system shows moderate accuracy, room for improvement")
    else:
        print("❌ POOR: Forecast system needs significant improvement")
    
    print(f"Current system accuracy: {accuracy:.1%}")

if __name__ == "__main__":
    main()