import requests
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json
import os
from scipy import interpolate
import warnings
warnings.filterwarnings('ignore')

class SeaFogPredictionEngine:
    """利尻島専用海霧予測システム
    
    海霧発生の物理的メカニズム：
    1. 海水温と気温の差（海水温 > 気温 + 3°C で発生しやすい）
    2. 相対湿度（90%以上で発生しやすい）
    3. 風速（2-8m/s で滞留しやすい）
    4. 気圧配置（高気圧の縁で発生しやすい）
    5. 地形効果（利尻山による上昇気流）
    """
    
    def __init__(self):
        self.config_file = "sea_fog_config.json"
        self.historical_data_file = "sea_fog_historical.json"
        
        self.default_config = {
            "prediction_thresholds": {
                "temperature_difference": 3.0,    # 海水温-気温差（°C）
                "humidity_threshold": 90.0,       # 相対湿度閾値（%）
                "wind_min": 2.0,                  # 最小風速（m/s）
                "wind_max": 8.0,                  # 最大風速（m/s）
                "pressure_gradient": 2.0,         # 気圧勾配（hPa/100km）
                "cloud_cover_min": 60.0,          # 最小雲量（%）
                "visibility_threshold": 1000      # 視程閾値（m）
            },
            "rishiri_parameters": {
                "mountain_effect_radius": 15.0,   # 利尻山影響半径（km）
                "coastal_effect_distance": 5.0,  # 沿岸効果距離（km）
                "typical_sea_temp": {             # 月別典型海水温
                    "06": 8.0, "07": 12.0, "08": 16.0, "09": 14.0
                },
                "fog_prone_areas": [               # 霧多発地域
                    {"name": "鴛泊港周辺", "lat": 45.242, "lon": 141.242, "risk_factor": 1.3},
                    {"name": "仙法志港周辺", "lat": 45.134, "lon": 141.203, "risk_factor": 1.2},
                    {"name": "利尻山麓", "lat": 45.178, "lon": 141.228, "risk_factor": 1.4}
                ]
            },
            "prediction_models": {
                "statistical_weight": 0.4,       # 統計モデル重み
                "physical_weight": 0.6,          # 物理モデル重み
                "local_adjustment": 0.15         # 地域調整係数
            },
            "alert_levels": {
                "level_1": {"threshold": 0.3, "label": "注意", "color": "yellow"},
                "level_2": {"threshold": 0.6, "label": "警戒", "color": "orange"},
                "level_3": {"threshold": 0.8, "label": "危険", "color": "red"}
            }
        }
        
        self.load_config()
        self.load_historical_data()
        
    def load_config(self):
        """設定ファイルの読み込み"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    self.config = json.load(f)
            else:
                self.config = self.default_config.copy()
                self.save_config()
        except Exception as e:
            print(f"Sea fog config load error: {e}")
            self.config = self.default_config.copy()
    
    def save_config(self):
        """設定ファイルの保存"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Sea fog config save error: {e}")
    
    def load_historical_data(self):
        """過去の海霧データの読み込み"""
        try:
            if os.path.exists(self.historical_data_file):
                with open(self.historical_data_file, 'r', encoding='utf-8') as f:
                    self.historical_data = json.load(f)
            else:
                self.historical_data = []
        except Exception as e:
            print(f"Historical data load error: {e}")
            self.historical_data = []
    
    def save_historical_data(self):
        """過去データの保存"""
        try:
            with open(self.historical_data_file, 'w', encoding='utf-8') as f:
                json.dump(self.historical_data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Historical data save error: {e}")
    
    def get_enhanced_weather_data(self, lat, lon, date):
        """海霧予測用の詳細気象データ取得"""
        url = "https://api.open-meteo.com/v1/forecast"
        
        start_date = date
        end_date = (datetime.strptime(date, "%Y-%m-%d") + timedelta(days=3)).strftime("%Y-%m-%d")
        
        params = {
            "latitude": lat,
            "longitude": lon,
            "start_date": start_date,
            "end_date": end_date,
            "hourly": [
                "temperature_2m", "relative_humidity_2m", "precipitation",
                "wind_speed_10m", "wind_direction_10m", "pressure_msl",
                "cloud_cover", "visibility", "weather_code",
                "shortwave_radiation", "surface_pressure"
            ],
            "timezone": "Asia/Tokyo"
        }
        
        try:
            response = requests.get(url, params=params)
            data = response.json()
            return data.get("hourly", {})
        except Exception as e:
            print(f"Enhanced weather data fetch error: {e}")
            return {}
    
    def estimate_sea_surface_temperature(self, lat, lon, date):
        """海面水温の推定（月別典型値＋調整）"""
        try:
            date_obj = datetime.strptime(date, "%Y-%m-%d")
            month_key = date_obj.strftime("%m")
            
            # 基本海水温
            typical_temps = self.config["rishiri_parameters"]["typical_sea_temp"]
            base_temp = typical_temps.get(month_key, 10.0)
            
            # 地域別調整
            # 鴛泊港周辺（北側）: やや低め
            if lat > 45.2:
                adjustment = -0.5
            # 仙法志港周辺（南側）: やや高め
            elif lat < 45.15:
                adjustment = 0.5
            else:
                adjustment = 0.0
            
            return base_temp + adjustment
            
        except Exception as e:
            print(f"Sea temperature estimation error: {e}")
            return 10.0  # デフォルト値
    
    def calculate_physical_fog_probability(self, weather_data, lat, lon, hour_index):
        """物理的メカニズムに基づく海霧発生確率計算"""
        try:
            # 基本気象パラメータ
            temp = weather_data.get("temperature_2m", [0] * 200)[hour_index]
            humidity = weather_data.get("relative_humidity_2m", [0] * 200)[hour_index]
            wind_speed = weather_data.get("wind_speed_10m", [0] * 200)[hour_index]
            pressure = weather_data.get("pressure_msl", [1013] * 200)[hour_index]
            cloud_cover = weather_data.get("cloud_cover", [0] * 200)[hour_index]
            visibility = weather_data.get("visibility", [10000] * 200)[hour_index]
            
            # 海水温推定
            date_str = datetime.now().strftime("%Y-%m-%d")
            sea_temp = self.estimate_sea_surface_temperature(lat, lon, date_str)
            
            # 温度差要因（海水温 > 気温の場合に霧が発生しやすい）
            temp_diff = sea_temp - temp
            temp_factor = 0.0
            if temp_diff > self.config["prediction_thresholds"]["temperature_difference"]:
                temp_factor = min(temp_diff / 6.0, 1.0)  # 6°C差で最大
            
            # 湿度要因
            humidity_threshold = self.config["prediction_thresholds"]["humidity_threshold"]
            humidity_factor = 0.0
            if humidity > humidity_threshold:
                humidity_factor = min((humidity - humidity_threshold) / 10.0, 1.0)
            
            # 風速要因（適度な風で霧が滞留）
            wind_min = self.config["prediction_thresholds"]["wind_min"]
            wind_max = self.config["prediction_thresholds"]["wind_max"]
            wind_factor = 0.0
            if wind_min <= wind_speed <= wind_max:
                # 最適風速は5m/s付近
                optimal_wind = 5.0
                wind_factor = 1.0 - abs(wind_speed - optimal_wind) / optimal_wind
                wind_factor = max(0.0, wind_factor)
            elif wind_speed < wind_min:
                # 風が弱すぎる場合は部分的に有利
                wind_factor = wind_speed / wind_min * 0.6
            
            # 雲量要因（適度な雲が必要）
            cloud_threshold = self.config["prediction_thresholds"]["cloud_cover_min"]
            cloud_factor = 0.0
            if cloud_cover > cloud_threshold:
                cloud_factor = min(cloud_cover / 100.0, 1.0)
            
            # 既存の視程要因（低視程は霧の可能性）
            visibility_threshold = self.config["prediction_thresholds"]["visibility_threshold"]
            visibility_factor = 0.0
            if visibility < visibility_threshold:
                visibility_factor = 1.0 - (visibility / visibility_threshold)
            
            # 地形効果（利尻山の影響）
            mountain_effect = self.calculate_mountain_effect(lat, lon)
            
            # 総合確率計算（重み付き平均）
            factors = {
                "temperature": temp_factor * 0.25,
                "humidity": humidity_factor * 0.25,
                "wind": wind_factor * 0.20,
                "cloud": cloud_factor * 0.15,
                "visibility": visibility_factor * 0.10,
                "mountain": mountain_effect * 0.05
            }
            
            total_probability = sum(factors.values())
            
            return {
                "probability": min(total_probability, 1.0),
                "factors": factors,
                "conditions": {
                    "temperature": temp,
                    "sea_temperature": sea_temp,
                    "temperature_difference": temp_diff,
                    "humidity": humidity,
                    "wind_speed": wind_speed,
                    "cloud_cover": cloud_cover,
                    "visibility": visibility,
                    "pressure": pressure
                }
            }
            
        except Exception as e:
            print(f"Physical fog probability calculation error: {e}")
            return {"probability": 0.0, "factors": {}, "conditions": {}}
    
    def calculate_mountain_effect(self, lat, lon):
        """利尻山による地形効果の計算"""
        try:
            # 利尻山の座標
            mountain_lat = 45.178
            mountain_lon = 141.228
            
            # 距離計算（簡易版）
            lat_diff = lat - mountain_lat
            lon_diff = lon - mountain_lon
            distance_km = ((lat_diff * 111.0) ** 2 + (lon_diff * 85.0) ** 2) ** 0.5
            
            # 影響半径内での効果計算
            radius = self.config["rishiri_parameters"]["mountain_effect_radius"]
            if distance_km < radius:
                # 山に近いほど上昇気流による霧発生効果が大きい
                effect = (radius - distance_km) / radius * 0.3
                return effect
            
            return 0.0
            
        except Exception as e:
            print(f"Mountain effect calculation error: {e}")
            return 0.0
    
    def calculate_statistical_fog_probability(self, weather_data, lat, lon, hour_index):
        """過去データに基づく統計的海霧発生確率"""
        try:
            # 過去データから類似条件を検索
            current_conditions = {
                "temperature": weather_data.get("temperature_2m", [0] * 200)[hour_index],
                "humidity": weather_data.get("relative_humidity_2m", [0] * 200)[hour_index],
                "wind_speed": weather_data.get("wind_speed_10m", [0] * 200)[hour_index],
                "pressure": weather_data.get("pressure_msl", [1013] * 200)[hour_index]
            }
            
            # 過去データがない場合は物理モデルベースの初期値
            if not self.historical_data:
                return self.estimate_seasonal_probability(lat, lon)
            
            # 類似条件の検索と確率計算
            similar_count = 0
            fog_count = 0
            
            for record in self.historical_data:
                similarity = self.calculate_condition_similarity(current_conditions, record)
                if similarity > 0.7:  # 70%以上の類似度
                    similar_count += 1
                    if record.get("fog_observed", False):
                        fog_count += 1
            
            if similar_count > 0:
                return fog_count / similar_count
            else:
                return self.estimate_seasonal_probability(lat, lon)
                
        except Exception as e:
            print(f"Statistical fog probability calculation error: {e}")
            return 0.1  # デフォルト確率
    
    def calculate_condition_similarity(self, current, historical):
        """気象条件の類似度計算"""
        try:
            hist_conditions = historical.get("conditions", {})
            
            temp_sim = 1.0 - abs(current["temperature"] - hist_conditions.get("temperature", 15)) / 20.0
            humidity_sim = 1.0 - abs(current["humidity"] - hist_conditions.get("humidity", 70)) / 50.0
            wind_sim = 1.0 - abs(current["wind_speed"] - hist_conditions.get("wind_speed", 5)) / 10.0
            pressure_sim = 1.0 - abs(current["pressure"] - hist_conditions.get("pressure", 1013)) / 50.0
            
            # 負の値を0にクリップ
            similarities = [max(0, sim) for sim in [temp_sim, humidity_sim, wind_sim, pressure_sim]]
            
            return np.mean(similarities)
            
        except Exception as e:
            print(f"Condition similarity calculation error: {e}")
            return 0.0
    
    def estimate_seasonal_probability(self, lat, lon):
        """季節・地域別の基準確率推定"""
        try:
            month = datetime.now().month
            
            # 夏季（6-8月）は海霧が多い
            if 6 <= month <= 8:
                base_prob = 0.25
            elif month in [5, 9]:
                base_prob = 0.15
            else:
                base_prob = 0.05
            
            # 地域別調整
            fog_areas = self.config["rishiri_parameters"]["fog_prone_areas"]
            for area in fog_areas:
                area_lat = area["lat"]
                area_lon = area["lon"]
                
                # 距離計算
                lat_diff = lat - area_lat
                lon_diff = lon - area_lon
                distance = ((lat_diff * 111.0) ** 2 + (lon_diff * 85.0) ** 2) ** 0.5
                
                # 2km以内なら地域係数を適用
                if distance < 2.0:
                    risk_factor = area["risk_factor"]
                    base_prob *= risk_factor
                    break
            
            return min(base_prob, 1.0)
            
        except Exception as e:
            print(f"Seasonal probability estimation error: {e}")
            return 0.1
    
    def predict_sea_fog(self, lat, lon, date, hours_ahead=24):
        """指定地点・期間の海霧予測"""
        try:
            weather_data = self.get_enhanced_weather_data(lat, lon, date)
            if not weather_data:
                return {"error": "気象データ取得に失敗しました"}
            
            predictions = []
            
            for hour in range(min(hours_ahead, len(weather_data.get("temperature_2m", [])))):
                # 物理モデル確率
                physical_result = self.calculate_physical_fog_probability(weather_data, lat, lon, hour)
                physical_prob = physical_result["probability"]
                
                # 統計モデル確率
                statistical_prob = self.calculate_statistical_fog_probability(weather_data, lat, lon, hour)
                
                # 重み付き統合
                model_weights = self.config["prediction_models"]
                combined_prob = (
                    physical_prob * model_weights["physical_weight"] +
                    statistical_prob * model_weights["statistical_weight"]
                )
                
                # 地域調整
                local_adj = model_weights["local_adjustment"]
                final_prob = combined_prob * (1 + local_adj) if combined_prob > 0.5 else combined_prob
                final_prob = min(final_prob, 1.0)
                
                # アラートレベル決定
                alert_level = self.determine_alert_level(final_prob)
                
                # 時刻計算
                hour_datetime = datetime.strptime(date, "%Y-%m-%d") + timedelta(hours=hour)
                
                prediction = {
                    "datetime": hour_datetime.isoformat(),
                    "hour": hour,
                    "fog_probability": round(final_prob, 3),
                    "alert_level": alert_level,
                    "components": {
                        "physical_probability": round(physical_prob, 3),
                        "statistical_probability": round(statistical_prob, 3)
                    },
                    "factors": physical_result.get("factors", {}),
                    "conditions": physical_result.get("conditions", {}),
                    "recommendations": self.generate_recommendations(final_prob, physical_result.get("conditions", {}))
                }
                
                predictions.append(prediction)
            
            # サマリー作成
            summary = self.create_prediction_summary(predictions)
            
            return {
                "location": {"lat": lat, "lon": lon},
                "prediction_date": date,
                "summary": summary,
                "hourly_predictions": predictions,
                "generated_at": datetime.now().isoformat()
            }
            
        except Exception as e:
            print(f"Sea fog prediction error: {e}")
            return {"error": f"予測計算エラー: {str(e)}"}
    
    def determine_alert_level(self, probability):
        """確率に基づくアラートレベルの決定"""
        alert_levels = self.config["alert_levels"]
        
        if probability >= alert_levels["level_3"]["threshold"]:
            return {
                "level": 3,
                "label": alert_levels["level_3"]["label"],
                "color": alert_levels["level_3"]["color"]
            }
        elif probability >= alert_levels["level_2"]["threshold"]:
            return {
                "level": 2,
                "label": alert_levels["level_2"]["label"],
                "color": alert_levels["level_2"]["color"]
            }
        elif probability >= alert_levels["level_1"]["threshold"]:
            return {
                "level": 1,
                "label": alert_levels["level_1"]["label"],
                "color": alert_levels["level_1"]["color"]
            }
        else:
            return {
                "level": 0,
                "label": "正常",
                "color": "green"
            }
    
    def generate_recommendations(self, probability, conditions):
        """海霧確率に基づく推奨事項生成"""
        recommendations = []
        
        if probability >= 0.8:
            recommendations.extend([
                "海霧の発生可能性が非常に高いです",
                "昆布作業の延期を強く推奨します",
                "視程が急激に悪化する可能性があります",
                "港での待機を検討してください"
            ])
        elif probability >= 0.6:
            recommendations.extend([
                "海霧の発生可能性が高いです",
                "作業開始を慎重に判断してください",
                "視程確保用の装備を準備してください",
                "天候変化を密に監視してください"
            ])
        elif probability >= 0.3:
            recommendations.extend([
                "海霧発生の可能性があります",
                "作業中の視程変化に注意してください",
                "緊急時の対応計画を確認してください"
            ])
        else:
            recommendations.append("海霧の心配は少ないです")
        
        # 条件別の追加推奨事項
        wind_speed = conditions.get("wind_speed", 0)
        humidity = conditions.get("humidity", 0)
        
        if wind_speed < 2.0:
            recommendations.append("風が弱く、霧が滞留しやすい条件です")
        elif wind_speed > 10.0:
            recommendations.append("強風により作業自体が困難な可能性があります")
        
        if humidity > 95:
            recommendations.append("非常に高い湿度により霧が発生しやすい状況です")
        
        return recommendations
    
    def create_prediction_summary(self, predictions):
        """予測結果のサマリー作成"""
        try:
            if not predictions:
                return {}
            
            probabilities = [p["fog_probability"] for p in predictions]
            max_prob = max(probabilities)
            avg_prob = np.mean(probabilities)
            
            # 最高リスク時間帯
            max_risk_prediction = max(predictions, key=lambda x: x["fog_probability"])
            
            # 作業時間帯（4-16時）のリスク
            work_hours_risk = []
            for p in predictions:
                hour_dt = datetime.fromisoformat(p["datetime"])
                if 4 <= hour_dt.hour <= 16:
                    work_hours_risk.append(p["fog_probability"])
            
            work_hours_avg = np.mean(work_hours_risk) if work_hours_risk else 0
            
            return {
                "overall_risk": {
                    "maximum_probability": round(max_prob, 3),
                    "average_probability": round(avg_prob, 3),
                    "peak_risk_time": max_risk_prediction["datetime"],
                    "alert_level": max_risk_prediction["alert_level"]
                },
                "work_hours_risk": {
                    "average_probability": round(work_hours_avg, 3),
                    "recommendation": "作業可能" if work_hours_avg < 0.3 else "要注意" if work_hours_avg < 0.6 else "作業困難"
                },
                "trend_analysis": self.analyze_trend(probabilities)
            }
            
        except Exception as e:
            print(f"Summary creation error: {e}")
            return {}
    
    def analyze_trend(self, probabilities):
        """確率推移の傾向分析"""
        try:
            if len(probabilities) < 3:
                return "データ不足"
            
            # 線形回帰による傾向分析
            hours = np.arange(len(probabilities))
            slope = np.polyfit(hours, probabilities, 1)[0]
            
            if slope > 0.02:
                return "上昇傾向（悪化）"
            elif slope < -0.02:
                return "下降傾向（改善）"
            else:
                return "安定"
                
        except Exception as e:
            print(f"Trend analysis error: {e}")
            return "不明"
    
    def add_observation(self, lat, lon, datetime_str, fog_observed, conditions):
        """観測データの追加（学習用）"""
        try:
            observation = {
                "lat": lat,
                "lon": lon,
                "datetime": datetime_str,
                "fog_observed": fog_observed,
                "conditions": conditions,
                "added_at": datetime.now().isoformat()
            }
            
            self.historical_data.append(observation)
            
            # データ数制限（最新1000件）
            if len(self.historical_data) > 1000:
                self.historical_data = self.historical_data[-1000:]
            
            self.save_historical_data()
            return True
            
        except Exception as e:
            print(f"Observation addition error: {e}")
            return False
    
    def get_fog_statistics(self, days_back=30):
        """過去の海霧統計"""
        try:
            cutoff_date = datetime.now() - timedelta(days=days_back)
            recent_data = [
                record for record in self.historical_data
                if datetime.fromisoformat(record["datetime"]) >= cutoff_date
            ]
            
            if not recent_data:
                return {"message": "統計データがありません"}
            
            total_records = len(recent_data)
            fog_records = sum(1 for record in recent_data if record["fog_observed"])
            
            return {
                "period_days": days_back,
                "total_observations": total_records,
                "fog_observations": fog_records,
                "fog_frequency": round(fog_records / total_records, 3) if total_records > 0 else 0,
                "data_quality": "良好" if total_records >= days_back * 4 else "要改善"
            }
            
        except Exception as e:
            print(f"Statistics calculation error: {e}")
            return {"error": str(e)}

if __name__ == "__main__":
    # テスト実行
    print("=== Sea Fog Prediction Engine Test ===")
    
    engine = SeaFogPredictionEngine()
    
    # 利尻島鴛泊港での予測テスト
    test_date = datetime.now().strftime("%Y-%m-%d")
    prediction = engine.predict_sea_fog(45.242, 141.242, test_date, 12)
    
    if "error" not in prediction:
        print(f"\\nTest Location: 鴛泊港周辺")
        print(f"Date: {test_date}")
        print(f"Maximum Risk: {prediction['summary']['overall_risk']['maximum_probability']}")
        print(f"Work Hours Risk: {prediction['summary']['work_hours_risk']['average_probability']}")
        print(f"Recommendation: {prediction['summary']['work_hours_risk']['recommendation']}")
        
        # 高リスク時間の表示
        high_risk_hours = [
            p for p in prediction["hourly_predictions"]
            if p["fog_probability"] >= 0.5
        ]
        
        if high_risk_hours:
            print(f"\\nHigh Risk Hours ({len(high_risk_hours)} hours):")
            for hour_pred in high_risk_hours[:3]:  # 最初の3件のみ
                dt = datetime.fromisoformat(hour_pred["datetime"])
                print(f"  {dt.strftime('%H:%M')} - Probability: {hour_pred['fog_probability']:.3f}")
        
        print("\\n=== Test Completed ===")
    else:
        print(f"Test failed: {prediction['error']}")