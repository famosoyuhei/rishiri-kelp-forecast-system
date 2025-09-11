#!/usr/bin/env python3
"""
利尻島過去1週間天気データの干場別偏差分析システム
Historical Weather Analysis for Rishiri Island Hoshiba Spots

過去1週間の実測天気データを分析し、干場間の気象偏差とその原因を解明する。
"""

import pandas as pd
import numpy as np
import requests
import json
from datetime import datetime, timedelta
from geopy.distance import geodesic
import matplotlib.pyplot as plt
import seaborn as sns
from collections import defaultdict
import math

class HistoricalWeatherAnalyzer:
    def __init__(self):
        self.spots_df = None
        self.records_df = None
        self.weather_data = {}
        self.analysis_results = {}
        
    def load_data(self):
        """干場データと記録データを読み込み"""
        try:
            self.spots_df = pd.read_csv('hoshiba_spots.csv', encoding='utf-8')
            self.records_df = pd.read_csv('hoshiba_records.csv', encoding='utf-8')
            print(f"Loaded {len(self.spots_df)} spots and {len(self.records_df)} records")
            return True
        except Exception as e:
            print(f"Error loading data: {e}")
            return False
    
    def get_active_spots_last_week(self):
        """過去1週間でアクティブだった干場を特定"""
        end_date = datetime.now()
        start_date = end_date - timedelta(days=7)
        
        # 記録データから過去1週間の活動干場を抽出
        self.records_df['date'] = pd.to_datetime(self.records_df['date'])
        recent_records = self.records_df[
            (self.records_df['date'] >= start_date) & 
            (self.records_df['date'] <= end_date)
        ]
        
        active_spots = recent_records['name'].unique()
        print(f"Active spots in last week: {len(active_spots)}")
        
        # 地理的分散も考慮して代表的な干場を選択
        if len(active_spots) > 0:
            active_spots_info = self.spots_df[self.spots_df['name'].isin(active_spots)].copy()
        else:
            # 活動記録がない場合は地理的分散で選択
            active_spots_info = self.select_geographically_diverse_spots()
            
        return active_spots_info
    
    def select_geographically_diverse_spots(self):
        """地理的に分散した代表干場を選択"""
        # 地理的極値を見つける
        north = self.spots_df.loc[self.spots_df['lat'].idxmax()]
        south = self.spots_df.loc[self.spots_df['lat'].idxmin()] 
        east = self.spots_df.loc[self.spots_df['lon'].idxmax()]
        west = self.spots_df.loc[self.spots_df['lon'].idxmin()]
        
        # 中央付近（利尻山周辺）
        center_lat = 45.1821
        center_lon = 141.2421
        self.spots_df['dist_from_center'] = np.sqrt(
            (self.spots_df['lat'] - center_lat)**2 + 
            (self.spots_df['lon'] - center_lon)**2
        )
        center = self.spots_df.loc[self.spots_df['dist_from_center'].idxmin()]
        
        diverse_spots = pd.DataFrame([north, south, east, west, center])
        print("Selected geographically diverse spots as no recent activity found")
        return diverse_spots
    
    def fetch_historical_weather(self, lat, lon, spot_name, days_back=7):
        """過去の天気データを取得"""
        try:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days_back)
            
            # Open-MeteoのHistorical Weather API
            url = "https://archive-api.open-meteo.com/v1/archive"
            params = {
                'latitude': lat,
                'longitude': lon,
                'start_date': start_date.strftime('%Y-%m-%d'),
                'end_date': end_date.strftime('%Y-%m-%d'),
                'hourly': [
                    'temperature_2m',
                    'relative_humidity_2m', 
                    'wind_speed_10m',
                    'wind_direction_10m',
                    'precipitation',
                    'cloud_cover',
                    'shortwave_radiation'
                ],
                'daily': [
                    'temperature_2m_max',
                    'temperature_2m_min',
                    'precipitation_sum',
                    'wind_speed_10m_max',
                    'wind_direction_10m_dominant',
                    'shortwave_radiation_sum'
                ]
            }
            
            response = requests.get(url, params=params, timeout=30)
            if response.status_code == 200:
                data = response.json()
                self.weather_data[spot_name] = data
                print(f"Weather data fetched for {spot_name}")
                return True
            else:
                print(f"Failed to fetch weather for {spot_name}: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"Error fetching weather for {spot_name}: {e}")
            return False
    
    def analyze_weather_deviations(self):
        """干場間の気象偏差を分析"""
        if not self.weather_data:
            print("No weather data available for analysis")
            return
        
        print("\n=== Weather Deviation Analysis ===")
        
        # 日別データの比較分析
        daily_analysis = {}
        for spot_name, data in self.weather_data.items():
            if 'daily' in data:
                daily = data['daily']
                daily_analysis[spot_name] = {
                    'temp_max': daily['temperature_2m_max'],
                    'temp_min': daily['temperature_2m_min'],
                    'precipitation': daily['precipitation_sum'],
                    'wind_speed': daily['wind_speed_10m_max'],
                    'wind_direction': daily['wind_direction_10m_dominant'],
                    'radiation': daily['shortwave_radiation_sum']
                }
        
        # 統計分析
        parameters = ['temp_max', 'temp_min', 'precipitation', 'wind_speed', 'radiation']
        deviations = {}
        
        for param in parameters:
            values_by_spot = {}
            for spot_name, data in daily_analysis.items():
                # NoneTypeを除外してから平均を計算
                values = [v for v in data[param] if v is not None]
                if values:
                    values_by_spot[spot_name] = np.mean(values)
                else:
                    values_by_spot[spot_name] = 0.0
                
            if values_by_spot:
                mean_val = np.mean(list(values_by_spot.values()))
                std_val = np.std(list(values_by_spot.values()))
                max_val = max(values_by_spot.values())
                min_val = min(values_by_spot.values())
                
                deviations[param] = {
                    'mean': mean_val,
                    'std': std_val,
                    'range': max_val - min_val,
                    'by_spot': values_by_spot
                }
        
        self.analysis_results['deviations'] = deviations
        self.print_deviation_results(deviations)
        
    def print_deviation_results(self, deviations):
        """偏差分析結果を表示"""
        print(f"\n{'Parameter':<15} | {'Mean':<8} | {'Std Dev':<8} | {'Range':<8} | {'CoV%':<6}")
        print("-" * 60)
        
        for param, stats in deviations.items():
            cov = (stats['std'] / stats['mean'] * 100) if stats['mean'] != 0 else 0
            print(f"{param:<15} | {stats['mean']:<8.2f} | {stats['std']:<8.2f} | {stats['range']:<8.2f} | {cov:<6.1f}")
        
        print("\nSpot-by-spot comparison:")
        for param, stats in deviations.items():
            print(f"\n{param.upper()}:")
            sorted_spots = sorted(stats['by_spot'].items(), key=lambda x: x[1], reverse=True)
            for spot, value in sorted_spots:
                deviation = value - stats['mean']
                print(f"  {spot}: {value:.2f} (deviation: {deviation:+.2f})")
    
    def analyze_geographic_factors(self):
        """地理的要因と気象偏差の関係を分析"""
        if not self.analysis_results.get('deviations'):
            print("No deviation data available for geographic analysis")
            return
            
        print("\n=== Geographic Factor Analysis ===")
        
        # 各干場の地理的特性を計算
        geographic_factors = {}
        
        for spot_name in self.weather_data.keys():
            spot_info = self.spots_df[self.spots_df['name'] == spot_name].iloc[0]
            lat, lon = spot_info['lat'], spot_info['lon']
            
            # 利尻山からの距離
            rishiri_peak = (45.1821, 141.2421)
            distance_to_peak = geodesic((lat, lon), rishiri_peak).kilometers
            
            # 海岸からの距離（簡易計算）
            coastline_distance = self.estimate_coastline_distance(lat, lon)
            
            # 標高（簡易推定）
            elevation = self.estimate_elevation(lat, lon, distance_to_peak)
            
            # 卓越風向に対する地形遮蔽効果
            terrain_exposure = self.calculate_terrain_exposure(lat, lon)
            
            geographic_factors[spot_name] = {
                'distance_to_peak': distance_to_peak,
                'coastline_distance': coastline_distance,
                'estimated_elevation': elevation,
                'terrain_exposure': terrain_exposure,
                'lat': lat,
                'lon': lon
            }
        
        self.analysis_results['geographic_factors'] = geographic_factors
        self.correlate_geography_weather(geographic_factors)
    
    def estimate_coastline_distance(self, lat, lon):
        """海岸線からの距離を推定"""
        # 利尻島の海岸線の近似的な境界
        center_lat, center_lon = 45.1821, 141.2421
        distance_from_center = geodesic((lat, lon), (center_lat, center_lon)).kilometers
        
        # 利尻島の半径を約8-10kmと仮定
        island_radius = 9.0
        coastline_distance = max(0, island_radius - distance_from_center)
        return coastline_distance
    
    def estimate_elevation(self, lat, lon, distance_to_peak):
        """標高を推定（利尻山からの距離ベース）"""
        # 利尻山（1721m）からの距離に基づく簡易標高推定
        if distance_to_peak < 1.0:
            return 1500 - (distance_to_peak * 300)  # 山頂付近
        elif distance_to_peak < 3.0:
            return 1200 - (distance_to_peak * 200)  # 中腹
        elif distance_to_peak < 6.0:
            return 600 - (distance_to_peak * 80)   # 麓
        else:
            return max(10, 200 - (distance_to_peak * 20))  # 海岸平地
    
    def calculate_terrain_exposure(self, lat, lon):
        """地形露出度を計算（風の通りやすさ）"""
        # 利尻山を中心とした8方位での遮蔽度を計算
        center_lat, center_lon = 45.1821, 141.2421
        
        # 方位角計算
        dlat = lat - center_lat
        dlon = lon - center_lon
        azimuth = math.degrees(math.atan2(dlon, dlat))
        if azimuth < 0:
            azimuth += 360
            
        # 卓越風向（ヤマセ：東風90°、ニシ：西風270°）に対する露出度
        yamase_exposure = 1 - abs(azimuth - 90) / 180  # 東向き斜面ほど高い
        nishi_exposure = 1 - abs(azimuth - 270) / 180  # 西向き斜面ほど高い
        
        return {
            'yamase_exposure': max(0, yamase_exposure),
            'nishi_exposure': max(0, nishi_exposure),
            'azimuth': azimuth
        }
    
    def correlate_geography_weather(self, geographic_factors):
        """地理的要因と気象偏差の相関分析"""
        print("\n=== Geography-Weather Correlations ===")
        
        if not self.analysis_results.get('deviations'):
            return
            
        # 相関分析用データ準備
        spots = list(geographic_factors.keys())
        correlations = {}
        
        geo_params = ['distance_to_peak', 'coastline_distance', 'estimated_elevation']
        weather_params = ['temp_max', 'temp_min', 'precipitation', 'wind_speed', 'radiation']
        
        for weather_param in weather_params:
            weather_values = [self.analysis_results['deviations'][weather_param]['by_spot'][spot] 
                            for spot in spots]
            
            correlations[weather_param] = {}
            for geo_param in geo_params:
                geo_values = [geographic_factors[spot][geo_param] for spot in spots]
                
                if len(set(geo_values)) > 1:  # 値にばらつきがある場合のみ
                    corr = np.corrcoef(geo_values, weather_values)[0, 1]
                    correlations[weather_param][geo_param] = corr
                    
        self.print_correlation_results(correlations)
        
    def print_correlation_results(self, correlations):
        """相関分析結果を表示"""
        print(f"{'Weather Param':<15} | {'vs Distance to Peak':<18} | {'vs Coast Distance':<17} | {'vs Elevation':<13}")
        print("-" * 80)
        
        for weather_param, corr_dict in correlations.items():
            peak_corr = corr_dict.get('distance_to_peak', 0)
            coast_corr = corr_dict.get('coastline_distance', 0)
            elev_corr = corr_dict.get('estimated_elevation', 0)
            
            print(f"{weather_param:<15} | {peak_corr:<18.3f} | {coast_corr:<17.3f} | {elev_corr:<13.3f}")
    
    def generate_analysis_report(self):
        """分析結果レポートを生成"""
        report_lines = []
        report_lines.append("=== 利尻島干場間気象偏差分析レポート ===")
        report_lines.append(f"分析日時: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report_lines.append(f"分析期間: 過去7日間")
        report_lines.append(f"分析対象: {len(self.weather_data)}箇所の干場")
        report_lines.append("")
        
        if self.analysis_results.get('deviations'):
            report_lines.append("## 気象パラメータ偏差分析")
            deviations = self.analysis_results['deviations']
            
            for param, stats in deviations.items():
                report_lines.append(f"### {param}")
                report_lines.append(f"平均値: {stats['mean']:.2f}")
                report_lines.append(f"標準偏差: {stats['std']:.2f}")
                report_lines.append(f"レンジ: {stats['range']:.2f}")
                cov = (stats['std'] / stats['mean'] * 100) if stats['mean'] != 0 else 0
                report_lines.append(f"変動係数: {cov:.1f}%")
                
                if cov > 10:
                    report_lines.append("→ 高い地点間差異あり")
                elif cov > 5:
                    report_lines.append("→ 中程度の地点間差異")
                else:
                    report_lines.append("→ 地点間差異は小さい")
                report_lines.append("")
        
        # レポートをファイルに保存
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        report_file = f'weather_deviation_analysis_report_{timestamp}.txt'
        
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write('\n'.join(report_lines))
        
        print(f"\nAnalysis report saved: {report_file}")
        return report_file

def main():
    """メイン実行関数"""
    print("=== Historical Weather Deviation Analysis ===")
    print("Analyzing weather deviations across Rishiri Island hoshiba spots\n")
    
    analyzer = HistoricalWeatherAnalyzer()
    
    # データ読み込み
    if not analyzer.load_data():
        return
    
    # アクティブな干場を特定
    active_spots = analyzer.get_active_spots_last_week()
    if active_spots.empty:
        print("No active spots found")
        return
    
    print(f"\nAnalyzing {len(active_spots)} spots:")
    for _, spot in active_spots.iterrows():
        print(f"  {spot['name']} ({spot['lat']:.4f}, {spot['lon']:.4f})")
    
    # 各地点の過去天気データを取得
    print(f"\nFetching historical weather data...")
    success_count = 0
    for _, spot in active_spots.iterrows():
        if analyzer.fetch_historical_weather(spot['lat'], spot['lon'], spot['name']):
            success_count += 1
    
    print(f"Successfully fetched weather data for {success_count} spots")
    
    if success_count == 0:
        print("No weather data available for analysis")
        return
    
    # 気象偏差分析
    analyzer.analyze_weather_deviations()
    
    # 地理的要因分析
    analyzer.analyze_geographic_factors()
    
    # レポート生成
    analyzer.generate_analysis_report()
    
    print(f"\nAnalysis completed. Processed {success_count} spots.")

if __name__ == "__main__":
    main()