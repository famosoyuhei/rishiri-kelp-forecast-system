#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
中止ケース影響分析
Analysis of Cancellation Impact on Forecast Accuracy
"""

import pandas as pd
import json
import numpy as np
from datetime import datetime

def compare_validation_results():
    """中止含む/除く検証結果の比較分析"""
    
    # 結果ファイル読み込み
    try:
        # 中止除く結果
        with open('comprehensive_forecast_validation_20250808_205310.json', 'r', encoding='utf-8') as f:
            results_excluding = json.load(f)
        
        # 中止含む結果  
        with open('comprehensive_forecast_validation_20250808_210710.json', 'r', encoding='utf-8') as f:
            results_including = json.load(f)
            
    except FileNotFoundError as e:
        print(f"Result files not found: {e}")
        return
    
    print("=" * 80)
    print("CANCELLATION IMPACT ANALYSIS")
    print("=" * 80)
    
    # 比較表作成
    comparison = {
        "days_ahead": [],
        "accuracy_excluding_cancellations": [],
        "accuracy_including_cancellations": [], 
        "accuracy_difference": [],
        "predictions_excluding": [],
        "predictions_including": [],
        "cancellation_prediction_rate": []
    }
    
    for days in range(1, 8):
        days_str = str(days)
        
        if days_str in results_excluding and days_str in results_including:
            exc_acc = results_excluding[days_str]['accuracy_percentage']
            inc_acc = results_including[days_str]['accuracy_percentage'] 
            
            comparison["days_ahead"].append(days)
            comparison["accuracy_excluding_cancellations"].append(exc_acc)
            comparison["accuracy_including_cancellations"].append(inc_acc)
            comparison["accuracy_difference"].append(inc_acc - exc_acc)
            comparison["predictions_excluding"].append(results_excluding[days_str]['total_predictions'])
            comparison["predictions_including"].append(results_including[days_str]['total_predictions'])
            
            # 中止予測率計算
            if 'cancellation_stats' in results_including[days_str]:
                cancel_stats = results_including[days_str]['cancellation_stats']
                total_cancels = cancel_stats['total_cancellations']
                correct_cancels = cancel_stats['correctly_predicted_cancellations']
                cancel_rate = (correct_cancels / total_cancels * 100) if total_cancels > 0 else 0
                comparison["cancellation_prediction_rate"].append(cancel_rate)
            else:
                comparison["cancellation_prediction_rate"].append(0)
    
    # 結果表示
    print("\nACCURACY COMPARISON TABLE")
    print("-" * 80)
    print(f"{'Days':<5} {'Excl.Cancel':<12} {'Incl.Cancel':<12} {'Difference':<11} {'Cancel Pred':<12}")
    print("-" * 80)
    
    for i in range(len(comparison["days_ahead"])):
        print(f"{comparison['days_ahead'][i]:<5} "
              f"{comparison['accuracy_excluding_cancellations'][i]:<12.1f} "
              f"{comparison['accuracy_including_cancellations'][i]:<12.1f} "
              f"{comparison['accuracy_difference'][i]:<11.1f} "
              f"{comparison['cancellation_prediction_rate'][i]:<12.1f}")
    
    # サマリー統計
    avg_acc_exc = np.mean(comparison["accuracy_excluding_cancellations"])
    avg_acc_inc = np.mean(comparison["accuracy_including_cancellations"])
    avg_diff = np.mean(comparison["accuracy_difference"])
    avg_cancel_pred = np.mean(comparison["cancellation_prediction_rate"])
    
    print("\nSUMMARY STATISTICS")
    print("-" * 40)
    print(f"Average Accuracy (Excluding Cancellations): {avg_acc_exc:.1f}%")
    print(f"Average Accuracy (Including Cancellations): {avg_acc_inc:.1f}%")
    print(f"Average Impact of Including Cancellations: {avg_diff:.1f}%")
    print(f"Average Cancellation Prediction Rate: {avg_cancel_pred:.1f}%")
    
    # 中止データ分析
    print("\nCANCELLATION DATA ANALYSIS")
    print("-" * 40)
    
    total_cancellations = 0
    total_correct_cancel_predictions = 0
    
    for days_str in results_including:
        if 'cancellation_stats' in results_including[days_str]:
            stats = results_including[days_str]['cancellation_stats']
            total_cancellations += stats['total_cancellations']
            total_correct_cancel_predictions += stats['correctly_predicted_cancellations']
    
    overall_cancel_accuracy = (total_correct_cancel_predictions / total_cancellations * 100) if total_cancellations > 0 else 0
    
    print(f"Total Cancellation Records: {total_cancellations // 7}") # 7日分なので割る
    print(f"Overall Cancellation Prediction Accuracy: {overall_cancel_accuracy:.1f}%")
    
    # 重み付け効果分析
    print("\nFALSE NEGATIVE WEIGHTING EFFECT")
    print("-" * 40)
    
    # 偽陰性の数を分析
    total_false_negatives_exc = 0
    total_false_negatives_inc = 0
    
    for days_str in results_excluding:
        if 'confusion_matrix' in results_excluding[days_str]:
            total_false_negatives_exc += results_excluding[days_str]['confusion_matrix']['false_negative']
    
    for days_str in results_including:
        if 'confusion_matrix' in results_including[days_str]:
            total_false_negatives_inc += results_including[days_str]['confusion_matrix']['false_negative']
    
    print(f"False Negatives (Excluding Cancellations): {total_false_negatives_exc}")
    print(f"False Negatives (Including Cancellations): {total_false_negatives_inc}")
    print(f"Additional False Negatives from Cancellations: {total_false_negatives_inc - total_false_negatives_exc}")
    
    # 実用的な評価
    print("\nPRACTICAL EVALUATION")
    print("-" * 40)
    
    if avg_diff < -10:
        evaluation = "Significant negative impact - cancellations severely reduce apparent accuracy"
    elif avg_diff < -5:
        evaluation = "Moderate negative impact - cancellations reduce accuracy but system remains viable"
    elif avg_diff < 0:
        evaluation = "Minor negative impact - cancellations slightly reduce accuracy"
    else:
        evaluation = "No negative impact or improvement when including cancellations"
    
    print(f"Impact Assessment: {evaluation}")
    
    return comparison

if __name__ == "__main__":
    compare_validation_results()