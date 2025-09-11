#!/usr/bin/env python3
"""
等値線解析エンジン
Isoline Analysis Engine

利尻島局地気象予測のため、等温線・等湿線・等圧線・等相当温位線を生成し、
地形との関係を可視化・解析する。
"""

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.tri as tri
from matplotlib.colors import ListedColormap, BoundaryNorm
from matplotlib.patches import Polygon
import seaborn as sns
from scipy.interpolate import griddata, RectBivariateSpline
from scipy.ndimage import gaussian_filter
import pandas as pd
from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional, Union
import json
from pathlib import Path
import logging
from datetime import datetime

from multi_source_weather_api import WeatherDataPoint, MultiSourceWeatherAPI
from terrain_database import RishiriTerrainDatabase, TerrainPoint

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class IsolineData:
    """等値線データ"""
    parameter: str  # 気象要素名
    level: float    # 等値線レベル
    coordinates: List[Tuple[float, float]]  # 座標リスト[(lat, lon), ...]
    timestamp: datetime
    confidence: float = 1.0  # 信頼度

@dataclass
class WeatherField:
    """気象場データ"""
    parameter: str
    timestamp: datetime
    lats: np.ndarray
    lons: np.ndarray
    values: np.ndarray
    unit: str
    quality_mask: np.ndarray  # データ品質マスク

