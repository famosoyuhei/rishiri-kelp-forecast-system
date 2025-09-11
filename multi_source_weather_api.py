#!/usr/bin/env python3
"""
複数データソース統合気象API
Multi-Source Weather API Integration System

利尻島局地気象予測のため、複数の気象データソースを統合し、
高密度・高精度な観測データを提供する。
"""

import requests
import json
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from dataclasses import dataclass
from typing import Dict, List, Optional, Union
import asyncio
import aiohttp
from concurrent.futures import ThreadPoolExecutor
import logging

# ログ設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class WeatherDataPoint:
    """気象データポイント"""
    timestamp: datetime
    latitude: float
    longitude: float
    temperature: Optional[float] = None
    humidity: Optional[float] = None
    pressure: Optional[float] = None
    wind_speed: Optional[float] = None
    wind_direction: Optional[float] = None
    precipitation: Optional[float] = None
    cloud_cover: Optional[float] = None
    solar_radiation: Optional[float] = None
    source: str = "unknown"
    quality: float = 1.0  # データ品質スコア (0-1)

class MultiSourceWeatherAPI:
    """複数データソース統合気象APIクラス"""
    
    def __init__(self):
        self.data_sources = {
            'openmeteo': OpenMeteoAPI(),
            'jma_amedas': JMAAmedasAPI(),
            'satellite': SatelliteDataAPI(),
            'msm_model': MSMModelAPI(),
            'radiosonde': RadiosondeAPI()
        }
        self.quality_weights = {
            'openmeteo': 0.8,
            'jma_amedas': 0.95,
            'satellite': 0.85,
            'msm_model': 0.9,
            'radiosonde': 0.98
        }
        self.cache = {}
        self.update_interval = 600  # 10分間隔（秒）
        
    async def get_integrated_weather_data(self, lat: float, lon: float, 
                                        start_time: datetime, 
                                        end_time: datetime) -> List[WeatherDataPoint]:
        """統合気象データ取得"""
        cache_key = f"{lat}_{lon}_{start_time}_{end_time}"
        
        # キャッシュチェック
        if cache_key in self.cache:
            cache_time, data = self.cache[cache_key]
            if (datetime.now() - cache_time).seconds < self.update_interval:
                logger.info(f"Using cached data for {cache_key}")
                return data
        
        # 複数ソースから並行データ取得
        tasks = []
        for source_name, api in self.data_sources.items():
            if api.is_available():
                task = asyncio.create_task(
                    self._fetch_from_source(api, source_name, lat, lon, start_time, end_time)
                )
                tasks.append(task)
        
        # 全ソースからデータ取得完了を待機
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # データ統合・品質管理
        integrated_data = self._integrate_multi_source_data(results)
        
        # キャッシュ更新
        self.cache[cache_key] = (datetime.now(), integrated_data)
        
        logger.info(f"Integrated data from {len([r for r in results if not isinstance(r, Exception)])} sources")
        return integrated_data
    
    async def _fetch_from_source(self, api, source_name: str, lat: float, lon: float,
                               start_time: datetime, end_time: datetime) -> List[WeatherDataPoint]:
        """個別ソースからデータ取得"""
        try:
            data = await api.fetch_data(lat, lon, start_time, end_time)
            for point in data:
                point.source = source_name
                point.quality = self.quality_weights.get(source_name, 0.7)
            return data
        except Exception as e:
            logger.error(f"Error fetching from {source_name}: {e}")
            return []
    
    def _integrate_multi_source_data(self, source_results: List) -> List[WeatherDataPoint]:
        """複数ソースデータの統合"""
        # 有効な結果のみ抽出
        valid_results = [r for r in source_results if isinstance(r, list)]
        
        if not valid_results:
            logger.warning("No valid data from any source")
            return []
        
        # 時刻別にデータをグループ化
        time_groups = {}
        for result in valid_results:
            for point in result:
                time_key = point.timestamp.replace(minute=0, second=0, microsecond=0)
                if time_key not in time_groups:
                    time_groups[time_key] = []
                time_groups[time_key].append(point)
        
        # 各時刻でデータ融合
        integrated_points = []
        for timestamp, points in time_groups.items():
            integrated_point = self._fuse_data_points(points, timestamp)
            if integrated_point:
                integrated_points.append(integrated_point)
        
        return sorted(integrated_points, key=lambda x: x.timestamp)
    
    def _fuse_data_points(self, points: List[WeatherDataPoint], timestamp: datetime) -> Optional[WeatherDataPoint]:
        """複数データポイントの融合"""
        if not points:
            return None
        
        # 代表位置（平均）
        lat = np.mean([p.latitude for p in points])
        lon = np.mean([p.longitude for p in points])
        
        # 品質重み付き平均
        def weighted_average(values, weights):
            valid_pairs = [(v, w) for v, w in zip(values, weights) if v is not None]
            if not valid_pairs:
                return None
            values, weights = zip(*valid_pairs)
            return np.average(values, weights=weights)
        
        weights = [p.quality for p in points]
        
        fused_point = WeatherDataPoint(
            timestamp=timestamp,
            latitude=lat,
            longitude=lon,
            temperature=weighted_average([p.temperature for p in points], weights),
            humidity=weighted_average([p.humidity for p in points], weights),
            pressure=weighted_average([p.pressure for p in points], weights),
            wind_speed=weighted_average([p.wind_speed for p in points], weights),
            wind_direction=self._circular_average([p.wind_direction for p in points if p.wind_direction is not None]),
            precipitation=weighted_average([p.precipitation for p in points], weights),
            cloud_cover=weighted_average([p.cloud_cover for p in points], weights),
            solar_radiation=weighted_average([p.solar_radiation for p in points], weights),
            source="integrated",
            quality=np.mean(weights)
        )
        
        return fused_point
    
    def _circular_average(self, angles: List[float]) -> Optional[float]:
        """風向等の円形平均計算"""
        if not angles:
            return None
        
        # 角度をラジアンに変換
        rads = np.array(angles) * np.pi / 180
        
        # 単位ベクトルの平均
        mean_x = np.mean(np.cos(rads))
        mean_y = np.mean(np.sin(rads))
        
        # 平均角度を度に変換
        mean_angle = np.arctan2(mean_y, mean_x) * 180 / np.pi
        
        # 0-360度範囲に正規化
        if mean_angle < 0:
            mean_angle += 360
            
        return mean_angle

