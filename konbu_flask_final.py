from dotenv import load_dotenv
load_dotenv()
from flask import Flask, request, jsonify, send_file, render_template_string
import pandas as pd
import os
import csv
import datetime
import requests
from flask_cors import CORS
from openai import OpenAI
import joblib
import numpy as np
from konbu_specialized_forecast import KonbuForecastSystem
from adaptive_learning_system import AdaptiveLearningSystem
try:
    from sea_fog_prediction import SeaFogPredictionEngine
    from sea_fog_visualization import SeaFogVisualization
except ImportError:
    SeaFogPredictionEngine = None
    SeaFogVisualization = None
from fishing_season_manager import FishingSeasonManager
from notification_system import NotificationSystem
from system_monitor import SystemMonitor
from backup_system import BackupSystem
from favorites_manager import FavoritesManager

app = Flask(__name__)
CORS(app)

CSV_FILE = "hoshiba_spots.csv"
RECORD_FILE = "hoshiba_records.csv"
KML_FILE = "hoshiba_spots_named.kml"

# Initialize systems
konbu_forecast = KonbuForecastSystem()
adaptive_learning = AdaptiveLearningSystem()
fishing_season = FishingSeasonManager()
notification_system = NotificationSystem()
system_monitor = SystemMonitor()
backup_system = BackupSystem()
favorites_manager = FavoritesManager()
sea_fog_engine = SeaFogPredictionEngine() if SeaFogPredictionEngine else None
sea_fog_viz = SeaFogVisualization() if SeaFogVisualization else None

# Initialize Sea Fog Alert System
try:
    from sea_fog_alert_system import SeaFogAlertSystem
    sea_fog_alerts = SeaFogAlertSystem()
except ImportError:
    sea_fog_alerts = None

# Initialize Personal Notification System
try:
    from personal_notification_system import PersonalNotificationSystem
    personal_notifications = PersonalNotificationSystem()
except ImportError:
    personal_notifications = None

# Initialize Data Visualization System
try:
    from data_visualization_system import DataVisualizationSystem
    data_visualization = DataVisualizationSystem()
except ImportError:
    data_visualization = None

# Load ML model (try adaptive model first)
try:
    model_data = joblib.load("adaptive_model.pkl")
    ml_model = model_data['model']
    model_features = model_data['features']
    print(f"Loaded adaptive ML model with features: {model_features}")
    print(f"Training size: {model_data.get('training_size', 'unknown')}")
    print(f"CV accuracy: {model_data.get('cv_accuracy', 'unknown'):.3f}")
except:
    try:
        model_data = joblib.load("improved_model.pkl")
        ml_model = model_data['model']
        model_features = model_data['features']
        print(f"Loaded improved ML model with features: {model_features}")
    except:
        try:
            ml_model = joblib.load("model.pkl")
            model_features = ["radiation_sum", "windspeed_mean"]
            print("Loaded basic model")
        except:
            ml_model = None
            model_features = []
            print("No ML model found")

@app.route("/")
def index():
    """メインページ - 完全版地図を表示"""
    try:
        with open("hoshiba_map_complete.html", "r", encoding="utf-8") as f:
            html_content = f.read()
        return html_content
    except:
        return """
        <h1>利尻島昆布干場予報システム</h1>
        <p>hoshiba_map_complete.html が見つかりません</p>
        <p><a href="/spots">干場一覧API</a></p>
        <p><a href="/konbu_forecast_test">昆布予報テスト</a></p>
        <p><a href="/dashboard">統合ダッシュボード</a></p>
        """

@app.route("/dashboard")
def dashboard():
    """統合ダッシュボードページ"""
    try:
        with open("dashboard.html", "r", encoding="utf-8") as f:
            html_content = f.read()
        return html_content
    except Exception as e:
        return f"""
        <h1>ダッシュボード表示エラー</h1>
        <p>dashboard.html が見つかりません: {str(e)}</p>
        <p><a href="/">メインページに戻る</a></p>
        """

@app.route("/spots")
def get_spots():
    """干場一覧を取得"""
    try:
        df = pd.read_csv(CSV_FILE)
        return jsonify(df.to_dict(orient="records"))
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/add", methods=["POST"])
def add_spot():
    """新規干場を追加"""
    try:
        data = request.get_json()
        new_row = pd.DataFrame([data])
        df = pd.read_csv(CSV_FILE)
        
        if data["name"] in df["name"].values:
            return jsonify({"status": "error", "message": "Name already exists"})
        
        df = pd.concat([df, new_row], ignore_index=True)
        df.to_csv(CSV_FILE, index=False, encoding="utf-8")
        generate_kml(df)
        
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/delete", methods=["POST"])
def delete_spot():
    """干場を削除（記録がない場合のみ）"""
    try:
        data = request.get_json()
        name = data["name"]
        
        # 記録があるかチェック
        if os.path.exists(RECORD_FILE):
            records_df = pd.read_csv(RECORD_FILE)
            if len(records_df[records_df["name"] == name]) > 0:
                return jsonify({
                    "status": "error", 
                    "message": "この干場には記録があるため削除できません"
                }), 400
        
        # 干場を削除
        df = pd.read_csv(CSV_FILE)
        df = df[df["name"] != name]
        df.to_csv(CSV_FILE, index=False, encoding="utf-8")
        generate_kml(df)
        
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/forecast")
def forecast():
    """昆布特化型予報を提供"""
    try:
        lat = float(request.args.get("lat"))
        lon = float(request.args.get("lon"))
        start_date = request.args.get("start_date", 
                                      (datetime.datetime.now() + datetime.timedelta(days=1)).strftime("%Y-%m-%d"))
        
        # 昆布特化型予報を取得
        tomorrow_analysis = konbu_forecast.get_week_forecast(lat, lon, start_date)
        
        if tomorrow_analysis and len(tomorrow_analysis) > 0:
            # 明日の予報データ
            tomorrow = tomorrow_analysis[0]
            analysis = tomorrow["analysis"]
            
            # Open-Meteo APIからの生データも取得
            hourly_data = konbu_forecast.get_specialized_weather(lat, lon, start_date)
            
            # ML予測（従来モデル）
            ml_result = None
            ml_confidence = 0
            if ml_model and hourly_data:
                try:
                    ml_result, ml_confidence = predict_with_ml_model(hourly_data)
                except:
                    ml_result = "ML prediction error"
            
            # 結果の統合
            result = {
                "konbu_specialized": {
                    "recommendation": analysis.get("overall", {}).get("recommendation", "不明"),
                    "confidence": analysis.get("overall", {}).get("confidence", 0),
                    "reasons": analysis.get("overall", {}).get("reasons", []),
                    "warnings": analysis.get("overall", {}).get("warnings", []),
                    "morning_wind": analysis.get("morning_wind", {}),
                    "afternoon_radiation": analysis.get("afternoon_radiation", {}),
                    "precipitation": analysis.get("precipitation", {}),
                    "humidity_cloud": analysis.get("humidity_cloud", {})
                },
                "ml_prediction": ml_result or "Model not available",
                "ml_confidence": ml_confidence,
                "week_forecast": tomorrow_analysis,
                "recommendation": analysis.get("overall", {}).get("recommendation", "不明")
            }
            
            return jsonify({"result": result, "hourly": hourly_data})
        else:
            return jsonify({"error": "Forecast data not available"}), 500
            
    except Exception as e:
        return jsonify({"error": f"Forecast error: {str(e)}"}), 500

@app.route("/konbu_forecast_test")
def konbu_forecast_test():
    """昆布予報システムのテスト画面"""
    return """
    <html>
    <head><title>昆布予報テスト</title></head>
    <body>
        <h1>🌊 昆布特化型予報システム テスト</h1>
        <div id="result"></div>
        <script>
        fetch('/forecast?lat=45.241667&lon=141.230833')
            .then(res => res.json())
            .then(data => {
                const result = data.result;
                let html = '<h2>予報結果</h2>';
                
                if (result.konbu_specialized) {
                    const ks = result.konbu_specialized;
                    html += `
                        <div style="border: 1px solid #ccc; padding: 15px; margin: 10px 0; border-radius: 5px;">
                            <h3>🎯 昆布特化型予報</h3>
                            <p><strong>総合判定:</strong> ${ks.recommendation}</p>
                            <p><strong>信頼度:</strong> ${ks.confidence}%</p>
                            
                            <h4>✅ 良好な条件</h4>
                            <ul>${ks.reasons.map(r => `<li>${r}</li>`).join('')}</ul>
                            
                            <h4>⚠️ 注意事項</h4>
                            <ul>${ks.warnings.map(w => `<li>${w}</li>`).join('')}</ul>
                            
                            <h4>📊 詳細条件</h4>
                            <p><strong>朝の風:</strong> 平均${ks.morning_wind.avg_speed?.toFixed(1)}m/s 
                               (${ks.morning_wind.optimal ? '適正' : '不適正'})</p>
                            <p><strong>昼の日射:</strong> 合計${ks.afternoon_radiation.total?.toFixed(0)}Wh/m² 
                               (${ks.afternoon_radiation.sufficient ? '十分' : '不足'})</p>
                            <p><strong>降水リスク:</strong> 最大${ks.precipitation.max_probability?.toFixed(0)}% 
                               (${ks.precipitation.safe ? '安全' : '注意'})</p>
                        </div>
                    `;
                }
                
                if (result.week_forecast) {
                    html += '<h3>📅 週間予報</h3>';
                    result.week_forecast.forEach(day => {
                        const overall = day.analysis.overall || {};
                        html += `
                            <div style="border: 1px solid #ddd; padding: 10px; margin: 5px 0;">
                                <strong>${day.date} (${day.day_of_week})</strong><br>
                                ${overall.recommendation || '不明'} (${overall.confidence || 0}%)
                            </div>
                        `;
                    });
                }
                
                document.getElementById('result').innerHTML = html;
            })
            .catch(err => {
                document.getElementById('result').innerHTML = '<p style="color: red;">エラー: ' + err + '</p>';
            });
        </script>
    </body>
    </html>
    """

