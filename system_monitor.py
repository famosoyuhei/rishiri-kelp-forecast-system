import os
import json
import time
import psutil
import threading
from datetime import datetime, timedelta
import requests
from pathlib import Path

class SystemMonitor:
    """利尻島昆布干場予報システム稼働状況監視"""
    
    def __init__(self):
        self.monitor_config_file = "system_monitor_config.json"
        self.health_log_file = "system_health.json"
        self.alert_log_file = "system_alerts.json"
        
        self.default_config = {
            "monitoring_interval": 60,  # 60秒間隔
            "health_check_enabled": True,
            "performance_monitoring_enabled": True,
            "error_log_monitoring_enabled": True,
            "alert_thresholds": {
                "cpu_usage_max": 80.0,      # CPU使用率警告レベル
                "memory_usage_max": 85.0,   # メモリ使用率警告レベル
                "disk_usage_max": 90.0,     # ディスク使用率警告レベル
                "response_time_max": 5.0,   # レスポンス時間警告レベル(秒)
                "error_count_max": 10       # エラー回数警告レベル(1時間)
            },
            "endpoints_to_monitor": [
                "http://localhost:8000/",
                "http://localhost:8000/spots",
                "http://localhost:8000/system_status",
                "http://localhost:8000/fishing_season/status"
            ],
            "files_to_monitor": [
                "konbu_flask_final.py",
                "hoshiba_spots.csv",
                "hoshiba_records.csv",
                "weather_labeled_dataset.csv"
            ],
            "alert_methods": {
                "console": True,
                "file": True,
                "email": False,  # 設定次第で有効化
                "webhook": False  # 設定次第で有効化
            }
        }
        
        self.load_config()
        self.running = False
        self.last_health_check = None
        self.error_counts = {}
        
    def load_config(self):
        """設定ファイルの読み込み"""
        try:
            if os.path.exists(self.monitor_config_file):
                with open(self.monitor_config_file, 'r', encoding='utf-8') as f:
                    loaded_config = json.load(f)
                
                self.config = self.default_config.copy()
                self._merge_config(self.config, loaded_config)
            else:
                self.config = self.default_config.copy()
                self.save_config()
        except Exception as e:
            print(f"Monitor config load error: {e}")
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
            with open(self.monitor_config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"Monitor config save error: {e}")
            return False
    
    def get_system_health(self):
        """システムヘルスチェック"""
        health_data = {
            "timestamp": datetime.now().isoformat(),
            "status": "healthy",
            "issues": [],
            "metrics": {}
        }
        
        try:
            # CPU使用率チェック
            cpu_percent = psutil.cpu_percent(interval=1)
            health_data["metrics"]["cpu_usage"] = cpu_percent
            
            if cpu_percent > self.config["alert_thresholds"]["cpu_usage_max"]:
                health_data["issues"].append(f"High CPU usage: {cpu_percent:.1f}%")
                health_data["status"] = "warning"
            
            # メモリ使用率チェック
            memory = psutil.virtual_memory()
            memory_percent = memory.percent
            health_data["metrics"]["memory_usage"] = memory_percent
            health_data["metrics"]["memory_available_gb"] = memory.available / (1024**3)
            
            if memory_percent > self.config["alert_thresholds"]["memory_usage_max"]:
                health_data["issues"].append(f"High memory usage: {memory_percent:.1f}%")
                health_data["status"] = "warning"
            
            # ディスク使用率チェック
            disk = psutil.disk_usage('/')
            disk_percent = (disk.used / disk.total) * 100
            health_data["metrics"]["disk_usage"] = disk_percent
            health_data["metrics"]["disk_free_gb"] = disk.free / (1024**3)
            
            if disk_percent > self.config["alert_thresholds"]["disk_usage_max"]:
                health_data["issues"].append(f"High disk usage: {disk_percent:.1f}%")
                health_data["status"] = "warning"
            
            # プロセス情報
            try:
                current_process = psutil.Process()
                health_data["metrics"]["process_memory_mb"] = current_process.memory_info().rss / (1024**2)
                health_data["metrics"]["process_cpu_percent"] = current_process.cpu_percent()
            except:
                pass
            
        except Exception as e:
            health_data["status"] = "error"
            health_data["issues"].append(f"Health check error: {str(e)}")
        
        return health_data
    
    def check_endpoints(self):
        """エンドポイントのヘルスチェック"""
        endpoint_results = []
        
        for endpoint in self.config["endpoints_to_monitor"]:
            result = {
                "endpoint": endpoint,
                "status": "unknown",
                "response_time": None,
                "error": None,
                "timestamp": datetime.now().isoformat()
            }
            
            try:
                start_time = time.time()
                response = requests.get(endpoint, timeout=10)
                response_time = time.time() - start_time
                
                result["response_time"] = response_time
                result["status_code"] = response.status_code
                
                if response.status_code == 200:
                    result["status"] = "healthy"
                    if response_time > self.config["alert_thresholds"]["response_time_max"]:
                        result["status"] = "slow"
                        result["warning"] = f"Slow response: {response_time:.2f}s"
                else:
                    result["status"] = "error"
                    result["error"] = f"HTTP {response.status_code}"
                    
            except requests.exceptions.Timeout:
                result["status"] = "timeout"
                result["error"] = "Request timeout"
            except requests.exceptions.ConnectionError:
                result["status"] = "unreachable"
                result["error"] = "Connection failed"
            except Exception as e:
                result["status"] = "error"
                result["error"] = str(e)
            
            endpoint_results.append(result)
        
        return endpoint_results
    
    def check_files(self):
        """重要ファイルの存在チェック"""
        file_results = []
        
        for file_path in self.config["files_to_monitor"]:
            result = {
                "file": file_path,
                "exists": False,
                "size_mb": None,
                "modified": None,
                "status": "missing"
            }
            
            try:
                if os.path.exists(file_path):
                    result["exists"] = True
                    result["status"] = "ok"
                    
                    stat = os.stat(file_path)
                    result["size_mb"] = stat.st_size / (1024**2)
                    result["modified"] = datetime.fromtimestamp(stat.st_mtime).isoformat()
                else:
                    result["status"] = "missing"
                    
            except Exception as e:
                result["status"] = "error"
                result["error"] = str(e)
            
            file_results.append(result)
        
        return file_results
    
    def save_health_log(self, health_data):
        """ヘルスログの保存"""
        try:
            # 既存ログの読み込み
            if os.path.exists(self.health_log_file):
                with open(self.health_log_file, 'r', encoding='utf-8') as f:
                    logs = json.load(f)
            else:
                logs = []
            
            # 新しいログを追加
            logs.append(health_data)
            
            # 最新1000件のみ保持
            if len(logs) > 1000:
                logs = logs[-1000:]
            
            # ファイルに保存
            with open(self.health_log_file, 'w', encoding='utf-8') as f:
                json.dump(logs, f, ensure_ascii=False, indent=2)
                
            return True
        except Exception as e:
            print(f"Health log save error: {e}")
            return False
    
    def check_for_alerts(self, health_data):
        """アラート条件のチェック"""
        alerts = []
        
        # ヘルス状態でのアラート
        if health_data["status"] in ["warning", "error"]:
            for issue in health_data["issues"]:
                alerts.append({
                    "type": "system_health",
                    "severity": health_data["status"],
                    "message": issue,
                    "timestamp": health_data["timestamp"]
                })
        
        # エラー回数の追跡（簡易版）
        current_hour = datetime.now().strftime("%Y-%m-%d %H")
        if health_data["status"] == "error":
            self.error_counts[current_hour] = self.error_counts.get(current_hour, 0) + 1
            
            if self.error_counts[current_hour] > self.config["alert_thresholds"]["error_count_max"]:
                alerts.append({
                    "type": "error_frequency",
                    "severity": "critical",
                    "message": f"High error frequency: {self.error_counts[current_hour]} errors in current hour",
                    "timestamp": health_data["timestamp"]
                })
        
        # 古い時間のエラーカウントをクリーンアップ
        cutoff_time = datetime.now() - timedelta(hours=24)
        cutoff_str = cutoff_time.strftime("%Y-%m-%d %H")
        self.error_counts = {k: v for k, v in self.error_counts.items() if k >= cutoff_str}
        
        return alerts
    
    def send_alerts(self, alerts):
        """アラートの送信"""
        if not alerts:
            return
        
        for alert in alerts:
            message = f"🚨 System Alert: {alert['message']} (Severity: {alert['severity']})"
            
            # コンソール出力
            if self.config["alert_methods"]["console"]:
                print(f"\n{'-'*50}")
                print(message)
                print(f"Time: {alert['timestamp']}")
                print(f"{'-'*50}")
            
            # ファイル出力
            if self.config["alert_methods"]["file"]:
                self.save_alert_log(alert)
    
    def save_alert_log(self, alert):
        """アラートログの保存"""
        try:
            if os.path.exists(self.alert_log_file):
                with open(self.alert_log_file, 'r', encoding='utf-8') as f:
                    logs = json.load(f)
            else:
                logs = []
            
            logs.append(alert)
            
            # 最新500件のみ保持
            if len(logs) > 500:
                logs = logs[-500:]
            
            with open(self.alert_log_file, 'w', encoding='utf-8') as f:
                json.dump(logs, f, ensure_ascii=False, indent=2)
                
        except Exception as e:
            print(f"Alert log save error: {e}")
    
    def run_health_check(self):
        """単発ヘルスチェック実行"""
        print("🔍 System health check starting...")
        
        # システムヘルス取得
        health_data = self.get_system_health()
        
        # エンドポイントチェック
        endpoint_results = self.check_endpoints()
        health_data["endpoints"] = endpoint_results
        
        # ファイルチェック
        file_results = self.check_files()
        health_data["files"] = file_results
        
        # 総合ステータスの決定
        overall_status = health_data["status"]
        for endpoint in endpoint_results:
            if endpoint["status"] in ["error", "timeout", "unreachable"]:
                overall_status = "error"
                health_data["issues"].append(f"Endpoint issue: {endpoint['endpoint']} - {endpoint['status']}")
            elif endpoint["status"] == "slow" and overall_status == "healthy":
                overall_status = "warning"
        
        for file_result in file_results:
            if file_result["status"] in ["missing", "error"]:
                overall_status = "error"
                health_data["issues"].append(f"File issue: {file_result['file']} - {file_result['status']}")
        
        health_data["overall_status"] = overall_status
        
        # ログ保存
        self.save_health_log(health_data)
        
        # アラートチェック
        alerts = self.check_for_alerts(health_data)
        self.send_alerts(alerts)
        
        self.last_health_check = datetime.now()
        
        return health_data
    
    def start_monitoring(self):
        """監視の開始"""
        if self.running:
            print("Monitor is already running")
            return
        
        self.running = True
        print(f"🔍 System monitoring started (interval: {self.config['monitoring_interval']}s)")
        
        def monitoring_loop():
            while self.running:
                try:
                    self.run_health_check()
                    time.sleep(self.config["monitoring_interval"])
                except Exception as e:
                    print(f"Monitor loop error: {e}")
                    time.sleep(60)  # エラー時は1分待機
        
        monitor_thread = threading.Thread(target=monitoring_loop, daemon=True)
        monitor_thread.start()
    
    def stop_monitoring(self):
        """監視の停止"""
        self.running = False
        print("🔍 System monitoring stopped")
    
    def get_monitoring_status(self):
        """監視状況の取得"""
        return {
            "running": self.running,
            "last_check": self.last_health_check.isoformat() if self.last_health_check else None,
            "config": {
                "interval": self.config["monitoring_interval"],
                "endpoints_count": len(self.config["endpoints_to_monitor"]),
                "files_count": len(self.config["files_to_monitor"]),
                "alert_methods": self.config["alert_methods"]
            }
        }
    
    def get_health_history(self, hours=24):
        """ヘルス履歴の取得"""
        try:
            if not os.path.exists(self.health_log_file):
                return []
            
            with open(self.health_log_file, 'r', encoding='utf-8') as f:
                logs = json.load(f)
            
            # 指定時間内のログのみフィルタ
            cutoff_time = datetime.now() - timedelta(hours=hours)
            filtered_logs = []
            
            for log in logs:
                log_time = datetime.fromisoformat(log["timestamp"])
                if log_time >= cutoff_time:
                    filtered_logs.append(log)
            
            return filtered_logs
        except Exception as e:
            print(f"Health history error: {e}")
            return []
    
    def get_alert_history(self, hours=24):
        """アラート履歴の取得"""
        try:
            if not os.path.exists(self.alert_log_file):
                return []
            
            with open(self.alert_log_file, 'r', encoding='utf-8') as f:
                logs = json.load(f)
            
            # 指定時間内のアラートのみフィルタ
            cutoff_time = datetime.now() - timedelta(hours=hours)
            filtered_alerts = []
            
            for alert in logs:
                alert_time = datetime.fromisoformat(alert["timestamp"])
                if alert_time >= cutoff_time:
                    filtered_alerts.append(alert)
            
            return filtered_alerts
        except Exception as e:
            print(f"Alert history error: {e}")
            return []

if __name__ == "__main__":
    # テスト実行
    print("=== System Monitor テスト ===")
    
    monitor = SystemMonitor()
    
    # 単発ヘルスチェック
    print("\n単発ヘルスチェック実行...")
    health = monitor.run_health_check()
    print(f"Overall Status: {health['overall_status']}")
    print(f"Issues: {len(health['issues'])}")
    
    # 監視状況確認
    status = monitor.get_monitoring_status()
    print(f"\nMonitoring Status: {status}")
    
    print("\n=== テスト完了 ===")