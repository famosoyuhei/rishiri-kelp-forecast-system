"""
Configuration file for forecast accuracy analysis system
"""

# 12干場のリスト（泉町エリア、アメダス沓形から500m以内）
IZUMI_SPOTS = [
    {'name': 'H_1782_1394', 'lat': 45.1782154, 'lon': 141.1394976},  # 距離21m - 最優先
    {'name': 'H_1795_1393', 'lat': 45.1795069, 'lon': 141.1393681},  # 距離123m
    {'name': 'H_1795_1395', 'lat': 45.1795069, 'lon': 141.1395271},  # 距離125m
    {'name': 'H_1790_1377', 'lat': 45.1790064, 'lon': 141.1377058},  # 距離156m
    {'name': 'H_1798_1396', 'lat': 45.1798074, 'lon': 141.1396066},  # 距離160m
    {'name': 'H_1799_1392', 'lat': 45.1799074, 'lon': 141.1392086},  # 距離170m
    {'name': 'H_1788_1372', 'lat': 45.1788059, 'lon': 141.1372063},  # 距離183m
    {'name': 'H_1804_1404', 'lat': 45.1804084, 'lon': 141.1404091},  # 距離236m
    {'name': 'H_1762_1377', 'lat': 45.1762024, 'lon': 141.1377058},  # 距離277m
    {'name': 'H_1811_1399', 'lat': 45.1811099, 'lon': 141.1399086},  # 距離302m
    {'name': 'H_1817_1402', 'lat': 45.1817109, 'lon': 141.1402091},  # 距離375m
    {'name': 'H_1818_1416', 'lat': 45.1818109, 'lon': 141.1416111},  # 距離420m
]

# アメダス沓形の情報
AMEDAS_KUTSUGATA = {
    'id': '11151',  # 気象庁アメダス沓形ID (JMAマスターファイルから確認済み)
    'name': '沓形',
    'lat': 45.17840444072544,
    'lon': 141.139540511718,
    'elevation': 29,  # 標高（メートル）
}

# 気象庁API設定
JMA_AMEDAS_API_BASE = 'https://www.jma.go.jp/bosai/amedas/data/point'

# 内部予報APIエンドポイント
FORECAST_API_BASE = 'http://localhost:8000/api/forecast'

# 乾燥判定閾値（STAGE_WEIGHT_ANALYSIS.mdから）
DRYING_THRESHOLDS = {
    'precipitation': 0.0,      # 降水量（mm）- 絶対条件
    'min_humidity': 94.0,      # 最低湿度（%）- 絶対条件
    'avg_wind_speed': 2.0,     # 平均風速（m/s）- 絶対条件
}

# データベース設定
import os
DB_PATH = os.path.join(os.path.dirname(__file__), 'forecast_accuracy.db')

# ログ設定
LOG_LEVEL = 'INFO'
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
