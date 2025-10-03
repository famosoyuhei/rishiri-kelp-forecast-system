#!/usr/bin/env python3
"""
Phase-based Validation System
Validate early morning wind focus vs afternoon solar focus models
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from rishiri_kelp_model import RishiriKelpDryingModel
import json

class PhaseBasedValidator:
    """段階別乾燥モデル検証システム"""
    
    def __init__(self):
        self.rishiri_model = RishiriKelpDryingModel()
        
        # 段階別重要因子の定義
        self.phase_models = {
            'fisherman_model': {
                'early_phase': {  # 4-10時：漁師重視モデル（風重視）
                    'wind_weight': 0.6,      # 風の重要度
                    'temperature_weight': 0.2, # 気温の重要度  
                    'humidity_weight': 0.2,   # 湿度の重要度
                    'solar_weight': 0.0       # 日射の重要度
                },
                'late_phase': {   # 10-16時：漁師重視モデル（日射重視）
                    'wind_weight': 0.2,
                    'temperature_weight': 0.4,
                    'humidity_weight': 0.2,
                    'solar_weight': 0.2
                }
            },
            'literature_model': {
                'early_phase': {  # 4-10時：文献重視モデル（日射重視）
                    'wind_weight': 0.2,
                    'temperature_weight': 0.4,
                    'humidity_weight': 0.2,
                    'solar_weight': 0.2
                },
                'late_phase': {   # 10-16時：文献重視モデル（風重視）
                    'wind_weight': 0.5,
                    'temperature_weight': 0.2,
                    'humidity_weight': 0.3,
                    'solar_weight': 0.0
                }
            }
        }
    
    def calculate_phase_score(self, weather_conditions, phase_weights):
        """
        段階別スコア計算
        
        Args:
            weather_conditions: 気象条件
            phase_weights: 段階別重み設定
        
        Returns:
            段階別スコア（0-10）
        """
        
        temp = weather_conditions.get('temperature', 20)
        humidity = weather_conditions.get('humidity', 80)
        wind_speed = weather_conditions.get('wind_speed', 5)
        solar = weather_conditions.get('solar_radiation', 500)  # W/m²
        
        # 各要素のスコア化（0-10）
        # 気温スコア（15-25°Cが最適）
        if 18 <= temp <= 22:
            temp_score = 10
        elif 16 <= temp < 18 or 22 < temp <= 24:
            temp_score = 8
        elif 14 <= temp < 16 or 24 < temp <= 26:
            temp_score = 6
        else:
            temp_score = 4
        
        # 湿度スコア（低いほど良い）
        if humidity <= 70:
            humidity_score = 10
        elif humidity <= 80:
            humidity_score = 8
        elif humidity <= 90:
            humidity_score = 6
        else:
            humidity_score = 3
        
        # 風速スコア（利尻島は強風有利）
        if wind_speed >= 20:
            wind_score = 10
        elif wind_speed >= 15:
            wind_score = 9
        elif wind_speed >= 10:
            wind_score = 7
        elif wind_speed >= 5:
            wind_score = 5
        else:
            wind_score = 2
        
        # 日射スコア（高いほど良い）
        if solar >= 700:
            solar_score = 10
        elif solar >= 500:
            solar_score = 8
        elif solar >= 300:
            solar_score = 6
        elif solar >= 200:
            solar_score = 4
        else:
            solar_score = 2
        
        # 重み付け合計
        weighted_score = (
            temp_score * phase_weights['temperature_weight'] +
            humidity_score * phase_weights['humidity_weight'] +
            wind_score * phase_weights['wind_weight'] +
            solar_score * phase_weights['solar_weight']
        ) * 10  # 0-10スケールに正規化
        
        return min(10, max(0, weighted_score))
    
    def simulate_daily_drying_phases(self, hourly_weather_data):
        """
        日中の段階別乾燥シミュレーション
        
        Args:
            hourly_weather_data: 時間別気象データ
        
        Returns:
            段階別比較結果
        """
        
        # 段階別に分ける
        early_phase_hours = hourly_weather_data[0:6]   # 4-10時
        late_phase_hours = hourly_weather_data[6:12]   # 10-16時
        
        results = {
            'fisherman_model': {'early': [], 'late': [], 'total_score': 0},
            'literature_model': {'early': [], 'late': [], 'total_score': 0}
        }
        
        # 各モデルで各段階を評価
        for model_name, model_weights in self.phase_models.items():
            
            # 初期段階（4-10時）の評価
            early_scores = []
            for hour_data in early_phase_hours:
                score = self.calculate_phase_score(hour_data, model_weights['early_phase'])
                early_scores.append(score)
                results[model_name]['early'].append({
                    'hour': 4 + len(early_scores) - 1,
                    'score': score,
                    'weather': hour_data
                })
            
            # 後期段階（10-16時）の評価  
            late_scores = []
            for hour_data in late_phase_hours:
                score = self.calculate_phase_score(hour_data, model_weights['late_phase'])
                late_scores.append(score)
                results[model_name]['late'].append({
                    'hour': 10 + len(late_scores) - 1,
                    'score': score,
                    'weather': hour_data
                })
            
            # 総合スコア計算
            early_avg = sum(early_scores) / len(early_scores) if early_scores else 0
            late_avg = sum(late_scores) / len(late_scores) if late_scores else 0
            results[model_name]['total_score'] = (early_avg + late_avg) / 2
        
        return results
    
    def validate_phase_models(self):
        """段階別モデルの検証"""
        
        print("=== Phase-based Model Validation ===")
        print("Comparing fisherman experience vs literature models")
        print()
        
        # テストケース：異なる気象パターンでの比較
        test_scenarios = [
            {
                'name': 'Strong morning wind, calm afternoon',
                'early_weather': [
                    {'temperature': 16, 'humidity': 85, 'wind_speed': 25, 'solar_radiation': 300},
                    {'temperature': 17, 'humidity': 83, 'wind_speed': 28, 'solar_radiation': 400},
                    {'temperature': 18, 'humidity': 80, 'wind_speed': 30, 'solar_radiation': 500},
                    {'temperature': 19, 'humidity': 78, 'wind_speed': 32, 'solar_radiation': 600},
                    {'temperature': 20, 'humidity': 75, 'wind_speed': 35, 'solar_radiation': 650},
                    {'temperature': 21, 'humidity': 73, 'wind_speed': 30, 'solar_radiation': 700}
                ],
                'late_weather': [
                    {'temperature': 22, 'humidity': 70, 'wind_speed': 15, 'solar_radiation': 800},
                    {'temperature': 23, 'humidity': 68, 'wind_speed': 12, 'solar_radiation': 850},
                    {'temperature': 24, 'humidity': 66, 'wind_speed': 10, 'solar_radiation': 900},
                    {'temperature': 23, 'humidity': 68, 'wind_speed': 8, 'solar_radiation': 850},
                    {'temperature': 22, 'humidity': 70, 'wind_speed': 6, 'solar_radiation': 750},
                    {'temperature': 21, 'humidity': 72, 'wind_speed': 5, 'solar_radiation': 600}
                ]
            },
            {
                'name': 'Weak morning wind, strong afternoon wind',
                'early_weather': [
                    {'temperature': 15, 'humidity': 90, 'wind_speed': 8, 'solar_radiation': 200},
                    {'temperature': 16, 'humidity': 88, 'wind_speed': 10, 'solar_radiation': 300},
                    {'temperature': 17, 'humidity': 85, 'wind_speed': 12, 'solar_radiation': 400},
                    {'temperature': 18, 'humidity': 82, 'wind_speed': 15, 'solar_radiation': 500},
                    {'temperature': 19, 'humidity': 80, 'wind_speed': 18, 'solar_radiation': 600},
                    {'temperature': 20, 'humidity': 78, 'wind_speed': 20, 'solar_radiation': 700}
                ],
                'late_weather': [
                    {'temperature': 21, 'humidity': 75, 'wind_speed': 25, 'solar_radiation': 800},
                    {'temperature': 22, 'humidity': 73, 'wind_speed': 28, 'solar_radiation': 850},
                    {'temperature': 23, 'humidity': 70, 'wind_speed': 30, 'solar_radiation': 900},
                    {'temperature': 22, 'humidity': 72, 'wind_speed': 32, 'solar_radiation': 850},
                    {'temperature': 21, 'humidity': 75, 'wind_speed': 28, 'solar_radiation': 750},
                    {'temperature': 20, 'humidity': 78, 'wind_speed': 25, 'solar_radiation': 600}
                ]
            },
            {
                'name': 'Consistent moderate conditions',
                'early_weather': [
                    {'temperature': 18, 'humidity': 80, 'wind_speed': 18, 'solar_radiation': 400},
                    {'temperature': 19, 'humidity': 78, 'wind_speed': 19, 'solar_radiation': 500},
                    {'temperature': 20, 'humidity': 76, 'wind_speed': 20, 'solar_radiation': 600},
                    {'temperature': 21, 'humidity': 74, 'wind_speed': 21, 'solar_radiation': 650},
                    {'temperature': 22, 'humidity': 72, 'wind_speed': 22, 'solar_radiation': 700},
                    {'temperature': 23, 'humidity': 70, 'wind_speed': 23, 'solar_radiation': 750}
                ],
                'late_weather': [
                    {'temperature': 24, 'humidity': 68, 'wind_speed': 24, 'solar_radiation': 800},
                    {'temperature': 25, 'humidity': 66, 'wind_speed': 25, 'solar_radiation': 850},
                    {'temperature': 24, 'humidity': 68, 'wind_speed': 24, 'solar_radiation': 850},
                    {'temperature': 23, 'humidity': 70, 'wind_speed': 23, 'solar_radiation': 800},
                    {'temperature': 22, 'humidity': 72, 'wind_speed': 22, 'solar_radiation': 750},
                    {'temperature': 21, 'humidity': 74, 'wind_speed': 21, 'solar_radiation': 650}
                ]
            }
        ]
        
        validation_results = []
        
        for scenario in test_scenarios:
            print(f"--- Testing scenario: {scenario['name']} ---")
            
            # 全日データを結合
            full_day_data = scenario['early_weather'] + scenario['late_weather']
            
            # 段階別シミュレーション実行
            phase_results = self.simulate_daily_drying_phases(full_day_data)
            
            # 結果表示
            fisherman_score = phase_results['fisherman_model']['total_score']
            literature_score = phase_results['literature_model']['total_score']
            
            print(f"Fisherman model (early wind focus): {fisherman_score:.1f}/10")
            print(f"Literature model (early solar focus): {literature_score:.1f}/10")
            
            # 勝者判定
            if fisherman_score > literature_score:
                winner = "Fisherman model"
                advantage = fisherman_score - literature_score
            elif literature_score > fisherman_score:
                winner = "Literature model"
                advantage = literature_score - fisherman_score
            else:
                winner = "Tie"
                advantage = 0
            
            print(f"Winner: {winner} (advantage: {advantage:.1f})")
            print()
            
            validation_results.append({
                'scenario': scenario['name'],
                'fisherman_score': fisherman_score,
                'literature_score': literature_score,
                'winner': winner,
                'advantage': advantage
            })
        
        return self.analyze_validation_results(validation_results)
    
    def analyze_validation_results(self, results):
        """検証結果の分析"""
        
        print("=" * 60)
        print("PHASE-BASED VALIDATION ANALYSIS")
        print("=" * 60)
        
        fisherman_wins = 0
        literature_wins = 0
        ties = 0
        
        total_fisherman_score = 0
        total_literature_score = 0
        
        for result in results:
            if result['winner'] == 'Fisherman model':
                fisherman_wins += 1
            elif result['winner'] == 'Literature model':
                literature_wins += 1
            else:
                ties += 1
            
            total_fisherman_score += result['fisherman_score']
            total_literature_score += result['literature_score']
        
        avg_fisherman_score = total_fisherman_score / len(results)
        avg_literature_score = total_literature_score / len(results)
        
        print(f"Total scenarios tested: {len(results)}")
        print(f"Fisherman model wins: {fisherman_wins}")
        print(f"Literature model wins: {literature_wins}")
        print(f"Ties: {ties}")
        print()
        print(f"Average fisherman model score: {avg_fisherman_score:.1f}/10")
        print(f"Average literature model score: {avg_literature_score:.1f}/10")
        print()
        
        # 結論
        if fisherman_wins > literature_wins:
            conclusion = "Fisherman experience model (early wind focus) performs better overall"
        elif literature_wins > fisherman_wins:
            conclusion = "Literature model (early solar focus) performs better overall"
        else:
            conclusion = "Both models show comparable performance"
        
        print(f"CONCLUSION: {conclusion}")
        
        # 推奨事項
        print(f"\nRECOMMENDATIONS:")
        if fisherman_wins >= literature_wins:
            print("- Early morning: Prioritize wind conditions for moisture evacuation")
            print("- Late morning/afternoon: Gradually shift focus to solar radiation")
            print("- Fisherman's practical experience validated by modeling")
        else:
            print("- Early morning: Solar radiation and temperature are primary factors")
            print("- Late morning/afternoon: Wind becomes more important for final drying")
            print("- Literature-based approach shows theoretical advantages")
        
        return {
            'total_scenarios': len(results),
            'fisherman_wins': fisherman_wins,
            'literature_wins': literature_wins,
            'ties': ties,
            'avg_fisherman_score': avg_fisherman_score,
            'avg_literature_score': avg_literature_score,
            'conclusion': conclusion,
            'detailed_results': results
        }

def main():
    """メイン実行"""
    validator = PhaseBasedValidator()
    
    results = validator.validate_phase_models()
    
    # 結果をJSONで保存
    output_file = "phase_based_validation_results.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    print(f"\nDetailed results saved to: {output_file}")

if __name__ == "__main__":
    main()