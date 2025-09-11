#!/usr/bin/env python3
"""
Kelp Drying Quantitative Model
Based on scientific formulas from Hokkaido research
"""

import math
import numpy as np

class KelpDryingModel:
    """昆布乾燥速度の定量的モデル"""
    
    def __init__(self):
        """初期化"""
        pass
    
    def calculate_absolute_humidity(self, temperature, relative_humidity, pressure=1013.25):
        """
        絶対湿度を計算
        
        Args:
            temperature: 気温 [°C]
            relative_humidity: 相対湿度 [%]
            pressure: 気圧 [hPa]
        
        Returns:
            絶対湿度 [kg/kg']
        """
        # 飽和水蒸気圧計算（Magnus式）
        es = 6.112 * math.exp((17.67 * temperature) / (temperature + 243.5))
        
        # 実際の水蒸気圧
        e = es * (relative_humidity / 100.0)
        
        # 絶対湿度計算
        absolute_humidity = 0.622 * e / (pressure - e)
        
        return absolute_humidity
    
    def calculate_wet_bulb_saturation_humidity(self, temperature, relative_humidity, pressure=1013.25):
        """
        湿球温度での飽和絶対湿度 Hm を計算
        
        Args:
            temperature: 気温 [°C]
            relative_humidity: 相対湿度 [%]
            pressure: 気圧 [hPa]
        
        Returns:
            湿球温度での飽和絶対湿度 Hm [kg/kg']
        """
        # 簡易湿球温度計算（近似式）
        wet_bulb_temp = temperature * math.atan(0.151977 * math.sqrt(relative_humidity + 8.313659)) + \
                       math.atan(temperature + relative_humidity) - \
                       math.atan(relative_humidity - 1.676331) + \
                       0.00391838 * (relative_humidity ** 1.5) * math.atan(0.023101 * relative_humidity) - 4.686035
        
        # 湿球温度での飽和水蒸気圧
        es_wb = 6.112 * math.exp((17.67 * wet_bulb_temp) / (wet_bulb_temp + 243.5))
        
        # 湿球温度での飽和絶対湿度
        hm = 0.622 * es_wb / (pressure - es_wb)
        
        return hm
    
    def calculate_drying_coefficient(self, free_water_content, wind_speed):
        """
        乾燥係数 f(Wf, V) を計算
        
        Args:
            free_water_content: 自由含水率 Wf [% d.b.]
            wind_speed: 風速 V [m/s]
        
        Returns:
            乾燥係数 f(Wf, V)
        """
        # 基本係数（自由含水率の二次関数）
        base_coeff = -0.00134 * (free_water_content ** 2) + 0.02162 * free_water_content
        
        # 風速による修正係数
        wind_factor = (0.159 * wind_speed + 0.0132) / 0.050
        
        # 総合係数
        f_wf_v = base_coeff * wind_factor
        
        return max(0, f_wf_v)  # 負値は0に制限
    
    def calculate_drying_rate(self, temperature, relative_humidity, wind_speed, 
                            free_water_content, pressure=1013.25):
        """
        昆布の乾燥速度 Rc を計算
        
        Args:
            temperature: 気温 [°C]
            relative_humidity: 相対湿度 [%]
            wind_speed: 風速 [m/s]
            free_water_content: 自由含水率 [% d.b.]
            pressure: 気圧 [hPa]
        
        Returns:
            乾燥速度 Rc [kg/(kg·s)]
        """
        # 湿球温度での飽和絶対湿度 Hm
        hm = self.calculate_wet_bulb_saturation_humidity(temperature, relative_humidity, pressure)
        
        # 空気の絶対湿度 H
        h = self.calculate_absolute_humidity(temperature, relative_humidity, pressure)
        
        # 乾燥係数
        f_wf_v = self.calculate_drying_coefficient(free_water_content, wind_speed)
        
        # 乾燥速度計算
        rc = f_wf_v * (hm - h)
        
        return max(0, rc)  # 負値は0に制限
    
    def simulate_drying_process(self, weather_data, initial_water_content=300.0, target_water_content=15.0):
        """
        時系列気象データを用いて乾燥過程をシミュレーション
        
        Args:
            weather_data: 時系列気象データのリスト
                [{temperature, relative_humidity, wind_speed, time}, ...]
            initial_water_content: 初期含水率 [% d.b.]
            target_water_content: 目標含水率 [% d.b.]
        
        Returns:
            乾燥シミュレーション結果
        """
        results = []
        current_water_content = initial_water_content
        total_time = 0
        
        for i, data in enumerate(weather_data):
            temp = data['temperature']
            humidity = data['relative_humidity']
            wind = data['wind_speed']
            time_step = data.get('time_step', 3600)  # デフォルト1時間
            
            # 自由含水率（簡易モデル：含水率から平衡含水率を差し引いた値）
            equilibrium_water = max(8.0, 15.0 - temp * 0.1)  # 簡易平衡含水率
            free_water = max(0, current_water_content - equilibrium_water)
            
            # 乾燥速度計算
            drying_rate = self.calculate_drying_rate(temp, humidity, wind, free_water)
            
            # 含水率更新（時間積分）
            water_loss = drying_rate * time_step
            current_water_content = max(target_water_content, current_water_content - water_loss * 100)
            
            # 結果記録
            result = {
                'time': total_time,
                'hour': i,
                'temperature': temp,
                'humidity': humidity,
                'wind_speed': wind,
                'water_content': current_water_content,
                'free_water_content': free_water,
                'drying_rate': drying_rate,
                'water_loss': water_loss,
                'drying_completed': current_water_content <= target_water_content
            }
            results.append(result)
            
            total_time += time_step / 3600  # 時間に変換
            
            # 目標含水率達成で終了
            if current_water_content <= target_water_content:
                break
        
        return results
    
    def evaluate_drying_conditions(self, weather_forecast):
        """
        気象予報データから乾燥条件を定量評価
        
        Args:
            weather_forecast: 気象予報データ
        
        Returns:
            乾燥条件の評価結果
        """
        # 標準的な初期条件でシミュレーション
        simulation = self.simulate_drying_process(weather_forecast)
        
        if not simulation:
            return {"error": "シミュレーション失敗"}
        
        # 乾燥完了時間予測
        completed_hours = None
        for result in simulation:
            if result['drying_completed']:
                completed_hours = result['hour']
                break
        
        # 最終含水率
        final_water_content = simulation[-1]['water_content']
        
        # 平均乾燥速度
        avg_drying_rate = np.mean([r['drying_rate'] for r in simulation])
        
        # 条件評価
        if completed_hours is not None and completed_hours <= 8:
            condition = "Excellent"
            score = 5
        elif completed_hours is not None and completed_hours <= 10:
            condition = "Good"
            score = 4
        elif final_water_content <= 25:
            condition = "Fair"
            score = 3
        elif final_water_content <= 50:
            condition = "Poor"
            score = 2
        else:
            condition = "Very Poor"
            score = 1
        
        return {
            "condition": condition,
            "score": score,
            "predicted_drying_hours": completed_hours,
            "final_water_content": final_water_content,
            "average_drying_rate": avg_drying_rate,
            "simulation_results": simulation[-5:]  # 最後の5時間分
        }

def test_kelp_drying_model():
    """テスト用の実行例"""
    model = KelpDryingModel()
    
    # サンプル気象データ（1日分）
    sample_weather = []
    for hour in range(12):  # 12時間分
        sample_weather.append({
            'temperature': 20 + 5 * math.sin(hour * math.pi / 6),  # 15-25°C変化
            'relative_humidity': 70 - 10 * math.sin(hour * math.pi / 6),  # 60-80%変化
            'wind_speed': 2.0 + 1.0 * math.sin(hour * math.pi / 4),  # 1-3m/s変化
            'time_step': 3600  # 1時間
        })
    
    # 乾燥条件評価
    evaluation = model.evaluate_drying_conditions(sample_weather)
    
    print("=== Kelp Drying Condition Evaluation Test ===")
    print(f"Drying condition: {evaluation['condition']}")
    print(f"Score: {evaluation['score']}/5")
    print(f"Predicted drying hours: {evaluation['predicted_drying_hours']} hours")
    print(f"Final water content: {evaluation['final_water_content']:.1f}%")
    print(f"Average drying rate: {evaluation['average_drying_rate']:.6f} kg/(kg·s)")

if __name__ == "__main__":
    test_kelp_drying_model()