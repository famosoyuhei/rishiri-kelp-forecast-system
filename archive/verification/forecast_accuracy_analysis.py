#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
利尻島昆布干し予報システム - 予報精度統計分析
Forecast Accuracy Statistical Analysis

包括的検証結果の詳細分析とレポート生成
"""

import pandas as pd
import numpy as np
import json
from datetime import datetime
import matplotlib.pyplot as plt
from typing import Dict, List, Tuple
import os

class ForecastAccuracyAnalyzer:
    """予報精度分析クラス"""
    
    def __init__(self, validation_file: str):
        self.validation_file = validation_file
        self.results = self.load_validation_results()
        
    def load_validation_results(self) -> Dict:
        """検証結果を読み込み"""
        try:
            with open(self.validation_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Failed to load validation results: {e}")
            return {}
    
    def calculate_performance_metrics(self) -> Dict:
        """予報性能指標を計算"""
        metrics = {}
        
        for days_str, day_results in self.results.items():
            days = int(days_str)
            cm = day_results['confusion_matrix']
            
            # 基本指標
            total = sum(cm.values())
            accuracy = day_results['accuracy_percentage'] / 100
            
            # 精密度、再現率、F1スコア
            tp = cm['true_positive']
            fp = cm['false_positive'] 
            tn = cm['true_negative']
            fn = cm['false_negative']
            
            precision = tp / (tp + fp) if (tp + fp) > 0 else 0
            recall = tp / (tp + fn) if (tp + fn) > 0 else 0
            f1_score = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0
            
            specificity = tn / (tn + fp) if (tn + fp) > 0 else 0
            
            metrics[days] = {
                'accuracy': accuracy,
                'precision': precision,
                'recall': recall, 
                'specificity': specificity,
                'f1_score': f1_score,
                'total_predictions': total,
                'confusion_matrix': cm
            }
        
        return metrics
    
    def analyze_accuracy_trends(self) -> Dict:
        """予報精度の傾向分析"""
        days = list(range(1, 8))
        accuracies = []
        
        for day in days:
            if str(day) in self.results:
                accuracies.append(self.results[str(day)]['accuracy_percentage'])
            else:
                accuracies.append(0)
        
        # 線形回帰による傾向
        slope, intercept = np.polyfit(days, accuracies, 1)
        
        # 統計情報
        trends = {
            'daily_accuracies': dict(zip(days, accuracies)),
            'mean_accuracy': np.mean(accuracies),
            'std_accuracy': np.std(accuracies),
            'best_day': days[np.argmax(accuracies)],
            'worst_day': days[np.argmin(accuracies)],
            'accuracy_slope': slope,
            'accuracy_intercept': intercept,
            'accuracy_decline_per_day': slope
        }
        
        return trends
    
    def analyze_prediction_types(self) -> Dict:
        """予測タイプ別分析"""
        type_analysis = {
            'by_days_ahead': {},
            'overall_distribution': {
                'true_positive': 0,
                'false_positive': 0,
                'true_negative': 0, 
                'false_negative': 0
            }
        }
        
        for days_str, day_results in self.results.items():
            days = int(days_str)
            cm = day_results['confusion_matrix']
            
            total = sum(cm.values())
            
            type_analysis['by_days_ahead'][days] = {
                'true_positive_rate': cm['true_positive'] / total * 100,
                'false_positive_rate': cm['false_positive'] / total * 100,
                'true_negative_rate': cm['true_negative'] / total * 100,
                'false_negative_rate': cm['false_negative'] / total * 100
            }
            
            # 全体への累積
            for key in cm:
                type_analysis['overall_distribution'][key] += cm[key]
        
        # 全体分布の割合計算
        total_overall = sum(type_analysis['overall_distribution'].values())
        percentage_dict = {}
        for key, value in type_analysis['overall_distribution'].items():
            percentage_dict[f'{key}_percentage'] = value / total_overall * 100
        type_analysis['overall_distribution'].update(percentage_dict)
        
        return type_analysis
    
    def identify_problematic_conditions(self) -> Dict:
        """問題のある予報条件を特定"""
        condition_analysis = {
            'false_positive_conditions': [],
            'false_negative_conditions': [],
            'condition_accuracy': {}
        }
        
        for days_str, day_results in self.results.items():
            for result in day_results['detailed_results']:
                condition = result['forecast_condition']
                
                # 条件別精度追跡
                if condition not in condition_analysis['condition_accuracy']:
                    condition_analysis['condition_accuracy'][condition] = {
                        'total': 0,
                        'correct': 0
                    }
                
                condition_analysis['condition_accuracy'][condition]['total'] += 1
                if result['correct']:
                    condition_analysis['condition_accuracy'][condition]['correct'] += 1
                
                # 問題ケース収集
                if result['prediction_type'] == 'false_positive':
                    condition_analysis['false_positive_conditions'].append({
                        'days_ahead': int(days_str),
                        'condition': condition,
                        'score': result['forecast_score'],
                        'spot': result['spot_name'],
                        'date': result['target_date']
                    })
                elif result['prediction_type'] == 'false_negative':
                    condition_analysis['false_negative_conditions'].append({
                        'days_ahead': int(days_str),
                        'condition': condition,
                        'score': result['forecast_score'],
                        'spot': result['spot_name'],
                        'date': result['target_date']
                    })
        
        # 条件別精度を割合に変換
        for condition in condition_analysis['condition_accuracy']:
            stats = condition_analysis['condition_accuracy'][condition]
            stats['accuracy_percentage'] = stats['correct'] / stats['total'] * 100
        
        return condition_analysis
    
    def generate_comprehensive_report(self) -> Dict:
        """包括的分析レポート生成"""
        print("=== Generating Comprehensive Forecast Accuracy Report ===")
        
        # 各種分析実行
        performance_metrics = self.calculate_performance_metrics()
        accuracy_trends = self.analyze_accuracy_trends()
        prediction_types = self.analyze_prediction_types()
        problematic_conditions = self.identify_problematic_conditions()
        
        # レポート構築
        report = {
            'analysis_timestamp': datetime.now().isoformat(),
            'data_summary': {
                'total_validations': len(self.results),
                'validation_period': '1-7 days ahead',
                'total_predictions': sum(day['total_predictions'] for day in self.results.values())
            },
            'performance_metrics': performance_metrics,
            'accuracy_trends': accuracy_trends,
            'prediction_type_analysis': prediction_types,
            'problematic_conditions': problematic_conditions,
            'key_findings': self._generate_key_findings(
                performance_metrics, accuracy_trends, prediction_types, problematic_conditions
            )
        }
        
        return report
    
    def _generate_key_findings(self, metrics, trends, types, problems) -> List[str]:
        """主要な発見事項を生成"""
        findings = []
        
        # 精度傾向
        if trends['accuracy_slope'] < 0:
            findings.append(f"Forecast accuracy declines by {abs(trends['accuracy_slope']):.1f}% per day")
        else:
            findings.append(f"Forecast accuracy improves by {trends['accuracy_slope']:.1f}% per day")
        
        findings.append(f"Best performance at {trends['best_day']}-day ahead ({trends['daily_accuracies'][trends['best_day']]:.1f}%)")
        findings.append(f"Worst performance at {trends['worst_day']}-day ahead ({trends['daily_accuracies'][trends['worst_day']]:.1f}%)")
        
        # F1スコア分析
        best_f1_day = max(metrics.keys(), key=lambda d: metrics[d]['f1_score'])
        findings.append(f"Best F1-score at {best_f1_day}-day ahead ({metrics[best_f1_day]['f1_score']:.3f})")
        
        # 予測タイプ傾向
        overall_dist = types['overall_distribution']
        if overall_dist['false_positive_percentage'] > overall_dist['false_negative_percentage']:
            findings.append("System tends to over-predict success (more false positives)")
        else:
            findings.append("System tends to under-predict success (more false negatives)")
        
        # 条件別問題
        condition_accuracies = problems['condition_accuracy']
        if condition_accuracies:
            worst_condition = min(condition_accuracies.keys(), 
                                key=lambda c: condition_accuracies[c]['accuracy_percentage'])
            findings.append(f"Most problematic condition: {worst_condition} "
                          f"({condition_accuracies[worst_condition]['accuracy_percentage']:.1f}% accuracy)")
        
        return findings
    
    def save_report(self, report: Dict) -> str:
        """レポートを保存"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"forecast_accuracy_analysis_report_{timestamp}.json"
        
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(report, f, indent=2, ensure_ascii=False)
            print(f"Analysis report saved to: {filename}")
            return filename
        except Exception as e:
            print(f"Failed to save report: {e}")
            return ""