@app.route("/record", methods=["POST"])
def record():
    """乾燥記録を保存"""
    try:
        data = request.get_json()
        name = data["name"]
        date = data["date"]
        result = data["result"]

        if not os.path.exists(RECORD_FILE):
            with open(RECORD_FILE, "w", newline='', encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["date", "name", "result"])

        df = pd.read_csv(RECORD_FILE)
        df = df[(df["date"] != date) | (df["name"] != name)]
        df = pd.concat([df, pd.DataFrame([[date, name, result]], columns=["date", "name", "result"])], ignore_index=True)
        df.to_csv(RECORD_FILE, index=False, encoding="utf-8")
        
        # Trigger adaptive learning after saving record
        try:
            adaptive_learning.process_new_records()
            print(f"Adaptive learning processed new record: {name} {date} {result}")
        except Exception as e:
            print(f"Adaptive learning error: {e}")
        
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/get_record")
def get_record():
    """記録を取得"""
    try:
        name = request.args.get("name")
        date = request.args.get("date")
        
        if not os.path.exists(RECORD_FILE):
            return jsonify({"result": ""})
        
        df = pd.read_csv(RECORD_FILE)
        row = df[(df["name"] == name) & (df["date"] == date)]
        
        if len(row) == 0:
            return jsonify({"result": ""})
        
        return jsonify({"result": row.iloc[0]["result"]})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/check_spot_records")
def check_spot_records():
    """干場に記録があるかチェック"""
    try:
        name = request.args.get("name")
        
        if not os.path.exists(RECORD_FILE):
            return jsonify({"has_records": False})
        
        df = pd.read_csv(RECORD_FILE)
        has_records = len(df[df["name"] == name]) > 0
        
        return jsonify({"has_records": has_records})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/chat", methods=["POST"])
def chat():
    """昆布漁師向けAIチャット"""
    try:
        data = request.get_json()
        user_message = data.get("message", "")
        
        if not user_message:
            return jsonify({"reply": "メッセージが空です。"})

        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        
        system_prompt = """あなたは利尻島の昆布漁師専門のAIアシスタントです。
昆布の天日干しに関する以下の専門知識を持っています：

【作業時間帯】
- 未明〜朝4時: 昆布引き上げ
- 朝4時〜10時: 干場での乾燥開始（適度な風が重要）
- 午前10時頃: 手直し作業
- 午前10時〜午後4時: 本格乾燥（日射量が最重要）
- 午後2-4時: 乾燥した昆布の回収

【重要な気象条件】
- 朝の風: 2-8m/s程度の適度な風が理想的
- 昼の日射: 10-16時の累積日射量3000Wh/m²以上が必要
- 降水: 作業時間中（4-16時）の降水確率30%未満が安全
- 湿度: 80%未満が望ましい
- 霧・雲: 日射を遮るため避けたい

昆布漁師の質問に実用的で的確なアドバイスをしてください。"""

        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ]
        )
        
        reply = response.choices[0].message.content
        return jsonify({"reply": reply})
        
    except Exception as e:
        return jsonify({"reply": f"エラーが発生しました: {str(e)}"})

@app.route("/download/csv")
def download_csv():
    """CSV ダウンロード"""
    return send_file(CSV_FILE, as_attachment=True)

@app.route("/download/kml")
def download_kml():
    """KML ダウンロード"""
    return send_file(KML_FILE, as_attachment=True)

def predict_with_ml_model(hourly_data):
    """ML予測（従来システム）"""
    if not ml_model:
        return "ML model not available", 0
    
    try:
        # 4-16時の気象データを集計
        hours = list(range(4, 17))
        radiation_sum = sum(hourly_data["shortwave_radiation"][h] for h in hours)
        windspeed_mean = sum(hourly_data["wind_speed_10m"][h] for h in hours) / len(hours)
        
        # 基本特徴量
        features = [radiation_sum, windspeed_mean]
        
        # 追加特徴量（利用可能な場合）
        if len(model_features) > 2:
            radiation_mean = radiation_sum / len(hours)
            winddirection_mean = sum(hourly_data.get("wind_direction_10m", [0]*24)[h] for h in hours) / len(hours)
            features.extend([radiation_mean, winddirection_mean])
        
        X = pd.DataFrame([features[:len(model_features)]], columns=model_features)
        prediction = ml_model.predict(X)[0]
        
        try:
            proba = ml_model.predict_proba(X)[0]
            confidence = max(proba)
        except:
            confidence = 0.8 if prediction == 1 else 0.6
        
        if prediction == 1:
            result = f"◎ 干せる（ML予測: 成功確率 {confidence:.1%}）"
        else:
            result = f"× 干せない（ML予測: 失敗確率 {1-confidence:.1%}）"
        
        return result, confidence
    
    except Exception as e:
        return f"ML prediction error: {str(e)}", 0

def generate_kml(df):
    """KMLファイル生成"""
    try:
        with open(KML_FILE, "w", encoding="utf-8") as f:
            f.write("<?xml version='1.0' encoding='UTF-8'?>\n")
            f.write("<kml xmlns='http://www.opengis.net/kml/2.2'>\n")
            f.write("<Document>\n")
            for _, row in df.iterrows():
                f.write("<Placemark>\n")
                f.write(f"<name>{row['name']}</name>\n")
                f.write("<Point><coordinates>{},{}</coordinates></Point>\n".format(row['lon'], row['lat']))
                f.write("</Placemark>\n")
            f.write("</Document>\n</kml>")
    except Exception as e:
        print(f"KML generation error: {e}")

@app.route("/adaptive_learning/process", methods=["POST"])
def process_adaptive_learning():
    """自動学習システムの手動実行"""
    try:
        new_data_added = adaptive_learning.process_new_records()
        
        if new_data_added:
            retrain_success = adaptive_learning.retrain_model()
            return jsonify({
                "status": "success",
                "new_data_added": True,
                "model_retrained": retrain_success,
                "message": "Adaptive learning completed successfully"
            })
        else:
            return jsonify({
                "status": "success", 
                "new_data_added": False,
                "message": "No new data to process"
            })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/adaptive_learning/quality")
def get_data_quality():
    """データ品質レポート取得"""
    try:
        quality_summary = adaptive_learning.get_data_quality_summary()
        return jsonify(quality_summary)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/adaptive_learning/retrain", methods=["POST"])