class IsolineAnalysisEngine:
    """等値線解析エンジンクラス"""
    
    def __init__(self, terrain_db: RishiriTerrainDatabase):
        self.terrain_db = terrain_db
        self.weather_api = None  # 後で初期化
        
        # 利尻島境界
        self.island_bounds = {
            'lat_min': 45.05, 'lat_max': 45.28,
            'lon_min': 141.13, 'lon_max': 141.33
        }
        
        # 等値線設定
        self.isoline_configs = {
            'temperature': {
                'levels': np.arange(-20, 40, 2),  # 2度間隔
                'colors': 'RdYlBu_r',
                'unit': '°C',
                'line_styles': ['-', '--'][0]
            },
            'humidity': {
                'levels': np.arange(20, 101, 10),  # 10%間隔
                'colors': 'Blues',
                'unit': '%',
                'line_styles': '-'
            },
            'pressure': {
                'levels': np.arange(980, 1040, 2),  # 2hPa間隔
                'colors': 'viridis',
                'unit': 'hPa',
                'line_styles': '-'
            },
            'wind_speed': {
                'levels': np.arange(0, 30, 2),  # 2m/s間隔
                'colors': 'plasma',
                'unit': 'm/s',
                'line_styles': '-'
            },
            'precipitation': {
                'levels': [0.1, 0.5, 1, 2, 5, 10, 20, 50],  # 降水量レベル
                'colors': 'YlGnBu',
                'unit': 'mm/h',
                'line_styles': '-'
            },
            'equivalent_potential_temperature': {
                'levels': np.arange(280, 370, 5),  # 5K間隔
                'colors': 'coolwarm',
                'unit': 'K',
                'line_styles': '-'
            }
        }
        
        # 解析グリッド設定
        self.analysis_grid = self._create_analysis_grid()
        
    def _create_analysis_grid(self) -> Tuple[np.ndarray, np.ndarray]:
        """解析用グリッド作成"""
        grid_resolution = 0.002  # 約200m間隔
        
        lats = np.arange(self.island_bounds['lat_min'], 
                        self.island_bounds['lat_max'], 
                        grid_resolution)
        lons = np.arange(self.island_bounds['lon_min'], 
                        self.island_bounds['lon_max'], 
                        grid_resolution)
        
        lat_grid, lon_grid = np.meshgrid(lats, lons)
        return lat_grid, lon_grid
    
    async def analyze_weather_field(self, weather_data: List[WeatherDataPoint], 
                                  parameter: str, timestamp: datetime) -> WeatherField:
        """気象場解析"""
        if not weather_data:
            logger.error("No weather data provided for analysis")
            return None
        
        # データ抽出
        lats = np.array([point.latitude for point in weather_data])
        lons = np.array([point.longitude for point in weather_data])
        
        # パラメータ値抽出
        if parameter == 'temperature':
            values = np.array([point.temperature for point in weather_data if point.temperature is not None])
            valid_indices = [i for i, point in enumerate(weather_data) if point.temperature is not None]
        elif parameter == 'humidity':
            values = np.array([point.humidity for point in weather_data if point.humidity is not None])
            valid_indices = [i for i, point in enumerate(weather_data) if point.humidity is not None]
        elif parameter == 'pressure':
            values = np.array([point.pressure for point in weather_data if point.pressure is not None])
            valid_indices = [i for i, point in enumerate(weather_data) if point.pressure is not None]
        elif parameter == 'wind_speed':
            values = np.array([point.wind_speed for point in weather_data if point.wind_speed is not None])
            valid_indices = [i for i, point in enumerate(weather_data) if point.wind_speed is not None]
        elif parameter == 'precipitation':
            values = np.array([point.precipitation for point in weather_data if point.precipitation is not None])
            valid_indices = [i for i, point in enumerate(weather_data) if point.precipitation is not None]
        else:
            logger.error(f"Unsupported parameter: {parameter}")
            return None
        
        # 有効データのフィルタリング
        if len(valid_indices) == 0:
            logger.error(f"No valid data for parameter: {parameter}")
            return None
        
        lats_valid = lats[valid_indices]
        lons_valid = lons[valid_indices]
        
        # グリッドデータへの補間
        lat_grid, lon_grid = self.analysis_grid
        
        # 地形効果を考慮した補間
        interpolated_values = self._interpolate_with_terrain(
            lats_valid, lons_valid, values, lat_grid, lon_grid, parameter
        )
        
        # 品質マスク作成
        quality_mask = self._create_quality_mask(lat_grid, lon_grid, lats_valid, lons_valid)
        
        weather_field = WeatherField(
            parameter=parameter,
            timestamp=timestamp,
            lats=lat_grid,
            lons=lon_grid,
            values=interpolated_values,
            unit=self.isoline_configs[parameter]['unit'],
            quality_mask=quality_mask
        )
        
        logger.info(f"Weather field analyzed for {parameter} at {timestamp}")
        return weather_field
    
    def _interpolate_with_terrain(self, lats_obs: np.ndarray, lons_obs: np.ndarray, 
                                values_obs: np.ndarray, lat_grid: np.ndarray, 
                                lon_grid: np.ndarray, parameter: str) -> np.ndarray:
        """地形効果を考慮した補間"""
        
        # 基本補間
        points_obs = np.column_stack((lats_obs, lons_obs))
        grid_points = np.column_stack((lat_grid.ravel(), lon_grid.ravel()))
        
        # RBF補間（Radial Basis Function）
        interpolated = griddata(points_obs, values_obs, grid_points, method='cubic')
        
        # NaN値を線形補間で補完
        nan_mask = np.isnan(interpolated)
        if np.any(nan_mask):
            interpolated_linear = griddata(points_obs, values_obs, grid_points, method='linear')
            interpolated[nan_mask] = interpolated_linear[nan_mask]
        
        # まだNaN値があれば最近傍で補完
        nan_mask = np.isnan(interpolated)
        if np.any(nan_mask):
            interpolated_nearest = griddata(points_obs, values_obs, grid_points, method='nearest')
            interpolated[nan_mask] = interpolated_nearest[nan_mask]
        
        interpolated_2d = interpolated.reshape(lat_grid.shape)
        
        # 地形効果補正
        if parameter in ['temperature', 'pressure']:
            interpolated_2d = self._apply_terrain_correction(
                interpolated_2d, lat_grid, lon_grid, parameter
            )
        
        # スムージング
        interpolated_2d = gaussian_filter(interpolated_2d, sigma=1.0)
        
        return interpolated_2d
    
    def _apply_terrain_correction(self, field: np.ndarray, lat_grid: np.ndarray, 
                                lon_grid: np.ndarray, parameter: str) -> np.ndarray:
        """地形効果補正"""
        corrected_field = field.copy()
        
        for i in range(lat_grid.shape[0]):
            for j in range(lat_grid.shape[1]):
                lat, lon = lat_grid[i, j], lon_grid[i, j]
                
                # 地形情報取得
                terrain_info = self.terrain_db.get_terrain_at_point(lat, lon)
                if terrain_info is None:
                    continue
                
                # 標高による補正
                if parameter == 'temperature':
                    # 気温逓減率: 100mあたり約0.6度
                    elevation_correction = -terrain_info.elevation * 0.006
                    corrected_field[i, j] += elevation_correction
                
                elif parameter == 'pressure':
                    # 気圧の高度補正: 100mあたり約12hPa
                    elevation_correction = -terrain_info.elevation * 0.12
                    corrected_field[i, j] += elevation_correction
        
        return corrected_field
    
    def _create_quality_mask(self, lat_grid: np.ndarray, lon_grid: np.ndarray,
                           lats_obs: np.ndarray, lons_obs: np.ndarray) -> np.ndarray:
        """データ品質マスク作成"""
        quality_mask = np.ones_like(lat_grid)
        
        # 観測点からの距離に基づく品質スコア
        for i in range(lat_grid.shape[0]):
            for j in range(lat_grid.shape[1]):
                lat, lon = lat_grid[i, j], lon_grid[i, j]
                
                # 最近傍観測点との距離
                distances = np.sqrt((lats_obs - lat)**2 + (lons_obs - lon)**2)
                min_distance = np.min(distances)
                
                # 距離に基づく品質スコア（最大5km）
                if min_distance > 0.05:  # 5km以上離れている場合
                    quality_mask[i, j] = max(0.1, 1.0 - (min_distance - 0.05) * 2)
        
        return quality_mask
    
    def generate_isolines(self, weather_field: WeatherField) -> List[IsolineData]:
        """等値線生成"""
        if weather_field is None:
            return []
        
        parameter = weather_field.parameter
        if parameter not in self.isoline_configs:
            logger.error(f"No isoline configuration for parameter: {parameter}")
            return []
        
        config = self.isoline_configs[parameter]
        levels = config['levels']
        
        # 品質マスクを適用
        masked_values = weather_field.values.copy()
        low_quality_mask = weather_field.quality_mask < 0.5
        masked_values[low_quality_mask] = np.nan
        
        # 等値線計算
        isolines = []
        
        try:
            # matplotlib contourを使用
            fig, ax = plt.subplots(figsize=(1, 1))  # 最小サイズ
            contours = ax.contour(weather_field.lons, weather_field.lats, 
                                masked_values, levels=levels)
            
            # 等値線データ抽出
            for level, collection in zip(levels, contours.collections):
                for path in collection.get_paths():
                    # 座標抽出（lon, lat → lat, lon変換）
                    vertices = path.vertices
                    coordinates = [(vertex[1], vertex[0]) for vertex in vertices]
                    
                    # 利尻島範囲内のみ
                    filtered_coords = []
                    for lat, lon in coordinates:
                        if (self.island_bounds['lat_min'] <= lat <= self.island_bounds['lat_max'] and
                            self.island_bounds['lon_min'] <= lon <= self.island_bounds['lon_max']):
                            filtered_coords.append((lat, lon))
                    
                    if len(filtered_coords) > 2:  # 最低3点以上
                        isoline = IsolineData(
                            parameter=parameter,
                            level=level,
                            coordinates=filtered_coords,
                            timestamp=weather_field.timestamp,
                            confidence=self._calculate_isoline_confidence(filtered_coords, weather_field)
                        )
                        isolines.append(isoline)
            
            plt.close(fig)
            
        except Exception as e:
            logger.error(f"Error generating isolines: {e}")
        
        logger.info(f"Generated {len(isolines)} isolines for {parameter}")
        return isolines
    
    def _calculate_isoline_confidence(self, coordinates: List[Tuple[float, float]], 
                                    weather_field: WeatherField) -> float:
        """等値線信頼度計算"""
        if not coordinates:
            return 0.0
        
        confidences = []
        for lat, lon in coordinates:
            # グリッド上の位置を特定
            lat_idx = np.argmin(np.abs(weather_field.lats[:, 0] - lat))
            lon_idx = np.argmin(np.abs(weather_field.lons[0, :] - lon))
            
            quality = weather_field.quality_mask[lat_idx, lon_idx]
            confidences.append(quality)
        
        return np.mean(confidences) if confidences else 0.0
    
    def create_weather_map(self, weather_field: WeatherField, isolines: List[IsolineData],
                          output_file: str = None, show_terrain: bool = True) -> str:
        """気象マップ作成"""
        fig, ax = plt.subplots(figsize=(12, 10))
        
        parameter = weather_field.parameter
        config = self.isoline_configs[parameter]
        
        # 地形背景（オプション）
        if show_terrain:
            terrain_data = self.terrain_db.get_terrain_grid()
            if terrain_data:
                terrain_lats, terrain_lons, elevations = terrain_data
                ax.scatter(terrain_lons, terrain_lats, c=elevations, 
                          cmap='terrain', s=0.5, alpha=0.3, zorder=0)
        
        # 気象場の塗りつぶし
        im = ax.contourf(weather_field.lons, weather_field.lats, weather_field.values,
                        levels=config['levels'], cmap=config['colors'], 
                        alpha=0.7, extend='both')
        
        # カラーバー
        cbar = plt.colorbar(im, ax=ax, shrink=0.7)
        cbar.set_label(f"{parameter.replace('_', ' ').title()} ({config['unit']})")
        
        # 等値線
        line_colors = 'black' if parameter != 'temperature' else 'white'
        contour_lines = ax.contour(weather_field.lons, weather_field.lats, weather_field.values,
                                  levels=config['levels'], colors=line_colors, 
                                  linewidths=0.8, alpha=0.8)
        ax.clabel(contour_lines, inline=True, fontsize=8, fmt='%.0f')
        
        # 風向矢印（風速場の場合）
        if parameter == 'wind_speed' and hasattr(weather_field, 'wind_direction'):
            self._add_wind_arrows(ax, weather_field)
        
        # 利尻山位置
        rishiri_center = (45.1821, 141.2421)
        ax.plot(rishiri_center[1], rishiri_center[0], 'r^', 
               markersize=12, label='Rishiri-san', zorder=10)
        
        # 地図設定
        ax.set_xlim(self.island_bounds['lon_min'], self.island_bounds['lon_max'])
        ax.set_ylim(self.island_bounds['lat_min'], self.island_bounds['lat_max'])
        ax.set_xlabel('Longitude')
        ax.set_ylabel('Latitude')
        ax.set_title(f'{parameter.replace("_", " ").title()} - {weather_field.timestamp.strftime("%Y-%m-%d %H:%M")}')
        ax.grid(True, alpha=0.3)
        ax.legend()
        ax.set_aspect('equal')
        
        # 保存
        if output_file is None:
            timestamp_str = weather_field.timestamp.strftime("%Y%m%d_%H%M")
            output_file = f"weather_map_{parameter}_{timestamp_str}.png"
        
        plt.savefig(output_file, dpi=300, bbox_inches='tight')
        plt.show()
        
        logger.info(f"Weather map saved: {output_file}")
        return output_file
    
    def _add_wind_arrows(self, ax, weather_field: WeatherField):
        """風向矢印追加"""
        # 簡素化のため省略（風向データが利用可能な場合に実装）
        pass
    
    def analyze_terrain_weather_relationship(self, weather_field: WeatherField, 
                                           parameter: str) -> Dict:
        """地形と気象の関係分析"""
        analysis_results = {
            'parameter': parameter,
            'timestamp': weather_field.timestamp,
            'correlations': {},
            'statistics': {}
        }
        
        # サンプリング点での地形・気象データ取得
        sample_lats = weather_field.lats[::5, ::5].ravel()  # 5格子おきにサンプリング
        sample_lons = weather_field.lons[::5, ::5].ravel()
        sample_values = weather_field.values[::5, ::5].ravel()
        
        elevations = []
        slopes = []
        aspects = []
        
        for lat, lon in zip(sample_lats, sample_lons):
            terrain_info = self.terrain_db.get_terrain_at_point(lat, lon)
            if terrain_info:
                elevations.append(terrain_info.elevation)
                slopes.append(terrain_info.slope)
                aspects.append(terrain_info.aspect)
            else:
                elevations.append(np.nan)
                slopes.append(np.nan)
                aspects.append(np.nan)
        
        # 相関分析
        elevations = np.array(elevations)
        slopes = np.array(slopes)
        sample_values = np.array(sample_values)
        
        # NaN値を除去
        valid_mask = ~(np.isnan(elevations) | np.isnan(sample_values))
        if np.sum(valid_mask) > 10:  # 最低10点以上
            elev_corr = np.corrcoef(elevations[valid_mask], sample_values[valid_mask])[0, 1]
            analysis_results['correlations']['elevation'] = elev_corr
        
        valid_mask = ~(np.isnan(slopes) | np.isnan(sample_values))
        if np.sum(valid_mask) > 10:
            slope_corr = np.corrcoef(slopes[valid_mask], sample_values[valid_mask])[0, 1]
            analysis_results['correlations']['slope'] = slope_corr
        
        # 統計情報
        analysis_results['statistics'] = {
            'mean': np.nanmean(sample_values),
            'std': np.nanstd(sample_values),
            'min': np.nanmin(sample_values),
            'max': np.nanmax(sample_values),
            'range': np.nanmax(sample_values) - np.nanmin(sample_values)
        }
        
        logger.info(f"Terrain-weather relationship analyzed for {parameter}")
        return analysis_results