class OpenMeteoAPI:
    """Open-Meteo API クラス"""
    
    def __init__(self):
        self.base_url = "https://api.open-meteo.com/v1/forecast"
        self.archive_url = "https://archive-api.open-meteo.com/v1/archive"
    
    def is_available(self) -> bool:
        return True
    
    async def fetch_data(self, lat: float, lon: float, 
                        start_time: datetime, end_time: datetime) -> List[WeatherDataPoint]:
        """Open-Meteoからデータ取得"""
        params = {
            'latitude': lat,
            'longitude': lon,
            'start_date': start_time.strftime('%Y-%m-%d'),
            'end_date': end_time.strftime('%Y-%m-%d'),
            'hourly': [
                'temperature_2m', 'relative_humidity_2m', 'surface_pressure',
                'wind_speed_10m', 'wind_direction_10m', 'precipitation',
                'cloud_cover', 'shortwave_radiation'
            ]
        }
        
        async with aiohttp.ClientSession() as session:
            url = self.base_url if end_time > datetime.now() else self.archive_url
            async with session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    return self._parse_openmeteo_data(data, lat, lon)
                else:
                    logger.error(f"OpenMeteo API error: {response.status}")
                    return []
    
    def _parse_openmeteo_data(self, data: dict, lat: float, lon: float) -> List[WeatherDataPoint]:
        """Open-Meteoデータ解析"""
        if 'hourly' not in data:
            return []
        
        hourly = data['hourly']
        times = [datetime.fromisoformat(t.replace('Z', '+00:00')) for t in hourly['time']]
        
        points = []
        for i, timestamp in enumerate(times):
            point = WeatherDataPoint(
                timestamp=timestamp,
                latitude=lat,
                longitude=lon,
                temperature=self._safe_get(hourly, 'temperature_2m', i),
                humidity=self._safe_get(hourly, 'relative_humidity_2m', i),
                pressure=self._safe_get(hourly, 'surface_pressure', i),
                wind_speed=self._safe_get(hourly, 'wind_speed_10m', i),
                wind_direction=self._safe_get(hourly, 'wind_direction_10m', i),
                precipitation=self._safe_get(hourly, 'precipitation', i),
                cloud_cover=self._safe_get(hourly, 'cloud_cover', i),
                solar_radiation=self._safe_get(hourly, 'shortwave_radiation', i)
            )
            points.append(point)
        
        return points
    
    def _safe_get(self, data: dict, key: str, index: int) -> Optional[float]:
        """安全なデータ取得"""
        if key in data and index < len(data[key]):
            value = data[key][index]
            return value if value is not None else None
        return None

class JMAAmedasAPI:
    """気象庁アメダスAPI クラス（仮想実装）"""
    
    def is_available(self) -> bool:
        # 実際のJMA APIキーや認証が必要
        return False  # 現在は無効
    
    async def fetch_data(self, lat: float, lon: float, 
                        start_time: datetime, end_time: datetime) -> List[WeatherDataPoint]:
        """JMAアメダスデータ取得（実装予定）"""
        # TODO: 実際のJMA API実装
        return []

