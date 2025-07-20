import json
import os
from datetime import datetime, timedelta
import threading
import time
import schedule
from typing import Dict, List, Optional, Callable
try:
    import smtplib
    from email.mime.text import MimeText
    from email.mime.multipart import MimeMultipart
    EMAIL_AVAILABLE = True
except ImportError:
    EMAIL_AVAILABLE = False
    print("Warning: Email functionality not available")

try:
    from sea_fog_alert_system import SeaFogAlertSystem
except ImportError:
    SeaFogAlertSystem = None

class PersonalNotificationSystem:
    """利尻島昆布漁師向け個人別通知カスタマイズシステム
    
    各ユーザーの作業スケジュール、位置情報、連絡手段に応じた
    パーソナライズされた通知を提供する統合システム
    """
    
    def __init__(self):
        self.config_file = "personal_notification_config.json"
        self.users_file = "notification_users.json"
        self.templates_file = "notification_templates.json"
        self.notification_history_file = "notification_history.json"
        
        self.default_config = {
            "notification_channels": {
                "sms": {
                    "enabled": False,
                    "provider": "twilio",
                    "api_key": "",
                    "sender_number": ""
                },
                "email": {
                    "enabled": True,
                    "smtp_server": "smtp.gmail.com",
                    "smtp_port": 587,
                    "sender_email": "",
                    "sender_password": ""
                },
                "push": {
                    "enabled": False,
                    "service": "firebase",
                    "api_key": ""
                },
                "voice": {
                    "enabled": False,
                    "service": "voice_api",
                    "api_key": ""
                },
                "line": {
                    "enabled": False,
                    "bot_token": "",
                    "webhook_url": ""
                }
            },
            "notification_timing": {
                "weather_check_hours": [5, 11, 17],  # 朝・昼・夕の天気確認
                "urgent_alert_immediate": True,      # 緊急時は即時通知
                "work_start_advance_minutes": 30,    # 作業開始30分前
                "fog_warning_advance_hours": 2       # 海霧警報2時間前
            },
            "personalization_factors": {
                "work_experience_levels": ["beginner", "intermediate", "expert"],
                "risk_tolerance": ["conservative", "moderate", "aggressive"],
                "notification_verbosity": ["minimal", "standard", "detailed"],
                "work_schedule_flexibility": ["fixed", "flexible", "on_demand"]
            },
            "location_zones": {
                "oshidomari": {"name": "鴛泊港周辺", "priority": "high"},
                "senposhi": {"name": "仙法志港周辺", "priority": "high"},
                "kutsugata": {"name": "沓形周辺", "priority": "medium"},
                "oniwaki": {"name": "鬼脇周辺", "priority": "medium"},
                "custom": {"name": "カスタム地点", "priority": "user_defined"}
            }
        }
        
        self.default_templates = {
            "weather_summary": {
                "minimal": "{location}の天気: {condition}, 風{wind_speed}m/s, 降水確率{rain_prob}%",
                "standard": "【{location}】天気: {condition}, 気温{temp}℃, 風{wind_speed}m/s, 降水確率{rain_prob}%. {recommendation}",
                "detailed": "【{location} 詳細予報】\n天気: {condition}\n気温: {temp}℃ (体感{feels_like}℃)\n風速: {wind_speed}m/s ({wind_dir})\n降水確率: {rain_prob}%\n湿度: {humidity}%\n推奨: {recommendation}\n注意事項: {warnings}"
            },
            "fog_alert": {
                "minimal": "海霧注意: {location} {alert_level} {probability}%",
                "standard": "【海霧{alert_level}警報】{location}にて発生確率{probability}%. {main_recommendation}",
                "detailed": "【海霧詳細警報】\n地点: {location}\n警報レベル: {alert_level}\n発生確率: {probability}%\n予想時刻: {peak_time}\n持続時間: {duration}\n推奨事項:\n{detailed_recommendations}\n緊急連絡先: {emergency_contact}"
            },
            "work_schedule": {
                "minimal": "{time}から作業開始予定. 天候:{condition}",
                "standard": "【作業開始通知】{time}からの{location}での作業について: 天候{condition}, {work_recommendation}",
                "detailed": "【本日の作業計画】\n時間: {time}\n場所: {location}\n天候: {condition}\n海況: {sea_condition}\n作業適性: {work_suitability}\n推奨作業時間: {recommended_hours}\n注意事項: {precautions}\n代替計画: {alternative_plan}"
            }
        }
        
        self.load_config()
        self.load_users()
        self.load_templates()
        self.load_notification_history()
        
        # 海霧アラートシステムとの連携
        self.fog_alert_system = SeaFogAlertSystem() if SeaFogAlertSystem else None
        
        # スケジューラー管理
        self.scheduler_running = False
        self.scheduler_thread = None
        
        # 通知キュー
        self.notification_queue = []
        self.failed_notifications = []
        
        self.setup_notification_schedule()
    
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
            print(f"Personal notification config load error: {e}")
            self.config = self.default_config.copy()
    
    def save_config(self):
        """設定ファイルの保存"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Personal notification config save error: {e}")
    
    def load_users(self):
        """ユーザー設定の読み込み"""
        try:
            if os.path.exists(self.users_file):
                with open(self.users_file, 'r', encoding='utf-8') as f:
                    self.users = json.load(f)
            else:
                self.users = []
        except Exception as e:
            print(f"Users data load error: {e}")
            self.users = []
    
    def save_users(self):
        """ユーザー設定の保存"""
        try:
            with open(self.users_file, 'w', encoding='utf-8') as f:
                json.dump(self.users, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Users data save error: {e}")
    
    def load_templates(self):
        """通知テンプレートの読み込み"""
        try:
            if os.path.exists(self.templates_file):
                with open(self.templates_file, 'r', encoding='utf-8') as f:
                    self.templates = json.load(f)
            else:
                self.templates = self.default_templates.copy()
                self.save_templates()
        except Exception as e:
            print(f"Templates load error: {e}")
            self.templates = self.default_templates.copy()
    
    def save_templates(self):
        """通知テンプレートの保存"""
        try:
            with open(self.templates_file, 'w', encoding='utf-8') as f:
                json.dump(self.templates, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Templates save error: {e}")
    
    def load_notification_history(self):
        """通知履歴の読み込み"""
        try:
            if os.path.exists(self.notification_history_file):
                with open(self.notification_history_file, 'r', encoding='utf-8') as f:
                    self.notification_history = json.load(f)
            else:
                self.notification_history = []
        except Exception as e:
            print(f"Notification history load error: {e}")
            self.notification_history = []
    
    def save_notification_history(self):
        """通知履歴の保存"""
        try:
            # 最新1000件のみ保持
            if len(self.notification_history) > 1000:
                self.notification_history = self.notification_history[-1000:]
            
            with open(self.notification_history_file, 'w', encoding='utf-8') as f:
                json.dump(self.notification_history, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Notification history save error: {e}")
    
    def create_user_profile(self, user_data: Dict):
        """新規ユーザープロファイルの作成"""
        try:
            user_profile = {
                "user_id": len(self.users) + 1,
                "name": user_data.get("name", ""),
                "contact_info": {
                    "phone": user_data.get("phone", ""),
                    "email": user_data.get("email", ""),
                    "line_id": user_data.get("line_id", ""),
                    "preferred_method": user_data.get("preferred_method", "email")
                },
                "work_profile": {
                    "experience_level": user_data.get("experience_level", "intermediate"),
                    "primary_locations": user_data.get("primary_locations", ["oshidomari"]),
                    "work_schedule": {
                        "typical_start_time": user_data.get("start_time", "05:00"),
                        "typical_end_time": user_data.get("end_time", "16:00"),
                        "work_days": user_data.get("work_days", ["monday", "tuesday", "wednesday", "thursday", "friday"]),
                        "flexibility": user_data.get("schedule_flexibility", "flexible")
                    },
                    "equipment": {
                        "has_boat": user_data.get("has_boat", True),
                        "boat_size": user_data.get("boat_size", "small"),
                        "safety_equipment": user_data.get("safety_equipment", ["life_jacket", "radio"])
                    }
                },
                "notification_preferences": {
                    "verbosity": user_data.get("verbosity", "standard"),
                    "risk_tolerance": user_data.get("risk_tolerance", "moderate"),
                    "notification_channels": user_data.get("channels", ["email"]),
                    "quiet_hours": {
                        "start": user_data.get("quiet_start", "22:00"),
                        "end": user_data.get("quiet_end", "05:00")
                    },
                    "custom_thresholds": {
                        "fog_warning": user_data.get("fog_threshold", 0.3),
                        "wind_warning": user_data.get("wind_threshold", 8.0),
                        "rain_warning": user_data.get("rain_threshold", 30.0)
                    }
                },
                "emergency_contacts": user_data.get("emergency_contacts", []),
                "created_at": datetime.now().isoformat(),
                "last_updated": datetime.now().isoformat(),
                "active": True
            }
            
            self.users.append(user_profile)
            self.save_users()
            
            return user_profile["user_id"]
            
        except Exception as e:
            print(f"User profile creation error: {e}")
            return None
    
    def update_user_profile(self, user_id: int, updates: Dict):
        """ユーザープロファイルの更新"""
        try:
            user = self.get_user_by_id(user_id)
            if not user:
                return {"error": "ユーザーが見つかりません"}
            
            # 深い更新処理
            def deep_update(base_dict, update_dict):
                for key, value in update_dict.items():
                    if isinstance(value, dict) and key in base_dict and isinstance(base_dict[key], dict):
                        deep_update(base_dict[key], value)
                    else:
                        base_dict[key] = value
            
            deep_update(user, updates)
            user["last_updated"] = datetime.now().isoformat()
            
            self.save_users()
            return {"status": "success", "message": "プロファイルを更新しました"}
            
        except Exception as e:
            return {"error": f"プロファイル更新エラー: {str(e)}"}
    
    def get_user_by_id(self, user_id: int):
        """ユーザーIDによる検索"""
        for user in self.users:
            if user.get("user_id") == user_id:
                return user
        return None
    
    def setup_notification_schedule(self):
        """通知スケジュールの設定"""
        schedule.clear()
        
        # 定期天気確認
        check_hours = self.config["notification_timing"]["weather_check_hours"]
        for hour in check_hours:
            schedule.every().day.at(f"{hour:02d}:00").do(self.send_scheduled_weather_updates)
        
        # 作業開始前通知チェック
        schedule.every(15).minutes.do(self.check_work_start_notifications)
        
        # 海霧警報チェック
        schedule.every(10).minutes.do(self.check_fog_alerts)
        
        # 失敗した通知の再試行
        schedule.every(30).minutes.do(self.retry_failed_notifications)
    
    def start_notification_service(self):
        """通知サービスの開始"""
        if self.scheduler_running:
            return {"status": "already_running"}
        
        self.scheduler_running = True
        self.scheduler_thread = threading.Thread(target=self._notification_scheduler_loop, daemon=True)
        self.scheduler_thread.start()
        
        return {
            "status": "started",
            "message": "個人別通知サービスを開始しました",
            "active_users": len([u for u in self.users if u.get("active", True)])
        }
    
    def stop_notification_service(self):
        """通知サービスの停止"""
        self.scheduler_running = False
        if self.scheduler_thread:
            self.scheduler_thread.join(timeout=5)
        
        return {
            "status": "stopped",
            "message": "個人別通知サービスを停止しました"
        }
    
    def _notification_scheduler_loop(self):
        """通知スケジューラーループ"""
        while self.scheduler_running:
            try:
                schedule.run_pending()
                self.process_notification_queue()
                time.sleep(30)  # 30秒間隔でチェック
            except Exception as e:
                print(f"Notification scheduler error: {e}")
                time.sleep(60)
    
    def send_scheduled_weather_updates(self):
        """定期天気更新の送信"""
        try:
            for user in self.users:
                if not user.get("active", True):
                    continue
                
                # ユーザーの主要活動地点での天気予報を取得
                primary_locations = user["work_profile"]["primary_locations"]
                for location in primary_locations:
                    weather_data = self.get_location_weather(location)
                    if weather_data:
                        notification = self.create_weather_notification(user, location, weather_data)
                        self.queue_notification(notification)
            
            return {"status": "scheduled_weather_sent"}
            
        except Exception as e:
            print(f"Scheduled weather update error: {e}")
            return {"error": str(e)}
    
    def check_work_start_notifications(self):
        """作業開始前通知のチェック"""
        try:
            current_time = datetime.now()
            advance_minutes = self.config["notification_timing"]["work_start_advance_minutes"]
            
            for user in self.users:
                if not user.get("active", True):
                    continue
                
                work_schedule = user["work_profile"]["work_schedule"]
                start_time_str = work_schedule.get("typical_start_time", "05:00")
                
                # 作業開始時刻を今日の日付で計算
                try:
                    start_time = datetime.strptime(f"{current_time.date()} {start_time_str}", "%Y-%m-%d %H:%M")
                    notification_time = start_time - timedelta(minutes=advance_minutes)
                    
                    # 通知時刻の5分前後の範囲内かチェック
                    time_diff = abs((current_time - notification_time).total_seconds())
                    if time_diff <= 300:  # 5分以内
                        self.send_work_start_notification(user)
                        
                except ValueError:
                    continue
            
            return {"status": "work_start_check_completed"}
            
        except Exception as e:
            print(f"Work start notification check error: {e}")
            return {"error": str(e)}
    
    def check_fog_alerts(self):
        """海霧警報のチェック"""
        try:
            if not self.fog_alert_system:
                return {"error": "海霧アラートシステムが利用できません"}
            
            # アクティブな海霧警報を取得
            active_alerts = self.fog_alert_system.get_active_alerts()
            
            for alert in active_alerts:
                # 警報に関連するユーザーを特定
                affected_users = self.find_users_by_location(alert["zone"])
                
                for user in affected_users:
                    if self.should_notify_user_about_fog(user, alert):
                        notification = self.create_fog_alert_notification(user, alert)
                        self.queue_notification(notification)
            
            return {"status": "fog_alert_check_completed", "alerts_processed": len(active_alerts)}
            
        except Exception as e:
            print(f"Fog alert check error: {e}")
            return {"error": str(e)}
    
    def find_users_by_location(self, location_zone: str):
        """指定地域のユーザーを検索"""
        affected_users = []
        for user in self.users:
            if not user.get("active", True):
                continue
            
            primary_locations = user["work_profile"]["primary_locations"]
            if location_zone in primary_locations:
                affected_users.append(user)
        
        return affected_users
    
    def should_notify_user_about_fog(self, user: Dict, alert: Dict):
        """海霧警報でユーザーに通知すべきかの判定"""
        try:
            # ユーザーの警告閾値をチェック
            user_threshold = user["notification_preferences"]["custom_thresholds"]["fog_warning"]
            alert_probability = alert["risk_assessment"]["max_probability"]
            
            if alert_probability < user_threshold:
                return False
            
            # 静寂時間のチェック
            if self.is_quiet_hours(user):
                # 危険レベルでない限り通知しない
                if alert["alert_level"] != "danger":
                    return False
            
            # 最近同じ警報を送信済みかチェック
            recent_notifications = self.get_recent_user_notifications(user["user_id"], hours=2)
            for notification in recent_notifications:
                if (notification.get("type") == "fog_alert" and 
                    notification.get("zone") == alert["zone"]):
                    return False
            
            return True
            
        except Exception as e:
            print(f"Fog notification decision error: {e}")
            return False
    
    def is_quiet_hours(self, user: Dict):
        """静寂時間かどうかの判定"""
        try:
            quiet_hours = user["notification_preferences"]["quiet_hours"]
            current_time = datetime.now().time()
            start_time = datetime.strptime(quiet_hours["start"], "%H:%M").time()
            end_time = datetime.strptime(quiet_hours["end"], "%H:%M").time()
            
            if start_time <= end_time:
                return start_time <= current_time <= end_time
            else:  # 夜をまたぐ場合
                return current_time >= start_time or current_time <= end_time
                
        except Exception as e:
            print(f"Quiet hours check error: {e}")
            return False
    
    def get_recent_user_notifications(self, user_id: int, hours: int = 24):
        """ユーザーの最近の通知履歴を取得"""
        cutoff_time = datetime.now() - timedelta(hours=hours)
        
        recent_notifications = []
        for notification in self.notification_history:
            if (notification.get("user_id") == user_id and
                datetime.fromisoformat(notification["sent_at"]) >= cutoff_time):
                recent_notifications.append(notification)
        
        return recent_notifications
    
    def create_weather_notification(self, user: Dict, location: str, weather_data: Dict):
        """天気通知の作成"""
        try:
            verbosity = user["notification_preferences"]["verbosity"]
            template = self.templates["weather_summary"][verbosity]
            
            # 位置情報の解決
            location_name = self.config["location_zones"].get(location, {}).get("name", location)
            
            # テンプレート変数の準備
            template_vars = {
                "location": location_name,
                "condition": weather_data.get("condition", "不明"),
                "temp": weather_data.get("temperature", "N/A"),
                "feels_like": weather_data.get("feels_like", "N/A"),
                "wind_speed": weather_data.get("wind_speed", "N/A"),
                "wind_dir": weather_data.get("wind_direction", "N/A"),
                "rain_prob": weather_data.get("rain_probability", "N/A"),
                "humidity": weather_data.get("humidity", "N/A"),
                "recommendation": self.generate_work_recommendation(user, weather_data),
                "warnings": self.generate_weather_warnings(user, weather_data)
            }
            
            message_content = template.format(**template_vars)
            
            return {
                "user_id": user["user_id"],
                "type": "weather_update",
                "location": location,
                "priority": "normal",
                "channels": user["notification_preferences"]["notification_channels"],
                "content": message_content,
                "data": weather_data,
                "created_at": datetime.now().isoformat()
            }
            
        except Exception as e:
            print(f"Weather notification creation error: {e}")
            return None
    
    def create_fog_alert_notification(self, user: Dict, alert: Dict):
        """海霧警報通知の作成"""
        try:
            verbosity = user["notification_preferences"]["verbosity"]
            template = self.templates["fog_alert"][verbosity]
            
            # 警報レベルの日本語表示
            alert_level_names = {
                "warning": "注意報",
                "watch": "警戒警報", 
                "danger": "危険警報"
            }
            
            alert_level_jp = alert_level_names.get(alert["alert_level"], alert["alert_level"])
            probability_pct = int(alert["risk_assessment"]["max_probability"] * 100)
            
            # 詳細推奨事項の準備
            recommendations = alert.get("recommendations", [])
            detailed_recommendations = "\n".join([f"• {rec}" for rec in recommendations[:5]])
            
            template_vars = {
                "location": alert["zone"],
                "alert_level": alert_level_jp,
                "probability": probability_pct,
                "peak_time": alert["risk_assessment"].get("max_risk_time", "不明"),
                "duration": "2-4時間程度",  # 推定
                "main_recommendation": recommendations[0] if recommendations else "注意してください",
                "detailed_recommendations": detailed_recommendations,
                "emergency_contact": "海上保安庁: 118"
            }
            
            message_content = template.format(**template_vars)
            
            # 優先度の決定
            priority_map = {"warning": "normal", "watch": "high", "danger": "urgent"}
            priority = priority_map.get(alert["alert_level"], "normal")
            
            return {
                "user_id": user["user_id"],
                "type": "fog_alert",
                "zone": alert["zone"],
                "alert_level": alert["alert_level"],
                "priority": priority,
                "channels": user["notification_preferences"]["notification_channels"],
                "content": message_content,
                "data": alert,
                "created_at": datetime.now().isoformat()
            }
            
        except Exception as e:
            print(f"Fog alert notification creation error: {e}")
            return None
    
    def send_work_start_notification(self, user: Dict):
        """作業開始通知の送信"""
        try:
            # 今日の天気予報と海霧予測を取得
            primary_location = user["work_profile"]["primary_locations"][0]
            weather_data = self.get_location_weather(primary_location)
            
            verbosity = user["notification_preferences"]["verbosity"]
            template = self.templates["work_schedule"][verbosity]
            
            work_suitability = self.assess_work_suitability(user, weather_data)
            
            template_vars = {
                "time": user["work_profile"]["work_schedule"]["typical_start_time"],
                "location": self.config["location_zones"].get(primary_location, {}).get("name", primary_location),
                "condition": weather_data.get("condition", "不明"),
                "sea_condition": weather_data.get("sea_condition", "普通"),
                "work_suitability": work_suitability["assessment"],
                "work_recommendation": work_suitability["recommendation"],
                "recommended_hours": work_suitability["recommended_hours"],
                "precautions": work_suitability["precautions"],
                "alternative_plan": work_suitability["alternative_plan"]
            }
            
            message_content = template.format(**template_vars)
            
            notification = {
                "user_id": user["user_id"],
                "type": "work_start",
                "location": primary_location,
                "priority": "high",
                "channels": user["notification_preferences"]["notification_channels"],
                "content": message_content,
                "data": weather_data,
                "created_at": datetime.now().isoformat()
            }
            
            self.queue_notification(notification)
            
        except Exception as e:
            print(f"Work start notification error: {e}")
    
    def queue_notification(self, notification: Dict):
        """通知をキューに追加"""
        if notification:
            self.notification_queue.append(notification)
    
    def process_notification_queue(self):
        """通知キューの処理"""
        try:
            while self.notification_queue:
                notification = self.notification_queue.pop(0)
                success = self.send_notification(notification)
                
                if success:
                    self.add_to_notification_history(notification, "sent")
                else:
                    self.failed_notifications.append(notification)
                    self.add_to_notification_history(notification, "failed")
        
        except Exception as e:
            print(f"Notification queue processing error: {e}")
    
    def send_notification(self, notification: Dict):
        """実際の通知送信"""
        try:
            user = self.get_user_by_id(notification["user_id"])
            if not user:
                return False
            
            channels = notification["channels"]
            success_count = 0
            
            for channel in channels:
                if channel == "email" and self.config["notification_channels"]["email"]["enabled"]:
                    if self.send_email_notification(user, notification):
                        success_count += 1
                elif channel == "sms" and self.config["notification_channels"]["sms"]["enabled"]:
                    if self.send_sms_notification(user, notification):
                        success_count += 1
                elif channel == "console":
                    if self.send_console_notification(user, notification):
                        success_count += 1
            
            return success_count > 0
            
        except Exception as e:
            print(f"Notification sending error: {e}")
            return False
    
    def send_email_notification(self, user: Dict, notification: Dict):
        """メール通知の送信"""
        try:
            if not EMAIL_AVAILABLE:
                print(f"Email to {user['contact_info'].get('email', 'unknown')}: {notification['content'][:50]}... (simulated)")
                return True
            
            email_config = self.config["notification_channels"]["email"]
            user_email = user["contact_info"]["email"]
            
            if not user_email or not email_config.get("sender_email"):
                return False
            
            msg = MimeMultipart()
            msg['From'] = email_config["sender_email"]
            msg['To'] = user_email
            msg['Subject'] = f"利尻島昆布干場予報 - {notification['type']}"
            
            msg.attach(MimeText(notification["content"], 'plain', 'utf-8'))
            
            # SMTPサーバー設定（実際の実装では認証情報が必要）
            print(f"Email sent to {user_email}: {notification['content'][:50]}...")
            return True
            
        except Exception as e:
            print(f"Email notification error: {e}")
            return False
    
    def send_sms_notification(self, user: Dict, notification: Dict):
        """SMS通知の送信（スタブ実装）"""
        try:
            phone = user["contact_info"]["phone"]
            if not phone:
                return False
            
            # SMS送信の実装（Twilio等のAPIを使用）
            print(f"SMS sent to {phone}: {notification['content'][:100]}...")
            return True
            
        except Exception as e:
            print(f"SMS notification error: {e}")
            return False
    
    def send_console_notification(self, user: Dict, notification: Dict):
        """コンソール通知の送信"""
        try:
            priority_colors = {
                "normal": "\033[92m",    # 緑
                "high": "\033[93m",      # 黄
                "urgent": "\033[91m"     # 赤
            }
            
            color = priority_colors.get(notification.get("priority", "normal"), "\033[0m")
            reset = "\033[0m"
            
            # Unicode encoding issues workaround
            user_name = user['name']
            notification_type = notification['type']
            priority = notification.get('priority', 'normal')
            content = notification['content']
            
            print(f"\n{color}=== PERSONAL NOTIFICATION ==={reset}")
            print(f"{color}User: {user_name}{reset}")
            print(f"Type: {notification_type}")
            print(f"Priority: {priority}")
            print(f"Content: {content}")
            print(f"{color}=============================={reset}\n")
            
            return True
            
        except UnicodeEncodeError:
            # Fallback for encoding issues
            print(f"\n=== PERSONAL NOTIFICATION ===")
            print(f"User: {user['name'].encode('ascii', 'replace').decode('ascii')}")
            print(f"Type: {notification['type']}")
            print(f"Priority: {notification.get('priority', 'normal')}")
            print(f"Content: [notification content]")
            print(f"==============================\n")
            return True
        except Exception as e:
            print(f"Console notification error: {e}")
            return False
    
    def add_to_notification_history(self, notification: Dict, status: str):
        """通知履歴への追加"""
        try:
            history_entry = {
                "notification_id": len(self.notification_history) + 1,
                "user_id": notification["user_id"],
                "type": notification["type"],
                "status": status,
                "sent_at": datetime.now().isoformat(),
                "content_preview": notification["content"][:100],
                "channels_used": notification["channels"],
                "priority": notification.get("priority", "normal")
            }
            
            self.notification_history.append(history_entry)
            self.save_notification_history()
            
        except Exception as e:
            print(f"Notification history error: {e}")
    
    def retry_failed_notifications(self):
        """失敗した通知の再試行"""
        try:
            retry_count = 0
            for notification in self.failed_notifications[:]:
                # 1時間以内の失敗通知のみ再試行
                created_time = datetime.fromisoformat(notification["created_at"])
                if datetime.now() - created_time <= timedelta(hours=1):
                    if self.send_notification(notification):
                        self.failed_notifications.remove(notification)
                        self.add_to_notification_history(notification, "retried_success")
                        retry_count += 1
                else:
                    self.failed_notifications.remove(notification)
            
            return {"retried_count": retry_count}
            
        except Exception as e:
            print(f"Failed notification retry error: {e}")
            return {"error": str(e)}
    
    def get_location_weather(self, location: str):
        """位置別天気データの取得（スタブ実装）"""
        # 実際の実装では外部気象APIを使用
        return {
            "condition": "晴れ時々曇り",
            "temperature": 18,
            "feels_like": 16,
            "wind_speed": 5.2,
            "wind_direction": "北東",
            "rain_probability": 20,
            "humidity": 75,
            "sea_condition": "穏やか"
        }
    
    def generate_work_recommendation(self, user: Dict, weather_data: Dict):
        """作業推奨事項の生成"""
        experience = user["work_profile"]["experience_level"]
        wind_speed = weather_data.get("wind_speed", 0)
        rain_prob = weather_data.get("rain_probability", 0)
        
        if wind_speed > 8:
            return "強風のため作業延期を推奨"
        elif rain_prob > 60:
            return "降雨の可能性が高いため注意"
        elif experience == "beginner" and wind_speed > 5:
            return "初心者の方は風に注意して作業してください"
        else:
            return "作業に適した条件です"
    
    def generate_weather_warnings(self, user: Dict, weather_data: Dict):
        """気象警告の生成"""
        warnings = []
        
        if weather_data.get("wind_speed", 0) > 6:
            warnings.append("強風注意")
        if weather_data.get("rain_probability", 0) > 40:
            warnings.append("降雨可能性")
        if weather_data.get("visibility", 10000) < 2000:
            warnings.append("視程不良")
        
        return "、".join(warnings) if warnings else "特に注意事項なし"
    
    def assess_work_suitability(self, user: Dict, weather_data: Dict):
        """作業適性の評価"""
        wind_speed = weather_data.get("wind_speed", 0)
        rain_prob = weather_data.get("rain_probability", 0)
        experience = user["work_profile"]["experience_level"]
        
        if wind_speed > 8 or rain_prob > 60:
            return {
                "assessment": "不適",
                "recommendation": "作業延期を推奨",
                "recommended_hours": "0時間",
                "precautions": "安全確保のため作業中止",
                "alternative_plan": "屋内での準備作業"
            }
        elif wind_speed > 5 and experience == "beginner":
            return {
                "assessment": "要注意",
                "recommendation": "経験者同行推奨",
                "recommended_hours": "3-4時間",
                "precautions": "風速と安全装備確認",
                "alternative_plan": "午後まで待機"
            }
        else:
            return {
                "assessment": "良好",
                "recommendation": "通常作業可能",
                "recommended_hours": "6-8時間",
                "precautions": "通常の安全対策",
                "alternative_plan": "計画通り実施"
            }
    
    def get_user_notification_dashboard(self, user_id: int):
        """ユーザー通知ダッシュボードの取得"""
        try:
            user = self.get_user_by_id(user_id)
            if not user:
                return {"error": "ユーザーが見つかりません"}
            
            # 最近の通知履歴
            recent_notifications = self.get_recent_user_notifications(user_id, 168)  # 1週間
            
            # 通知統計
            total_notifications = len(recent_notifications)
            notification_types = {}
            for notification in recent_notifications:
                type_name = notification.get("type", "unknown")
                notification_types[type_name] = notification_types.get(type_name, 0) + 1
            
            # 次回予定通知
            next_notifications = self.get_upcoming_notifications(user_id)
            
            return {
                "user_info": {
                    "name": user["name"],
                    "user_id": user_id,
                    "last_updated": user["last_updated"]
                },
                "notification_stats": {
                    "total_recent": total_notifications,
                    "by_type": notification_types,
                    "success_rate": self.calculate_success_rate(user_id)
                },
                "recent_notifications": recent_notifications[-10:],  # 最新10件
                "upcoming_notifications": next_notifications,
                "current_settings": user["notification_preferences"],
                "active_alerts": self.get_user_active_alerts(user_id)
            }
            
        except Exception as e:
            return {"error": f"ダッシュボード取得エラー: {str(e)}"}
    
    def calculate_success_rate(self, user_id: int):
        """通知成功率の計算"""
        try:
            user_notifications = [n for n in self.notification_history if n.get("user_id") == user_id]
            if not user_notifications:
                return 1.0
            
            success_count = len([n for n in user_notifications if n.get("status") in ["sent", "retried_success"]])
            return success_count / len(user_notifications)
            
        except Exception:
            return 1.0
    
    def get_upcoming_notifications(self, user_id: int):
        """予定通知の取得"""
        user = self.get_user_by_id(user_id)
        if not user:
            return []
        
        upcoming = []
        
        # 次回の天気通知時刻
        check_hours = self.config["notification_timing"]["weather_check_hours"]
        current_hour = datetime.now().hour
        
        for hour in check_hours:
            if hour > current_hour:
                next_weather = datetime.now().replace(hour=hour, minute=0, second=0, microsecond=0)
                upcoming.append({
                    "type": "weather_update",
                    "scheduled_time": next_weather.isoformat(),
                    "description": "定期天気更新"
                })
                break
        
        # 明日の作業開始通知
        work_start = user["work_profile"]["work_schedule"]["typical_start_time"]
        try:
            tomorrow = datetime.now().date() + timedelta(days=1)
            work_time = datetime.strptime(f"{tomorrow} {work_start}", "%Y-%m-%d %H:%M")
            advance_minutes = self.config["notification_timing"]["work_start_advance_minutes"]
            notification_time = work_time - timedelta(minutes=advance_minutes)
            
            upcoming.append({
                "type": "work_start",
                "scheduled_time": notification_time.isoformat(),
                "description": "作業開始前通知"
            })
        except ValueError:
            pass
        
        return upcoming
    
    def get_user_active_alerts(self, user_id: int):
        """ユーザー関連のアクティブ警報取得"""
        user = self.get_user_by_id(user_id)
        if not user or not self.fog_alert_system:
            return []
        
        active_alerts = self.fog_alert_system.get_active_alerts()
        user_locations = user["work_profile"]["primary_locations"]
        
        relevant_alerts = []
        for alert in active_alerts:
            if alert["zone"] in user_locations:
                relevant_alerts.append({
                    "zone": alert["zone"],
                    "alert_level": alert["alert_level"],
                    "probability": alert["risk_assessment"]["max_probability"],
                    "expires_at": alert["expires_at"]
                })
        
        return relevant_alerts
    
    def get_system_status(self):
        """個人通知システムの状態取得"""
        return {
            "service_running": self.scheduler_running,
            "total_users": len(self.users),
            "active_users": len([u for u in self.users if u.get("active", True)]),
            "notifications_in_queue": len(self.notification_queue),
            "failed_notifications": len(self.failed_notifications),
            "fog_alert_integration": self.fog_alert_system is not None,
            "last_notification_sent": self.notification_history[-1]["sent_at"] if self.notification_history else None,
            "notification_channels_enabled": {
                channel: config.get("enabled", False) 
                for channel, config in self.config["notification_channels"].items()
            }
        }

if __name__ == "__main__":
    # テスト実行
    print("=== Personal Notification System Test ===")
    
    notification_system = PersonalNotificationSystem()
    
    # テストユーザーの作成
    test_user_data = {
        "name": "Test Fisherman",
        "email": "test@example.com",
        "phone": "090-1234-5678",
        "experience_level": "intermediate",
        "primary_locations": ["oshidomari", "senposhi"],
        "start_time": "05:30",
        "end_time": "15:30",
        "preferred_method": "email",
        "verbosity": "standard",
        "channels": ["email", "console"]
    }
    
    user_id = notification_system.create_user_profile(test_user_data)
    if user_id:
        print(f"Test user created with ID: {user_id}")
        
        # 通知サービスの開始
        start_result = notification_system.start_notification_service()
        print(f"Notification service: {start_result.get('status')}")
        
        # テスト通知の送信
        test_user = notification_system.get_user_by_id(user_id)
        if test_user:
            weather_data = notification_system.get_location_weather("oshidomari")
            notification = notification_system.create_weather_notification(test_user, "oshidomari", weather_data)
            
            if notification:
                notification_system.queue_notification(notification)
                notification_system.process_notification_queue()
                print("Test notification sent")
        
        # ダッシュボード表示
        dashboard = notification_system.get_user_notification_dashboard(user_id)
        if "error" not in dashboard:
            print(f"Dashboard generated for user: {dashboard['user_info']['name']}")
            print(f"Recent notifications: {dashboard['notification_stats']['total_recent']}")
        
        # システム状態表示
        status = notification_system.get_system_status()
        print(f"System status: Service running: {status['service_running']}")
        print(f"Active users: {status['active_users']}")
        
    else:
        print("Failed to create test user")
    
    print("\n=== Test Completed ===")