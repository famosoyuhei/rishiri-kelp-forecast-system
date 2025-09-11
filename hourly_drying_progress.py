#!/usr/bin/env python3
"""
Hourly Drying Progress Display System
Generate detailed hourly drying progression forecasts
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from rishiri_kelp_model import RishiriKelpDryingModel
import json

class HourlyDryingProgressGenerator:
    """時間別乾燥進行表示システム"""
    
    def __init__(self):
        self.rishiri_model = RishiriKelpDryingModel()
        
        # 乾燥段階の定義
        self.drying_stages = {
            300: "Initial state (wet kelp)",
            200: "Surface moisture reduction",
            100: "Mid-stage drying",
            50: "Late-stage drying",
            25: "Final drying",
            15: "Complete drying achieved"
        }
    
    def simulate_hourly_drying(self, hourly_weather_data, terrain_info=None, initial_moisture=300):
        """
        時間別乾燥進行をシミュレート
        
        Args:
            hourly_weather_data: 時間別気象データ
            terrain_info: 地形情報
            initial_moisture: 初期含水率 (%)
        
        Returns:
            時間別乾燥進行データ
        """
        
        progress_data = []
        current_moisture = initial_moisture
        work_start_hour = 4  # 午前4時開始
        
        for hour_index, hour_data in enumerate(hourly_weather_data):
            current_hour = work_start_hour + hour_index
            
            if current_hour > 16:  # 午後4時まで
                break
            
            # その時点の気象条件
            weather_conditions = {
                'temperature_avg': hour_data.get('temperature', 20),
                'humidity_avg': hour_data.get('relative_humidity', 80),
                'wind_speed_avg': hour_data.get('wind_speed', 5),
                'cloud_cover_avg': hour_data.get('cloud_cover', 50)
            }
            
            # 地形補正を適用
            terrain_corrections = None
            if terrain_info:
                terrain_corrections = {
                    'temperature_correction': terrain_info.get('temperature_correction', 0),
                    'humidity_correction': terrain_info.get('humidity_correction', 0),
                    'wind_speed_correction': terrain_info.get('wind_speed_correction', 0)
                }
            
            # 利尻島モデルで乾燥効率を評価
            drying_evaluation = self.rishiri_model.evaluate_drying_conditions(weather_conditions, terrain_corrections)
            drying_score = drying_evaluation['score']
            
            # 乾燥速度計算（簡易モデル）
            # スコアが高いほど乾燥速度が大きい
            base_drying_rate = max(0, drying_score * 2.5)  # 0-25%/hour の範囲
            
            # 含水率による減衰効果（含水率が低いほど乾燥が遅くなる）
            moisture_factor = min(1.0, current_moisture / 100)
            actual_drying_rate = base_drying_rate * moisture_factor
            
            # 1時間後の含水率
            moisture_loss = actual_drying_rate
            new_moisture = max(15, current_moisture - moisture_loss)  # 最低15%まで
            
            # 乾燥段階の判定
            stage = self.get_drying_stage(new_moisture)
            
            # 条件評価
            condition_assessment = self.assess_hourly_conditions(weather_conditions, terrain_corrections)
            
            hour_progress = {
                'hour': current_hour,
                'time_display': f"{current_hour:02d}:00",
                'weather': {
                    'temperature': weather_conditions['temperature_avg'],
                    'humidity': weather_conditions['humidity_avg'],
                    'wind_speed': weather_conditions['wind_speed_avg'],
                    'cloud_cover': weather_conditions['cloud_cover_avg']
                },
                'drying_metrics': {
                    'score': round(drying_score, 1),
                    'rate_per_hour': round(actual_drying_rate, 1),
                    'moisture_before': round(current_moisture, 1),
                    'moisture_after': round(new_moisture, 1),
                    'moisture_loss': round(moisture_loss, 1)
                },
                'stage': {
                    'name': stage,
                    'progress_percent': max(0, 100 - (new_moisture - 15) / (initial_moisture - 15) * 100)
                },
                'conditions': condition_assessment,
                'completed': new_moisture <= 15
            }
            
            progress_data.append(hour_progress)
            current_moisture = new_moisture
            
            # 完全乾燥達成で終了
            if new_moisture <= 15:
                break
        
        return self.generate_progress_summary(progress_data, initial_moisture)
    
    def get_drying_stage(self, moisture_level):
        """含水率から乾燥段階を判定"""
        for threshold, stage_name in self.drying_stages.items():
            if moisture_level >= threshold:
                return stage_name
        return "Complete drying achieved"
    
    def assess_hourly_conditions(self, weather, terrain_corrections):
        """時間別条件評価"""
        temp = weather['temperature_avg']
        humidity = weather['humidity_avg']
        wind = weather['wind_speed_avg']
        
        # 地形補正適用
        if terrain_corrections:
            temp += terrain_corrections.get('temperature_correction', 0)
            humidity += terrain_corrections.get('humidity_correction', 0)
            wind = max(0, wind + terrain_corrections.get('wind_speed_correction', 0))
        
        conditions = []
        
        # 温度条件
        if temp >= 20:
            conditions.append("Good temp")
        elif temp >= 16:
            conditions.append("Fair temp")
        else:
            conditions.append("Low temp")
        
        # 湿度条件
        if humidity <= 75:
            conditions.append("Low humidity")
        elif humidity <= 85:
            conditions.append("Mid humidity")
        else:
            conditions.append("High humidity")
        
        # 風速条件
        if wind >= 20:
            conditions.append("Strong wind")
        elif wind >= 10:
            conditions.append("Fair wind")
        else:
            conditions.append("Weak wind")
        
        return conditions
    
    def generate_progress_summary(self, progress_data, initial_moisture):
        """進行状況のサマリー生成"""
        
        if not progress_data:
            return {
                'hourly_progress': [],
                'summary': {
                    'completion_possible': False,
                    'estimated_completion_time': None,
                    'final_moisture': initial_moisture,
                    'total_drying_hours': 0
                }
            }
        
        final_hour_data = progress_data[-1]
        completion_possible = final_hour_data['completed']
        
        # 完了予想時刻の計算
        estimated_completion_time = None
        if completion_possible:
            estimated_completion_time = final_hour_data['time_display']
        else:
            # 線形外挿で完了時刻を推定
            if len(progress_data) >= 2:
                last_rate = progress_data[-1]['drying_metrics']['rate_per_hour']
                current_moisture = final_hour_data['drying_metrics']['moisture_after']
                
                if last_rate > 0:
                    remaining_hours = (current_moisture - 15) / last_rate
                    final_hour = final_hour_data['hour'] + remaining_hours
                    
                    if final_hour <= 20:  # 夜8時まで
                        estimated_completion_time = f"{int(final_hour):02d}:{int((final_hour % 1) * 60):02d}"
        
        # 最適作業時間帯の提案
        best_hours = []
        for hour_data in progress_data:
            if hour_data['drying_metrics']['score'] >= 4.0:
                best_hours.append(hour_data['time_display'])
        
        # 注意すべき時間帯
        caution_hours = []
        for hour_data in progress_data:
            if hour_data['drying_metrics']['score'] < 3.0:
                caution_hours.append({
                    'time': hour_data['time_display'],
                    'reason': self.identify_caution_reason(hour_data['weather'])
                })
        
        summary = {
            'completion_possible': completion_possible,
            'estimated_completion_time': estimated_completion_time,
            'final_moisture': round(final_hour_data['drying_metrics']['moisture_after'], 1),
            'total_drying_hours': len(progress_data),
            'best_hours': best_hours,
            'caution_hours': caution_hours,
            'overall_efficiency': self.calculate_overall_efficiency(progress_data)
        }
        
        return {
            'hourly_progress': progress_data,
            'summary': summary
        }
    
    def identify_caution_reason(self, weather):
        """注意理由の特定"""
        reasons = []
        
        if weather['humidity'] > 90:
            reasons.append("High humidity")
        if weather['wind_speed'] < 8:
            reasons.append("Insufficient wind")
        if weather['temperature'] < 16:
            reasons.append("Low temperature")
        if weather['cloud_cover'] > 80:
            reasons.append("Heavy clouds")
            
        return ", ".join(reasons) if reasons else "Poor conditions"
    
    def calculate_overall_efficiency(self, progress_data):
        """総合乾燥効率の計算"""
        if not progress_data:
            return 0
        
        total_score = sum(hour['drying_metrics']['score'] for hour in progress_data)
        average_score = total_score / len(progress_data)
        
        # 0-10スケールを0-100%に変換
        efficiency = min(100, max(0, average_score * 10))
        return round(efficiency, 1)

def test_hourly_progress():
    """時間別進行表示のテスト"""
    
    generator = HourlyDryingProgressGenerator()
    
    # サンプル気象データ（12時間分）
    sample_weather = []
    
    # 朝方（4-8時）：高湿度だが風強め
    for hour in range(4):
        sample_weather.append({
            'temperature': 16 + hour * 0.5,
            'relative_humidity': 92 - hour * 2,
            'wind_speed': 15 + hour,
            'cloud_cover': 80 - hour * 5
        })
    
    # 昼間（8-12時）：条件改善
    for hour in range(4):
        sample_weather.append({
            'temperature': 18 + hour * 1.5,
            'relative_humidity': 84 - hour * 3,
            'wind_speed': 18 + hour * 2,
            'cloud_cover': 60 - hour * 8
        })
    
    # 午後（12-16時）：最適条件
    for hour in range(4):
        sample_weather.append({
            'temperature': 22 + hour * 0.5,
            'relative_humidity': 72 - hour * 2,
            'wind_speed': 22 + hour,
            'cloud_cover': 30 - hour * 5
        })
    
    # 地形情報（森林地帯を想定）
    terrain_info = {
        'temperature_correction': -1.2,  # 標高200m相当
        'humidity_correction': 10,       # 森林効果
        'wind_speed_correction': -2.5    # 森林による風速減少
    }
    
    # 時間別進行シミュレーション実行
    result = generator.simulate_hourly_drying(sample_weather, terrain_info)
    
    print("=== Hourly Drying Progress Test ===")
    print()
    
    # サマリー表示
    summary = result['summary']
    print(f"Completion possible: {'Yes' if summary['completion_possible'] else 'No'}")
    print(f"Estimated completion: {summary['estimated_completion_time'] or 'Not completed'}")
    print(f"Final moisture: {summary['final_moisture']}%")
    print(f"Overall efficiency: {summary['overall_efficiency']}%")
    print()
    
    # 時間別詳細表示
    print("Hourly Progress:")
    print(f"{'Time':<6} {'Temp':<6} {'Humid':<6} {'Wind':<6} {'DryRate':<8} {'Moisture':<8} {'Stage'}")
    print("-" * 70)
    
    for hour_data in result['hourly_progress']:
        weather = hour_data['weather']
        metrics = hour_data['drying_metrics']
        
        print(f"{hour_data['time_display']:<6} "
              f"{weather['temperature']:<6.1f} "
              f"{weather['humidity']:<6.1f} "
              f"{weather['wind_speed']:<6.1f} "
              f"{metrics['rate_per_hour']:<8.1f} "
              f"{metrics['moisture_after']:<8.1f} "
              f"{hour_data['stage']['name']}")
    
    # 推奨事項
    if summary['best_hours']:
        print(f"\nBest hours: {', '.join(summary['best_hours'])}")
    
    if summary['caution_hours']:
        print("\nCaution hours:")
        for caution in summary['caution_hours']:
            print(f"  {caution['time']}: {caution['reason']}")

if __name__ == "__main__":
    test_hourly_progress()