class SatelliteDataAPI:
    """気象衛星データAPI クラス（仮想実装）"""
    
    def is_available(self) -> bool:
        return False  # 現在は無効
    
    async def fetch_data(self, lat: float, lon: float, 
                        start_time: datetime, end_time: datetime) -> List[WeatherDataPoint]:
        """衛星データ取得（実装予定）"""
        # TODO: 気象衛星API実装
        return []

class MSMModelAPI:
    """MSM数値予報モデルAPI クラス（仮想実装）"""
    
    def is_available(self) -> bool:
        return False  # 現在は無効
    
    async def fetch_data(self, lat: float, lon: float, 
                        start_time: datetime, end_time: datetime) -> List[WeatherDataPoint]:
        """MSMモデルデータ取得（実装予定）"""
        # TODO: MSM API実装
        return []

class RadiosondeAPI:
    """ラジオゾンデ高層観測API クラス（仮想実装）"""
    
    def is_available(self) -> bool:
        return False  # 現在は無効
    
    async def fetch_data(self, lat: float, lon: float, 
                        start_time: datetime, end_time: datetime) -> List[WeatherDataPoint]:
        """ラジオゾンデデータ取得（実装予定）"""
        # TODO: ラジオゾンデAPI実装
        return []

class WeatherDataQualityController:
    """気象データ品質管理クラス"""
    
    def __init__(self):
        # データ品質チェック閾値
        self.quality_thresholds = {
            'temperature': {'min': -50, 'max': 60, 'std_limit': 10},
            'humidity': {'min': 0, 'max': 100, 'std_limit': 30},
            'pressure': {'min': 800, 'max': 1100, 'std_limit': 50},
            'wind_speed': {'min': 0, 'max': 100, 'std_limit': 20},
            'precipitation': {'min': 0, 'max': 200, 'std_limit': 50}
        }
    
    def validate_data_point(self, point: WeatherDataPoint) -> bool:
        """データポイント品質検証"""
        checks = []
        
        # 範囲チェック
        if point.temperature is not None:
            checks.append(self._range_check('temperature', point.temperature))
        
        if point.humidity is not None:
            checks.append(self._range_check('humidity', point.humidity))
        
        if point.pressure is not None:
            checks.append(self._range_check('pressure', point.pressure))
        
        if point.wind_speed is not None:
            checks.append(self._range_check('wind_speed', point.wind_speed))
        
        if point.precipitation is not None:
            checks.append(self._range_check('precipitation', point.precipitation))
        
        # 全チェック合格の場合のみTrue
        return all(checks) if checks else False
    
    def _range_check(self, parameter: str, value: float) -> bool:
        """範囲チェック"""
        if parameter not in self.quality_thresholds:
            return True
        
        thresholds = self.quality_thresholds[parameter]
        return thresholds['min'] <= value <= thresholds['max']
    
    def filter_quality_data(self, data_points: List[WeatherDataPoint], 
                          min_quality: float = 0.5) -> List[WeatherDataPoint]:
        """品質フィルタリング"""
        filtered = []
        for point in data_points:
            if (point.quality >= min_quality and 
                self.validate_data_point(point)):
                filtered.append(point)
        
        logger.info(f"Quality filtering: {len(filtered)}/{len(data_points)} points passed")
        return filtered

async def main():
    """メイン実行関数（テスト用）"""
    api = MultiSourceWeatherAPI()
    quality_controller = WeatherDataQualityController()
    
    # 利尻島代表地点
    lat, lon = 45.1821, 141.2421
    start_time = datetime.now() - timedelta(days=1)
    end_time = datetime.now()
    
    print("=== Multi-Source Weather API Test ===")
    print(f"Location: {lat}, {lon}")
    print(f"Period: {start_time} to {end_time}")
    
    # データ取得
    raw_data = await api.get_integrated_weather_data(lat, lon, start_time, end_time)
    print(f"Raw data points: {len(raw_data)}")
    
    # 品質管理
    filtered_data = quality_controller.filter_quality_data(raw_data)
    print(f"Quality-filtered data points: {len(filtered_data)}")
    
    # 結果表示
    if filtered_data:
        latest_point = filtered_data[-1]
        print(f"\nLatest weather data:")
        print(f"  Time: {latest_point.timestamp}")
        print(f"  Temperature: {latest_point.temperature}°C")
        print(f"  Humidity: {latest_point.humidity}%")
        print(f"  Wind: {latest_point.wind_speed}m/s @ {latest_point.wind_direction}°")
        print(f"  Source: {latest_point.source}")
        print(f"  Quality: {latest_point.quality:.2f}")

if __name__ == "__main__":
    asyncio.run(main())