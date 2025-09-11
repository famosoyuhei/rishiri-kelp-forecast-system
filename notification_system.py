import json
import os
import threading
import schedule
import time
from datetime import datetime, timedelta
import requests
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import logging

# 漁期管理システムとの連携
try:
    from fishing_season_manager import FishingSeasonManager
except ImportError:
    FishingSeasonManager = None

class NotificationSystem:
    """利尻島昆布漁師向け自動通知システム（柔軟な時刻設定対応）"""
    
    def __init__(self):
        self.config_file = "notification_config.json"
        self.subscribers_file = "notification_subscribers.json"
        self.log_file = "notification_log.json"
        
        # デフォルト設定（漁師のフィードバックに基づいて変更可能）
        self.default_config = {
            "notification_times": {
                "daily_forecast": "16:00",     # 翌日予報通知（変更可能）
                "morning_alert": "05:00",      # 朝の気象アラート
                "evening_summary": "18:00"     # 夕方の作業結果確認
            },
            "notification_types": {
                "daily_forecast": {
                    "enabled": True,
                    "title": "🌊 明日の昆布干し予報",
                    "description": "翌日の気象条件と作業可否をお知らせ"
                },
                "weather_alert": {
                    "enabled": True,
                    "title": "⚠️ 気象警報",
                    "description": "強風・降雨などの危険条件をお知らせ"
                },
                "season_reminder": {
                    "enabled": True,
                    "title": "📅 漁期お知らせ",
                    "description": "漁期開始・終了の重要なお知らせ"
                }
            },
            "weather_thresholds": {
                "wind_warning": 15.0,          # 風速警報レベル
                "rain_warning": 10.0,          # 降水量警報レベル
                "temperature_low": 5.0,        # 低温注意レベル
                "humidity_high": 90.0          # 高湿度注意レベル
            },
            "delivery_methods": {
                "console": True,               # コンソール出力
                "file": True,                  # ファイル出力
                "email": False,                # メール送信（設定次第）
                "webhook": False               # Webhook送信（設定次第）
            },
            "email_settings": {
                "smtp_server": "smtp.gmail.com",
                "smtp_port": 587,
                "sender_email": "",
                "sender_password": "",
                "use_tls": True
            },
            "webhook_settings": {
                "url": "",
                "headers": {},
                "timeout": 10
            }
        }
        
        self.load_config()
        self.load_subscribers()
        self.setup_logging()
        self.running = False
        
    def load_config(self):
        """設定ファイルの読み込み（時刻変更に対応）"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    loaded_config = json.load(f)
                
                # デフォルト設定をベースに、保存された設定で上書き
                self.config = self.default_config.copy()
                self._merge_config(self.config, loaded_config)
            else:
                self.config = self.default_config.copy()
                self.save_config()
        except Exception as e:
            print(f"Config load error: {e}")
            self.config = self.default_config.copy()
    
    def _merge_config(self, default, loaded):
        """設定の再帰的マージ"""
        for key, value in loaded.items():
            if key in default:
                if isinstance(value, dict) and isinstance(default[key], dict):
                    self._merge_config(default[key], value)
                else:
                    default[key] = value
    
    def save_config(self):
        """設定ファイルの保存"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"Config save error: {e}")
            return False
    
    def load_subscribers(self):
        """通知対象者リストの読み込み"""
        try:
            if os.path.exists(self.subscribers_file):
                with open(self.subscribers_file, 'r', encoding='utf-8') as f:
                    self.subscribers = json.load(f)
            else:
                self.subscribers = []
                self.save_subscribers()
        except Exception as e:
            print(f"Subscribers load error: {e}")
            self.subscribers = []
    
    def save_subscribers(self):
        """通知対象者リストの保存"""
        try:
            with open(self.subscribers_file, 'w', encoding='utf-8') as f:
                json.dump(self.subscribers, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"Subscribers save error: {e}")
            return False
    
    def setup_logging(self):
        """ログ設定"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('notification_system.log', encoding='utf-8'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
    
    def update_notification_time(self, notification_type, new_time):
        """通知時刻の変更（柔軟な時刻設定）"""
        try:
            # 時刻形式の検証
            datetime.strptime(new_time, "%H:%M")
            
            if notification_type in self.config["notification_times"]:
                old_time = self.config["notification_times"][notification_type]
                self.config["notification_times"][notification_type] = new_time
                self.save_config()
                
                # スケジュールの再設定
                self.setup_schedule()
                
                self.logger.info(f"通知時刻変更: {notification_type} {old_time} -> {new_time}")
                return True
            else:
                self.logger.error(f"Unknown notification type: {notification_type}")
                return False
                
        except ValueError:
            self.logger.error(f"Invalid time format: {new_time}. Use HH:MM format.")
            return False
        except Exception as e:
            self.logger.error(f"Time update error: {e}")
            return False
    
    def add_subscriber(self, name, email=None, phone=None, favorite_spots=None):
        """通知対象者の追加"""
        subscriber = {
            "id": len(self.subscribers) + 1,
            "name": name,
            "email": email,
            "phone": phone,
            "favorite_spots": favorite_spots or [],
            "notification_preferences": {
                "daily_forecast": True,
                "weather_alert": True,
                "season_reminder": True
            },
            "created_at": datetime.now().isoformat(),
            "active": True
        }
        
        self.subscribers.append(subscriber)
        self.save_subscribers()
        self.logger.info(f"Subscriber added: {name}")
        return subscriber["id"]
    
    def remove_subscriber(self, subscriber_id):
        """通知対象者の削除"""
        self.subscribers = [s for s in self.subscribers if s["id"] != subscriber_id]
        self.save_subscribers()
        self.logger.info(f"Subscriber removed: {subscriber_id}")
    
    def get_weather_forecast(self, lat, lon):
        """気象予報データの取得"""
        try:
            tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
            
            # Open-Meteo APIから直接取得
            params = {
                "latitude": lat,
                "longitude": lon,
                "start_date": tomorrow,
                "end_date": (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d"),
                "hourly": "temperature_2m,relative_humidity_2m,precipitation_probability,precipitation,wind_speed_10m,wind_direction_10m,weather_code",
                "timezone": "Asia/Tokyo"
            }
            
            response = requests.get(
                "https://api.open-meteo.com/v1/forecast",
                params=params,
                timeout=10
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                self.logger.error(f"Weather API error: {response.status_code}")
                return None
                
        except Exception as e:
            self.logger.error(f"Weather fetch error: {e}")
            return None
    
    def create_daily_forecast_message(self, forecast_data, spot_name=None):
        """翌日予報メッセージの作成"""
        try:
            if not forecast_data or "result" not in forecast_data:
                return "明日の気象データを取得できませんでした。"
            
            result = forecast_data["result"]
            
            # 場所情報
            location = f"【{spot_name}】" if spot_name else "【利尻島】"
            
            # 昆布特化型予報
            konbu_forecast = result.get("konbu_specialized", {})
            recommendation = konbu_forecast.get("recommendation", "データなし")
            confidence = konbu_forecast.get("confidence", 0)
            
            # 詳細条件
            morning_wind = konbu_forecast.get("morning_wind", {})
            afternoon_radiation = konbu_forecast.get("afternoon_radiation", {})
            precipitation = konbu_forecast.get("precipitation", {})
            
            message = f"""🌊 {location} 明日の昆布干し予報

