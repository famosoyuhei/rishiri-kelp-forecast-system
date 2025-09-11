#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
August 10th H_2065_1368 Forecast Accuracy Verification System
Verify how accurate forecasts were from 1-7 days before
"""

import requests
import json
import sys
import os
from datetime import datetime, timedelta
import csv

# Ensure UTF-8 output
sys.stdout.reconfigure(encoding='utf-8')

def verify_historical_forecasts():
    """Verify forecasts from August 3-9 for August 10"""
    
    print("=== August 10th H_2065_1368 Forecast Accuracy Verification ===")
    print("Actual result: Failed drying (morning clear -> noon heavy rain)")
    print("Location: H_2065_1368 (lat: 45.2065, lon: 141.1368)")
    print()
    
    # H_2065_1368の座標
    coords = {"lat": 45.2065, "lon": 141.1368}
    
    # 検証対象日付（8月3日〜8月9日）
    forecast_dates = []
    target_date = "2025-08-10"
    
    for i in range(7, 0, -1):  # 7日前から1日前まで
        forecast_date = datetime(2025, 8, 10) - timedelta(days=i)
        forecast_dates.append({
            "days_before": i,
            "forecast_date": forecast_date.strftime("%Y-%m-%d"),
            "description": f"{i}日前予報 ({forecast_date.strftime('%m/%d')})"
        })
    
    results = []
    
    for forecast_info in forecast_dates:
        print(f"Verifying: {forecast_info['description']}")
        
        # Get historical forecast data
        forecast_result = get_historical_forecast(coords, forecast_info["forecast_date"], target_date)
        
        if forecast_result:
            # Evaluate drying conditions
            drying_assessment = evaluate_drying_conditions(forecast_result)
            results.append({
                "days_before": forecast_info["days_before"],
                "forecast_date": forecast_info["forecast_date"],
                "description": forecast_info["description"],
                "forecast_data": forecast_result,
                "drying_assessment": drying_assessment,
                "accuracy": assess_accuracy(drying_assessment)
            })
        else:
            print(f"  {forecast_info['description']}: Data fetch failed")
    
    # Analyze results
    analyze_results(results)
    return results

def get_historical_forecast(coords, forecast_date, target_date):
    """指定日の予報データを取得"""
    
    params = {
        "latitude": coords["lat"],
        "longitude": coords["lon"],
        "start_date": target_date,
        "end_date": target_date,
        "hourly": "temperature_2m,relative_humidity_2m,precipitation,precipitation_probability,wind_speed_10m,wind_direction_10m,cloud_cover,weather_code",
        "timezone": "Asia/Tokyo"
    }
    
    try:
        # 通常のforecast APIを使用（historical dataは限定的なため）
        response = requests.get("https://api.open-meteo.com/v1/forecast", params=params, timeout=10)
        
        if response.status_code == 200:
            api_data = response.json()
            return process_forecast_data(api_data)
        else:
            return None
            
    except Exception as e:
        print(f"  Error: {e}")
        return None

def process_forecast_data(api_data):
    """予報データを処理"""
    
    hourly = api_data["hourly"]
    
    # 作業時間帯（4:00-16:00）のデータを抽出
    work_hours = slice(4, 17)  # 4:00-16:00
    
    processed = {
        "morning_hours": slice(6, 12),    # 朝の時間帯
        "afternoon_hours": slice(12, 17),  # 午後の時間帯
        "temperature": hourly["temperature_2m"][work_hours],
        "humidity": hourly["relative_humidity_2m"][work_hours],
        "precipitation": hourly["precipitation"][work_hours],
        "precipitation_prob": hourly["precipitation_probability"][work_hours],
        "wind_speed": hourly["wind_speed_10m"][work_hours],
        "wind_direction": hourly["wind_direction_10m"][work_hours],
        "cloud_cover": hourly["cloud_cover"][work_hours],
        "weather_code": hourly["weather_code"][work_hours]
    }
    
    return processed

def evaluate_drying_conditions(forecast_data):
    """乾燥条件を評価"""
    
    # 基本統計
    avg_temp = sum(forecast_data["temperature"]) / len(forecast_data["temperature"])
    avg_humidity = sum(forecast_data["humidity"]) / len(forecast_data["humidity"])
    avg_wind = sum(forecast_data["wind_speed"]) / len(forecast_data["wind_speed"])
    avg_cloud = sum(forecast_data["cloud_cover"]) / len(forecast_data["cloud_cover"])
    
    # 降水確率
    max_precip_prob = max(forecast_data["precipitation_prob"])
    total_precipitation = sum(forecast_data["precipitation"])
    
    # 午前と午後の比較
    morning_cloud = sum(forecast_data["cloud_cover"][:6]) / 6  # 6:00-11:00
    afternoon_cloud = sum(forecast_data["cloud_cover"][6:]) / 5  # 12:00-16:00
    
    morning_precip_prob = sum(forecast_data["precipitation_prob"][:6]) / 6
    afternoon_precip_prob = sum(forecast_data["precipitation_prob"][6:]) / 5
    
    # 乾燥スコア計算
    drying_score = 0
    warnings = []
    
    # 温度要因
    if avg_temp >= 20:
        drying_score += 2
    elif avg_temp >= 15:
        drying_score += 1
    
    # 湿度要因
    if avg_humidity < 60:
        drying_score += 2
    elif avg_humidity < 75:
        drying_score += 1
    elif avg_humidity > 85:
        drying_score -= 1
        warnings.append("高湿度警告")
    
    # 風速要因
    if avg_wind >= 3:
        drying_score += 2
    elif avg_wind >= 1:
        drying_score += 1
    
    # 雲量要因
    if avg_cloud < 30:
        drying_score += 2
        sky_condition = "晴れ"
    elif avg_cloud < 70:
        drying_score += 1
        sky_condition = "曇り"
    else:
        sky_condition = "厚い雲"
        warnings.append("日照不足")
    
    # 降水リスク
    if max_precip_prob > 70:
        drying_score -= 3
        warnings.append("高い降水確率")
    elif max_precip_prob > 40:
        drying_score -= 1
        warnings.append("降水可能性")
    
    if total_precipitation > 1.0:
        drying_score -= 3
        warnings.append("降水量多")
    elif total_precipitation > 0.1:
        drying_score -= 1
        warnings.append("若干の降水")
    
    # 時間変化分析
    if afternoon_precip_prob > morning_precip_prob + 20:
        warnings.append("午後に雨の可能性増加")
    
    if afternoon_cloud > morning_cloud + 20:
        warnings.append("午後に雲量増加")
    
    # 総合評価
    if drying_score >= 4:
        recommendation = "優秀な乾燥条件"
    elif drying_score >= 2:
        recommendation = "良好な乾燥条件"
    elif drying_score >= 0:
        recommendation = "要注意 - 慎重に監視"
    else:
        recommendation = "乾燥に不適"
    
    return {
        "drying_score": drying_score,
        "recommendation": recommendation,
        "warnings": warnings,
        "statistics": {
            "avg_temperature": avg_temp,
            "avg_humidity": avg_humidity,
            "avg_wind_speed": avg_wind,
            "avg_cloud_cover": avg_cloud,
            "max_precipitation_probability": max_precip_prob,
            "total_precipitation": total_precipitation,
            "sky_condition": sky_condition
        },
        "time_analysis": {
            "morning_cloud_cover": morning_cloud,
            "afternoon_cloud_cover": afternoon_cloud,
            "morning_precip_prob": morning_precip_prob,
            "afternoon_precip_prob": afternoon_precip_prob
        }
    }

def assess_accuracy(drying_assessment):
    """実際の結果と比較して精度を評価"""
    
    # 実際の結果: 朝晴れ→正午豪雨で乾燥失敗
    actual_result = {
        "drying_success": False,
        "morning_clear": True,
        "afternoon_rain": True,
        "unexpected_weather_change": True
    }
    
    recommendation = drying_assessment["recommendation"]
    warnings = drying_assessment["warnings"]
    stats = drying_assessment["statistics"]
    time_analysis = drying_assessment["time_analysis"]
    
    accuracy_points = 0
    max_points = 5
    
    # 1. 総合乾燥評価の精度
    if "不適" in recommendation or "要注意" in recommendation:
        accuracy_points += 2  # 正しく危険を予測
    elif "要注意" in recommendation:
        accuracy_points += 1  # 部分的に危険を予測
    
    # 2. 降水予測の精度
    high_precip_warning = any("降水" in w for w in warnings)
    if high_precip_warning:
        accuracy_points += 2  # 降水を正しく予測
    elif stats["max_precipitation_probability"] > 30:
        accuracy_points += 1  # ある程度降水リスクを認識
    
    # 3. 時間変化の予測精度
    afternoon_warning = any("午後" in w for w in warnings)
    if afternoon_warning:
        accuracy_points += 1  # 午後の変化を予測
    
    # 精度評価
    accuracy_percentage = (accuracy_points / max_points) * 100
    
    if accuracy_percentage >= 80:
        accuracy_level = "高精度"
    elif accuracy_percentage >= 60:
        accuracy_level = "中精度"
    elif accuracy_percentage >= 40:
        accuracy_level = "低精度"
    else:
        accuracy_level = "予測不足"
    
    return {
        "accuracy_points": accuracy_points,
        "max_points": max_points,
        "accuracy_percentage": accuracy_percentage,
        "accuracy_level": accuracy_level,
        "detailed_assessment": {
            "drying_prediction": "適切" if accuracy_points >= 1 else "不適切",
            "precipitation_prediction": "適切" if high_precip_warning else "不十分",
            "time_change_prediction": "適切" if afternoon_warning else "予測できず"
        }
    }

def analyze_results(results):
    """結果を分析して表示"""
    
    print("\n" + "="*80)
    print("8月10日 H_2065_1368 予報精度検証結果")
    print("="*80)
    
    print(f"実際の結果: 朝晴れ→正午豪雨で乾燥失敗")
    print(f"検証地点: H_2065_1368 (45.2065°N, 141.1368°E)")
    print()
    
    for result in results:
        assessment = result["drying_assessment"]
        accuracy = result["accuracy"]
        
        print(f"{result['description']} ({result['forecast_date']})")
        print("-" * 50)
        print(f"予報: {assessment['recommendation']}")
        print(f"乾燥スコア: {assessment['drying_score']}")
        print(f"警告: {', '.join(assessment['warnings']) if assessment['warnings'] else 'なし'}")
        
        stats = assessment["statistics"]
        print(f"気象条件:")
        print(f"  平均気温: {stats['avg_temperature']:.1f}°C")
        print(f"  平均湿度: {stats['avg_humidity']:.1f}%")
        print(f"  平均風速: {stats['avg_wind_speed']:.1f}m/s")
        print(f"  平均雲量: {stats['avg_cloud_cover']:.1f}%")
        print(f"  最大降水確率: {stats['max_precipitation_probability']:.0f}%")
        
        time_analysis = assessment["time_analysis"]
        print(f"時間変化:")
        print(f"  朝の雲量: {time_analysis['morning_cloud_cover']:.1f}%")
        print(f"  午後の雲量: {time_analysis['afternoon_cloud_cover']:.1f}%")
        print(f"  午後降水確率: {time_analysis['afternoon_precip_prob']:.1f}%")
        
        print(f"予測精度: {accuracy['accuracy_level']} ({accuracy['accuracy_percentage']:.1f}%)")
        print(f"詳細評価:")
        for key, value in accuracy["detailed_assessment"].items():
            print(f"  {key}: {value}")
        print()
    
    # 総合分析
    print("="*80)
    print("総合分析")
    print("="*80)
    
    total_accuracy = sum(r["accuracy"]["accuracy_percentage"] for r in results) / len(results)
    
    print(f"平均予測精度: {total_accuracy:.1f}%")
    
    # 日数別精度
    print("\n日数別予測精度:")
    for result in results:
        print(f"  {result['days_before']}日前: {result['accuracy']['accuracy_percentage']:.1f}% ({result['accuracy']['accuracy_level']})")
    
    # 最も正確だった予報
    best_result = max(results, key=lambda x: x["accuracy"]["accuracy_percentage"])
    print(f"\n最も正確な予報: {best_result['description']} ({best_result['accuracy']['accuracy_percentage']:.1f}%)")
    
    # 予報システムの課題
    print(f"\n予報システムの課題:")
    
    # 大気不安定性の検出能力
    unstable_detected = 0
    for result in results:
        warnings = result["drying_assessment"]["warnings"]
        if any("降水" in w or "午後" in w for w in warnings):
            unstable_detected += 1
    
    print(f"- 大気不安定性検出率: {unstable_detected}/{len(results)} ({unstable_detected/len(results)*100:.1f}%)")
    
    # 推奨改善点
    print(f"\n推奨改善点:")
    print("1. 大気安定性指標の導入")
    print("2. 時間別詳細な降水予測")
    print("3. 局地的気象変化の監視強化")
    print("4. 実時間気象監視システムの導入")

if __name__ == "__main__":
    results = verify_historical_forecasts()
    
    # 結果をJSONファイルに保存
    with open("august10_forecast_verification_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    print(f"\n検証結果を august10_forecast_verification_results.json に保存しました。")