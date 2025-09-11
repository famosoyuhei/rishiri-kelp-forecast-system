#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
強化予報システム
Enhanced Forecast System with Optimized Thresholds, Multi-Source Data, and High-Resolution Terrain

最も効果的な組み合わせを実装:
1. 予測閾値の最適化
2. 多源気象データ統合
3. 地形高精度化
4. データ取得速度管理
"""

import asyncio
import aiohttp
import time
import pandas as pd
import numpy as np
import json
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional, Union
from concurrent.futures import ThreadPoolExecutor, as_completed
import warnings
from dataclasses import dataclass

@dataclass
class PerformanceMetrics:
    """性能指標管理クラス"""
    api_response_time: float = 0.0
    data_processing_time: float = 0.0
    total_prediction_time: float = 0.0
    data_sources_used: int = 0
    cache_hit_rate: float = 0.0

class EnhancedForecastSystem:
    """強化予報システム"""
    
    def __init__(self):
        # 最適化された予測閾値（検証結果に基づく調整）
        self.optimized_thresholds = {
            "poor_to_marginal": 3.5,      # 3.0 → 3.5
            "marginal_to_good": 6.0,      # 5.0 → 6.0  
            "good_to_excellent": 8.0      # 7.0 → 8.0
        }
        
        # 日数別特化閾値
        self.daily_thresholds = {
            1: {"good": 5.8, "excellent": 7.8},  # 1日前は少し緩め
            2: {"good": 6.2, "excellent": 8.2},  # 2日前は標準より厳しめ
            3: {"good": 6.0, "excellent": 8.0},  # 標準
            4: {"good": 5.8, "excellent": 7.8},
            5: {"good": 5.6, "excellent": 7.6}, 
            6: {"good": 5.4, "excellent": 7.4},  # 長期は緩め
            7: {"good": 5.2, "excellent": 7.2}
        }
        
        # 多源気象データAPI設定
        self.weather_apis = {
            "openweather": {
                "url": "http://api.openweathermap.org/data/2.5/forecast",
                "key": "your_openweather_key",  # 実際のキーに置換
                "timeout": 5.0,
                "weight": 0.4  # 信頼度重み
            },
            "jma_msm": {
                "url": "https://www.jma.go.jp/bosai/forecast/data/forecast/",
                "key": None,
                "timeout": 10.0, 
                "weight": 0.6  # JMAは高信頼度
            }
        }
        
        # 高精度地形データ
        self.terrain_database = self._initialize_enhanced_terrain()
        
        # 性能監視
        self.performance_cache = {}
        self.data_cache = {}
        self.cache_ttl = 1800  # 30分キャッシュ
        
        # 並列処理設定
        self.max_workers = 4
        self.request_delay = 0.2  # API間隔制御
        
    def _initialize_enhanced_terrain(self) -> Dict:
        """高精度地形データ初期化"""
        try:
            from terrain_database import RishiriTerrainDatabase
            terrain_db = RishiriTerrainDatabase()
            
            # 拡張地形データ
            enhanced_terrain = {
                "base_db": terrain_db,
                "elevation_mesh": self._create_elevation_mesh(),
                "coastal_distance": self._calculate_coastal_distances(),
                "wind_exposure": self._calculate_wind_exposure(),
                "local_climate_zones": self._define_climate_zones()
            }
            return enhanced_terrain
        except ImportError:
            warnings.warn("Terrain database not available, using simplified model")
            return {"simplified": True}
    
    def _create_elevation_mesh(self) -> Dict:
        """標高メッシュ作成（10mメッシュ）"""
        # 実装では詳細なDEMデータを使用
        # ここでは代表的な標高データを設定
        return {
            "mesh_resolution": 10,  # 10mメッシュ  
            "elevation_data": {
                # 利尻島の標高分布（簡略版）
                (45.18, 141.24): 1721,  # 利尻山頂
                (45.16, 141.14): 15,    # 鬼脇港付近
                (45.25, 141.22): 25,    # 沓形港付近
                (45.20, 141.13): 45,    # 西海岸
                (45.15, 141.25): 35     # 東海岸
            }
        }
    
    def _calculate_coastal_distances(self) -> Dict:
        """海岸からの距離計算"""
        # 各干場の海岸距離を事前計算
        return {
            "distance_model": "euclidean",
            "coastal_points": [
                (45.16, 141.14), (45.18, 141.12), (45.20, 141.13),
                (45.22, 141.15), (45.24, 141.18), (45.25, 141.22),
                (45.24, 141.26), (45.22, 141.28), (45.19, 141.29),
                (45.16, 141.27), (45.14, 141.24), (45.13, 141.20)
            ]
        }
    
    def _calculate_wind_exposure(self) -> Dict:
        """風向別暴露度計算"""
        # 16方位別の風暴露度
        return {
            "exposure_matrix": {
                "N": 0.8, "NNE": 0.9, "NE": 1.0, "ENE": 1.1,
                "E": 1.2, "ESE": 1.1, "SE": 1.0, "SSE": 0.9,
                "S": 0.8, "SSW": 0.7, "SW": 0.6, "WSW": 0.7,
                "W": 0.8, "WNW": 0.9, "NW": 0.8, "NNW": 0.7
            }
        }
    
    def _define_climate_zones(self) -> Dict:
        """局地気候区分定義"""
        return {
            "zones": {
                "mountain_side": {"temp_offset": -2.0, "humidity_offset": +5},
                "coastal_west": {"temp_offset": +0.5, "humidity_offset": +10},
                "coastal_east": {"temp_offset": +0.3, "humidity_offset": +8}, 
                "inland_valley": {"temp_offset": +1.0, "humidity_offset": -3}
            }
        }
    
    async def fetch_weather_data_async(self, lat: float, lon: float, 
                                     target_date: datetime) -> Dict:
        """非同期気象データ取得"""
        start_time = time.time()
        
        async with aiohttp.ClientSession() as session:
            tasks = []
            
            # OpenWeatherMap取得
            if self.weather_apis["openweather"]["key"]:
                tasks.append(self._fetch_openweather(session, lat, lon))
            
            # JMA取得（簡易実装）
            tasks.append(self._fetch_jma_data(session, lat, lon))
            
            # 並列実行
            results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # データ統合
        integrated_data = self._integrate_weather_data(results, target_date)
        
        # 性能記録
        processing_time = time.time() - start_time
        integrated_data["performance"] = {
            "fetch_time": processing_time,
            "sources_used": len([r for r in results if not isinstance(r, Exception)]),
            "cache_used": False
        }
        
        return integrated_data
    
    async def _fetch_openweather(self, session: aiohttp.ClientSession, 
                                lat: float, lon: float) -> Dict:
        """OpenWeatherMap API取得"""
        try:
            url = self.weather_apis["openweather"]["url"]
            params = {
                "lat": lat,
                "lon": lon, 
                "appid": self.weather_apis["openweather"]["key"],
                "units": "metric"
            }
            
            timeout = aiohttp.ClientTimeout(total=self.weather_apis["openweather"]["timeout"])
            async with session.get(url, params=params, timeout=timeout) as response:
                if response.status == 200:
                    data = await response.json()
                    return {"source": "openweather", "data": data, "weight": 0.4}
                else:
                    return {"source": "openweather", "error": f"HTTP {response.status}"}
        except Exception as e:
            return {"source": "openweather", "error": str(e)}
    
    async def _fetch_jma_data(self, session: aiohttp.ClientSession,
                            lat: float, lon: float) -> Dict:
        """JMAデータ取得（簡易実装）"""
        try:
            # 実際の実装では気象庁APIを使用
            # ここでは模擬データ
            await asyncio.sleep(0.1)  # API遅延シミュレーション
            
            mock_data = {
                "temperature": np.random.normal(20, 5),
                "humidity": np.random.normal(70, 15),
                "wind_speed": np.random.normal(8, 3), 
                "pressure": np.random.normal(1013, 10),
                "cloud_cover": np.random.uniform(0, 100)
            }
            
            return {"source": "jma", "data": mock_data, "weight": 0.6}
        except Exception as e:
            return {"source": "jma", "error": str(e)}
    
    def _integrate_weather_data(self, api_results: List, target_date: datetime) -> Dict:
        """気象データ統合"""
        integrated = {
            "temperature": 0, "humidity": 0, "wind_speed": 0,
            "pressure": 1013, "cloud_cover": 50,
            "confidence": 0, "sources": []
        }
        
        total_weight = 0
        successful_sources = 0
        
        for result in api_results:
            if isinstance(result, dict) and "error" not in result:
                data = result["data"]
                weight = result["weight"]
                
                if "temperature" in data:
                    integrated["temperature"] += data["temperature"] * weight
                if "humidity" in data:
                    integrated["humidity"] += data["humidity"] * weight
                if "wind_speed" in data:
                    integrated["wind_speed"] += data["wind_speed"] * weight
                if "pressure" in data:
                    integrated["pressure"] += data["pressure"] * weight
                if "cloud_cover" in data:
                    integrated["cloud_cover"] += data["cloud_cover"] * weight
                
                total_weight += weight
                successful_sources += 1
                integrated["sources"].append(result["source"])
        
        # 重み付き平均で正規化
        if total_weight > 0:
            for key in ["temperature", "humidity", "wind_speed", "pressure", "cloud_cover"]:
                integrated[key] /= total_weight
            integrated["confidence"] = min(total_weight, 1.0)
        else:
            # フォールバック: デフォルト値
            integrated["confidence"] = 0.1
            print("Warning: All weather data sources failed, using fallback values")
        
        return integrated
    
    def apply_enhanced_terrain_corrections(self, lat: float, lon: float, 
                                         weather_data: Dict) -> Dict:
        """強化地形補正適用"""
        corrections = {
            "temperature_correction": 0,
            "humidity_correction": 0, 
            "wind_speed_correction": 0,
            "terrain_zone": "unknown"
        }
        
        if "simplified" in self.terrain_database:
            return corrections
            
        try:
            # 標高補正
            elevation = self._get_elevation(lat, lon)
            corrections["temperature_correction"] = -0.6 * (elevation / 100)  # 100mあたり-0.6°C
            corrections["humidity_correction"] = -1.0 * (elevation / 100)     # 100mあたり-1%
            
            # 海岸距離補正
            coastal_distance = self._get_coastal_distance(lat, lon)
            if coastal_distance < 0.5:  # 500m以内
                corrections["humidity_correction"] += 8  # 海洋性気候
                corrections["wind_speed_correction"] += 1.2
            
            # 風向別暴露補正
            wind_direction = weather_data.get("wind_direction", 180)
            exposure_factor = self._get_wind_exposure(lat, lon, wind_direction)
            corrections["wind_speed_correction"] *= exposure_factor
            
            # 気候区分
            corrections["terrain_zone"] = self._get_climate_zone(lat, lon)
            
        except Exception as e:
            print(f"Terrain correction error: {e}")
        
        return corrections
    
    def _get_elevation(self, lat: float, lon: float) -> float:
        """標高取得"""
        mesh_data = self.terrain_database["elevation_mesh"]["elevation_data"]
        
        # 最近傍点検索（実装では補間を使用）
        min_distance = float('inf')
        nearest_elevation = 0
        
        for (mesh_lat, mesh_lon), elevation in mesh_data.items():
            distance = ((lat - mesh_lat) ** 2 + (lon - mesh_lon) ** 2) ** 0.5
            if distance < min_distance:
                min_distance = distance
                nearest_elevation = elevation
        
        return nearest_elevation
    
    def _get_coastal_distance(self, lat: float, lon: float) -> float:
        """海岸距離計算"""
        coastal_points = self.terrain_database["coastal_distance"]["coastal_points"]
        
        min_distance = float('inf')
        for coast_lat, coast_lon in coastal_points:
            # 簡易距離計算（実装では正確な測地計算）
            distance = ((lat - coast_lat) ** 2 + (lon - coast_lon) ** 2) ** 0.5 * 111  # km換算
            if distance < min_distance:
                min_distance = distance
        
        return min_distance
    
    def _get_wind_exposure(self, lat: float, lon: float, wind_direction: float) -> float:
        """風向別暴露度計算"""
        # 風向を16方位に変換
        directions = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
                     "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]
        dir_index = int((wind_direction + 11.25) // 22.5) % 16
        direction_name = directions[dir_index]
        
        exposure_matrix = self.terrain_database["wind_exposure"]["exposure_matrix"]
        return exposure_matrix.get(direction_name, 1.0)
    
    def _get_climate_zone(self, lat: float, lon: float) -> str:
        """気候区分取得"""
        # 簡易区分（実際の実装ではより詳細）
        elevation = self._get_elevation(lat, lon)
        coastal_distance = self._get_coastal_distance(lat, lon)
        
        if elevation > 100:
            return "mountain_side"
        elif coastal_distance < 0.5 and lon < 141.20:
            return "coastal_west"
        elif coastal_distance < 0.5:
            return "coastal_east" 
        else:
            return "inland_valley"
    
    def calculate_enhanced_forecast_score(self, lat: float, lon: float, 
                                        target_date: datetime, days_ahead: int,
                                        weather_data: Dict) -> Dict:
        """強化予報スコア計算"""
        start_time = time.time()
        
        # 基本スコア計算
        base_score = self._calculate_base_score(weather_data, target_date)
        
        # 地形補正適用
        terrain_corrections = self.apply_enhanced_terrain_corrections(lat, lon, weather_data)
        
        # 補正後データ
        corrected_temp = weather_data["temperature"] + terrain_corrections["temperature_correction"]
        corrected_humidity = weather_data["humidity"] + terrain_corrections["humidity_correction"]
        corrected_wind = weather_data["wind_speed"] * (1 + terrain_corrections["wind_speed_correction"] / 100)
        
        # 統合スコア計算
        # 気温要素（理想: 15-25°C）
        temp_score = 1.0 - abs(corrected_temp - 20) / 20
        temp_score = max(0, min(1, temp_score))
        
        # 湿度要素（理想: <70%）
        humidity_score = max(0, (100 - corrected_humidity) / 100)
        
        # 風速要素（理想: 3-10m/s）
        if 3 <= corrected_wind <= 10:
            wind_score = 1.0
        elif corrected_wind < 3:
            wind_score = corrected_wind / 3
        else:
            wind_score = max(0, 1 - (corrected_wind - 10) / 10)
        
        # 雲量要素
        cloud_score = max(0, (100 - weather_data["cloud_cover"]) / 100)
        
        # 重み付き統合
        integrated_score = (
            temp_score * 0.25 + 
            humidity_score * 0.35 + 
            wind_score * 0.25 + 
            cloud_score * 0.15
        ) * 10  # 0-10スケール
        
        # 信頼度による調整
        confidence_factor = weather_data.get("confidence", 0.5)
        final_score = integrated_score * (0.5 + 0.5 * confidence_factor)
        
        # 最適化された閾値で条件判定
        condition, success_prediction = self._determine_condition_optimized(
            final_score, days_ahead
        )
        
        processing_time = time.time() - start_time
        
        return {
            "forecast_score": final_score,
            "condition": condition,
            "success_prediction": success_prediction,
            "component_scores": {
                "temperature": temp_score * 10,
                "humidity": humidity_score * 10,
                "wind_speed": wind_score * 10,
                "cloud_cover": cloud_score * 10
            },
            "terrain_corrections": terrain_corrections,
            "corrected_values": {
                "temperature": corrected_temp,
                "humidity": corrected_humidity,
                "wind_speed": corrected_wind
            },
            "confidence": confidence_factor,
            "processing_time": processing_time,
            "data_sources": weather_data.get("sources", [])
        }
    
    def _calculate_base_score(self, weather_data: Dict, target_date: datetime) -> float:
        """基本スコア計算"""
        # 季節性考慮
        month = target_date.month
        seasonal_factor = 1.0
        if month in [7, 8]:
            seasonal_factor = 1.3  # 夏季最適
        elif month in [6, 9]:
            seasonal_factor = 1.1
        elif month in [5, 10]:
            seasonal_factor = 0.9
        
        return 5.0 * seasonal_factor  # ベーススコア
    
    def _determine_condition_optimized(self, score: float, days_ahead: int) -> Tuple[str, bool]:
        """最適化された条件判定"""
        # 日数別閾値取得
        daily_threshold = self.daily_thresholds.get(days_ahead, self.daily_thresholds[3])
        
        if score >= daily_threshold["excellent"]:
            return "Excellent", True
        elif score >= daily_threshold["good"]:
            return "Good", True
        elif score >= self.optimized_thresholds["poor_to_marginal"]:
            return "Marginal", False
        else:
            return "Poor", False
    
    async def generate_enhanced_forecast(self, lat: float, lon: float, 
                                       target_date: datetime, days_ahead: int) -> Dict:
        """強化予報生成（メイン関数）"""
        performance = PerformanceMetrics()
        start_time = time.time()
        
        try:
            # キャッシュチェック
            cache_key = f"{lat:.4f}_{lon:.4f}_{target_date.date()}_{days_ahead}"
            if cache_key in self.data_cache:
                cached_data = self.data_cache[cache_key]
                if time.time() - cached_data["timestamp"] < self.cache_ttl:
                    performance.cache_hit_rate = 1.0
                    cached_data["forecast"]["performance_metrics"] = performance
                    return cached_data["forecast"]
            
            # 気象データ取得
            api_start = time.time()
            weather_data = await self.fetch_weather_data_async(lat, lon, target_date)
            performance.api_response_time = time.time() - api_start
            performance.data_sources_used = len(weather_data.get("sources", []))
            
            # 予報スコア計算  
            processing_start = time.time()
            forecast_result = self.calculate_enhanced_forecast_score(
                lat, lon, target_date, days_ahead, weather_data
            )
            performance.data_processing_time = time.time() - processing_start
            
            # 結果統合
            enhanced_forecast = {
                "forecast_date": target_date.isoformat(),
                "forecast_base_date": (target_date - timedelta(days=days_ahead)).isoformat(),
                "days_ahead": days_ahead,
                "coordinates": {"lat": lat, "lon": lon},
                "weather_data": weather_data,
                **forecast_result,
                "system_version": "Enhanced_v1.0",
                "performance_metrics": performance
            }
            
            # キャッシュ保存
            self.data_cache[cache_key] = {
                "forecast": enhanced_forecast,
                "timestamp": time.time()
            }
            
            performance.total_prediction_time = time.time() - start_time
            enhanced_forecast["performance_metrics"] = performance
            
            return enhanced_forecast
            
        except Exception as e:
            print(f"Enhanced forecast error: {e}")
            performance.total_prediction_time = time.time() - start_time
            return {
                "error": str(e),
                "performance_metrics": performance,
                "system_version": "Enhanced_v1.0"
            }

# 使用例とテスト関数
async def test_enhanced_system():
    """強化システムテスト"""
    print("=== Enhanced Forecast System Test ===")
    
    system = EnhancedForecastSystem()
    
    # テスト座標（利尻島）
    test_coordinates = [
        (45.1631, 141.1435),  # 鬼脇
        (45.2480, 141.2198),  # 沓形
        (45.2065, 141.1376)   # 仙法志
    ]
    
    test_date = datetime.now() + timedelta(days=2)
    
    print(f"Test Date: {test_date.date()}")
    print(f"Testing {len(test_coordinates)} locations...")
    
    for i, (lat, lon) in enumerate(test_coordinates, 1):
        print(f"\n--- Location {i}: ({lat:.4f}, {lon:.4f}) ---")
        
        for days in [1, 2, 3]:
            forecast = await system.generate_enhanced_forecast(
                lat, lon, test_date, days
            )
            
            if "error" not in forecast:
                metrics = forecast["performance_metrics"]
                print(f"  {days}-day forecast: {forecast['condition']} "
                      f"(Score: {forecast['forecast_score']:.2f}, "
                      f"Success: {forecast['success_prediction']}, "
                      f"Time: {metrics.total_prediction_time:.3f}s, "
                      f"Sources: {metrics.data_sources_used})")
            else:
                print(f"  {days}-day forecast: ERROR - {forecast['error']}")

def main():
    """メイン実行"""
    asyncio.run(test_enhanced_system())

if __name__ == "__main__":
    main()