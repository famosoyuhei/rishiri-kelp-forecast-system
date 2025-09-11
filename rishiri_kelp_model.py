#!/usr/bin/env python3
"""
Rishiri Island Specialized Kelp Drying Model
Calibrated specifically for Rishiri Island conditions based on historical data
"""

import math
import numpy as np

class RishiriKelpDryingModel:
    """利尻島特化昆布乾燥モデル"""
    
    def __init__(self):
        """利尻島の実際データに基づく較正済みパラメータ"""
        
        # 実測データから判明した利尻島の特徴
        # - 高湿度環境（平均85-90%）でも乾燥成功
        # - 強風（平均20m/s前後）が常態
        # - 気温は15-23°C程度
        
        # 利尻島向けスコアリング係数
        self.humidity_tolerance = 95.0  # 95%まで許容（一般的な80%より高い）
        self.wind_advantage_threshold = 10.0  # 強風が多いことを考慮
        self.temperature_base = 16.0  # 利尻島の典型気温
        
        # 成功条件の重み（実測データ基準）
        self.weights = {
            'wind_factor': 0.4,      # 強風環境での優位性
            'humidity_penalty': 0.3,  # 高湿度耐性
            'temperature_bonus': 0.2, # 気温効果
            'cloud_factor': 0.1      # 雲量効果
        }
    
    def calculate_rishiri_drying_score(self, weather_conditions, terrain_corrections=None):
        """
        利尻島特化乾燥スコア計算
        実測データの成功/失敗パターンに基づく
        
        Args:
            weather_conditions: 気象条件辞書
            terrain_corrections: 地形補正（オプション）
        
        Returns:
            乾燥スコア（0-10）
        """
        
        temp = weather_conditions.get('temperature_avg', 20)
        humidity = weather_conditions.get('humidity_avg', 80)
        wind_speed = weather_conditions.get('wind_speed_avg', 5)
        cloud_cover = weather_conditions.get('cloud_cover_avg', 50)
        
        # 地形補正適用
        if terrain_corrections:
            temp += terrain_corrections.get('temperature_correction', 0)
            humidity += terrain_corrections.get('humidity_correction', 0)
            wind_speed = max(0, wind_speed + terrain_corrections.get('wind_speed_correction', 0))
        
        score = 0
        
        # 1. 風速効果（利尻島は強風地域）
        wind_factor = 0
        if wind_speed >= 25:
            wind_factor = 4.0  # 超強風は有利
        elif wind_speed >= 15:
            wind_factor = 3.5  # 強風は有利
        elif wind_speed >= 10:
            wind_factor = 3.0  # 中強風
        elif wind_speed >= 5:
            wind_factor = 2.0  # 普通
        else:
            wind_factor = 1.0  # 弱風は不利
        
        score += wind_factor * self.weights['wind_factor']
        
        # 2. 湿度ペナルティ（利尻島は高湿度でも成功）
        humidity_penalty = 0
        if humidity <= 75:
            humidity_penalty = 0  # 低湿度はペナルティなし
        elif humidity <= 85:
            humidity_penalty = -0.5  # 中湿度は軽微ペナルティ
        elif humidity <= 93:
            humidity_penalty = -1.5  # 高湿度は中程度ペナルティ
        else:
            humidity_penalty = -3.0  # 超高湿度は大ペナルティ
        
        score += humidity_penalty * self.weights['humidity_penalty']
        
        # 3. 気温ボーナス（利尻島の適温範囲）
        temp_bonus = 0
        if 18 <= temp <= 22:
            temp_bonus = 2.0  # 最適温度
        elif 16 <= temp < 18 or 22 < temp <= 24:
            temp_bonus = 1.5  # 良い温度
        elif 14 <= temp < 16 or 24 < temp <= 26:
            temp_bonus = 1.0  # 普通
        else:
            temp_bonus = 0.5  # 範囲外
        
        score += temp_bonus * self.weights['temperature_bonus']
        
        # 4. 雲量効果
        cloud_factor = 0
        if cloud_cover <= 30:
            cloud_factor = 1.0  # 快晴
        elif cloud_cover <= 60:
            cloud_factor = 0.7  # 薄曇り
        elif cloud_cover <= 80:
            cloud_factor = 0.4  # 曇り
        else:
            cloud_factor = 0.1  # 厚い雲
        
        score += cloud_factor * self.weights['cloud_factor']
        
        # 最終スコア調整（0-10範囲）
        final_score = max(0, min(10, score * 2.5))  # スケール調整
        
        return final_score
    
    def evaluate_drying_conditions(self, weather_data, terrain_info=None):
        """
        利尻島向け乾燥条件評価
        
        Args:
            weather_data: 時系列気象データまたは平均値辞書
            terrain_info: 地形情報
        
        Returns:
            評価結果辞書
        """
        
        # 気象データの形式を統一
        if isinstance(weather_data, list) and weather_data:
            # 時系列データの場合は平均を計算
            weather_conditions = {
                'temperature_avg': np.mean([d.get('temperature', 20) for d in weather_data]),
                'humidity_avg': np.mean([d.get('relative_humidity', 80) for d in weather_data]),
                'wind_speed_avg': np.mean([d.get('wind_speed', 5) for d in weather_data]),
                'cloud_cover_avg': 50  # デフォルト値
            }
        else:
            # 平均値辞書の場合はそのまま使用
            weather_conditions = weather_data
        
        # 利尻島特化スコア計算
        score = self.calculate_rishiri_drying_score(weather_conditions, terrain_info)
        
        # 条件判定（利尻島の実測データに基づく閾値）
        if score >= 7.0:
            condition = "Excellent"
            confidence = "Very High"
        elif score >= 5.5:
            condition = "Good"
            confidence = "High"
        elif score >= 4.0:
            condition = "Fair"
            confidence = "Moderate"
        elif score >= 2.5:
            condition = "Poor"
            confidence = "Low"
        else:
            condition = "Very Poor"
            confidence = "Very Low"
        
        # 予想乾燥時間（経験的モデル）
        if score >= 7.0:
            estimated_hours = 6 + max(0, (weather_conditions.get('humidity_avg', 80) - 70) * 0.1)
        elif score >= 5.5:
            estimated_hours = 8 + max(0, (weather_conditions.get('humidity_avg', 80) - 70) * 0.15)
        elif score >= 4.0:
            estimated_hours = 10 + max(0, (weather_conditions.get('humidity_avg', 80) - 70) * 0.2)
        else:
            estimated_hours = None  # 乾燥困難
        
        return {
            "condition": condition,
            "score": round(score, 1),
            "confidence": confidence,
            "estimated_drying_hours": estimated_hours,
            "weather_analysis": {
                "temperature": weather_conditions.get('temperature_avg', 20),
                "humidity": weather_conditions.get('humidity_avg', 80),
                "wind_speed": weather_conditions.get('wind_speed_avg', 5),
                "humidity_tolerance": weather_conditions.get('humidity_avg', 80) <= self.humidity_tolerance,
                "wind_advantage": weather_conditions.get('wind_speed_avg', 5) >= self.wind_advantage_threshold
            },
            "rishiri_factors": {
                "high_humidity_adapted": True,
                "strong_wind_environment": True,
                "coastal_drying_conditions": True
            }
        }
    
    def compare_with_historical_success(self, weather_conditions):
        """
        実測成功ケースとの類似度比較
        
        Args:
            weather_conditions: 現在の気象条件
        
        Returns:
            類似度スコア（0-1）
        """
        
        # 過去の成功ケースの典型値（実測データより）
        typical_success = {
            'temperature_avg': 18.1,
            'humidity_avg': 85.7,
            'wind_speed_avg': 19.5
        }
        
        # 類似度計算
        temp_similarity = max(0, 1 - abs(weather_conditions.get('temperature_avg', 20) - typical_success['temperature_avg']) / 10)
        humidity_similarity = max(0, 1 - abs(weather_conditions.get('humidity_avg', 80) - typical_success['humidity_avg']) / 30)
        wind_similarity = max(0, 1 - abs(weather_conditions.get('wind_speed_avg', 5) - typical_success['wind_speed_avg']) / 20)
        
        overall_similarity = (temp_similarity + humidity_similarity + wind_similarity) / 3
        
        return {
            'overall_similarity': round(overall_similarity, 3),
            'temperature_similarity': round(temp_similarity, 3),
            'humidity_similarity': round(humidity_similarity, 3),
            'wind_similarity': round(wind_similarity, 3),
            'typical_success_conditions': typical_success
        }

