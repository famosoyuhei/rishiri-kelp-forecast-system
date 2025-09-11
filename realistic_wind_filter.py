#!/usr/bin/env python3
"""
Realistic Wind Speed Filter System
Filter out extreme weather conditions from kelp drying analysis
"""

import pandas as pd
import json
from datetime import datetime

class RealisticWindFilter:
    """現実的風速フィルターシステム"""
    
    def __init__(self):
        # 現実的な昆布干し条件の定義
        self.realistic_limits = {
            "max_average_wind": 20.0,    # 平均風速上限 (m/s)
            "max_gust_wind": 35.0,       # 突風上限 (m/s)
            "min_work_wind": 3.0,        # 最低作業風速 (m/s)
            "severe_weather_tolerance": 2 # 悪天候時間の許容値 (hours)
        }
        
        # 天候分類
        self.weather_categories = {
            "normal": "Normal kelp drying conditions",
            "marginal": "Marginal conditions - monitor closely", 
            "storm": "Storm conditions - no kelp drying possible"
        }
    
    def categorize_weather_data(self, weather_data):
        """
        天候データの分類
        
        Args:
            weather_data: 天候データ（辞書形式）
        
        Returns:
            分類結果とフィルタリング情報
        """
        
        avg_wind = weather_data.get('wind_speed_avg', 0)
        max_wind = weather_data.get('wind_speed_max', 0)
        max_gust = weather_data.get('wind_gust_max', 0)
        severe_hours = weather_data.get('severe_weather_hours', 0)
        
        # 分類判定
        if avg_wind > self.realistic_limits["max_average_wind"]:
            category = "storm"
            reason = f"Average wind too high: {avg_wind:.1f} m/s (limit: {self.realistic_limits['max_average_wind']} m/s)"
        elif max_gust > self.realistic_limits["max_gust_wind"]:
            category = "storm"
            reason = f"Gust too high: {max_gust:.1f} m/s (limit: {self.realistic_limits['max_gust_wind']} m/s)"
        elif severe_hours > self.realistic_limits["severe_weather_tolerance"]:
            category = "storm"
            reason = f"Too many severe weather hours: {severe_hours} (limit: {self.realistic_limits['severe_weather_tolerance']})"
        elif avg_wind < self.realistic_limits["min_work_wind"]:
            category = "marginal"
            reason = f"Insufficient wind: {avg_wind:.1f} m/s (minimum: {self.realistic_limits['min_work_wind']} m/s)"
        elif avg_wind > 15.0:  # 強風だが作業可能範囲
            category = "marginal"
            reason = f"Strong but workable wind: {avg_wind:.1f} m/s"
        else:
            category = "normal"
            reason = "Within normal working conditions"
        
        return {
            "category": category,
            "category_description": self.weather_categories[category],
            "reason": reason,
            "is_realistic": category in ["normal", "marginal"],
            "wind_metrics": {
                "average_wind": avg_wind,
                "max_wind": max_wind,
                "max_gust": max_gust,
                "severe_hours": severe_hours
            }
        }
    
    def filter_historical_data(self):
        """過去データの現実的条件フィルタリング"""
        
        print("=== Realistic Wind Speed Filtering ===")
        print("Filtering extreme weather from kelp drying analysis")
        print()
        
        # 検証済み風速データを使用
        suspicious_dates_data = {
            "2025-07-29": {"wind_speed_avg": 14.5, "wind_speed_max": 18.2, "wind_gust_max": 25.1, "severe_weather_hours": 0},
            "2025-07-25": {"wind_speed_avg": 27.8, "wind_speed_max": 32.5, "wind_gust_max": 46.1, "severe_weather_hours": 0},
            "2025-07-15": {"wind_speed_avg": 29.7, "wind_speed_max": 32.8, "wind_gust_max": 45.7, "severe_weather_hours": 2},
            "2025-07-12": {"wind_speed_avg": 27.4, "wind_speed_max": 32.1, "wind_gust_max": 45.0, "severe_weather_hours": 0},
            "2025-07-11": {"wind_speed_avg": 12.3, "wind_speed_max": 16.8, "wind_gust_max": 22.4, "severe_weather_hours": 0},
            "2025-07-10": {"wind_speed_avg": 8.9, "wind_speed_max": 12.1, "wind_gust_max": 16.7, "severe_weather_hours": 0},
            "2025-07-09": {"wind_speed_avg": 11.2, "wind_speed_max": 14.6, "wind_gust_max": 19.8, "severe_weather_hours": 0},
            "2025-07-08": {"wind_speed_avg": 9.7, "wind_speed_max": 13.2, "wind_gust_max": 18.1, "severe_weather_hours": 0},
            "2025-07-07": {"wind_speed_avg": 15.4, "wind_speed_max": 19.8, "wind_gust_max": 26.3, "severe_weather_hours": 0},
            "2025-06-22": {"wind_speed_avg": 38.3, "wind_speed_max": 43.9, "wind_gust_max": 63.4, "severe_weather_hours": 2},
            "2025-06-23": {"wind_speed_avg": 29.0, "wind_speed_max": 35.1, "wind_gust_max": 48.6, "severe_weather_hours": 0},
            "2025-06-25": {"wind_speed_avg": 31.2, "wind_speed_max": 36.5, "wind_gust_max": 50.8, "severe_weather_hours": 0},
            "2025-06-29": {"wind_speed_avg": 30.6, "wind_speed_max": 34.0, "wind_gust_max": 49.3, "severe_weather_hours": 0}
        }
        
        filtering_results = {
            "normal_conditions": [],
            "marginal_conditions": [],
            "storm_conditions": [],
            "summary": {}
        }
        
        for date, weather_data in suspicious_dates_data.items():
            print(f"Analyzing {date}...")
            
            classification = self.categorize_weather_data(weather_data)
            
            result_entry = {
                "date": date,
                "classification": classification,
                "weather_data": weather_data
            }
            
            filtering_results[f"{classification['category']}_conditions"].append(result_entry)
            
            print(f"  Category: {classification['category'].upper()}")
            print(f"  Reason: {classification['reason']}")
            print(f"  Suitable for kelp drying: {'Yes' if classification['is_realistic'] else 'No'}")
            print()
        
        # サマリー生成
        total_days = len(suspicious_dates_data)
        normal_count = len(filtering_results["normal_conditions"])
        marginal_count = len(filtering_results["marginal_conditions"])
        storm_count = len(filtering_results["storm_conditions"])
        
        filtering_results["summary"] = {
            "total_analyzed_days": total_days,
            "normal_days": normal_count,
            "marginal_days": marginal_count,
            "storm_days": storm_count,
            "realistic_percentage": round((normal_count + marginal_count) / total_days * 100, 1),
            "storm_percentage": round(storm_count / total_days * 100, 1)
        }
        
        return self.generate_filtering_report(filtering_results)
    
    def generate_filtering_report(self, results):
        """フィルタリングレポートの生成"""
        
        print("=" * 60)
        print("REALISTIC WIND SPEED FILTERING REPORT")
        print("=" * 60)
        
        summary = results["summary"]
        
        print(f"Total days analyzed: {summary['total_analyzed_days']}")
        print(f"Normal conditions: {summary['normal_days']} days")
        print(f"Marginal conditions: {summary['marginal_days']} days")
        print(f"Storm conditions: {summary['storm_days']} days")
        print()
        print(f"Realistic kelp drying conditions: {summary['realistic_percentage']}%")
        print(f"Extreme weather (storms): {summary['storm_percentage']}%")
        print()
        
        # 正常条件の詳細
        if results["normal_conditions"]:
            print("NORMAL CONDITIONS (Ideal for kelp drying):")
            for entry in results["normal_conditions"]:
                date = entry["date"]
                wind_avg = entry["weather_data"]["wind_speed_avg"]
                print(f"  {date}: Average wind {wind_avg:.1f} m/s - Excellent drying conditions")
        
        print()
        
        # 限界条件の詳細
        if results["marginal_conditions"]:
            print("MARGINAL CONDITIONS (Monitor closely):")
            for entry in results["marginal_conditions"]:
                date = entry["date"]
                wind_avg = entry["weather_data"]["wind_speed_avg"]
                reason = entry["classification"]["reason"]
                print(f"  {date}: Average wind {wind_avg:.1f} m/s - {reason}")
        
        print()
        
        # 嵐条件の詳細
        if results["storm_conditions"]:
            print("STORM CONDITIONS (No kelp drying possible):")
            for entry in results["storm_conditions"]:
                date = entry["date"]
                wind_avg = entry["weather_data"]["wind_speed_avg"]
                wind_max = entry["weather_data"]["wind_speed_max"]
                print(f"  {date}: Average {wind_avg:.1f} m/s, Max {wind_max:.1f} m/s - Hurricane-level")
        
        print()
        
        # 推奨事項
        print("RECOMMENDATIONS:")
        if summary["storm_percentage"] > 50:
            print("- WARNING: Majority of data represents extreme weather conditions")
            print("- Exclude storm days from normal kelp drying model training")
            print("- Use only normal/marginal conditions for accuracy assessment")
        
        if summary["normal_days"] > 0:
            normal_dates = [entry["date"] for entry in results["normal_conditions"]]
            print(f"- Use these {summary['normal_days']} normal condition days for model calibration:")
            for date in normal_dates:
                print(f"  - {date}")
        
        if summary["marginal_days"] > 0:
            print(f"- {summary['marginal_days']} marginal days require careful monitoring but are workable")
        
        print(f"- Corrected realistic wind range: 3.0-20.0 m/s (excludes {summary['storm_days']} storm days)")
        
        return results

def main():
    """メイン実行"""
    filter_system = RealisticWindFilter()
    
    # 現実的条件フィルタリングの実行
    results = filter_system.filter_historical_data()
    
    # 結果をJSONで保存
    output_file = "realistic_wind_filtering_results.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    print(f"\nDetailed filtering results saved to: {output_file}")

if __name__ == "__main__":
    main()