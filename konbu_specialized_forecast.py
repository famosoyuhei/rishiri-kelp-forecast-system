import requests
import pandas as pd
from datetime import datetime, timedelta
import numpy as np
try:
    from sea_fog_prediction import SeaFogPredictionEngine
except ImportError:
    SeaFogPredictionEngine = None

class KonbuForecastSystem:
    """利尻島昆布漁師専用の時間帯特化型予報システム"""
    
    def __init__(self):
        self.morning_start = 4   # 朝の作業開始時間（風が重要）
        self.morning_end = 10    # 手直し開始時間
        self.afternoon_start = 10 # 乾燥開始時間（日射が重要）
        self.afternoon_end = 16   # 回収時間
        self.work_end = 16       # 作業終了時間
        
        # 海霧予測エンジンの初期化
        self.sea_fog_engine = SeaFogPredictionEngine() if SeaFogPredictionEngine else None
        
    def get_specialized_weather(self, lat, lon, date):
        """昆布漁師向け特化型気象データ取得"""
        url = "https://api.open-meteo.com/v1/forecast"
        
        # 翌日から1週間の予報
        start_date = date
        end_date = (datetime.strptime(date, "%Y-%m-%d") + timedelta(days=7)).strftime("%Y-%m-%d")
        
        params = {
            "latitude": lat,
            "longitude": lon,
            "start_date": start_date,
            "end_date": end_date,
            "hourly": "temperature_2m,relative_humidity_2m,precipitation_probability,precipitation,wind_speed_10m,wind_direction_10m,shortwave_radiation,cloud_cover,weather_code",
            "timezone": "Asia/Tokyo"
        }
        
        try:
            response = requests.get(url, params=params)
            return response.json()["hourly"]
        except Exception as e:
            print(f"Weather data fetch error: {e}")
            return None
    
    def analyze_konbu_conditions(self, hourly_data, date_index=0):
        """昆布乾燥条件を時間帯別に分析"""
        # 24時間のオフセット計算（date_index=0は翌日）
        hour_offset = date_index * 24
        
        # 朝の作業時間帯（4-10時）の風条件
        morning_hours = range(self.morning_start + hour_offset, 
                            self.morning_end + hour_offset)
        
        # 昼の乾燥時間帯（10-16時）の日射条件  
        afternoon_hours = range(self.afternoon_start + hour_offset,
                              self.afternoon_end + hour_offset)
        
        # 全作業時間帯（4-16時）の降水条件
        work_hours = range(self.morning_start + hour_offset,
                          self.work_end + hour_offset)
        
        analysis = {}
        
        try:
            # 朝の風条件分析（4-10時）
            morning_winds = [hourly_data["wind_speed_10m"][h] for h in morning_hours]
            analysis["morning_wind"] = {
                "avg_speed": np.mean(morning_winds),
                "max_speed": np.max(morning_winds),
                "min_speed": np.min(morning_winds),
                "optimal": 2.0 <= np.mean(morning_winds) <= 8.0,  # 適度な風
                "too_strong": np.max(morning_winds) > 12.0,        # 強すぎる風
                "too_weak": np.mean(morning_winds) < 1.0           # 弱すぎる風
            }
            
            # 昼の日射条件分析（10-16時）
            afternoon_radiation = [hourly_data["shortwave_radiation"][h] for h in afternoon_hours]
            analysis["afternoon_radiation"] = {
                "total": sum(afternoon_radiation),
                "avg": np.mean(afternoon_radiation),
                "peak": np.max(afternoon_radiation),
                "sufficient": sum(afternoon_radiation) >= 3000,    # 十分な日射量
                "excellent": sum(afternoon_radiation) >= 4500     # 優秀な日射量
            }
            
            # 全日降水条件分析（4-16時）
            work_precipitation = [hourly_data["precipitation_probability"][h] for h in work_hours]
            work_actual_rain = [hourly_data["precipitation"][h] for h in work_hours]
            analysis["precipitation"] = {
                "max_probability": np.max(work_precipitation),
                "avg_probability": np.mean(work_precipitation),
                "total_rain": sum(work_actual_rain),
                "safe": np.max(work_precipitation) < 30,           # 安全な降水確率
                "risky": np.max(work_precipitation) > 50,          # 危険な降水確率
                "any_rain": sum(work_actual_rain) > 0.1            # 実際の降水
            }
            
            # 湿度・雲条件分析
            work_humidity = [hourly_data["relative_humidity_2m"][h] for h in work_hours]
            work_cloud = [hourly_data.get("cloud_cover", [0]*200)[h] for h in work_hours]
            analysis["humidity_cloud"] = {
                "max_humidity": np.max(work_humidity),
                "avg_humidity": np.mean(work_humidity),
                "max_cloud": np.max(work_cloud),
                "dry_enough": np.max(work_humidity) < 80,          # 乾燥十分
                "too_humid": np.max(work_humidity) > 90,           # 高湿度
                "cloudy": np.max(work_cloud) > 80                  # 曇りリスク
            }
            
            # 海霧予測分析（利用可能な場合）
            if self.sea_fog_engine:
                try:
                    date_str = (datetime.now() + timedelta(days=date_index)).strftime("%Y-%m-%d")
                    fog_prediction = self.sea_fog_engine.predict_sea_fog(lat, lon, date_str, 24)
                    
                    if "error" not in fog_prediction:
                        # 作業時間帯の海霧リスクを抽出
                        work_hour_fog_risks = []
                        for hour_pred in fog_prediction.get("hourly_predictions", []):
                            hour_dt = datetime.fromisoformat(hour_pred["datetime"])
                            if self.morning_start <= hour_dt.hour <= self.work_end:
                                work_hour_fog_risks.append(hour_pred["fog_probability"])
                        
                        if work_hour_fog_risks:
                            analysis["sea_fog"] = {
                                "max_probability": max(work_hour_fog_risks),
                                "avg_probability": np.mean(work_hour_fog_risks),
                                "high_risk_hours": sum(1 for risk in work_hour_fog_risks if risk >= 0.6),
                                "recommendation": fog_prediction["summary"]["work_hours_risk"]["recommendation"],
                                "alert_level": max([
                                    hour_pred["alert_level"]["level"] for hour_pred in fog_prediction.get("hourly_predictions", [])
                                    if self.morning_start <= datetime.fromisoformat(hour_pred["datetime"]).hour <= self.work_end
                                ], default=0),
                                "trend": fog_prediction["summary"].get("trend_analysis", "不明")
                            }
                        else:
                            analysis["sea_fog"] = {"status": "データ不足"}
                    else:
                        analysis["sea_fog"] = {"status": "予測エラー", "error": fog_prediction.get("error")}
                        
                except Exception as e:
                    analysis["sea_fog"] = {"status": "システムエラー", "error": str(e)}
            else:
                analysis["sea_fog"] = {"status": "機能無効"}
            
            # 総合判定
            analysis["overall"] = self.make_konbu_decision(analysis, lat, lon)
            
        except Exception as e:
            print(f"Analysis error: {e}")
            analysis["error"] = str(e)
        
        return analysis
    
    def make_konbu_decision(self, analysis, lat=None, lon=None):
        """昆布乾燥の総合判定（海霧要因含む）"""
        decision = {
            "recommendation": "unknown",
            "confidence": 0,
            "reasons": [],
            "warnings": []
        }
        
        try:
            # 基本条件チェック
            wind_ok = analysis["morning_wind"]["optimal"]
            radiation_ok = analysis["afternoon_radiation"]["sufficient"] 
            rain_ok = analysis["precipitation"]["safe"]
            humidity_ok = analysis["humidity_cloud"]["dry_enough"]
            
            # ポジティブ要因
            positive_score = 0
            if wind_ok:
                positive_score += 25
                decision["reasons"].append("朝の風条件良好")
            
            if analysis["afternoon_radiation"]["excellent"]:
                positive_score += 30
                decision["reasons"].append("優秀な日射量")
            elif radiation_ok:
                positive_score += 20
                decision["reasons"].append("十分な日射量")
            
            if rain_ok:
                positive_score += 20
                decision["reasons"].append("降水リスク低")
                
            if humidity_ok:
                positive_score += 15
                decision["reasons"].append("湿度適正")
            
            # ネガティブ要因
            negative_score = 0
            if analysis["morning_wind"]["too_strong"]:
                negative_score += 30
                decision["warnings"].append("朝の風が強すぎる")
            elif analysis["morning_wind"]["too_weak"]:
                negative_score += 20
                decision["warnings"].append("朝の風が弱い")
                
            if not radiation_ok:
                negative_score += 35
                decision["warnings"].append("日射量不足")
                
            if analysis["precipitation"]["risky"]:
                negative_score += 40
                decision["warnings"].append("降水リスク高")
            elif analysis["precipitation"]["any_rain"]:
                negative_score += 25
                decision["warnings"].append("降水予報あり")
                
            if analysis["humidity_cloud"]["too_humid"]:
                negative_score += 25
                decision["warnings"].append("高湿度")
                
            if analysis["humidity_cloud"]["cloudy"]:
                negative_score += 20
                decision["warnings"].append("曇り予報")
            
            # 海霧リスク評価
            if "sea_fog" in analysis and analysis["sea_fog"].get("status") != "機能無効":
                fog_data = analysis["sea_fog"]
                
                if fog_data.get("status") in ["データ不足", "予測エラー", "システムエラー"]:
                    decision["warnings"].append(f"海霧予測：{fog_data.get('status', '不明')}")
                else:
                    max_fog_prob = fog_data.get("max_probability", 0)
                    avg_fog_prob = fog_data.get("avg_probability", 0)
                    alert_level = fog_data.get("alert_level", 0)
                    high_risk_hours = fog_data.get("high_risk_hours", 0)
                    
                    if alert_level >= 3:  # 危険レベル
                        negative_score += 50
                        decision["warnings"].append(f"海霧危険（最大確率{max_fog_prob:.1%}）")
                    elif alert_level >= 2:  # 警戒レベル
                        negative_score += 35
                        decision["warnings"].append(f"海霧警戒（最大確率{max_fog_prob:.1%}）")
                    elif alert_level >= 1:  # 注意レベル
                        negative_score += 20
                        decision["warnings"].append(f"海霧注意（最大確率{max_fog_prob:.1%}）")
                    elif avg_fog_prob < 0.1:
                        # 海霧リスク低い場合はポジティブ要因
                        positive_score += 10
                        decision["reasons"].append("海霧リスク低")
                    
                    if high_risk_hours > 6:  # 6時間以上高リスク
                        negative_score += 15
                        decision["warnings"].append(f"長時間海霧リスク（{high_risk_hours}時間）")
            
            # 最終判定
            final_score = positive_score - negative_score
            decision["confidence"] = max(0, min(100, final_score))
            
            if final_score >= 60:
                decision["recommendation"] = "◎ 干せる"
            elif final_score >= 30:
                decision["recommendation"] = "○ 条件次第で干せる"
            elif final_score >= 0:
                decision["recommendation"] = "△ 注意が必要"
            else:
                decision["recommendation"] = "× 干さない方が良い"
                
        except Exception as e:
            decision["error"] = str(e)
        
        return decision
    
    def get_week_forecast(self, lat, lon, start_date):
        """1週間の昆布乾燥予報"""
        hourly_data = self.get_specialized_weather(lat, lon, start_date)
        if not hourly_data:
            return None
        
        week_forecast = []
        
        for day in range(7):
            date_obj = datetime.strptime(start_date, "%Y-%m-%d") + timedelta(days=day)
            day_analysis = self.analyze_konbu_conditions(hourly_data, day)
            
            forecast = {
                "date": date_obj.strftime("%Y-%m-%d"),
                "day_of_week": date_obj.strftime("%A"),
                "analysis": day_analysis
            }
            week_forecast.append(forecast)
        
        return week_forecast

