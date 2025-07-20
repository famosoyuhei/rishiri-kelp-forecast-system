import json
import os
from datetime import datetime, timedelta
import threading
import time
import schedule
from typing import Dict, List, Optional, Callable

try:
    from sea_fog_prediction import SeaFogPredictionEngine
except ImportError:
    SeaFogPredictionEngine = None

class SeaFogAlertSystem:
    """利尻島海霧アラートシステム
    
    海霧予測データに基づいて自動アラートを生成し、
    昆布漁師への早期警告を提供する統合システム
    """
    
    def __init__(self):
        self.config_file = "sea_fog_alert_config.json"
        self.alert_history_file = "sea_fog_alert_history.json"
        self.subscribers_file = "sea_fog_alert_subscribers.json"
        
        self.default_config = {
            "alert_thresholds": {
                "warning": 0.3,      # 注意警報（30%以上）
                "watch": 0.6,        # 警戒警報（60%以上）
                "danger": 0.8        # 危険警報（80%以上）
            },
            "monitoring_schedule": {
                "check_interval_minutes": 15,     # 15分間隔でチェック
                "early_morning_check": "04:00",   # 作業開始前チェック
                "work_hours_check": "06:00",      # 作業時間チェック
                "evening_check": "16:00"          # 作業終了チェック
            },
            "alert_conditions": {
                "work_hours_only": False,         # 作業時間外もアラート
                "consecutive_hours_threshold": 3, # 3時間連続高リスクでアラート
                "rapid_increase_threshold": 0.3,  # 急激な上昇（30%/時間）
                "minimum_advance_notice": 2       # 最低2時間前に警告
            },
            "notification_channels": {
                "console": True,
                "file": True,
                "email": False,
                "sms": False,
                "webhook": False,
                "system_notification": True
            },
            "alert_zones": {
                "oshidomari": {"lat": 45.242, "lon": 141.231, "priority": "high"},
                "senposhi": {"lat": 45.136, "lon": 141.211, "priority": "high"},
                "kutsugata": {"lat": 45.210, "lon": 141.200, "priority": "medium"},
                "oniwaki": {"lat": 45.180, "lon": 141.270, "priority": "medium"},
                "rishiri_mountain": {"lat": 45.178, "lon": 141.228, "priority": "low"}
            }
        }
        
        self.load_config()
        self.load_alert_history()
        self.load_subscribers()
        
        # アラート状態管理
        self.active_alerts = {}
        self.last_check_time = None
        self.alert_callbacks = []
        
        # 海霧予測エンジンの初期化
        self.fog_engine = SeaFogPredictionEngine() if SeaFogPredictionEngine else None
        
        # スケジューラー
        self.scheduler_running = False
        self.scheduler_thread = None
        
        self.setup_alert_schedule()
    
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
            print(f"Alert config load error: {e}")
            self.config = self.default_config.copy()
    
    def save_config(self):
        """設定ファイルの保存"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Alert config save error: {e}")
    
    def load_alert_history(self):
        """アラート履歴の読み込み"""
        try:
            if os.path.exists(self.alert_history_file):
                with open(self.alert_history_file, 'r', encoding='utf-8') as f:
                    self.alert_history = json.load(f)
            else:
                self.alert_history = []
        except Exception as e:
            print(f"Alert history load error: {e}")
            self.alert_history = []
    
    def save_alert_history(self):
        """アラート履歴の保存"""
        try:
            # 最新1000件のみ保持
            if len(self.alert_history) > 1000:
                self.alert_history = self.alert_history[-1000:]
            
            with open(self.alert_history_file, 'w', encoding='utf-8') as f:
                json.dump(self.alert_history, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Alert history save error: {e}")
    
    def load_subscribers(self):
        """アラート購読者の読み込み"""
        try:
            if os.path.exists(self.subscribers_file):
                with open(self.subscribers_file, 'r', encoding='utf-8') as f:
                    self.subscribers = json.load(f)
            else:
                self.subscribers = []
        except Exception as e:
            print(f"Alert subscribers load error: {e}")
            self.subscribers = []
    
    def save_subscribers(self):
        """アラート購読者の保存"""
        try:
            with open(self.subscribers_file, 'w', encoding='utf-8') as f:
                json.dump(self.subscribers, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Alert subscribers save error: {e}")
    
    def add_subscriber(self, name: str, contact_info: Dict, alert_preferences: Dict = None):
        """アラート購読者の追加"""
        subscriber = {
            "id": len(self.subscribers) + 1,
            "name": name,
            "contact_info": contact_info,
            "alert_preferences": alert_preferences or {
                "minimum_level": "warning",
                "zones": list(self.config["alert_zones"].keys()),
                "notification_methods": ["console", "file"],
                "quiet_hours": {"start": "22:00", "end": "05:00"},
                "active": True
            },
            "created_at": datetime.now().isoformat()
        }
        
        self.subscribers.append(subscriber)
        self.save_subscribers()
        return subscriber["id"]
    
    def remove_subscriber(self, subscriber_id: int):
        """アラート購読者の削除"""
        self.subscribers = [s for s in self.subscribers if s["id"] != subscriber_id]
        self.save_subscribers()
    
    def setup_alert_schedule(self):
        """アラートスケジュールの設定"""
        schedule.clear()
        
        # 定期チェック
        interval = self.config["monitoring_schedule"]["check_interval_minutes"]
        schedule.every(interval).minutes.do(self.run_periodic_check)
        
        # 重要時刻のチェック
        schedule.every().day.at(self.config["monitoring_schedule"]["early_morning_check"]).do(
            lambda: self.run_scheduled_check("early_morning")
        )
        schedule.every().day.at(self.config["monitoring_schedule"]["work_hours_check"]).do(
            lambda: self.run_scheduled_check("work_hours")
        )
        schedule.every().day.at(self.config["monitoring_schedule"]["evening_check"]).do(
            lambda: self.run_scheduled_check("evening")
        )
    
    def start_monitoring(self):
        """アラート監視の開始"""
        if self.scheduler_running:
            return {"status": "already_running"}
        
        self.scheduler_running = True
        self.scheduler_thread = threading.Thread(target=self._scheduler_loop, daemon=True)
        self.scheduler_thread.start()
        
        return {
            "status": "started",
            "message": "海霧アラート監視を開始しました",
            "check_interval": self.config["monitoring_schedule"]["check_interval_minutes"]
        }
    
    def stop_monitoring(self):
        """アラート監視の停止"""
        self.scheduler_running = False
        if self.scheduler_thread:
            self.scheduler_thread.join(timeout=5)
        
        return {
            "status": "stopped",
            "message": "海霧アラート監視を停止しました"
        }
    
    def _scheduler_loop(self):
        """スケジューラーループ"""
        while self.scheduler_running:
            try:
                schedule.run_pending()
                time.sleep(60)  # 1分間隔でスケジュールをチェック
            except Exception as e:
                print(f"Scheduler error: {e}")
                time.sleep(60)
    
    def run_periodic_check(self):
        """定期チェックの実行"""
        try:
            return self.check_all_zones()
        except Exception as e:
            print(f"Periodic check error: {e}")
            return {"error": str(e)}
    
    def run_scheduled_check(self, check_type: str):
        """スケジュール済みチェックの実行"""
        try:
            result = self.check_all_zones()
            result["check_type"] = check_type
            result["scheduled"] = True
            return result
        except Exception as e:
            print(f"Scheduled check error ({check_type}): {e}")
            return {"error": str(e), "check_type": check_type}
    
    def check_all_zones(self):
        """全アラートゾーンのチェック"""
        if not self.fog_engine:
            return {"error": "海霧予測エンジンが利用できません"}
        
        alerts_generated = []
        zones_checked = 0
        
        for zone_name, zone_info in self.config["alert_zones"].items():
            try:
                alert = self.check_zone_alert(zone_name, zone_info)
                if alert:
                    alerts_generated.append(alert)
                zones_checked += 1
            except Exception as e:
                print(f"Zone check error ({zone_name}): {e}")
        
        self.last_check_time = datetime.now()
        
        return {
            "status": "completed",
            "zones_checked": zones_checked,
            "alerts_generated": len(alerts_generated),
            "alerts": alerts_generated,
            "check_time": self.last_check_time.isoformat()
        }
    
    def check_zone_alert(self, zone_name: str, zone_info: Dict):
        """個別ゾーンのアラートチェック"""
        lat = zone_info["lat"]
        lon = zone_info["lon"]
        priority = zone_info["priority"]
        
        # 海霧予測データの取得
        prediction = self.fog_engine.predict_sea_fog(lat, lon, 
                                                   datetime.now().strftime("%Y-%m-%d"), 12)
        
        if "error" in prediction:
            return None
        
        # アラート条件の評価
        alert_info = self.evaluate_alert_conditions(zone_name, prediction, priority)
        
        if alert_info:
            # アラートの生成と配信
            alert = self.generate_alert(zone_name, zone_info, alert_info, prediction)
            self.distribute_alert(alert)
            return alert
        
        return None
    
    def evaluate_alert_conditions(self, zone_name: str, prediction: Dict, priority: str):
        """アラート条件の評価"""
        hourly_predictions = prediction.get("hourly_predictions", [])
        if not hourly_predictions:
            return None
        
        thresholds = self.config["alert_thresholds"]
        conditions = self.config["alert_conditions"]
        
        # 現在時刻から予測をチェック
        current_time = datetime.now()
        
        # 最大リスクとその時刻
        max_risk = 0
        max_risk_time = None
        
        # 連続高リスク時間
        consecutive_high_risk = 0
        
        # 急激な上昇検出
        rapid_increase_detected = False
        prev_prob = 0
        
        # 作業時間帯の高リスク
        work_hours_risk = []
        
        for i, pred in enumerate(hourly_predictions):
            prob = pred["fog_probability"]
            pred_time = datetime.fromisoformat(pred["datetime"])
            
            # 最大リスク更新
            if prob > max_risk:
                max_risk = prob
                max_risk_time = pred_time
            
            # 作業時間帯（4-16時）のリスク
            if 4 <= pred_time.hour <= 16:
                work_hours_risk.append(prob)
            
            # 連続高リスクチェック
            if prob >= thresholds["watch"]:
                consecutive_high_risk += 1
            else:
                consecutive_high_risk = 0
            
            # 急激な上昇チェック
            if i > 0 and (prob - prev_prob) >= conditions["rapid_increase_threshold"]:
                rapid_increase_detected = True
            
            prev_prob = prob
        
        # アラート条件の判定
        alert_level = None
        alert_reasons = []
        
        if max_risk >= thresholds["danger"]:
            alert_level = "danger"
            alert_reasons.append(f"Danger level ({max_risk:.1%})")
        elif max_risk >= thresholds["watch"]:
            alert_level = "watch"
            alert_reasons.append(f"Watch level ({max_risk:.1%})")
        elif max_risk >= thresholds["warning"]:
            alert_level = "warning"
            alert_reasons.append(f"Warning level ({max_risk:.1%})")
        
        if consecutive_high_risk >= conditions["consecutive_hours_threshold"]:
            alert_reasons.append(f"Consecutive high risk ({consecutive_high_risk} hours)")
            if not alert_level or alert_level == "warning":
                alert_level = "watch"
        
        if rapid_increase_detected:
            alert_reasons.append("Rapid risk increase")
            if not alert_level:
                alert_level = "warning"
        
        # 作業時間帯の平均リスク
        work_avg_risk = sum(work_hours_risk) / len(work_hours_risk) if work_hours_risk else 0
        if work_avg_risk >= thresholds["warning"]:
            alert_reasons.append(f"Work hours high risk (avg {work_avg_risk:.1%})")
        
        if alert_level:
            return {
                "level": alert_level,
                "max_risk": max_risk,
                "max_risk_time": max_risk_time.isoformat() if max_risk_time else None,
                "work_hours_avg_risk": work_avg_risk,
                "consecutive_hours": consecutive_high_risk,
                "rapid_increase": rapid_increase_detected,
                "reasons": alert_reasons,
                "priority": priority
            }
        
        return None
    
    def generate_alert(self, zone_name: str, zone_info: Dict, alert_info: Dict, prediction: Dict):
        """アラートの生成"""
        alert = {
            "id": f"fog_alert_{zone_name}_{int(datetime.now().timestamp())}",
            "timestamp": datetime.now().isoformat(),
            "zone": zone_name,
            "location": {
                "lat": zone_info["lat"],
                "lon": zone_info["lon"]
            },
            "alert_level": alert_info["level"],
            "priority": alert_info["priority"],
            "risk_assessment": {
                "max_probability": alert_info["max_risk"],
                "max_risk_time": alert_info["max_risk_time"],
                "work_hours_average": alert_info["work_hours_avg_risk"],
                "consecutive_high_risk_hours": alert_info["consecutive_hours"],
                "rapid_increase_detected": alert_info["rapid_increase"]
            },
            "recommendations": self.generate_recommendations(alert_info, prediction),
            "summary": {
                "message": self.format_alert_message(zone_name, alert_info),
                "reasons": alert_info["reasons"]
            },
            "prediction_data": prediction,
            "expires_at": (datetime.now() + timedelta(hours=6)).isoformat()
        }
        
        # アラート履歴に追加
        self.alert_history.append(alert)
        self.save_alert_history()
        
        # アクティブアラートに追加
        self.active_alerts[alert["id"]] = alert
        
        return alert
    
    def generate_recommendations(self, alert_info: Dict, prediction: Dict):
        """推奨事項の生成"""
        recommendations = []
        level = alert_info["level"]
        max_risk = alert_info["max_risk"]
        
        if level == "danger":
            recommendations.extend([
                "Strongly recommend immediate cessation of kelp work",
                "Consider collecting kelp already being dried",
                "Recommend waiting at port or evacuation",
                "Visibility may deteriorate rapidly",
                "Check safety equipment and secure emergency communication"
            ])
        elif level == "watch":
            recommendations.extend([
                "Consider postponing start of kelp work",
                "If working, recommend early completion",
                "Prepare visibility equipment",
                "Monitor weather conditions closely",
                "Check emergency evacuation plan"
            ])
        elif level == "warning":
            recommendations.extend([
                "Check latest weather information before starting work",
                "Pay attention to visibility changes during work",
                "Secure communication means and report status regularly",
                "Consider shortening work hours"
            ])
        
        # 時間帯別の推奨事項
        work_avg = alert_info["work_hours_avg_risk"]
        if work_avg >= 0.6:
            recommendations.append("High risk throughout work hours (4-16)")
        elif work_avg >= 0.3:
            recommendations.append("Caution needed during part of work hours")
        
        return recommendations
    
    def format_alert_message(self, zone_name: str, alert_info: Dict):
        """アラートメッセージのフォーマット"""
        level_names = {
            "warning": "Warning Alert",
            "watch": "Watch Alert", 
            "danger": "Danger Alert"
        }
        
        level_name = level_names.get(alert_info["level"], "Alert")
        max_risk_pct = alert_info["max_risk"] * 100
        
        return f"[{level_name}] {zone_name} Sea Fog Risk {max_risk_pct:.1f}%"
    
    def distribute_alert(self, alert: Dict):
        """アラートの配信"""
        channels = self.config["notification_channels"]
        alert_level = alert["alert_level"]
        
        # コンソール出力
        if channels.get("console", True):
            self._send_console_alert(alert)
        
        # ファイル出力
        if channels.get("file", True):
            self._send_file_alert(alert)
        
        # 購読者への通知
        self._notify_subscribers(alert)
        
        # コールバック関数の実行
        for callback in self.alert_callbacks:
            try:
                callback(alert)
            except Exception as e:
                print(f"Alert callback error: {e}")
    
    def _send_console_alert(self, alert: Dict):
        """コンソールアラート"""
        level_colors = {
            "warning": "\033[93m",  # 黄色
            "watch": "\033[91m",    # 赤色
            "danger": "\033[95m"    # マゼンタ
        }
        color = level_colors.get(alert["alert_level"], "\033[0m")
        reset = "\033[0m"
        
        print(f"\n{color}=== SEA FOG ALERT ==={reset}")
        print(f"{color}{alert['summary']['message']}{reset}")
        print(f"Zone: {alert['zone']}")
        print(f"Time: {alert['timestamp']}")
        print(f"Max Risk: {alert['risk_assessment']['max_probability']:.1%}")
        print(f"Recommendations:")
        for rec in alert['recommendations'][:3]:  # 最初の3件のみ表示
            print(f"  - {rec}")
        print(f"{color}========================{reset}\n")
    
    def _send_file_alert(self, alert: Dict):
        """ファイルアラート"""
        alert_log_file = f"sea_fog_alerts_{datetime.now().strftime('%Y%m')}.log"
        try:
            with open(alert_log_file, 'a', encoding='utf-8') as f:
                f.write(f"{alert['timestamp']} - {alert['alert_level'].upper()} - {alert['zone']}\n")
                f.write(f"  Message: {alert['summary']['message']}\n")
                f.write(f"  Max Risk: {alert['risk_assessment']['max_probability']:.1%}\n")
                f.write(f"  Recommendations: {'; '.join(alert['recommendations'][:2])}\n\n")
        except Exception as e:
            print(f"File alert error: {e}")
    
    def _notify_subscribers(self, alert: Dict):
        """購読者への通知"""
        for subscriber in self.subscribers:
            if not subscriber.get("alert_preferences", {}).get("active", True):
                continue
            
            # アラートレベルのフィルタリング
            min_level = subscriber["alert_preferences"].get("minimum_level", "warning")
            level_priority = {"warning": 1, "watch": 2, "danger": 3}
            
            if level_priority.get(alert["alert_level"], 0) < level_priority.get(min_level, 1):
                continue
            
            # ゾーンのフィルタリング
            zones = subscriber["alert_preferences"].get("zones", [])
            if zones and alert["zone"] not in zones:
                continue
            
            # 静寂時間のチェック
            if self._is_quiet_hours(subscriber):
                continue
            
            # 通知の送信
            self._send_subscriber_notification(subscriber, alert)
    
    def _is_quiet_hours(self, subscriber: Dict):
        """静寂時間のチェック"""
        quiet_hours = subscriber["alert_preferences"].get("quiet_hours")
        if not quiet_hours:
            return False
        
        current_time = datetime.now().time()
        start_time = datetime.strptime(quiet_hours["start"], "%H:%M").time()
        end_time = datetime.strptime(quiet_hours["end"], "%H:%M").time()
        
        if start_time <= end_time:
            return start_time <= current_time <= end_time
        else:  # 夜をまたぐ場合
            return current_time >= start_time or current_time <= end_time
    
    def _send_subscriber_notification(self, subscriber: Dict, alert: Dict):
        """購読者個別通知"""
        methods = subscriber["alert_preferences"].get("notification_methods", ["console"])
        
        # 実装例（実際の通知システムと統合）
        notification_data = {
            "subscriber_id": subscriber["id"],
            "subscriber_name": subscriber["name"],
            "alert_id": alert["id"],
            "message": alert["summary"]["message"],
            "recommendations": alert["recommendations"][:3],
            "methods": methods
        }
        
        # ここで実際の通知システム（メール、SMS等）と統合
        print(f"Notification sent to {subscriber['name']}: {alert['summary']['message']}")
    
    def add_alert_callback(self, callback: Callable):
        """アラートコールバックの追加"""
        self.alert_callbacks.append(callback)
    
    def remove_alert_callback(self, callback: Callable):
        """アラートコールバックの削除"""
        if callback in self.alert_callbacks:
            self.alert_callbacks.remove(callback)
    
    def get_active_alerts(self):
        """アクティブアラートの取得"""
        # 期限切れアラートの削除
        current_time = datetime.now()
        expired_alerts = []
        
        for alert_id, alert in self.active_alerts.items():
            expires_at = datetime.fromisoformat(alert["expires_at"])
            if current_time > expires_at:
                expired_alerts.append(alert_id)
        
        for alert_id in expired_alerts:
            del self.active_alerts[alert_id]
        
        return list(self.active_alerts.values())
    
    def get_alert_history(self, days: int = 7):
        """アラート履歴の取得"""
        cutoff_date = datetime.now() - timedelta(days=days)
        
        return [
            alert for alert in self.alert_history
            if datetime.fromisoformat(alert["timestamp"]) >= cutoff_date
        ]
    
    def get_status(self):
        """アラートシステムの状態取得"""
        return {
            "monitoring_active": self.scheduler_running,
            "last_check": self.last_check_time.isoformat() if self.last_check_time else None,
            "active_alerts_count": len(self.get_active_alerts()),
            "subscribers_count": len([s for s in self.subscribers if s.get("alert_preferences", {}).get("active", True)]),
            "zones_monitored": len(self.config["alert_zones"]),
            "check_interval": self.config["monitoring_schedule"]["check_interval_minutes"],
            "fog_engine_available": self.fog_engine is not None
        }

if __name__ == "__main__":
    # テスト実行
    print("=== Sea Fog Alert System Test ===")
    
    alert_system = SeaFogAlertSystem()
    
    # システム状態の表示
    status = alert_system.get_status()
    print(f"Monitoring: {'Active' if status['monitoring_active'] else 'Inactive'}")
    print(f"Fog Engine: {'Available' if status['fog_engine_available'] else 'Unavailable'}")
    print(f"Zones: {status['zones_monitored']}")
    print(f"Subscribers: {status['subscribers_count']}")
    
    # テスト購読者の追加
    subscriber_id = alert_system.add_subscriber(
        "Test Fisherman",
        {"email": "test@example.com"},
        {
            "minimum_level": "warning",
            "zones": ["oshidomari", "senposhi"],
            "notification_methods": ["console", "file"]
        }
    )
    print(f"Test subscriber added with ID: {subscriber_id}")
    
    # 監視の開始（テスト用）
    if status['fog_engine_available']:
        result = alert_system.start_monitoring()
        print(f"Monitoring start result: {result.get('status', 'unknown')}")
        
        # 手動チェックのテスト
        print("\nRunning manual check...")
        check_result = alert_system.run_periodic_check()
        if "error" not in check_result:
            print(f"Check completed: {check_result['zones_checked']} zones, {check_result['alerts_generated']} alerts")
        else:
            print(f"Check error: {check_result['error']}")
    else:
        print("Cannot start monitoring: Fog engine not available")
    
    print("\n=== Test Completed ===")