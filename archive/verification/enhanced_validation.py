#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
強化システム検証
Enhanced System Validation

新しい強化予報システムの精度検証と従来システムとの比較
"""

import asyncio
import pandas as pd
import numpy as np
import json
from datetime import datetime, timedelta
from typing import Dict, List
import time

from enhanced_forecast_system import EnhancedForecastSystem

class EnhancedSystemValidator:
    """強化システム検証クラス"""
    
    def __init__(self):
        self.enhanced_system = EnhancedForecastSystem()
        self.records_file = "hoshiba_records.csv"
        self.spots_file = "hoshiba_spots.csv"
        
    async def validate_enhanced_system(self) -> Dict:
        """強化システムの検証実行"""
        print("=== Enhanced System Validation ===")
        print(f"Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # データ読み込み
        records_df = pd.read_csv(self.records_file, encoding='utf-8')
        records_df['date'] = pd.to_datetime(records_df['date'])
        spots_df = pd.read_csv(self.spots_file, encoding='utf-8')
        
        # 作業記録のみ対象（中止除く）
        working_records = records_df[records_df['result'] != '中止'].copy()
        print(f"Validating {len(working_records)} working records")
        
        validation_results = {}
        performance_stats = {
            "total_api_time": 0,
            "total_processing_time": 0,
            "avg_response_time": 0,
            "cache_hits": 0,
            "total_requests": 0
        }
        
        # 1-7日前予報の検証
        for days_ahead in range(1, 8):
            print(f"\n--- Validating Enhanced {days_ahead}-day ahead forecasts ---")
            
            day_results = {
                "days_ahead": days_ahead,
                "total_predictions": 0,
                "correct_predictions": 0,
                "accuracy_percentage": 0.0,
                "detailed_results": [],
                "confusion_matrix": {
                    "true_positive": 0,
                    "false_positive": 0,
                    "true_negative": 0,
                    "false_negative": 0
                },
                "performance_metrics": {
                    "avg_response_time": 0,
                    "avg_processing_time": 0,
                    "data_sources_avg": 0
                }
            }
            
            response_times = []
            processing_times = []
            sources_counts = []
            
            for _, record in working_records.iterrows():
                spot_name = record['name']
                target_date = record['date']
                actual_result = record['result']
                
                # 座標取得
                spot_row = spots_df[spots_df['name'] == spot_name]
                if spot_row.empty:
                    continue
                
                lat, lon = float(spot_row.iloc[0]['lat']), float(spot_row.iloc[0]['lon'])
                
                # 強化予報生成
                try:
                    forecast = await self.enhanced_system.generate_enhanced_forecast(
                        lat, lon, target_date, days_ahead
                    )
                    
                    if "error" in forecast:
                        continue
                    
                    # 性能統計記録
                    metrics = forecast["performance_metrics"]
                    response_times.append(metrics.total_prediction_time)
                    processing_times.append(metrics.data_processing_time)
                    sources_counts.append(metrics.data_sources_used)
                    
                    if metrics.cache_hit_rate > 0:
                        performance_stats["cache_hits"] += 1
                    
                    # 精度評価
                    actual_success = actual_result == "完全乾燥"
                    predicted_success = forecast['success_prediction']
                    correct = (predicted_success and actual_success) or (not predicted_success and not actual_success)
                    
                    # 予測タイプ分類
                    if predicted_success and actual_success:
                        prediction_type = "true_positive"
                    elif predicted_success and not actual_success:
                        prediction_type = "false_positive"
                    elif not predicted_success and not actual_success:
                        prediction_type = "true_negative"
                    else:
                        prediction_type = "false_negative"
                    
                    # 詳細結果記録
                    detailed_result = {
                        "spot_name": spot_name,
                        "target_date": target_date.isoformat(),
                        "coordinates": {"lat": lat, "lon": lon},
                        "forecast_condition": forecast['condition'],
                        "forecast_score": forecast['forecast_score'],
                        "success_prediction": predicted_success,
                        "actual_success": actual_success,
                        "actual_result": actual_result,
                        "correct": correct,
                        "prediction_type": prediction_type,
                        "terrain_corrections": forecast['terrain_corrections'],
                        "confidence": forecast['confidence'],
                        "data_sources": forecast['data_sources'],
                        "response_time": metrics.total_prediction_time
                    }
                    
                    day_results['detailed_results'].append(detailed_result)
                    day_results['total_predictions'] += 1
                    
                    if correct:
                        day_results['correct_predictions'] += 1
                    
                    # 混同行列更新
                    day_results['confusion_matrix'][prediction_type] += 1
                    
                except Exception as e:
                    print(f"Validation error for {spot_name}: {e}")
                    continue
            
            # 精度計算
            if day_results['total_predictions'] > 0:
                day_results['accuracy_percentage'] = (
                    day_results['correct_predictions'] / day_results['total_predictions'] * 100
                )
                
                # 性能統計計算
                if response_times:
                    day_results['performance_metrics']['avg_response_time'] = np.mean(response_times)
                    day_results['performance_metrics']['avg_processing_time'] = np.mean(processing_times)
                    day_results['performance_metrics']['data_sources_avg'] = np.mean(sources_counts)
                    
                    performance_stats["total_api_time"] += sum(response_times)
                    performance_stats["total_processing_time"] += sum(processing_times)
                    performance_stats["total_requests"] += len(response_times)
            
            validation_results[str(days_ahead)] = day_results
            
            print(f"  Enhanced {days_ahead}-day ahead: {day_results['accuracy_percentage']:.1f}% "
                  f"({day_results['correct_predictions']}/{day_results['total_predictions']}) "
                  f"[Avg: {day_results['performance_metrics']['avg_response_time']:.3f}s]")
        
        # 全体統計計算
        if performance_stats["total_requests"] > 0:
            performance_stats["avg_response_time"] = (
                performance_stats["total_api_time"] / performance_stats["total_requests"]
            )
        
        # 結果保存
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"enhanced_system_validation_{timestamp}.json"
        
        final_results = {
            "validation_timestamp": datetime.now().isoformat(),
            "system_version": "Enhanced_v1.0",
            "validation_results": validation_results,
            "performance_statistics": performance_stats
        }
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(final_results, f, indent=2, ensure_ascii=False)
        
        print(f"\nEnhanced validation results saved to: {filename}")
        return final_results
    
    def compare_with_original_system(self, enhanced_results: Dict, 
                                   original_results_file: str) -> Dict:
        """従来システムとの比較分析"""
        print("\n=== Comparing Enhanced vs Original System ===")
        
        try:
            with open(original_results_file, 'r', encoding='utf-8') as f:
                original_results = json.load(f)
        except FileNotFoundError:
            print(f"Original results file not found: {original_results_file}")
            return {}
        
        comparison = {
            "accuracy_comparison": {},
            "performance_comparison": {},
            "improvement_metrics": {}
        }
        
        print(f"{'Days':<5} {'Original':<10} {'Enhanced':<10} {'Improvement':<12} {'Performance':<12}")
        print("-" * 60)
        
        total_original_acc = 0
        total_enhanced_acc = 0
        days_compared = 0
        
        for days in range(1, 8):
            days_str = str(days)
            
            if days_str in original_results and days_str in enhanced_results["validation_results"]:
                orig_acc = original_results[days_str]['accuracy_percentage']
                enh_acc = enhanced_results["validation_results"][days_str]['accuracy_percentage']
                improvement = enh_acc - orig_acc
                
                # 性能比較
                enh_perf = enhanced_results["validation_results"][days_str]['performance_metrics']
                avg_time = enh_perf.get('avg_response_time', 0)
                
                comparison["accuracy_comparison"][days] = {
                    "original_accuracy": orig_acc,
                    "enhanced_accuracy": enh_acc,
                    "improvement": improvement,
                    "relative_improvement": (improvement / orig_acc * 100) if orig_acc > 0 else 0
                }
                
                comparison["performance_comparison"][days] = {
                    "avg_response_time": avg_time,
                    "data_sources_used": enh_perf.get('data_sources_avg', 1)
                }
                
                print(f"{days:<5} {orig_acc:<10.1f} {enh_acc:<10.1f} {improvement:<+12.1f} {avg_time:<12.3f}")
                
                total_original_acc += orig_acc
                total_enhanced_acc += enh_acc
                days_compared += 1
        
        if days_compared > 0:
            avg_original = total_original_acc / days_compared
            avg_enhanced = total_enhanced_acc / days_compared
            overall_improvement = avg_enhanced - avg_original
            
            comparison["improvement_metrics"] = {
                "average_original_accuracy": avg_original,
                "average_enhanced_accuracy": avg_enhanced,
                "overall_improvement": overall_improvement,
                "relative_improvement_percent": (overall_improvement / avg_original * 100) if avg_original > 0 else 0,
                "days_compared": days_compared
            }
            
            print("-" * 60)
            print(f"{'Avg':<5} {avg_original:<10.1f} {avg_enhanced:<10.1f} {overall_improvement:<+12.1f}")
            print(f"\nOverall Improvement: {overall_improvement:.1f}% ({(overall_improvement/avg_original*100):+.1f}%)")
        
        return comparison

async def main():
    """メイン実行関数"""
    validator = EnhancedSystemValidator()
    
    # 強化システム検証実行
    enhanced_results = await validator.validate_enhanced_system()
    
    # 従来システムとの比較
    original_file = "comprehensive_forecast_validation_20250808_205310.json"
    comparison = validator.compare_with_original_system(enhanced_results, original_file)
    
    # サマリー表示
    print("\n" + "="*70)
    print("ENHANCED SYSTEM VALIDATION SUMMARY")
    print("="*70)
    
    if "improvement_metrics" in comparison:
        metrics = comparison["improvement_metrics"]
        print(f"Average Original Accuracy: {metrics['average_original_accuracy']:.1f}%")
        print(f"Average Enhanced Accuracy: {metrics['average_enhanced_accuracy']:.1f}%")
        print(f"Overall Improvement: {metrics['overall_improvement']:.1f}% ({metrics['relative_improvement_percent']:+.1f}%)")
        print(f"Days Compared: {metrics['days_compared']}")
    
    # 性能統計
    perf_stats = enhanced_results["performance_statistics"]
    print(f"\nPerformance Statistics:")
    print(f"  Average Response Time: {perf_stats['avg_response_time']:.3f}s")
    print(f"  Cache Hit Rate: {perf_stats['cache_hits']}/{perf_stats['total_requests']} ({perf_stats['cache_hits']/perf_stats['total_requests']*100:.1f}%)")
    
    return enhanced_results, comparison

if __name__ == "__main__":
    asyncio.run(main())