#!/usr/bin/env python3
"""
利尻島地形データベースシステム
Rishiri Island Terrain Database System

局地気象予測のため、利尻島の詳細地形・地表面データを管理し、
等高線・土地利用・海岸線情報を提供する。
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
import json
import sqlite3
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from scipy.interpolate import griddata, RectBivariateSpline
from scipy.spatial import cKDTree
import requests
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class TerrainPoint:
    """地形データポイント"""
    latitude: float
    longitude: float
    elevation: float
    land_use: str  # 土地利用区分
    distance_to_coast: float  # 海岸からの距離(km)
    slope: float  # 傾斜角度(度)
    aspect: float  # 斜面方位角(度)
    theta: float  # 干場極座標θ

@dataclass
class ContourLine:
    """等高線データ"""
    elevation: float
    coordinates: List[Tuple[float, float]]  # (lat, lon)のリスト

class RishiriTerrainDatabase:
    """利尻島地形データベースクラス"""
    
    def __init__(self, db_path: str = "rishiri_terrain.db"):
        self.db_path = db_path
        self.rishiri_center = (45.1821, 141.2421)  # 利尻山座標
        self.theta_zero_point = (45.1007, 141.2461)  # θ=0基準点（南岸境界）
        self.island_bounds = {
            'lat_min': 45.05, 'lat_max': 45.28,
            'lon_min': 141.13, 'lon_max': 141.33
        }
        self.grid_resolution = 0.001  # 約100m
        
        # 土地利用分類
        self.land_use_categories = {
            0: "海域",
            1: "森林（針葉樹）",
            2: "森林（広葉樹）", 
            3: "森林（混交林）",
            4: "草地",
            5: "農地",
            6: "市街地",
            7: "裸地・岩石",
            8: "水域（湖沼）",
            9: "雪氷",
            10: "海岸・砂浜"
        }
        
        self._initialize_database()
        
    def _initialize_database(self):
        """データベース初期化"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 地形データテーブル
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS terrain_points (
                id INTEGER PRIMARY KEY,
                latitude REAL NOT NULL,
                longitude REAL NOT NULL,
                elevation REAL NOT NULL,
                land_use INTEGER NOT NULL,
                distance_to_coast REAL,
                slope REAL,
                aspect REAL,
                theta REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # 等高線データテーブル
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS contour_lines (
                id INTEGER PRIMARY KEY,
                elevation REAL NOT NULL,
                coordinates TEXT NOT NULL,  -- JSON形式
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # 海岸線データテーブル
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS coastline (
                id INTEGER PRIMARY KEY,
                latitude REAL NOT NULL,
                longitude REAL NOT NULL,
                segment_id INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        conn.commit()
        conn.close()
        logger.info("Terrain database initialized")
    
    def generate_synthetic_terrain_data(self):
        """合成地形データ生成（実際のDEMデータ取得まで）"""
        logger.info("Generating synthetic terrain data for Rishiri Island")
        
        # 利尻島の基本地形モデル
        lat_range = np.arange(self.island_bounds['lat_min'], 
                             self.island_bounds['lat_max'], 
                             self.grid_resolution)
        lon_range = np.arange(self.island_bounds['lon_min'], 
                             self.island_bounds['lon_max'], 
                             self.grid_resolution)
        
        terrain_points = []
        
        for lat in lat_range:
            for lon in lon_range:
                # 利尻山からの距離
                distance_to_peak = self._calculate_distance(
                    lat, lon, self.rishiri_center[0], self.rishiri_center[1]
                )
                
                # 海岸からの距離
                distance_to_coast = self._estimate_coastline_distance(lat, lon)
                
                # 島内かどうかの判定
                if distance_to_coast < 0:  # 海域
                    continue
                
                # 標高推定（利尻山を中心とした円錐モデル）
                elevation = self._estimate_elevation(distance_to_peak, distance_to_coast)
                
                # 土地利用推定
                land_use = self._estimate_land_use(elevation, distance_to_coast)
                
                # 傾斜・方位角計算
                slope, aspect = self._calculate_slope_aspect(lat, lon, elevation)
                
                # 干場極座標θ計算
                theta = self._calculate_theta(lat, lon)
                
                point = TerrainPoint(
                    latitude=lat,
                    longitude=lon,
                    elevation=elevation,
                    land_use=self.land_use_categories[land_use],
                    distance_to_coast=distance_to_coast,
                    slope=slope,
                    aspect=aspect,
                    theta=theta
                )
                terrain_points.append(point)
        
        # データベースに保存
        self._save_terrain_points(terrain_points)
        logger.info(f"Generated {len(terrain_points)} terrain data points")
        
        # 等高線生成
        self._generate_contour_lines()
        
        return terrain_points
    
    def _calculate_distance(self, lat1: float, lon1: float, 
                          lat2: float, lon2: float) -> float:
        """2点間距離計算（km）"""
        # 簡易距離計算（小範囲なので平面近似）
        dlat = lat1 - lat2
        dlon = lon1 - lon2
        
        # 緯度1度≈111km、経度1度≈111km*cos(lat)
        lat_km = dlat * 111.0
        lon_km = dlon * 111.0 * np.cos(np.radians(lat1))
        
        return np.sqrt(lat_km**2 + lon_km**2)
    
    def _estimate_coastline_distance(self, lat: float, lon: float) -> float:
        """海岸線からの距離推定"""
        # 利尻島を半径約9kmの円と仮定
        distance_from_center = self._calculate_distance(
            lat, lon, self.rishiri_center[0], self.rishiri_center[1]
        )
        
        island_radius = 9.0  # km
        coastline_distance = island_radius - distance_from_center
        
        return max(coastline_distance, -5.0)  # 海域は負の値
    
    def _estimate_elevation(self, distance_to_peak: float, distance_to_coast: float) -> float:
        """標高推定"""
        if distance_to_coast < 0:  # 海域
            return 0.0
        
        # 利尻山（1721m）からの距離に基づく標高推定
        max_elevation = 1721.0
        
        if distance_to_peak < 0.5:  # 山頂付近
            elevation = max_elevation - (distance_to_peak * 400)
        elif distance_to_peak < 2.0:  # 山腹
            elevation = 1500 - (distance_to_peak * 300)
        elif distance_to_peak < 4.0:  # 麓
            elevation = 800 - (distance_to_peak * 100)
        else:  # 海岸平地
            elevation = max(10, 300 - (distance_to_peak * 30))
        
        # 海岸効果を考慮
        if distance_to_coast < 1.0:
            elevation *= (distance_to_coast + 0.1) / 1.1
        
        return max(elevation, 0.0)
    
    def _estimate_land_use(self, elevation: float, distance_to_coast: float) -> int:
        """土地利用推定"""
        if distance_to_coast < 0:
            return 0  # 海域
        elif distance_to_coast < 0.2:
            return 10  # 海岸・砂浜
        elif elevation > 1200:
            return 7  # 裸地・岩石（高山帯）
        elif elevation > 600:
            return 1  # 森林（針葉樹）
        elif elevation > 200:
            return 2  # 森林（広葉樹）
        elif elevation > 50:
            return 4  # 草地
        else:
            return 5  # 農地（低地）
    
    def _calculate_slope_aspect(self, lat: float, lon: float, elevation: float) -> Tuple[float, float]:
        """傾斜・方位角計算"""
        # 利尻山方向を基準とした簡易計算
        dlat = lat - self.rishiri_center[0]
        dlon = lon - self.rishiri_center[1]
        
        # 方位角（度）
        aspect = np.degrees(np.arctan2(dlon, dlat))
        if aspect < 0:
            aspect += 360
        
        # 傾斜角（利尻山からの距離と標高から推定）
        distance_to_peak = self._calculate_distance(lat, lon, 
                                                   self.rishiri_center[0], 
                                                   self.rishiri_center[1])
        if distance_to_peak > 0:
            slope = np.degrees(np.arctan((1721 - elevation) / (distance_to_peak * 1000)))
            slope = max(0, min(slope, 45))  # 0-45度に制限
        else:
            slope = 0
        
        return slope, aspect
    
    def _calculate_theta(self, lat: float, lon: float) -> float:
        """干場極座標θ計算"""
        # 利尻山を中心とした極座標
        dlat = lat - self.rishiri_center[0]
        dlon = lon - self.rishiri_center[1]
        
        # 角度計算（真北から時計回り）
        angle = np.degrees(np.arctan2(dlon, dlat))
        if angle < 0:
            angle += 360
        
        # θ=0基準点（南岸境界）への補正
        # θ=0基準点の角度
        theta_zero_dlat = self.theta_zero_point[0] - self.rishiri_center[0]
        theta_zero_dlon = self.theta_zero_point[1] - self.rishiri_center[1]
        theta_zero_angle = np.degrees(np.arctan2(theta_zero_dlon, theta_zero_dlat))
        if theta_zero_angle < 0:
            theta_zero_angle += 360
        
        # θ値計算
        theta = angle - theta_zero_angle
        if theta < 0:
            theta += 360
        
        return theta
    
    def _save_terrain_points(self, points: List[TerrainPoint]):
        """地形データポイントをデータベースに保存"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 既存データクリア
        cursor.execute("DELETE FROM terrain_points")
        
        # 新データ挿入
        for point in points:
            land_use_id = next(k for k, v in self.land_use_categories.items() 
                             if v == point.land_use)
            cursor.execute("""
                INSERT INTO terrain_points 
                (latitude, longitude, elevation, land_use, distance_to_coast, 
                 slope, aspect, theta)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (point.latitude, point.longitude, point.elevation, land_use_id,
                  point.distance_to_coast, point.slope, point.aspect, point.theta))
        
        conn.commit()
        conn.close()
    
    def _generate_contour_lines(self):
        """等高線生成"""
        # データベースから地形データ取得
        terrain_data = self.get_terrain_grid()
        
        if terrain_data is None:
            logger.error("No terrain data available for contour generation")
            return
        
        lats, lons, elevations = terrain_data
        
        # 等高線レベル設定（10m間隔）
        elevation_levels = np.arange(0, 1800, 10)
        
        # 等高線計算
        contour_lines = []
        
        # グリッドデータ作成
        lat_grid = np.unique(lats)
        lon_grid = np.unique(lons)
        
        if len(lat_grid) < 2 or len(lon_grid) < 2:
            logger.error("Insufficient grid data for contour generation")
            return
        
        # 補間用グリッド作成
        lat_interp = np.linspace(lat_grid.min(), lat_grid.max(), 100)
        lon_interp = np.linspace(lon_grid.min(), lon_grid.max(), 100)
        lat_mesh, lon_mesh = np.meshgrid(lat_interp, lon_interp)
        
        # 標高データを補間
        points = np.column_stack((lats, lons))
        elevation_interp = griddata(points, elevations, (lat_mesh, lon_mesh), method='cubic')
        
        # 等高線計算
        plt.figure(figsize=(10, 8))
        contours = plt.contour(lon_mesh, lat_mesh, elevation_interp, levels=elevation_levels)
        
        # 等高線データ抽出・保存
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM contour_lines")
        
        for level, collection in zip(elevation_levels, contours.collections):
            for path in collection.get_paths():
                coordinates = path.vertices.tolist()  # [(lon, lat), ...]
                # lon, lat を lat, lon に変換
                coordinates = [(coord[1], coord[0]) for coord in coordinates]
                
                cursor.execute("""
                    INSERT INTO contour_lines (elevation, coordinates)
                    VALUES (?, ?)
                """, (float(level), json.dumps(coordinates)))
        
        conn.commit()
        conn.close()
        plt.close()
        
        logger.info(f"Generated contour lines for {len(elevation_levels)} elevation levels")
    
    def get_terrain_at_point(self, lat: float, lon: float) -> Optional[TerrainPoint]:
        """指定地点の地形データ取得"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 最近傍点検索
        cursor.execute("""
            SELECT latitude, longitude, elevation, land_use, distance_to_coast,
                   slope, aspect, theta,
                   (latitude - ?)*(latitude - ?) + (longitude - ?)*(longitude - ?) as distance
            FROM terrain_points
            ORDER BY distance
            LIMIT 1
        """, (lat, lat, lon, lon))
        
        result = cursor.fetchone()
        conn.close()
        
        if result:
            return TerrainPoint(
                latitude=result[0],
                longitude=result[1],
                elevation=result[2],
                land_use=self.land_use_categories[result[3]],
                distance_to_coast=result[4],
                slope=result[5],
                aspect=result[6],
                theta=result[7]
            )
        return None
    
    def get_terrain_grid(self) -> Optional[Tuple[np.ndarray, np.ndarray, np.ndarray]]:
        """地形グリッドデータ取得"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT latitude, longitude, elevation
            FROM terrain_points
            WHERE distance_to_coast >= 0
            ORDER BY latitude, longitude
        """)
        
        results = cursor.fetchall()
        conn.close()
        
        if not results:
            return None
        
        lats = np.array([r[0] for r in results])
        lons = np.array([r[1] for r in results])
        elevations = np.array([r[2] for r in results])
        
        return lats, lons, elevations
    
    def get_contour_lines(self, min_elevation: float = 0, 
                         max_elevation: float = 2000) -> List[ContourLine]:
        """等高線データ取得"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT elevation, coordinates
            FROM contour_lines
            WHERE elevation >= ? AND elevation <= ?
            ORDER BY elevation
        """, (min_elevation, max_elevation))
        
        results = cursor.fetchall()
        conn.close()
        
        contour_lines = []
        for elevation, coordinates_json in results:
            coordinates = json.loads(coordinates_json)
            contour_lines.append(ContourLine(
                elevation=elevation,
                coordinates=coordinates
            ))
        
        return contour_lines
    
    def visualize_terrain(self, output_file: str = "rishiri_terrain_map.png"):
        """地形可視化"""
        terrain_data = self.get_terrain_grid()
        if terrain_data is None:
            logger.error("No terrain data available for visualization")
            return
        
        lats, lons, elevations = terrain_data
        
        # プロット作成
        plt.figure(figsize=(12, 10))
        
        # 地形の散布図
        scatter = plt.scatter(lons, lats, c=elevations, cmap='terrain', s=1, alpha=0.8)
        plt.colorbar(scatter, label='Elevation (m)')
        
        # 等高線追加
        contour_lines = self.get_contour_lines(0, 1800)
        for contour in contour_lines[::5]:  # 50m間隔で表示
            if contour.coordinates:
                lats_line = [coord[0] for coord in contour.coordinates]
                lons_line = [coord[1] for coord in contour.coordinates]
                plt.plot(lons_line, lats_line, 'k-', alpha=0.3, linewidth=0.5)
        
        # 利尻山位置マーク
        plt.plot(self.rishiri_center[1], self.rishiri_center[0], 'r^', 
                markersize=10, label='Rishiri-san (1721m)')
        
        plt.xlabel('Longitude')
        plt.ylabel('Latitude')
        plt.title('Rishiri Island Terrain Map')
        plt.legend()
        plt.grid(True, alpha=0.3)
        plt.axis('equal')
        
        plt.savefig(output_file, dpi=300, bbox_inches='tight')
        plt.show()
        
        logger.info(f"Terrain map saved to {output_file}")

def main():
    """メイン実行関数（テスト用）"""
    print("=== Rishiri Island Terrain Database System ===")
    
    # データベース初期化
    terrain_db = RishiriTerrainDatabase()
    
    # 地形データ生成
    print("Generating terrain data...")
    terrain_points = terrain_db.generate_synthetic_terrain_data()
    
    # テスト地点での地形情報取得
    test_lat, test_lon = 45.15, 141.20
    terrain_info = terrain_db.get_terrain_at_point(test_lat, test_lon)
    
    if terrain_info:
        print(f"\nTerrain information at ({test_lat}, {test_lon}):")
        print(f"  Elevation: {terrain_info.elevation:.1f}m")
        print(f"  Land use: {terrain_info.land_use}")
        print(f"  Distance to coast: {terrain_info.distance_to_coast:.2f}km")
        print(f"  Slope: {terrain_info.slope:.1f}°")
        print(f"  Aspect: {terrain_info.aspect:.1f}°")
        print(f"  Theta: {terrain_info.theta:.1f}°")
    
    # 等高線情報
    contour_lines = terrain_db.get_contour_lines(0, 500)
    print(f"\nContour lines (0-500m): {len(contour_lines)} lines")
    
    # 地形可視化
    print("Creating terrain visualization...")
    terrain_db.visualize_terrain()
    
    print("Terrain database system test completed!")

if __name__ == "__main__":
    main()