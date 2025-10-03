#!/usr/bin/env python3
"""
利尻島昆布干場予報精度検証システム
Horizontal & Vertical Forecast Accuracy Validation System

水平検証: 特定干場の時系列予報精度向上検証 (7日前→翌日予報)
垂直検証: 同一日の全干場予報一貫性・空間連続性検証
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime, timedelta
import sqlite3
import json
from typing import Dict, List, Tuple, Optional
from pathlib import Path
import warnings
warnings.filterwarnings('ignore')

class ForecastAccuracyValidator:
    def __init__(self, spots_file='hoshiba_spots.csv', terrain_db='rishiri_terrain.db'):
        """予報精度検証システム初期化"""
        self.spots_df = pd.read_csv(spots_file)
        self.terrain_db = terrain_db
        self.forecast_data = {}
        self.validation_results = {}
        
        # 日本語フォント設定
        plt.rcParams['font.family'] = 'DejaVu Sans'
        sns.set_style("whitegrid")
        
    def load_forecast_data(self, target_date: str = "2024-08-25") -> Dict:
        """
        予報データ読み込み（7日前から翌日まで）
        
        Args:
            target_date: 検証対象日 (YYYY-MM-DD)
            
        Returns:
            Dict: 各予報日のデータ
        """
        target_dt = datetime.strptime(target_date, "%Y-%m-%d")
        forecast_data = {}
        
        # 7日前から翌日予報まで
        for days_ahead in range(7, 0, -1):
            forecast_date = target_dt - timedelta(days=days_ahead)
            forecast_key = f"{days_ahead}d_ahead"
            
            # 模擬予報データ生成（実際のAPIから取得する部分）
            forecast_data[forecast_key] = self._generate_mock_forecast_data(
                forecast_date, target_dt, days_ahead
            )
            
        return forecast_data
    
    def _generate_mock_forecast_data(self, forecast_date: datetime, target_date: datetime, 
                                   days_ahead: int) -> Dict:
        """
        模擬予報データ生成
        実際の運用では気象APIから取得
        """
        np.random.seed(int(forecast_date.timestamp()) % 1000)
        
        forecast_data = {}
        base_uncertainty = 0.1 + (days_ahead - 1) * 0.05  # 日数が増えるほど不確実性増加
        
        for idx, row in self.spots_df.iterrows():
            spot_name = row['name']
            lat, lon = row['lat'], row['lon']
            
            # 地理的位置による基本パターン
            base_temp = 20 + 5 * np.sin(lat * np.pi / 180) + np.random.normal(0, base_uncertainty)
            base_humidity = 70 + 10 * np.cos(lon * np.pi / 180) + np.random.normal(0, base_uncertainty * 5)
            base_wind = 5 + 3 * np.random.random() + np.random.normal(0, base_uncertainty * 2)
            
            # 予報精度は日数が近づくほど向上
            accuracy_factor = 1 - (days_ahead - 1) * 0.08
            
            forecast_data[spot_name] = {
                'temperature': max(0, base_temp * accuracy_factor),
                'humidity': max(0, min(100, base_humidity * accuracy_factor)),
                'wind_speed': max(0, base_wind * accuracy_factor),
                'forecast_date': forecast_date.isoformat(),
                'target_date': target_date.isoformat(),
                'days_ahead': days_ahead,
                'drying_suitability': self._calculate_drying_suitability(
                    base_temp * accuracy_factor, 
                    base_humidity * accuracy_factor, 
                    base_wind * accuracy_factor
                )
            }
            
        return forecast_data
    
    def _calculate_drying_suitability(self, temp: float, humidity: float, wind: float) -> float:
        """昆布干し適性度計算"""
        # 温度係数 (15-25°Cが最適)
        temp_factor = 1.0 if 15 <= temp <= 25 else max(0.2, 1.0 - abs(temp - 20) * 0.05)
        
        # 湿度係数 (40-70%が最適)
        humidity_factor = 1.0 if 40 <= humidity <= 70 else max(0.2, 1.0 - abs(humidity - 55) * 0.02)
        
        # 風速係数 (3-8m/sが最適)
        wind_factor = 1.0 if 3 <= wind <= 8 else max(0.2, 1.0 - abs(wind - 5.5) * 0.1)
        
        return min(1.0, temp_factor * humidity_factor * wind_factor)
    
    def horizontal_validation(self, target_date: str = "2024-08-25", 
                            target_spots: List[str] = None) -> Dict:
        """
        水平検証: 特定干場の時系列予報精度検証
        
        Args:
            target_date: 検証対象日
            target_spots: 検証対象干場リスト（Noneで全干場）
            
        Returns:
            Dict: 水平検証結果
        """
        if target_spots is None:
            target_spots = self.spots_df['name'].tolist()[:5]  # サンプルとして5箇所
            
        forecast_data = self.load_forecast_data(target_date)
        
        # 実測値（模擬）
        actual_data = self._generate_actual_data(target_date)
        
        horizontal_results = {}
        
        for spot in target_spots:
            spot_results = {
                'forecast_progression': [],
                'accuracy_metrics': {},
                'improvement_trend': {}
            }
            
            # 各予報段階の精度計算
            for days_ahead in range(7, 0, -1):
                forecast_key = f"{days_ahead}d_ahead"
                
                if forecast_key in forecast_data and spot in forecast_data[forecast_key]:
                    forecast = forecast_data[forecast_key][spot]
                    actual = actual_data[spot]
                    
                    # 予報精度メトリクス計算
                    temp_error = abs(forecast['temperature'] - actual['temperature'])
                    humidity_error = abs(forecast['humidity'] - actual['humidity'])
                    wind_error = abs(forecast['wind_speed'] - actual['wind_speed'])
                    suitability_error = abs(forecast['drying_suitability'] - actual['drying_suitability'])
                    
                    spot_results['forecast_progression'].append({
                        'days_ahead': days_ahead,
                        'temperature_error': temp_error,
                        'humidity_error': humidity_error,
                        'wind_error': wind_error,
                        'suitability_error': suitability_error,
                        'overall_accuracy': 1 - (temp_error/30 + humidity_error/100 + 
                                               wind_error/15 + suitability_error)/4
                    })
            
            # 改善傾向分析
            errors = [p['suitability_error'] for p in spot_results['forecast_progression']]
            accuracies = [p['overall_accuracy'] for p in spot_results['forecast_progression']]
            
            spot_results['improvement_trend'] = {
                'error_reduction_rate': (errors[0] - errors[-1]) / errors[0] if errors[0] > 0 else 0,
                'accuracy_improvement_rate': (accuracies[-1] - accuracies[0]) / accuracies[0] if accuracies[0] > 0 else 0,
                'consistent_improvement': all(errors[i] >= errors[i+1] for i in range(len(errors)-1))
            }
            
            horizontal_results[spot] = spot_results
            
        return horizontal_results
    
    def vertical_validation(self, target_date: str = "2024-08-25", 
                          forecast_horizon: int = 1) -> Dict:
        """
        垂直検証: 同一日の全干場予報一貫性検証
        
        Args:
            target_date: 検証対象日
            forecast_horizon: 予報日数（1=翌日予報）
            
        Returns:
            Dict: 垂直検証結果
        """
        forecast_data = self.load_forecast_data(target_date)
        forecast_key = f"{forecast_horizon}d_ahead"
        
        if forecast_key not in forecast_data:
            return {"error": f"No forecast data for {forecast_horizon} days ahead"}
        
        day_forecast = forecast_data[forecast_key]
        
        # 空間データ準備
        spatial_data = []
        for spot_name, forecast in day_forecast.items():
            spot_info = self.spots_df[self.spots_df['name'] == spot_name].iloc[0]
            spatial_data.append({
                'name': spot_name,
                'latitude': spot_info['lat'],
                'longitude': spot_info['lon'],
                'temperature': forecast['temperature'],
                'humidity': forecast['humidity'],
                'wind_speed': forecast['wind_speed'],
                'drying_suitability': forecast['drying_suitability']
            })
        
        spatial_df = pd.DataFrame(spatial_data)
        
        # 空間連続性検証
        vertical_results = {
            'spatial_consistency': self._analyze_spatial_consistency(spatial_df),
            'outlier_detection': self._detect_outliers(spatial_df),
            'geographic_correlation': self._analyze_geographic_correlation(spatial_df),
            'terrain_influence': self._analyze_terrain_influence(spatial_df)
        }
        
        return vertical_results
    
    def _generate_actual_data(self, target_date: str) -> Dict:
        """実測値データ生成（模擬）"""
        np.random.seed(42)  # 再現性のため固定シード
        actual_data = {}
        
        for idx, row in self.spots_df.iterrows():
            spot_name = row['name']
            lat, lon = row['lat'], row['lon']
            
            # 実測値（予報より少し変動）
            actual_temp = 20 + 5 * np.sin(lat * np.pi / 180) + np.random.normal(0, 0.5)
            actual_humidity = 70 + 10 * np.cos(lon * np.pi / 180) + np.random.normal(0, 2)
            actual_wind = 5 + 3 * np.random.random() + np.random.normal(0, 0.3)
            
            actual_data[spot_name] = {
                'temperature': actual_temp,
                'humidity': max(0, min(100, actual_humidity)),
                'wind_speed': max(0, actual_wind),
                'drying_suitability': self._calculate_drying_suitability(
                    actual_temp, actual_humidity, actual_wind
                )
            }
            
        return actual_data
    
    def _analyze_spatial_consistency(self, spatial_df: pd.DataFrame) -> Dict:
        """空間一貫性分析"""
        metrics = {}
        
        for param in ['temperature', 'humidity', 'wind_speed', 'drying_suitability']:
            values = spatial_df[param].values
            
            # 統計的指標
            metrics[f'{param}_coefficient_of_variation'] = np.std(values) / np.mean(values)
            metrics[f'{param}_range'] = np.max(values) - np.min(values)
            metrics[f'{param}_std'] = np.std(values)
            
            # 空間勾配分析
            coords = spatial_df[['latitude', 'longitude']].values
            gradients = []
            
            for i in range(len(coords)):
                for j in range(i+1, len(coords)):
                    distance = np.sqrt(np.sum((coords[i] - coords[j])**2))
                    value_diff = abs(values[i] - values[j])
                    if distance > 0:
                        gradients.append(value_diff / distance)
            
            metrics[f'{param}_avg_gradient'] = np.mean(gradients) if gradients else 0
            
        return metrics
    
    def _detect_outliers(self, spatial_df: pd.DataFrame) -> Dict:
        """外れ値検出"""
        outliers = {}
        
        for param in ['temperature', 'humidity', 'wind_speed', 'drying_suitability']:
            values = spatial_df[param].values
            q1, q3 = np.percentile(values, [25, 75])
            iqr = q3 - q1
            
            lower_bound = q1 - 1.5 * iqr
            upper_bound = q3 + 1.5 * iqr
            
            outlier_indices = np.where((values < lower_bound) | (values > upper_bound))[0]
            outlier_spots = spatial_df.iloc[outlier_indices]['name'].tolist()
            outlier_values = values[outlier_indices].tolist()
            
            outliers[param] = {
                'count': len(outlier_indices),
                'spots': outlier_spots,
                'values': outlier_values,
                'percentage': len(outlier_indices) / len(values) * 100
            }
            
        return outliers
    
    def _analyze_geographic_correlation(self, spatial_df: pd.DataFrame) -> Dict:
        """地理的相関分析"""
        correlations = {}
        
        # 緯度・経度との相関
        for param in ['temperature', 'humidity', 'wind_speed', 'drying_suitability']:
            lat_corr = np.corrcoef(spatial_df['latitude'], spatial_df[param])[0, 1]
            lon_corr = np.corrcoef(spatial_df['longitude'], spatial_df[param])[0, 1]
            
            correlations[param] = {
                'latitude_correlation': lat_corr,
                'longitude_correlation': lon_corr,
                'geographic_influence': np.sqrt(lat_corr**2 + lon_corr**2)
            }
            
        return correlations
    
    def _analyze_terrain_influence(self, spatial_df: pd.DataFrame) -> Dict:
        """地形影響分析"""
        # 簡易的な地形影響分析
        terrain_analysis = {
            'elevation_correlation': 'Not available - requires elevation data',
            'coastal_distance_effect': 'Not available - requires coastal distance data',
            'topographic_exposure': 'Not available - requires detailed terrain model'
        }
        
        # 位置による影響の推定
        lat_var = np.var(spatial_df['latitude'])
        lon_var = np.var(spatial_df['longitude'])
        
        terrain_analysis['position_variability'] = {
            'latitude_variance': lat_var,
            'longitude_variance': lon_var,
            'spatial_spread': np.sqrt(lat_var + lon_var)
        }
        
        return terrain_analysis
    
    def generate_validation_report(self, target_date: str = "2024-08-25") -> str:
        """総合検証レポート生成"""
        
        # 水平検証実行
        horizontal_results = self.horizontal_validation(target_date)
        
        # 垂直検証実行
        vertical_results = self.vertical_validation(target_date)
        
        # Report generation
        report = f"""