📊 総合判定: {recommendation}
🎯 信頼度: {confidence}%

🌬️ 朝の風条件 (4-10時):
   平均風速: {morning_wind.get('avg_speed', 0):.1f}m/s
   状態: {'✓ 適正' if morning_wind.get('optimal') else '⚠️ 要注意'}

☀️ 昼の日射条件 (10-16時):
   累積日射量: {afternoon_radiation.get('total', 0):.0f}Wh/m²
   状態: {'✓ 十分' if afternoon_radiation.get('sufficient') else '⚠️ 不足'}

🌧️ 降水リスク (4-16時):
   最大降水確率: {precipitation.get('max_probability', 0):.0f}%
   状態: {'✓ 安全' if precipitation.get('safe') else '⚠️ 注意'}

📝 推奨アクション:
"""
            
            # 理由とアドバイス
            reasons = konbu_forecast.get("reasons", [])
            warnings = konbu_forecast.get("warnings", [])
            
            if reasons:
                message += "\n✅ 有利な条件:\n"
                for reason in reasons:
                    message += f"   • {reason}\n"
            
            if warnings:
                message += "\n⚠️ 注意事項:\n"
                for warning in warnings:
                    message += f"   • {warning}\n"
            
            message += f"\n📅 作業スケジュール:\n"
            message += "   4:00-10:00  昆布引き上げ・展開\n"
            message += "   10:00-10:30 手直し作業\n"
            message += "   10:00-16:00 天日乾燥\n"
            message += "   14:00-16:00 回収作業\n"
            
            return message
            
        except Exception as e:
            self.logger.error(f"Message creation error: {e}")
            return "予報メッセージの作成に失敗しました。"
    
    def check_weather_alerts(self, forecast_data):
        """気象警報の確認"""
        alerts = []
        
        try:
            if not forecast_data or "hourly" not in forecast_data:
                return alerts
            
            hourly = forecast_data["hourly"]
            thresholds = self.config["weather_thresholds"]
            
            # 風速警報
            max_wind = max(hourly.get("wind_speed_10m", [0]))
            if max_wind > thresholds["wind_warning"]:
                alerts.append(f"⚠️ 強風警報: 最大風速 {max_wind:.1f}m/s")
            
            # 降水警報
            max_rain = max(hourly.get("precipitation", [0]))
            if max_rain > thresholds["rain_warning"]:
                alerts.append(f"⚠️ 降雨警報: 最大降水量 {max_rain:.1f}mm/h")
            
            # 低温注意
            min_temp = min(hourly.get("temperature_2m", [20]))
            if min_temp < thresholds["temperature_low"]:
                alerts.append(f"❄️ 低温注意: 最低気温 {min_temp:.1f}°C")
            
            # 高湿度注意
            max_humidity = max(hourly.get("relative_humidity_2m", [50]))
            if max_humidity > thresholds["humidity_high"]:
                alerts.append(f"💧 高湿度注意: 最大湿度 {max_humidity:.0f}%")
                
        except Exception as e:
            self.logger.error(f"Alert check error: {e}")
        
        return alerts
    
    def send_notification(self, message, title="通知", subscribers=None):
        """通知の送信"""
        if subscribers is None:
            subscribers = [s for s in self.subscribers if s["active"]]
        
        delivery_methods = self.config["delivery_methods"]
        sent_count = 0
        
        try:
            # コンソール出力
            if delivery_methods["console"]:
                print(f"\n=== {title} ===")
                print(message)
                print("=" * 50)
                sent_count += 1
            
            # ファイル出力
            if delivery_methods["file"]:
                self._save_notification_to_file(title, message)
                sent_count += 1
            
            # メール送信
            if delivery_methods["email"] and self._is_email_configured():
                for subscriber in subscribers:
                    if subscriber.get("email"):
                        if self._send_email(subscriber["email"], title, message):
                            sent_count += 1
            
            # Webhook送信
            if delivery_methods["webhook"] and self._is_webhook_configured():
                if self._send_webhook(title, message):
                    sent_count += 1
            
            self.logger.info(f"Notification sent: {title} (methods: {sent_count})")
            return True
            
        except Exception as e:
            self.logger.error(f"Notification send error: {e}")
            return False
    
    def _save_notification_to_file(self, title, message):
        """通知のファイル保存"""
        try:
            notification_record = {
                "timestamp": datetime.now().isoformat(),
                "title": title,
                "message": message
            }
            
            # ログファイルに追記
            if os.path.exists(self.log_file):
                with open(self.log_file, 'r', encoding='utf-8') as f:
                    logs = json.load(f)
            else:
                logs = []
            
            logs.append(notification_record)
            
            # 最新100件のみ保持
            if len(logs) > 100:
                logs = logs[-100:]
            
            with open(self.log_file, 'w', encoding='utf-8') as f:
                json.dump(logs, f, ensure_ascii=False, indent=2)
                
        except Exception as e:
            self.logger.error(f"File save error: {e}")
    
    def _is_email_configured(self):
        """メール設定の確認"""
        email_config = self.config["email_settings"]
        return (email_config["sender_email"] and 
                email_config["sender_password"] and 
                email_config["smtp_server"])
    
    def _send_email(self, recipient, subject, body):
        """メール送信"""
        try:
            email_config = self.config["email_settings"]
            
            msg = MIMEMultipart()
            msg['From'] = email_config["sender_email"]
            msg['To'] = recipient
            msg['Subject'] = subject
            
            msg.attach(MIMEText(body, 'plain', 'utf-8'))
            
            server = smtplib.SMTP(email_config["smtp_server"], email_config["smtp_port"])
            if email_config["use_tls"]:
                server.starttls()
            
            server.login(email_config["sender_email"], email_config["sender_password"])
            server.send_message(msg)
            server.quit()
            
            return True
            
        except Exception as e:
            self.logger.error(f"Email send error: {e}")
            return False
    
    def _is_webhook_configured(self):
        """Webhook設定の確認"""
        return bool(self.config["webhook_settings"]["url"])
    
    def _send_webhook(self, title, message):
        """Webhook送信"""
        try:
            webhook_config = self.config["webhook_settings"]
            
            payload = {
                "title": title,
                "message": message,
                "timestamp": datetime.now().isoformat(),
                "system": "利尻島昆布干場予報システム"
            }
            
            response = requests.post(
                webhook_config["url"],
                json=payload,
                headers=webhook_config.get("headers", {}),
                timeout=webhook_config.get("timeout", 10)
            )
            
            return response.status_code == 200
            
        except Exception as e:
            self.logger.error(f"Webhook send error: {e}")
            return False
    
    def daily_forecast_job(self):
        """翌日予報の定期送信ジョブ"""
        try:
            # 漁期管理システムとの連携チェック
            if FishingSeasonManager:
                fsm = FishingSeasonManager()
                
                # 通知送信許可チェック
                if not fsm.should_send_notifications():
                    self.logger.info("Notifications suspended until fishing season start")
                    return
                
                # 5月31日漁期開始プロンプトチェック
                if fsm.check_season_start_prompt_needed():
                    self._send_season_start_prompt(fsm)
                    return
            
            # 利尻島の代表座標で予報取得
            forecast_data = self.get_weather_forecast(45.178269, 141.228528)
            
            if forecast_data:
                message = self.create_daily_forecast_message(forecast_data, "利尻島全域")
                
                # 気象警報チェック
                alerts = self.check_weather_alerts(forecast_data)
                if alerts:
                    message += "\n\n🚨 気象警報:\n" + "\n".join(alerts)
                
                # 通知送信
                self.send_notification(
                    message, 
                    self.config["notification_types"]["daily_forecast"]["title"]
                )
            else:
                self.send_notification(
                    "明日の気象予報データを取得できませんでした。手動で確認してください。",
                    "⚠️ 予報取得エラー"
                )
                
        except Exception as e:
            self.logger.error(f"Daily forecast job error: {e}")
    
    def _send_season_start_prompt(self, fsm):
        """漁期開始日設定プロンプトの送信"""
        try:
            prompt_data = fsm.get_season_start_prompt_data()
            
            message = f"""📅 【重要】漁期開始日の設定

