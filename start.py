#!/usr/bin/env python3
"""
Rishiri Kelp Forecast System - Production Version with UI
Version: 2.6.0
"""
import os
import sys
import math
import numpy as np
import requests
import pandas as pd
import json
from datetime import datetime, timedelta, timezone
from flask import Flask, jsonify, request, send_file, send_from_directory
from flask_cors import CORS
from scipy.optimize import fsolve

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
JST = timezone(timedelta(hours=9))  # 日本標準時 (UTC+9)

# Create Flask app
app = Flask(__name__)
# M-2: CORS を本番URLとローカル開発に限定
CORS(app, origins=[
    "https://rishiri-kelp-forecast-system.onrender.com",
    "http://localhost:5000",
    "http://127.0.0.1:5000",
])

# M-3: APIレート制限（外部API呼び出しを誘発するエンドポイントを保護）
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
# Use Upstash Redis as limiter backend (shared across Gunicorn workers).
# Falls back to in-memory if env vars are not set (local dev).
_limiter_storage_uri = 'memory://'
_ul_rest   = os.environ.get('UPSTASH_REDIS_REST_URL', '').strip().rstrip('/')
_ul_token  = os.environ.get('UPSTASH_REDIS_REST_TOKEN', '')
if _ul_rest and _ul_token:
    _ul_host = _ul_rest.replace('https://', '').replace('http://', '')
    _limiter_storage_uri = f'rediss://default:{_ul_token}@{_ul_host}:6379'
limiter = Limiter(get_remote_address, app=app, default_limits=[], storage_uri=_limiter_storage_uri)

# Configuration — all paths are BASE_DIR-relative so the app works regardless of cwd
CSV_FILE             = os.path.join(BASE_DIR, "hoshiba_spots.csv")
RECORD_FILE          = os.path.join(BASE_DIR, "hoshiba_records.csv")
KML_FILE             = os.path.join(BASE_DIR, "hoshiba_spots_named.kml")
JS_ARRAY_FILE        = os.path.join(BASE_DIR, "all_spots_array.js")
USER_FAVORITES_FILE  = os.path.join(BASE_DIR, "user_favorites.json")
NOTIFICATION_FILE    = os.path.join(BASE_DIR, "notification_users.json")
FORECAST_HISTORY_DIR = os.path.join(BASE_DIR, "forecast_history")
AMEDAS_DATA_DIR      = os.path.join(BASE_DIR, "amedas_data")
LOCK_DIR             = os.path.join(BASE_DIR, "edit_locks")
os.makedirs(LOCK_DIR, exist_ok=True)

# ── JMA アメダスリアルタイムAPI ─────────────────────────────────────────────
JMA_AMEDAS_LATEST_URL = 'https://www.jma.go.jp/bosai/amedas/data/latest_time.txt'
JMA_AMEDAS_MAP_URL    = 'https://www.jma.go.jp/bosai/amedas/data/map/{timestamp}.json'
RISHIRI_AMEDAS_STATIONS = {
    '11151': {'name': '沓形',        'lat': 45.1783, 'lon': 141.1383},
    '11091': {'name': '本泊(利尻空港)', 'lat': 45.2417, 'lon': 141.1867},
}
# 16方位コード (0=無風, 1=NNE … 16=N)
_JMA_WIND_DIR = {
    0: '無風', 1: 'NNE', 2: 'NE', 3: 'ENE', 4: 'E', 5: 'ESE', 6: 'SE', 7: 'SSE',
    8: 'S', 9: 'SSW', 10: 'SW', 11: 'WSW', 12: 'W', 13: 'WNW', 14: 'NW', 15: 'NNW', 16: 'N'
}
_AMEDAS_RT_CACHE: dict = {'data': None, 'fetched_at': None}
_AMEDAS_RT_CACHE_TTL = 600  # 10分（JMA更新間隔に合わせる）

# ── JMA 高解像度降水ナウキャスト hrpns タイル ────────────────────────────────
HRPNS_TIMES_URL  = 'https://www.jma.go.jp/bosai/jmatile/data/nowc/targetTimes_N1.json'
HRPNS_TILE_URL   = 'https://www.jma.go.jp/bosai/jmatile/data/nowc/{bt}/none/{bt}/surf/hrpns/{z}/{x}/{y}.png'
HRPNS_TILE_Z     = 10   # ~107m/pixel at 45°N — 250mメッシュの実解像度に十分
# カラーパレット: 実タイル(20260531)のPLTE+tRNSから確認済み (idx0,1=透明)
# idx 2=0.1-1mm/h  (#f2f2ff)  idx 3=1-5mm/h   (#a0d2ff)
# idx 4=5-10mm/h   (#218cff)  idx 5=10-20mm/h  (#0041ff)
# idx 6=20-30mm/h  (#faf500)  idx 7=30-50mm/h  (#ff9900)
# idx 8=50-80mm/h  (#ff2800)  idx 9=80+mm/h    (#b40068)
_HRPNS_PRECIP_MID = [0.0, 0.0, 0.5, 3.0, 7.5, 15.0, 25.0, 40.0, 65.0, 80.0]
_NOWCAST_CACHE: dict = {'data': None, 'fetched_at': None}
_NOWCAST_CACHE_TTL = 300   # 5分（ナウキャスト更新間隔）

# ============================================================================
# Theta-e Correction System (相当温位保存による気象補正)
# ============================================================================

class ThetaECorrector:
    """
    相当温位保存を利用した風下地点の気象補正

    原理:
    1. 風上地点のエマグラムから相当温位θₑプロファイルを取得
    2. 風下地点で同じθₑを仮定（保存則）
    3. 地形下降を考慮して気温・湿度を補正
    4. ハイブリッドアプローチ: 下層は補正、上層は平滑化
    """

    def __init__(self):
        self.L = 2.5e6        # 蒸発潜熱（J/kg）
        self.Cp = 1005        # 定圧比熱（J/kg/K）
        self.kappa = 0.286    # R/Cp
        self.epsilon = 0.622  # 水蒸気と乾燥空気の分子量比
        self.rishiri_peak = (45.18, 141.24)  # 利尻山の位置

    def saturation_vapor_pressure(self, T):
        """飽和水蒸気圧（Magnus式）"""
        return 6.112 * np.exp(17.67 * T / (T + 243.5))

    def mixing_ratio(self, T, Td, P):
        """混合比を計算"""
        e = self.saturation_vapor_pressure(Td)
        return self.epsilon * e / (P - e)

    def potential_temperature(self, T, P):
        """温位を計算"""
        T_K = T + 273.15
        return T_K * (1000.0 / P) ** self.kappa

    def equivalent_potential_temperature(self, T, Td, P):
        """相当温位を計算"""
        theta = self.potential_temperature(T, P)
        q = self.mixing_ratio(T, Td, P)
        T_K = T + 273.15
        theta_e = theta * np.exp(self.L * q / (self.Cp * T_K))
        return theta_e

    def temperature_from_theta_e_with_rh(self, theta_e_target, P, RH=0.7, initial_guess=10.0):
        """
        相当温位と気圧から気温・露点温度を逆算

        Args:
            theta_e_target: 目標相当温位（K）
            P: 気圧（hPa）
            RH: 相対湿度（0-1）
            initial_guess: 初期推定気温（℃）
        """
        def objective(T):
            es_T = self.saturation_vapor_pressure(T)
            e = RH * es_T
            if e <= 0:
                return 1e10
            Td = 243.5 * np.log(e / 6.112) / (17.67 - np.log(e / 6.112))
            theta_e_calc = self.equivalent_potential_temperature(T, Td, P)
            return theta_e_calc - theta_e_target

        try:
            T_solution = fsolve(objective, initial_guess, full_output=True)
            if T_solution[2] == 1:  # 収束した場合
                T = T_solution[0][0]
                es_T = self.saturation_vapor_pressure(T)
                e = RH * es_T
                Td = 243.5 * np.log(e / 6.112) / (17.67 - np.log(e / 6.112))
                return T, Td
            else:
                return None, None
        except:
            return None, None

    def calculate_bearing(self, lat1, lon1, lat2, lon2):
        """2点間の方位角を計算（度）"""
        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        dlon_rad = math.radians(lon2 - lon1)

        y = math.sin(dlon_rad) * math.cos(lat2_rad)
        x = math.cos(lat1_rad) * math.sin(lat2_rad) - \
            math.sin(lat1_rad) * math.cos(lat2_rad) * math.cos(dlon_rad)

        bearing = math.degrees(math.atan2(y, x))
        return (bearing + 360) % 360

    def haversine_distance(self, lat1, lon1, lat2, lon2):
        """2点間の距離を計算（km）"""
        R = 6371  # 地球の半径（km）
        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)

        a = math.sin(dlat/2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon/2)**2
        c = 2 * math.asin(math.sqrt(a))
        return R * c

    def select_windward_spot(self, target_lat, target_lon, wind_direction, spots_df):
        """
        風向に基づいて風上地点を選定

        Args:
            target_lat, target_lon: 補正対象地点
            wind_direction: 風向（度、北を0度）
            spots_df: 干場データベース

        Returns:
            最適な風上地点の情報、またはNone
        """
        # 風向の逆方向（風上方向）
        windward_direction = (wind_direction + 180) % 360

        candidates = []

        for _, spot in spots_df.iterrows():
            # 対象地点から見た干場の方位角
            bearing = self.calculate_bearing(target_lat, target_lon,
                                            spot['lat'], spot['lon'])

            # 風上方向との角度差
            angle_diff = abs(windward_direction - bearing)
            if angle_diff > 180:
                angle_diff = 360 - angle_diff

            # 距離
            distance = self.haversine_distance(target_lat, target_lon,
                                              spot['lat'], spot['lon'])

            # 条件: 角度差45度以内、距離3-15km
            if angle_diff < 45 and 3.0 < distance < 15.0:
                candidates.append({
                    'spot': spot,
                    'angle_diff': angle_diff,
                    'distance': distance,
                    'score': angle_diff + distance * 2  # スコア（小さいほど良い）
                })

        if not candidates:
            return None

        # スコアが最小の地点を選択
        best = min(candidates, key=lambda x: x['score'])
        return best['spot']

    def estimate_terrain_descent(self, windward_lat, windward_lon,
                                 leeward_lat, leeward_lon, wind_direction):
        """
        利尻山の標高と風向から下降高度を推定

        Args:
            windward_lat, windward_lon: 風上地点
            leeward_lat, leeward_lon: 風下地点
            wind_direction: 風向

        Returns:
            推定下降高度（m）
        """
        # 簡易版: 利尻山（1721m）を越える経路かチェック

        # 風上・風下地点の中点
        mid_lat = (windward_lat + leeward_lat) / 2
        mid_lon = (windward_lon + leeward_lon) / 2

        # 中点から利尻山までの距離
        dist_to_peak = self.haversine_distance(mid_lat, mid_lon,
                                               self.rishiri_peak[0],
                                               self.rishiri_peak[1])

        # 利尻山に近い経路（<5km）は山越えと判定
        if dist_to_peak < 5.0:
            # 標高差を推定（簡易: 山頂の半分程度を通過と仮定）
            return 500  # m
        else:
            # 山を迂回する経路
            return 100  # m（小さな地形起伏のみ）

    def apply_hybrid_correction(self, pressure, windward_theta_e,
                               windward_rh, api_temp, api_dewpoint,
                               reference_temp, reference_dewpoint):
        """
        ハイブリッドアプローチによる補正

        Args:
            pressure: 気圧（hPa）
            windward_theta_e: 風上の相当温位
            windward_rh: 風上の相対湿度
            api_temp, api_dewpoint: APIの生データ
            reference_temp, reference_dewpoint: 参照地点の値（上層用）

        Returns:
            補正後の気温・露点温度
        """
        if pressure >= 850:
            # 下層（1000-850hPa）: θₑ補正を100%適用
            weight = 1.0

        elif pressure >= 600:
            # 中層（800-600hPa）: θₑ補正を線形減衰
            weight = (pressure - 600) / (850 - 600)

        else:
            # 上層（500hPa以上）: 参照地点の値を使用（補正なし）
            return reference_temp, reference_dewpoint

        # θₑ補正を適用
        if weight > 0:
            # 下降により相対湿度が低下
            rh_reduction = 0.15 * weight  # 最大15%低下
            corrected_rh = max(0.1, windward_rh - rh_reduction)

            # θₑとRHから気温・露点温度を逆算
            T_corr, Td_corr = self.temperature_from_theta_e_with_rh(
                windward_theta_e, pressure, corrected_rh, initial_guess=api_temp
            )

            if T_corr is not None:
                # 補正値とAPI値を重み付き平均
                final_temp = api_temp * (1 - weight) + T_corr * weight
                final_dewpoint = api_dewpoint * (1 - weight) + Td_corr * weight
                return final_temp, final_dewpoint

        # フォールバック: API値をそのまま返す
        return api_temp, api_dewpoint

# グローバルインスタンス
theta_e_corrector = ThetaECorrector()

def generate_spot_name(lat, lon):
    """Generate spot name from coordinates"""
    lat_str = f"{int(lat * 10000):04d}"
    lon_str = f"{int(lon * 10000):04d}"
    return f"H_{lat_str}_{lon_str}"

def validate_terrain_for_spot(lat, lon):
    """Basic terrain validation for new spots"""
    # Simple validation - ensure coordinates are within Rishiri Island bounds
    if not (45.0 <= lat <= 45.3 and 141.1 <= lon <= 141.4):
        return {"valid": False, "message": "座標が利尻島の範囲外です"}
    return {"valid": True, "message": "OK"}

def calculate_spot_theta(lat, lon):
    """
    干場の極座標θを計算（仕様書 lines 72-73）

    Parameters:
    - lat: 干場の緯度
    - lon: 干場の経度

    Returns:
    - theta: 利尻山中心からの極座標角度（度）
            南岸境界（北緯45.1007度、東経141.2461度）をθ=0とする
    """
    import math

    # 利尻山の座標（仕様書 line 72）
    mountain_lat = 45.1821
    mountain_lon = 141.2421

    # 南岸境界の座標（仕様書 line 73）
    base_lat = 45.1007
    base_lon = 141.2461

    # 利尻山からの相対座標
    dx = lon - mountain_lon
    dy = lat - mountain_lat

    # 南岸境界までの角度（基準角度）
    base_dx = base_lon - mountain_lon
    base_dy = base_lat - mountain_lat
    base_angle = math.degrees(math.atan2(base_dy, base_dx))

    # 干場の角度
    spot_angle = math.degrees(math.atan2(dy, dx))

    # θ = (spot_angle - base_angle) を0-360度に正規化
    theta = (spot_angle - base_angle) % 360

    return theta

def calculate_wind_angle_difference(wind_direction, spot_theta):
    """
    風向と干場θ値との角度差を計算（仕様書 line 95）

    Parameters:
    - wind_direction: 気象風向（度、0-360、真北=0）
    - spot_theta: 干場の極座標θ（度、0-360）

    Returns:
    - angle_diff: 風向と干場θの角度差（度、-180～180）
                 正の値: 風が干場から時計回りに吹く
                 負の値: 風が干場から反時計回りに吹く
    """
    if wind_direction is None or spot_theta is None:
        return None

    # 気象風向を干場θ座標系に変換（仕様書 line 338）
    # 干場θ = 177.2° - 気象風向
    wind_theta = 177.2 - wind_direction
    if wind_theta < 0:
        wind_theta += 360

    # 角度差を計算（-180～180度に正規化）
    diff = wind_theta - spot_theta
    if diff > 180:
        diff -= 360
    elif diff < -180:
        diff += 360

    return diff

# ============================================================================
# 4-File Synchronization Functions (4ファイル自動同期)
# ============================================================================

def sync_kml_file(df):
    """
    CSVデータからKMLファイルを生成（hoshiba_spots.csvと同期）

    Args:
        df: hoshiba_spots.csvのDataFrame
    """
    try:
        kml_header = """<?xml version='1.0' encoding='UTF-8'?>
<kml xmlns='http://www.opengis.net/kml/2.2'>
<Document>
"""
        kml_footer = """</Document>
</kml>"""

        placemark_entries = []
        for _, row in df.iterrows():
            placemark = f"""<Placemark>
<name>{row['name']}</name>
<Point><coordinates>{row['lon']:.7f},{row['lat']:.7f}</coordinates></Point>
</Placemark>"""
            placemark_entries.append(placemark)

        kml_content = kml_header + "\n".join(placemark_entries) + "\n" + kml_footer

        with open(KML_FILE, 'w', encoding='utf-8') as f:
            f.write(kml_content)

        return True
    except Exception as e:
        print(f"KML sync error: {e}")
        return False


def sync_js_array_file(df):
    """
    CSVデータからJavaScript配列ファイルを生成（hoshiba_spots.csvと同期）

    Args:
        df: hoshiba_spots.csvのDataFrame
    """
    try:
        js_header = "const hoshibaSpots = [\n"
        js_footer = "];\n"

        js_entries = []
        for _, row in df.iterrows():
            # Handle NaN values
            town = row.get('town', '')
            district = row.get('district', '')
            buraku = row.get('buraku', '')

            if pd.isna(town):
                town = ''
            if pd.isna(district):
                district = ''
            if pd.isna(buraku):
                buraku = ''

            js_entry = f'    {{ name: "{row["name"]}", lat: {row["lat"]:.7f}, lon: {row["lon"]:.7f}, town: "{town}", district: "{district}", buraku: "{buraku}" }}'
            js_entries.append(js_entry)

        js_content = js_header + ",\n".join(js_entries) + "\n" + js_footer

        with open(JS_ARRAY_FILE, 'w', encoding='utf-8') as f:
            f.write(js_content)

        return True
    except Exception as e:
        print(f"JS array sync error: {e}")
        return False


def sync_all_files_from_csv():
    """
    CSVを基準として全4ファイルを同期

    Returns:
        dict: 同期結果 {"csv": True, "kml": bool, "js": bool}
    """
    try:
        df = pd.read_csv(CSV_FILE)

        kml_success = sync_kml_file(df)
        js_success = sync_js_array_file(df)

        return {
            "csv": True,
            "kml": kml_success,
            "js": js_success,
            "total_spots": len(df)
        }
    except Exception as e:
        print(f"Sync all files error: {e}")
        return {
            "csv": False,
            "kml": False,
            "js": False,
            "error": str(e)
        }

# Web UI Routes
@app.route('/dashboard')
def dashboard():
    """Serve the dashboard"""
    return send_file(os.path.join(BASE_DIR, 'dashboard.html'))

@app.route('/mobile')
def mobile():
    """Serve mobile interface"""
    return send_file(os.path.join(BASE_DIR, 'mobile_forecast_interface.html'))

@app.route('/rishiri-island')
@app.route('/island')
def rishiri_island_landing():
    """Serve the Rishiri island-facing landing page"""
    response = send_file(os.path.join(BASE_DIR, 'rishiri_island_lp.html'))
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

@app.route("/drying-map")
@app.route("/map")
@app.route("/")
def drying_map():
    """Serve the unified kelp drying map (production version with all features)"""
    response = send_file(os.path.join(BASE_DIR, "kelp_drying_map.html"))
    # Prevent caching to ensure users always get the latest version
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

# Static file routes for JavaScript files
@app.route('/all_spots_array.js')
def serve_all_spots_js():
    """Serve the all_spots_array.js file"""
    return send_file(os.path.join(BASE_DIR, 'all_spots_array.js'), mimetype='application/javascript')

@app.route('/rishiri_wind_names.js')
def serve_wind_names_js():
    """Traditional wind-name JS removed in v2.6.15. Return 410 Gone."""
    return ('// rishiri_wind_names.js was removed in v2.6.15 '
            '(traditional wind names replaced by windDisplay()).\n',
            410, {'Content-Type': 'application/javascript'})

@app.route('/manifest.json')
def serve_manifest():
    """Serve the PWA manifest file"""
    response = send_file(os.path.join(BASE_DIR, 'manifest.json'), mimetype='application/manifest+json')
    response.headers['Cache-Control'] = 'no-cache'
    return response

@app.route('/service-worker.js')
def serve_service_worker():
    """Serve the service worker for PWA and offline functionality"""
    return send_file(os.path.join(BASE_DIR, 'service-worker.js'), mimetype='application/javascript')

@app.route('/offline.html')
def serve_offline():
    """Serve the offline fallback page"""
    return send_file(os.path.join(BASE_DIR, 'offline.html'))

@app.route('/static/icons/<path:filename>')
def serve_icon(filename):
    """Serve PWA icon files"""
    return send_from_directory(os.path.join(BASE_DIR, 'static', 'icons'), filename)

@app.route('/favicon.svg')
def serve_favicon():
    """Serve the favicon"""
    return send_file(os.path.join(BASE_DIR, 'favicon.svg'), mimetype='image/svg+xml')

@app.route('/app_icon.png')
def serve_app_icon():
    """Serve the app logo used in all UI pages"""
    return send_file(os.path.join(BASE_DIR, 'app_icon.png'), mimetype='image/png')

@app.route('/api/info')
def api_info():
    """API information and available endpoints"""
    return {
        'message': 'Rishiri Kelp Forecast System - Production Version',
        'status': 'ok',
        'version': '2.6.15',
        'api_endpoints': {
            'weather': '/api/weather',
            'forecast': '/api/forecast',
            'spots': '/api/spots',
            'terrain': '/api/terrain/<spot_name>',
            'contours': '/api/analysis/contours',
            'spot_differences': '/api/analysis/spot-differences',
            'accuracy': '/api/validation/accuracy',
            'emagram': '/api/emagram',
            'forecast_calibration': '/api/forecast_calibration',
            'record': '/record',
            'add_spot': '/add',
            'delete_spot': '/delete',
            'health': '/health',
            'info': '/api/info',
            'amedas_realtime': '/api/amedas/realtime',
            'nowcast_precip': '/api/nowcast/precip',
        },
        'web_ui': {
            'main': '/',
            'drying_map': '/drying-map',
            'map': '/map',
            'dashboard': '/dashboard',
            'mobile': '/mobile',
            'offline': '/offline.html'
        },
        'features': {
            'validated_thresholds': 'H_1631_1434実測データ基準（21件、2025/6-8）',
            'traditional_wind_names': '利尻島16方位伝統風名',
            'terrain_corrections': '地形・標高・海岸効果補正',
            'stage_based_assessment': '段階別乾燥判定（初期/後半）',
            'offline_support': 'PWA対応・オフライン機能',
            'deletion_restrictions': '4条件制限付き干場削除',
            'wind_angle_diff': '風向と方位角の角度差表示（2025年11月：気象方位角に統一）',
            'four_file_sync': '4ファイル自動同期（CSV/KML/JS/Records、2025年12月実装）',
            'unified_html': '統合版HTML（v1/v2統合、等値線マップ・エマグラム全機能搭載）'
        }
    }

@app.route('/health')
def health():
    return {'status': 'healthy', 'version': '2.6.15'}, 200

@app.route('/api/weather')
def get_weather():
    """Get current weather for Rishiri Island"""
    # Rishiri Island coordinates
    lat = request.args.get('lat', 45.178269)
    lon = request.args.get('lon', 141.228528)

    try:
        # Get elevation for accurate DEM correction
        elevation = get_elevation(float(lat), float(lon))

        # Open-Meteo API for current weather with elevation parameter
        url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&elevation={elevation}&current_weather=true&hourly=temperature_2m,relative_humidity_2m,wind_speed_10m,wind_direction_10m"

        response = requests.get(url, timeout=10)
        response.raise_for_status()

        data = response.json()
        current = data.get('current_weather', {})

        return {
            'location': 'Rishiri Island',
            'coordinates': {'lat': float(lat), 'lon': float(lon)},
            'current': {
                'temperature': current.get('temperature'),
                'wind_speed': current.get('windspeed') / 3.6 if current.get('windspeed') is not None else None,  # Convert km/h to m/s
                'wind_direction': current.get('winddirection'),
                'weather_code': current.get('weathercode')
            },
            'timestamp': datetime.now(tz=JST).isoformat(),
            'status': 'success'
        }

    except Exception as e:
        return {
            'error': 'Weather data unavailable',
            'message': str(e),
            'status': 'error'
        }, 503

@app.route('/api/jma_warnings')
def get_jma_warnings():
    """Get JMA weather warnings/advisories for Rishiri Island (利尻島)"""
    try:
        # Hokkaido prefecture warning data (016000)
        url = "https://www.jma.go.jp/bosai/warning/data/warning/016000.json"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()

        warnings = []
        # areaStatuses contains per-area warning info; search for 利尻
        for area in data.get('areaStatuses', []):
            area_name = area.get('areaName', '')
            if '利尻' not in area_name:
                continue
            area_warnings = area.get('warnings', [])
            active = [
                {'name': w.get('name', ''), 'status': w.get('status', '')}
                for w in area_warnings
                if w.get('status') not in ('', '解除', None)
            ]
            if active:
                warnings.append({'area': area_name, 'warnings': active})

        return {
            'warnings': warnings,
            'hasWarnings': len(warnings) > 0,
            'timestamp': datetime.now(tz=JST).isoformat(),
            'status': 'success'
        }

    except Exception as e:
        return {
            'warnings': [],
            'hasWarnings': False,
            'error': str(e),
            'status': 'error'
        }, 503


SEASONAL_OUTLOOK_FILE = os.path.join(BASE_DIR, 'seasonal_outlook.json')

