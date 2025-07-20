import os
import json
import shutil
import zipfile
import threading
import schedule
import time
from datetime import datetime, timedelta
from pathlib import Path

class BackupSystem:
    """利尻島昆布干場予報システム データバックアップ・復元システム"""
    
    def __init__(self):
        self.backup_config_file = "backup_config.json"
        self.backup_base_dir = "backups"
        
        self.default_config = {
            "auto_backup_enabled": True,
            "backup_interval_hours": 24,  # 24時間間隔
            "backup_time": "02:00",       # 午前2時
            "max_backups": 30,            # 最大30個のバックアップを保持
            "compress_backups": True,     # バックアップを圧縮
            "backup_targets": {
                "critical_files": [
                    "hoshiba_spots.csv",
                    "hoshiba_records.csv", 
                    "weather_labeled_dataset.csv",
                    "model.pkl",
                    "improved_model.pkl"
                ],
                "config_files": [
                    "fishing_season_config.json",
                    "notification_config.json",
                    "system_monitor_config.json",
                    "backup_config.json"
                ],
                "log_files": [
                    "notification_system.log",
                    "system_health.json",
                    "system_alerts.json",
                    "notification_log.json"
                ]
            },
            "notification_on_backup": True,
            "notification_on_error": True,
            "cloud_backup": {
                "enabled": False,
                "provider": "local",  # future: aws_s3, google_drive, etc
                "settings": {}
            }
        }
        
        self.load_config()
        self.ensure_backup_directory()
        self.running = False
        
    def load_config(self):
        """設定ファイルの読み込み"""
        try:
            if os.path.exists(self.backup_config_file):
                with open(self.backup_config_file, 'r', encoding='utf-8') as f:
                    loaded_config = json.load(f)
                
                self.config = self.default_config.copy()
                self._merge_config(self.config, loaded_config)
            else:
                self.config = self.default_config.copy()
                self.save_config()
        except Exception as e:
            print(f"Backup config load error: {e}")
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
            with open(self.backup_config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"Backup config save error: {e}")
            return False
    
    def ensure_backup_directory(self):
        """バックアップディレクトリの作成"""
        try:
            os.makedirs(self.backup_base_dir, exist_ok=True)
            return True
        except Exception as e:
            print(f"Backup directory creation error: {e}")
            return False
    
    def create_backup(self, backup_name=None, include_logs=True):
        """バックアップの作成"""
        try:
            # バックアップ名の生成
            if not backup_name:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_name = f"konbu_backup_{timestamp}"
            
            backup_dir = os.path.join(self.backup_base_dir, backup_name)
            
            # バックアップディレクトリの作成
            os.makedirs(backup_dir, exist_ok=True)
            
            backup_info = {
                "backup_name": backup_name,
                "created_at": datetime.now().isoformat(),
                "backup_type": "manual",
                "files": [],
                "size_mb": 0,
                "status": "in_progress"
            }
            
            total_size = 0
            
            # クリティカルファイルのバックアップ
            critical_dir = os.path.join(backup_dir, "critical")
            os.makedirs(critical_dir, exist_ok=True)
            
            for file_path in self.config["backup_targets"]["critical_files"]:
                if os.path.exists(file_path):
                    dest_path = os.path.join(critical_dir, os.path.basename(file_path))
                    shutil.copy2(file_path, dest_path)
                    
                    file_size = os.path.getsize(dest_path) / (1024**2)  # MB
                    total_size += file_size
                    
                    backup_info["files"].append({
                        "category": "critical",
                        "source": file_path,
                        "size_mb": round(file_size, 2),
                        "backed_up": True
                    })
                else:
                    backup_info["files"].append({
                        "category": "critical",
                        "source": file_path,
                        "size_mb": 0,
                        "backed_up": False,
                        "reason": "file_not_found"
                    })
            
            # 設定ファイルのバックアップ
            config_dir = os.path.join(backup_dir, "config")
            os.makedirs(config_dir, exist_ok=True)
            
            for file_path in self.config["backup_targets"]["config_files"]:
                if os.path.exists(file_path):
                    dest_path = os.path.join(config_dir, os.path.basename(file_path))
                    shutil.copy2(file_path, dest_path)
                    
                    file_size = os.path.getsize(dest_path) / (1024**2)
                    total_size += file_size
                    
                    backup_info["files"].append({
                        "category": "config",
                        "source": file_path,
                        "size_mb": round(file_size, 2),
                        "backed_up": True
                    })
                else:
                    backup_info["files"].append({
                        "category": "config",
                        "source": file_path,
                        "size_mb": 0,
                        "backed_up": False,
                        "reason": "file_not_found"
                    })
            
            # ログファイルのバックアップ（オプション）
            if include_logs:
                log_dir = os.path.join(backup_dir, "logs")
                os.makedirs(log_dir, exist_ok=True)
                
                for file_path in self.config["backup_targets"]["log_files"]:
                    if os.path.exists(file_path):
                        dest_path = os.path.join(log_dir, os.path.basename(file_path))
                        shutil.copy2(file_path, dest_path)
                        
                        file_size = os.path.getsize(dest_path) / (1024**2)
                        total_size += file_size
                        
                        backup_info["files"].append({
                            "category": "logs",
                            "source": file_path,
                            "size_mb": round(file_size, 2),
                            "backed_up": True
                        })
            
            backup_info["size_mb"] = round(total_size, 2)
            
            # バックアップ情報ファイルの保存
            info_path = os.path.join(backup_dir, "backup_info.json")
            with open(info_path, 'w', encoding='utf-8') as f:
                json.dump(backup_info, f, ensure_ascii=False, indent=2)
            
            # 圧縮（オプション）
            final_path = backup_dir
            if self.config["compress_backups"]:
                zip_path = f"{backup_dir}.zip"
                self._create_zip(backup_dir, zip_path)
                shutil.rmtree(backup_dir)  # 元のディレクトリを削除
                final_path = zip_path
                backup_info["compressed"] = True
                backup_info["final_path"] = zip_path
            else:
                backup_info["compressed"] = False
                backup_info["final_path"] = backup_dir
            
            backup_info["status"] = "completed"
            backup_info["completed_at"] = datetime.now().isoformat()
            
            # 古いバックアップの清理
            self._cleanup_old_backups()
            
            return backup_info
            
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "created_at": datetime.now().isoformat()
            }
    
    def _create_zip(self, source_dir, zip_path):
        """ディレクトリのZIP圧縮"""
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk(source_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, source_dir)
                    zipf.write(file_path, arcname)
    
    def _cleanup_old_backups(self):
        """古いバックアップの削除"""
        try:
            if not os.path.exists(self.backup_base_dir):
                return
            
            # バックアップファイル・ディレクトリを取得
            backups = []
            for item in os.listdir(self.backup_base_dir):
                item_path = os.path.join(self.backup_base_dir, item)
                if item.startswith("konbu_backup_"):
                    mtime = os.path.getmtime(item_path)
                    backups.append((item_path, mtime))
            
            # 作成日時でソート（古い順）
            backups.sort(key=lambda x: x[1])
            
            # 制限を超えた分を削除
            max_backups = self.config["max_backups"]
            if len(backups) > max_backups:
                for backup_path, _ in backups[:-max_backups]:
                    try:
                        if os.path.isdir(backup_path):
                            shutil.rmtree(backup_path)
                        else:
                            os.remove(backup_path)
                        print(f"Old backup removed: {backup_path}")
                    except Exception as e:
                        print(f"Failed to remove old backup {backup_path}: {e}")
                        
        except Exception as e:
            print(f"Cleanup error: {e}")
    
    def list_backups(self):
        """バックアップ一覧の取得"""
        try:
            if not os.path.exists(self.backup_base_dir):
                return []
            
            backups = []
            for item in os.listdir(self.backup_base_dir):
                if item.startswith("konbu_backup_"):
                    item_path = os.path.join(self.backup_base_dir, item)
                    
                    backup_info = {
                        "name": item,
                        "path": item_path,
                        "is_compressed": item.endswith(".zip"),
                        "created_at": datetime.fromtimestamp(os.path.getmtime(item_path)).isoformat()
                    }
                    
                    # サイズ情報
                    if os.path.isdir(item_path):
                        total_size = 0
                        for root, dirs, files in os.walk(item_path):
                            for file in files:
                                total_size += os.path.getsize(os.path.join(root, file))
                        backup_info["size_mb"] = round(total_size / (1024**2), 2)
                    else:
                        backup_info["size_mb"] = round(os.path.getsize(item_path) / (1024**2), 2)
                    
                    # バックアップ情報ファイルから詳細取得
                    if backup_info["is_compressed"]:
                        # ZIPファイルから情報を取得（簡易版）
                        pass
                    else:
                        info_file = os.path.join(item_path, "backup_info.json")
                        if os.path.exists(info_file):
                            try:
                                with open(info_file, 'r', encoding='utf-8') as f:
                                    detailed_info = json.load(f)
                                backup_info.update(detailed_info)
                            except:
                                pass
                    
                    backups.append(backup_info)
            
            # 作成日時でソート（新しい順）
            backups.sort(key=lambda x: x["created_at"], reverse=True)
            return backups
            
        except Exception as e:
            print(f"List backups error: {e}")
            return []
    
    def restore_backup(self, backup_name, target_files=None, confirm_callback=None):
        """バックアップの復元"""
        try:
            backup_path = os.path.join(self.backup_base_dir, backup_name)
            
            if not os.path.exists(backup_path):
                return {
                    "status": "error",
                    "error": f"Backup not found: {backup_name}"
                }
            
            restore_info = {
                "backup_name": backup_name,
                "started_at": datetime.now().isoformat(),
                "restored_files": [],
                "errors": [],
                "status": "in_progress"
            }
            
            # 圧縮されたバックアップの場合、一時展開
            temp_dir = None
            if backup_name.endswith(".zip"):
                temp_dir = f"temp_restore_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                with zipfile.ZipFile(backup_path, 'r') as zipf:
                    zipf.extractall(temp_dir)
                source_dir = temp_dir
            else:
                source_dir = backup_path
            
            # 復元対象ファイルの決定
            if target_files is None:
                # 全ファイル復元
                categories = ["critical", "config", "logs"]
            else:
                categories = target_files
            
            # 各カテゴリのファイルを復元
            for category in categories:
                category_dir = os.path.join(source_dir, category)
                if not os.path.exists(category_dir):
                    continue
                
                for file_name in os.listdir(category_dir):
                    source_file = os.path.join(category_dir, file_name)
                    target_file = file_name  # 現在のディレクトリに復元
                    
                    try:
                        # 既存ファイルのバックアップ作成
                        if os.path.exists(target_file):
                            backup_suffix = datetime.now().strftime("_%Y%m%d_%H%M%S.backup")
                            backup_file = f"{target_file}{backup_suffix}"
                            shutil.copy2(target_file, backup_file)
                            restore_info["restored_files"].append({
                                "file": target_file,
                                "category": category,
                                "action": "replaced",
                                "backup_created": backup_file
                            })
                        else:
                            restore_info["restored_files"].append({
                                "file": target_file,
                                "category": category,
                                "action": "created"
                            })
                        
                        # ファイル復元
                        shutil.copy2(source_file, target_file)
                        
                    except Exception as e:
                        restore_info["errors"].append({
                            "file": target_file,
                            "error": str(e)
                        })
            
            # 一時ディレクトリの削除
            if temp_dir and os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
            
            restore_info["status"] = "completed" if not restore_info["errors"] else "completed_with_errors"
            restore_info["completed_at"] = datetime.now().isoformat()
            
            return restore_info
            
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "started_at": datetime.now().isoformat()
            }
    
    def delete_backup(self, backup_name):
        """バックアップの削除"""
        try:
            backup_path = os.path.join(self.backup_base_dir, backup_name)
            
            if not os.path.exists(backup_path):
                return False
            
            if os.path.isdir(backup_path):
                shutil.rmtree(backup_path)
            else:
                os.remove(backup_path)
            
            return True
            
        except Exception as e:
            print(f"Delete backup error: {e}")
            return False
    
    def auto_backup_job(self):
        """自動バックアップジョブ"""
        try:
            backup_info = self.create_backup(backup_name=None, include_logs=True)
            backup_info["backup_type"] = "automatic"
            
            if backup_info["status"] == "completed":
                print(f"Auto backup completed: {backup_info['backup_name']}")
                
                # 通知（オプション）
                if self.config["notification_on_backup"]:
                    self._send_backup_notification("success", backup_info)
            else:
                print(f"Auto backup failed: {backup_info.get('error', 'Unknown error')}")
                
                if self.config["notification_on_error"]:
                    self._send_backup_notification("error", backup_info)
                    
        except Exception as e:
            print(f"Auto backup job error: {e}")
            if self.config["notification_on_error"]:
                self._send_backup_notification("error", {"error": str(e)})
    
    def _send_backup_notification(self, status, backup_info):
        """バックアップ通知の送信（簡易版）"""
        if status == "success":
            message = f"✓ 自動バックアップ完了: {backup_info['backup_name']} ({backup_info['size_mb']}MB)"
        else:
            message = f"✗ バックアップエラー: {backup_info.get('error', 'Unknown error')}"
        
        print(f"Backup Notification: {message}")
    
    def start_auto_backup(self):
        """自動バックアップの開始"""
        if self.running:
            return False
        
        if not self.config["auto_backup_enabled"]:
            return False
        
        # スケジュール設定
        schedule.clear()
        backup_time = self.config["backup_time"]
        schedule.every().day.at(backup_time).do(self.auto_backup_job)
        
        self.running = True
        print(f"Auto backup started (daily at {backup_time})")
        
        def scheduler_loop():
            while self.running:
                schedule.run_pending()
                time.sleep(60)
        
        scheduler_thread = threading.Thread(target=scheduler_loop, daemon=True)
        scheduler_thread.start()
        
        return True
    
    def stop_auto_backup(self):
        """自動バックアップの停止"""
        self.running = False
        schedule.clear()
        print("Auto backup stopped")
    
    def get_backup_status(self):
        """バックアップシステム状況の取得"""
        backups = self.list_backups()
        total_size = sum(backup["size_mb"] for backup in backups)
        
        return {
            "auto_backup_running": self.running,
            "auto_backup_enabled": self.config["auto_backup_enabled"],
            "backup_time": self.config["backup_time"],
            "backup_count": len(backups),
            "total_size_mb": round(total_size, 2),
            "max_backups": self.config["max_backups"],
            "compress_enabled": self.config["compress_backups"],
            "last_backup": backups[0] if backups else None
        }

if __name__ == "__main__":
    # テスト実行
    print("=== Backup System テスト ===")
    
    backup_system = BackupSystem()
    
    # バックアップ作成テスト
    print("\nバックアップ作成テスト...")
    backup_info = backup_system.create_backup("test_backup")
    print(f"Status: {backup_info['status']}")
    if backup_info['status'] == 'completed':
        print(f"Files: {len(backup_info['files'])}")
        print(f"Size: {backup_info['size_mb']}MB")
    
    # バックアップ一覧
    print("\nバックアップ一覧:")
    backups = backup_system.list_backups()
    for backup in backups:
        print(f"  - {backup['name']} ({backup['size_mb']}MB)")
    
    # システム状況
    status = backup_system.get_backup_status()
    print(f"\nBackup Status: {status}")
    
    print("\n=== テスト完了 ===")