{prompt_data['current_year']}年の昆布漁期開始日を設定してください。

🎯 推奨日程：
"""
            
            for rec in prompt_data['recommended_dates']:
                date_obj = datetime.strptime(rec['date'], '%Y-%m-%d')
                message += f"• {date_obj.strftime('%m月%d日')} - {rec['reason']}\n"
            
            message += f"""
⚙️ 設定方法：
1. システム画面で「漁期管理」を選択
2. 開始日を選択（6月1日〜9月30日）
3. 設定完了まで通知は一時停止されます

💡 ヒント：
• 気象条件や準備状況を考慮して選択
• 後から変更も可能です
• 設定しない場合は6月1日が適用されます

このメッセージは年1回（5月31日）のみ表示されます。"""
            
            self.send_notification(
                message,
                "📅 漁期開始日設定のお知らせ"
            )
            
            self.logger.info("Season start prompt sent successfully")
            
        except Exception as e:
            self.logger.error(f"Season start prompt error: {e}")
    
    def setup_schedule(self):
        """スケジュールの設定"""
        # 既存のスケジュールをクリア
        schedule.clear()
        
        # 設定された時刻で各通知をスケジュール
        times = self.config["notification_times"]
        
        if self.config["notification_types"]["daily_forecast"]["enabled"]:
            schedule.every().day.at(times["daily_forecast"]).do(self.daily_forecast_job)
            self.logger.info(f"Daily forecast scheduled at {times['daily_forecast']}")
    
    def start_scheduler(self):
        """スケジューラーの開始"""
        self.setup_schedule()
        self.running = True
        
        def run_scheduler():
            while self.running:
                schedule.run_pending()
                time.sleep(60)  # 1分間隔でチェック
        
        scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
        scheduler_thread.start()
        
        self.logger.info("Notification scheduler started")
    
    def stop_scheduler(self):
        """スケジューラーの停止"""
        self.running = False
        self.logger.info("Notification scheduler stopped")
    
    def get_config_summary(self):
        """設定サマリーの取得"""
        summary = {
            "notification_times": self.config["notification_times"],
            "enabled_notifications": {
                k: v["enabled"] for k, v in self.config["notification_types"].items()
            },
            "delivery_methods": self.config["delivery_methods"],
            "subscriber_count": len([s for s in self.subscribers if s["active"]]),
            "weather_thresholds": self.config["weather_thresholds"]
        }
        
        # 漁期管理システムとの連携情報を追加
        if FishingSeasonManager:
            try:
                fsm = FishingSeasonManager()
                notification_status = fsm.get_notification_status()
                summary["fishing_season_integration"] = {
                    "connected": True,
                    "notification_status": notification_status,
                    "should_send_notifications": fsm.should_send_notifications(),
                    "prompt_needed": fsm.check_season_start_prompt_needed()
                }
            except Exception as e:
                summary["fishing_season_integration"] = {
                    "connected": False,
                    "error": str(e)
                }
        else:
            summary["fishing_season_integration"] = {
                "connected": False,
                "reason": "FishingSeasonManager not available"
            }
        
        return summary

if __name__ == "__main__":
    # テスト実行
    print("=== 通知システム テスト ===")
    
    notification_system = NotificationSystem()
    
    # 設定確認
    config = notification_system.get_config_summary()
    print(f"通知時刻設定: {config['notification_times']}")
    
    # 時刻変更テスト
    print("\n時刻変更テスト...")
    if notification_system.update_notification_time("daily_forecast", "15:30"):
        print("✓ 通知時刻を15:30に変更しました")
    
    # 通知テスト
    print("\n通知テスト...")
    test_message = """🌊 明日の昆布干し予報テスト

📊 総合判定: ◎ 干せる
🎯 信頼度: 85%

テストメッセージです。"""
    
    notification_system.send_notification(test_message, "🧪 システムテスト")
    
    print("\n=== テスト完了 ===")