# テスト実行
if __name__ == "__main__":
    print("=== Rishiri Kelp Drying Forecast System Test ===")
    
    forecast_system = KonbuForecastSystem()
    
    # Sample drying spot forecast test (鴛泊港周辺の干場)
    test_lat = 45.241667
    test_lon = 141.230833
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    
    print(f"Test location: {test_lat}, {test_lon}")
    print(f"Forecast start date: {tomorrow}")
    
    week_forecast = forecast_system.get_week_forecast(test_lat, test_lon, tomorrow)
    
    if week_forecast:
        print(f"\n=== 7-Day Kelp Drying Forecast ===")
        for day_forecast in week_forecast:
            date = day_forecast["date"]
            day = day_forecast["day_of_week"]
            overall = day_forecast["analysis"].get("overall", {})
            
            recommendation = overall.get("recommendation", "Unknown")
            confidence = overall.get("confidence", 0)
            
            print(f"\n{date} ({day})")
            print(f"  Decision: {recommendation} (Confidence: {confidence}%)")
            
            if "reasons" in overall:
                for reason in overall["reasons"]:
                    print(f"  + {reason}")
            
            if "warnings" in overall:
                for warning in overall["warnings"]:
                    print(f"  ! {warning}")
    else:
        print("Failed to fetch forecast data")
    
    print(f"\n=== Test Complete ===")