def main():
    """メイン実行関数（テスト用）"""
    print("=== Isoline Analysis Engine Test ===")
    
    # データベース初期化
    terrain_db = RishiriTerrainDatabase()
    
    # 地形データが存在しない場合は生成
    if terrain_db.get_terrain_grid() is None:
        print("Generating terrain data...")
        terrain_db.generate_synthetic_terrain_data()
    
    # 等値線解析エンジン初期化
    engine = IsolineAnalysisEngine(terrain_db)
    
    # テスト用の気象データ生成
    from datetime import datetime
    test_weather_data = []
    
    # 利尻島周辺の仮想観測点
    for i, (lat, lon) in enumerate([
        (45.10, 141.20), (45.15, 141.25), (45.20, 141.15),
        (45.18, 141.30), (45.12, 141.18), (45.25, 141.22)
    ]):
        # 標高に基づく気温推定
        terrain_info = terrain_db.get_terrain_at_point(lat, lon)
        base_temp = 20.0
        if terrain_info:
            temp = base_temp - terrain_info.elevation * 0.006  # 気温逓減
            humidity = 70 + np.random.normal(0, 10)
            pressure = 1013 - terrain_info.elevation * 0.12
        else:
            temp = base_temp + np.random.normal(0, 2)
            humidity = 70 + np.random.normal(0, 10)
            pressure = 1013 + np.random.normal(0, 5)
        
        point = WeatherDataPoint(
            timestamp=datetime.now(),
            latitude=lat,
            longitude=lon,
            temperature=temp,
            humidity=max(0, min(100, humidity)),
            pressure=pressure,
            wind_speed=5 + np.random.normal(0, 2),
            wind_direction=np.random.uniform(0, 360)
        )
        test_weather_data.append(point)
    
    print(f"Created {len(test_weather_data)} test weather points")
    
    # 気象場解析（非同期関数のテスト実行）
    import asyncio
    
    async def test_analysis():
        # 気温場解析
        temp_field = await engine.analyze_weather_field(
            test_weather_data, 'temperature', datetime.now()
        )
        
        if temp_field:
            print(f"Temperature field analyzed: {temp_field.values.shape}")
            
            # 等値線生成
            isolines = engine.generate_isolines(temp_field)
            print(f"Generated {len(isolines)} temperature isolines")
            
            # 気象マップ作成
            map_file = engine.create_weather_map(temp_field, isolines, 
                                               "test_temperature_map.png")
            
            # 地形-気象関係分析
            relationship = engine.analyze_terrain_weather_relationship(temp_field, 'temperature')
            print(f"Terrain correlation: {relationship['correlations']}")
            
            print("Isoline analysis test completed!")
    
    # テスト実行
    asyncio.run(test_analysis())

if __name__ == "__main__":
    main()