@app.route('/api/seasonal_outlook', methods=['GET'])
def get_seasonal_outlook():
    """Get kelp-season long-range outlook (monthly admin input)"""
    try:
        if os.path.exists(SEASONAL_OUTLOOK_FILE):
            with open(SEASONAL_OUTLOOK_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
        else:
            data = {
                'season': str(datetime.now(tz=JST).year),
                'updated': None,
                'source': '',
                'expertComment': '',
                'enso': '',
                'months': {str(m): {'outlook': '', 'confidence': '', 'detail': ''} for m in range(6, 10)}
            }
        return jsonify(data)
    except Exception as e:
        return jsonify({'error': str(e), 'status': 'error'}), 500


@app.route('/api/seasonal_outlook', methods=['POST'])
def update_seasonal_outlook():
    """Update kelp-season long-range outlook"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data'}), 400
        # Only allow known fields
        allowed = {'season', 'updated', 'source', 'expertComment', 'enso', 'months'}
        cleaned = {k: v for k, v in data.items() if k in allowed}
        cleaned['updated'] = datetime.now(JST).strftime('%Y-%m-%d')
        with open(SEASONAL_OUTLOOK_FILE, 'w', encoding='utf-8') as f:
            json.dump(cleaned, f, ensure_ascii=False, indent=2)
        return jsonify({'status': 'ok', 'updated': cleaned['updated']})
    except Exception as e:
        return jsonify({'error': str(e), 'status': 'error'}), 500


def _save_forecast_history(spot_name, forecasts):
    """Save each day's forecast to forecast_history/ for later accuracy comparison."""
    today_str = datetime.now(tz=JST).strftime('%Y%m%d')
    spot_dir = os.path.join(FORECAST_HISTORY_DIR, spot_name)
    os.makedirs(spot_dir, exist_ok=True)
    for fc in forecasts:
        target_date_str = fc['date'].replace('-', '')
        filepath = os.path.join(spot_dir, f'forecast_{today_str}_for_{target_date_str}.json')
        if os.path.exists(filepath):
            continue
        hourly = fc.get('hourly_details', [])
        valid_humidity = [h['humidity'] for h in hourly if h.get('humidity') is not None]
        valid_wind = [h['wind_speed'] for h in hourly if h.get('wind_speed') is not None]
        # hourly_details は 04:00-16:00 の時別データのみ（13時間）
        precip_0416 = round(sum(h.get('precipitation') or 0 for h in hourly), 2)
        record = {
            'forecast_date':    today_str,
            'target_date':      fc['date'],
            'day_number':       fc['day_number'],
            'max_temp':         fc['daily_summary']['temperature_max'],
            'min_humidity':     min(valid_humidity) if valid_humidity else None,
            'avg_wind':         sum(valid_wind) / len(valid_wind) if valid_wind else None,
            'precipitation':    fc['daily_summary']['precipitation'],  # 24時間全日積算
            'precipitation_0416': precip_0416,                         # 04:00-16:00 積算（実測比較用）
            'drying_score':     fc['daily_summary']['drying_score'],
            'suitability':      fc['daily_summary']['suitability'],
        }
        # ローカルファイルに保存（副）
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(record, f, ensure_ascii=False)
        except Exception as e:
            app.logger.error('[forecast_history] local save error for %s %s: %s', spot_name, target_date_str, e)
        # Redis に保存（主：デプロイをまたいで永続化）
        # Key: forecast:hist:{spot_name}:{target_YYYYMMDD}
        redis_key = f'forecast:hist:{spot_name}:{target_date_str}'
        try:
            existing = _obs_redis_get(redis_key) or []
            if not any(e.get('forecast_date') == today_str for e in existing):
                existing.append(record)
                _obs_redis_set(redis_key, existing)
        except Exception as re:
            app.logger.warning('[forecast_history] Redis save error for %s: %s', redis_key, re)


@app.route('/api/forecast')
@limiter.limit("60 per minute")
def get_forecast():
    """Get enhanced kelp drying forecast for Rishiri Island"""
    lat = float(request.args.get('lat', 45.178269))
    lon = float(request.args.get('lon', 141.228528))

    # Get elevation for accurate DEM correction
    elevation = get_elevation(lat, lon)

    # Calculate spot theta for wind angle difference calculation
    spot_theta = calculate_spot_theta(lat, lon)

    # Calculate mountain azimuth (spot→peak direction)
    import math
    RISHIRI_SAN_LAT = 45.1821
    RISHIRI_SAN_LON = 141.2421
    delta_lat = RISHIRI_SAN_LAT - lat
    delta_lon = RISHIRI_SAN_LON - lon
    # atan2(dy, dx) gives mathematical angle (East=0°, counterclockwise)
    # Convert to azimuth (North=0°, clockwise): azimuth = 90° - math_angle
    math_angle = math.degrees(math.atan2(delta_lat, delta_lon))
    mountain_azimuth = 90 - math_angle
    if mountain_azimuth < 0:
        mountain_azimuth += 360
    elif mountain_azimuth >= 360:
        mountain_azimuth -= 360

    try:
        # Enhanced weather data with hourly details including moisture and boundary layer
        # Note: Use surface_pressure and dewpoint to calculate PWV, use mixing_height for PBLH
        url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&elevation={elevation}&hourly=temperature_2m,relative_humidity_2m,wind_speed_10m,wind_direction_10m,cloud_cover,shortwave_radiation,direct_radiation,pressure_msl,precipitation,precipitation_probability,cape,temperature_700hPa,relative_humidity_700hPa,wind_speed_700hPa,wind_direction_700hPa,temperature_850hPa,relative_humidity_850hPa,wind_speed_850hPa,wind_direction_850hPa,dewpoint_2m,surface_pressure&daily=temperature_2m_max,temperature_2m_min,wind_speed_10m_max,relative_humidity_2m_mean,precipitation_sum,precipitation_probability_max&timezone=Asia/Tokyo&forecast_days=7"

        response = requests.get(url, timeout=10)
        response.raise_for_status()

        data = response.json()
        daily = data.get('daily', {})
        hourly = data.get('hourly', {})

        # Reliability by forecast day
        reliability_table = {
            0: {'accuracy': 100, 'confidence': '最高', 'usage': '作業決定'},
            1: {'accuracy': 95, 'confidence': '高', 'usage': '作業計画'},
            2: {'accuracy': 85, 'confidence': '良', 'usage': '準備検討'},
            3: {'accuracy': 70, 'confidence': '中', 'usage': '参考情報'},
            4: {'accuracy': 70, 'confidence': '中', 'usage': '参考情報'},
            5: {'accuracy': 50, 'confidence': '低', 'usage': '傾向把握'},
            6: {'accuracy': 50, 'confidence': '低', 'usage': '傾向把握'}
        }

        # SST（海面水温）取得 — 7日分をまとめて取得（WINDY_RESEARCH §6 W6）
        sst_list = get_sea_surface_temperature(lat, lon)

        # Enhanced kelp drying forecasts
        forecasts = []
        for i in range(min(7, len(daily.get('time', [])))):
            date_str = daily['time'][i]

            # Daily data
            temp_max = daily['temperature_2m_max'][i]
            temp_min = daily['temperature_2m_min'][i]
            humidity = daily['relative_humidity_2m_mean'][i]
            wind_speed = daily['wind_speed_10m_max'][i] / 3.6  # Convert km/h to m/s
            pop_max = daily['precipitation_probability_max'][i] if 'precipitation_probability_max' in daily and daily['precipitation_probability_max'][i] is not None else None

            # 作業時間帯（04:00-16:00 JST）の降水量のみ積算
            # 砂利干場は夜間雨が滞水しないため、夜間降水は乾燥判定に含めない
            start_hour = i * 24 + 4  # 4AM of the day
            end_hour = start_hour + 13  # Until 4PM inclusive (13 hours: 4,5,6,...,16)
            _ph = hourly.get('precipitation', [])
            precipitation = round(
                sum(p for p in _ph[start_hour:end_hour] if p is not None), 2
            )

            # Calculate daily representative wind direction (average of working hours)
            daily_wind_directions = []

            for h in range(start_hour, min(end_hour, len(hourly.get('wind_direction_10m', [])))):
                if h < len(hourly['wind_direction_10m']) and hourly['wind_direction_10m'][h] is not None:
                    daily_wind_directions.append(hourly['wind_direction_10m'][h])

            # Calculate average wind direction (circular mean)
            representative_wind_dir = None
            if daily_wind_directions:
                # Convert to radians, calculate circular mean
                import math
                sin_sum = sum(math.sin(math.radians(d)) for d in daily_wind_directions)
                cos_sum = sum(math.cos(math.radians(d)) for d in daily_wind_directions)
                if cos_sum != 0 or sin_sum != 0:
                    mean_rad = math.atan2(sin_sum, cos_sum)
                    representative_wind_dir = (math.degrees(mean_rad) + 360) % 360

            # Hourly data for 4AM-4PM inclusive (working hours: 13 hours)
            hourly_data = []

            for h in range(start_hour, min(end_hour, len(hourly.get('temperature_2m', [])))):
                if h < len(hourly['temperature_2m']):
                    wind_dir = hourly['wind_direction_10m'][h] if hourly['wind_direction_10m'][h] is not None else None
                    # Calculate angle difference between wind direction and mountain azimuth
                    # Wind direction = where wind comes FROM, so wind blows TOWARD (wind_dir + 180°)
                    if wind_dir is not None:
                        wind_toward = (wind_dir + 180) % 360  # Direction wind is blowing toward
                        angle_diff = abs(wind_toward - mountain_azimuth)
                        if angle_diff > 180:
                            angle_diff = 360 - angle_diff
                        wind_mountain_angle_diff = angle_diff
                    else:
                        wind_mountain_angle_diff = None

                    hour_data = {
                        'time': f"{h % 24:02d}:00",
                        'temperature': hourly['temperature_2m'][h] if hourly['temperature_2m'][h] is not None else None,
                        'humidity': hourly['relative_humidity_2m'][h] if hourly['relative_humidity_2m'][h] is not None else None,
                        'wind_speed': hourly['wind_speed_10m'][h] / 3.6 if hourly['wind_speed_10m'][h] is not None else None,  # Convert km/h to m/s
                        'wind_direction': wind_dir,
                        'wind_angle_diff': wind_mountain_angle_diff,  # 後方互換性のため
                        'wind_mountain_angle_diff': wind_mountain_angle_diff,  # 風向と山頂方位角の角度差
                        'cloud_cover': hourly['cloud_cover'][h] if hourly['cloud_cover'][h] is not None else None,
                        'solar_radiation': (hourly.get('shortwave_radiation', [None])[h] if h < len(hourly.get('shortwave_radiation', [])) and hourly.get('shortwave_radiation', [None])[h] is not None else hourly['direct_radiation'][h] if hourly['direct_radiation'][h] is not None else None),
                        'pressure': hourly['pressure_msl'][h] if hourly['pressure_msl'][h] is not None else None,
                        'precipitation': hourly['precipitation'][h] if hourly['precipitation'][h] is not None else 0.0,
                        # 700hPa pressure level data (for vertical velocity estimation)
                        'temp_700hpa': hourly['temperature_700hPa'][h] if h < len(hourly.get('temperature_700hPa', [])) and hourly['temperature_700hPa'][h] is not None else None,
                        'humidity_700hpa': hourly['relative_humidity_700hPa'][h] if h < len(hourly.get('relative_humidity_700hPa', [])) and hourly['relative_humidity_700hPa'][h] is not None else None,
                        'wind_speed_700hpa': hourly['wind_speed_700hPa'][h] / 3.6 if h < len(hourly.get('wind_speed_700hPa', [])) and hourly['wind_speed_700hPa'][h] is not None else None,
                        'wind_direction_700hpa': hourly['wind_direction_700hPa'][h] if h < len(hourly.get('wind_direction_700hPa', [])) and hourly['wind_direction_700hPa'][h] is not None else None,
                        # 850hPa pressure level data (for equivalent potential temperature)
                        'temp_850hpa': hourly['temperature_850hPa'][h] if h < len(hourly.get('temperature_850hPa', [])) and hourly['temperature_850hPa'][h] is not None else None,
                        'humidity_850hpa': hourly['relative_humidity_850hPa'][h] if h < len(hourly.get('relative_humidity_850hPa', [])) and hourly['relative_humidity_850hPa'][h] is not None else None,
                        'wind_speed_850hpa': hourly['wind_speed_850hPa'][h] / 3.6 if h < len(hourly.get('wind_speed_850hPa', [])) and hourly['wind_speed_850hPa'][h] is not None else None,
                        'wind_direction_850hpa': hourly['wind_direction_850hPa'][h] if h < len(hourly.get('wind_direction_850hPa', [])) and hourly['wind_direction_850hPa'][h] is not None else None,
                        # Dewpoint and surface pressure for PWV calculation
                        'dewpoint': hourly['dewpoint_2m'][h] if h < len(hourly.get('dewpoint_2m', [])) and hourly['dewpoint_2m'][h] is not None else None,
                        'surface_pressure': hourly['surface_pressure'][h] if h < len(hourly.get('surface_pressure', [])) and hourly['surface_pressure'][h] is not None else None,
                        # CAPE (convective instability) and precipitation probability (Windy W10/W11)
                        'cape': hourly['cape'][h] if h < len(hourly.get('cape', [])) and hourly['cape'][h] is not None else None,
                        'precipitation_probability': hourly['precipitation_probability'][h] if h < len(hourly.get('precipitation_probability', [])) and hourly['precipitation_probability'][h] is not None else None,
                    }
                    # Fog risk from dew point depression (ISLAND_METEOROLOGY_RESEARCH §7, G4)
                    temp_val = hour_data.get('temperature')
                    dew_val  = hour_data.get('dewpoint')
                    if temp_val is not None and dew_val is not None:
                        depression = temp_val - dew_val
                        if depression < 2:
                            hour_data['fog_risk'] = 'high'
                        elif depression < 5:
                            hour_data['fog_risk'] = 'medium'
                        else:
                            hour_data['fog_risk'] = 'low'
                    else:
                        hour_data['fog_risk'] = 'unknown'
                    hourly_data.append(hour_data)

            # 地形補正を時間帯別データに適用（等値線図との整合性確保）
            is_forest = is_forest_area(lat, lon)
            is_coastal = is_coastal_area(lat, lon)
            elevation = get_elevation(lat, lon)

            for j, hour_data in enumerate(hourly_data):
                # 地形補正を適用
                # 気温補正は削除：Open-Meteoが既に0.7°C/100mで補正済み

                # onshore 判定（ISLAND_METEOROLOGY_RESEARCH §11 G2）
                # 風が山側から吹く方向かどうか: angle_diff < 90° = onshore
                angle_diff = hour_data.get('wind_mountain_angle_diff')
                is_onshore = (angle_diff is not None and angle_diff < 90)

                if hour_data.get('humidity') is not None:
                    if is_forest:
                        hour_data['humidity'] = min(100, hour_data['humidity'] + 10.0)
                    # 海岸湿度補正: onshore 風のときのみ適用（改善: onshore限定）
                    if is_coastal and is_onshore:
                        hour_data['humidity'] = min(100, hour_data['humidity'] + 5.0)
                    if elevation > 10:
                        hour_data['humidity'] = max(0, hour_data['humidity'] - (elevation / 100) * 1.0)

                if hour_data.get('wind_speed') is not None:
                    if is_forest:
                        hour_data['wind_speed'] = max(0, hour_data['wind_speed'] - 2.5)
                    # 海岸風速補正: onshore 限定に改善
                    if is_coastal and is_onshore:
                        hour_data['wind_speed'] += 1.0

                # フェーンボーナス（ISLAND_METEOROLOGY_RESEARCH §11 G6）
                # 山背風: angle_diff > 150° かつ風速 > 3 m/s → 乾燥促進フラグ
                wind_spd = hour_data.get('wind_speed', 0) or 0
                hour_data['foehn_effect'] = (
                    angle_diff is not None and angle_diff > 150 and wind_spd > 3.0
                )

            # Calculate enhanced vertical p-velocity estimation using 700hPa data
            for j, hour_data in enumerate(hourly_data):
                omega = estimate_vertical_p_velocity_700hpa(hourly_data, j, hourly, start_hour + j)
                hour_data['vertical_p_velocity'] = omega

                # Calculate simplified SSI estimation
                ssi = estimate_ssi_simplified(hour_data, hourly_data, j)
                hour_data['ssi'] = ssi

                # Calculate equivalent potential temperature at 850hPa level
                theta_e = calculate_equivalent_potential_temperature_850hpa(
                    hour_data['temp_850hpa'],
                    hour_data['humidity_850hpa'],
                    850.0  # 850hPa pressure level
                )
                hour_data['equivalent_potential_temperature'] = theta_e

                # Calculate 500hPa vorticity approximation
                vorticity = calculate_500hpa_vorticity(hourly_data, j)
                hour_data['vorticity_500hpa'] = vorticity

                # Calculate PWV from dewpoint and surface pressure
                pwv = calculate_pwv_from_dewpoint(
                    hour_data.get('temperature'),
                    hour_data.get('dewpoint'),
                    hour_data.get('surface_pressure')
                )
                hour_data['precipitable_water'] = pwv

                # Estimate PBLH from surface conditions
                pblh = estimate_pblh_from_conditions(
                    hour_data.get('temperature'),
                    hour_data.get('wind_speed'),
                    hour_data.get('solar_radiation', 0),
                    hour_data.get('cloud_cover', 0),
                    int(hour_data['time'].split(':')[0])
                )
                hour_data['boundary_layer_height'] = pblh

                # Calculate PWV and PBLH scores
                pwv_pblh_analysis = calculate_pwv_pblh_combined_score(pwv, pblh)
                hour_data['pwv_pblh_analysis'] = pwv_pblh_analysis

            # 作業時間帯（4:00-16:00）の平均日射量を算出して enhanced score に渡す
            solar_values = [h.get('solar_radiation') for h in hourly_data if h.get('solar_radiation') is not None]
            avg_solar = sum(solar_values) / len(solar_values) if solar_values else None

            # Enhanced drying score calculation (K1/K2/K8: solar + Arrhenius temp + 0mm rule)
            score = calculate_enhanced_drying_score(temp_max, humidity, wind_speed, precipitation,
                                                    lat, lon, avg_solar_radiation=avg_solar,
                                                    pop_max=pop_max)

            # Stage-based drying assessment according to specification
            stage_analysis = calculate_stage_based_drying_assessment(hourly_data, i)

            # --- 再吸湿リスク (K6) ---
            remoistening_risk = calculate_remoistening_risk(hourly_data)

            # --- CAPE リスク (W10) ---
            cape_values = [h.get('cape') for h in hourly_data if h.get('cape') is not None]
            max_cape = max(cape_values) if cape_values else None
            cape_risk = assess_cape_risk(max_cape)

            # --- フェーンボーナス: stage_analysis のみ ───────────────────────
            # drying_score への適用は _apply_local_risk_adjustments() で統一実施。
            foehn_hours = sum(1 for h in hourly_data if h.get('foehn_effect'))
            foehn_bonus = min(15, foehn_hours * 3)  # 最大+15点
            if foehn_hours > 0:
                stage_analysis['overall_score'] = min(
                    100, stage_analysis['overall_score'] + foehn_bonus
                )

            # --- 霧リスク: stage_analysis のみ ──────────────────────────────
            fog_summary, _fog_note_fc = _compute_fog_from_hourly_flags(hourly_data)
            _fog_sa_pen = {'high': -15, 'medium': -7, 'low': 0}[fog_summary]
            if _fog_sa_pen < 0:
                stage_analysis['overall_score'] = max(
                    0, stage_analysis['overall_score'] + _fog_sa_pen
                )

            # --- SST & 霧リスク: stage_analysis のみ ─────────────────────────
            sst_today = sst_list[i] if i < len(sst_list) else None
            sst_fog_risk = assess_sst_fog_risk(sst_today, temp_max)
            if sst_fog_risk in ('very_high', 'high'):
                stage_analysis['overall_score'] = max(
                    0, stage_analysis['overall_score'] - 10
                )

            # ─── 4補正を drying_score に一括適用（共通経路）─────────────────
            # 係数は stage_analysis より控えめ（実測根拠が薄いため）:
            #   fog: medium -5 / high -10   foehn: +2/h max+8   SST: -5
            # 新補正追加時は _apply_local_risk_adjustments() だけを変更すること。
            score, local_risk_adjustments = _apply_local_risk_adjustments(
                score,
                cape_risk    = cape_risk,
                fog_summary  = fog_summary,
                fog_note     = _fog_note_fc,
                foehn_hours  = foehn_hours,
                sst_fog_risk = sst_fog_risk,
            )

            # --- ソルナー指数 (W9) ---
            try:
                target_dt = datetime.strptime(date_str, '%Y-%m-%d')
                solunar_score, moon_phase_name, moon_age = calculate_solunar_score(target_dt)
            except Exception:
                solunar_score, moon_phase_name, moon_age = 0, '不明', 0.0

            # --- 予報信頼度（日数ベース簡易版、W14）---
            # Day0-1:5★(今日・明日), Day2-3:3★(準備検討), Day4-6:2★(傾向把握)
            reliability_stars = [5, 5, 3, 3, 2, 2, 1][i] if i < 7 else 1

            # Determine suitability based on corrected drying_score (= score).
            # 旧実装: stage_analysis['overall_score'] を使用 → drying_score と乖離しUIに矛盾が生じた
            #   例: drying_score=72 なのに suitability='poor'（stage_overall≈0）
            # 新実装: score（補正済み drying_score）を基準にする → UI整合性を確保。
            # stage_analysis は 'stage_analysis' フィールドとして内部診断値として保持（変更なし）。
            # estimated_drying_time は score>=40 の場合に限り stage_analysis の予測値を流用する。
            if score >= 80:
                suitability = 'excellent'
                drying_time = stage_analysis['predicted_completion_time']
            elif score >= 60:
                suitability = 'good'
                drying_time = stage_analysis['predicted_completion_time']
            elif score >= 40:
                suitability = 'fair'
                drying_time = stage_analysis['predicted_completion_time']
            else:
                suitability = 'poor'
                drying_time = '乾燥困難、延期推奨'

            # --- 風速警告 (表示レイヤー _wind_color と整合した4バンド) ---
            # 平均(wind_speed)ではなく日内最大(max_wind)を使用してピーク強風を捉える
            _max_wind = stage_analysis.get('conditions_summary', {}).get('max_wind') or wind_speed or 0
            wind_warning = _make_wind_warning(_max_wind)   # 共通ヘルパーで生成

            forecast_day = {
                'date': date_str,
                'day_number': i,  # 0=今日, 1=明日, 2=明後日...
                'reliability': reliability_table.get(i, reliability_table[6]),
                'reliability_stars': reliability_stars,  # W14: 1〜5 の簡易信頼度
                'daily_summary': {
                    'temperature_max': temp_max,
                    'temperature_min': temp_min,
                    'humidity': humidity,
                    'wind_speed': wind_speed,
                    'wind_direction': representative_wind_dir,
                    'precipitation': precipitation,
                    'precipitation_probability': pop_max,      # W11: 降水確率
                    'avg_solar_radiation': round(avg_solar, 1) if avg_solar is not None else None,
                    'drying_score': score,
                    'suitability': suitability,
                    'estimated_drying_time': drying_time,
                    'stage_analysis': stage_analysis,
                    # --- 新規リスク評価 ---
                    'remoistening_risk': remoistening_risk,        # K6: 再吸湿リスク
                    'cape_risk': cape_risk,                        # W10: 対流不安定リスク
                    'wind_warning': wind_warning,                  # 風速警告 (None / caution / danger)
                    'fog_risk_summary': fog_summary,               # G4: 霧リスク（露点）
                    'foehn_bonus': foehn_bonus,                    # G6: フェーンボーナス点数
                    'sea_surface_temperature': sst_today,          # W6: 海面水温
                    'sst_fog_risk': sst_fog_risk,                  # W6: SST由来霧リスク
                    'local_risk_adjustments': local_risk_adjustments,  # 霧/CAPE/フェーン/SST補正の集計
                    'solunar': {                               # W9: ソルナー指数
                        'score': solunar_score,
                        'moon_phase': moon_phase_name,
                        'moon_age_days': moon_age
                    }
                },
                'hourly_details': hourly_data
            }
            forecasts.append(forecast_day)

        spot_name_param = request.args.get('name', f'spot_{lat}_{lon}')
        _save_forecast_history(spot_name_param, forecasts)

        return {
            'location': 'Rishiri Island',
            'coordinates': {'lat': lat, 'lon': lon},
            'spot_theta': round(spot_theta, 1),  # 干場の極座標θ（仕様書 lines 72-73）
            'mountain_azimuth': round(mountain_azimuth, 1),  # 干場→山頂方位角
            'forecasts': forecasts,
            'timestamp': datetime.now(tz=JST).isoformat(),
            'status': 'success'
        }

    except Exception as e:
        return {
            'error': 'Enhanced forecast data unavailable',
            'message': str(e),
            'status': 'error'
        }, 503

def calculate_enhanced_drying_score(temp_max, humidity, wind_speed, precipitation, lat, lon,
                                    avg_solar_radiation=None, pop_max=None, elevation=None):
    """Enhanced drying score with terrain corrections.
    Improved per KOMBU_DRYING_RESEARCH.md §10 (K1/K2/K8) and WINDY_RESEARCH.md §6 (W11).

    Parameters:
        elevation : 事前取得した標高(m)。None の場合は get_elevation() でAPI取得。
                    _compute_score_field() はバッチ取得して渡すことで高速化する。
                    /api/forecast などの個別呼び出しは従来どおり None のままでよい。
    """
    # --- 入力値の防衛的クランプ（呼び出し元での補正後に範囲を超えた場合に備える）---
    humidity    = max(0.0, min(100.0, float(humidity or 0)))
    wind_speed  = max(0.0, float(wind_speed or 0))
    precipitation = max(0.0, float(precipitation or 0))

    score = 0

    # --- 降水量: 0mm絶対条件 (K8) ---
    # 実測21件すべて0mm。微量雨でも昆布は吸湿し乾燥失敗となる。
    if precipitation == 0:
        score += 15
    # precipitation > 0 は加点なし（最終ゲートで圧縮される）

    # --- 気温: アレニウス近似で細粒度化 (K2) ---
    # 10°C上昇で乾燥速度定数 k が1.5倍。25°Cを基準に連続スコア化。
    if temp_max is not None:
        temp_factor = 1.5 ** ((temp_max - 25) / 10)
        score += min(40, max(0, int(temp_factor * 20)))

    # --- 湿度 ---
    if humidity is not None:
        if humidity < 70: score += 20
        if humidity < 60: score += 10

    # --- 風速: 4バンド評価（表示レイヤー _wind_color と完全整合） ---
    # 「強ければ強いほど良い」ではなく「適風域が最大加点」の逆U字型特性。
    # 2.0 m/s: 境界層が十分に薄化する物理的下限（KOMBU_DRYING_RESEARCH §3）
    # 6.0 m/s: 作業注意域（干場作業の実態に基づく）
    # 9.0 m/s: 飛散危険域（昆布・作業道具の飛散リスク）
    if wind_speed is not None:
        if wind_speed < 2.0:
            pass                 # 弱風: 境界層厚い・乾きにくい → 加点なし
        elif wind_speed < 6.0:
            score += 25          # 適風 (2.0〜5.9 m/s): 最大加点
        elif wind_speed < 9.0:
            score += 10          # 強め (6.0〜8.9 m/s): 乾燥は進むが作業注意
        else:
            score -= 15          # 強風 (≥9.0 m/s): 飛散注意・作業危険 → 減点

    # --- 日射量: Deff 7倍効果を反映 (K1) ---
    # 日射400 W/m²以上でDeffが最大7倍向上（KOMBU_DRYING_RESEARCH §3-2）
    if avg_solar_radiation is not None:
        if avg_solar_radiation >= 600:   score += 20
        elif avg_solar_radiation >= 400: score += 15  # Deff 7倍の閾値
        elif avg_solar_radiation >= 200: score += 8
        elif avg_solar_radiation >= 50:  score += 3
        else:                            score -= 15  # 曇天・日射なし → 乾燥ほぼ停止

    # --- 降水確率ペナルティ (W11) ---
    if pop_max is not None:
        if pop_max >= 70:   score = int(score * 0.3)
        elif pop_max >= 50: score = int(score * 0.6)
        elif pop_max >= 30: score = int(score * 0.85)

    # --- 地形補正 ---
    if is_forest_area(lat, lon):
        score -= 5  # 森林：通風減少

    if is_coastal_area(lat, lon):
        score += 5  # 海岸：通風増加
        score -= 3  # 海岸：湿度増加

    if elevation is None:
        # 個別呼び出し（/api/forecast 等）: Open-Meteo Elevation API で取得
        elevation = get_elevation(lat, lon)
    # フィールド分析では _fetch_elevations_batch() で一括取得済みの値が渡される
    if elevation > 100:
        score += int(elevation / 100) * 2

    # --- 最終降水ゲート（実測根拠による強制圧縮） ---
    # calculate_enhanced_drying_score は気温・風・日射で points を積み上げるが、
    # 雨天時は他の条件が良くても昆布乾燥は不可能。
    # 実測21件: 0.5mm以上は全件乾燥失敗 → 最大8点に強制圧縮（「不可」帯）
    # 0〜0.5mm未満（微量）: 最大30点に圧縮（「要注意」帯）
    if precipitation >= 0.5:
        score = min(score, 8)
    elif precipitation > 0:
        score = min(score, 30)

    return max(0, min(100, score))

def is_forest_area(lat, lon):
    """Simplified forest detection"""
    # Simplified: assume areas near Rishiri mountain are forested
    mountain_lat, mountain_lon = 45.1821, 141.2421
    distance = ((lat - mountain_lat) ** 2 + (lon - mountain_lon) ** 2) ** 0.5
    return distance < 0.02  # Within ~2km of mountain

def is_coastal_area(lat, lon):
    """Simplified coastal area detection"""
    # Most spots are coastal in Rishiri
    return True

_elevation_cache: dict = {}  # key=(round(lat,2), round(lon,2)) → metres

def get_elevation(lat, lon):
    """
    Get elevation from Open-Meteo Elevation API (Copernicus GLO-90 DEM).
    Results are cached in-process at 0.01° resolution (~1 km) to avoid
    repeated API calls when scoring 334 spots sharing the same grid cell.
    """
    cache_key = (round(lat, 2), round(lon, 2))
    if cache_key in _elevation_cache:
        return _elevation_cache[cache_key]

    try:
        url = f"https://api.open-meteo.com/v1/elevation?latitude={lat}&longitude={lon}"
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        data = response.json()

        if 'elevation' in data:
            elevation = data['elevation'][0] if isinstance(data['elevation'], list) else data['elevation']
            result = max(0, elevation)
            _elevation_cache[cache_key] = result
            return result
    except Exception:
        pass

    # Fallback: simplified calculation
    mountain_lat, mountain_lon = 45.1821, 141.2421
    distance = ((lat - mountain_lat) ** 2 + (lon - mountain_lon) ** 2) ** 0.5
    result = max(0, 200 - distance * 10000)
    _elevation_cache[cache_key] = result
    return result

def get_onshore_wind_factor(lat, lon, wind_direction):
    """
    海岸補正の風向依存係数を計算（放射方向モデル）

    利尻山頂を極とした方位角を計算し、その方向を海の方向とする。
    この方位角は部落分類でも使われており、システム全体で整合性がある。

    Parameters:
    - lat, lon: 地点座標
    - wind_direction: 風向（度、気象学的：風が吹いてくる方向、北=0°）

    Returns:
    - factor: 0.0（offshore）～ 1.0（onshore）の係数

    Note:
    - 利尻山頂を極とした極座標の方位角を使用
    - この方位角は hoshiba_spots.csv の部落分類でも使われている
    - 例: 御崎（仙法志）は264°（西）、栄浜（沓形）は162°（南）
    - 放射方向そのものを使うため、円形の島に対して最も正確
    """
    import math

    # 利尻島地理中心座標（利尻山頂上付近）
    island_center_lat, island_center_lon = 45.1821, 141.2421

    # 島中心から地点への方向（地点が島のどちら側にあるか）
    delta_lat = lat - island_center_lat
    delta_lon = lon - island_center_lon

    # 島中心→地点の方位角を計算（これが海の方向）
    # 気象学的方位角: 北=0°、東=90°、南=180°、西=270°（時計回り）
    # atan2(delta_lat, delta_lon)で数学的極座標を計算し、気象学的方位角に変換
    math_angle = math.degrees(math.atan2(delta_lat, delta_lon))
    sea_direction = (90 - math_angle) % 360

    # 風向と海の方向の角度差を計算
    angle_diff = abs(wind_direction - sea_direction)
    if angle_diff > 180:
        angle_diff = 360 - angle_diff

    # 角度差が小さいほど onshore wind（海→陸）
    # 0°（完全なonshore）で factor=1.0、90°（平行）で factor=0.0
    if angle_diff <= 90:
        factor = math.cos(math.radians(angle_diff))  # cos(0°)=1.0, cos(90°)=0.0
    else:
        factor = 0.0  # 90°超は offshore wind（陸→海）

    return max(0.0, factor)

def get_season_solar_factor(month, hour_jst):
    """
    森林補正の季節・日射依存係数を計算

    森林の水蒸気効果は、樹冠蒸散（日射依存）＋日射遮蔽（湿度保持）の複合効果

    Parameters:
    - month: 月（1-12）
    - hour_jst: 日本標準時の時刻（0-23）

    Returns:
    - transpiration_factor: 蒸散係数（0.5～1.5、夏・昼間に大きい）
    - shade_factor: 遮蔽係数（0.8～1.2、夏に大きい）
    """
    import math

    # 季節係数（蒸散量は夏に最大）
    # 6-8月: 1.5、3-5月/9-11月: 1.0、12-2月: 0.5
    if 6 <= month <= 8:
        season_transp = 1.5  # 夏季：活発な蒸散
        season_shade = 1.2   # 夏季：強い日射遮蔽
    elif 3 <= month <= 5 or 9 <= month <= 11:
        season_transp = 1.0  # 春秋：中程度
        season_shade = 1.0
    else:  # 12, 1, 2月
        season_transp = 0.5  # 冬季：蒸散抑制
        season_shade = 0.8   # 冬季：弱い日射

    # 日射係数（蒸散は昼間のみ）
    # 太陽高度の簡易モデル: 6時～18時に山型
    if 6 <= hour_jst <= 18:
        # 正午（12時）に最大1.0、朝夕に0.0
        hour_angle = (hour_jst - 12) * 15  # 度（12時=0°、±90°）
        solar_factor = math.cos(math.radians(hour_angle))  # cos(0°)=1.0
        solar_factor = max(0.0, solar_factor)
    else:
        solar_factor = 0.0  # 夜間は蒸散なし

    # 蒸散係数（季節×日射）
    transpiration_factor = season_transp * solar_factor

    # 遮蔽係数（季節のみ依存、時刻依存小）
    shade_factor = season_shade

    return transpiration_factor, shade_factor

def apply_terrain_correction_to_grid(grid_lat, grid_lon, grid_values, category, grid_temperature=None,
                                    grid_wind_direction=None, month=7, hour_jst=12):
    """
    グリッド点ごとに地形補正を適用（物理的により妥当な方法・状況依存版）

    【物理的妥当性の改善 v2】
    1. 風速補正：加算型→乗算型（負値の自然な防止）
    2. 湿度補正：相対湿度直接補正→水蒸気圧ベース補正（温度依存性を考慮）
    3. 気圧補正：SLP（海面更正気圧）のため補正不要→正しく除外済み
    4. 降水補正：NWPが地形込みのため二重補正防止→正しく除外済み
    5. 海岸補正：風向依存（onshore wind時のみ有効）← NEW
    6. 森林補正：季節・日射依存（蒸散は夏・昼間に最大）← NEW

    Parameters:
    - grid_lat: 緯度グリッド（2D array）
    - grid_lon: 経度グリッド（2D array）
    - grid_values: 補間された気象値（2D array）
    - category: カテゴリー（temperature, humidity, wind等）
    - grid_temperature: 気温グリッド（湿度補正時に必要、℃、オプション）
    - grid_wind_direction: 風向グリッド（海岸補正時に必要、度、オプション）
    - month: 月（1-12、森林補正の季節依存用）
    - hour_jst: 時刻JST（0-23、森林補正の日射依存用）

    Returns:
    - corrected_values: 地形補正後の値（2D array）
    - correction_stats: 補正統計情報dict（クリップ発生回数等）
    """
    corrected_values = grid_values.copy()

    # 補正統計（ログ用）
    correction_stats = {
        'clipped_high': 0,  # 上限クリップ回数
        'clipped_low': 0,   # 下限クリップ回数
        'wind_reduced_to_zero': 0,  # 風速がゼロに減衰した回数
        'humidity_saturated': 0,  # 湿度が100%に達した回数
        'onshore_wind_active': 0,  # onshore wind補正が有効だった回数
        'forest_transpiration_active': 0  # 森林蒸散補正が有効だった回数
    }

    # カテゴリー別に補正を適用
    for i in range(grid_lat.shape[0]):
        for j in range(grid_lat.shape[1]):
            lat = grid_lat[i, j]
            lon = grid_lon[i, j]

            # 地形特性を取得
            is_forest = is_forest_area(lat, lon)
            is_coastal = is_coastal_area(lat, lon)
            elevation = get_elevation(lat, lon)

            # 風向を取得（海岸補正用）
            wind_dir = grid_wind_direction[i, j] if grid_wind_direction is not None else None

            # 季節・日射係数を取得（森林補正用）
            transp_factor, shade_factor = get_season_solar_factor(month, hour_jst)

            # カテゴリー別補正
            if category in ['wind', 'wind_850hpa', 'wind_700hpa']:
                # 風速補正（乗算型：物理的により妥当、負値を自然に防ぐ）
                original_wind = corrected_values[i, j]
                reduction_factor = 1.0

                if is_forest:
                    reduction_factor *= 0.4  # 森林で60%減衰（実測：2.5m/s減少@4m/s → 約60%減）

                # 海岸補正（風向依存）
                if is_coastal and wind_dir is not None:
                    onshore_factor = get_onshore_wind_factor(lat, lon, wind_dir)
                    if onshore_factor > 0.1:  # 閾値：onshore windと判定
                        reduction_factor *= (1.0 + 0.25 * onshore_factor)  # 最大25%増加
                        correction_stats['onshore_wind_active'] += 1

                corrected_values[i, j] = max(0, original_wind * reduction_factor)

                if corrected_values[i, j] == 0 and original_wind > 0:
                    correction_stats['wind_reduced_to_zero'] += 1

            elif category in ['humidity', 'humidity_850hpa', 'humidity_700hpa']:
                # 湿度補正（相対湿度→水蒸気圧→補正→相対湿度：物理的により妥当）
                RH_original = corrected_values[i, j]

                # 気温データがない場合は簡易補正（後方互換性）
                if grid_temperature is None:
                    if is_forest:
                        corrected_values[i, j] = min(100, RH_original + 10.0)
                    if is_coastal:
                        corrected_values[i, j] = min(100, corrected_values[i, j] + 5.0)
                    if elevation > 10:
                        corrected_values[i, j] = max(0, corrected_values[i, j] - (elevation / 100) * 1.0)
                else:
                    # 気温データがある場合：水蒸気圧ベースの物理的補正
                    T_celsius = grid_temperature[i, j]

                    # 飽和水蒸気圧（Magnus式、Sonntag 1990）
                    def es(T):
                        return 6.112 * np.exp(17.67 * T / (T + 243.5))  # hPa

                    es_original = es(T_celsius)
                    e_original = es_original * (RH_original / 100.0)  # 実際の水蒸気圧

                    # 水蒸気圧を補正（森林・海岸効果、状況依存）
                    e_corrected = e_original

                    # 森林補正（季節・日射依存）
                    if is_forest:
                        # 基本係数1.15を季節・日射で変調
                        # 蒸散成分（日射依存）+ 遮蔽成分（季節依存）
                        forest_factor = 1.0 + (0.10 * transp_factor + 0.05 * shade_factor)
                        e_corrected *= forest_factor

                        if transp_factor > 0.3:  # 昼間の蒸散が有効
                            correction_stats['forest_transpiration_active'] += 1

                    # 海岸補正（風向依存）
                    if is_coastal and wind_dir is not None:
                        onshore_factor = get_onshore_wind_factor(lat, lon, wind_dir)
                        if onshore_factor > 0.1:  # onshore windの時のみ
                            # 基本係数1.08を風向で変調
                            coastal_factor = 1.0 + (0.08 * onshore_factor)
                            e_corrected *= coastal_factor
                            correction_stats['onshore_wind_active'] += 1

                    # 標高補正（断熱減率と気圧低下を考慮）
                    if elevation > 10:
                        # Open-Meteoの気温データをそのまま使用（既に標高補正済み）
                        es_at_elevation = es(T_celsius)
                        # 混合比保存：気圧低下に応じて水蒸気圧も変化
                        pressure_ratio = (1000 - elevation / 9) / 1000  # 簡易的な気圧低下（標高100m≈12hPa）
                        e_corrected *= pressure_ratio

                        # 相対湿度を再計算
                        RH_corrected = (e_corrected / es_at_elevation) * 100
                    else:
                        # 標高補正なし
                        RH_corrected = (e_corrected / es_original) * 100

                    corrected_values[i, j] = RH_corrected

                # 境界値処理＆統計記録
                if corrected_values[i, j] >= 100:
                    correction_stats['humidity_saturated'] += 1
                if corrected_values[i, j] > 100:
                    corrected_values[i, j] = 100
                    correction_stats['clipped_high'] += 1
                if corrected_values[i, j] < 0:
                    corrected_values[i, j] = 0
                    correction_stats['clipped_low'] += 1

            elif category in ['temperature', 'temperature_850hpa', 'temperature_700hpa']:
                # 気温補正は削除：Open-Meteoが既に0.7°C/100mで補正済み
                pass

    return corrected_values, correction_stats

@app.route('/api/spots')
def get_spots():
    """Get all hoshiba spots data from CSV"""
    try:
        import csv
        spots = []
        with open(CSV_FILE, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                spots.append({
                    'name': row['name'],
                    'lat': float(row['lat']),
                    'lon': float(row['lon']),
                    'town': row['town'],
                    'district': row['district'],
                    'buraku': row['buraku']
                })
        return jsonify(spots)
    except Exception as e:
        return jsonify({
            'error': 'Spots data unavailable',
            'message': str(e),
            'status': 'error'
        }), 503


@app.route('/api/integration/spots/sheets')
def get_spot_master_for_sheets():
    """Current spot master snapshot for n8n -> Google Sheets replacement sync."""
    try:
        spots_df = pd.read_csv(CSV_FILE)
        synced_at = datetime.now(tz=JST).strftime('%Y-%m-%dT%H:%M:%S+09:00')
        rows = []
        for _, spot in spots_df.iterrows():
            name = str(spot.get('name', ''))
            if name.startswith('A_'):
                spot_type = 'amedas'
            elif name.startswith('R_'):
                spot_type = 'reference'
            else:
                spot_type = 'hoshiba'
            rows.append({
                'master_key': name,
                'spot_name': name,
                'spot_type': spot_type,
                'is_active': True,
                'is_protected': spot_type in ('amedas', 'reference'),
                'lat': _json_safe_value(spot.get('lat')),
                'lon': _json_safe_value(spot.get('lon')),
                'town': _json_safe_value(spot.get('town')),
                'district': _json_safe_value(spot.get('district')),
                'buraku': _json_safe_value(spot.get('buraku')),
                'synced_at_jst': synced_at,
            })
        return jsonify({
            'status': 'ok',
            'generated_at_jst': synced_at,
            'sync_mode': 'replace_current_snapshot',
            'columns': [
                'master_key', 'spot_name', 'spot_type', 'is_active', 'is_protected',
                'lat', 'lon', 'town', 'district', 'buraku', 'synced_at_jst',
            ],
            'summary': {
                'total': len(rows),
                'hoshiba': sum(1 for row in rows if row['spot_type'] == 'hoshiba'),
                'special_points': sum(1 for row in rows if row['spot_type'] != 'hoshiba'),
            },
            'rows': rows,
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/spots')
def get_spots_legacy():
    """Legacy endpoint for /spots - redirects to /api/spots"""
    return get_spots()

@app.route('/favorites')
def get_favorites():
    """Get favorites data - placeholder endpoint"""
    return jsonify([])

@app.route('/forecast')
def get_forecast_legacy():
    """Legacy endpoint for /forecast - redirects to /api/forecast"""
    return get_forecast()

def _sanitize_csv_field(value) -> str:
    """
    CSVインジェクション対策: 改行・NULLバイトを除去し最大100文字に制限。
    カンマはPandasのCSV書き込み時に自動クォートされるため除去不要。
    """
    return str(value or '').replace('\r', '').replace('\n', ' ').replace('\x00', '')[:100]


@app.route('/add', methods=['POST'])
def add_spot():
    """新規干場を追加"""
    try:
        data = request.get_json()
        lat = float(data.get("lat", 0))
        lon = float(data.get("lon", 0))

        # 地形・標高制限チェック
        terrain_check = validate_terrain_for_spot(lat, lon)
        if not terrain_check["valid"]:
            return jsonify({"status": "error", "message": terrain_check["message"]}), 400

        # 重複チェック（命名規則による）
        name = generate_spot_name(lat, lon)

        # M-4: ユーザー入力をサニタイズしてCSVインジェクションを防ぐ
        town     = _sanitize_csv_field(data.get("town", ""))
        district = _sanitize_csv_field(data.get("district", ""))
        buraku   = _sanitize_csv_field(data.get("buraku", ""))

        new_row = pd.DataFrame([{
            "name": name,
            "lat": lat,
            "lon": lon,
            "town": town,
            "district": district,
            "buraku": buraku
        }])

        # Read existing data
        try:
            df = pd.read_csv(CSV_FILE)
        except FileNotFoundError:
            # Create new CSV if it doesn't exist
            df = pd.DataFrame(columns=["name", "lat", "lon", "town", "district", "buraku"])

        if name in df["name"].values:
            return jsonify({"status": "error", "message": "同じ座標の干場が既に存在します"})

        # Add new spot
        df = pd.concat([df, new_row], ignore_index=True)
        df.to_csv(CSV_FILE, index=False, encoding="utf-8")

        # 4ファイル自動同期: KMLとJSファイルも更新
        sync_result = sync_all_files_from_csv()

        sync_ok = sync_result.get("kml") and sync_result.get("js")
        http_code = 200 if sync_ok else 207  # 207: 干場追加は成功だが同期に一部失敗
        response_body = {
            "status": "success",
            "message": "新しい干場が追加されました（4ファイル同期完了）" if sync_ok else "干場は追加されましたが、一部のファイル同期に失敗しました",
            "spot": {
                "name": name,
                "lat": lat,
                "lon": lon,
                "town": town,
                "district": district,
                "buraku": buraku
            },
            "sync_status": sync_result
        }
        return jsonify(response_body), http_code

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/delete', methods=['POST'])
def delete_spot():
    """
    干場を削除（制限付き削除）

    削除不可条件（3条件）:
    1. 記録データが存在する場合（hoshiba_records.csv）
    2. LINE通知に登録中のユーザーがいる場合（Upstash Redis）
    3. 同時編集ロックがかかっている場合（edit_locks/, 5分間）
    """
    try:
        data = request.get_json()
        name = data.get("name")

        if not name:
            return jsonify({"status": "error", "message": "干場名が指定されていません"}), 400

        # 特別地点の削除禁止（アメダス観測点・基準点）
        PROTECTED_SPOTS = ['A_1783_1383', 'A_2417_1867', 'R_1800_2392']
        if name in PROTECTED_SPOTS:
            spot_descriptions = {
                'A_1783_1383': 'アメダス沓形（公式観測点）',
                'A_2417_1867': 'アメダス本泊（公式観測点）',
                'R_1800_2392': '利尻山頂（基準点）'
            }
            return jsonify({
                "status": "error",
                "message": f"この地点は{spot_descriptions[name]}のため削除できません",
                "restriction_type": "protected_reference_point"
            }), 403

        # Read existing spot data
        try:
            df = pd.read_csv(CSV_FILE)
        except FileNotFoundError:
            return jsonify({"status": "error", "message": "データファイルが見つかりません"}), 404

        if name not in df["name"].values:
            return jsonify({"status": "error", "message": "指定された干場が見つかりません"}), 404

        # 制限1 & 5 / 制限3: 全ブロック理由を先にまとめて収集し、一括で返す
        block_reasons = []

        # 制限1: 記録データ存在チェック（機械学習訓練データとしても使用）
        try:
            records_df = pd.read_csv(RECORD_FILE)
            if name in records_df["name"].values:
                block_reasons.append("乾燥記録がある")
        except FileNotFoundError:
            pass

        # 制限2: お気に入り登録チェック（v2.6.5でお気に入り機能廃止済み・条件は削除）

        # 制限3: LINE通知登録チェック（v2.6.5以降、通知はLINEに一本化）
        try:
            from line_integration import load_subscriptions
            subs = load_subscriptions()
            for _sub_key, sub in subs.items():
                if not sub.get('notify_enabled'):
                    continue
                registered = sub.get('spots', [])
                nicknames = sub.get('spot_nicknames', {})
                if name in registered or name in nicknames.values():
                    block_reasons.append("LINE通知に登録しているユーザーがいる")
                    break
        except Exception:
            # LINE連携未設定・Upstash接続失敗時は安全側に倒してスキップ
            pass

        if block_reasons:
            reason_text = "・" + "\n・".join(block_reasons)
            return jsonify({
                "status": "error",
                "message": f"この干場は削除できません。\n\n理由：\n{reason_text}",
                "restriction_type": "blocked",
                "block_reasons": block_reasons,
            }), 403

        # 制限4: 同時編集ロックチェック（簡易版）
        import os
        from datetime import datetime, timedelta
        lock_file = os.path.join(LOCK_DIR, f"edit_lock_{name}.tmp")

        if os.path.exists(lock_file):
            # ロックファイルの更新時刻を確認
            lock_time = datetime.fromtimestamp(os.path.getmtime(lock_file), tz=JST)
            if datetime.now(tz=JST) - lock_time < timedelta(minutes=5):
                return jsonify({
                    "status": "error",
                    "message": "他のユーザーが同じ干場を編集中です。しばらく時間を置いてから再度お試しください。",
                    "restriction_type": "edit_locked"
                }), 423  # HTTP 423 Locked
            else:
                # 5分以上経過したロックファイルは削除
                try:
                    os.remove(lock_file)
                except:
                    pass

        # すべての制限をクリア - 削除実行
        df = df[df["name"] != name]
        df.to_csv(CSV_FILE, index=False, encoding="utf-8")

        # 4ファイル自動同期: KMLとJSファイルも更新
        sync_result = sync_all_files_from_csv()

        sync_ok = sync_result.get("kml") and sync_result.get("js")
        http_code = 200 if sync_ok else 207  # 207: 削除は成功だが同期に一部失敗
        return jsonify({
            "status": "success",
            "message": f"干場 {name} が削除されました（4ファイル同期完了）" if sync_ok else f"干場 {name} は削除されましたが、一部のファイル同期に失敗しました",
            "sync_status": sync_result
        }), http_code

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

RECORD_COLUMNS = ["date", "name", "result", "stop_cause", "did_dry",
                  "collection_time", "recorded_at", "correction_count", "correction_reason"]

VALID_RESULTS = ["完全乾燥", "概ね乾燥", "半乾燥", "ほぼ乾燥なし"]
VALID_STOP_CAUSES = ["雨が降った", "霧が出た・昆布が湿り戻った", "飛散リスク・強風",
                     "曇り続きで乾かなかった", "天候以外"]
VALID_CORRECTION_REASONS = ["記録の誤り（日付・干場の選択ミス）", "判断が変わった（再評価）", "その他"]

def merge_records_with_spots(records_df, spots_df):
    """
    hoshiba_records.csv と hoshiba_spots.csv を安全にマージする。

    - records 側: date, name, result のみ使用（余分カラムで _x/_y 衝突を防ぐ）
    - spots 側:   name, lat, lon, town, district, buraku のみ使用
    - validate="many_to_one" で spots の name 重複を検出
    - _merge != "both" の行が孤児レコード（spots に存在しない name）

    Returns:
        merged (DataFrame): left-joined DataFrame。
            '_merge' カラムで "both"/"left_only" を確認できる。
        orphans (DataFrame): spots に存在しない孤児レコードの部分集合。
    """
    rec_cols = [c for c in ['date', 'name', 'result'] if c in records_df.columns]
    spot_cols = [c for c in ['name', 'lat', 'lon', 'town', 'district', 'buraku'] if c in spots_df.columns]

    merged = pd.merge(
        records_df[rec_cols],
        spots_df[spot_cols],
        on='name',
        how='left',
        validate='many_to_one',
        indicator=True,
    )
    orphans = merged[merged['_merge'] != 'both'].copy()
    return merged, orphans

# ── 予報精度フィードバック ──────────────────────────────────────────────────────
FEEDBACK_FILE = os.path.join(BASE_DIR, "feedback_log.csv")
FEEDBACK_COLUMNS = [
    # ── キー ──────────────────────────────────────────────────────────────
    "date",                     # 対象日 (YYYY-MM-DD)
    "spot_name",                # 干場名
    "days_ahead",               # 何日前に出した予報か (0=当日朝)
    "town",                     # 記録作成時点の町（削除後も履歴保持）
    "district",                 # 記録作成時点の地区
    "buraku",                   # 記録作成時点の部落
    # ── 実測降水量（Open-Meteo Archive / 沓形局基準）────────────────────
    "actual_precip_0416_mm",    # 04:00-16:00 実測降水量合計 (mm)
    "actual_precip_total_mm",   # 全日 実測降水量合計 (mm)
    "actual_rain_0416",         # 04:00-16:00 に降水あり (True/False)
    # ── 予報降水量 ────────────────────────────────────────────────────────
    "forecast_precip_mm",       # 予報降水量・全日 (mm)
    "forecast_rain",            # 予報で降水あり (True/False)
    # ── 降水予報正誤 ──────────────────────────────────────────────────────
    "precip_forecast_correct",  # 降水有無の二値判定が合っていたか (True/False)
    # ── 乾燥スコア系 ──────────────────────────────────────────────────────
    "forecast_score",           # 予報乾燥スコア
    "forecast_suitability",     # excellent/good/fair/poor
    "forecast_label",           # 可/不可
    # ── 干し記録（ユーザー入力、任意）────────────────────────────────────
    "actual_result",            # 完全乾燥/概ね乾燥/不可 etc.
    "actual_label",             # 可/不可
    "judgment_correct",         # 乾燥可否の判定正誤 (True/False)
    "has_drying_record",        # 干し記録があるか (True/False)
    # ── メタデータ ────────────────────────────────────────────────────────
    "data_source",              # openmeteo_archive / jma_realtime
    "recorded_at",              # ログ追記日時
]


def _load_spot_metadata_map() -> dict:
    """Load current spot classifications keyed by spot name."""
    if not os.path.exists(CSV_FILE):
        return {}
    try:
        spots_df = pd.read_csv(CSV_FILE)
        result = {}
        for _, row in spots_df.iterrows():
            name = row.get('name')
            if not name:
                continue
            result[str(name)] = {
                'town': _json_safe_value(row.get('town')),
                'district': _json_safe_value(row.get('district')),
                'buraku': _json_safe_value(row.get('buraku')),
            }
        return result
    except Exception as exc:
        app.logger.warning('[spot_metadata] load failed: %s', exc)
        return {}

def _result_to_label(result):
    """乾燥記録結果 → 二値ラベル（可/不可）"""
    return "可" if result in ("完全乾燥", "概ね乾燥") else "不可"

def _suitability_to_label(suitability):
    """予報 suitability → 二値ラベル（可/不可）"""
    return "可" if suitability in ("excellent", "good") else "不可"


def _json_safe_value(value):
    """Convert pandas/numpy scalar values to JSON-safe primitives."""
    if pd.isna(value):
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float, str)):
        return value
    return str(value)


def _load_feedback_sheet_rows(days_back: int = 90, spot_name: str | None = None,
                              has_record: str | None = None) -> tuple[list[dict], dict]:
    """Return feedback_log.csv as flat rows for n8n / Google Sheets ingestion."""
    if not os.path.exists(FEEDBACK_FILE):
        return [], {
            'total_rows': 0,
            'note': 'feedback_log.csv not found yet',
        }

    fb_df = pd.read_csv(FEEDBACK_FILE)
    for col in FEEDBACK_COLUMNS:
        if col not in fb_df.columns:
            fb_df[col] = None

    bool_columns = [
        'actual_rain_0416', 'forecast_rain', 'precip_forecast_correct',
        'judgment_correct', 'has_drying_record',
    ]
    for col in bool_columns:
        fb_df[col] = fb_df[col].map({
            True: True, False: False,
            'True': True, 'False': False,
            'true': True, 'false': False,
            '1': True, '0': False,
            1: True, 0: False,
        })

    fb_df['date'] = pd.to_datetime(fb_df['date'], errors='coerce')
    cutoff = datetime.now(tz=JST).date() - timedelta(days=days_back)
    fb_df = fb_df[fb_df['date'].dt.date >= cutoff].copy()

    if spot_name:
        fb_df = fb_df[fb_df['spot_name'] == spot_name].copy()

    if has_record in ('true', '1', 'yes'):
        fb_df = fb_df[fb_df['has_drying_record'] == True].copy()
    elif has_record in ('false', '0', 'no'):
        fb_df = fb_df[fb_df['has_drying_record'] == False].copy()

    if os.path.exists(CSV_FILE):
        try:
            spots_df = pd.read_csv(CSV_FILE)[['name', 'town', 'district', 'buraku']]
            spots_df.rename(columns={
                'town': 'current_town',
                'district': 'current_district',
                'buraku': 'current_buraku',
            }, inplace=True)
            fb_df = fb_df.merge(spots_df, left_on='spot_name', right_on='name', how='left')
            fb_df.drop(columns=['name'], inplace=True, errors='ignore')
            for col in ('town', 'district', 'buraku'):
                current_col = f'current_{col}'
                fb_df[col] = fb_df[col].combine_first(fb_df[current_col])
                fb_df.drop(columns=[current_col], inplace=True, errors='ignore')
        except Exception as exc:
            app.logger.warning('[accuracy_sheets] spot metadata merge failed: %s', exc)
            for col in ('town', 'district', 'buraku'):
                if col not in fb_df.columns:
                    fb_df[col] = None

    fb_df['date'] = fb_df['date'].dt.strftime('%Y-%m-%d')
    fb_df.sort_values(['date', 'spot_name', 'days_ahead'], inplace=True)

    sheet_columns = [
        'upsert_key',
        'date', 'spot_name', 'town', 'district', 'buraku', 'days_ahead',
        'actual_precip_0416_mm', 'actual_precip_total_mm', 'actual_rain_0416',
        'forecast_precip_mm', 'forecast_rain', 'precip_forecast_correct',
        'forecast_score', 'forecast_suitability', 'forecast_label',
        'actual_result', 'actual_label', 'judgment_correct',
        'has_drying_record', 'data_source', 'recorded_at',
    ]
    for col in sheet_columns:
        if col not in fb_df.columns:
            fb_df[col] = None

    fb_df['upsert_key'] = (
        fb_df['date'].fillna('').astype(str) + '|' +
        fb_df['spot_name'].fillna('').astype(str) + '|' +
        fb_df['days_ahead'].fillna('').astype(str)
    )

    rows = [
        {col: _json_safe_value(row[col]) for col in sheet_columns}
        for _, row in fb_df[sheet_columns].iterrows()
    ]

    def _rate(series):
        valid = series.dropna()
        if valid.empty:
            return None
        return round(float(valid.mean()) * 100, 1)

    summary = {
        'total_rows': len(rows),
        'days_back': days_back,
        'spot': spot_name or 'all',
        'has_record_filter': has_record or 'all',
        'precip_hit_rate_pct': _rate(fb_df['precip_forecast_correct']),
        'judgment_hit_rate_pct': _rate(fb_df['judgment_correct']),
        'drying_record_rows': int((fb_df['has_drying_record'] == True).sum()),
    }
    return rows, summary


@app.route('/api/validation/accuracy/sheets')
def get_accuracy_for_sheets():
    """Flat forecast accuracy rows for n8n -> Google Sheets visualization."""
    try:
        days_back = min(max(int(request.args.get('days', 90)), 1), 365)
        spot_name = request.args.get('spot') or None
        has_record = request.args.get('has_record')
        rows, summary = _load_feedback_sheet_rows(days_back, spot_name, has_record)
        return jsonify({
            'status': 'ok',
            'generated_at_jst': datetime.now(tz=JST).strftime('%Y-%m-%dT%H:%M:%S+09:00'),
            'columns': [
                'upsert_key',
                'date', 'spot_name', 'town', 'district', 'buraku', 'days_ahead',
                'actual_precip_0416_mm', 'actual_precip_total_mm', 'actual_rain_0416',
                'forecast_precip_mm', 'forecast_rain', 'precip_forecast_correct',
                'forecast_score', 'forecast_suitability', 'forecast_label',
                'actual_result', 'actual_label', 'judgment_correct',
                'has_drying_record', 'data_source', 'recorded_at',
            ],
            'summary': summary,
            'rows': rows,
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


def _pct(series):
    valid = series.dropna()
    if valid.empty:
        return None
    return round(float(valid.mean()) * 100, 1)


def _count_true(series):
    valid = series.dropna()
    if valid.empty:
        return 0
    return int((valid == True).sum())


def _build_accuracy_summary_tables(rows: list[dict]) -> dict:
    """Build chart-ready summary tables from flat feedback rows."""
    if not rows:
        return {
            'by_day': [],
            'by_days_ahead': [],
            'by_area': [],
            'by_buraku': [],
        }

    df = pd.DataFrame(rows)

    def summarize(group_cols):
        table = []
        for keys, group in df.groupby(group_cols, dropna=False):
            if not isinstance(keys, tuple):
                keys = (keys,)
            row = {col: _json_safe_value(val) for col, val in zip(group_cols, keys)}
            row['summary_key'] = '|'.join('' if val is None else str(val) for val in keys)
            row.update({
                'rows': int(len(group)),
                'drying_record_rows': _count_true(group['has_drying_record']),
                'precip_hit_rate_pct': _pct(group['precip_forecast_correct']),
                'judgment_hit_rate_pct': _pct(group['judgment_correct']),
                'avg_forecast_score': (
                    round(float(pd.to_numeric(group['forecast_score'], errors='coerce').mean()), 1)
                    if pd.to_numeric(group['forecast_score'], errors='coerce').notna().any()
                    else None
                ),
                'false_positive_count': int(
                    ((group['forecast_label'] == '可') & (group['actual_label'] == '不可')).sum()
                ),
                'false_negative_count': int(
                    ((group['forecast_label'] == '不可') & (group['actual_label'] == '可')).sum()
                ),
            })
            table.append(row)
        return table

    return {
        'by_day': summarize(['date']),
        'by_days_ahead': summarize(['days_ahead']),
        'by_area': summarize(['town', 'district']),
        'by_buraku': summarize(['town', 'district', 'buraku']),
    }


@app.route('/api/validation/accuracy/sheets/summary')
def get_accuracy_sheet_summaries():
    """Chart-ready summary rows for n8n -> Google Sheets dashboard tabs."""
    try:
        days_back = min(max(int(request.args.get('days', 90)), 1), 365)
        spot_name = request.args.get('spot') or None
        has_record = request.args.get('has_record')
        rows, source_summary = _load_feedback_sheet_rows(days_back, spot_name, has_record)
        tables = _build_accuracy_summary_tables(rows)
        return jsonify({
            'status': 'ok',
            'generated_at_jst': datetime.now(tz=JST).strftime('%Y-%m-%dT%H:%M:%S+09:00'),
            'source_summary': source_summary,
            'tables': tables,
            'recommended_sheet_tabs': [
                'raw_feedback',
                'summary_by_day',
                'summary_by_days_ahead',
                'summary_by_area',
                'summary_by_buraku',
            ],
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


def _record_forecast_feedback(name, date_str, result):
    """
    記録追加・更新のたびに呼び出す。
    forecast_history/{name}/ から対象日の予報ファイルを検索し、
    予報判定と実結果の正誤を feedback_log.csv に記録する。
    記録が訂正された場合は既存行を上書きする。
    """
    try:
        import glob as _glob
        from datetime import datetime as _dt, timezone as _tz2, timedelta as _td2

        target_date_str = date_str.replace('-', '')
        spot_dir = os.path.join(FORECAST_HISTORY_DIR, name)
        fc_files = _glob.glob(os.path.join(spot_dir, f'forecast_*_for_{target_date_str}.json'))

        if not fc_files:
            return  # 予報履歴なし → フィードバック不可

        actual_label = _result_to_label(result)
        jst = _tz2(_td2(hours=9))
        now_jst = _dt.now(jst).strftime("%Y-%m-%dT%H:%M:%S+09:00")
        spot_meta = _load_spot_metadata_map().get(name, {})

        # 既存フィードバックログを読み込み
        try:
            fb_df = pd.read_csv(FEEDBACK_FILE)
            for col in FEEDBACK_COLUMNS:
                if col not in fb_df.columns:
                    fb_df[col] = None
        except FileNotFoundError:
            fb_df = pd.DataFrame(columns=FEEDBACK_COLUMNS)

        new_rows = []
        for fc_file in fc_files:
            try:
                with open(fc_file, 'r', encoding='utf-8') as f:
                    fc_data = json.load(f)

                forecast_date_str = fc_data.get('forecast_date', '')
                if not forecast_date_str:
                    continue

                try:
                    fc_dt = _dt.strptime(forecast_date_str, '%Y%m%d')
                    tg_dt = _dt.strptime(target_date_str, '%Y%m%d')
                    days_ahead = (tg_dt - fc_dt).days
                except ValueError:
                    days_ahead = None

                fc_score  = fc_data.get('drying_score')
                fc_suit   = fc_data.get('suitability', '')
                # precipitation_0416（04:00-16:00積算）を優先。旧データは24時間積算で代替
                fc_precip = fc_data.get('precipitation_0416', fc_data.get('precipitation')) or 0.0
                fc_label  = _suitability_to_label(fc_suit)
                correct   = (actual_label == fc_label)

                # 同一 date + spot_name + days_ahead の行は上書き（訂正対応）
                mask = (
                    (fb_df['date'] == date_str) &
                    (fb_df['spot_name'] == name) &
                    (fb_df['days_ahead'] == days_ahead)
                )
                if mask.any():
                    # 干し記録フィールドのみ更新（降水照合フィールドは _auto_compare が担当）
                    fb_df.loc[mask, 'actual_result']    = result
                    fb_df.loc[mask, 'actual_label']     = actual_label
                    fb_df.loc[mask, 'judgment_correct'] = correct
                    fb_df.loc[mask, 'has_drying_record'] = True
                    fb_df.loc[mask, 'recorded_at']      = now_jst
                    for meta_col in ('town', 'district', 'buraku'):
                        if spot_meta.get(meta_col) is not None:
                            fb_df.loc[mask, meta_col] = spot_meta[meta_col]
                else:
                    new_rows.append({
                        'date':                  date_str,
                        'spot_name':             name,
                        'days_ahead':            days_ahead,
                        'town':                  spot_meta.get('town'),
                        'district':              spot_meta.get('district'),
                        'buraku':                spot_meta.get('buraku'),
                        'actual_result':         result,
                        'actual_label':          actual_label,
                        'forecast_score':        fc_score,
                        'forecast_suitability':  fc_suit,
                        'forecast_precip_mm':    fc_precip,
                        'forecast_rain':         fc_precip > 0.0,
                        'forecast_label':        fc_label,
                        'judgment_correct':      correct,
                        'has_drying_record':     True,
                        'recorded_at':           now_jst,
                    })
            except Exception as e:
                print(f'[feedback] parse error {fc_file}: {e}')

        if new_rows:
            fb_df = pd.concat([fb_df, pd.DataFrame(new_rows)], ignore_index=True)

        fb_df.to_csv(FEEDBACK_FILE, index=False, encoding='utf-8')
        print(f'[feedback] {name} {date_str} → {result} ({len(fc_files)} forecast(s) evaluated)')

    except Exception as e:
        print(f'[feedback] error: {e}')

# ──────────────────────────────────────────────────────────────────────────────

def _load_records():
    """hoshiba_records.csvを読み込み、旧カラム構造を自動移行して返す"""
    try:
        df = pd.read_csv(RECORD_FILE)
    except FileNotFoundError:
        return pd.DataFrame(columns=RECORD_COLUMNS)
    for col in RECORD_COLUMNS:
        if col not in df.columns:
            df[col] = None
    return df[RECORD_COLUMNS]

@app.route('/record', methods=['POST'])
def add_record():
    """記録を追加または更新（v2.6.0: 9カラム拡張版）"""
    try:
        data = request.get_json()
        name = data.get("name")
        date = data.get("date")
        result = data.get("result")
        stop_cause = data.get("stop_cause")
        did_dry = data.get("did_dry")
        collection_time = data.get("collection_time")
        correction_reason = data.get("correction_reason")

        if not all([name, date, result]):
            return jsonify({"status": "error", "message": "name, date, resultがすべて必要です"}), 400

        PROTECTED_SPOTS = ['A_1783_1383', 'A_2417_1867', 'R_1800_2392']
        if name in PROTECTED_SPOTS:
            spot_descriptions = {
                'A_1783_1383': 'アメダス沓形',
                'A_2417_1867': 'アメダス本泊',
                'R_1800_2392': '利尻山頂'
            }
            return jsonify({
                "status": "error",
                "message": f"{spot_descriptions[name]}は観測点であり干場ではないため、乾燥記録を登録できません"
            }), 400

        # hoshiba_spots.csv に存在しない干場名は拒否（孤児レコード生成防止）
        try:
            spots_df = pd.read_csv(CSV_FILE)
            if name not in spots_df['name'].values:
                return jsonify({
                    "status": "error",
                    "message": f"干場 '{name}' は存在しません。先に干場を登録してください。"
                }), 400
        except FileNotFoundError:
            return jsonify({"status": "error", "message": "干場データベースが見つかりません"}), 500

        if result not in VALID_RESULTS:
            return jsonify({"status": "error", "message": f"無効な記録結果です。有効値: {VALID_RESULTS}"}), 400

        if stop_cause is not None and stop_cause not in VALID_STOP_CAUSES:
            return jsonify({"status": "error", "message": f"無効な主因です。有効値: {VALID_STOP_CAUSES}"}), 400

        if correction_reason is not None and correction_reason not in VALID_CORRECTION_REASONS:
            return jsonify({"status": "error", "message": f"無効な訂正理由です。"}), 400

        from datetime import timezone as _tz, timedelta as _td
        jst = _tz(_td(hours=9))
        now_jst = datetime.now(jst).strftime("%Y-%m-%dT%H:%M:%S+09:00")

        df = _load_records()
        mask = (df["name"] == name) & (df["date"] == date)
        existing = df[mask]

        if len(existing) > 0:
            current_count = int(existing.iloc[0].get("correction_count") or 0)
            df.loc[mask, "result"] = result
            df.loc[mask, "stop_cause"] = stop_cause
            df.loc[mask, "did_dry"] = did_dry
            df.loc[mask, "collection_time"] = collection_time
            df.loc[mask, "recorded_at"] = now_jst
            df.loc[mask, "correction_count"] = current_count + 1
            df.loc[mask, "correction_reason"] = correction_reason
            message = f"記録が更新されました: {name} ({date}) - {result}"
        else:
            new_row = pd.DataFrame([{
                "date": date,
                "name": name,
                "result": result,
                "stop_cause": stop_cause,
                "did_dry": did_dry,
                "collection_time": collection_time,
                "recorded_at": now_jst,
                "correction_count": 0,
                "correction_reason": None
            }])
            df = pd.concat([df, new_row], ignore_index=True)
            message = f"記録が追加されました: {name} ({date}) - {result}"

        df.to_csv(RECORD_FILE, index=False, encoding="utf-8")

        # 予報精度フィードバックを自動記録（失敗してもメインの記録保存には影響しない）
        _record_forecast_feedback(name, date, result)

        return jsonify({"status": "success", "message": message})

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/record/<name>/<date>', methods=['GET'])
def get_record(name, date):
    """指定した干場・日付の記録を取得（v2.6.0: 全カラム返却）"""
    try:
        df = _load_records()
        existing = df[(df["name"] == name) & (df["date"] == date)]

        if len(existing) > 0:
            row = existing.iloc[0]
            def _val(v):
                import math
                if v is None:
                    return None
                try:
                    if math.isnan(float(v)):
                        return None
                except (TypeError, ValueError):
                    pass
                return v
            return jsonify({
                "exists": True,
                "record": {
                    "date": _val(row.get("date")),
                    "name": _val(row.get("name")),
                    "result": _val(row.get("result")),
                    "stop_cause": _val(row.get("stop_cause")),
                    "did_dry": _val(row.get("did_dry")),
                    "collection_time": _val(row.get("collection_time")),
                    "recorded_at": _val(row.get("recorded_at")),
                    "correction_count": int(row.get("correction_count") or 0),
                    "correction_reason": _val(row.get("correction_reason"))
                }
            })
        else:
            return jsonify({"exists": False})

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/terrain/<spot_name>')
def get_terrain_info(spot_name):
    """
    指定干場の地形情報を取得

    Returns terrain corrections and local geography for accurate forecasting
    """
    try:
        # Extract coordinates from spot name
        # Format: H_LLLL_NNNN -> 45.LLLL, 141.NNNN
        parts = spot_name.split('_')
        if len(parts) != 3 or parts[0] not in ('H', 'A', 'R'):
            return jsonify({"status": "error", "message": "無効な干場名形式"}), 400

        lat = 45.0 + float(parts[1]) / 10000.0
        lon = 141.0 + float(parts[2]) / 10000.0

        # Calculate terrain characteristics
        spot_theta = calculate_spot_theta(lat, lon)

        # Basic terrain analysis
        is_forest = is_forest_area(lat, lon)
        is_coastal = is_coastal_area(lat, lon)
        elevation = get_elevation(lat, lon)

        # Distance to coast (simplified)
        mountain_lat, mountain_lon = 45.1821, 141.2421
        distance_from_mountain = ((lat - mountain_lat) ** 2 + (lon - mountain_lon) ** 2) ** 0.5 * 111  # km

        # Terrain corrections
        corrections = {
            'wind_speed': 0.0,
            'humidity': 0.0,
            'temperature': 0.0
        }

        if is_forest:
            corrections['wind_speed'] = -2.5  # 森林効果: 風速減少
            corrections['humidity'] = 10.0    # 森林効果: 湿度増加

        if is_coastal:
            corrections['wind_speed'] = 1.0   # 海岸効果: 風速増加
            corrections['humidity'] = 5.0     # 海岸効果: 湿度増加

        if elevation > 10:
            corrections['temperature'] = -(elevation / 100) * 0.6  # 標高効果: 気温低下
            corrections['humidity'] = -(elevation / 100) * 1.0     # 標高効果: 湿度低下

        return jsonify({
            'status': 'success',
            'spot_name': spot_name,
            'coordinates': {'lat': lat, 'lon': lon},
            'theta': round(spot_theta, 1),
            'terrain': {
                'elevation': round(elevation, 1),
                'distance_from_mountain': round(distance_from_mountain, 2),
                'is_forest': is_forest,
                'is_coastal': is_coastal,
                'land_use': 'forest' if is_forest else ('coastal' if is_coastal else 'open')
            },
            'corrections': corrections,
            'description': generate_terrain_description(is_forest, is_coastal, elevation)
        })

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

def fetch_pressure_level_data(lat, lon, forecast_hours=384):
    """
    Open-Meteo Pressure Level APIから高層データを取得

    Parameters:
    - lat: 緯度
    - lon: 経度
    - forecast_hours: 予報時間（デフォルト384時間=16日間）

    Returns:
    - dict: 500hPa, 700hPa, 850hPaの気象データ
    """
    try:
        # Get elevation for accurate DEM correction
        elevation = get_elevation(lat, lon)

        # 16日間の高層データを取得
        forecast_days = min(16, (forecast_hours + 23) // 24)  # 時間を日数に変換（切り上げ）

        url = (
            f"https://api.open-meteo.com/v1/forecast?"
            f"latitude={lat}&longitude={lon}&elevation={elevation}&"
            f"hourly=temperature_200hPa,geopotential_height_200hPa,wind_speed_200hPa,wind_direction_200hPa,"
            f"temperature_300hPa,geopotential_height_300hPa,wind_speed_300hPa,wind_direction_300hPa,"
            f"temperature_500hPa,geopotential_height_500hPa,relative_humidity_500hPa,"
            f"wind_speed_500hPa,wind_direction_500hPa,"
            f"temperature_700hPa,geopotential_height_700hPa,relative_humidity_700hPa,"
            f"wind_speed_700hPa,wind_direction_700hPa,"
            f"temperature_850hPa,geopotential_height_850hPa,relative_humidity_850hPa,"
            f"wind_speed_850hPa,wind_direction_850hPa&"
            f"timezone=Asia/Tokyo&forecast_days={forecast_days}"
        )

        response = requests.get(url, timeout=15)
        response.raise_for_status()

        return response.json()

    except Exception as e:
        print(f"Error fetching pressure level data: {e}")
        return None

def fetch_marine_data(lat, lon, forecast_hours=168):
    """
    Open-Meteo Marine APIから海域データを取得

    Parameters:
    - lat: 緯度
    - lon: 経度
    - forecast_hours: 予報時間（デフォルト168時間=7日間）

    Returns:
    - dict: 有義波高、波向、波周期データ
    """
    try:
        # 7日間の海域データを取得
        forecast_days = min(7, (forecast_hours + 23) // 24)

        url = (
            f"https://marine-api.open-meteo.com/v1/marine?"
            f"latitude={lat}&longitude={lon}&"
            f"hourly=wave_height,wave_direction,wave_period&"
            f"timezone=Asia/Tokyo&forecast_days={forecast_days}"
        )

        response = requests.get(url, timeout=15)
        response.raise_for_status()

        return response.json()

    except Exception as e:
        print(f"Error fetching marine data: {e}")
        return None

# ---------------------------------------------------------------------------
# Analysis field API — island-wide distribution maps (replaces matplotlib PNG)
# ---------------------------------------------------------------------------
import math as _math

_analysis_field_cache: dict = {}
_FIELD_CACHE_TTL = 3600  # 60 min TTL
_ALLOWED_HOURS = [4, 7, 10, 13, 16]  # JST hours allowed for non-score field types

# Redis helpers for field cache (Upstash REST API).
# Falls back silently to in-memory when Upstash env vars are absent.
_FC_KEY_PREFIX = 'fc:'


def _fc_redis_get(key: str):
    """Fetch JSON value from Upstash Redis via REST GET. Returns None on any error."""
    rest_url = os.environ.get('UPSTASH_REDIS_REST_URL', '').strip().rstrip('/')
    token    = os.environ.get('UPSTASH_REDIS_REST_TOKEN', '')
    if not rest_url or not token:
        return None
    try:
        resp = requests.get(
            f'{rest_url}/get/{_FC_KEY_PREFIX}{key}',
            headers={'Authorization': f'Bearer {token}'},
            timeout=2,
        )
        result = resp.json().get('result')
        if result is None:
            return None
        return json.loads(result)
    except Exception:
        return None


def _fc_redis_set(key: str, data, ttl: int) -> bool:
    """Store JSON value in Upstash Redis with EX TTL. Returns True on success."""
    rest_url = os.environ.get('UPSTASH_REDIS_REST_URL', '').strip().rstrip('/')
    token    = os.environ.get('UPSTASH_REDIS_REST_TOKEN', '')
    if not rest_url or not token:
        return False
    try:
        payload = json.dumps(data, ensure_ascii=False)
        resp = requests.post(
            f'{rest_url}/set/{_FC_KEY_PREFIX}{key}',
            headers={'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'},
            json=['EX', ttl, payload],
            timeout=2,
        )
        # Upstash REST SET with EX uses pipeline-style: POST /set/KEY ["EX", N, "value"]
        return resp.status_code == 200
    except Exception:
        return False


# ── 観測データ・ナウキャスト永続化用 Redis（prefix なし、90日TTL） ────────────
_OBS_KEY_TTL = 90 * 24 * 3600  # 90日 = 7,776,000 秒


def _obs_redis_get(key: str):
    """観測データ/ナウキャスト用 Redis GET（_FC_KEY_PREFIX なし）。"""
    rest_url = os.environ.get('UPSTASH_REDIS_REST_URL', '').strip().rstrip('/')
    token    = os.environ.get('UPSTASH_REDIS_REST_TOKEN', '')
    if not rest_url or not token:
        return None
    try:
        resp = requests.get(
            f'{rest_url}/get/{key}',
            headers={'Authorization': f'Bearer {token}'},
            timeout=3,
        )
        result = resp.json().get('result')
        return json.loads(result) if result else None
    except Exception:
        return None


def _obs_redis_set(key: str, data, ttl: int = _OBS_KEY_TTL) -> bool:
    """観測データ/ナウキャスト用 Redis SET EX（pipeline API経由）。"""
    rest_url = os.environ.get('UPSTASH_REDIS_REST_URL', '').strip().rstrip('/')
    token    = os.environ.get('UPSTASH_REDIS_REST_TOKEN', '')
    if not rest_url or not token:
        return False
    try:
        payload = json.dumps(data, ensure_ascii=False)
        resp = requests.post(
            f'{rest_url}/pipeline',
            headers={'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'},
            json=[['SET', key, payload, 'EX', ttl]],
            timeout=5,
        )
        results = resp.json()
        return isinstance(results, list) and bool(results) and results[0].get('result') == 'OK'
    except Exception:
        return False


def _obs_redis_scan_keys(pattern: str) -> list:
    """Upstash REST SCAN でパターンに一致するキーを全件返す（ページング対応）。"""
    rest_url = os.environ.get('UPSTASH_REDIS_REST_URL', '').strip().rstrip('/')
    token    = os.environ.get('UPSTASH_REDIS_REST_TOKEN', '')
    if not rest_url or not token:
        return []
    keys   = []
    cursor = '0'
    try:
        while True:
            resp = requests.get(
                f'{rest_url}/scan/{cursor}',
                headers={'Authorization': f'Bearer {token}'},
                params={'match': pattern, 'count': '500'},
                timeout=5,
            )
            result = resp.json().get('result', ['0', []])
            cursor = str(result[0])
            keys.extend(result[1] if len(result) > 1 else [])
            if cursor == '0':
                break
    except Exception:
        pass
    return keys


def _field_cache_get(key: str):
    """Hybrid cache read: Redis primary → in-memory fallback."""
    # 1. Try Redis (shared across workers)
    redis_val = _fc_redis_get(key)
    if redis_val is not None:
        # Warm local memory cache for same-process subsequent calls
        _analysis_field_cache[key] = {
            'data': redis_val,
            'expires': datetime.now(JST) + timedelta(seconds=_FIELD_CACHE_TTL),
        }
        return redis_val
    # 2. Local in-memory fallback
    now = datetime.now(JST)
    entry = _analysis_field_cache.get(key)
    if entry and now < entry['expires']:
        return entry['data']
    _analysis_field_cache.pop(key, None)
    return None


def _field_cache_set(key: str, data, ttl: int = _FIELD_CACHE_TTL):
    """Hybrid cache write: Redis primary + in-memory."""
    # 1. Write to Redis (best-effort; errors are swallowed)
    _fc_redis_set(key, data, ttl)
    # 2. Always write to local memory (fast same-process reads)
    _analysis_field_cache[key] = {
        'data': data,
        'expires': datetime.now(JST) + timedelta(seconds=ttl),
    }


def _load_all_spots_for_field() -> list:
    """Load all 334 spots from CSV for field analysis."""
    spots = []
    try:
        import csv as _csv
        with open(CSV_FILE, 'r', encoding='utf-8') as f:
            reader = _csv.DictReader(f)
            for row in reader:
                try:
                    spots.append({
                        'name':     row['name'],
                        'lat':      float(row['lat']),
                        'lon':      float(row['lon']),
                        'town':     row.get('town', ''),
                        'district': row.get('district', ''),
                        'buraku':   row.get('buraku', ''),
                    })
                except (ValueError, KeyError):
                    continue
    except Exception as e:
        print(f'[field] _load_all_spots error: {e}')
    return spots


_grid_bounds_cache: dict = {}   # process-lifetime cache; cleared on first call


def _compute_grid_bounds() -> dict:
    """Return lat/lon bounds for the representative grid.

    Algorithm:
        1. Read hoshiba_spots.csv (CSV_FILE) and compute min/max of all spots.
        2. Add MARGIN_LAT / MARGIN_LON on each edge.
        3. Clamp to SAFETY_* limits (generous Rishiri Island outer envelope).
        4. Cache the result for the process lifetime.
           – If spots are added well outside the current extent, a server restart
             will pick up the new bounds automatically.
        5. Fall back to known Rishiri Island bounds if CSV is unavailable.
    """
    global _grid_bounds_cache
    if _grid_bounds_cache:
        return _grid_bounds_cache

    MARGIN_LAT   = 0.03   # ≈ 3.3 km north/south buffer
    MARGIN_LON   = 0.02   # ≈ 1.6 km east/west buffer
    # Safety limits: outer envelope of Rishiri Island (never go beyond here)
    SAFETY_LAT_MIN, SAFETY_LAT_MAX = 44.95, 45.40
    SAFETY_LON_MIN, SAFETY_LON_MAX = 141.05, 141.50

    try:
        import csv as _csv
        lats, lons = [], []
        with open(CSV_FILE, newline='', encoding='utf-8') as f:
            for row in _csv.DictReader(f):
                try:
                    lats.append(float(row['lat']))
                    lons.append(float(row['lon']))
                except (KeyError, ValueError):
                    continue

        if lats and lons:
            lat_min = max(SAFETY_LAT_MIN, min(lats) - MARGIN_LAT)
            lat_max = min(SAFETY_LAT_MAX, max(lats) + MARGIN_LAT)
            lon_min = max(SAFETY_LON_MIN, min(lons) - MARGIN_LON)
            lon_max = min(SAFETY_LON_MAX, max(lons) + MARGIN_LON)
            _grid_bounds_cache = {
                'lat_min': lat_min, 'lat_max': lat_max,
                'lon_min': lon_min, 'lon_max': lon_max,
                'source': 'csv',
                'n_spots': len(lats),
            }
            print(f'[grid] bounds from CSV ({len(lats)} spots): '
                  f'lat {lat_min:.4f}–{lat_max:.4f}, lon {lon_min:.4f}–{lon_max:.4f}')
            return _grid_bounds_cache

    except Exception as e:
        print(f'[grid] CSV bounds failed ({e}); using fallback')

    # Fallback: Rishiri Island known full extent + margin
    # (covers lat 45.0976–45.2582, lon 141.1317–141.3283 as of 334-spot CSV)
    _grid_bounds_cache = {
        'lat_min': 45.07, 'lat_max': 45.27,
        'lon_min': 141.12, 'lon_max': 141.35,
        'source': 'fallback',
        'n_spots': 0,
    }
    print('[grid] bounds: using fallback (Rishiri Island known extent)')
    return _grid_bounds_cache


def _build_rishiri_grid() -> list:
    """利尻島の島内分布グリッドを生成。

    【構成: 利尻山頂 + 二重リング = 49点】
    - 利尻山頂 1点 (中心) ── 山頂の気象を基準として可視化
    - 内リング 24点: 方位 0°/15°/.../345° (15°刻み) ── 半径は方位別に異なる（下記）
    - 外リング 24点: r=8km, 方位 7.5°/22.5°/.../352.5° (内リングと7.5°ずれで千鳥配置)

    【内リング半径の方位別設計】
    利尻山頂 (45.1800N, 141.2392E) は島の「東寄り」に位置する。
    このため、北東・東方向の海岸は5.8〜7.5km（山頂に近い）、
    西・北西・南方向の海岸は7.1〜9.4km（遠い）と非対称になる。

    実測データ（331干場）に基づく各方向の平均沿岸距離と内リング半径の割り当て:
      北:6.9km / 北東:6.2km / 東:6.6km          → r=6km  (i=0〜8,  0°〜120°)
      南東:7.7km / 南2,3:8.3km / 南西:7.4km / 西1,2:8.0km → r=7km  (i=9〜11, i=13〜19, 135°〜285°)
      真南:8.3km(max 9.1km)                     → r=9km  (i=12, 180°)
      西3:8.0km / 北西:8.8km(max 9.4km)         → r=9km  (i=20〜23, 300°〜345°)

    座標計算
    ----------
    中心: 利尻山頂 (45.1800N, 141.2392E) — onshore/foehn計算と同じ基準点
    LAT_D = 1/111.0 °/km
    LON_D = 1/(111.0×cos(45.18°)) °/km  ≈ 1/78.5 °/km
    方位: 北=0°、時計回り（気象学的方位角と同一）

    ラベル規則 (8方位 × 3サブ = 24点/リング)
    ----------
    内リング: 内北1 / 内北2 / 内北3 / 内北東1 ... 内北西3  (半径はラベルに反映しない)
    外リング: 外北1 / 外北2 / 外北3 / 外北東1 ... 外北西3
    山頂:     利尻山頂
    """
    import math as _m

    _CLAT  = 45.1800
    _CLON  = 141.2392
    _LAT_D = 1.0 / 111.0
    _LON_D = 1.0 / (111.0 * _m.cos(_m.radians(_CLAT)))

    _C8 = ['北', '北東', '東', '南東', '南', '南西', '西', '北西']

    def _pt(bearing_deg, radius_km, label):
        _brad = _m.radians(bearing_deg)
        return {
            'lat':     round(_CLAT + radius_km * _LAT_D * _m.cos(_brad), 4),
            'lon':     round(_CLON + radius_km * _LON_D * _m.sin(_brad), 4),
            'bearing': bearing_deg,
            'radius':  radius_km,
            'label':   label,
        }

    _grid = [
        # ── 山頂 (中心) ─────────────────────────────────────────────────────
        {'lat': _CLAT, 'lon': _CLON, 'bearing': None, 'radius': 0, 'label': '利尻山頂'},
    ]

    # ── 内リング: 方位別半径 ────────────────────────────────────────────────
    # r=6km: i=0〜7  (0°〜105°, 北/北東/東1-2) — 東寄り海岸線(avg 6.2〜6.9km)に合わせる
    # r=9km: i=12   (180°, 真南)              — 南avg 8.3km, max 9.1km
    # r=9km: i=20〜23 (300°〜345°, 内西3〜北西) — 北西avg 8.8km, max 9.4km
    # r=7km: それ以外 (内東3=120°/南東/南2,3/南西/西) — i=8(120°)は南東境界のため7kmに戻す
    for _i in range(24):
        _bdeg = 15.0 * _i
        if _i <= 7:
            _r = 6.0                       # 北/北東/東1-2(0°〜105°): 東寄り近い海岸
        elif _i == 12 or _i >= 20:
            _r = 9.0                       # 真南(180°)・北西〜北北西(300°〜345°): 遠い海岸
        else:
            _r = 7.0                       # 内東3(120°)含む南東〜西: 中間帯
        _lbl  = f'内{_C8[_i // 3]}{(_i % 3) + 1}'
        _grid.append(_pt(_bdeg, _r, _lbl))

    # ── 外リング: 方位別半径, 7.5°, 22.5°, ..., 352.5° ──────────────────────
    # r=7km: i=0〜6 (7.5°〜97.5°, 外北1〜外東1) — N/NE/E海岸はavg6.2〜6.9km,max6.6〜7.5km
    #                                              8kmは沖合に出すぎのため7kmへ
    # r=8km: それ以外 — 南/西/北西は海岸が遠い(avg7.4〜8.8km)
    for _i in range(24):
        _bdeg = 15.0 * _i + 7.5
        _r    = 7.0 if _i <= 6 else 8.0
        _lbl  = f'外{_C8[_i // 3]}{(_i % 3) + 1}'
        _grid.append(_pt(_bdeg, _r, _lbl))

    return _grid


def _fetch_elevations_batch(lats: list, lons: list) -> list:
    """
    Open-Meteo Elevation API で複数地点の標高を一括取得（単一HTTPリクエスト）。

    _compute_score_field() から呼び出すことで、個別の get_elevation() を
    48回（48×~1.5s ≈ 72s）呼ぶ代わりに1回のリクエスト（~2s）で済む。

    Returns:
        各地点の標高(m)リスト。長さは常に len(lats) と一致する。
        失敗・欠損・型エラーがあった要素は個別に 0.0 で補完し、
        呼び出し元が IndexError / TypeError で落ちないことを保証する。

    Fallback:
        - API通信失敗 / タイムアウト → 全点 0.0（警告をログ出力）
        - API応答の配列長がlats長より短い → 不足分を 0.0 で補完
        - 個別要素が None / 非数値 → その点を 0.0 で補完
        ※ elevation=0 は「標高0m（海面付近）」として正しく扱われ、
          None とは区別される（calculate_enhanced_drying_score の `if elevation is None:` 分岐参照）
    """
    n = len(lats)
    try:
        lat_str = ','.join(f'{lat:.4f}' for lat in lats)
        lon_str = ','.join(f'{lon:.4f}' for lon in lons)
        url = f'https://api.open-meteo.com/v1/elevation?latitude={lat_str}&longitude={lon_str}'
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        raw = data.get('elevation', [])

        # 長さ不一致・個別欠損をすべて安全に補完
        result: list = []
        missing = 0
        for i in range(n):
            try:
                v = raw[i]
                result.append(max(0.0, float(v)) if v is not None else 0.0)
                if v is None:
                    missing += 1
            except (IndexError, TypeError, ValueError):
                result.append(0.0)
                missing += 1
        if missing:
            print(f'[elevation-batch] {missing}/{n} points missing; 0m fallback applied')
        return result

    except Exception as e:
        print(f'[elevation-batch] batch request failed ({e}); '
              f'using 0m fallback for all {n} points. '
              f'Score terrain correction will be skipped (elevation > 100m check).')
        return [0.0] * n


def _score_color(score: int) -> str:
    if score >= 80: return '#1f9d55'
    if score >= 50: return '#c9a500'  # 凡例(legend.stops/HTML)と完全一致
    return '#d64545'

def _score_category(score: int) -> str:
    if score >= 80: return 'excellent'
    if score >= 50: return 'fair'
    return 'poor'

def _wind_color(speed) -> str:
    """Color for wind speed: 4-band scale (too weak / ideal / strong / dangerous)."""
    if speed is None: return '#adb5bd'
    if speed >= 9.0:  return '#d64545'   # 強風・飛散注意（乾燥不適）
    if speed >= 6.0:  return '#e07b39'   # 強め・作業注意
    if speed >= 2.0:  return '#1f9d55'   # 適風（2.0–5.9 m/s 乾燥適正）
    return '#4a90d9'                      # 弱風・乾きにくい（< 2.0 m/s）

def _wind_category(speed) -> str:
    if speed is None: return 'unknown'
    if speed >= 9.0:  return 'strong_danger'
    if speed >= 6.0:  return 'strong_caution'
    if speed >= 2.0:  return 'ideal'
    return 'weak'

def _hum_color(hum) -> str:
    if hum is None: return '#adb5bd'
    if hum > 94:  return '#d64545'
    if hum >= 85: return '#c9a500'  # 凡例(legend.stops/HTML)と完全一致
    return '#1f9d55'

def _hum_category(hum) -> str:
    if hum is None: return 'unknown'
    if hum > 94:  return 'poor'
    if hum >= 85: return 'fair'
    return 'good'

def _solar_color(solar) -> str:
    if solar is None: return '#adb5bd'
    if solar >= 400: return '#1f9d55'
    if solar >= 50:  return '#c9a500'  # 凡例(legend.stops/HTML)と完全一致
    return '#d64545'

def _solar_category(solar) -> str:
    if solar is None: return 'unknown'
    if solar >= 400: return 'excellent'
    if solar >= 50:  return 'fair'
    return 'poor'

def _temp_color(temp) -> str:
    if temp is None: return '#adb5bd'
    if temp >= 20: return '#e07b39'
    if temp >= 10: return '#1f9d55'
    return '#4a90d9'

def _temp_category(temp) -> str:
    if temp is None: return 'unknown'
    if temp >= 20: return 'warm'
    if temp >= 10: return 'moderate'
    return 'cool'

def _precip_color(precip) -> str:
    """Color for hourly precipitation (mm/h).
    0mm = 干し可能（緑）、0.1〜0.9mm = 小雨（橙）、1〜4.9mm = 雨（赤）、5+mm = 強雨（濃赤）
    """
    if precip is None: return '#adb5bd'
    if precip >= 5.0:  return '#9b2335'   # 強雨・完全干し不可
    if precip >= 1.0:  return '#d64545'   # 雨・干し不可
    if precip >= 0.1:  return '#e07b39'   # 小雨・干し不可（殺し屋境界）
    return '#1f9d55'                       # 0mm・乾燥可能

def _precip_category(precip) -> str:
    if precip is None: return 'unknown'
    if precip >= 5.0:  return 'heavy'
    if precip >= 1.0:  return 'rain'
    if precip >= 0.1:  return 'trace'
    return 'dry'


def _make_wind_warning(max_wind_ms) -> dict | None:
    """
    日内最大風速(m/s)から wind_warning オブジェクトを生成する共通ヘルパー。

    判定基準（_wind_color・get_forecast の wind_warning と完全整合）:
        < 6.0 m/s  → None        (弱風〜適風)
        6.0〜8.9   → caution     (強め・作業注意)
        ≥ 9.0      → danger      (強風・飛散注意)

    使用箇所: get_forecast() と _compute_score_field() の両方で参照する。
    """
    if max_wind_ms is None:
        return None
    ms = float(max_wind_ms)
    if ms >= 9.0:
        return {
            'level':       'danger',
            'label':       '強風・飛散注意',
            'message':     '昆布の飛散や作業安全に注意してください',
            'max_wind_ms': round(ms, 1),
        }
    if ms >= 6.0:
        return {
            'level':       'caution',
            'label':       '強めの風・作業注意',
            'message':     '乾燥は進みやすい一方、取り扱いに注意してください',
            'max_wind_ms': round(ms, 1),
        }
    return None


def _field_target_date(day: int) -> str:
    """day=0→今日(JST), day=1→明日, … Returns 'YYYY-MM-DD'."""
    return (datetime.now(tz=JST) + timedelta(days=day)).strftime('%Y-%m-%d')


def _fetch_open_meteo_multi(lats: list, lons: list, hourly_vars: list) -> list:
    """
    Open-Meteo JMA-MSM 予報を複数地点並列取得（ThreadPoolExecutor）。
    Returns list[dict] — 順序は lats/lons と一致。
    失敗した地点は {'hourly': {}} で補完するため呼び出し元が IndexError にならない。
    """
    import concurrent.futures as _cf

    vars_str = ','.join(hourly_vars)

    def _fetch_one(lat_lon):
        lat, lon = lat_lon
        url = (
            f'https://api.open-meteo.com/v1/forecast'
            f'?latitude={lat:.4f}&longitude={lon:.4f}'
            f'&hourly={vars_str}'
            f'&timezone=Asia%2FTokyo&forecast_days=8&models=jma_seamless'
        )
        try:
            r = requests.get(url, timeout=15)
            r.raise_for_status()
            return r.json()
        except Exception as exc:
            print(f'[field-multi] {lat:.4f},{lon:.4f} failed: {exc}')
            return {'hourly': {}}

    with _cf.ThreadPoolExecutor(max_workers=10) as ex:
        return list(ex.map(_fetch_one, zip(lats, lons)))


def _extract_day_window(hourly: dict, target_date: str) -> dict:
    """
    Open-Meteo hourly dict から target_date の作業時間帯（04〜16時JST）だけ抽出。
    Returns {variable: [values]} — time キーは除外。
    """
    times = hourly.get('time', [])
    indices = [
        i for i, t in enumerate(times)
        if t.startswith(target_date) and 4 <= int(t[11:13]) <= 16
    ]
    result = {}
    for var, values in hourly.items():
        if var == 'time':
            continue
        result[var] = [values[i] for i in indices if i < len(values)]
    return result


def _safe_max(values) -> float | None:
    """None を除いた最大値。値が空なら None。"""
    valid = [v for v in (values or []) if v is not None]
    return max(valid) if valid else None


def _safe_min(values) -> float | None:
    """None を除いた最小値。値が空なら None。"""
    valid = [v for v in (values or []) if v is not None]
    return min(valid) if valid else None


def _safe_avg(values) -> float | None:
    """None を除いた平均値。値が空なら None。"""
    valid = [v for v in (values or []) if v is not None]
    return sum(valid) / len(valid) if valid else None


def _safe_sum(values) -> float | None:
    """None を除いた合計。値が空なら None。"""
    valid = [v for v in (values or []) if v is not None]
    return sum(valid) if valid else None


# ═══════════════════════════════════════════════════════════════════════════════
#  ローカルリスク補正ヘルパー群
#  ─────────────────────────────────────────────────────────────────────────────
#  /api/forecast と _compute_score_field の両コードパスで呼ばれる。
#  「新しい補正を追加するときはこのブロックだけ触れば良い」が設計原則。
#  ▶ 片方の呼び出し側だけに補正を追加しないこと（スコア乖離の再発防止）
# ═══════════════════════════════════════════════════════════════════════════════

def _compute_fog_from_hourly_flags(hourly_data: list) -> tuple[str, str]:
    """
    hourly_data の fog_risk フラグ集計から (fog_summary, fog_note) を返す。
    /api/forecast 専用。fog_risk は露点 + 雲量 + 風速で判定済みの複合フラグ。

    Returns
    -------
    fog_summary : 'low' / 'medium' / 'high'
    fog_note    : ペナルティ説明文（ペナルティなしは空文字）
    """
    high_h = sum(1 for h in hourly_data if h.get('fog_risk') == 'high')
    if high_h >= 4:
        level = 'high'
    elif high_h >= 2:
        level = 'medium'
    else:
        level = 'low'
    pen   = {'high': -10, 'medium': -5, 'low': 0}[level]
    note  = f'霧リスク({level}): {pen:+d}点' if pen < 0 else ''
    return level, note


def _compute_fog_from_dewpoint(
        temp_vals: list, dewpt_vals: list, humidity_min: float | None
) -> tuple[str, str, str]:
    """
    露点降下量（temp - dewpoint）から (fog_summary, fog_note, method) を返す。
    _compute_score_field 専用。露点データがなければ最低湿度で推定。

    Returns
    -------
    fog_summary  : 'low' / 'medium' / 'high'
    fog_note     : ペナルティ説明文（ペナルティなしは空文字）
    method       : 'dewpoint_depression' or 'humidity_estimate'
    """
    _valid = _high = _med = 0
    for _t, _d in zip(temp_vals or [], dewpt_vals or []):
        if _t is not None and _d is not None:
            _dep = _t - _d
            _valid += 1
            if _dep < 2.0:
                _high += 1
            elif _dep < 5.0:
                _med  += 1

    if _valid > 0:
        method = 'dewpoint_depression'
        if _high >= 4:
            level = 'high'
        elif _high >= 2:
            level = 'medium'
        elif _med >= 4:
            level = 'medium'
        else:
            level = 'low'
    else:
        method = 'humidity_estimate'
        if humidity_min is not None and humidity_min > 95:
            level = 'high'
        elif humidity_min is not None and humidity_min > 90:
            level = 'medium'
        else:
            level = 'low'

    pen = {'high': -10, 'medium': -5, 'low': 0}[level]
    if pen < 0:
        note = (
            f'露点降下霧リスク({level}, 高リスク{_high}h): {pen:+d}点'
            if method == 'dewpoint_depression'
            else f'高湿度霧推定({level}): {pen:+d}点'
        )
    else:
        note = ''
    return level, note, method


def _compute_foehn_hours(
        wind_dir_raw: list, wind_spd_kmh_raw: list, mountain_az: float
) -> int:
    """
    山背風フェーン時間数を算出。
    wind_toward（wind_dir + 180°）と mountain_az の角度差 > 150° かつ風速 > 3 m/s。

    Parameters
    ----------
    wind_dir_raw    : 風向リスト [°] (where wind comes FROM)
    wind_spd_kmh_raw: 風速リスト [km/h]
    mountain_az     : 観測点から利尻山頂への気象学的方位角 [°] (北=0, 時計回り)

    Returns
    -------
    フェーン効果が発生した時間数 (int)
    """
    count = 0
    for _wd, _wkm in zip(wind_dir_raw or [], wind_spd_kmh_raw or []):
        if _wd is None or _wkm is None:
            continue
        _adiff = abs((_wd + 180) % 360 - mountain_az)
        if _adiff > 180:
            _adiff = 360 - _adiff
        if _adiff > 150 and (_wkm / 3.6) > 3.0:
            count += 1
    return count


def _apply_local_risk_adjustments(
        score: float, *,
        cape_risk:    dict,
        fog_summary:  str,
        foehn_hours:  int,
        sst_fog_risk: str,
        fog_note:     str   = '',
        dewpt_method: str   = 'dewpoint_depression',
) -> tuple[int, dict]:
    """
    4補正（CAPE・霧・フェーン・SST）をスコアに一括適用し dict を返す **唯一の場所**。

    /api/forecast と _compute_score_field の両方がここを呼ぶ。
    ▶ 新補正を追加するときはこの関数のシグネチャと本体だけを変更すること。
    ▶ 呼び出し側 2 箇所のうち片方だけに直接書かないこと（スコア乖離の再発防止）。

    Parameters
    ----------
    score        : 基礎スコア（precipitation gate 適用後、local risk 未適用）
    cape_risk    : assess_cape_risk() の戻り値
    fog_summary  : 'low' / 'medium' / 'high'
    foehn_hours  : 山背風フェーン時間数
    sst_fog_risk : assess_sst_fog_risk() の戻り値
    fog_note     : 霧の説明文（空文字で自動生成）
    dewpt_method : 'dewpoint_depression' or 'humidity_estimate'（UI 表示用）

    Returns
    -------
    (new_score: int, local_risk_adjustments: dict)
    """
    # 1. CAPE ─────────────────────────────────────────────────────────────────
    score = max(0, min(100, score + cape_risk['score_penalty']))

    # 2. 霧 ───────────────────────────────────────────────────────────────────
    _fog_pen = {'low': 0, 'medium': -5, 'high': -10}.get(fog_summary, 0)
    score = max(0, min(100, score + _fog_pen))

    # 3. フェーン + SST ─────────────────────────────────────────────────────
    _foehn_adj = min(8, foehn_hours * 2)
    _sst_adj   = -5 if sst_fog_risk in ('very_high', 'high') else 0
    score = max(0, min(100, score + _foehn_adj + _sst_adj))

    # notes 組み立て
    notes = []
    if _fog_pen < 0:
        notes.append(fog_note or f'霧リスク({fog_summary}): {_fog_pen:+d}点')
    if cape_risk['score_penalty'] < 0:
        notes.append(f'CAPE対流リスク({cape_risk["risk"]}): {cape_risk["score_penalty"]:+d}点')
    if _foehn_adj > 0:
        notes.append(f'山背風フェーン({foehn_hours}時間): +{_foehn_adj}点')
    if _sst_adj < 0:
        notes.append(f'SST霧リスク({sst_fog_risk}): {_sst_adj:+d}点')

    adj = {
        'fog_penalty':      _fog_pen,
        'cape_penalty':     cape_risk['score_penalty'],
        'foehn_adjustment': _foehn_adj,
        'sst_fog_penalty':  _sst_adj,
        'total_adjustment': _fog_pen + cape_risk['score_penalty'] + _foehn_adj + _sst_adj,
        'notes':            notes,
        'method':           dewpt_method,
    }

    return int(max(0, min(100, score))), adj


def _compute_score_field(day: int) -> dict:
    """
    Compute drying score for 6×8=48 representative grid points.

    【旧実装の問題】
    334地点を0.01°精度でユニーク化 → 100点以上のユニーク座標 → Open-Meteo URL超長大
    → 初回レスポンス約401秒 のタイムアウト問題が発生していた。

    【修正後】
    wind/humidity/solar/temperature と同じく _build_rishiri_grid() の49点グリッドを使用。
    島内分布の面表示として十分な近似。個別干場の精密予報は /api/forecast を使うこと。

    【風速スコア修正済み（v2.6.1相当）】
    旧実装: wind_speed ≥ 2.0 で +15、≥ 3.0 で +10（上限なし → ≥9m/s でも +25点）
    新実装: 4バンド評価で表示レイヤー（_wind_color）と完全整合。
        < 2.0 m/s → +0  (弱風)
        2.0〜5.9  → +25 (適風)
        6.0〜8.9  → +10 (強め・作業注意)
        ≥ 9.0     → -15 (強風・飛散注意)
    """
    target_date = _field_target_date(day)

    grid = _build_rishiri_grid()   # 1+24+24=49点（山頂1 + 内リング24 + 外リング24）
    lats = [g['lat'] for g in grid]
    lons = [g['lon'] for g in grid]

    hourly_vars = [
        'temperature_2m', 'relative_humidity_2m', 'wind_speed_10m',
        'precipitation', 'precipitation_probability', 'shortwave_radiation',
        'dewpoint_2m',          # 露点温度: 霧リスク判定に使用 (/api/forecast と同一ロジック)
        'cape',                 # CAPE 対流不安定リスク（assess_cape_risk() に供給）
        'wind_direction_10m',   # フェーン判定（山背風: angle_diff > 150° + wind > 3 m/s）
    ]

    # 標高を一括取得（1HTTPリクエスト ≈ 2s）
    # 個別取得(48×get_elevation() ≈ 72s)を回避する核心の高速化
    grid_elevations = _fetch_elevations_batch(lats, lons)

    try:
        api_results = _fetch_open_meteo_multi(lats, lons, hourly_vars)
    except Exception as e:
        return {'error': f'Open-Meteo fetch failed: {e}'}

    # ─── 島共通 SST（Marine API は 1 回だけ取得）──────────────────────────────
    # 利尻島は直径約20km。SST の島内空間変動は小さいため、
    # 島中心1点で代表し全48格子点に共通適用する。
    _ISLAND_LAT,  _ISLAND_LON  = 45.1821, 141.2421   # 利尻島地理中心
    _SUMMIT_LAT,  _SUMMIT_LON  = 45.1800, 141.2392   # 利尻山頂（R_1800_2392）
    _sst_field = get_sea_surface_temperature(_ISLAND_LAT, _ISLAND_LON)
    _sst_today_field = _sst_field[day] if day < len(_sst_field) else None

    points = []
    counts = {'excellent': 0, 'fair': 0, 'poor': 0}
    best = None

    for i, (g, api_data) in enumerate(zip(grid, api_results)):
        win = _extract_day_window(api_data.get('hourly', {}), target_date)
        wind_kmh     = win.get('wind_speed_10m', [])
        wind_ms_vals = [v / 3.6 for v in wind_kmh if v is not None]

        temp_vals    = win.get('temperature_2m', [])
        dewpt_vals   = win.get('dewpoint_2m', [])
        temp_max     = _safe_max(temp_vals)
        temp_avg     = _safe_avg(temp_vals)
        humidity_min = _safe_min(win.get('relative_humidity_2m', []))
        wind_avg_ms  = _safe_avg(wind_ms_vals)
        wind_max_ms  = _safe_max(wind_ms_vals)   # 日内最大風速（wind_warning 判定に使用）
        precip_sum   = _safe_sum(win.get('precipitation', []))
        pop_max      = _safe_max(win.get('precipitation_probability', []))
        solar_avg    = _safe_avg(win.get('shortwave_radiation', []))
        elev         = grid_elevations[i] if i < len(grid_elevations) else 0.0

        score = calculate_enhanced_drying_score(
            temp_max=temp_max,
            humidity=humidity_min,
            wind_speed=wind_avg_ms,
            precipitation=precip_sum or 0,
            lat=g['lat'],
            lon=g['lon'],
            avg_solar_radiation=solar_avg,
            pop_max=pop_max,
            elevation=elev,          # バッチ取得済み標高を渡す（個別API呼び出しをスキップ）
        )

        # ─── local_risk_adjustments (field score 版) ───────────────────────────
        # _apply_local_risk_adjustments() を通じて /api/forecast と完全に同一の
        # 4補正を適用する。入力値の算出のみがここの責務。

        # CAPE
        _cape_risk_f = assess_cape_risk(_safe_max(win.get('cape', [])))

        # 霧（露点降下法 / 湿度推定フォールバック）
        _fog_sum_f, _fog_note_f, _dewpt_method = _compute_fog_from_dewpoint(
            temp_vals, dewpt_vals, humidity_min
        )

        # フェーン（格子点→利尻山頂の方位角を動的計算）
        _dlat_f = _SUMMIT_LAT - g['lat']
        _dlon_f = _SUMMIT_LON - g['lon']
        _maz_f  = (90 - math.degrees(math.atan2(_dlat_f, _dlon_f))) % 360
        _foehn_h = _compute_foehn_hours(
            win.get('wind_direction_10m', []),
            win.get('wind_speed_10m', []),
            _maz_f,
        )

        # SST（島共通）
        _sst_risk_f = assess_sst_fog_risk(_sst_today_field, temp_max)

        # 4補正を一括適用（唯一の適用経路）
        score, local_risk_adjustments = _apply_local_risk_adjustments(
            score,
            cape_risk    = _cape_risk_f,
            fog_summary  = _fog_sum_f,
            fog_note     = _fog_note_f,
            foehn_hours  = _foehn_h,
            sst_fog_risk = _sst_risk_f,
            dewpt_method = _dewpt_method,
        )
        # ────────────────────────────────────────────────────────────────────────

        cat = _score_category(score)
        counts[cat] = counts.get(cat, 0) + 1

        # wind_warning: _make_wind_warning() で /api/forecast と同一ロジックを共用
        # max_wind_ms（日内最大）を使用し、avg（平均）では見逃すピーク強風を捕捉する
        wind_warning = _make_wind_warning(wind_max_ms)

        display_name = g.get('label') or f'沿岸{i + 1} ({g["lat"]:.2f}N,{g["lon"]:.2f}E)'
        if best is None or score > best['score']:
            best = {'name': display_name, 'score': score}

        points.append({
            'name':     display_name,
            'lat':      round(g['lat'], 4),
            'lon':      round(g['lon'], 4),
            'bearing':  g.get('bearing'),    # 山頂からの方位角（フロントエンドツールチップ用）
            'town':     '',          # グリッド点は行政区分なし（干場個別は /api/forecast を使用）
            'district': '',
            'buraku':   '',
            'value':    score,
            'category': cat,
            'color':    _score_color(score),
            'metrics': {
                'precipitation': round(precip_sum or 0, 2),
                'min_humidity':  round(humidity_min or 0),
                'avg_wind_ms':   round(wind_avg_ms, 1) if wind_avg_ms is not None else None,
                'max_wind_ms':   round(wind_max_ms, 1) if wind_max_ms is not None else None,
                'avg_solar':     round(solar_avg or 0),
                'pop_max':       round(pop_max or 0),
            },
            'wind_warning': wind_warning,   # None / {level, label, message, max_wind_ms}
            'local_risk_adjustments': local_risk_adjustments,
        })

    return {
        'summary': {
            'total':     len(points),
            'excellent': counts.get('excellent', 0),
            'fair':      counts.get('fair', 0),
            'poor':      counts.get('poor', 0),
            'best_spot': best,
        },
        'legend': {
            'unit': 'score (0-100)',
            'stops': [
                {'value': 80, 'label': '干せる',  'color': '#1f9d55'},
                {'value': 50, 'label': '微妙',    'color': '#c9a500'},
                {'value': 0,  'label': '厳しい',  'color': '#d64545'},
            ],
        },
        'points': points,
    }


def _compute_wind_field(day: int, hour: int) -> dict:
    """Compute wind vectors for 6×8 representative grid (covers all 334 spots)."""
    target_date = _field_target_date(day)
    target_time = f'{target_date}T{hour:02d}:00'

    grid = _build_rishiri_grid()
    lats = [g['lat'] for g in grid]
    lons = [g['lon'] for g in grid]

    try:
        api_results = _fetch_open_meteo_multi(
            lats, lons, ['wind_speed_10m', 'wind_direction_10m']
        )
    except Exception as e:
        return {'error': f'Open-Meteo fetch failed: {e}'}

    vectors = []
    for g, api_data in zip(grid, api_results):
        hourly = api_data.get('hourly', {})
        times  = hourly.get('time', [])
        try:
            idx = times.index(target_time)
        except ValueError:
            idx = None

        speed_kmh = hourly.get('wind_speed_10m', [None])[idx] if idx is not None else None
        direction = hourly.get('wind_direction_10m', [None])[idx] if idx is not None else None
        speed_ms  = speed_kmh / 3.6 if speed_kmh is not None else None

        if speed_ms is not None and direction is not None:
            rad = _math.radians(direction)
            u = round(-speed_ms * _math.sin(rad), 3)
            v = round(-speed_ms * _math.cos(rad), 3)
        else:
            u = v = None

        vectors.append({
            'lat':       round(g['lat'], 4),
            'lon':       round(g['lon'], 4),
            'speed':     round(speed_ms, 1) if speed_ms is not None else None,
            'direction': direction,
            'u':         u,
            'v':         v,
            'color':     _wind_color(speed_ms),
            'category':  _wind_category(speed_ms),
        })

    return {
        'hour': hour,
        'thresholds': {'drying_min_wind': 2.0, 'caution': 6.0, 'danger': 9.0},
        'legend': {
            'unit': 'm/s',
            'stops': [
                {'value': 9.0, 'label': '9.0+ m/s 強風・飛散注意',  'color': '#d64545'},
                {'value': 6.0, 'label': '6.0〜8.9 m/s 強め・注意', 'color': '#e07b39'},
                {'value': 2.0, 'label': '2.0〜5.9 m/s 適風',       'color': '#1f9d55'},
                {'value': 0,   'label': '2.0未満 m/s 弱風',         'color': '#4a90d9'},
            ],
        },
        'vectors': vectors,
    }


def _compute_humidity_field(day: int, hour: int) -> dict:
    """Compute humidity for 6×8 grid with terrain correction (covers all 334 spots)."""
    target_date = _field_target_date(day)
    target_time = f'{target_date}T{hour:02d}:00'

    grid = _build_rishiri_grid()
    lats = [g['lat'] for g in grid]
    lons = [g['lon'] for g in grid]

    try:
        api_results = _fetch_open_meteo_multi(
            lats, lons, ['relative_humidity_2m', 'wind_direction_10m']
        )
    except Exception as e:
        return {'error': f'Open-Meteo fetch failed: {e}'}

    points = []
    for i, (g, api_data) in enumerate(zip(grid, api_results)):
        hourly = api_data.get('hourly', {})
        times  = hourly.get('time', [])
        try:
            idx = times.index(target_time)
        except ValueError:
            idx = None

        raw      = hourly.get('relative_humidity_2m', [None])[idx] if idx is not None else None
        wind_dir = hourly.get('wind_direction_10m',   [None])[idx] if idx is not None else None

        hum = raw
        correction_parts = []
        if hum is not None:
            if is_forest_area(g['lat'], g['lon']):
                hum = min(100.0, hum + 10.0)
                correction_parts.append('森林+10%')
            if is_coastal_area(g['lat'], g['lon']) and wind_dir is not None:
                onshore_factor = get_onshore_wind_factor(g['lat'], g['lon'], wind_dir)
                coastal_adj = 5.0 * onshore_factor
                if coastal_adj > 0.1:
                    hum = min(100.0, hum + coastal_adj)
                    correction_parts.append(f'海岸+{coastal_adj:.1f}%')
            hum = round(hum)

        display_name = f'格子点{i + 1} ({g["lat"]:.2f}N,{g["lon"]:.2f}E)'
        points.append({
            'name':       display_name,
            'lat':        round(g['lat'], 4),
            'lon':        round(g['lon'], 4),
            'value':      hum,
            'raw_value':  round(raw) if raw is not None else None,
            'wind_dir':   round(wind_dir) if wind_dir is not None else None,
            'color':      _hum_color(hum),
            'category':   _hum_category(hum),
            'correction': ', '.join(correction_parts) if correction_parts else 'なし',
        })

    return {
        'hour': hour,
        'thresholds': {'drying_critical': 94, 'drying_caution': 85},
        'legend': {
            'unit': '%',
            'stops': [
                {'value': 95, 'label': '95%超 乾きにくい', 'color': '#d64545'},
                {'value': 85, 'label': '85〜94% 注意',    'color': '#c9a500'},  # HTML legend color
                {'value': 0,  'label': '84%以下 良好',    'color': '#1f9d55'},
            ],
        },
        'correction_note': '森林+10% / 海岸+5%×onshore係数の地形補正を適用',
        'points': points,
    }


def _compute_solar_field(day: int, hour: int) -> dict:
    """Compute shortwave radiation (W/m²) for 6×8 grid (covers all 334 spots)."""
    target_date = _field_target_date(day)
    target_time = f'{target_date}T{hour:02d}:00'

    grid = _build_rishiri_grid()
    lats = [g['lat'] for g in grid]
    lons = [g['lon'] for g in grid]

    try:
        api_results = _fetch_open_meteo_multi(lats, lons, ['shortwave_radiation'])
    except Exception as e:
        return {'error': f'Open-Meteo fetch failed: {e}'}

    points = []
    for i, (g, api_data) in enumerate(zip(grid, api_results)):
        hourly = api_data.get('hourly', {})
        times  = hourly.get('time', [])
        try:
            idx = times.index(target_time)
        except ValueError:
            idx = None

        raw = hourly.get('shortwave_radiation', [None])[idx] if idx is not None else None
        solar = round(raw) if raw is not None else None

        display_name = f'格子点{i + 1} ({g["lat"]:.2f}N,{g["lon"]:.2f}E)'
        points.append({
            'name':     display_name,
            'lat':      round(g['lat'], 4),
            'lon':      round(g['lon'], 4),
            'value':    solar,
            'color':    _solar_color(solar),
            'category': _solar_category(solar),
        })

    return {
        'hour': hour,
        'thresholds': {'excellent': 400, 'poor': 50},
        'legend': {
            'unit': 'W/m²',
            'stops': [
                {'value': 400, 'label': '400+ W/m² 乾燥促進',   'color': '#1f9d55'},
                {'value': 50,  'label': '50〜399 W/m² 曇天',    'color': '#c9a500'},  # HTML legend color
                {'value': 0,   'label': '50未満 W/m² 乾燥困難', 'color': '#d64545'},
            ],
        },
        'correction_note': '地形補正なし（Open-Meteo MSM/GSMの日射量をそのまま表示）',
        'points': points,
    }


def _compute_temperature_field(day: int, hour: int) -> dict:
    """Compute temperature (°C) for 6×8 grid (covers all 334 spots)."""
    target_date = _field_target_date(day)
    target_time = f'{target_date}T{hour:02d}:00'

    grid = _build_rishiri_grid()
    lats = [g['lat'] for g in grid]
    lons = [g['lon'] for g in grid]

    try:
        api_results = _fetch_open_meteo_multi(lats, lons, ['temperature_2m'])
    except Exception as e:
        return {'error': f'Open-Meteo fetch failed: {e}'}

    points = []
    for i, (g, api_data) in enumerate(zip(grid, api_results)):
        hourly = api_data.get('hourly', {})
        times  = hourly.get('time', [])
        try:
            idx = times.index(target_time)
        except ValueError:
            idx = None

        raw  = hourly.get('temperature_2m', [None])[idx] if idx is not None else None
        temp = round(raw, 1) if raw is not None else None

        display_name = f'格子点{i + 1} ({g["lat"]:.2f}N,{g["lon"]:.2f}E)'
        points.append({
            'name':     display_name,
            'lat':      round(g['lat'], 4),
            'lon':      round(g['lon'], 4),
            'value':    temp,
            'color':    _temp_color(temp),
            'category': _temp_category(temp),
        })

    return {
        'hour': hour,
        'thresholds': {'warm': 20, 'cool': 10},
        'legend': {
            'unit': '°C',
            'stops': [
                {'value': 20, 'label': '20°C以上 温暖', 'color': '#e07b39'},
                {'value': 10, 'label': '10〜19°C 適温', 'color': '#1f9d55'},
                {'value': 0,  'label': '10°C未満 低温', 'color': '#4a90d9'},
            ],
        },
        'correction_note': 'Open-Meteoが標高補正済み（0.7°C/100m）のため独自補正なし',
        'points': points,
    }


def _compute_precipitation_field(day: int, hour: int) -> dict:
    """Compute hourly precipitation (mm/h) for the 49-point Rishiri grid.

    Open-Meteo `precipitation` は時間雨量 (mm/h)。
    0mm = 乾燥可能（緑）、0.1mm以上 = 干し不可（橙〜濃赤）の殺し屋判定に直結。
    地形補正なし（Open-Meteo MSM が地形性降雨を計算済み）。
    """
    target_date = _field_target_date(day)
    target_time = f'{target_date}T{hour:02d}:00'

    grid = _build_rishiri_grid()
    lats = [g['lat'] for g in grid]
    lons = [g['lon'] for g in grid]

    try:
        api_results = _fetch_open_meteo_multi(lats, lons, ['precipitation'])
    except Exception as e:
        return {'error': f'Open-Meteo fetch failed: {e}'}

    points     = []
    all_zero   = True
    max_precip = 0.0
    max_spot   = None

    for i, (g, api_data) in enumerate(zip(grid, api_results)):
        hourly = api_data.get('hourly', {})
        times  = hourly.get('time', [])
        try:
            idx = times.index(target_time)
        except ValueError:
            idx = None

        raw    = hourly.get('precipitation', [None])[idx] if idx is not None else None
        precip = round(raw, 1) if raw is not None else None

        if precip is not None and precip > 0:
            all_zero = False
        if precip is not None and precip > max_precip:
            max_precip = precip
            max_spot   = g.get('label') or f'格子点{i + 1}'

        display_name = g.get('label') or f'格子点{i + 1} ({g["lat"]:.2f}N,{g["lon"]:.2f}E)'
        points.append({
            'name':     display_name,
            'lat':      round(g['lat'], 4),
            'lon':      round(g['lon'], 4),
            'bearing':  g.get('bearing'),
            'value':    precip,
            'color':    _precip_color(precip),
            'category': _precip_category(precip),
        })

    return {
        'hour':      hour,
        'all_zero':  all_zero,
        'max_precip': round(max_precip, 1),
        'max_spot':  max_spot,
        'thresholds': {'trace': 0.1, 'light': 1.0, 'heavy': 5.0},
        'legend': {
            'unit': 'mm/h',
            'stops': [
                {'value': 5.0, 'label': '5mm以上 強雨（完全干し不可）', 'color': '#9b2335'},
                {'value': 1.0, 'label': '1〜4.9mm 雨（干し不可）',      'color': '#d64545'},
                {'value': 0.1, 'label': '0.1〜0.9mm 小雨（干し不可）',  'color': '#e07b39'},
                {'value': 0,   'label': '0mm 降水なし（乾燥可能）',      'color': '#1f9d55'},
            ],
        },
        'note': '1時間降水量。0mm = 干し可能、0.1mm以上 = 干し不可（Open-Meteo MSM地形性降雨込み）',
        'points': points,
    }


@app.route('/api/analysis/field')
@limiter.limit("20 per minute")
def get_analysis_field():
    """
    島内分布図データを返す。
    Leaflet/Canvas でフロント描画するため matplotlib を使わない。

    Parameters:
        type : score | wind | humidity | temperature | solar | precipitation
        day  : 0=今日, 1=明日, ..., 6 (default 0)
        hour : 4|7|10|13|16 (JST) — score以外で必須。未指定時は10。
    """
    now_jst = datetime.now(JST)

    field_type = request.args.get('type', 'score')
    try:
        day = max(0, min(6, int(request.args.get('day', 0))))
    except ValueError:
        day = 0
    try:
        hour = int(request.args.get('hour', 10))
    except ValueError:
        hour = 10

    valid_types = ('score', 'wind', 'humidity', 'temperature', 'solar', 'precipitation')
    if field_type not in valid_types:
        return jsonify({'status': 'error',
                        'message': f'type は {"|".join(valid_types)} のいずれか'}), 400

    if field_type != 'score':
        if hour not in _ALLOWED_HOURS:
            return jsonify({
                'status':  'error',
                'message': f'hour は {_ALLOWED_HOURS} のいずれかを指定してください',
                'allowed_hours': _ALLOWED_HOURS,
            }), 400

    # キャッシュヒット確認（外部APIコールをスキップ）
    cache_key = f'{field_type}:{day}:{hour}'
    cached = _field_cache_get(cache_key)
    if cached:
        cached['cache'] = {'hit': True}
        return jsonify(cached)

    target_date = _field_target_date(day)

    # フィールドタイプ別データ取得
    if field_type == 'score':
        data = _compute_score_field(day)
    elif field_type == 'wind':
        data = _compute_wind_field(day, hour)
    elif field_type == 'humidity':
        data = _compute_humidity_field(day, hour)
    elif field_type == 'temperature':
        data = _compute_temperature_field(day, hour)
    elif field_type == 'solar':
        data = _compute_solar_field(day, hour)
    elif field_type == 'precipitation':
        data = _compute_precipitation_field(day, hour)
    else:
        data = {'error': 'unknown type'}

    if 'error' in data:
        return jsonify({'status': 'error', 'message': data['error']}), 503

    response_data = {
        'status':       'success',
        'type':         field_type,
        'day':          day,
        'target_date':  target_date,
        'timezone':     'Asia/Tokyo',
        'generated_at': now_jst.isoformat(),
        'cache':        {'hit': False},
        'data_resolution': {
            'source_model': 'Open-Meteo JMA MSM/GSM',
            'note': '利尻島内はMSMで概ね5kmメッシュ。干場間の差は地形補正による推定値',
            'rendering': 'client_leaflet',
        },
        **data,
    }
    _field_cache_set(cache_key, response_data)
    return jsonify(response_data)


@app.route('/api/analysis/contours')
def get_contour_analysis():
    """
    等値線解析データを取得（仕様書 lines 584-682）

    地上レベル（7日間）と高層レベル（16日間）の等値線解析をサポート

    Parameters:
    - type: 解析カテゴリー（temperature, humidity, pressure, wind, precipitation,
            vorticity_500hpa, omega_700hpa, theta_e_850hpa）
    - time: 予報時間オフセット（0-168h 地上、0-384h 高層）
    """
    try:
        category = request.args.get('type', 'temperature')
        time_offset = int(request.args.get('time', 0))

        # 利尻島中心座標
        lat = 45.1821
        lon = 141.2421

        # カテゴリー別処理
        if category in ['temperature', 'humidity', 'pressure', 'wind', 'precipitation',
                       'temperature_850hpa', 'humidity_850hpa', 'wind_850hpa',
                       'temperature_700hpa', 'humidity_700hpa', 'wind_700hpa']:
            # matplotlib による等値線図生成は廃止（v2.6.1）
            # 代替: /api/analysis/field?type=score|wind|humidity|temperature|solar を使用
            return jsonify({
                'status': 'deprecated',
                'message': (
                    'このカテゴリーのmatplotlib等値線図は廃止されました。'
                    '新エンドポイント /api/analysis/field?type=score|wind|humidity|temperature|solar を使用してください。'
                ),
                'new_endpoint': '/api/analysis/field'
            }), 410

        elif category in ['wave_height', 'wave_direction_period']:
            # 海域レベル（最大168時間=7日間）
            if time_offset > 168:
                return jsonify({
                    'status': 'error',
                    'message': '海域データは最大168時間（7日間）までです'
                }), 400

            # 海域データ取得
            marine_data = fetch_marine_data(lat, lon, time_offset + 24)

            if not marine_data:
                return jsonify({
                    'status': 'error',
                    'message': 'Open-Meteo Marine APIからのデータ取得に失敗しました'
                }), 500

            hourly = marine_data.get('hourly', {})

            # 指定時刻のデータを抽出
            if time_offset >= len(hourly.get('time', [])):
                return jsonify({
                    'status': 'error',
                    'message': f'指定時刻（{time_offset}時間後）のデータが利用できません'
                }), 400

            result = {
                'status': 'success',
                'map_type': category,
                'time_offset': time_offset,
                'time': hourly['time'][time_offset],
                'level': '海面',
                'grid_resolution': 'Open-Meteo Marine API解像度（約5km）',
                'interpolation_method': 'scipy griddata (cubic)',
                'data_source': 'Open-Meteo Marine Weather API (ECMWF WAM)'
            }

            if category == 'wave_height':
                wave_height = hourly.get('wave_height', [None])[time_offset]
                wave_dir = hourly.get('wave_direction', [None])[time_offset]
                wave_period = hourly.get('wave_period', [None])[time_offset]

                # 波高による作業可否判定（強化版）
                work_safety = "安全"
                safety_level = 5  # 5段階評価（5=安全、1=危険）
                alert_level = "normal"  # normal, caution, warning, danger

                if wave_height:
                    if wave_height >= 3.0:
                        work_safety = "🔴 危険（飛沫到達・作業中止推奨）"
                        safety_level = 1
                        alert_level = "danger"
                    elif wave_height >= 2.0:
                        work_safety = "🟠 要注意（高波・作業困難）"
                        safety_level = 2
                        alert_level = "warning"
                    elif wave_height >= 1.5:
                        work_safety = "🟡 やや注意（アクセス困難）"
                        safety_level = 3
                        alert_level = "caution"
                    elif wave_height >= 1.0:
                        work_safety = "🟢 ほぼ安全（通常作業可）"
                        safety_level = 4
                        alert_level = "normal"
                    else:
                        work_safety = "🟢 安全（穏やか）"
                        safety_level = 5
                        alert_level = "normal"

                # 海岸干場への具体的影響
                coastal_impact = []
                if wave_height and wave_height >= 3.0:
                    coastal_impact.append("飛沫が干場まで到達し昆布が濡れる危険性")
                    coastal_impact.append("干場へのアクセス路が波で遮断される可能性")
                    coastal_impact.append("作業者の安全確保が困難")
                elif wave_height and wave_height >= 2.0:
                    coastal_impact.append("海岸近くの干場で飛沫の影響あり")
                    coastal_impact.append("干場へのアクセスに注意が必要")
                elif wave_height and wave_height >= 1.5:
                    coastal_impact.append("海岸線に近い干場では注意")

                # 波向と干場の関係性（利尻島の海岸線を考慮）
                wave_impact_areas = []
                if wave_dir is not None:
                    if 315 <= wave_dir or wave_dir < 45:  # 北からの波
                        wave_impact_areas = ["鴛泊", "沓形北部", "仙法志北部"]
                    elif 45 <= wave_dir < 135:  # 東からの波
                        wave_impact_areas = ["沓形東部", "仙法志東部"]
                    elif 135 <= wave_dir < 225:  # 南からの波
                        wave_impact_areas = ["鬼脇", "仙法志南部", "沓形南部"]
                    elif 225 <= wave_dir < 315:  # 西からの波
                        wave_impact_areas = ["鴛泊西部", "沓形西部"]

                result.update({
                    'parameter': '有義波高',
                    'unit': 'm',
                    'wave_height': wave_height,
                    'wave_direction': wave_dir,
                    'wave_period': wave_period,
                    'work_safety': work_safety,
                    'safety_level': safety_level,
                    'alert_level': alert_level,
                    'coastal_impact': coastal_impact,
                    'affected_areas': wave_impact_areas,
                    'message': f'作業安全度: {work_safety}\n影響地域: {", ".join(wave_impact_areas) if wave_impact_areas else "全域で影響軽微"}'
                })

            elif category == 'wave_direction_period':
                wave_dir = hourly.get('wave_direction', [None])[time_offset]
                wave_period = hourly.get('wave_period', [None])[time_offset]
                wave_height = hourly.get('wave_height', [None])[time_offset]

                # うねりの状態判定（強化版）
                swell_condition = "穏やか"
                low_pressure_forecast = None
                forecast_confidence = "low"

                if wave_period and wave_height:
                    # 長周期うねり（10秒以上）= 遠方低気圧からの警告信号
                    if wave_period >= 10:
                        swell_condition = "長周期うねり（遠方の低気圧）"

                        # 波向から低気圧の位置を推定
                        if wave_dir is not None:
                            if 315 <= wave_dir or wave_dir < 45:  # 北からのうねり
                                low_pressure_forecast = "北方海上（オホーツク海・ベーリング海）に低気圧。2-3日後に接近の可能性"
                                forecast_confidence = "high" if wave_height >= 2.0 else "medium"
                            elif 45 <= wave_dir < 135:  # 東からのうねり
                                low_pressure_forecast = "東方海上（太平洋）に低気圧。東進中のため直接影響は限定的"
                                forecast_confidence = "medium"
                            elif 135 <= wave_dir < 225:  # 南からのうねり
                                low_pressure_forecast = "南方海上（日本海・東シナ海）に低気圧。1-2日後に北上接近の可能性大"
                                forecast_confidence = "high" if wave_height >= 2.0 else "medium"
                            elif 225 <= wave_dir < 315:  # 西からのうねり
                                low_pressure_forecast = "西方海上（大陸側）に低気圧。東進中、2-3日後に影響の可能性"
                                forecast_confidence = "medium"

                    # 中周期うねり（7-10秒）= 近傍の気圧の谷
                    elif wave_period >= 7:
                        swell_condition = "中周期うねり（風波＋うねり）"
                        low_pressure_forecast = "気圧の谷が接近中。天気の崩れに注意（12-24時間後）"
                        forecast_confidence = "medium"

                    # 短周期波（5-7秒）= 局地的な風
                    elif wave_period >= 5:
                        swell_condition = "短周期波（局地風波）"
                        low_pressure_forecast = "局地的な風による波。大規模な気圧配置の変化なし"
                        forecast_confidence = "low"

                # 7日間予報との統合アドバイス
                weather_advice = []
                if low_pressure_forecast and forecast_confidence in ["high", "medium"]:
                    weather_advice.append("7日間予報で降水確率・風速を重点的に確認してください")
                    weather_advice.append("昆布乾燥作業は低気圧接近前に完了を推奨")
                    if wave_height and wave_height >= 2.0:
                        weather_advice.append("高波注意：海岸干場の使用は避けてください")

                result.update({
                    'parameter': '波向・波周期場',
                    'unit': '度、秒',
                    'wave_direction': wave_dir,
                    'wave_period': wave_period,
                    'wave_height': wave_height,
                    'swell_condition': swell_condition,
                    'low_pressure_forecast': low_pressure_forecast,
                    'forecast_confidence': forecast_confidence,
                    'weather_advice': weather_advice,
                    'message': f'うねり状態: {swell_condition}\n低気圧予測: {low_pressure_forecast or "なし"}'
                })

            return jsonify(result)

        elif category in ['vorticity_500hpa', 'omega_700hpa', 'theta_e_850hpa',
                          'jet_stream_300hpa', 'height_anomaly_200hpa']:
            # 高層レベル（最大384時間=16日間）
            if time_offset > 384:
                return jsonify({
                    'status': 'error',
                    'message': '高層データは最大384時間（16日間）までです'
                }), 400

            # 高層データ取得
            pressure_data = fetch_pressure_level_data(lat, lon, time_offset + 24)

            if not pressure_data:
                return jsonify({
                    'status': 'error',
                    'message': 'Open-Meteo Pressure Level APIからのデータ取得に失敗しました'
                }), 500

            hourly = pressure_data.get('hourly', {})

            # 指定時刻のデータを抽出
            if time_offset >= len(hourly.get('time', [])):
                return jsonify({
                    'status': 'error',
                    'message': f'指定時刻（{time_offset}時間後）のデータが利用できません'
                }), 400

            result = {
                'status': 'success',
                'map_type': category,
                'time_offset': time_offset,
                'time': hourly['time'][time_offset],
                'grid_resolution': 'Open-Meteo API解像度（約11km）',
                'interpolation_method': 'scipy griddata (cubic)',
                'data_source': 'Open-Meteo Pressure Level API (ECMWF IFS)'
            }

            if category == 'vorticity_500hpa':
                # 相対渦度を計算
                # ζ = ∂v/∂x - ∂u/∂y（鉛直成分の渦度）
                # 正値=低気圧性回転（反時計回り）、負値=高気圧性回転（時計回り）

                temp_500 = hourly.get('temperature_500hPa', [None])[time_offset]
                geo_height_500 = hourly.get('geopotential_height_500hPa', [None])[time_offset]
                wind_speed_500 = hourly.get('wind_speed_500hPa', [None])[time_offset]
                wind_dir_500 = hourly.get('wind_direction_500hPa', [None])[time_offset]

                # 風向風速からu, v成分を計算
                vorticity_500 = None
                vorticity_interpretation = "データ不足"

                if wind_speed_500 is not None and wind_dir_500 is not None:
                    # 気象学的風向をラジアンに変換
                    wind_rad = np.deg2rad(270 - wind_dir_500)
                    u_500 = wind_speed_500 * np.cos(wind_rad)  # 東西成分 (m/s)
                    v_500 = wind_speed_500 * np.sin(wind_rad)  # 南北成分 (m/s)

                    # 簡易的な渦度推定：風向の曲率から推定
                    # 前後1時間の風向変化から渦度を近似
                    wind_dir_all = hourly.get('wind_direction_500hPa', [])
                    wind_speed_all = hourly.get('wind_speed_500hPa', [])

                    if (time_offset > 0 and time_offset < len(wind_dir_all) - 1 and
                        all(v is not None for v in [wind_dir_all[time_offset-1], wind_dir_all[time_offset+1],
                                                     wind_speed_all[time_offset-1], wind_speed_all[time_offset+1]])):

                        # 前後の風向変化（度/hour）
                        dir_before = wind_dir_all[time_offset - 1]
                        dir_after = wind_dir_all[time_offset + 1]

                        # 風向差を-180~180°に正規化
                        dir_change = ((dir_after - dir_before + 180) % 360) - 180

                        # 風向の時間変化から渦度を推定（非常に簡易的な手法）
                        # 反時計回りの回転（正の変化）= 正渦度（低気圧性）
                        # 時計回りの回転（負の変化）= 負渦度（高気圧性）
                        time_interval = 2.0  # hours
                        angular_velocity = dir_change / time_interval  # deg/hour

                        # 渦度に変換（10⁻⁵ s⁻¹単位）
                        # 1 deg/hour ≈ 4.85 × 10⁻⁶ rad/s
                        vorticity_500 = angular_velocity * 4.85  # 10⁻⁵ s⁻¹

                        # 渦度の解釈
                        if vorticity_500 > 10:
                            vorticity_interpretation = "強い低気圧性渦度（トラフ接近）"
                        elif vorticity_500 > 5:
                            vorticity_interpretation = "中程度の低気圧性渦度"
                        elif vorticity_500 > 1:
                            vorticity_interpretation = "弱い低気圧性渦度"
                        elif vorticity_500 > -1:
                            vorticity_interpretation = "中立（直線流）"
                        elif vorticity_500 > -5:
                            vorticity_interpretation = "弱い高気圧性渦度"
                        elif vorticity_500 > -10:
                            vorticity_interpretation = "中程度の高気圧性渦度"
                        else:
                            vorticity_interpretation = "強い高気圧性渦度（リッジ）"

                result.update({
                    'level': '500hPa',
                    'parameter': '相対渦度',
                    'unit': '10⁻⁵ s⁻¹',
                    'temperature_500hpa': temp_500,
                    'geopotential_height_500hpa': geo_height_500,
                    'wind_speed_500hpa': wind_speed_500,
                    'wind_direction_500hpa': wind_dir_500,
                    'relative_vorticity_500hpa': vorticity_500,
                    'vorticity_interpretation': vorticity_interpretation,
                    'calculation_method': '風向の時間変化から推定（角速度法）',
                    'message': f'渦度: {vorticity_interpretation}（正値=低気圧接近、負値=高気圧優勢）'
                })

            elif category == 'omega_700hpa':
                # Omega（鉛直p速度）を計算
                # Omega = dp/dt（気圧の時間変化率）を近似
                # 正値=下降気流、負値=上昇気流

                temp_700 = hourly.get('temperature_700hPa', [None])[time_offset]
                geo_height_700 = hourly.get('geopotential_height_700hPa', [None])[time_offset]
                rh_700 = hourly.get('relative_humidity_700hPa', [None])[time_offset]

                # 地上気圧の時間変化からOmegaを推定
                pressure_msl = hourly.get('pressure_msl', [])
                omega_700 = None
                omega_interpretation = "データ不足"

                if time_offset > 0 and time_offset < len(pressure_msl) - 1:
                    # 前後1時間の気圧変化から傾向を計算
                    p_before = pressure_msl[time_offset - 1]
                    p_current = pressure_msl[time_offset]
                    p_after = pressure_msl[time_offset + 1]

                    if all(v is not None for v in [p_before, p_current, p_after]):
                        # 3点差分で気圧傾向を計算（hPa/hour → Pa/s変換）
                        dp_dt = ((p_after - p_before) / 2.0) * 100 / 3600  # Pa/s

                        # 700hPaでのOmegaを地上気圧傾向から推定
                        # 簡易的に地上気圧傾向 × 0.7（700hPa ≈ 70%気圧）
                        omega_700 = dp_dt * 0.7

                        # Omegaの解釈
                        if omega_700 > 0.1:
                            omega_interpretation = "強い下降気流（晴天・乾燥傾向）"
                        elif omega_700 > 0.02:
                            omega_interpretation = "弱い下降気流（安定）"
                        elif omega_700 > -0.02:
                            omega_interpretation = "中立（鉛直運動なし）"
                        elif omega_700 > -0.1:
                            omega_interpretation = "弱い上昇気流（雲発生の可能性）"
                        else:
                            omega_interpretation = "強い上昇気流（降水の可能性大）"

                result.update({
                    'level': '700hPa',
                    'parameter': '鉛直p速度（Omega）',
                    'unit': 'Pa/s',
                    'temperature_700hpa': temp_700,
                    'geopotential_height_700hpa': geo_height_700,
                    'relative_humidity_700hpa': rh_700,
                    'omega_700hpa': omega_700,
                    'omega_interpretation': omega_interpretation,
                    'calculation_method': '地上気圧傾向から推定（3点差分法）',
                    'message': f'鉛直流: {omega_interpretation}（昆布乾燥には下降気流が有利）'
                })

            elif category == 'theta_e_850hpa':
                # 相当温位を計算して等値線画像を生成
                temp_850 = hourly.get('temperature_850hPa', [None])[time_offset]
                rh_850 = hourly.get('relative_humidity_850hPa', [None])[time_offset]

                theta_e = None
                theta_e_interpretation = "データ不足"
                if temp_850 is not None and rh_850 is not None:
                    theta_e = calculate_equivalent_potential_temperature_850hpa(temp_850, rh_850, 850.0)

                    # 相当温位の解釈（湿潤気団vs乾燥気団）
                    if theta_e >= 330:
                        theta_e_interpretation = "非常に湿潤な気団（熱帯性）"
                    elif theta_e >= 310:
                        theta_e_interpretation = "湿潤気団（梅雨前線・台風周辺）"
                    elif theta_e >= 295:
                        theta_e_interpretation = "やや湿潤気団"
                    elif theta_e >= 285:
                        theta_e_interpretation = "中立（平均的）"
                    elif theta_e >= 275:
                        theta_e_interpretation = "やや乾燥気団"
                    elif theta_e >= 265:
                        theta_e_interpretation = "乾燥気団（移動性高気圧）"
                    else:
                        theta_e_interpretation = "非常に乾燥な気団（寒気）"

                result.update({
                    'level': '850hPa',
                    'parameter': '相当温位',
                    'unit': 'K',
                    'temperature_850hpa': temp_850,
                    'relative_humidity_850hpa': rh_850,
                    'geopotential_height_850hpa': hourly.get('geopotential_height_850hPa', [None])[time_offset],
                    'equivalent_potential_temperature': theta_e,
                    'theta_e_interpretation': theta_e_interpretation,
                    'message': f'気団判定: {theta_e_interpretation}（昆布乾燥には乾燥気団が有利）'
                })

            elif category == 'jet_stream_300hpa':
                # ジェット気流解析（300hPa）
                wind_speed_300 = hourly.get('wind_speed_300hPa', [None])[time_offset]
                wind_dir_300 = hourly.get('wind_direction_300hPa', [None])[time_offset]
                geo_height_300 = hourly.get('geopotential_height_300hPa', [None])[time_offset]

                # ジェット強度判定
                jet_intensity = "弱"
                if wind_speed_300 is not None:
                    wind_speed_ms = wind_speed_300 / 3.6  # km/h to m/s
                    if wind_speed_ms >= 50:
                        jet_intensity = "非常に強い"
                    elif wind_speed_ms >= 40:
                        jet_intensity = "強い"
                    elif wind_speed_ms >= 30:
                        jet_intensity = "中程度"
                    elif wind_speed_ms >= 20:
                        jet_intensity = "弱い"

                result.update({
                    'level': '300hPa',
                    'parameter': 'ジェット気流',
                    'unit': 'm/s',
                    'wind_speed_300hpa': wind_speed_300,
                    'wind_speed_ms': wind_speed_300 / 3.6 if wind_speed_300 is not None else None,
                    'wind_direction_300hpa': wind_dir_300,
                    'geopotential_height_300hpa': geo_height_300,
                    'jet_intensity': jet_intensity,
                    'message': f'ジェット気流強度: {jet_intensity}（偏西風帯の蛇行パターンから7-16日後の気圧配置を予測）'
                })

            elif category == 'height_anomaly_200hpa':
                # 高度偏差解析（200hPa）- ブロッキング高気圧・エゾ梅雨検出
                geo_height_200 = hourly.get('geopotential_height_200hPa', [None])[time_offset]
                wind_speed_200 = hourly.get('wind_speed_200hPa', [None])[time_offset]
                wind_dir_200 = hourly.get('wind_direction_200hPa', [None])[time_offset]

                # 気候値（利尻島付近の200hPa平年値、夏季想定）
                # 実際の平年値は月別・緯度別に要調整
                climatology_200hpa = 12000  # メートル（概算）

                height_anomaly = None
                anomaly_category = "平年並み"
                blocking_detected = False
                blocking_type = None
                ezo_tsuyu_risk = "低"
                persistence_days = 0

                if geo_height_200:
                    height_anomaly = geo_height_200 - climatology_200hpa

                    # 高度偏差の判定（±100m ≈ ±5℃相当）
                    if height_anomaly >= 200:
                        anomaly_category = "極めて高い（強いブロッキング）"
                        blocking_detected = True
                    elif height_anomaly >= 100:
                        anomaly_category = "高い（ブロッキング傾向）"
                        blocking_detected = True
                    elif height_anomaly >= 50:
                        anomaly_category = "やや高い"
                    elif height_anomaly <= -200:
                        anomaly_category = "極めて低い（強い寒気）"
                    elif height_anomaly <= -100:
                        anomaly_category = "低い（寒気優勢）"
                    elif height_anomaly <= -50:
                        anomaly_category = "やや低い"

                    # ブロッキング高気圧の持続性判定（前後2日間の高度偏差を確認）
                    if blocking_detected and time_offset >= 48 and time_offset < len(hourly.get('time', [])) - 48:
                        geo_heights = hourly.get('geopotential_height_200hPa', [])
                        persistent_count = 0

                        # 前後48時間（2日間）の高度偏差を確認
                        for offset in range(time_offset - 48, time_offset + 49, 12):
                            if offset >= 0 and offset < len(geo_heights) and geo_heights[offset]:
                                anomaly = geo_heights[offset] - climatology_200hpa
                                if anomaly >= 100:  # ブロッキング閾値
                                    persistent_count += 1

                        # 12時間間隔で9点以上（4日間のうち4.5日以上）継続していればブロッキング確定
                        if persistent_count >= 7:
                            persistence_days = 5
                            blocking_type = "持続的ブロッキング（5日以上）"
                        elif persistent_count >= 5:
                            persistence_days = 3
                            blocking_type = "準持続的ブロッキング（3-4日）"
                        else:
                            persistence_days = 1
                            blocking_type = "一時的リッジ（1-2日）"

                # エゾ梅雨（蝦夷梅雨）リスク判定：200hPaブロッキング × 850hPa湿潤気団の組み合わせ
                ezo_tsuyu_detected = False
                ezo_tsuyu_message = []
                kelp_drying_impact = []

                if blocking_detected and blocking_type:
                    # 850hPa相当温位を取得して湿潤気団を検出
                    temp_850 = hourly.get('temperature_850hPa', [None])[time_offset]
                    rh_850 = hourly.get('relative_humidity_850hPa', [None])[time_offset]

                    theta_e_850 = None
                    is_moist_airmass = False

                    if temp_850 is not None and rh_850 is not None:
                        # 850hPa相当温位を計算
                        theta_e_850 = calculate_equivalent_potential_temperature_850hpa(temp_850, rh_850, 850.0)

                        # θe ≥ 310Kで湿潤気団と判定
                        if theta_e_850 >= 310:
                            is_moist_airmass = True

                    # エゾ梅雨条件：持続的ブロッキング（3日以上） + 湿潤気団
                    if persistence_days >= 3 and is_moist_airmass:
                        ezo_tsuyu_detected = True
                        ezo_tsuyu_risk = "高"

                        ezo_tsuyu_message.append(
                            f"⚠️ エゾ梅雨パターン検出（発生確率: 高）"
                        )
                        ezo_tsuyu_message.append(
                            f"  ・200hPa持続的ブロッキング高気圧（{persistence_days}日間継続）"
                        )
                        ezo_tsuyu_message.append(
                            f"  ・850hPa湿潤気団（θe={theta_e_850:.1f}K ≥ 310K）"
                        )
                        ezo_tsuyu_message.append(
                            f"  ・停滞前線の形成により、利尻島周辺で曇天・霧雨が{persistence_days+2}～{persistence_days+5}日間継続する可能性"
                        )

                        kelp_drying_impact.append("🌧️ 昆布乾燥への影響（深刻）：")
                        kelp_drying_impact.append(f"  • 今後{persistence_days+2}～{persistence_days+5}日間、乾燥適性「不可」が継続する予想")
                        kelp_drying_impact.append("  • 霧雨・霧により湿度が常時95%以上に維持される")
                        kelp_drying_impact.append("  • 乾燥作業は前線通過後まで待機を強く推奨")
                        kelp_drying_impact.append("  • 既に干している昆布は早急に取り込むことを推奨")

                    elif persistence_days >= 3 and not is_moist_airmass:
                        # ブロッキングはあるが乾燥気団→好天持続の可能性
                        ezo_tsuyu_risk = "低"
                        ezo_tsuyu_message.append(
                            f"✅ ブロッキング高気圧（乾燥型）検出"
                        )
                        ezo_tsuyu_message.append(
                            f"  ・持続的高気圧（{persistence_days}日間）+ 乾燥気団"
                        )
                        ezo_tsuyu_message.append(
                            f"  ・好天が{persistence_days}～{persistence_days+2}日間継続する可能性が高い"
                        )

                        kelp_drying_impact.append("☀️ 昆布乾燥への影響（良好）：")
                        kelp_drying_impact.append(f"  • 今後{persistence_days}～{persistence_days+2}日間、安定した好天が期待できる")
                        kelp_drying_impact.append("  • 乾燥作業に最適な期間（計画的な作業を推奨）")

                    elif is_moist_airmass:
                        # 湿潤気団だがブロッキング弱い→短期的な曇天
                        ezo_tsuyu_risk = "中"
                        ezo_tsuyu_message.append(
                            f"⚠️ 一時的な曇天・降水パターン"
                        )
                        ezo_tsuyu_message.append(
                            f"  ・ブロッキング弱い（{persistence_days}日以下）+ 湿潤気団"
                        )
                        ezo_tsuyu_message.append(
                            f"  ・1-3日間の曇天・降水の可能性（エゾ梅雨には発展しない見込み）"
                        )

                        kelp_drying_impact.append("🌥️ 昆布乾燥への影響（注意）：")
                        kelp_drying_impact.append("  • 短期的な乾燥不適期間（1-3日）")
                        kelp_drying_impact.append("  • 天気回復後に乾燥作業再開可能")

                # 結果を更新
                result.update({
                    'level': '200hPa',
                    'parameter': 'ジオポテンシャル高度偏差',
                    'unit': 'm',
                    'geopotential_height_200hpa': geo_height_200,
                    'climatology': climatology_200hpa,
                    'height_anomaly': height_anomaly,
                    'anomaly_category': anomaly_category,
                    'wind_speed_200hpa': wind_speed_200,
                    'wind_direction_200hpa': wind_dir_200,
                    'blocking_detected': blocking_detected,
                    'blocking_type': blocking_type,
                    'persistence_days': persistence_days,
                    'ezo_tsuyu_detected': ezo_tsuyu_detected,
                    'ezo_tsuyu_risk_level': ezo_tsuyu_risk,
                    'ezo_tsuyu_message': '\n'.join(ezo_tsuyu_message) if ezo_tsuyu_message else None,
                    'kelp_drying_impact': '\n'.join(kelp_drying_impact) if kelp_drying_impact else None,
                    'message': f'高度偏差: {anomaly_category} | エゾ梅雨リスク: {ezo_tsuyu_risk}'
                })

            return jsonify(result)

        else:
            return jsonify({
                'status': 'error',
                'message': f'未対応のカテゴリー: {category}'
            }), 400

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/emagram')
def get_emagram_data():
    """
    簡易エマグラム用の気温・露点温度鉛直プロファイルを取得

    Parameters:
        lat: 緯度
        lon: 経度
        time: 予報時刻オフセット（時間単位、デフォルト0=現在）
        apply_theta_e_correction: θₑ補正を適用（'true'/'false'、デフォルト'false'）
        wind_direction: 風向（度、北を0度）※補正時必須

    Returns:
        pressure_levels: 気圧面リスト（hPa）
        temperature: 各気圧面の気温（℃）
        dewpoint: 各気圧面の露点温度（℃）
        height: 各気圧面の高度（m）
        correction_applied: 補正が適用されたか
        correction_info: 補正情報（適用時のみ）
    """
    try:
        lat = float(request.args.get('lat', 45.242))
        lon = float(request.args.get('lon', 141.242))
        time_offset = int(request.args.get('time', 0))
        apply_correction = request.args.get('apply_theta_e_correction', 'false').lower() == 'true'
        wind_direction = float(request.args.get('wind_direction', 270.0)) if apply_correction else None

        # Get elevation for accurate DEM correction
        elevation = get_elevation(lat, lon)

        # 利用可能な気圧面（1000hPaから上層まで）- 100hPaまで拡張（雲頂高度検出のため）
        pressure_levels = [1000, 975, 950, 925, 900, 850, 800, 700, 600, 500, 400, 300, 250, 200, 150, 100]

        # Open-Meteo Pressure Level APIから気温・露点温度・高度を取得
        url = (
            f"https://api.open-meteo.com/v1/forecast?"
            f"latitude={lat}&longitude={lon}&elevation={elevation}&"
            f"hourly=temperature_1000hPa,dewpoint_1000hPa,geopotential_height_1000hPa,"
            f"temperature_975hPa,dewpoint_975hPa,geopotential_height_975hPa,"
            f"temperature_950hPa,dewpoint_950hPa,geopotential_height_950hPa,"
            f"temperature_925hPa,dewpoint_925hPa,geopotential_height_925hPa,"
            f"temperature_900hPa,dewpoint_900hPa,geopotential_height_900hPa,"
            f"temperature_850hPa,dewpoint_850hPa,geopotential_height_850hPa,"
            f"temperature_800hPa,dewpoint_800hPa,geopotential_height_800hPa,"
            f"temperature_700hPa,dewpoint_700hPa,geopotential_height_700hPa,"
            f"temperature_600hPa,dewpoint_600hPa,geopotential_height_600hPa,"
            f"temperature_500hPa,dewpoint_500hPa,geopotential_height_500hPa,"
            f"temperature_400hPa,dewpoint_400hPa,geopotential_height_400hPa,"
            f"temperature_300hPa,dewpoint_300hPa,geopotential_height_300hPa,"
            f"temperature_250hPa,dewpoint_250hPa,geopotential_height_250hPa,"
            f"temperature_200hPa,dewpoint_200hPa,geopotential_height_200hPa,"
            f"temperature_150hPa,dewpoint_150hPa,geopotential_height_150hPa,"
            f"temperature_100hPa,dewpoint_100hPa,geopotential_height_100hPa&"
            f"timezone=Asia/Tokyo&forecast_days=7"
        )

        response = requests.get(url, timeout=15)
        response.raise_for_status()
        data = response.json()

        hourly = data.get('hourly', {})

        # 各気圧面のデータを抽出
        profile = {
            'pressure': [],
            'temperature': [],
            'dewpoint': [],
            'height': [],
            'time': hourly.get('time', [])[time_offset] if hourly.get('time') else None
        }

        for p in pressure_levels:
            temp_key = f'temperature_{p}hPa'
            dewpoint_key = f'dewpoint_{p}hPa'
            height_key = f'geopotential_height_{p}hPa'

            temp = hourly.get(temp_key, [None])[time_offset] if hourly.get(temp_key) else None
            dewpoint = hourly.get(dewpoint_key, [None])[time_offset] if hourly.get(dewpoint_key) else None
            height = hourly.get(height_key, [None])[time_offset] if hourly.get(height_key) else None

            # データが存在する気圧面のみ追加
            if temp is not None and dewpoint is not None and height is not None:
                profile['pressure'].append(p)
                profile['temperature'].append(temp)
                profile['dewpoint'].append(dewpoint)
                profile['height'].append(height)

        # θₑ補正の適用
        correction_info = None
        if apply_correction and wind_direction is not None:
            try:
                # 干場データベースを読み込み
                spots_df = pd.read_csv(CSV_FILE)

                # 風上地点を選定
                windward_spot = theta_e_corrector.select_windward_spot(
                    lat, lon, wind_direction, spots_df
                )

                if windward_spot is not None:
                    # 風上地点のエマグラムデータを取得
                    windward_url = (
                        f"https://api.open-meteo.com/v1/forecast?"
                        f"latitude={windward_spot['lat']}&longitude={windward_spot['lon']}&"
                        f"hourly=temperature_1000hPa,dewpoint_1000hPa,"
                        f"temperature_850hPa,dewpoint_850hPa&"
                        f"timezone=Asia/Tokyo&forecast_days=7"
                    )
                    windward_response = requests.get(windward_url, timeout=10)
                    windward_data = windward_response.json().get('hourly', {})

                    # 参照地点（鴛泊）のデータを取得（上層用）
                    ref_url = (
                        f"https://api.open-meteo.com/v1/forecast?"
                        f"latitude=45.242&longitude=141.242&"
                        f"hourly=temperature_500hPa,dewpoint_500hPa,"
                        f"temperature_400hPa,dewpoint_400hPa,"
                        f"temperature_300hPa,dewpoint_300hPa,"
                        f"temperature_250hPa,dewpoint_250hPa,"
                        f"temperature_200hPa,dewpoint_200hPa&"
                        f"timezone=Asia/Tokyo&forecast_days=7"
                    )
                    ref_response = requests.get(ref_url, timeout=10)
                    ref_data = ref_response.json().get('hourly', {})

                    # 補正を適用
                    corrected_temps = []
                    corrected_dewpoints = []

                    for i, p in enumerate(profile['pressure']):
                        api_temp = profile['temperature'][i]
                        api_dewpoint = profile['dewpoint'][i]

                        if p >= 850:
                            # 下層: 風上のθₑを計算
                            w_temp = windward_data.get(f'temperature_{p}hPa', [None])[time_offset]
                            w_dewpoint = windward_data.get(f'dewpoint_{p}hPa', [None])[time_offset]

                            if w_temp is not None and w_dewpoint is not None:
                                windward_theta_e = theta_e_corrector.equivalent_potential_temperature(
                                    w_temp, w_dewpoint, p
                                )
                                # 風上のRHを計算
                                es = theta_e_corrector.saturation_vapor_pressure(w_temp)
                                e = theta_e_corrector.saturation_vapor_pressure(w_dewpoint)
                                windward_rh = e / es if es > 0 else 0.7

                                # 補正適用
                                corr_temp, corr_dewpoint = theta_e_corrector.apply_hybrid_correction(
                                    p, windward_theta_e, windward_rh,
                                    api_temp, api_dewpoint,
                                    api_temp, api_dewpoint  # 下層では参照不要
                                )
                                corrected_temps.append(corr_temp)
                                corrected_dewpoints.append(corr_dewpoint)
                            else:
                                corrected_temps.append(api_temp)
                                corrected_dewpoints.append(api_dewpoint)

                        elif p < 500:
                            # 上層: 参照地点の値を使用
                            ref_temp = ref_data.get(f'temperature_{p}hPa', [None])[time_offset]
                            ref_dewpoint = ref_data.get(f'dewpoint_{p}hPa', [None])[time_offset]

                            if ref_temp is not None and ref_dewpoint is not None:
                                corrected_temps.append(ref_temp)
                                corrected_dewpoints.append(ref_dewpoint)
                            else:
                                corrected_temps.append(api_temp)
                                corrected_dewpoints.append(api_dewpoint)

                        else:
                            # 中層: 簡易的に風上データを使用
                            corrected_temps.append(api_temp)
                            corrected_dewpoints.append(api_dewpoint)

                    # 補正データで置き換え
                    profile['temperature'] = corrected_temps
                    profile['dewpoint'] = corrected_dewpoints

                    correction_info = {
                        'windward_spot': {
                            'name': windward_spot.get('name', 'Unknown'),
                            'lat': float(windward_spot['lat']),
                            'lon': float(windward_spot['lon'])
                        },
                        'wind_direction': wind_direction,
                        'method': 'Hybrid theta-e correction (lower: 100%, middle: decay, upper: reference)'
                    }
                else:
                    correction_info = {'error': 'No suitable windward spot found'}

            except Exception as e:
                correction_info = {'error': str(e)}

        result = {
            'status': 'success',
            'data': profile,
            'location': {'lat': lat, 'lon': lon},
            'message': f'{len(profile["pressure"])}気圧面のデータを取得（{profile["time"]}）',
            'correction_applied': apply_correction and correction_info is not None
        }

        if correction_info:
            result['correction_info'] = correction_info

        return jsonify(result)

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/forecast_calibration')
def get_forecast_calibration():
    """
    予報補正情報を取得（等値線解析の信頼度）

    Returns:
        weights: 500hPa渦度と700hPa鉛直流の信頼度（0-1）
    """
    try:
        import os
        import json

        # ERA5等値線相関データを読み込み
        correlation_file = os.path.join(BASE_DIR, 'era5_contour_correlation_results.json')

        if os.path.exists(correlation_file):
            with open(correlation_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # 相関係数から信頼度を計算（絶対値を0-1にマッピング）
            correlations = data.get('correlations', {})
            vorticity_corr = abs(correlations.get('cos_angle_vs_vorticity_500hPa_spatial', 0))
            omega_corr = abs(correlations.get('cos_angle_vs_omega_700hPa', 0))

            # 信頼度スコア: 相関が0.3以上で有効、0.5以上で高信頼
            vorticity_weight = min(1.0, vorticity_corr * 2.0)  # 0.5で満点
            omega_weight = min(1.0, omega_corr * 2.0)

        else:
            # デフォルト値（中程度の信頼度）
            vorticity_weight = 0.5
            omega_weight = 0.5

        return jsonify({
            'status': 'success',
            'weights': {
                'vorticity_500hPa': round(vorticity_weight, 3),
                'omega_700hPa': round(omega_weight, 3)
            },
            'source': 'era5_contour_correlation_results.json' if os.path.exists(correlation_file) else 'default'
        })

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/validation/accuracy')
def get_forecast_accuracy():
    """
    予報精度検証データを取得（仕様書 lines 356-429）

    アメダス実測データと予報データを比較して精度を検証
    """
    try:
        days_back = int(request.args.get('days', 30))
        spot_name = request.args.get('spot', 'H_1631_1434')  # デフォルトは神居

        # アメダスデータディレクトリの確認
        import os
        from datetime import datetime, timedelta
        import json
        import glob

        amedas_dir = AMEDAS_DATA_DIR
        forecast_dir = FORECAST_HISTORY_DIR

        if not os.path.exists(amedas_dir):
            os.makedirs(amedas_dir, exist_ok=True)

        # 過去N日分の検証データを収集
        validation_results = []
        accuracy_by_day = {f'{i}_day': {'errors': [], 'count': 0} for i in range(1, 8)}

        end_date = datetime.now(tz=JST)
        start_date = end_date - timedelta(days=days_back)

        for day_offset in range(days_back):
            check_date = start_date + timedelta(days=day_offset)
            date_str = check_date.strftime('%Y%m%d')

            # アメダス実測データの読み込み
            amedas_file = os.path.join(amedas_dir, f'amedas_11151_{date_str}.json')

            if os.path.exists(amedas_file):
                try:
                    with open(amedas_file, 'r', encoding='utf-8') as f:
                        amedas_data = json.load(f)

                    # 実測値から統計を計算
                    temps = [h.get('temp') for h in amedas_data.get('hourly', []) if h.get('temp') is not None]
                    humidities = [h.get('humidity') for h in amedas_data.get('hourly', []) if h.get('humidity') is not None]
                    winds = [h.get('wind_speed') for h in amedas_data.get('hourly', []) if h.get('wind_speed') is not None]
                    precips = [h.get('precipitation') for h in amedas_data.get('hourly', []) if h.get('precipitation') is not None]

                    actual = {
                        'max_temp': max(temps) if temps else None,
                        'min_temp': min(temps) if temps else None,
                        'min_humidity': min(humidities) if humidities else None,
                        'avg_wind': sum(winds) / len(winds) if winds else None,
                        'total_precip': sum(precips) if precips else None
                    }

                    # 1-6日前の予報データと比較
                    for forecast_days_before in range(1, 7):
                        forecast_date = check_date - timedelta(days=forecast_days_before)
                        forecast_date_str = forecast_date.strftime('%Y%m%d')
                        target_date_str = check_date.strftime('%Y%m%d')

                        forecast_file = os.path.join(forecast_dir, spot_name, f'forecast_{forecast_date_str}_for_{target_date_str}.json')

                        if os.path.exists(forecast_file):
                            with open(forecast_file, 'r', encoding='utf-8') as f:
                                forecast_data = json.load(f)

                            # 予報誤差計算
                            errors = {}
                            if actual['max_temp'] and forecast_data.get('max_temp'):
                                errors['temp'] = abs(actual['max_temp'] - forecast_data['max_temp'])
                            if actual['min_humidity'] and forecast_data.get('min_humidity'):
                                errors['humidity'] = abs(actual['min_humidity'] - forecast_data['min_humidity'])
                            if actual['avg_wind'] and forecast_data.get('avg_wind'):
                                errors['wind'] = abs(actual['avg_wind'] - forecast_data['avg_wind'])

                            day_key = f'{forecast_days_before}_day'
                            if errors:
                                accuracy_by_day[day_key]['errors'].append(errors)
                                accuracy_by_day[day_key]['count'] += 1

                except Exception as e:
                    print(f"Error processing {amedas_file}: {e}")
                    continue

        # 精度指標を計算
        accuracy_summary = {}
        for day_key, data in accuracy_by_day.items():
            if data['count'] > 0:
                errors = data['errors']

                temp_errors = [e['temp'] for e in errors if 'temp' in e]
                humidity_errors = [e['humidity'] for e in errors if 'humidity' in e]
                wind_errors = [e['wind'] for e in errors if 'wind' in e]

                mae_temp = sum(temp_errors) / len(temp_errors) if temp_errors else 0
                mae_humidity = sum(humidity_errors) / len(humidity_errors) if humidity_errors else 0
                mae_wind = sum(wind_errors) / len(wind_errors) if wind_errors else 0

                # 総合精度スコア（誤差が小さいほど高得点）
                # 気温: MAE < 2°C で90点以上、湿度: MAE < 10% で90点以上、風速: MAE < 2m/s で90点以上
                temp_score = max(0, 100 - mae_temp * 10)
                humidity_score = max(0, 100 - mae_humidity * 2)
                wind_score = max(0, 100 - mae_wind * 10)
                overall_score = (temp_score + humidity_score + wind_score) / 3

                accuracy_summary[day_key] = {
                    'accuracy': round(overall_score, 1),
                    'mae_temp': round(mae_temp, 1),
                    'mae_humidity': round(mae_humidity, 1),
                    'mae_wind': round(mae_wind, 1),
                    'sample_count': data['count']
                }
            else:
                # データがない場合は仕様書の理論値を使用
                day_num = int(day_key.split('_')[0])
                theoretical_accuracy = max(50, 100 - day_num * 7)
                accuracy_summary[day_key] = {
                    'accuracy': theoretical_accuracy,
                    'mae_temp': 1.0 + day_num * 0.5,
                    'mae_humidity': 5 + day_num * 3,
                    'mae_wind': 1.0 + day_num * 0.5,
                    'sample_count': 0,
                    'note': '理論値（実測データ不足）'
                }

        total_samples = sum(data['count'] for data in accuracy_by_day.values())

        # ── 記録ベースの判定正誤率（feedback_log.csv） ──────────────────────────
        judgment_accuracy = {}
        judgment_overall = None
        try:
            if os.path.exists(FEEDBACK_FILE):
                fb_df = pd.read_csv(FEEDBACK_FILE)
                if not fb_df.empty and 'days_ahead' in fb_df.columns:
                    # days_ahead ごとに正答率を集計
                    for da in sorted(fb_df['days_ahead'].dropna().unique()):
                        da = int(da)
                        subset = fb_df[fb_df['days_ahead'] == da]
                        total = len(subset)
                        if total == 0:
                            continue
                        correct = int(subset['judgment_correct'].sum())
                        tp = int(((subset['actual_label'] == '可') & (subset['forecast_label'] == '可')).sum())
                        fp = int(((subset['actual_label'] == '不可') & (subset['forecast_label'] == '可')).sum())
                        fn = int(((subset['actual_label'] == '可') & (subset['forecast_label'] == '不可')).sum())
                        tn = int(((subset['actual_label'] == '不可') & (subset['forecast_label'] == '不可')).sum())
                        judgment_accuracy[f'{da}_day'] = {
                            'correct': correct,
                            'total': total,
                            'hit_rate': round(correct / total * 100, 1),
                            'true_positive': tp,
                            'false_positive': fp,
                            'false_negative': fn,
                            'true_negative': tn,
                        }

                    all_total = len(fb_df)
                    all_correct = int(fb_df['judgment_correct'].sum()) if all_total > 0 else 0
                    judgment_overall = {
                        'total': all_total,
                        'correct': all_correct,
                        'hit_rate': round(all_correct / all_total * 100, 1) if all_total > 0 else None,
                    }
        except Exception as _e:
            print(f'[accuracy] feedback_log read error: {_e}')
        # ── 降水予報精度（feedback_log.csv の precip 列） ─────────────────────
        precip_accuracy = {}
        precip_overall  = None
        try:
            if os.path.exists(FEEDBACK_FILE):
                fb_df_p = pd.read_csv(FEEDBACK_FILE)
                if not fb_df_p.empty and 'precip_forecast_correct' in fb_df_p.columns:
                    p_valid = fb_df_p.dropna(subset=['precip_forecast_correct',
                                                      'actual_rain_0416', 'forecast_rain'])
                    if not p_valid.empty:
                        total_p  = len(p_valid)
                        correct_p = int(p_valid['precip_forecast_correct'].sum())
                        # 降水なし予報 → 実際も降水なし（最重要: 干せた日の裏付け）
                        no_rain_fc   = p_valid[p_valid['forecast_rain'] == False]
                        no_rain_ok   = int((no_rain_fc['actual_rain_0416'] == False).sum())
                        # 降水あり予報 → 実際も降水あり
                        rain_fc      = p_valid[p_valid['forecast_rain'] == True]
                        rain_ok      = int((rain_fc['actual_rain_0416'] == True).sum())
                        # 見逃し: 「降水なし予報」なのに実際は雨 → 昆布が濡れたリスク
                        missed_rain  = int((no_rain_fc['actual_rain_0416'] == True).sum())
                        # 空振り: 「降水あり予報」なのに晴れ → 干す機会を逃した
                        false_alarm  = int((rain_fc['actual_rain_0416'] == False).sum())
                        precip_overall = {
                            'total':               total_p,
                            'correct':             correct_p,
                            'accuracy_pct':        round(correct_p / total_p * 100, 1),
                            'no_rain_forecast_cnt':     len(no_rain_fc),
                            'no_rain_confirmed_cnt':    no_rain_ok,
                            'no_rain_precision_pct':    round(no_rain_ok / len(no_rain_fc) * 100, 1)
                                                        if len(no_rain_fc) > 0 else None,
                            'rain_forecast_cnt':        len(rain_fc),
                            'rain_confirmed_cnt':       rain_ok,
                            'missed_rain_cnt':          missed_rain,   # 危険: 昆布が濡れた可能性
                            'false_alarm_cnt':          false_alarm,   # 機会損失: 晴れなのに干さなかった
                            'window': '04:00-16:00 JST 実測（Open-Meteo Archive 沓形局）',
                        }
        except Exception as _pe:
            print(f'[accuracy] precip feedback error: {_pe}')
        # ──────────────────────────────────────────────────────────────────────

        return jsonify({
            'status': 'success',
            'spot': spot_name,
            'period': f'Past {days_back} days',
            'accuracy_by_forecast_day': accuracy_summary,
            'overall_metrics': {
                'total_validations': total_samples,
                'data_coverage': f'{total_samples}/{days_back * 6} days',
                'average_accuracy': round(sum(s['accuracy'] for s in accuracy_summary.values()) / 7, 1)
            },
            'judgment_accuracy_by_day': judgment_accuracy,
            'judgment_accuracy_overall': judgment_overall,
            'precip_forecast_accuracy': precip_overall,   # 降水有無の二値予報精度（最重要）
            'data_source': '沓形アメダス(11151) vs 予報データ比較 + hoshiba_records.csv 実記録',
            'methodology': ('(1) 気温・湿度・風速のMAEによる数値精度スコア '
                            '(2) 干せた/干せないの判定正誤率（feedback_log.csv）'
                            '(3) 降水有無の二値予報精度（04:00-16:00 実測vs予報）'),
            'note': 'アメダスデータがない期間は仕様書の理論精度値を使用'
        })

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


def _collect_amedas_from_openmeteo(target_date_str):
    """Open-Meteo Archive から両アメダス局の実測値を取得し Redis（主）＋ローカル（副）に保存する。

    Redis key: amedas:obs:{station_id}:{YYYYMMDD}  TTL 90日
    Returns True on success, False on failure.
    """
    STATIONS = [
        {'id': '11151', 'lat': 45.1783, 'lon': 141.1383, 'name': '沓形'},
        {'id': '11311', 'lat': 45.2417, 'lon': 141.1867, 'name': '本泊'},
    ]
    os.makedirs(AMEDAS_DATA_DIR, exist_ok=True)
    success = True
    for st in STATIONS:
        redis_key = f'amedas:obs:{st["id"]}:{target_date_str}'

        # ── Redis にすでにあればスキップ ─────────────────────────────────────
        if _obs_redis_get(redis_key) is not None:
            app.logger.info('[amedas] %s already in Redis, skip fetch', redis_key)
            continue

        # ── ローカルファイルから Redis へ移行（デプロイ前収集分を救済） ────────
        filepath = os.path.join(AMEDAS_DATA_DIR, f'amedas_{st["id"]}_{target_date_str}.json')
        if os.path.exists(filepath):
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    record = json.load(f)
                _obs_redis_set(redis_key, record)
                app.logger.info('[amedas] migrated local → Redis: %s', redis_key)
                continue
            except Exception:
                pass  # 読み込み失敗なら API から再取得

        # ── Open-Meteo Archive API から取得 ──────────────────────────────────
        url = (
            f'https://archive-api.open-meteo.com/v1/archive'
            f'?latitude={st["lat"]}&longitude={st["lon"]}'
            f'&start_date={target_date_str[:4]}-{target_date_str[4:6]}-{target_date_str[6:]}'
            f'&end_date={target_date_str[:4]}-{target_date_str[4:6]}-{target_date_str[6:]}'
            f'&hourly=temperature_2m,relative_humidity_2m,wind_speed_10m,precipitation'
            f'&timezone=Asia%2FTokyo'
        )
        try:
            import urllib.request
            with urllib.request.urlopen(url, timeout=15) as resp:
                data = json.loads(resp.read().decode())
            hourly = data.get('hourly', {})
            times   = hourly.get('time', [])
            temps   = hourly.get('temperature_2m', [])
            humids  = hourly.get('relative_humidity_2m', [])
            winds   = hourly.get('wind_speed_10m', [])
            precips = hourly.get('precipitation', [])
            valid_h = [h for h in humids  if h is not None]
            valid_w = [w for w in winds   if w is not None]
            valid_p = [p for p in precips if p is not None]
            record = {
                'date':         f'{target_date_str[:4]}-{target_date_str[4:6]}-{target_date_str[6:]}',
                'station_id':   st['id'],
                'station_name': st['name'],
                'hourly': [
                    {'time': t, 'temperature': te, 'humidity': hu,
                     'wind_speed': wi, 'precipitation': pr}
                    for t, te, hu, wi, pr in zip(times, temps, humids, winds, precips)
                ],
                'daily_summary': {
                    'min_humidity':        min(valid_h) if valid_h else None,
                    'avg_wind':            round(sum(valid_w) / len(valid_w), 2) if valid_w else None,
                    'total_precipitation': round(sum(valid_p), 2) if valid_p else None,
                },
                'collected_at': datetime.now(tz=JST).isoformat(),
            }
            # Redis に保存（主）
            _obs_redis_set(redis_key, record)
            # ローカルにも保存（副：ローカル確認用）
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(record, f, ensure_ascii=False)
            app.logger.info('[amedas] saved %s → Redis + local', redis_key)
        except Exception as e:
            app.logger.error('[amedas] fetch error %s %s: %s', st['id'], target_date_str, e)
            success = False
    return success


@app.route('/api/collect_amedas')
def collect_amedas():
    """Manually trigger amedas data collection for one or more past days.

    Query params:
      days (int, default 1): how many past days to collect (1 = yesterday only)
    """
    days = int(request.args.get('days', 1))
    days = min(days, 90)  # cap at 90 days to avoid abuse
    results = []
    for i in range(1, days + 1):
        target = (datetime.now(tz=JST) - timedelta(days=i)).strftime('%Y%m%d')
        ok = _collect_amedas_from_openmeteo(target)
        compared = 0
        if ok:
            compared = _auto_compare_precip_forecast(target)
        results.append({'date': target, 'success': ok, 'feedback_rows': compared})
    return jsonify({'status': 'ok', 'results': results})


def _record_nowcast_snapshot() -> None:
    """全干場（334地点）のナウキャスト降水量を Redis にスナップショットとして蓄積する。

    16:00 / 01:30 / 03:00 JST の各バックグラウンドスレッドから呼ばれる。
    Redis key: nowcast:daily:{YYYYMMDD}
      → [{time, basetime, any_rain, max_precip_mmh, spots:{name: mm_h}}, ...]
    TTL: 90日

    重複スナップショット防止: nowcast:snap_done:{YYYYMMDD}:{HHMM} を Redis NX で確保。
    """
    try:
        result = _fetch_nowcast_precip_rishiri()
        if result is None:
            app.logger.warning('[nowcast] snapshot skipped — fetch returned None')
            return

        now      = datetime.now(tz=JST)
        date_str = now.strftime('%Y%m%d')
        time_str = now.strftime('%H:%M')

        # NX で重複防止（同分内に複数ワーカーが呼んでも1回のみ記録）
        rest_url = os.environ.get('UPSTASH_REDIS_REST_URL', '').strip().rstrip('/')
        token    = os.environ.get('UPSTASH_REDIS_REST_TOKEN', '')
        if rest_url and token:
            try:
                dedup_key = f'nowcast:snap_done:{date_str}:{time_str}'
                r = requests.post(
                    f'{rest_url}/pipeline',
                    headers={'Authorization': f'Bearer {token}',
                             'Content-Type': 'application/json'},
                    json=[['SET', dedup_key, '1', 'NX', 'EX', '3600']],
                    timeout=3,
                )
                results = r.json()
                if isinstance(results, list) and results and results[0].get('result') != 'OK':
                    app.logger.info('[nowcast] snapshot dedup skip %s %s', date_str, time_str)
                    return
            except Exception:
                pass  # dedup 失敗なら記録を続行

        key      = f'nowcast:daily:{date_str}'
        existing = _obs_redis_get(key) or []
        existing.append({
            'time':           time_str,
            'basetime':       result.get('basetime'),
            'any_rain':       result.get('any_rain', False),
            'max_precip_mmh': result.get('max_precip_mmh', 0.0),
            'spots':          result.get('spots', {}),
        })
        _obs_redis_set(key, existing)
        app.logger.info('[nowcast] snapshot saved %d spots at %s (key=%s)',
                        len(result.get('spots', {})), time_str, key)
    except Exception as e:
        app.logger.error('[nowcast] snapshot error: %s', e)


def _daily_amedas_collection():
    """Background thread: collect yesterday's amedas data once a day at 03:00 JST."""
    import time
    from datetime import timedelta
    while True:
        now = datetime.now(tz=JST)
        # Target 03:00 JST (same timezone the app runs in)
        next_run = now.replace(hour=3, minute=0, second=0, microsecond=0)
        if now >= next_run:
            next_run = next_run + timedelta(days=1)
        time.sleep((next_run - now).total_seconds())
        yesterday = (datetime.now(tz=JST) - timedelta(days=1)).strftime('%Y%m%d')
        ok = _collect_amedas_from_openmeteo(yesterday)
        if ok:
            _auto_compare_precip_forecast(yesterday)
        _record_nowcast_snapshot()  # 03:00 JST ナウキャストスナップショット


def _auto_compare_precip_forecast(date_str: str, station_id: str = '11151') -> int:
    """実測降水量（04:00-16:00）と予報降水量を自動照合し feedback_log.csv に記録する。

    毎日 _daily_amedas_collection() から呼ばれる（03:00 JST）。
    手動で /api/collect_amedas?days=N を叩いた後にも自動実行される。

    処理フロー:
    1. amedas_data/amedas_{station_id}_{date_str}.json を読む
    2. 04:00-16:00 JST の時間帯の降水量を合計する（昆布干し時間帯）
    3. 対象日に予報を保存した全干場の forecast_history/ を走査
    4. 予報降水量 vs 実測降水量（有雨/無雨）の正誤を判定
    5. hoshiba_records.csv と照合して干し記録の有無を付加
    6. feedback_log.csv を upsert（date + spot + days_ahead がキー）

    Args:
        date_str: 対象日 YYYYMMDD
        station_id: アメダス局ID（デフォルト沓形 11151）
    Returns:
        新規または更新したフィードバック行数
    """
    import glob as _glob
    import csv as _csv

    # ── 0. 実測データ取得（Redis 優先 → ローカルファイル fallback） ──────────
    redis_key = f'amedas:obs:{station_id}:{date_str}'
    amedas = _obs_redis_get(redis_key)
    if amedas is None:
        amedas_path = os.path.join(AMEDAS_DATA_DIR, f'amedas_{station_id}_{date_str}.json')
        if not os.path.exists(amedas_path):
            app.logger.warning('[auto_compare] %s not in Redis or local, skip', date_str)
            return 0
        try:
            with open(amedas_path, 'r', encoding='utf-8') as f:
                amedas = json.load(f)
        except Exception as e:
            app.logger.error('[auto_compare] read error %s: %s', amedas_path, e)
            return 0

    # ── 1. 実測降水量を抽出（04:00-16:00 JST） ─────────────────────────────

    hourly = amedas.get('hourly', [])
    # "YYYY-MM-DDTHH:MM" 形式。04:00〜16:00 JST（時刻文字列のHH部分で判定）
    precip_0416 = [
        h.get('precipitation') or 0.0
        for h in hourly
        if h.get('time', '')[-5:] >= '04:00' and h.get('time', '')[-5:] <= '16:00'
    ]
    actual_precip_0416 = round(sum(precip_0416), 2)
    actual_precip_total = amedas.get('daily_summary', {}).get('total_precipitation') or 0.0
    actual_rain_0416 = actual_precip_0416 > 0.0

    # ── 2. 予報履歴を収集（Redis 優先 → ローカルファイル fallback） ────────
    # Redis key pattern: forecast:hist:{spot_name}:{date_str}
    # (spot_name は H_/A_/R_ 形式で : を含まない)
    fc_entries: list[tuple[str, dict]] = []  # [(spot_name, record), ...]

    redis_keys = _obs_redis_scan_keys(f'forecast:hist:*:{date_str}')
    for rk in redis_keys:
        parts = rk.split(':')
        if len(parts) < 4:
            continue
        spot_from_key = parts[2]
        hist = _obs_redis_get(rk) or []
        for entry in hist:
            fc_entries.append((spot_from_key, entry))

    if not fc_entries:
        # ローカルファイル fallback（ローカル開発環境またはRedis未設定時）
        fc_pattern = os.path.join(FORECAST_HISTORY_DIR, '*',
                                  f'forecast_*_for_{date_str}.json')
        for fc_file in _glob.glob(fc_pattern):
            try:
                spot_name = os.path.basename(os.path.dirname(fc_file))
                with open(fc_file, 'r', encoding='utf-8') as f:
                    fc_entries.append((spot_name, json.load(f)))
            except Exception:
                pass

    if not fc_entries:
        app.logger.warning('[auto_compare] no forecast data for %s (Redis + local)', date_str)
        return 0

    # ── 3. 干し記録（records）を事前に日付で絞り込む ─────────────────────
    target_date_fmt = f'{date_str[:4]}-{date_str[4:6]}-{date_str[6:]}'  # YYYY-MM-DD
    records_on_date: dict[str, str] = {}  # spot_name → result
    try:
        if os.path.exists(RECORD_FILE):
            with open(RECORD_FILE, 'r', encoding='utf-8') as rf:
                for row in _csv.DictReader(rf):
                    if row.get('date') == target_date_fmt and row.get('name'):
                        records_on_date[row['name']] = row.get('result', '')
    except Exception as re:
        app.logger.warning('[auto_compare] records read error: %s', re)

    # ── 4. 既存 feedback_log を読み込む ──────────────────────────────────
    if os.path.exists(FEEDBACK_FILE):
        try:
            fb_df = pd.read_csv(FEEDBACK_FILE)
            for col in FEEDBACK_COLUMNS:
                if col not in fb_df.columns:
                    fb_df[col] = None
        except Exception:
            fb_df = pd.DataFrame(columns=FEEDBACK_COLUMNS)
    else:
        fb_df = pd.DataFrame(columns=FEEDBACK_COLUMNS)

    # ── 5. 予報エントリごとに照合 ─────────────────────────────────────────
    now_jst = datetime.now(tz=JST).strftime('%Y-%m-%dT%H:%M:%S+09:00')
    updated = 0
    new_rows = []
    spot_metadata = _load_spot_metadata_map()

    for spot_name, fc in fc_entries:
        try:
            spot_meta = spot_metadata.get(spot_name, {})
            forecast_date_str = fc.get('forecast_date', '')
            try:
                fc_dt = datetime.strptime(forecast_date_str, '%Y%m%d')
                tg_dt = datetime.strptime(date_str, '%Y%m%d')
                days_ahead = (tg_dt - fc_dt).days
            except ValueError:
                days_ahead = None

            # precipitation_0416（04:00-16:00積算）を優先。旧データは24時間積算で代替
            fc_precip = fc.get('precipitation_0416', fc.get('precipitation')) or 0.0
            fc_rain   = fc_precip > 0.0
            fc_score  = fc.get('drying_score')
            fc_suit   = fc.get('suitability', '')
            fc_label  = _suitability_to_label(fc_suit)
            precip_ok = (fc_rain == actual_rain_0416)

            # 干し記録があれば付加
            rec_result   = records_on_date.get(spot_name)
            actual_label = _result_to_label(rec_result) if rec_result else None
            judg_correct = (actual_label == fc_label) if actual_label else None
            has_record   = rec_result is not None

            # upsert: (date, spot_name, days_ahead) が一致する行を更新
            mask = (
                (fb_df['date']       == target_date_fmt) &
                (fb_df['spot_name']  == spot_name)       &
                (fb_df['days_ahead'] == days_ahead)
            )
            if mask.any():
                fb_df.loc[mask, 'actual_precip_0416_mm']   = actual_precip_0416
                fb_df.loc[mask, 'actual_precip_total_mm']  = actual_precip_total
                fb_df.loc[mask, 'actual_rain_0416']        = actual_rain_0416
                fb_df.loc[mask, 'forecast_precip_mm']      = fc_precip
                fb_df.loc[mask, 'forecast_rain']           = fc_rain
                fb_df.loc[mask, 'precip_forecast_correct'] = precip_ok
                fb_df.loc[mask, 'data_source']             = 'openmeteo_archive'
                fb_df.loc[mask, 'recorded_at']             = now_jst
                for meta_col in ('town', 'district', 'buraku'):
                    if spot_meta.get(meta_col) is not None:
                        fb_df.loc[mask, meta_col] = spot_meta[meta_col]
                if has_record:
                    fb_df.loc[mask, 'actual_result']      = rec_result
                    fb_df.loc[mask, 'actual_label']       = actual_label
                    fb_df.loc[mask, 'judgment_correct']   = judg_correct
                    fb_df.loc[mask, 'has_drying_record']  = True
                updated += 1
            else:
                new_rows.append({
                    'date':                   target_date_fmt,
                    'spot_name':              spot_name,
                    'days_ahead':             days_ahead,
                    'town':                   spot_meta.get('town'),
                    'district':               spot_meta.get('district'),
                    'buraku':                 spot_meta.get('buraku'),
                    'actual_precip_0416_mm':  actual_precip_0416,
                    'actual_precip_total_mm': actual_precip_total,
                    'actual_rain_0416':       actual_rain_0416,
                    'forecast_precip_mm':     fc_precip,
                    'forecast_rain':          fc_rain,
                    'precip_forecast_correct': precip_ok,
                    'forecast_score':         fc_score,
                    'forecast_suitability':   fc_suit,
                    'forecast_label':         fc_label,
                    'actual_result':          rec_result,
                    'actual_label':           actual_label,
                    'judgment_correct':       judg_correct,
                    'has_drying_record':      has_record,
                    'data_source':            'openmeteo_archive',
                    'recorded_at':            now_jst,
                })

        except Exception as fe:
            app.logger.error('[auto_compare] parse error for %s: %s', spot_name, fe)

    if new_rows:
        fb_df = pd.concat([fb_df, pd.DataFrame(new_rows)], ignore_index=True)
        updated += len(new_rows)

    fb_df.to_csv(FEEDBACK_FILE, index=False, encoding='utf-8')
    app.logger.info('[auto_compare] %s: actual_precip_0416=%.2fmm rain=%s | %d rows written',
                    date_str, actual_precip_0416, actual_rain_0416, updated)
    return updated


def _fetch_jma_amedas_realtime() -> dict | None:
    """JMA bosai APIから利尻島アメダスのリアルタイム気象データを取得。

    取得項目: 10分降水量・1時間降水量・気温・湿度・風速・風向
    キャッシュ: 10分間有効（JMAの更新間隔に合わせる）
    返り値: {'observed_at': str, 'stations': {code: {...}}} または None
    """
    import urllib.request as _ur

    # キャッシュチェック
    now_ts = datetime.now(tz=JST).timestamp()
    if (_AMEDAS_RT_CACHE['data'] is not None and
            _AMEDAS_RT_CACHE['fetched_at'] is not None and
            now_ts - _AMEDAS_RT_CACHE['fetched_at'] < _AMEDAS_RT_CACHE_TTL):
        return _AMEDAS_RT_CACHE['data']

    try:
        # 1. 最新観測時刻を取得
        with _ur.urlopen(JMA_AMEDAS_LATEST_URL, timeout=10) as r:
            latest_str = r.read().decode().strip()   # 例: "2026-05-31T12:20:00+09:00"

        # ISO文字列 → YYYYMMDDHHmmss
        dt_clean = latest_str[:19].replace('-', '').replace('T', '').replace(':', '')
        timestamp = dt_clean  # "20260531122000"

        # 2. 全局マップデータを取得
        map_url = JMA_AMEDAS_MAP_URL.format(timestamp=timestamp)
        with _ur.urlopen(map_url, timeout=10) as r:
            all_data = json.loads(r.read().decode())

        # 3. 利尻島地点のみ抽出
        def _v(field, d):
            """[value, flag] 形式のリストから値を取り出す"""
            v = d.get(field)
            return v[0] if isinstance(v, list) and len(v) > 0 else None

        stations_out = {}
        for code, info in RISHIRI_AMEDAS_STATIONS.items():
            d = all_data.get(code)
            if d is None:
                continue
            wd_code = _v('windDirection', d)
            stations_out[code] = {
                'name':               info['name'],
                'lat':                info['lat'],
                'lon':                info['lon'],
                'temp_c':             _v('temp', d),
                'humidity_pct':       _v('humidity', d),
                'wind_speed_ms':      _v('wind', d),
                'wind_dir_code':      wd_code,
                'wind_dir':           _JMA_WIND_DIR.get(wd_code) if wd_code is not None else None,
                'precip_10m_mm':      _v('precipitation10m', d),
                'precip_1h_mm':       _v('precipitation1h', d),
                'precip_3h_mm':       _v('precipitation3h', d),
                'precip_24h_mm':      _v('precipitation24h', d),
                'sunshine_10m_min':   _v('sun10m', d),
                'sunshine_1h_min':    _v('sun1h', d),
            }

        result = {'observed_at': latest_str, 'stations': stations_out}
        _AMEDAS_RT_CACHE['data'] = result
        _AMEDAS_RT_CACHE['fetched_at'] = now_ts
        return result

    except Exception as e:
        print(f'[JMA amedas realtime] fetch error: {e}')
        return None


@app.route('/api/amedas/realtime')
def get_amedas_realtime():
    """利尻島アメダス（沓形・本泊）のリアルタイム気象データ。

    JMA bosai APIから10分ごとに更新される実測値を返す。
    降水量0mmの確認・予報検証・干し判断補助に使用。

    Returns:
        observed_at: 観測時刻 (ISO8601)
        stations:
          11151: 沓形 (気温・湿度・風速・風向・降水量10分/1h/3h/24h・日照)
          11091: 本泊/利尻空港 (気温・風速・風向・降水量)
    """
    data = _fetch_jma_amedas_realtime()
    if data is None:
        return jsonify({'error': 'JMA AMeDAS data unavailable'}), 503
    return jsonify(data)


# ── 降水ナウキャスト ヘルパー関数 ───────────────────────────────────────────

def _lat_lon_to_tile_pixel(lat: float, lon: float, z: int) -> tuple[int, int, int, int]:
    """緯度経度をWebメルカトルのタイル座標(tx,ty)とピクセル座標(px,py)に変換。

    Args:
        lat: 緯度 (度)
        lon: 経度 (度)
        z:   ズームレベル
    Returns:
        (tx, ty, px, py) — タイルインデックスとタイル内ピクセル位置 (0-255)
    """
    n = 2 ** z
    x_f = (lon + 180.0) / 360.0 * n
    lr  = math.radians(lat)
    y_f = (1.0 - math.log(math.tan(lr) + 1.0 / math.cos(lr)) / math.pi) / 2.0 * n
    tx, ty = int(x_f), int(y_f)
    px, py = int((x_f - tx) * 256), int((y_f - ty) * 256)
    return tx, ty, px, py


def _parse_hrpns_pixel(png_bytes: bytes | None, px: int, py: int) -> float:
    """JMA hrpns PNGタイルのピクセル(px,py)から降水量(mm/h)を返す。

    JMAタイル仕様:
    - ファイルサイズ <= 500 bytes: 全透明(降水なし) → 0.0
    - 4-bit indexed PNG (color_type=3, bit_depth=4): PLTEパレットでデコード
    - 8-bit RGBA PNG (color_type=6): alpha=0 → 0.0、alpha>0 → 軽雨

    パレットはJMA実タイル(2026-05-31)から確認済み (_HRPNS_PRECIP_MID 参照)。
    フィルタータイプ: JMAはフィルター0(None)のみ使用 (再構築不要)。
    """
    import struct as _s
    import zlib   as _z

    if not png_bytes or len(png_bytes) <= 500:
        return 0.0   # blank tile = no rain

    pos  = 8         # PNG シグネチャをスキップ
    idat = b''
    plte, trns = [], []
    w = h = bd = ct = 0

    while pos < len(png_bytes) - 8:
        try:
            ln   = _s.unpack('>I', png_bytes[pos:pos+4])[0]
            ctyp = png_bytes[pos+4:pos+8]
            cd   = png_bytes[pos+8:pos+8+ln]
        except Exception:
            break
        if ctyp == b'IHDR':
            w, h, bd, ct = _s.unpack('>IIBB', cd[:10])
        elif ctyp == b'PLTE':
            plte = [(cd[i*3], cd[i*3+1], cd[i*3+2]) for i in range(ln // 3)]
        elif ctyp == b'tRNS':
            trns = list(cd)
        elif ctyp == b'IDAT':
            idat += cd
        elif ctyp == b'IEND':
            break
        pos += 12 + ln

    try:
        raw = _z.decompress(idat)
    except Exception:
        return 0.0

    try:
        if ct == 3 and bd == 4:
            # 4-bit indexed — 256px幅: bytes_per_row=128, row_stride=129 (filter+data)
            bpr  = (w * 4 + 7) // 8          # = 128
            base = py * (1 + bpr) + 1 + px // 2
            byte = raw[base]
            idx  = (byte >> 4) & 0xF if px % 2 == 0 else byte & 0xF
            # tRNS[idx]==0 → 透明 → 降水なし
            if trns and idx < len(trns) and trns[idx] == 0:
                return 0.0
            return _HRPNS_PRECIP_MID[idx] if idx < len(_HRPNS_PRECIP_MID) else 0.0

        elif ct == 6:
            # 8-bit RGBA — 空タイル(全透明)はすでに上のサイズチェックで捕捉済み
            base = py * (1 + w * 4) + 1 + px * 4
            a    = raw[base + 3]
            return 0.0 if a == 0 else 0.5   # alpha>0 は少なくとも軽雨

    except (IndexError, Exception):
        pass
    return 0.0


def _fetch_nowcast_precip_rishiri() -> dict | None:
    """利尻島全干場（334地点）の高解像度降水ナウキャスト(250mメッシュ)を一括取得。

    JMA hrpnsタイルAPIを使用。z=10では利尻島全体が2枚のタイルに収まるため、
    334地点すべてを2回のHTTPリクエストで処理できる（効率的）。

    キャッシュ: 5分間有効 (_NOWCAST_CACHE)。
    返り値: {'basetime': str, 'observed_at': str, 'spots': {name: mm/h},
             'tiles_fetched': int, 'max_precip_mmh': float, 'any_rain': bool}
    """
    import urllib.request as _ur
    import csv

    # キャッシュチェック
    now_ts = datetime.now(tz=JST).timestamp()
    if (_NOWCAST_CACHE['data'] is not None and
            _NOWCAST_CACHE['fetched_at'] is not None and
            now_ts - _NOWCAST_CACHE['fetched_at'] < _NOWCAST_CACHE_TTL):
        return _NOWCAST_CACHE['data']

    try:
        # 1. 最新バスタイムを取得
        req = _ur.Request(HRPNS_TIMES_URL, headers={'User-Agent': 'rishiri-kelp/2.6'})
        with _ur.urlopen(req, timeout=8) as r:
            times_data = json.loads(r.read())
        basetime = times_data[0]['basetime']   # 例: "20260531041000"
        observed = (f"{basetime[:4]}-{basetime[4:6]}-{basetime[6:8]}"
                    f"T{basetime[8:10]}:{basetime[10:12]}:{basetime[12:14]}Z")

        # 2. 全干場の座標を読み込む
        spots = []
        with open(CSV_FILE, 'r', encoding='utf-8') as f:
            for row in csv.DictReader(f):
                try:
                    spots.append({'name': row['name'],
                                  'lat':  float(row['lat']),
                                  'lon':  float(row['lon'])})
                except (ValueError, KeyError):
                    pass

        # 3. 必要なタイルを判定してまとめて取得（利尻島全体 = 通常2タイル）
        z = HRPNS_TILE_Z
        tile_bytes: dict[tuple, bytes | None] = {}
        spot_results: dict[str, float] = {}

        for sp in spots:
            tx, ty, px, py = _lat_lon_to_tile_pixel(sp['lat'], sp['lon'], z)
            key = (tx, ty)
            if key not in tile_bytes:
                url = HRPNS_TILE_URL.format(bt=basetime, z=z, x=tx, y=ty)
                try:
                    req2 = _ur.Request(url, headers={'User-Agent': 'rishiri-kelp/2.6'})
                    with _ur.urlopen(req2, timeout=8) as r2:
                        tile_bytes[key] = r2.read()
                except Exception as tile_err:
                    print(f'[nowcast] tile fetch error {key}: {tile_err}')
                    tile_bytes[key] = None
            spot_results[sp['name']] = _parse_hrpns_pixel(tile_bytes[key], px, py)

        max_precip = max(spot_results.values()) if spot_results else 0.0
        result = {
            'basetime':       basetime,
            'observed_at':    observed,
            'spots':          spot_results,
            'tiles_fetched':  len(tile_bytes),
            'max_precip_mmh': round(max_precip, 1),
            'any_rain':       max_precip > 0.0,
        }
        _NOWCAST_CACHE['data']       = result
        _NOWCAST_CACHE['fetched_at'] = now_ts
        return result

    except Exception as e:
        print(f'[nowcast] error: {e}')
        return None


@app.route('/api/nowcast/precip')
@limiter.limit('20 per minute')
def get_nowcast_precip():
    """高解像度降水ナウキャスト（250mメッシュ）— 利尻島全干場の降水量一括取得。

    JMA高解像度降水ナウキャスト(hrpns)タイルAPIを使用し、
    利尻島の334地点すべてに対して5分ごとの降水強度(mm/h)を返す。
    タイル取得はz=10で2枚のみ（全334地点を2HTTPリクエストでカバー）。

    Returns:
        basetime:        観測基準時刻 (YYYYMMDDHHmmss UTC)
        observed_at:     観測時刻 (ISO8601 UTC)
        spots:           {地点名: 降水量mm/h} — 全334地点
        tiles_fetched:   取得タイル枚数 (通常2)
        max_precip_mmh:  全地点中の最大降水量 (mm/h)
        any_rain:        1地点でも降水があればtrue
    """
    data = _fetch_nowcast_precip_rishiri()
    if data is None:
        return jsonify({'error': 'JMA nowcast data unavailable'}), 503
    return jsonify(data)


def generate_terrain_description(is_forest, is_coastal, elevation):
    """Generate human-readable terrain description"""
    desc_parts = []

    if elevation > 100:
        desc_parts.append(f"標高{int(elevation)}m")

    if is_forest:
        desc_parts.append("森林地帯")

    if is_coastal:
        desc_parts.append("海岸沿い")

    if not desc_parts:
        desc_parts.append("平地")

    return "、".join(desc_parts)

@app.route('/api/analysis/spot-differences')
def get_spot_weather_differences():
    """
    干場間の気象差異分析（高解像度予測の基盤）

    Returns predicted weather differences between spots based on:
    - Distance and direction from reference point
    - Elevation differences
    - Terrain type differences
    - Local geography effects
    """
    try:
        # Get reference spot (default: Kutsugata Amedas location)
        ref_lat = float(request.args.get('ref_lat', 45.178333))
        ref_lon = float(request.args.get('ref_lon', 141.138333))

        # Get comparison spots
        spots_param = request.args.get('spots', '')
        if not spots_param:
            return jsonify({
                "status": "error",
                "message": "比較する干場を指定してください（spots パラメータ）"
            }), 400

        spot_names = spots_param.split(',')
        differences = []

        for spot_name in spot_names:
            spot_name = spot_name.strip()
            if not spot_name:
                continue

            # Extract coordinates
            parts = spot_name.split('_')
            if len(parts) != 3 or parts[0] != 'H':
                continue

            lat = 45.0 + float(parts[1]) / 10000.0
            lon = 141.0 + float(parts[2]) / 10000.0

            # Calculate distance
            distance = ((lat - ref_lat) ** 2 + (lon - ref_lon) ** 2) ** 0.5 * 111  # km

            # Calculate direction
            import math
            dx = lon - ref_lon
            dy = lat - ref_lat
            direction = (math.degrees(math.atan2(dx, dy)) + 360) % 360

            # Terrain differences
            ref_elevation = get_elevation(ref_lat, ref_lon)
            spot_elevation = get_elevation(lat, lon)
            elevation_diff = spot_elevation - ref_elevation

            ref_is_forest = is_forest_area(ref_lat, ref_lon)
            spot_is_forest = is_forest_area(lat, lon)

            # Estimate weather differences based on distance and terrain
            # Temperature: decreases with elevation and distance from coast
            temp_diff = -(elevation_diff / 100) * 0.6

            # Humidity: increases with forest cover and decreases with elevation
            humidity_diff = 0.0
            if spot_is_forest and not ref_is_forest:
                humidity_diff += 10.0
            elif ref_is_forest and not spot_is_forest:
                humidity_diff -= 10.0
            humidity_diff -= (elevation_diff / 100) * 1.0

            # Wind speed: decreases with forest cover, increases with elevation
            wind_diff = 0.0
            if spot_is_forest and not ref_is_forest:
                wind_diff -= 2.5
            elif ref_is_forest and not spot_is_forest:
                wind_diff += 2.5
            wind_diff += (elevation_diff / 100) * 0.5

            differences.append({
                'spot_name': spot_name,
                'coordinates': {'lat': lat, 'lon': lon},
                'distance_km': round(distance, 2),
                'direction_deg': round(direction, 1),
                'direction_name': get_direction_name(direction),
                'elevation_difference_m': round(elevation_diff, 1),
                'predicted_differences': {
                    'temperature_c': round(temp_diff, 1),
                    'humidity_percent': round(humidity_diff, 1),
                    'wind_speed_ms': round(wind_diff, 1)
                },
                'confidence': calculate_difference_confidence(distance, elevation_diff)
            })

        return jsonify({
            'status': 'success',
            'reference_point': {'lat': ref_lat, 'lon': ref_lon},
            'spot_differences': differences,
            'methodology': '地形・距離・標高差に基づく局地気象差異推定（仕様書 lines 425-433）',
            'note': '100m格子高解像度モデルの基盤データ'
        })

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

def get_direction_name(degrees):
    """Convert degrees to cardinal direction name"""
    directions = ['北', '北北東', '北東', '東北東', '東', '東南東', '南東', '南南東',
                  '南', '南南西', '南西', '西南西', '西', '西北西', '北西', '北北西']
    index = int((degrees + 11.25) / 22.5) % 16
    return directions[index]

def calculate_difference_confidence(distance_km, elevation_diff):
    """
    Calculate confidence level for predicted weather differences

    Confidence decreases with:
    - Greater distance (less correlation)
    - Larger elevation differences (more uncertainty)
    """
    confidence = 100.0

    # Distance penalty: -10% per km
    confidence -= distance_km * 10

    # Elevation penalty: -5% per 100m
    confidence -= abs(elevation_diff) / 100 * 5

    # Clamp to 0-100
    confidence = max(0, min(100, confidence))

    if confidence >= 80:
        return {'level': 'high', 'percent': round(confidence, 1)}
    elif confidence >= 60:
        return {'level': 'medium', 'percent': round(confidence, 1)}
    elif confidence >= 40:
        return {'level': 'low', 'percent': round(confidence, 1)}
    else:
        return {'level': 'very_low', 'percent': round(confidence, 1)}

# Simple startup function
def main():
    # Multiple fallback strategies for PORT
    port_env = os.environ.get('PORT')
    if port_env is None or port_env == '' or port_env == '$PORT':
        port = 8000
        print("WARNING: PORT not properly set, using default 8000", file=sys.stdout)
    else:
        try:
            port = int(port_env)
        except (ValueError, TypeError):
            port = 8000
            print(f"WARNING: Invalid PORT '{port_env}', using default 8000", file=sys.stdout)

    print(f"Starting Rishiri Kelp Forecast System on port {port}", file=sys.stdout)
    print(f"Environment PORT variable: '{os.environ.get('PORT', 'NOT SET')}'", file=sys.stdout)

    app.run(
        host='0.0.0.0',
        port=port,
        debug=False,
        threaded=True
    )

def estimate_vertical_p_velocity(hourly_data, current_index, full_hourly, absolute_hour_index):
    """
    Estimate vertical p-velocity (omega) from available meteorological parameters

    Parameters:
    - hourly_data: List of processed hourly data for the current day
    - current_index: Index in the hourly_data array
    - full_hourly: Full hourly data from API
    - absolute_hour_index: Absolute index in the full API data

    Returns:
    - omega: Estimated vertical p-velocity in Pa/s (positive = downward, negative = upward)
    """
    try:
        # Method 1: Pressure tendency (most reliable with available data)
        if (absolute_hour_index > 0 and
            absolute_hour_index < len(full_hourly.get('pressure_msl', [])) and
            full_hourly['pressure_msl'][absolute_hour_index] is not None and
            full_hourly['pressure_msl'][absolute_hour_index - 1] is not None):

            # Pressure change rate (hPa/hour)
            pressure_current = full_hourly['pressure_msl'][absolute_hour_index]
            pressure_prev = full_hourly['pressure_msl'][absolute_hour_index - 1]
            dp_dt = pressure_current - pressure_prev  # hPa/hour

            # Convert to Pa/s: 1 hPa/hour = 100 Pa / 3600 s = 0.0278 Pa/s
            dp_dt_pas = dp_dt * 100 / 3600

            # Simple omega estimation: ω ≈ dp/dt (first approximation)
            omega_pressure = dp_dt_pas
        else:
            omega_pressure = 0.0

        # Method 2: Cloud cover tendency (secondary indicator)
        omega_cloud = 0.0
        if (current_index > 0 and
            hourly_data[current_index]['cloud_cover'] is not None and
            hourly_data[current_index - 1]['cloud_cover'] is not None):

            cloud_current = hourly_data[current_index]['cloud_cover']
            cloud_prev = hourly_data[current_index - 1]['cloud_cover']
            cloud_change = cloud_current - cloud_prev  # %/hour

            # Increasing clouds suggest upward motion (negative omega)
            # Scale factor: roughly -0.1 Pa/s per 10% cloud increase
            omega_cloud = -cloud_change * 0.01

        # Method 3: Temperature gradient estimation
        omega_temp = 0.0
        if (current_index > 0 and
            hourly_data[current_index]['temperature'] is not None and
            hourly_data[current_index - 1]['temperature'] is not None):

            temp_current = hourly_data[current_index]['temperature']
            temp_prev = hourly_data[current_index - 1]['temperature']
            temp_change = temp_current - temp_prev  # °C/hour

            # Cooling can indicate upward motion (adiabatic cooling)
            # Scale factor: roughly -0.05 Pa/s per °C cooling
            omega_temp = temp_change * 0.05

        # Weighted combination of methods
        # Pressure tendency is most reliable, cloud and temperature are secondary
        omega_estimated = (0.7 * omega_pressure +
                          0.2 * omega_cloud +
                          0.1 * omega_temp)

        # Clamp to reasonable range: ±5 Pa/s (very strong vertical motion is rare)
        omega_estimated = max(-5.0, min(5.0, omega_estimated))

        return round(omega_estimated, 3)

    except Exception as e:
        print(f"Error estimating vertical p-velocity: {e}")
        return 0.0

def estimate_ssi_simplified(current_hour, hourly_data, hour_index):
    """
    Estimate simplified SSI (Showalter Stability Index) from surface data

    Parameters:
    - current_hour: Current hour data dictionary
    - hourly_data: List of hourly data for context
    - hour_index: Index of current hour

    Returns:
    - ssi: Estimated SSI value (positive = stable, negative = unstable)
    """
    try:
        # Standard atmospheric temperature lapse rate: -6.5°C/km
        # SSI approximation based on surface conditions and atmospheric physics

        # Get current conditions
        temp = current_hour.get('temperature')
        humidity = current_hour.get('humidity')
        pressure = current_hour.get('pressure')

        if temp is None or humidity is None or pressure is None:
            return None

        # Calculate dewpoint temperature (Magnus formula approximation)
        # Td = T - ((100 - RH) / 5)  (simplified)
        dewpoint = temp - ((100 - humidity) / 5)

        # Estimate potential temperature at surface
        # θ = T * (1000/P)^0.286
        theta_surface = temp * pow(1000.0 / pressure, 0.286)

        # Simplified SSI calculation based on temperature-dewpoint spread
        # and estimated atmospheric stability from surface conditions

        # Method 1: Temperature-dewpoint spread indicator
        td_spread = temp - dewpoint

        # Method 2: Pressure tendency effect (if available)
        pressure_factor = 0
        if hour_index > 0 and hourly_data[hour_index - 1].get('pressure'):
            prev_pressure = hourly_data[hour_index - 1]['pressure']
            dp_dt = pressure - prev_pressure  # hPa/hour
            # Rising pressure often indicates stability
            pressure_factor = dp_dt * 0.5

        # Method 3: Humidity-based stability estimate
        # High humidity at surface often indicates lower stability
        humidity_factor = (humidity - 60) * -0.1  # Scale factor

        # Method 4: Temperature gradient estimation
        temp_factor = 0
        if hour_index > 0 and hourly_data[hour_index - 1].get('temperature'):
            prev_temp = hourly_data[hour_index - 1]['temperature']
            dt_dt = temp - prev_temp  # °C/hour
            # Rapid cooling can indicate instability
            temp_factor = -dt_dt * 2

        # Combine factors to estimate SSI
        # Positive SSI = stable conditions
        # Negative SSI = unstable conditions
        ssi_estimate = (
            td_spread * 0.8 +           # Main factor: T-Td spread
            pressure_factor +           # Pressure tendency
            humidity_factor +           # Humidity effect
            temp_factor                 # Temperature change
        )

        # Apply realistic bounds: SSI typically ranges from -10 to +10
        ssi_estimate = max(-10.0, min(10.0, ssi_estimate))

        return round(ssi_estimate, 1)

    except Exception as e:
        print(f"Error estimating SSI: {e}")
        return None

def get_ssi_category(ssi):
    """
    Categorize SSI value into stability classes

    Parameters:
    - ssi: SSI value

    Returns:
    - category: Stability category string
    """
    if ssi is None:
        return "不明"
    elif ssi >= 3:
        return "安定"
    elif ssi >= 0:
        return "中性"
    elif ssi >= -3:
        return "やや不安定"
    else:
        return "不安定"

def calculate_equivalent_potential_temperature(temperature_c, humidity, pressure_hpa):
    """
    Calculate equivalent potential temperature (相当温位) in Kelvin

    Parameters:
    - temperature_c: Temperature in Celsius
    - humidity: Relative humidity in %
    - pressure_hpa: Pressure in hPa

    Returns:
    - Equivalent potential temperature in Kelvin
    """
    try:
        if temperature_c is None or humidity is None or pressure_hpa is None:
            return None

        # Convert temperature to Kelvin
        T = temperature_c + 273.15

        # Constants
        Rd = 287.0  # Gas constant for dry air (J/kg/K)
        Rv = 461.5  # Gas constant for water vapor (J/kg/K)
        cp = 1004.0  # Specific heat of dry air at constant pressure (J/kg/K)
        L = 2.5e6   # Latent heat of vaporization (J/kg)

        # Calculate saturation vapor pressure (hPa) using Tetens formula
        es = 6.112 * math.exp(17.67 * temperature_c / (temperature_c + 243.5))

        # Calculate actual vapor pressure
        e = es * humidity / 100.0

        # Calculate mixing ratio (kg/kg)
        w = 0.622 * e / (pressure_hpa - e)

        # Calculate potential temperature
        theta = T * (1000.0 / pressure_hpa) ** (Rd / cp)

        # Calculate equivalent potential temperature
        # Simplified Bolton (1980) formula
        theta_e = theta * math.exp((L * w) / (cp * T))

        return theta_e

    except Exception as e:
        print(f"Error calculating equivalent potential temperature: {e}")
        return None

def estimate_vertical_p_velocity_700hpa(hourly_data, current_index, full_hourly, absolute_hour_index):
    """
    Enhanced vertical p-velocity estimation using 700hPa pressure level data

    Parameters:
    - hourly_data: List of processed hourly data for the current day
    - current_index: Index in the hourly_data array
    - full_hourly: Full hourly data from API
    - absolute_hour_index: Absolute index in the full API data

    Returns:
    - omega: Estimated vertical p-velocity in Pa/s at 700hPa level
    """
    try:
        # Method 1: Temperature tendency at 700hPa (more reliable than surface)
        omega_temp = 0.0
        if (current_index > 0 and
            hourly_data[current_index].get('temp_700hpa') is not None and
            hourly_data[current_index - 1].get('temp_700hpa') is not None):

            temp_current = hourly_data[current_index]['temp_700hpa']
            temp_prev = hourly_data[current_index - 1]['temp_700hpa']
            temp_change = temp_current - temp_prev  # °C/hour

            # Adiabatic cooling rate: ~6.5°C/km for dry air
            # Rising air cools at this rate, so negative temp change suggests upward motion
            # Scale: -1°C/hour ≈ 0.1 Pa/s upward motion
            omega_temp = temp_change * 0.1  # Pa/s

        # Method 2: Wind speed divergence at 700hPa
        omega_wind = 0.0
        if (current_index > 0 and
            hourly_data[current_index].get('wind_speed_700hpa') is not None and
            hourly_data[current_index - 1].get('wind_speed_700hpa') is not None):

            wind_current = hourly_data[current_index]['wind_speed_700hpa']
            wind_prev = hourly_data[current_index - 1]['wind_speed_700hpa']
            wind_change = wind_current - wind_prev  # m/s per hour

            # Increasing wind suggests convergence/upward motion (negative omega)
            # Scale: +1 m/s/hr wind increase ≈ -0.05 Pa/s
            omega_wind = -wind_change * 0.05

        # Method 3: Humidity tendency at 700hPa
        omega_humidity = 0.0
        if (current_index > 0 and
            hourly_data[current_index].get('humidity_700hpa') is not None and
            hourly_data[current_index - 1].get('humidity_700hpa') is not None):

            humidity_current = hourly_data[current_index]['humidity_700hpa']
            humidity_prev = hourly_data[current_index - 1]['humidity_700hpa']
            humidity_change = humidity_current - humidity_prev  # %/hour

            # Increasing humidity suggests upward motion (negative omega)
            # Scale: +10%/hr humidity increase ≈ -0.02 Pa/s
            omega_humidity = -humidity_change * 0.002

        # Weighted combination (temperature tendency is most reliable)
        omega_total = (0.6 * omega_temp + 0.3 * omega_wind + 0.1 * omega_humidity)

        # Clamp to reasonable values (-1.0 to +1.0 Pa/s)
        omega_total = max(-1.0, min(1.0, omega_total))

        return omega_total

    except Exception as e:
        print(f"Error calculating 700hPa vertical p-velocity: {e}")
        return 0.0

def calculate_equivalent_potential_temperature_850hpa(temperature_c, humidity, pressure_hpa):
    """
    Calculate equivalent potential temperature at 850hPa level

    Parameters:
    - temperature_c: Temperature in Celsius at 850hPa
    - humidity: Relative humidity in % at 850hPa
    - pressure_hpa: Pressure in hPa (should be 850)

    Returns:
    - Equivalent potential temperature in Kelvin
    """
    try:
        if temperature_c is None or humidity is None or pressure_hpa is None:
            return None

        # Convert temperature to Kelvin
        T = temperature_c + 273.15

        # Constants
        Rd = 287.0  # Gas constant for dry air (J/kg/K)
        cp = 1004.0  # Specific heat of dry air at constant pressure (J/kg/K)
        L = 2.5e6   # Latent heat of vaporization (J/kg)

        # Calculate saturation vapor pressure at 850hPa level
        es = 6.112 * math.exp(17.67 * temperature_c / (temperature_c + 243.5))

        # Calculate actual vapor pressure
        e = es * humidity / 100.0

        # Mixing ratio (kg/kg)
        w = 0.622 * e / (pressure_hpa - e)

        # Potential temperature at 850hPa
        theta = T * (1000.0 / pressure_hpa) ** (Rd / cp)

        # Equivalent potential temperature (Bolton 1980 formula)
        theta_e = theta * math.exp((L * w) / (cp * T))

        return theta_e

    except Exception as e:
        print(f"Error calculating 850hPa equivalent potential temperature: {e}")
        return None

def calculate_500hpa_vorticity(hourly_data, current_index):
    """
    Calculate approximate relative vorticity at 500hPa using wind data

    Parameters:
    - hourly_data: List of hourly data
    - current_index: Current hour index

    Returns:
    - Relative vorticity in s^-1 (approximate)
    """
    try:
        if (current_index < 1 or current_index >= len(hourly_data) - 1):
            return 0.0

        # Simple finite difference approximation using wind direction changes
        current_hour = hourly_data[current_index]
        prev_hour = hourly_data[current_index - 1]
        next_hour = hourly_data[current_index + 1]

        # Get wind directions (use 700hPa as proxy for 500hPa, fallback to 10m)
        wd_prev = prev_hour.get('wind_direction_700hpa') or prev_hour.get('wind_direction')
        wd_curr = current_hour.get('wind_direction_700hpa') or current_hour.get('wind_direction')
        wd_next = next_hour.get('wind_direction_700hpa') or next_hour.get('wind_direction')

        if wd_prev is None or wd_curr is None or wd_next is None:
            return 0.0

        # Calculate wind direction change rate (crude vorticity proxy)
        # Normalize for 360° boundary
        def normalize_angle_diff(a1, a2):
            diff = a2 - a1
            if diff > 180:
                diff -= 360
            elif diff < -180:
                diff += 360
            return diff

        dir_change_rate = (normalize_angle_diff(wd_prev, wd_curr) +
                          normalize_angle_diff(wd_curr, wd_next)) / 2.0

        # Convert degrees/hour to approximate vorticity (s^-1)
        # This is a very rough approximation
        vorticity = dir_change_rate * (math.pi / 180.0) / 3600.0  # rad/s

        return vorticity

    except Exception as e:
        print(f"Error calculating 500hPa vorticity: {e}")
        return 0.0

def assess_drying_risk(precipitation, pwv, min_humidity, avg_humidity, max_wind, avg_wind):
    """
    Evidence-based multi-stage risk assessment for kelp drying
    Based on H_1631_1434 actual Amedas data analysis (21 records, 2025/6-8)

    Validated thresholds from actual data:
    - Precipitation: 0mm (absolute)
    - Min humidity: ≤94% (critical)
    - Avg wind: ≥2.0m/s (important)

    Parameters:
    - precipitation: Total precipitation (mm)
    - pwv: Precipitable Water Vapor (mm)
    - min_humidity: Minimum humidity during working hours 4-16h (%)
    - avg_humidity: Average humidity (%)
    - max_wind: Maximum wind speed (m/s)
    - avg_wind: Average wind speed (m/s)

    Returns:
    - Dictionary with risk level, warnings, and score multiplier
    """
    warnings = []
    risk_level = "良好"
    score_multiplier = 1.0

    # Stage 1: Precipitation check (absolute condition)
    # Actual data: All 9 success cases had 0mm precipitation
    if precipitation > 0:
        warnings.append("降水あり - 乾燥不可（実測データ：成功例は全て0mm）")
        risk_level = "中止推奨"
        score_multiplier = 0.2
        return {
            'risk_level': risk_level,
            'warnings': warnings,
            'score_multiplier': score_multiplier,
            'assessment_details': {
                'precipitation_risk': True,
                'pwv_risk': False,
                'humidity_risk': False,
                'wind_risk': False
            }
        }

    # Stage 2: PWV check (precipitation risk prediction)
    # Keep existing PWV threshold as supplementary indicator
    pwv_risk = False
    if pwv is not None and pwv > 4.1:
        warnings.append(f"PWV高め({pwv:.1f}mm) - 降水リスク")
        pwv_risk = True
        score_multiplier *= 0.85  # 15% penalty

    # Stage 3: Humidity check (MOST CRITICAL FACTOR)
    # Actual data from H_1631_1434:
    # - Success: min_humidity 45-94% (avg 70.1%)
    # - Partial: min_humidity 79-90% (avg 84.5%)
    # - Cancelled: min_humidity 71-100% (avg 92.3%)
    # Key finding: Daily avg 99% can succeed if min drops to 94%
    humidity_risk = False

    if min_humidity > 94:
        warnings.append(f"最低湿度が高い({min_humidity:.0f}%) - 乾燥不可（実測：成功例は全て94%以下）")
        humidity_risk = True
        risk_level = "中止推奨"
        score_multiplier *= 0.3  # 70% penalty
    elif min_humidity > 84:
        warnings.append(f"最低湿度やや高め({min_humidity:.0f}%) - 部分乾燥の可能性")
        humidity_risk = True
        score_multiplier *= 0.7  # 30% penalty
    elif min_humidity > 79:
        warnings.append(f"最低湿度注意({min_humidity:.0f}%) - 風速条件に注意")
        score_multiplier *= 0.85  # 15% penalty
    elif min_humidity <= 70:
        # Excellent humidity condition
        warnings.append("湿度良好 - 乾燥に適した条件")
        score_multiplier *= 1.1  # 10% bonus

    # Stage 4: Wind check (drying speed factor)
    # Actual data from H_1631_1434:
    # - Success: avg_wind 2.0-4.7m/s (avg 3.1m/s)
    # - Partial: avg_wind 3.8-5.2m/s (avg 4.5m/s)
    # - Cancelled: avg_wind 1.2-5.9m/s (avg 4.2m/s)
    # Minimum threshold: 2.0m/s required for success
    wind_risk = False

    if avg_wind < 2.0:
        warnings.append(f"風速不足({avg_wind:.1f}m/s) - 乾燥困難（実測：成功例は全て2.0m/s以上）")
        wind_risk = True
        risk_level = "中止推奨"
        score_multiplier *= 0.5  # 50% penalty
    elif avg_wind < 2.5:
        warnings.append(f"風速弱め({avg_wind:.1f}m/s) - 部分乾燥の可能性")
        score_multiplier *= 0.8  # 20% penalty
    elif max_wind > 8.5:
        # Actual data: max_wind for success was ≤8.5m/s
        warnings.append(f"強風({max_wind:.1f}m/s) - 作業困難の可能性")
        wind_risk = True
        score_multiplier *= 0.75  # 25% penalty
    elif 2.5 <= avg_wind <= 4.7 and min_humidity <= 79:
        # Ideal conditions based on actual success data
        warnings.append("理想的な条件です（実測データに基づく）")
        risk_level = "最良"
        score_multiplier *= 1.15  # 15% bonus

    # Determine final risk level
    if not warnings or "理想的な条件です" in warnings:
        risk_level = "良好"
    elif len(warnings) == 1 and not (humidity_risk or wind_risk):
        risk_level = "注意"
    elif humidity_risk or wind_risk or pwv_risk:
        if risk_level != "中止推奨":
            risk_level = "リスクあり"

    return {
        'risk_level': risk_level,
        'warnings': warnings if warnings else ["条件良好"],
        'score_multiplier': score_multiplier,
        'assessment_details': {
            'precipitation_risk': precipitation > 0,
            'pwv_risk': pwv_risk,
            'humidity_risk': humidity_risk,
            'wind_risk': wind_risk,
            'thresholds_checked': {
                'precipitation': precipitation,
                'pwv': pwv,
                'min_humidity': min_humidity,
                'avg_humidity': avg_humidity,
                'max_wind': max_wind,
                'avg_wind': avg_wind
            },
            'data_source': 'H_1631_1434 Amedas actual data (21 records, 2025/6-8)'
        }
    }

def calculate_stage_based_drying_assessment(hourly_data, day_number):
    """
    Calculate stage-based drying assessment according to specification

    Parameters:
    - hourly_data: List of hourly data for the day (4AM-4PM inclusive, 13 hours)
    - day_number: Day number for reliability weighting

    Returns:
    - Dictionary containing stage analysis results
    """
    try:
        if not hourly_data:
            return {
                'ventilation_stage_score': 0,
                'heat_supply_stage_score': 0,
                'overall_score': 0,
                'predicted_completion_time': '予測不可',
                'stage_breakdown': {}
            }

        # Stage 1: Ventilation focus (4:00-10:00) - 6 hours
        ventilation_hours = []
        heat_supply_hours = []

        for hour_data in hourly_data:
            hour = int(hour_data['time'].split(':')[0])
            if 4 <= hour <= 10:
                ventilation_hours.append(hour_data)
            elif 10 < hour <= 16:
                heat_supply_hours.append(hour_data)

        # Ventilation Stage Analysis (4:00-10:00)
        ventilation_score = 0
        ventilation_wind_scores = []

        for hour_data in ventilation_hours:
            wind_speed = hour_data.get('wind_speed', 0) or 0
            humidity = hour_data.get('humidity', 100) or 100

            # Wind score: >1.5m/s is threshold from specification
            if wind_speed > 3.0:
                wind_score = 100
            elif wind_speed > 2.0:
                wind_score = 80
            elif wind_speed > 1.5:
                wind_score = 60
            elif wind_speed > 1.0:
                wind_score = 40
            else:
                wind_score = 20

            # Humidity is applied once at the daily risk layer via assess_drying_risk();
            # do not multiply hourly stage scores by humidity again (double-damping).
            # At 78% humidity: factor=(100-78)/100=0.22, which would crush wind_score=100→22
            # before assess_drying_risk() applies its own 0.85× multiplier — net ×0.19 error.
            hour_score = wind_score
            ventilation_wind_scores.append(hour_score)

        ventilation_score = sum(ventilation_wind_scores) / len(ventilation_wind_scores) if ventilation_wind_scores else 0

        # Heat Supply Stage Analysis (10:00-16:00)
        heat_supply_score = 0
        heat_supply_scores = []

        for hour_data in heat_supply_hours:
            temperature = hour_data.get('temperature', 0) or 0
            solar_radiation = hour_data.get('solar_radiation', 0) or 0
            humidity = hour_data.get('humidity', 100) or 100

            # Temperature score
            if temperature > 25:
                temp_score = 100
            elif temperature > 20:
                temp_score = 80
            elif temperature > 15:
                temp_score = 60
            elif temperature > 10:
                temp_score = 40
            else:
                temp_score = 20

            # Solar radiation score (W/m²) — K4: 曇天(< 50 W/m²)は下限0に修正
            # 日射400 W/m²以上でDeff 7倍向上（KOMBU_DRYING_RESEARCH §3-2）
            if solar_radiation >= 800:   solar_score = 100
            elif solar_radiation >= 600: solar_score = 80
            elif solar_radiation >= 400: solar_score = 60
            elif solar_radiation >= 200: solar_score = 35
            elif solar_radiation >= 50:  solar_score = 15
            else:                         solar_score = 0  # 曇天・霧：乾燥促進効果なし

            # Humidity is applied once at the daily risk layer via assess_drying_risk();
            # do not multiply hourly stage scores by humidity again (same reason as ventilation).

            # Combined heat supply score — K3: 温度と日射を同等重みに変更(0.5/0.5)
            # 研究知見「温度 ≈ 日射」(KOMBU_DRYING_RESEARCH §4-5)
            hour_score = temp_score * 0.5 + solar_score * 0.5
            heat_supply_scores.append(hour_score)

        heat_supply_score = sum(heat_supply_scores) / len(heat_supply_scores) if heat_supply_scores else 0

        # Fixed stage-based weighting (based on H_1631_1434 actual data analysis)
        # Ventilation stage (morning 4:00-10:00): 60% - Initial surface drying is critical
        # Heat supply stage (afternoon 10:00-16:00): 40% - Internal moisture evaporation
        # Rationale: Early-stage wind conditions cannot be compensated later;
        #            surface hardening prevents internal drying
        wind_weight = 0.6
        solar_weight = 0.4

        overall_score = ventilation_score * wind_weight + heat_supply_score * solar_weight

        # Calculate average conditions for evidence-based risk assessment
        pwv_values = [h.get('precipitable_water') for h in hourly_data if h.get('precipitable_water') is not None]
        pblh_values = [h.get('boundary_layer_height') for h in hourly_data if h.get('boundary_layer_height') is not None]
        precip_values = [h.get('precipitation', 0) for h in hourly_data]
        humidity_values = [h.get('humidity', 100) for h in hourly_data if h.get('humidity') is not None]
        wind_values = [h.get('wind_speed', 0) for h in hourly_data if h.get('wind_speed') is not None]

        avg_pwv = sum(pwv_values) / len(pwv_values) if pwv_values else None
        avg_pblh = sum(pblh_values) / len(pblh_values) if pblh_values else None
        total_precip = sum(precip_values) if precip_values else 0
        min_humidity = min(humidity_values) if humidity_values else 100
        avg_humidity = sum(humidity_values) / len(humidity_values) if humidity_values else 100
        max_wind = max(wind_values) if wind_values else 0
        avg_wind = sum(wind_values) / len(wind_values) if wind_values else 0

        # Evidence-based risk assessment (multi-stage filtering)
        risk_assessment = assess_drying_risk(
            precipitation=total_precip,
            pwv=avg_pwv,
            min_humidity=min_humidity,
            avg_humidity=avg_humidity,
            max_wind=max_wind,
            avg_wind=avg_wind
        )

        # Apply risk-based score adjustment
        overall_score = max(0, min(100, overall_score * risk_assessment['score_multiplier']))

        # Quantitative drying time prediction
        if overall_score >= 85:
            completion_time = "14:00頃完全乾燥"
            drying_hours = 10
        elif overall_score >= 70:
            completion_time = "16:00頃完全乾燥"
            drying_hours = 12
        elif overall_score >= 55:
            completion_time = "18:00頃完全乾燥"
            drying_hours = 14
        elif overall_score >= 40:
            completion_time = "夕方までに部分乾燥"
            drying_hours = 16
        else:
            completion_time = "乾燥困難、延期推奨"
            drying_hours = 24

        # Calculate average wind and solar for breakdown
        avg_ventilation_wind = sum(h.get('wind_speed', 0) or 0 for h in ventilation_hours) / len(ventilation_hours) if ventilation_hours else 0
        avg_heat_temp = sum(h.get('temperature', 0) or 0 for h in heat_supply_hours) / len(heat_supply_hours) if heat_supply_hours else 0
        avg_solar = sum(h.get('solar_radiation', 0) or 0 for h in heat_supply_hours) / len(heat_supply_hours) if heat_supply_hours else 0

        return {
            'ventilation_stage_score': round(ventilation_score, 1),
            'heat_supply_stage_score': round(heat_supply_score, 1),
            'overall_score': round(overall_score, 1),
            'predicted_completion_time': completion_time,
            'estimated_drying_hours': drying_hours,
            'risk_assessment': {
                'risk_level': risk_assessment['risk_level'],
                'warnings': risk_assessment['warnings'],
                'score_multiplier': round(risk_assessment['score_multiplier'], 2),
                'details': risk_assessment['assessment_details']
            },
            'time_weights': {
                'wind_weight': wind_weight,
                'solar_weight': solar_weight
            },
            'conditions_summary': {
                'precipitation': round(total_precip, 1),
                'pwv': round(avg_pwv, 1) if avg_pwv is not None else None,
                'min_humidity': round(min_humidity, 1),
                'avg_humidity': round(avg_humidity, 1),
                'max_wind': round(max_wind, 1),
                'avg_wind': round(avg_wind, 1)
            },
            'stage_breakdown': {
                'ventilation_period': {
                    'hours': '4:00-10:00',
                    'avg_wind_speed': round(avg_ventilation_wind, 1),
                    'score': round(ventilation_score, 1)
                },
                'heat_supply_period': {
                    'hours': '10:00-16:00',
                    'avg_temperature': round(avg_heat_temp, 1),
                    'avg_solar_radiation': round(avg_solar, 1),
                    'score': round(heat_supply_score, 1)
                }
            }
        }

    except Exception as e:
        print(f"Error in stage-based drying assessment: {e}")
        return {
            'ventilation_stage_score': 0,
            'heat_supply_stage_score': 0,
            'overall_score': 0,
            'predicted_completion_time': '予測エラー',
            'stage_breakdown': {}
        }

def calculate_pwv_from_dewpoint(temperature_c, dewpoint_c, surface_pressure_hpa):
    """
    Calculate Precipitable Water Vapor (PWV) from surface conditions using empirical formula

    Parameters:
    - temperature_c: Surface temperature in Celsius
    - dewpoint_c: Dewpoint temperature in Celsius
    - surface_pressure_hpa: Surface pressure in hPa

    Returns:
    - PWV in mm (approximate)
    """
    try:
        if temperature_c is None or dewpoint_c is None or surface_pressure_hpa is None:
            return None

        # Calculate saturation vapor pressure at dewpoint (hPa) - Magnus formula
        es_dewpoint = 6.112 * math.exp(17.67 * dewpoint_c / (dewpoint_c + 243.5))

        # Empirical PWV formula from surface vapor pressure
        # PWV (mm) ≈ 0.15 * e_s (hPa) * (T/273.15)
        # This accounts for exponential moisture decay with height
        # Validated against historical data: typical range 3.6-4.4mm for summer
        pwv = 0.15 * es_dewpoint * ((temperature_c + 273.15) / 273.15)

        return pwv

    except Exception as e:
        print(f"Error calculating PWV from dewpoint: {e}")
        return None

def estimate_pblh_from_conditions(temperature_c, wind_speed_ms, solar_radiation_wm2, cloud_cover_pct, hour_of_day):
    """
    Estimate Planetary Boundary Layer Height from surface conditions

    Parameters:
    - temperature_c: Surface temperature in Celsius
    - wind_speed_ms: Wind speed in m/s
    - solar_radiation_wm2: Solar radiation in W/m²
    - cloud_cover_pct: Cloud cover in %
    - hour_of_day: Hour of day (0-23)

    Returns:
    - PBLH in meters (approximate)
    """
    try:
        if any(x is None for x in [temperature_c, wind_speed_ms, solar_radiation_wm2, cloud_cover_pct]):
            return None

        # Base PBLH from time of day (diurnal cycle)
        if 6 <= hour_of_day <= 18:
            # Daytime - convective boundary layer
            base_pblh = 800  # meters

            # Solar heating contribution (0-600m)
            solar_factor = (solar_radiation_wm2 / 1000) * 600

            # Temperature contribution (warmer = higher)
            temp_factor = max(0, (temperature_c - 10) * 20)

            # Cloud cover reduction (more clouds = less heating = lower PBLH)
            cloud_factor = (100 - cloud_cover_pct) / 100

            pblh = base_pblh + (solar_factor + temp_factor) * cloud_factor
        else:
            # Nighttime - stable boundary layer
            base_pblh = 200  # meters

            # Wind mixing contribution
            wind_factor = wind_speed_ms * 50  # meters

            pblh = base_pblh + wind_factor

        # Wind always adds mechanical mixing
        pblh += wind_speed_ms * 30

        # Clamp to reasonable range
        pblh = max(100, min(2500, pblh))

        return pblh

    except Exception as e:
        print(f"Error estimating PBLH: {e}")
        return None

def calculate_pwv_score(pwv):
    """
    Calculate drying score based on Precipitable Water Vapor (PWV)

    Parameters:
    - pwv: Precipitable water vapor in mm

    Returns:
    - score: Drying score contribution (0-30 points)
    - category: PWV category string
    """
    if pwv is None:
        return 0, "不明"

    if pwv < 15:
        return 30, "非常に乾燥"
    elif pwv < 20:
        return 25, "乾燥"
    elif pwv < 25:
        return 15, "やや乾燥"
    elif pwv < 30:
        return 5, "普通"
    elif pwv < 35:
        return -5, "やや湿潤"
    elif pwv < 40:
        return -15, "湿潤"
    else:
        return -30, "非常に湿潤"

def calculate_pblh_score(pblh):
    """
    Calculate drying score based on Planetary Boundary Layer Height (PBLH)

    Parameters:
    - pblh: Boundary layer height in meters

    Returns:
    - score: Drying score contribution (0-25 points)
    - category: PBLH category string
    """
    if pblh is None:
        return 0, "不明"

    if pblh > 1500:
        return 25, "非常に良好"
    elif pblh > 1200:
        return 20, "良好"
    elif pblh > 1000:
        return 15, "やや良好"
    elif pblh > 800:
        return 10, "普通"
    elif pblh > 600:
        return 5, "やや不良"
    elif pblh > 400:
        return -10, "不良"
    else:
        return -25, "海霧リスク"

def calculate_pwv_pblh_combined_score(pwv, pblh):
    """
    Calculate combined score and risk assessment from PWV and PBLH

    Parameters:
    - pwv: Precipitable water vapor in mm
    - pblh: Boundary layer height in meters

    Returns:
    - Dictionary with combined score and risk assessment
    """
    pwv_score, pwv_category = calculate_pwv_score(pwv)
    pblh_score, pblh_category = calculate_pblh_score(pblh)

    combined_score = pwv_score + pblh_score

    # Special risk conditions
    sea_fog_risk = False
    if pwv is not None and pblh is not None:
        if pwv > 40 and pblh < 400:
            sea_fog_risk = True
            risk_level = "海霧確実"
        elif pwv > 35 and pblh < 600:
            sea_fog_risk = True
            risk_level = "海霧高リスク"
        elif pwv > 30 and pblh < 800:
            risk_level = "海霧注意"
        elif pwv < 20 and pblh > 1200:
            risk_level = "理想的条件"
        elif pwv < 25 and pblh > 1000:
            risk_level = "良好な条件"
        else:
            risk_level = "通常条件"
    else:
        risk_level = "不明"

    return {
        'pwv_score': pwv_score,
        'pwv_category': pwv_category,
        'pblh_score': pblh_score,
        'pblh_category': pblh_category,
        'combined_score': combined_score,
        'sea_fog_risk': sea_fog_risk,
        'risk_level': risk_level
    }

def calculate_remoistening_risk(hourly_data):
    """
    再吸湿リスク評価（KOMBU_DRYING_RESEARCH.md §10 K6）
    10:00〜16:00 の湿度上昇率から昆布の取り込み推奨時刻を算出する。
    Returns dict: risk level, rise_rate(%/h), recommended_collection_time
    """
    afternoon = [
        h for h in hourly_data
        if h.get('humidity') is not None and 10 <= int(h['time'].split(':')[0]) <= 16
    ]
    if len(afternoon) < 2:
        return {'risk': 'unknown', 'rise_rate': None, 'advice': '取り込み時刻: データ不足'}

    rise_rate = (afternoon[-1]['humidity'] - afternoon[0]['humidity']) / len(afternoon)

    if rise_rate > 4.0:
        return {'risk': 'high',   'rise_rate': round(rise_rate, 1),
                'advice': '14:00以前の早期取り込みを推奨（夕方湿度急上昇）'}
    elif rise_rate > 2.0:
        return {'risk': 'medium', 'rise_rate': round(rise_rate, 1),
                'advice': '16:00までに取り込み完了を推奨'}
    else:
        return {'risk': 'low',    'rise_rate': round(rise_rate, 1),
                'advice': '通常通り取り込み可（夕方の湿度上昇は緩やか）'}


def assess_cape_risk(cape_value):
    """
    CAPE指数による対流不安定リスク評価（WINDY_RESEARCH.md §6 W10）
    突発的な積乱雲・にわか雨リスクをスコアペナルティに変換する。
    """
    if cape_value is None:
        return {'risk': 'unknown', 'score_penalty': 0, 'warning': None}
    if cape_value > 1000:
        return {'risk': 'high',   'score_penalty': -20,
                'warning': f'CAPE {cape_value:.0f} J/kg — 突発的な強雨リスク高、緊急取り込み準備'}
    elif cape_value > 500:
        return {'risk': 'medium', 'score_penalty': -10,
                'warning': f'CAPE {cape_value:.0f} J/kg — 積乱雲発達リスクあり'}
    elif cape_value > 200:
        return {'risk': 'low',    'score_penalty': -3,
                'warning': f'CAPE {cape_value:.0f} J/kg — にわか雨注意'}
    else:
        return {'risk': 'none',   'score_penalty': 0, 'warning': None}


def get_sea_surface_temperature(lat, lon):
    """
    Open-Meteo Marine API から海面水温 (SST) を取得（WINDY_RESEARCH.md §6 W6）
    SST < 15°C のとき海霧リスク高（ISLAND_METEOROLOGY_RESEARCH §7）
    """
    try:
        url = (
            f"https://marine-api.open-meteo.com/v1/marine"
            f"?latitude={lat}&longitude={lon}"
            f"&daily=sea_surface_temperature"
            f"&timezone=Asia/Tokyo"
            f"&forecast_days=7"
        )
        response = requests.get(url, timeout=8)
        response.raise_for_status()
        data = response.json()
        sst_list = data.get('daily', {}).get('sea_surface_temperature', [])
        return sst_list  # list of 7 values (°C)
    except Exception:
        return [None] * 7


def assess_sst_fog_risk(sst, air_temp=None):
    """SST から霧リスクレベルを評価"""
    if sst is None:
        return 'unknown'
    if sst < 10:
        return 'very_high'   # 冷水塊（親潮）接近: 海霧ほぼ確実
    elif sst < 15:
        return 'high'        # 親潮影響域: 海霧リスク高
    elif air_temp is not None and (air_temp - sst) > 5:
        return 'medium'      # 暖気移流＋冷海面: 移流霧リスク
    return 'low'


def calculate_solunar_score(target_date):
    """
    ソルナー指数（WINDY_RESEARCH.md §6 W9）
    月相（新月・満月付近）が漁業活性・昆布採取の好機とされる経験則を数値化。
    外部 API 不要 — 月齢計算のみ。
    Returns: score (0-100), phase_name (str), moon_age_days (float)
    """
    from datetime import timezone as _tz
    # 2000-01-06 18:14 UTC = 新月（基準点）
    new_moon_epoch = datetime(2000, 1, 6, 18, 14, tzinfo=_tz.utc)
    lunar_cycle = 29.530588853  # 朔望月（日）

    if target_date.tzinfo is None:
        target_date = target_date.replace(tzinfo=_tz.utc)

    elapsed_days = (target_date - new_moon_epoch).total_seconds() / 86400
    moon_age = elapsed_days % lunar_cycle          # 0 = 新月, ~14.8 = 満月
    phase_ratio = moon_age / lunar_cycle            # 0.0〜1.0

    # 新月(0)・満月(0.5)付近で高スコア
    proximity_new  = min(phase_ratio, 1 - phase_ratio)      # 0〜0.5
    proximity_full = abs(phase_ratio - 0.5)                  # 0〜0.5
    best = min(proximity_new, proximity_full)                 # 0 = 新/満月
    score = max(0, int(100 - best * 400))

    if moon_age < 1.5 or moon_age > 28:
        phase_name = '新月'
    elif moon_age < 7:
        phase_name = '三日月（上弦へ）'
    elif moon_age < 8.5:
        phase_name = '上弦の月'
    elif moon_age < 13.5:
        phase_name = '十三夜（満月へ）'
    elif moon_age < 16.5:
        phase_name = '満月'
    elif moon_age < 22:
        phase_name = '十六夜（下弦へ）'
    elif moon_age < 23.5:
        phase_name = '下弦の月'
    else:
        phase_name = '晦（新月へ）'

    return score, phase_name, round(moon_age, 1)


import threading as _threading


def _try_acquire_notify_lock(key: str, ttl: int = 3600) -> bool:
    """Two-layer lock to prevent duplicate notifications.

    Layer 1 — file lock (atomic O_CREAT|O_EXCL on Linux):
        Works reliably within the same machine even with multiple workers.
        Falls back to True on unexpected errors.
    Layer 2 — Upstash Redis NX pipeline (defense in depth):
        Guards against multi-machine or container-restart edge cases.

    Returns True only if BOTH layers are acquired.
    """
    import tempfile
    from pathlib import Path

    # ── Layer 1: file lock ──────────────────────────────────────────────────
    safe_key = key.replace(':', '_').replace('/', '_')
    lock_path = Path(tempfile.gettempdir()) / f'rishiri_{safe_key}.lock'
    try:
        lock_path.open('x').close()  # atomic create; raises FileExistsError if exists
    except FileExistsError:
        app.logger.info('notify lock (file) already held for %s — skipping', key)
        return False
    except Exception as e:
        app.logger.warning('notify file-lock failed (%s), continuing', e)
        # continue to Redis layer

    # ── Layer 2: Redis NX pipeline ──────────────────────────────────────────
    rest_url = os.environ.get('UPSTASH_REDIS_REST_URL', '').strip().rstrip('/')
    token = os.environ.get('UPSTASH_REDIS_REST_TOKEN', '')
    if not rest_url or not token:
        return True  # no Redis configured → trust file lock alone
    try:
        resp = requests.post(
            f'{rest_url}/pipeline',
            headers={'Authorization': f'Bearer {token}',
                     'Content-Type': 'application/json'},
            json=[['SET', key, '1', 'NX', 'EX', str(ttl)]],
            timeout=3,
        )
        results = resp.json()
        if isinstance(results, list) and results:
            if results[0].get('result') != 'OK':
                lock_path.unlink(missing_ok=True)
                app.logger.info('notify lock (Redis) already held for %s — skipping', key)
                return False
        return True
    except Exception as e:
        app.logger.warning('notify Redis-lock failed (%s), trusting file lock', e)
        return True


def _scheduled_line_notify(kind: str, hour: int, minute: int) -> None:
    """Background thread: fire LINE push notifications at a fixed daily JST time.

    kind  : 'evening' (翌日予報) or 'morning' (当日予報)
    hour  : JST hour  (16 for evening, 1 for morning)
    minute: JST minute (0 for evening, 30 for morning)

    Uses a Redis NX lock so only one Gunicorn worker sends per day,
    even when --workers > 1.
    """
    import time
    from datetime import timedelta
    while True:
        now = datetime.now(tz=JST)
        next_run = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if now >= next_run:
            next_run += timedelta(days=1)
        time.sleep((next_run - now).total_seconds())

        date_str = datetime.now(tz=JST).strftime('%Y-%m-%d')
        lock_key = f'line_notify_lock:{kind}:{date_str}'

        if _try_acquire_notify_lock(lock_key):
            try:
                from line_integration import notify_all
                result = notify_all(kind)
                app.logger.info('LINE %s notification result: %s', kind, result)
            except Exception as exc:
                app.logger.error('LINE %s notification failed: %s', kind, exc)
            # 通知時刻のナウキャストスナップショットを記録（lockを取得したワーカーのみ）
            _record_nowcast_snapshot()
        else:
            app.logger.info(
                'LINE %s notification already sent by another worker, skipping', kind
            )


def _start_background_threads():
    """Start long-running background threads.  Called once from wsgi.py so the
    thread is NOT started when the module is merely imported (e.g. in tests or
    gunicorn worker forks before application code runs)."""
    # Nightly AMEDAS data collection at 03:00 JST
    t1 = _threading.Thread(target=_daily_amedas_collection, daemon=True)
    t1.start()

    # LINE evening notification at 16:00 JST (翌日予報)
    t2 = _threading.Thread(
        target=_scheduled_line_notify, args=('evening', 16, 0), daemon=True
    )
    t2.start()

    # LINE morning notification at 01:30 JST (当日予報)
    t3 = _threading.Thread(
        target=_scheduled_line_notify, args=('morning', 1, 30), daemon=True
    )
    t3.start()

    app.logger.info(
        'Background threads started: amedas@03:00, line-evening@16:00, line-morning@01:30 JST'
    )

# ============================================================================
# LINE Messaging API endpoints (line_integration.py)
# ============================================================================

@app.route('/line/webhook', methods=['POST'])
def line_webhook():
    """Receive LINE Platform webhooks. Verifies X-Line-Signature before processing."""
    from line_integration import handle_webhook  # lazy import avoids circular dep
    return handle_webhook()


@app.route('/api/line/status', methods=['GET'])
def line_status():
    """Return LINE integration status. Requires X-Admin-Secret when env var is set."""
    admin_secret = os.environ.get('LINE_ADMIN_NOTIFY_SECRET', '')
    if admin_secret and request.headers.get('X-Admin-Secret') != admin_secret:
        return jsonify({'status': 'unauthorized'}), 401
    from line_integration import get_status
    return get_status()


@app.route('/api/line/debug', methods=['GET', 'POST'])
def line_debug():
    """Upstash connectivity diagnostic. Requires X-Notify-Secret header."""
    from line_integration import get_debug
    return get_debug()


@app.route('/api/line/subscriptions_summary', methods=['GET'])
def line_subscriptions_summary():
    """Return subscription count and per-source spot counts.
    No secrets exposed — source_ids are masked. No auth required."""
    from line_integration import load_subscriptions
    subs = load_subscriptions()
    entries = []
    for key, sub in subs.items():
        source_type = sub.get('source_type', '?')
        source_id   = sub.get('source_id', '')
        masked_id   = source_id[:4] + '***' if len(source_id) > 4 else '***'
        entries.append({
            'key':          f'{source_type}:{masked_id}',
            'source_type':  source_type,
            'spot_ids':     sub.get('spots', []),   # H_XXXX_XXXX IDs (not sensitive)
            'spot_nicknames': sub.get('spot_nicknames', {}),
            'spots':        len(sub.get('spots', [])),
            'notify_enabled': sub.get('notify_enabled', False),
            'season_start': sub.get('season_start', ''),
            'season_end':   sub.get('season_end', ''),
        })
    return jsonify({
        'total_subscriptions': len(entries),
        'entries': entries,
        'note': 'source_ids are masked for privacy',
    })


@app.route('/api/line/notify', methods=['POST'])
def line_notify():
    """Trigger broadcast push for all LINE subscribers (Render Cron / admin)."""
    from line_integration import handle_notify
    return handle_notify()


@app.route('/api/line/setup-richmenu', methods=['POST'])
def line_setup_rich_menu():
    """
    Create / replace the LINE rich menu and upload auto-generated image.
    Requires X-Notify-Secret header or 'secret' in JSON body.
    """
    from line_integration import handle_setup_rich_menu
    return handle_setup_rich_menu()


if __name__ == '__main__':
    main()
