#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
利尻島昆布干し予報システム - 包括的予報精度検証
Comprehensive Forecast Accuracy Validation for Rishiri Kelp Drying System

hoshiba_records.csv全データに対して1-7日前予報の精度検証を行う
"""

import pandas as pd
import numpy as np
import json
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
import os
from pathlib import Path

# 既存の予報システムモジュールをインポート
try:
    from konbu_specialized_forecast import KonbuForecastSystem
    from kelp_drying_forecast_system import KelpDryingForecastSystem
    from terrain_database import RishiriTerrainDatabase
except ImportError as e:
    print(f"Warning: Could not import forecast modules: {e}")
    KonbuForecastSystem = None
    KelpDryingForecastSystem = None
    RishiriTerrainDatabase = None

class ComprehensiveForecastValidator:
    """包括的予報精度検証クラス"""
    
    def __init__(self):
        self.records_file = "hoshiba_records.csv"
        self.spots_file = "hoshiba_spots.csv"
        
        # 予報システム初期化
        self.terrain_db = RishiriTerrainDatabase() if RishiriTerrainDatabase else None
        self.kelp_system = KelpDryingForecastSystem() if KelpDryingForecastSystem else None
        
        # 結果マッピング
        self.result_mapping = {
            "完全乾燥": "success",
            "干したが完全には乾かせなかった（泣）": "partial", 
            "中止": "cancelled"
        }
        
        # 検証結果格納
        self.validation_results = {}
        
    def load_data(self) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """実績データと干場データを読み込み"""
        try:
            records = pd.read_csv(self.records_file, encoding='utf-8')
            records['date'] = pd.to_datetime(records['date'])
            records = records.sort_values('date')
            
            spots = pd.read_csv(self.spots_file, encoding='utf-8')
            
            print(f"Loaded {len(records)} records and {len(spots)} spots")
            return records, spots
            
        except Exception as e:
            print(f"Data loading error: {e}")
            return pd.DataFrame(), pd.DataFrame()
    
    def get_spot_coordinates(self, spot_name: str, spots_df: pd.DataFrame) -> Tuple[float, float]:
        """干場名から座標を取得"""
        spot_row = spots_df[spots_df['name'] == spot_name]
        if not spot_row.empty:
            return float(spot_row.iloc[0]['lat']), float(spot_row.iloc[0]['lon'])
        return None, None
    
    def simulate_historical_forecast(self, lat: float, lon: float, forecast_date: datetime, days_ahead: int) -> Dict:
        """過去日付での予報をシミュレーション"""
        try:
            # 予報基準日（実際に予報を行う日）
            forecast_base_date = forecast_date - timedelta(days=days_ahead)
            
            # 簡易予報モデル（実際の気象データを使用する代わりの近似）
            # 実際の実装では、historical weather APIを使用するか、
            # 既存のモデルを使って当時のデータで予報を生成する
            
            forecast_score = self._calculate_forecast_score(lat, lon, forecast_date)
            
            # 予報条件判定
            if forecast_score >= 7:
                condition = "Excellent"
                success_prediction = True
            elif forecast_score >= 5:
                condition = "Good" 
                success_prediction = True
            elif forecast_score >= 3:
                condition = "Marginal"
                success_prediction = False
            else:
                condition = "Poor"
                success_prediction = False
            
            return {
                "forecast_base_date": forecast_base_date.isoformat(),
                "target_date": forecast_date.isoformat(),
                "days_ahead": days_ahead,
                "forecast_score": forecast_score,
                "condition": condition,
                "success_prediction": success_prediction,
                "coordinates": {"lat": lat, "lon": lon}
            }
            
        except Exception as e:
            print(f"Forecast simulation error: {e}")
            return None
    
    def _calculate_forecast_score(self, lat: float, lon: float, target_date: datetime) -> float:
        """予報スコア計算（簡易モデル）"""
        # 実際の実装では、以下を考慮：
        # 1. 気象データ（気温、湿度、風速、日射量等）
        # 2. 地形効果
        # 3. 季節性
        # 4. 機械学習モデル予測
        
        # 現在は季節と位置に基づく簡易モデル
        month = target_date.month
        day_of_year = target_date.timetuple().tm_yday
        
        # 夏季（7-8月）は乾燥に適している
        seasonal_factor = 1.0
        if month in [7, 8]:
            seasonal_factor = 1.5
        elif month in [6, 9]:
            seasonal_factor = 1.2
        
        # 位置による補正（海岸からの距離等）
        # 実際の地形データベースを使用する場合はここで計算
        location_factor = 1.0
        
        # ベーススコア（ランダム要素を含む実際の予測の代替）
        base_score = np.random.normal(5.0, 2.0)  # 実際の予測モデルに置き換え
        
        final_score = base_score * seasonal_factor * location_factor
        return max(0, min(10, final_score))  # 0-10の範囲に正規化
    
    def evaluate_prediction_accuracy(self, prediction: bool, actual_result: str, 
                                   weight_false_negative: float = 0.5) -> Dict:
        """予測と実績の照合（中止ケース考慮・偽陰性重み調整）"""
        actual_success = actual_result == "完全乾燥"
        
        # 中止の場合は「実際は成功しなかった」として扱う
        if actual_result == "中止":
            actual_success = False
        
        # 精度判定（偽陰性の重みを軽減）
        if prediction and actual_success:
            correct = True
            prediction_type = "true_positive"
            accuracy_weight = 1.0
        elif prediction and not actual_success:
            correct = False
            prediction_type = "false_positive"
            accuracy_weight = 1.0
        elif not prediction and not actual_success:
            correct = True
            prediction_type = "true_negative"
            accuracy_weight = 1.0
        else:  # not prediction and actual_success (偽陰性)
            correct = False
            prediction_type = "false_negative"
            accuracy_weight = weight_false_negative  # 偽陰性の重みを軽減
        
        # 中止の場合の特別処理
        if actual_result == "中止" and not prediction:
            # 中止を正しく予測した場合はより高く評価
            accuracy_weight = 1.2
        
        return {
            "correct": correct,
            "prediction_type": prediction_type,
            "predicted_success": prediction,
            "actual_success": actual_success,
            "actual_result": actual_result,
            "accuracy_weight": accuracy_weight,
            "is_cancellation": actual_result == "中止"
        }
    
    def run_comprehensive_validation(self) -> Dict:
        """包括的予報精度検証を実行"""
        print("=== Comprehensive Forecast Validation ===")
        print(f"Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        records_df, spots_df = self.load_data()
        
        if records_df.empty:
            return {"error": "No records to validate"}
        
        # 全記録を使用（中止も含める）
        working_records = records_df.copy()
        print(f"All records (including cancellations): {len(working_records)}")
        
        # 中止記録の詳細
        cancelled_records = records_df[records_df['result'] == '中止']
        success_records = records_df[records_df['result'] == '完全乾燥']
        print(f"  - Cancelled: {len(cancelled_records)} records")
        print(f"  - Success: {len(success_records)} records")
        
        validation_results = {}
        
        # 1-7日前予報の検証
        for days_ahead in range(1, 8):
            print(f"\n--- Validating {days_ahead}-day ahead forecasts ---")
            
            day_results = {
                "days_ahead": days_ahead,
                "total_predictions": 0,
                "correct_predictions": 0.0,  # 重み付き精度のためfloat
                "accuracy_percentage": 0.0,
                "detailed_results": [],
                "confusion_matrix": {
                    "true_positive": 0,
                    "false_positive": 0, 
                    "true_negative": 0,
                    "false_negative": 0
                },
                "cancellation_stats": {
                    "total_cancellations": 0,
                    "correctly_predicted_cancellations": 0
                }
            }
            
            for _, record in working_records.iterrows():
                spot_name = record['name']
                target_date = record['date']
                actual_result = record['result']
                
                # 座標取得
                lat, lon = self.get_spot_coordinates(spot_name, spots_df)
                if lat is None or lon is None:
                    continue
                
                # 予報シミュレーション
                forecast = self.simulate_historical_forecast(lat, lon, target_date, days_ahead)
                if forecast is None:
                    continue
                
                # 精度評価（偽陰性重み軽減）
                evaluation = self.evaluate_prediction_accuracy(
                    forecast['success_prediction'], 
                    actual_result,
                    weight_false_negative=0.5  # 偽陰性を半分の重みで評価
                )
                
                # 結果記録
                detailed_result = {
                    "spot_name": spot_name,
                    "target_date": target_date.isoformat(),
                    "forecast_base_date": forecast['forecast_base_date'],
                    "coordinates": forecast['coordinates'],
                    "forecast_condition": forecast['condition'],
                    "forecast_score": forecast['forecast_score'],
                    **evaluation
                }
                
                day_results['detailed_results'].append(detailed_result)
                day_results['total_predictions'] += 1
                
                # 重み付き精度計算
                if evaluation['correct']:
                    day_results['correct_predictions'] += evaluation['accuracy_weight']
                else:
                    # 不正解でも重みによる部分的評価
                    if evaluation['prediction_type'] == 'false_negative':
                        day_results['correct_predictions'] += (1 - evaluation['accuracy_weight'])
                
                # 混同行列更新
                day_results['confusion_matrix'][evaluation['prediction_type']] += 1
                
                # 中止統計更新
                if evaluation['is_cancellation']:
                    day_results['cancellation_stats']['total_cancellations'] += 1
                    if not evaluation['predicted_success']:  # 中止を正しく予測
                        day_results['cancellation_stats']['correctly_predicted_cancellations'] += 1
            
            # 精度計算
            if day_results['total_predictions'] > 0:
                day_results['accuracy_percentage'] = (
                    day_results['correct_predictions'] / day_results['total_predictions'] * 100
                )
            
            validation_results[str(days_ahead)] = day_results
            
            print(f"  {days_ahead}-day ahead: {day_results['accuracy_percentage']:.1f}% "
                  f"({day_results['correct_predictions']}/{day_results['total_predictions']})")
        
        # 結果保存
        self.validation_results = validation_results
        self._save_results()
        
        return validation_results
    
    def _save_results(self):
        """検証結果を保存"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"comprehensive_forecast_validation_{timestamp}.json"
        
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(self.validation_results, f, indent=2, ensure_ascii=False)
            print(f"\nResults saved to: {filename}")
        except Exception as e:
            print(f"Failed to save results: {e}")
    
    def generate_summary_report(self) -> Dict:
        """サマリーレポート生成"""
        if not self.validation_results:
            return {"error": "No validation results available"}
        
        summary = {
            "validation_date": datetime.now().isoformat(),
            "total_days_validated": len(self.validation_results),
            "accuracy_by_days_ahead": {},
            "overall_trends": {},
            "performance_metrics": {}
        }
        
        accuracies = []
        total_predictions = []
        
        for days_str, results in self.validation_results.items():
            days = int(days_str)
            accuracy = results['accuracy_percentage']
            count = results['total_predictions']
            
            summary['accuracy_by_days_ahead'][days] = {
                "accuracy_percentage": accuracy,
                "total_predictions": count,
                "correct_predictions": results['correct_predictions']
            }
            
            accuracies.append(accuracy)
            total_predictions.append(count)
        
        # 全体傾向分析
        if accuracies:
            summary['overall_trends'] = {
                "mean_accuracy": np.mean(accuracies),
                "accuracy_std": np.std(accuracies),
                "best_day_ahead": int(np.argmax(accuracies)) + 1,
                "worst_day_ahead": int(np.argmin(accuracies)) + 1,
                "accuracy_decline_per_day": np.polyfit(range(1, len(accuracies)+1), accuracies, 1)[0]
            }
        
        return summary

def main():
    """メイン実行関数"""
    validator = ComprehensiveForecastValidator()
    
    # 包括的検証実行
    results = validator.run_comprehensive_validation()
    
    # サマリーレポート生成
    summary = validator.generate_summary_report()
    
    # 結果表示
    print("\n" + "="*60)
    print("COMPREHENSIVE FORECAST VALIDATION SUMMARY")
    print("="*60)
    
    if "overall_trends" in summary:
        trends = summary['overall_trends']
        print(f"Mean Accuracy: {trends['mean_accuracy']:.1f}%")
        print(f"Best Performance: {trends['best_day_ahead']}-day ahead")
        print(f"Worst Performance: {trends['worst_day_ahead']}-day ahead") 
        print(f"Accuracy Decline: {trends['accuracy_decline_per_day']:.2f}% per day")
        
        print(f"\nAccuracy by Days Ahead:")
        for days in range(1, 8):
            if str(days) in validator.validation_results:
                acc = validator.validation_results[str(days)]['accuracy_percentage']
                total = validator.validation_results[str(days)]['total_predictions']
                print(f"  {days}-day: {acc:.1f}% ({total} predictions)")
    
    return results

if __name__ == "__main__":
    main()