# Rishiri Kelp Drying Forecast Accuracy Validation Report
## Validation Target Date: {target_date}

## 1. Horizontal Validation Results (Time-series Forecast Accuracy Improvement)

"""
        
        for spot, results in horizontal_results.items():
            trend = results['improvement_trend']
            report += f"""
### {spot}
- Error Reduction Rate: {trend['error_reduction_rate']:.2%}
- Accuracy Improvement Rate: {trend['accuracy_improvement_rate']:.2%}
- Consistent Improvement: {'Yes' if trend['consistent_improvement'] else 'No'}
"""
        
        report += f"""
## 2. Vertical Validation Results (Spatial Consistency)

### Outlier Detection Results:
"""
        
        outliers = vertical_results['outlier_detection']
        for param, outlier_info in outliers.items():
            if outlier_info['count'] > 0:
                report += f"- {param}: {outlier_info['count']} spots ({outlier_info['percentage']:.1f}%)\n"
                report += f"  Outlier spots: {', '.join(outlier_info['spots'])}\n"
            else:
                report += f"- {param}: No outliers\n"
        
        spatial_consistency = vertical_results['spatial_consistency']
        report += f"""
### Spatial Consistency Indicators:
- Drying Suitability Coefficient of Variation: {spatial_consistency.get('drying_suitability_coefficient_of_variation', 0):.3f}
- Temperature Coefficient of Variation: {spatial_consistency.get('temperature_coefficient_of_variation', 0):.3f}
- Humidity Coefficient of Variation: {spatial_consistency.get('humidity_coefficient_of_variation', 0):.3f}