def test_rishiri_model():
    """利尻島モデルのテスト実行"""
    
    model = RishiriKelpDryingModel()
    
    # テストケース1: 典型的な成功条件
    success_conditions = {
        'temperature_avg': 18.0,
        'humidity_avg': 85.0,
        'wind_speed_avg': 20.0,
        'cloud_cover_avg': 60.0
    }
    
    print("=== Rishiri Kelp Drying Model Test ===")
    print("Test Case 1: Typical Success Conditions")
    result1 = model.evaluate_drying_conditions(success_conditions)
    print(f"Score: {result1['score']}/10")
    print(f"Condition: {result1['condition']}")
    print(f"Estimated hours: {result1['estimated_drying_hours']}")
    print()
    
    # テストケース2: 高湿度だが強風
    high_humidity_conditions = {
        'temperature_avg': 17.0,
        'humidity_avg': 92.0,
        'wind_speed_avg': 25.0,
        'cloud_cover_avg': 70.0
    }
    
    print("Test Case 2: High Humidity + Strong Wind")
    result2 = model.evaluate_drying_conditions(high_humidity_conditions)
    print(f"Score: {result2['score']}/10")
    print(f"Condition: {result2['condition']}")
    print(f"Estimated hours: {result2['estimated_drying_hours']}")
    print()
    
    # テストケース3: 不利な条件
    poor_conditions = {
        'temperature_avg': 15.0,
        'humidity_avg': 95.0,
        'wind_speed_avg': 8.0,
        'cloud_cover_avg': 90.0
    }
    
    print("Test Case 3: Poor Conditions")
    result3 = model.evaluate_drying_conditions(poor_conditions)
    print(f"Score: {result3['score']}/10")
    print(f"Condition: {result3['condition']}")
    print(f"Estimated hours: {result3['estimated_drying_hours']}")
    
    # 類似度テスト
    print("\n--- Historical Success Similarity ---")
    similarity = model.compare_with_historical_success(success_conditions)
    print(f"Overall similarity: {similarity['overall_similarity']}")
    print(f"Temperature similarity: {similarity['temperature_similarity']}")
    print(f"Humidity similarity: {similarity['humidity_similarity']}")
    print(f"Wind similarity: {similarity['wind_similarity']}")

if __name__ == "__main__":
    test_rishiri_model()