def retrain_model():
    """モデル再訓練の手動実行"""
    try:
        success = adaptive_learning.retrain_model()
        if success:
            # Reload the model in Flask app
            global ml_model, model_features
            try:
                model_data = joblib.load("adaptive_model.pkl")
                ml_model = model_data['model']
                model_features = model_data['features']
                return jsonify({
                    "status": "success",
                    "message": "Model retrained and reloaded successfully",
                    "features": model_features,
                    "training_size": model_data.get('training_size', 'unknown')
                })
            except:
                return jsonify({
                    "status": "partial_success",
                    "message": "Model retrained but failed to reload"
                })
        else:
            return jsonify({"status": "error", "message": "Model retraining failed"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/fishing_season/status")
def get_fishing_season_status():
    """漁期状況を取得"""
    try:
        date = request.args.get("date")  # YYYY-MM-DD形式
        status = fishing_season.get_season_status(date)
        return jsonify(status)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/fishing_season/schedule")
def get_work_schedule():
    """作業スケジュールを取得"""
    try:
        date = request.args.get("date")  # YYYY-MM-DD形式
        schedule_type = request.args.get("type", "daily")  # daily or weekly
        
        if schedule_type == "weekly":
            schedule = fishing_season.get_weekly_schedule(date)
        else:
            schedule = fishing_season.get_work_schedule(date)
        
        return jsonify(schedule)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/fishing_season/rest_days", methods=["GET", "POST", "DELETE"])
def manage_rest_days():
    """休漁日の管理"""
    try:
        if request.method == "GET":
            summary = fishing_season.get_season_summary()
            return jsonify({
                "rest_days": summary["rest_days"],
                "count": summary["rest_days_count"]
            })
        
        elif request.method == "POST":
            data = request.get_json()
            date = data.get("date")
            if fishing_season.add_rest_day(date):
                return jsonify({"status": "success", "message": "休漁日を追加しました"})
            else:
                return jsonify({"status": "error", "message": "既に休漁日に設定されています"})
        
        elif request.method == "DELETE":
            data = request.get_json()
            date = data.get("date")
            if fishing_season.remove_rest_day(date):
                return jsonify({"status": "success", "message": "休漁日を削除しました"})
            else:
                return jsonify({"status": "error", "message": "休漁日に設定されていません"})
                
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/fishing_season/config", methods=["GET", "PUT"])
def manage_season_config():
    """漁期設定の管理"""
    try:
        if request.method == "GET":
            summary = fishing_season.get_season_summary()
            return jsonify(summary)
        
        elif request.method == "PUT":
            data = request.get_json()
            if fishing_season.update_season_config(data):
                return jsonify({"status": "success", "message": "設定を更新しました"})
            else:
                return jsonify({"status": "error", "message": "設定の更新に失敗しました"})
                
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/notifications/config", methods=["GET", "PUT"])
def manage_notification_config():
    """通知設定の管理"""
    try:
        if request.method == "GET":
            config_summary = notification_system.get_config_summary()
            return jsonify(config_summary)
        
        elif request.method == "PUT":
            data = request.get_json()
            notification_type = data.get("notification_type")
            new_time = data.get("new_time")
            
            if notification_type and new_time:
                if notification_system.update_notification_time(notification_type, new_time):
                    return jsonify({"status": "success", "message": f"通知時刻を{new_time}に変更しました"})
                else:
                    return jsonify({"status": "error", "message": "通知時刻の変更に失敗しました"})
            else:
                return jsonify({"status": "error", "message": "notification_typeとnew_timeが必要です"})
                
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/notifications/subscribers", methods=["GET", "POST", "DELETE"])
def manage_subscribers():
    """通知対象者の管理"""
    try:
        if request.method == "GET":
            return jsonify({"subscribers": notification_system.subscribers})
        
        elif request.method == "POST":
            data = request.get_json()
            name = data.get("name")
            email = data.get("email")
            phone = data.get("phone")
            favorite_spots = data.get("favorite_spots", [])
            
            if name:
                subscriber_id = notification_system.add_subscriber(name, email, phone, favorite_spots)
                return jsonify({"status": "success", "subscriber_id": subscriber_id, "message": "通知対象者を追加しました"})
            else:
                return jsonify({"status": "error", "message": "名前が必要です"})
        
        elif request.method == "DELETE":
            data = request.get_json()
            subscriber_id = data.get("subscriber_id")
            
            if subscriber_id:
                notification_system.remove_subscriber(subscriber_id)
                return jsonify({"status": "success", "message": "通知対象者を削除しました"})
            else:
                return jsonify({"status": "error", "message": "subscriber_idが必要です"})
                
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/notifications/send", methods=["POST"])
def send_manual_notification():
    """手動通知の送信"""
    try:
        data = request.get_json()
        message = data.get("message")
        title = data.get("title", "手動通知")
        
        if message:
            success = notification_system.send_notification(message, title)
            if success:
                return jsonify({"status": "success", "message": "通知を送信しました"})
            else:
                return jsonify({"status": "error", "message": "通知の送信に失敗しました"})
        else:
            return jsonify({"status": "error", "message": "messageが必要です"})
            
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/notifications/test", methods=["POST"])
def test_notification():
    """通知システムのテスト"""
    try:
        # 利尻島の代表座標で予報取得
        forecast_data = notification_system.get_weather_forecast(45.178269, 141.228528)
        
        if forecast_data:
            test_message = notification_system.create_daily_forecast_message(forecast_data, "利尻島（テスト）")
            success = notification_system.send_notification(test_message, "🧪 通知システムテスト")
            
            if success:
                return jsonify({"status": "success", "message": "テスト通知を送信しました"})
            else:
                return jsonify({"status": "error", "message": "テスト通知の送信に失敗しました"})
        else:
            return jsonify({"status": "error", "message": "気象データを取得できませんでした"})
            
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/notifications/scheduler", methods=["GET", "POST", "DELETE"])
def manage_notification_scheduler():
    """通知スケジューラーの管理"""
    try:
        if request.method == "GET":
            return jsonify({
                "running": notification_system.running,
                "config": notification_system.get_config_summary()
            })
        
        elif request.method == "POST":
            notification_system.start_scheduler()
            return jsonify({"status": "success", "message": "通知スケジューラーを開始しました"})
        
        elif request.method == "DELETE":
            notification_system.stop_scheduler()
            return jsonify({"status": "success", "message": "通知スケジューラーを停止しました"})
            
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/system/monitor", methods=["GET", "POST", "DELETE"])
def manage_system_monitor():
    """システム監視の管理"""
    try:
        if request.method == "GET":
            # 監視状況と最新ヘルス情報を取得
            monitor_status = system_monitor.get_monitoring_status()
            latest_health = system_monitor.run_health_check()
            
            return jsonify({
                "monitor_status": monitor_status,
                "latest_health": latest_health
            })
        
        elif request.method == "POST":
            # 監視を開始
            system_monitor.start_monitoring()
            return jsonify({"status": "success", "message": "システム監視を開始しました"})
        
        elif request.method == "DELETE":
            # 監視を停止
            system_monitor.stop_monitoring()
            return jsonify({"status": "success", "message": "システム監視を停止しました"})
            
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/system/health")
def get_system_health():
    """現在のシステムヘルス取得"""
    try:
        health_data = system_monitor.run_health_check()
        return jsonify(health_data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/system/health/history")
def get_health_history():
    """ヘルス履歴取得"""
    try:
        hours = int(request.args.get("hours", 24))
        history = system_monitor.get_health_history(hours)
        return jsonify({"history": history, "hours": hours})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/system/alerts")
def get_alert_history():
    """アラート履歴取得"""
    try:
        hours = int(request.args.get("hours", 24))
        alerts = system_monitor.get_alert_history(hours)
        return jsonify({"alerts": alerts, "hours": hours})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/system/config", methods=["GET", "PUT"])
def manage_monitor_config():
    """監視設定の管理"""
    try:
        if request.method == "GET":
            return jsonify(system_monitor.config)
        
        elif request.method == "PUT":
            data = request.get_json()
            
            # 設定を更新
            for key, value in data.items():
                if key in system_monitor.config:
                    system_monitor.config[key] = value
            
            if system_monitor.save_config():
                return jsonify({"status": "success", "message": "監視設定を更新しました"})
            else:
                return jsonify({"status": "error", "message": "設定の保存に失敗しました"})
                
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/backup", methods=["GET", "POST"])
def manage_backups():
    """バックアップ管理"""
    try:
        if request.method == "GET":
            # バックアップ一覧とシステム状況を取得
            backups = backup_system.list_backups()
            status = backup_system.get_backup_status()
            
            return jsonify({
                "backups": backups,
                "status": status
            })
        
        elif request.method == "POST":
            # 新しいバックアップを作成
            data = request.get_json() or {}
            backup_name = data.get("backup_name")
            include_logs = data.get("include_logs", True)
            
            backup_info = backup_system.create_backup(backup_name, include_logs)
            
            if backup_info["status"] == "completed":
                return jsonify({
                    "status": "success", 
                    "message": "バックアップを作成しました",
                    "backup_info": backup_info
                })
            else:
                return jsonify({
                    "status": "error", 
                    "message": f"バックアップ作成に失敗しました: {backup_info.get('error', 'Unknown error')}"
                })
                
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/backup/<backup_name>", methods=["DELETE"])
def delete_backup(backup_name):
    """特定のバックアップを削除"""
    try:
        success = backup_system.delete_backup(backup_name)
        
        if success:
            return jsonify({"status": "success", "message": "バックアップを削除しました"})
        else:
            return jsonify({"status": "error", "message": "バックアップの削除に失敗しました"})
            
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/backup/restore", methods=["POST"])
def restore_backup():
    """バックアップの復元"""
    try:
        data = request.get_json()
        backup_name = data.get("backup_name")
        target_files = data.get("target_files")  # ["critical", "config", "logs"]
        
        if not backup_name:
            return jsonify({"status": "error", "message": "backup_nameが必要です"})
        
        restore_info = backup_system.restore_backup(backup_name, target_files)
        
        if restore_info["status"] in ["completed", "completed_with_errors"]:
            return jsonify({
                "status": "success", 
                "message": "バックアップを復元しました",
                "restore_info": restore_info
            })
        else:
            return jsonify({
                "status": "error", 
                "message": f"復元に失敗しました: {restore_info.get('error', 'Unknown error')}"
            })
            
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/backup/auto", methods=["GET", "POST", "DELETE"])
def manage_auto_backup():
    """自動バックアップの管理"""
    try:
        if request.method == "GET":
            status = backup_system.get_backup_status()
            return jsonify(status)
        
        elif request.method == "POST":
            # 自動バックアップを開始
            success = backup_system.start_auto_backup()
            
            if success:
                return jsonify({"status": "success", "message": "自動バックアップを開始しました"})
            else:
                return jsonify({"status": "error", "message": "自動バックアップの開始に失敗しました"})
        
        elif request.method == "DELETE":
            # 自動バックアップを停止
            backup_system.stop_auto_backup()
            return jsonify({"status": "success", "message": "自動バックアップを停止しました"})
            
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/backup/config", methods=["GET", "PUT"])
def manage_backup_config():
    """バックアップ設定の管理"""
    try:
        if request.method == "GET":
            return jsonify(backup_system.config)
        
        elif request.method == "PUT":
            data = request.get_json()
            
            # 設定を更新
            for key, value in data.items():
                if key in backup_system.config:
                    backup_system.config[key] = value
            
            if backup_system.save_config():
                return jsonify({"status": "success", "message": "バックアップ設定を更新しました"})
            else:
                return jsonify({"status": "error", "message": "設定の保存に失敗しました"})
                
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/favorites", methods=["GET", "POST", "DELETE"])
def manage_favorites():
    """お気に入り干場の管理"""
    try:
        if request.method == "GET":
            # お気に入り一覧を取得
            sort_by = request.args.get("sort_by", "auto")
            favorites = favorites_manager.get_all_favorites(sort_by)
            summary = favorites_manager.get_favorites_summary()
            
            return jsonify({
                "favorites": favorites,
                "summary": summary
            })
        
        elif request.method == "POST":
            # お気に入りに追加
            data = request.get_json()
            spot_name = data.get("spot_name")
            spot_data = data.get("spot_data", {})
            
            if not spot_name:
                return jsonify({"status": "error", "message": "spot_nameが必要です"})
            
            result = favorites_manager.add_favorite(spot_name, spot_data)
            return jsonify(result)
        
        elif request.method == "DELETE":
            # お気に入りから削除
            data = request.get_json()
            spot_name = data.get("spot_name")
            
            if not spot_name:
                return jsonify({"status": "error", "message": "spot_nameが必要です"})
            
            result = favorites_manager.remove_favorite(spot_name)
            return jsonify(result)
            
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/favorites/quick")
def get_quick_access_favorites():
    """クイックアクセス用お気に入りを取得"""
    try:
        quick_favorites = favorites_manager.get_quick_access_favorites()
        return jsonify({
            "quick_favorites": quick_favorites,
            "count": len(quick_favorites),
            "max_count": favorites_manager.settings["quick_access_count"]
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/favorites/search")
def search_favorites():
    """お気に入りを検索"""
    try:
        query = request.args.get("q", "")
        if not query:
            return jsonify({"results": [], "message": "検索クエリが必要です"})
        
        results = favorites_manager.search_favorites(query)
        return jsonify({
            "results": results,
            "query": query,
            "count": len(results)
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/favorites/<spot_name>/access", methods=["POST"])
def update_favorite_access(spot_name):
    """お気に入りアクセス情報を更新"""
    try:
        success = favorites_manager.update_access(spot_name)
        
        if success:
            return jsonify({"status": "success", "message": "アクセス情報を更新しました"})
        else:
            return jsonify({"status": "error", "message": "お気に入りに登録されていません"})
            
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/favorites/<spot_name>/note", methods=["PUT"])
def update_favorite_note(spot_name):
    """お気に入りのカスタムメモを更新"""
    try:
        data = request.get_json()
        note = data.get("note", "")
        
        success = favorites_manager.update_custom_note(spot_name, note)
        
        if success:
            return jsonify({"status": "success", "message": "メモを更新しました"})
        else:
            return jsonify({"status": "error", "message": "お気に入りに登録されていません"})
            
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/favorites/<spot_name>/color", methods=["PUT"])
def update_favorite_color(spot_name):
    """お気に入りの色タグを更新"""
    try:
        data = request.get_json()
        color_tag = data.get("color_tag", "default")
        
        success = favorites_manager.set_color_tag(spot_name, color_tag)
        
        if success:
            return jsonify({"status": "success", "message": "色タグを更新しました"})
        else:
            return jsonify({"status": "error", "message": "無効な色タグまたはお気に入りに登録されていません"})
            
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/favorites/<spot_name>/quick_access", methods=["PUT"])
def toggle_favorite_quick_access(spot_name):
    """クイックアクセスの切り替え"""
    try:
        result = favorites_manager.toggle_quick_access(spot_name)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/favorites/export", methods=["POST"])
def export_favorites():
    """お気に入りのエクスポート"""
    try:
        result = favorites_manager.export_favorites()
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/favorites/import", methods=["POST"])
def import_favorites():
    """お気に入りのインポート"""
    try:
        data = request.get_json()
        import_file = data.get("import_file")
        merge_mode = data.get("merge_mode", True)
        
        if not import_file:
            return jsonify({"status": "error", "message": "import_fileが必要です"})
        
        result = favorites_manager.import_favorites(import_file, merge_mode)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/favorites/cleanup", methods=["POST"])
def cleanup_favorites():
    """お気に入りのクリーンアップ"""
    try:
        result = favorites_manager.cleanup_favorites()
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/favorites/settings", methods=["GET", "PUT"])
def manage_favorites_settings():
    """お気に入り設定の管理"""
    try:
        if request.method == "GET":
            return jsonify(favorites_manager.settings)
        
        elif request.method == "PUT":
            data = request.get_json()
            
            # 設定を更新
            for key, value in data.items():
                if key in favorites_manager.settings:
                    favorites_manager.settings[key] = value
            
            if favorites_manager.save_settings():
                return jsonify({"status": "success", "message": "お気に入り設定を更新しました"})
            else:
                return jsonify({"status": "error", "message": "設定の保存に失敗しました"})
                
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/favorites/check/<spot_name>")
def check_favorite_status(spot_name):
    """お気に入り登録状況をチェック"""
    try:
        is_favorite = favorites_manager.is_favorite(spot_name)
        favorite_data = favorites_manager.get_favorite(spot_name) if is_favorite else None
        
        return jsonify({
            "is_favorite": is_favorite,
            "favorite_data": favorite_data
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/system_status")
def system_status():
    """システム状態の確認"""
    try:
        spot_count = len(pd.read_csv(CSV_FILE)) if os.path.exists(CSV_FILE) else 0
        record_count = len(pd.read_csv(RECORD_FILE)) if os.path.exists(RECORD_FILE) else 0
        
        # Check adaptive learning dataset
        adaptive_dataset_size = 0
        if os.path.exists("weather_labeled_dataset.csv"):
            adaptive_dataset_size = len(pd.read_csv("weather_labeled_dataset.csv"))
        
        # Check if adaptive model exists
        adaptive_model_exists = os.path.exists("adaptive_model.pkl")
        
        # Get fishing season status
        season_status = fishing_season.get_season_status()
        
        # Get notification system status
        notification_config = notification_system.get_config_summary()
        
        # Get system monitor status
        monitor_status = system_monitor.get_monitoring_status()
        
        # Get backup system status
        backup_status = backup_system.get_backup_status()
        
        return jsonify({
            "status": "operational",
            "spot_count": spot_count,
            "record_count": record_count,
            "adaptive_dataset_size": adaptive_dataset_size,
            "ml_model_loaded": ml_model is not None,
            "adaptive_model_exists": adaptive_model_exists,
            "specialized_forecast": "available",
            "fishing_season": season_status,
            "notification_system": {
                "running": notification_system.running,
                "subscriber_count": notification_config.get("subscriber_count", 0),
                "notification_times": notification_config.get("notification_times", {}),
                "delivery_methods": notification_config.get("delivery_methods", {})
            },
            "system_monitor": {
                "running": monitor_status["running"],
                "last_check": monitor_status["last_check"],
                "monitoring_interval": monitor_status["config"]["interval"],
                "endpoints_monitored": monitor_status["config"]["endpoints_count"],
                "files_monitored": monitor_status["config"]["files_count"]
            },
            "backup_system": {
                "auto_backup_running": backup_status["auto_backup_running"],
                "backup_count": backup_status["backup_count"],
                "total_size_mb": backup_status["total_size_mb"],
                "last_backup": backup_status["last_backup"]["created_at"] if backup_status["last_backup"] else None
            },
            "components": {
                "spot_management": "✓",
                "forecast_system": "✓", 
                "record_system": "✓",
                "ml_prediction": "✓" if ml_model else "✗",
                "specialized_analysis": "✓",
                "adaptive_learning": "✓",
                "data_quality_control": "✓",
                "fishing_season_management": "✓",
                "notification_system": "✓",
                "system_monitoring": "✓",
                "backup_system": "✓",
                "sea_fog_prediction": "✓" if sea_fog_engine else "✗"
            },
            "sea_fog_system": {
                "available": sea_fog_engine is not None,
                "historical_data_count": len(sea_fog_engine.historical_data) if sea_fog_engine else 0,
                "last_update": datetime.now().isoformat() if sea_fog_engine else None
            }
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/fishing_season/start_prompt", methods=["GET"])
def check_season_start_prompt():
    """漁期開始日設定プロンプトの必要性チェック"""
    try:
        prompt_needed = fishing_season.check_season_start_prompt_needed()
        if prompt_needed:
            prompt_data = fishing_season.get_season_start_prompt_data()
            return jsonify({
                "prompt_needed": True,
                "prompt_data": prompt_data
            })
        else:
            return jsonify({
                "prompt_needed": False,
                "message": "今年のプロンプトは不要または既に実施済みです"
            })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/fishing_season/start_date", methods=["GET", "POST"])
def manage_season_start_date():
    """漁期開始日の取得・設定"""
    try:
        if request.method == "GET":
            # 現在の開始日設定と選択データを取得
            prompt_data = fishing_season.get_season_start_prompt_data()
            notification_status = fishing_season.get_notification_status()
            
            return jsonify({
                "current_setting": fishing_season.config.get('season_start', '06-01'),
                "user_selected": fishing_season.config.get('season_start_setting', {}).get('user_selected_start'),
                "prompt_data": prompt_data,
                "notification_status": notification_status,
                "prompt_needed": fishing_season.check_season_start_prompt_needed()
            })
        
        elif request.method == "POST":
            # ユーザーが選択した開始日を設定
            data = request.get_json()
            selected_date = data.get("selected_date")
            
            if not selected_date:
                return jsonify({"status": "error", "message": "selected_dateが必要です"})
            
            result = fishing_season.set_user_selected_season_start(selected_date)
            
            # 通知システムにも状況変更を通知
            if result.get("status") == "success":
                notification_summary = notification_system.get_config_summary()
                result["notification_status"] = notification_summary.get("fishing_season_integration", {})
            
            return jsonify(result)
            
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/fishing_season/notifications", methods=["GET", "POST"])
def manage_season_notifications():
    """漁期通知の管理"""
    try:
        if request.method == "GET":
            # 通知状況の取得
            notification_status = fishing_season.get_notification_status()
            should_send = fishing_season.should_send_notifications()
            
            return jsonify({
                "notification_status": notification_status,
                "should_send_notifications": should_send,
                "current_season_status": fishing_season.get_season_status()
            })
        
        elif request.method == "POST":
            # 通知一時停止の設定
            data = request.get_json()
            action = data.get("action")  # "suspend" or "resume"
            
            if action == "suspend":
                result = fishing_season.suspend_notifications_until_season()
            elif action == "resume":
                # 通知再開（一時停止フラグを解除）
                if 'season_start_setting' not in fishing_season.config:
                    fishing_season.config['season_start_setting'] = {}
                fishing_season.config['season_start_setting']['notification_suspended'] = False
                fishing_season.save_config()
                result = {
                    "status": "success",
                    "message": "通知を再開しました"
                }
            else:
                return jsonify({"status": "error", "message": "actionは'suspend'または'resume'である必要があります"})
            
            return jsonify(result)
            
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/fishing_season/reset_prompt", methods=["POST"])
def reset_season_start_prompt():
    """漁期開始プロンプトのリセット（テスト用）"""
    try:
        result = fishing_season.reset_season_start_prompt()
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/notifications/status", methods=["GET"])
def get_notification_status():
    """通知システムの詳細状況取得"""
    try:
        config_summary = notification_system.get_config_summary()
        return jsonify(config_summary)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/sea_fog/predict", methods=["GET", "POST"])
def predict_sea_fog():
    """海霧予測API"""
    try:
        if not sea_fog_engine:
            return jsonify({"error": "海霧予測エンジンが利用できません"}), 503
        
        if request.method == "GET":
            # クエリパラメータから取得
            lat = float(request.args.get("lat", 45.178))
            lon = float(request.args.get("lon", 141.228))
            date = request.args.get("date", datetime.now().strftime("%Y-%m-%d"))
            hours = int(request.args.get("hours", 24))
        else:
            # POSTデータから取得
            data = request.get_json()
            lat = data.get("lat", 45.178)
            lon = data.get("lon", 141.228)
            date = data.get("date", datetime.now().strftime("%Y-%m-%d"))
            hours = data.get("hours", 24)
        
        # 海霧予測実行
        prediction = sea_fog_engine.predict_sea_fog(lat, lon, date, hours)
        
        return jsonify(prediction)
    
    except ValueError as e:
        return jsonify({"error": f"パラメータエラー: {str(e)}"}), 400
    except Exception as e:
        return jsonify({"error": f"予測エラー: {str(e)}"}), 500

@app.route("/sea_fog/observation", methods=["POST"])
def add_sea_fog_observation():
    """海霧観測データの追加"""
    try:
        if not sea_fog_engine:
            return jsonify({"error": "海霧予測エンジンが利用できません"}), 503
        
        data = request.get_json()
        lat = data.get("lat")
        lon = data.get("lon")
        datetime_str = data.get("datetime")
        fog_observed = data.get("fog_observed", False)
        conditions = data.get("conditions", {})
        
        if not all([lat, lon, datetime_str]):
            return jsonify({"error": "lat, lon, datetimeは必須です"}), 400
        
        success = sea_fog_engine.add_observation(lat, lon, datetime_str, fog_observed, conditions)
        
        if success:
            return jsonify({"status": "success", "message": "観測データを追加しました"})
        else:
            return jsonify({"status": "error", "message": "観測データの追加に失敗しました"}), 500
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/sea_fog/statistics", methods=["GET"])
def get_sea_fog_statistics():
    """海霧統計データの取得"""
    try:
        if not sea_fog_engine:
            return jsonify({"error": "海霧予測エンジンが利用できません"}), 503
        
        days_back = int(request.args.get("days", 30))
        statistics = sea_fog_engine.get_fog_statistics(days_back)
        
        return jsonify(statistics)
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/sea_fog/config", methods=["GET", "PUT"])
def manage_sea_fog_config():
    """海霧予測設定の管理"""
    try:
        if not sea_fog_engine:
            return jsonify({"error": "海霧予測エンジンが利用できません"}), 503
        
        if request.method == "GET":
            return jsonify(sea_fog_engine.config)
        
        elif request.method == "PUT":
            data = request.get_json()
            
            # 設定の更新
            for key, value in data.items():
                if key in sea_fog_engine.config:
                    sea_fog_engine.config[key] = value
            
            sea_fog_engine.save_config()
            return jsonify({"status": "success", "message": "設定を更新しました"})
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/sea_fog/spots", methods=["GET"])
def get_sea_fog_for_spots():
    """全干場の海霧予測"""
    try:
        if not sea_fog_engine:
            return jsonify({"error": "海霧予測エンジンが利用できません"}), 503
        
        # 干場データ読み込み
        df = pd.read_csv(CSV_FILE)
        date = request.args.get("date", datetime.now().strftime("%Y-%m-%d"))
        hours = int(request.args.get("hours", 12))
        
        results = []
        
        for _, spot in df.iterrows():
            try:
                prediction = sea_fog_engine.predict_sea_fog(
                    spot["lat"], spot["lon"], date, hours
                )
                
                if "error" not in prediction:
                    spot_result = {
                        "spot_name": spot["name"],
                        "lat": spot["lat"],
                        "lon": spot["lon"],
                        "fog_summary": prediction["summary"],
                        "max_risk_time": prediction["summary"]["overall_risk"]["peak_risk_time"],
                        "work_hours_recommendation": prediction["summary"]["work_hours_risk"]["recommendation"]
                    }
                    results.append(spot_result)
                    
            except Exception as e:
                print(f"Error predicting fog for {spot['name']}: {e}")
                continue
        
        return jsonify({
            "prediction_date": date,
            "total_spots": len(df),
            "successful_predictions": len(results),
            "spot_predictions": results
        })
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/sea_fog/charts/timeline", methods=["POST"])
def generate_fog_timeline_chart():
    """海霧確率時系列チャートの生成"""
    try:
        if not sea_fog_viz:
            return jsonify({"error": "可視化システムが利用できません"}), 503
        
        data = request.get_json()
        prediction_data = data.get("prediction_data")
        
        if not prediction_data:
            return jsonify({"error": "prediction_dataが必要です"}), 400
        
        result = sea_fog_viz.generate_probability_timeline_chart(prediction_data)
        return jsonify(result)
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/sea_fog/charts/heatmap", methods=["POST"])
def generate_fog_heatmap():
    """海霧リスクヒートマップの生成"""
    try:
        if not sea_fog_viz:
            return jsonify({"error": "可視化システムが利用できません"}), 503
        
        data = request.get_json()
        spot_predictions = data.get("spot_predictions")
        
        if not spot_predictions:
            return jsonify({"error": "spot_predictionsが必要です"}), 400
        
        result = sea_fog_viz.generate_risk_heatmap(spot_predictions)
        return jsonify(result)
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/sea_fog/charts/factors", methods=["POST"])
def generate_fog_factors_chart():
    """海霧要因分析チャートの生成"""
    try:
        if not sea_fog_viz:
            return jsonify({"error": "可視化システムが利用できません"}), 503
        
        data = request.get_json()
        prediction_data = data.get("prediction_data")
        
        if not prediction_data:
            return jsonify({"error": "prediction_dataが必要です"}), 400
        
        result = sea_fog_viz.generate_factors_chart(prediction_data)
        return jsonify(result)
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/sea_fog/charts/comparison", methods=["POST"])
def generate_fog_comparison_chart():
    """複数地点海霧比較チャートの生成"""
    try:
        if not sea_fog_viz:
            return jsonify({"error": "可視化システムが利用できません"}), 503
        
        data = request.get_json()
        predictions_list = data.get("predictions_list")
        labels = data.get("labels")
        
        if not predictions_list or not labels:
            return jsonify({"error": "predictions_listとlabelsが必要です"}), 400
        
        result = sea_fog_viz.generate_comparison_chart(predictions_list, labels)
        return jsonify(result)
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/sea_fog/dashboard", methods=["GET", "POST"])
def get_fog_dashboard_data():
    """海霧予測ダッシュボード用データの取得"""
    try:
        if not sea_fog_engine or not sea_fog_viz:
            return jsonify({"error": "海霧予測・可視化システムが利用できません"}), 503
        
        if request.method == "GET":
            # デフォルトパラメータで利尻島全体の予測
            lat = float(request.args.get("lat", 45.178))
            lon = float(request.args.get("lon", 141.228))
            date = request.args.get("date", datetime.now().strftime("%Y-%m-%d"))
            hours = int(request.args.get("hours", 24))
        else:
            # POSTデータから取得
            data = request.get_json()
            lat = data.get("lat", 45.178)
            lon = data.get("lon", 141.228)
            date = data.get("date", datetime.now().strftime("%Y-%m-%d"))
            hours = data.get("hours", 24)
        
        # 海霧予測実行
        prediction = sea_fog_engine.predict_sea_fog(lat, lon, date, hours)
        
        if "error" in prediction:
            return jsonify(prediction), 500
        
        # ダッシュボードデータ生成
        dashboard_data = sea_fog_viz.generate_web_dashboard_data(prediction)
        
        return jsonify(dashboard_data)
    
    except ValueError as e:
        return jsonify({"error": f"パラメータエラー: {str(e)}"}), 400
    except Exception as e:
        return jsonify({"error": f"ダッシュボードエラー: {str(e)}"}), 500

@app.route("/sea_fog/charts/export", methods=["POST"])
def export_fog_chart_data():
    """海霧チャートデータのエクスポート"""
    try:
        if not sea_fog_viz:
            return jsonify({"error": "可視化システムが利用できません"}), 503
        
        data = request.get_json()
        chart_data = data.get("chart_data")
        format_type = data.get("format", "json")
        
        if not chart_data:
            return jsonify({"error": "chart_dataが必要です"}), 400
        
        result = sea_fog_viz.export_chart_data(chart_data, format_type)
        return jsonify(result)
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/sea_fog/charts/cleanup", methods=["POST"])
def cleanup_fog_charts():
    """古い海霧チャートのクリーンアップ"""
    try:
        if not sea_fog_viz:
            return jsonify({"error": "可視化システムが利用できません"}), 503
        
        data = request.get_json() or {}
        days_to_keep = data.get("days_to_keep", 7)
        
        result = sea_fog_viz.cleanup_old_charts(days_to_keep)
        return jsonify(result)
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/sea_fog/charts/<path:filename>")
def serve_fog_chart(filename):
    """生成された海霧チャートの配信"""
    try:
        if not sea_fog_viz:
            return jsonify({"error": "可視化システムが利用できません"}), 503
        
        charts_dir = sea_fog_viz.charts_dir
        return send_file(os.path.join(charts_dir, filename))
    
    except FileNotFoundError:
        return jsonify({"error": "チャートファイルが見つかりません"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# === 海霧アラートシステム API ===

@app.route("/sea_fog/alerts/status", methods=["GET"])
def get_alert_system_status():
    """アラートシステムの状態取得"""
    try:
        if not sea_fog_alerts:
            return jsonify({"error": "アラートシステムが利用できません"}), 503
        
        status = sea_fog_alerts.get_status()
        return jsonify(status)
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/sea_fog/alerts/monitoring", methods=["GET", "POST", "DELETE"])
def manage_alert_monitoring():
    """アラート監視の管理"""
    try:
        if not sea_fog_alerts:
            return jsonify({"error": "アラートシステムが利用できません"}), 503
        
        if request.method == "GET":
            # 監視状態の取得
            status = sea_fog_alerts.get_status()
            return jsonify({
                "monitoring_active": status["monitoring_active"],
                "last_check": status["last_check"],
                "check_interval": status["check_interval"]
            })
        
        elif request.method == "POST":
            # 監視開始
            result = sea_fog_alerts.start_monitoring()
            return jsonify(result)
        
        elif request.method == "DELETE":
            # 監視停止
            result = sea_fog_alerts.stop_monitoring()
            return jsonify(result)
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/sea_fog/alerts/check", methods=["POST"])
def manual_alert_check():
    """手動アラートチェック"""
    try:
        if not sea_fog_alerts:
            return jsonify({"error": "アラートシステムが利用できません"}), 503
        
        result = sea_fog_alerts.run_periodic_check()
        return jsonify(result)
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/sea_fog/alerts/active", methods=["GET"])
def get_active_alerts():
    """アクティブアラートの取得"""
    try:
        if not sea_fog_alerts:
            return jsonify({"error": "アラートシステムが利用できません"}), 503
        
        active_alerts = sea_fog_alerts.get_active_alerts()
        return jsonify({
            "alerts": active_alerts,
            "count": len(active_alerts)
        })
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/sea_fog/alerts/history", methods=["GET"])
def get_sea_fog_alert_history():
    """アラート履歴の取得"""
    try:
        if not sea_fog_alerts:
            return jsonify({"error": "アラートシステムが利用できません"}), 503
        
        days = int(request.args.get("days", 7))
        history = sea_fog_alerts.get_alert_history(days)
        
        return jsonify({
            "alerts": history,
            "count": len(history),
            "period_days": days
        })
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/sea_fog/alerts/subscribers", methods=["GET", "POST", "DELETE"])
def manage_alert_subscribers():
    """アラート購読者の管理"""
    try:
        if not sea_fog_alerts:
            return jsonify({"error": "アラートシステムが利用できません"}), 503
        
        if request.method == "GET":
            # 購読者一覧の取得
            return jsonify({
                "subscribers": sea_fog_alerts.subscribers,
                "count": len(sea_fog_alerts.subscribers)
            })
        
        elif request.method == "POST":
            # 購読者の追加
            data = request.get_json()
            name = data.get("name")
            contact_info = data.get("contact_info", {})
            alert_preferences = data.get("alert_preferences")
            
            if not name:
                return jsonify({"error": "名前が必要です"}), 400
            
            subscriber_id = sea_fog_alerts.add_subscriber(name, contact_info, alert_preferences)
            return jsonify({
                "status": "success",
                "subscriber_id": subscriber_id,
                "message": "購読者を追加しました"
            })
        
        elif request.method == "DELETE":
            # 購読者の削除
            data = request.get_json()
            subscriber_id = data.get("subscriber_id")
            
            if not subscriber_id:
                return jsonify({"error": "購読者IDが必要です"}), 400
            
            sea_fog_alerts.remove_subscriber(subscriber_id)
            return jsonify({
                "status": "success",
                "message": "購読者を削除しました"
            })
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/sea_fog/alerts/config", methods=["GET", "PUT"])
def manage_alert_config():
    """アラート設定の管理"""
    try:
        if not sea_fog_alerts:
            return jsonify({"error": "アラートシステムが利用できません"}), 503
        
        if request.method == "GET":
            # 設定の取得
            return jsonify(sea_fog_alerts.config)
        
        elif request.method == "PUT":
            # 設定の更新
            data = request.get_json()
            
            # 既存設定のマージ
            if "alert_thresholds" in data:
                sea_fog_alerts.config["alert_thresholds"].update(data["alert_thresholds"])
            
            if "monitoring_schedule" in data:
                sea_fog_alerts.config["monitoring_schedule"].update(data["monitoring_schedule"])
            
            if "alert_conditions" in data:
                sea_fog_alerts.config["alert_conditions"].update(data["alert_conditions"])
            
            if "notification_channels" in data:
                sea_fog_alerts.config["notification_channels"].update(data["notification_channels"])
            
            sea_fog_alerts.save_config()
            
            # スケジュールの更新
            sea_fog_alerts.setup_alert_schedule()
            
            return jsonify({
                "status": "success",
                "message": "設定を更新しました",
                "config": sea_fog_alerts.config
            })
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/sea_fog/alerts/test", methods=["POST"])
def test_alert_system():
    """アラートシステムのテスト"""
    try:
        if not sea_fog_alerts:
            return jsonify({"error": "アラートシステムが利用できません"}), 503
        
        data = request.get_json() or {}
        zone_name = data.get("zone", "oshidomari")
        
        # テスト用の模擬アラート生成
        zone_info = sea_fog_alerts.config["alert_zones"].get(zone_name)
        if not zone_info:
            return jsonify({"error": "無効なゾーン名です"}), 400
        
        test_alert_info = {
            "level": "warning",
            "max_risk": 0.4,
            "max_risk_time": datetime.now().isoformat(),
            "work_hours_avg_risk": 0.3,
            "consecutive_hours": 0,
            "rapid_increase": False,
            "reasons": ["テストアラート"],
            "priority": zone_info["priority"]
        }
        
        test_prediction = {
            "hourly_predictions": [],
            "summary": {
                "overall_risk": {"maximum_probability": 0.4},
                "work_hours_risk": {"average_probability": 0.3, "recommendation": "要注意"}
            }
        }
        
        alert = sea_fog_alerts.generate_alert(zone_name, zone_info, test_alert_info, test_prediction)
        
        return jsonify({
            "status": "success",
            "message": "テストアラートを生成しました",
            "alert": alert
        })
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Personal Notification System API Endpoints
@app.route("/personal_notifications/users", methods=["GET", "POST"])
def manage_notification_users():
    """個人通知ユーザーの管理"""
    if not personal_notifications:
        return jsonify({"error": "個人通知システムが利用できません"}), 503
    
    try:
        if request.method == "GET":
            # ユーザー一覧を取得
            users = [
                {
                    "user_id": user["user_id"],
                    "name": user["name"],
                    "active": user.get("active", True),
                    "experience_level": user["work_profile"]["experience_level"],
                    "primary_locations": user["work_profile"]["primary_locations"],
                    "notification_channels": user["notification_preferences"]["notification_channels"],
                    "created_at": user["created_at"]
                }
                for user in personal_notifications.users
            ]
            
            return jsonify({
                "users": users,
                "total_users": len(users),
                "active_users": len([u for u in users if u["active"]])
            })
        
        elif request.method == "POST":
            # 新規ユーザー作成
            data = request.get_json()
            user_id = personal_notifications.create_user_profile(data)
            
            if user_id:
                return jsonify({
                    "status": "success",
                    "user_id": user_id,
                    "message": "ユーザープロファイルを作成しました"
                })
            else:
                return jsonify({"error": "ユーザー作成に失敗しました"}), 400
                
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/personal_notifications/users/<int:user_id>", methods=["GET", "PUT", "DELETE"])
def manage_specific_user(user_id):
    """特定ユーザーの管理"""
    if not personal_notifications:
        return jsonify({"error": "個人通知システムが利用できません"}), 503
    
    try:
        user = personal_notifications.get_user_by_id(user_id)
        if not user:
            return jsonify({"error": "ユーザーが見つかりません"}), 404
        
        if request.method == "GET":
            return jsonify(user)
        
        elif request.method == "PUT":
            # ユーザー情報更新
            updates = request.get_json()
            result = personal_notifications.update_user_profile(user_id, updates)
            return jsonify(result)
        
        elif request.method == "DELETE":
            # ユーザー削除（非アクティブ化）
            result = personal_notifications.update_user_profile(user_id, {"active": False})
            return jsonify(result)
            
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/personal_notifications/users/<int:user_id>/dashboard", methods=["GET"])
def get_user_notification_dashboard(user_id):
    """ユーザー通知ダッシュボード"""
    if not personal_notifications:
        return jsonify({"error": "個人通知システムが利用できません"}), 503
    
    try:
        dashboard = personal_notifications.get_user_notification_dashboard(user_id)
        return jsonify(dashboard)
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/personal_notifications/service", methods=["GET", "POST", "DELETE"])
def manage_notification_service():
    """個人通知サービスの管理"""
    if not personal_notifications:
        return jsonify({"error": "個人通知システムが利用できません"}), 503
    
    try:
        if request.method == "GET":
            # サービス状態取得
            status = personal_notifications.get_system_status()
            return jsonify(status)
        
        elif request.method == "POST":
            # サービス開始
            result = personal_notifications.start_notification_service()
            return jsonify(result)
        
        elif request.method == "DELETE":
            # サービス停止
            result = personal_notifications.stop_notification_service()
            return jsonify(result)
            
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/personal_notifications/send", methods=["POST"])
def send_personal_notification():
    """手動通知送信"""
    if not personal_notifications:
        return jsonify({"error": "個人通知システムが利用できません"}), 503
    
    try:
        data = request.get_json()
        user_id = data.get("user_id")
        notification_type = data.get("type", "manual")
        content = data.get("content", "")
        priority = data.get("priority", "normal")
        
        if not user_id or not content:
            return jsonify({"error": "user_idとcontentが必要です"}), 400
        
        user = personal_notifications.get_user_by_id(user_id)
        if not user:
            return jsonify({"error": "ユーザーが見つかりません"}), 404
        
        notification = {
            "user_id": user_id,
            "type": notification_type,
            "priority": priority,
            "channels": user["notification_preferences"]["notification_channels"],
            "content": content,
            "created_at": datetime.datetime.now().isoformat()
        }
        
        personal_notifications.queue_notification(notification)
        personal_notifications.process_notification_queue()
        
        return jsonify({
            "status": "success",
            "message": "通知を送信しました"
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/personal_notifications/config", methods=["GET", "PUT"])
def manage_personal_notification_config():
    """個人通知システム設定の管理"""
    if not personal_notifications:
        return jsonify({"error": "個人通知システムが利用できません"}), 503
    
    try:
        if request.method == "GET":
            return jsonify({
                "config": personal_notifications.config,
                "notification_channels": personal_notifications.config["notification_channels"],
                "timing_settings": personal_notifications.config["notification_timing"],
                "personalization_factors": personal_notifications.config["personalization_factors"]
            })
        
        elif request.method == "PUT":
            # 設定更新
            updates = request.get_json()
            
            def deep_update(base_dict, update_dict):
                for key, value in update_dict.items():
                    if isinstance(value, dict) and key in base_dict and isinstance(base_dict[key], dict):
                        deep_update(base_dict[key], value)
                    else:
                        base_dict[key] = value
            
            deep_update(personal_notifications.config, updates)
            personal_notifications.save_config()
            
            # スケジュールの再設定
            personal_notifications.setup_notification_schedule()
            
            return jsonify({
                "status": "success",
                "message": "設定を更新しました"
            })
            
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/personal_notifications/test", methods=["POST"])
def test_personal_notifications():
    """個人通知システムのテスト"""
    if not personal_notifications:
        return jsonify({"error": "個人通知システムが利用できません"}), 503
    
    try:
        data = request.get_json() or {}
        test_type = data.get("test_type", "basic")
        
        if test_type == "basic":
            # 基本テスト
            status = personal_notifications.get_system_status()
            return jsonify({
                "test_result": "success",
                "system_status": status,
                "message": "個人通知システムは正常に動作しています"
            })
        
        elif test_type == "notification_send":
            # 通知送信テスト
            if not personal_notifications.users:
                return jsonify({
                    "test_result": "skipped",
                    "message": "テスト用ユーザーが存在しません"
                })
            
            test_user = personal_notifications.users[0]
            test_notification = {
                "user_id": test_user["user_id"],
                "type": "test",
                "priority": "normal",
                "channels": ["console"],
                "content": f"個人通知システムテスト - {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                "created_at": datetime.datetime.now().isoformat()
            }
            
            personal_notifications.queue_notification(test_notification)
            personal_notifications.process_notification_queue()
            
            return jsonify({
                "test_result": "success",
                "message": f"テスト通知を {test_user['name']} に送信しました"
            })
        
        elif test_type == "user_creation":
            # ユーザー作成テスト
            test_user_data = {
                "name": f"Test User {datetime.datetime.now().strftime('%m%d_%H%M')}",
                "email": "test@example.com",
                "experience_level": "intermediate",
                "primary_locations": ["oshidomari"],
                "verbosity": "standard",
                "channels": ["console"]
            }
            
            user_id = personal_notifications.create_user_profile(test_user_data)
            
            if user_id:
                return jsonify({
                    "test_result": "success",
                    "user_id": user_id,
                    "message": "テストユーザーを作成しました"
                })
            else:
                return jsonify({
                    "test_result": "failed",
                    "message": "テストユーザーの作成に失敗しました"
                })
        
        else:
            return jsonify({"error": "不明なテストタイプです"}), 400
            
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Data Visualization System API Endpoints
@app.route("/visualization/dashboard", methods=["GET"])
def get_integrated_dashboard():
    """統合ダッシュボードデータの取得"""
    if not data_visualization:
        return jsonify({"error": "データ可視化システムが利用できません"}), 503
    
    try:
        dashboard_data = data_visualization.generate_integrated_dashboard()
        return jsonify(dashboard_data)
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/visualization/historical", methods=["GET"])
def get_historical_analysis():
    """履歴データ分析の取得"""
    if not data_visualization:
        return jsonify({"error": "データ可視化システムが利用できません"}), 503
    
    try:
        days_back = request.args.get("days", 30, type=int)
        analysis = data_visualization.generate_historical_analysis(days_back)
        return jsonify(analysis)
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/visualization/accuracy", methods=["GET"])
def get_prediction_accuracy():
    """予測精度レポートの取得"""
    if not data_visualization:
        return jsonify({"error": "データ可視化システムが利用できません"}), 503
    
    try:
        accuracy_report = data_visualization.generate_prediction_accuracy_report()
        return jsonify(accuracy_report)
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/visualization/export", methods=["POST"])
def export_visualization_data():
    """可視化データのエクスポート"""
    if not data_visualization:
        return jsonify({"error": "データ可視化システムが利用できません"}), 503
    
    try:
        data = request.get_json() or {}
        format_type = data.get("format", "json")
        
        export_result = data_visualization.export_dashboard_data(format_type)
        return jsonify(export_result)
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/visualization/status", methods=["GET"])
def get_visualization_status():
    """データ可視化システムの状態取得"""
    if not data_visualization:
        return jsonify({"error": "データ可視化システムが利用できません"}), 503
    
    try:
        status = data_visualization.get_visualization_status()
        return jsonify(status)
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/visualization/weather_patterns", methods=["GET"])
def get_weather_patterns():
    """天気パターン分析の取得"""
    if not data_visualization:
        return jsonify({"error": "データ可視化システムが利用できません"}), 503
    
    try:
        days_back = request.args.get("days", 30, type=int)
        patterns = data_visualization.analyze_weather_patterns(days_back)
        return jsonify({
            "analysis_period": days_back,
            "weather_patterns": patterns
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/visualization/sea_fog_trends", methods=["GET"])
def get_sea_fog_trends():
    """海霧傾向分析の取得"""
    if not data_visualization:
        return jsonify({"error": "データ可視化システムが利用できません"}), 503
    
    try:
        days_back = request.args.get("days", 30, type=int)
        trends = data_visualization.analyze_sea_fog_trends(days_back)
        return jsonify({
            "analysis_period": days_back,
            "sea_fog_trends": trends
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/visualization/user_behavior", methods=["GET"])
def get_user_behavior():
    """ユーザー行動分析の取得"""
    if not data_visualization:
        return jsonify({"error": "データ可視化システムが利用できません"}), 503
    
    try:
        days_back = request.args.get("days", 30, type=int)
        behavior = data_visualization.analyze_user_behavior(days_back)
        return jsonify({
            "analysis_period": days_back,
            "user_behavior": behavior
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/visualization/system_performance", methods=["GET"])
def get_system_performance():
    """システムパフォーマンス分析の取得"""
    if not data_visualization:
        return jsonify({"error": "データ可視化システムが利用できません"}), 503
    
    try:
        days_back = request.args.get("days", 30, type=int)
        performance = data_visualization.analyze_system_performance(days_back)
        return jsonify({
            "analysis_period": days_back,
            "system_performance": performance
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/visualization/clear_cache", methods=["POST"])
def clear_visualization_cache():
    """可視化キャッシュのクリア"""
    if not data_visualization:
        return jsonify({"error": "データ可視化システムが利用できません"}), 503
    
    try:
        cache_size_before = len(data_visualization.data_cache)
        data_visualization.data_cache.clear()
        data_visualization.cache_timestamps.clear()
        
        return jsonify({
            "status": "success",
            "message": f"キャッシュをクリアしました",
            "cache_items_cleared": cache_size_before
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    print("Starting Rishiri Kelp Drying Forecast System...")
    print(f"Location: Rishiri Island (45.178N, 141.229E)")
    print(f"Main Ports: Oshidomari, Senposhi")
    
    # 漁期状況表示
    try:
        season_status = fishing_season.get_season_status()
        print(f"Fishing Season: {season_status['status']}")
        if season_status['status'] == 'in_season':
            print(f"   Progress: {season_status['progress']}% ({season_status['days_remaining']} days remaining)")
        elif season_status['status'] == 'pre_season':
            print(f"   Starts in: {season_status['days_until_start']} days")
        elif season_status['status'] == 'post_season':
            print(f"   Next season in: {season_status['days_until_next']} days")
    except UnicodeEncodeError:
        print("Fishing Season: Status available via API")
    
    print(f"ML Model: {'Loaded' if ml_model else 'Not available'}")
    print(f"Specialized Forecast: Available")
    print(f"Adaptive Learning: Available")
    print(f"Data Quality Control: Available")
    print(f"Season Management: Available")
    print(f"Notification System: Available")
    print(f"System Monitoring: Available")
    print(f"Backup System: Available")
    print(f"Sea Fog Prediction: {'Available' if sea_fog_engine else 'Not available'}")
    print(f"Personal Notifications: {'Available' if personal_notifications else 'Not available'}")
    print(f"Data Visualization: {'Available' if data_visualization else 'Not available'}")
    print(f"Map Interface: hoshiba_map_complete.html")
    print(f"Dashboard Interface: dashboard.html")
    print(f"Access: http://localhost:8000")
    print(f"Dashboard: http://localhost:8000/dashboard")
    print(f"API Endpoints:")
    print(f"   - /fishing_season/status (GET): Fishing season status")
    print(f"   - /fishing_season/schedule (GET): Work schedule")
    print(f"   - /fishing_season/rest_days (GET/POST/DELETE): Rest days management")
    print(f"   - /fishing_season/config (GET/PUT): Season configuration")
    print(f"   - /fishing_season/start_prompt (GET): Check if season start prompt needed")
    print(f"   - /fishing_season/start_date (GET/POST): Season start date management")
    print(f"   - /fishing_season/notifications (GET/POST): Season notification management")
    print(f"   - /fishing_season/reset_prompt (POST): Reset season start prompt (test)")
    print(f"   - /notifications/status (GET): Detailed notification status")
    print(f"   - /notifications/config (GET/PUT): Notification settings")
    print(f"   - /sea_fog/predict (GET/POST): Sea fog prediction")
    print(f"   - /sea_fog/observation (POST): Add fog observation data")
    print(f"   - /sea_fog/statistics (GET): Fog occurrence statistics")
    print(f"   - /sea_fog/config (GET/PUT): Fog prediction configuration")
    print(f"   - /sea_fog/spots (GET): Fog prediction for all spots")
    print(f"   - /sea_fog/dashboard (GET/POST): Dashboard data for fog prediction")
    print(f"   - /sea_fog/charts/timeline (POST): Generate timeline chart")
    print(f"   - /sea_fog/charts/heatmap (POST): Generate risk heatmap")
    print(f"   - /sea_fog/charts/factors (POST): Generate factors analysis chart")
    print(f"   - /sea_fog/charts/comparison (POST): Generate comparison chart")
    print(f"   - /sea_fog/charts/export (POST): Export chart data")
    print(f"   - /sea_fog/charts/cleanup (POST): Cleanup old charts")
    print(f"   - /sea_fog/charts/<filename> (GET): Serve generated charts")
    print(f"   - /notifications/subscribers (GET/POST/DELETE): Subscriber management")
    print(f"   - /notifications/send (POST): Manual notification")
    print(f"   - /notifications/test (POST): Test notification")
    print(f"   - /notifications/scheduler (GET/POST/DELETE): Scheduler control")
    print(f"   - /system/monitor (GET/POST/DELETE): System monitoring control")
    print(f"   - /system/health (GET): Current system health")
    print(f"   - /system/health/history (GET): Health history")
    print(f"   - /system/alerts (GET): Alert history")
    print(f"   - /system/config (GET/PUT): Monitor configuration")
    print(f"   - /backup (GET/POST): Backup management")
    print(f"   - /backup/<name> (DELETE): Delete specific backup")
    print(f"   - /backup/restore (POST): Restore from backup")
    print(f"   - /backup/auto (GET/POST/DELETE): Auto backup control")
    print(f"   - /backup/config (GET/PUT): Backup configuration")
    print(f"   - /adaptive_learning/process (POST): Manual adaptive learning")
    print(f"   - /adaptive_learning/quality (GET): Data quality report")
    print(f"   - /adaptive_learning/retrain (POST): Manual model retraining")
    print(f"   - /system_status (GET): System status")
    print(f"   - /check_spot_records (GET): Check if spot has records")
    print(f"   - /personal_notifications/* (GET/POST/PUT/DELETE): Personal notification management")
    print(f"   - /personal_notifications/users (GET/POST): User profile management")
    print(f"   - /personal_notifications/users/<id> (GET/PUT/DELETE): Specific user management")
    print(f"   - /personal_notifications/users/<id>/dashboard (GET): User notification dashboard")
    print(f"   - /personal_notifications/service (GET/POST/DELETE): Notification service control")
    print(f"   - /personal_notifications/send (POST): Manual notification sending")
    print(f"   - /personal_notifications/config (GET/PUT): System configuration")
    print(f"   - /personal_notifications/test (POST): System testing")
    print(f"   - /visualization/dashboard (GET): Integrated dashboard data")
    print(f"   - /visualization/historical (GET): Historical data analysis")
    print(f"   - /visualization/accuracy (GET): Prediction accuracy report")
    print(f"   - /visualization/weather_patterns (GET): Weather pattern analysis")
    print(f"   - /visualization/sea_fog_trends (GET): Sea fog trend analysis")
    print(f"   - /visualization/user_behavior (GET): User behavior analysis")
    print(f"   - /visualization/system_performance (GET): System performance analysis")
    print(f"   - /visualization/export (POST): Export visualization data")
    print(f"   - /visualization/status (GET): Visualization system status")
    print(f"   - /visualization/clear_cache (POST): Clear visualization cache")
    
    app.run(host="0.0.0.0", port=8000, debug=True)