## 3. Validation Conclusions

Forecast accuracy was evaluated from both horizontal (time-series) and vertical (spatial) perspectives.
Please refer to the return values of each method for detailed numerical data.
"""
        
        return report
    
    def visualize_validation_results(self, target_date: str = "2024-08-25", 
                                   save_path: str = "validation_plots.png"):
        """検証結果可視化"""
        
        # 水平・垂直検証実行
        horizontal_results = self.horizontal_validation(target_date)
        vertical_results = self.vertical_validation(target_date)
        
        fig, axes = plt.subplots(2, 2, figsize=(15, 12))
        fig.suptitle(f'Forecast Accuracy Validation - {target_date}', fontsize=16)
        
        # 1. 水平検証: 予報精度の時系列変化
        ax1 = axes[0, 0]
        for spot, results in list(horizontal_results.items())[:3]:  # 上位3箇所
            progression = results['forecast_progression']
            days_ahead = [p['days_ahead'] for p in progression]
            overall_accuracy = [p['overall_accuracy'] for p in progression]
            ax1.plot(days_ahead, overall_accuracy, marker='o', label=spot)
        
        ax1.set_xlabel('Days Ahead')
        ax1.set_ylabel('Overall Accuracy')
        ax1.set_title('Horizontal Validation: Accuracy Improvement')
        ax1.legend()
        ax1.grid(True)
        
        # 2. 垂直検証: 空間分布
        ax2 = axes[0, 1]
        spatial_data = []
        for spot_name in self.spots_df['name']:
            spot_info = self.spots_df[self.spots_df['name'] == spot_name].iloc[0]
            spatial_data.append([spot_info['lat'], spot_info['lon']])
        
        spatial_data = np.array(spatial_data)
        scatter = ax2.scatter(spatial_data[:, 1], spatial_data[:, 0], 
                            c=range(len(spatial_data)), cmap='viridis', s=100)
        ax2.set_xlabel('Longitude')
        ax2.set_ylabel('Latitude')
        ax2.set_title('Vertical Validation: Spatial Distribution')
        plt.colorbar(scatter, ax=ax2)
        
        # 3. 外れ値分析
        ax3 = axes[1, 0]
        outlier_counts = []
        params = []
        for param, outlier_info in vertical_results['outlier_detection'].items():
            outlier_counts.append(outlier_info['count'])
            params.append(param.replace('_', ' ').title())
        
        ax3.bar(params, outlier_counts)
        ax3.set_ylabel('Number of Outliers')
        ax3.set_title('Outlier Detection Results')
        ax3.tick_params(axis='x', rotation=45)
        
        # 4. 空間一貫性指標
        ax4 = axes[1, 1]
        consistency_metrics = []
        metric_names = []
        
        spatial_consistency = vertical_results['spatial_consistency']
        for key, value in spatial_consistency.items():
            if 'coefficient_of_variation' in key:
                consistency_metrics.append(value)
                metric_names.append(key.replace('_coefficient_of_variation', '').replace('_', ' ').title())
        
        ax4.bar(metric_names, consistency_metrics)
        ax4.set_ylabel('Coefficient of Variation')
        ax4.set_title('Spatial Consistency Metrics')
        ax4.tick_params(axis='x', rotation=45)
        
        plt.tight_layout()
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        # plt.show()  # Commented out for headless execution
        
        return save_path

def main():
    """Main execution function"""
    validator = ForecastAccuracyValidator()
    
    print("Rishiri Kelp Drying Forecast Accuracy Validation System Starting...")
    
    # Validation execution
    target_date = "2024-08-25"
    
    print(f"\nValidation target date: {target_date}")
    print("=" * 60)
    
    # Horizontal validation
    print("Executing horizontal validation (time-series forecast accuracy)...")
    horizontal_results = validator.horizontal_validation(target_date)
    
    # Vertical validation  
    print("Executing vertical validation (spatial consistency)...")
    vertical_results = validator.vertical_validation(target_date)
    
    # Report generation
    print("Generating validation report...")
    report = validator.generate_validation_report(target_date)
    print(report)
    
    # Visualization
    print("Visualizing results...")
    try:
        plot_path = validator.visualize_validation_results(target_date)
        print(f"Visualization saved: {plot_path}")
    except Exception as e:
        print(f"Visualization skipped due to display limitations: {e}")
        plot_path = "visualization_skipped.png"
    
    # Save results
    results = {
        'horizontal_validation': horizontal_results,
        'vertical_validation': vertical_results,
        'validation_date': target_date,
        'report': report
    }
    
    with open(f'validation_results_{target_date.replace("-", "")}.json', 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2, default=str)
    
    print(f"\nValidation completed! Results saved to validation_results_{target_date.replace('-', '')}.json")
    
    return results

if __name__ == "__main__":
    results = main()