def main():
    """メイン実行関数"""
    # 最新の検証結果ファイルを検索
    validation_files = [f for f in os.listdir('.') if f.startswith('comprehensive_forecast_validation_') and f.endswith('.json')]
    
    if not validation_files:
        print("No validation results file found. Please run comprehensive_forecast_validation.py first.")
        return
    
    # 最新ファイルを使用
    latest_file = sorted(validation_files)[-1]
    print(f"Analyzing validation results from: {latest_file}")
    
    # 分析実行
    analyzer = ForecastAccuracyAnalyzer(latest_file)
    report = analyzer.generate_comprehensive_report()
    
    # レポート保存
    report_file = analyzer.save_report(report)
    
    # サマリー表示
    print("\n" + "="*70)
    print("FORECAST ACCURACY ANALYSIS SUMMARY")
    print("="*70)
    
    print(f"Total Predictions: {report['data_summary']['total_predictions']}")
    print(f"Mean Accuracy: {report['accuracy_trends']['mean_accuracy']:.1f}%")
    print(f"Accuracy Standard Deviation: {report['accuracy_trends']['std_accuracy']:.1f}%")
    
    print(f"\nKey Findings:")
    for i, finding in enumerate(report['key_findings'], 1):
        print(f"  {i}. {finding}")
    
    # 日別パフォーマンス詳細
    print(f"\nDetailed Performance by Days Ahead:")
    for days in range(1, 8):
        if days in report['performance_metrics']:
            metrics = report['performance_metrics'][days]
            print(f"  {days}-day: Accuracy={metrics['accuracy']:.1%}, "
                  f"Precision={metrics['precision']:.3f}, "
                  f"Recall={metrics['recall']:.3f}, "
                  f"F1={metrics['f1_score']:.3f}")
    
    return report

if __name__ == "__main__":
    main()