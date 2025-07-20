from datetime import datetime, timedelta
import json
import os

class FishingSeasonManager:
    """利尻島昆布漁期スケジュール管理システム"""
    
    def __init__(self):
        self.season_config_file = "fishing_season_config.json"
        self.default_config = {
            "current_year": datetime.now().year,
            "season_start": "06-01",  # 6月1日（デフォルト）
            "season_end": "09-30",    # 9月30日
            "work_start_time": "04:00",
            "work_end_time": "16:00",
            "rest_days": [],  # 休漁日
            "weather_threshold": {
                "wind_max": 12.0,      # 最大風速制限
                "rain_max": 5.0,       # 最大降水量制限
                "visibility_min": 1000  # 最小視程制限
            },
            "notifications": {
                "daily_forecast_time": "16:00",  # 午後4時予報通知
                "weather_alert": True,
                "season_reminder": True,
                "enabled_until_season": True  # 漁期開始まで通知有効
            },
            "season_start_setting": {
                "auto_prompt_enabled": True,  # 5/31自動プロンプト
                "prompt_date": "05-31",      # 5月31日
                "prompt_time": "16:00",      # 午後4時
                "last_prompted_year": None,  # 最後にプロンプトした年
                "user_selected_start": None, # ユーザー選択開始日
                "notification_suspended": False  # 通知一時停止状態
            }
        }
        self.load_config()
    
    def load_config(self):
        """設定ファイルの読み込み"""
        try:
            if os.path.exists(self.season_config_file):
                with open(self.season_config_file, 'r', encoding='utf-8') as f:
                    self.config = json.load(f)
                # デフォルト設定で不足分を補完
                for key, value in self.default_config.items():
                    if key not in self.config:
                        self.config[key] = value
            else:
                self.config = self.default_config.copy()
                self.save_config()
        except Exception as e:
            print(f"Config load error: {e}")
            self.config = self.default_config.copy()
    
    def save_config(self):
        """設定ファイルの保存"""
        try:
            with open(self.season_config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Config save error: {e}")
    
    def is_fishing_season(self, date=None):
        """指定日が漁期内かチェック"""
        if date is None:
            date = datetime.now()
        elif isinstance(date, str):
            date = datetime.strptime(date, "%Y-%m-%d")
        
        year = date.year
        season_start = datetime.strptime(f"{year}-{self.config['season_start']}", "%Y-%m-%d")
        season_end = datetime.strptime(f"{year}-{self.config['season_end']}", "%Y-%m-%d")
        
        return season_start <= date <= season_end
    
    def get_season_status(self, date=None):
        """現在の漁期状況を取得"""
        if date is None:
            date = datetime.now()
        elif isinstance(date, str):
            date = datetime.strptime(date, "%Y-%m-%d")
        
        year = date.year
        season_start = datetime.strptime(f"{year}-{self.config['season_start']}", "%Y-%m-%d")
        season_end = datetime.strptime(f"{year}-{self.config['season_end']}", "%Y-%m-%d")
        
        if date < season_start:
            days_until_start = (season_start - date).days
            return {
                "status": "pre_season",
                "message": "漁期前",
                "days_until_start": days_until_start,
                "season_start": season_start.strftime("%Y-%m-%d"),
                "season_end": season_end.strftime("%Y-%m-%d")
            }
        elif date > season_end:
            days_since_end = (date - season_end).days
            next_year_start = datetime.strptime(f"{year+1}-{self.config['season_start']}", "%Y-%m-%d")
            days_until_next = (next_year_start - date).days
            return {
                "status": "post_season",
                "message": "漁期終了",
                "days_since_end": days_since_end,
                "days_until_next": days_until_next,
                "next_season_start": next_year_start.strftime("%Y-%m-%d")
            }
        else:
            days_remaining = (season_end - date).days
            total_days = (season_end - season_start).days
            days_elapsed = (date - season_start).days
            progress = (days_elapsed / total_days) * 100
            
            return {
                "status": "in_season",
                "message": "漁期中",
                "days_remaining": days_remaining,
                "days_elapsed": days_elapsed,
                "total_days": total_days,
                "progress": round(progress, 1),
                "season_start": season_start.strftime("%Y-%m-%d"),
                "season_end": season_end.strftime("%Y-%m-%d")
            }
    
    def is_rest_day(self, date=None):
        """指定日が休漁日かチェック"""
        if date is None:
            date = datetime.now()
        elif isinstance(date, str):
            date = datetime.strptime(date, "%Y-%m-%d")
        
        date_str = date.strftime("%m-%d")
        return date_str in self.config['rest_days']
    
    def add_rest_day(self, date):
        """休漁日を追加"""
        if isinstance(date, str):
            date = datetime.strptime(date, "%Y-%m-%d")
        
        date_str = date.strftime("%m-%d")
        if date_str not in self.config['rest_days']:
            self.config['rest_days'].append(date_str)
            self.save_config()
            return True
        return False
    
    def remove_rest_day(self, date):
        """休漁日を削除"""
        if isinstance(date, str):
            date = datetime.strptime(date, "%Y-%m-%d")
        
        date_str = date.strftime("%m-%d")
        if date_str in self.config['rest_days']:
            self.config['rest_days'].remove(date_str)
            self.save_config()
            return True
        return False
    
    def get_work_schedule(self, date=None):
        """指定日の作業スケジュールを取得"""
        if date is None:
            date = datetime.now()
        elif isinstance(date, str):
            date = datetime.strptime(date, "%Y-%m-%d")
        
        season_status = self.get_season_status(date)
        is_rest = self.is_rest_day(date)
        
        # 作業時間の計算
        work_start = datetime.strptime(self.config['work_start_time'], "%H:%M").time()
        work_end = datetime.strptime(self.config['work_end_time'], "%H:%M").time()
        
        schedule = {
            "date": date.strftime("%Y-%m-%d"),
            "day_of_week": date.strftime("%A"),
            "season_status": season_status,
            "is_rest_day": is_rest,
            "work_permitted": season_status["status"] == "in_season" and not is_rest,
            "work_hours": {
                "start": self.config['work_start_time'],
                "end": self.config['work_end_time'],
                "duration": "12時間"
            },
            "schedule": {
                "04:00-10:00": "昆布引き上げ・干場展開（風条件重要）",
                "10:00-10:30": "手直し作業",
                "10:00-16:00": "天日乾燥（日射条件重要）",
                "14:00-16:00": "乾燥昆布回収"
            }
        }
        
        if not schedule["work_permitted"]:
            if season_status["status"] == "pre_season":
                schedule["note"] = f"漁期開始まで {season_status['days_until_start']} 日"
            elif season_status["status"] == "post_season":
                schedule["note"] = f"今期終了。来期開始まで {season_status['days_until_next']} 日"
            elif is_rest:
                schedule["note"] = "休漁日"
        
        return schedule
    
    def get_weekly_schedule(self, start_date=None):
        """1週間のスケジュールを取得"""
        if start_date is None:
            start_date = datetime.now()
        elif isinstance(start_date, str):
            start_date = datetime.strptime(start_date, "%Y-%m-%d")
        
        weekly_schedule = []
        for i in range(7):
            date = start_date + timedelta(days=i)
            daily_schedule = self.get_work_schedule(date)
            weekly_schedule.append(daily_schedule)
        
        return weekly_schedule
    
    def update_season_config(self, new_config):
        """漁期設定を更新"""
        try:
            for key, value in new_config.items():
                if key in self.config:
                    self.config[key] = value
            self.save_config()
            return True
        except Exception as e:
            print(f"Config update error: {e}")
            return False
    
    def get_season_summary(self):
        """漁期の総合サマリーを取得"""
        current_status = self.get_season_status()
        
        return {
            "current_year": self.config["current_year"],
            "season_period": f"{self.config['season_start']} ～ {self.config['season_end']}",
            "work_hours": f"{self.config['work_start_time']} ～ {self.config['work_end_time']}",
            "current_status": current_status,
            "rest_days_count": len(self.config['rest_days']),
            "rest_days": self.config['rest_days'],
            "notifications_enabled": self.config['notifications'],
            "weather_thresholds": self.config['weather_threshold'],
            "season_start_setting": self.config.get('season_start_setting', {})
        }
    
    def check_season_start_prompt_needed(self):
        """5月31日の漁期開始日設定プロンプトが必要かチェック"""
        now = datetime.now()
        current_year = now.year
        
        # 設定確認
        setting = self.config.get('season_start_setting', {})
        if not setting.get('auto_prompt_enabled', True):
            return False
        
        # 今年既にプロンプト済みかチェック
        last_prompted = setting.get('last_prompted_year')
        if last_prompted == current_year:
            return False
        
        # 5月31日の午後4時かチェック
        prompt_date = f"{current_year}-{setting.get('prompt_date', '05-31')}"
        prompt_time = setting.get('prompt_time', '16:00')
        
        try:
            prompt_datetime = datetime.strptime(f"{prompt_date} {prompt_time}", "%Y-%m-%d %H:%M")
            
            # 5月31日午後4時以降で、まだプロンプトしていない場合
            if now >= prompt_datetime and last_prompted != current_year:
                return True
                
        except ValueError as e:
            print(f"Date parsing error: {e}")
            return False
        
        return False
    
    def get_season_start_prompt_data(self):
        """漁期開始日設定プロンプト用のデータを取得"""
        current_year = datetime.now().year
        
        # 選択可能な開始日の範囲（6月1日〜9月30日）
        start_options = []
        start_date = datetime(current_year, 6, 1)
        end_date = datetime(current_year, 9, 30)
        
        current = start_date
        while current <= end_date:
            start_options.append({
                "date": current.strftime("%Y-%m-%d"),
                "display": current.strftime("%m月%d日 (%a)"),
                "month_day": current.strftime("%m-%d")
            })
            current += timedelta(days=1)
        
        return {
            "current_year": current_year,
            "default_start": f"{current_year}-06-01",
            "current_setting": self.config.get('season_start', '06-01'),
            "user_selected": self.config.get('season_start_setting', {}).get('user_selected_start'),
            "options": start_options[:30],  # 最初の30日分を提供
            "recommended_dates": [
                {"date": f"{current_year}-06-01", "reason": "例年通りの開始日"},
                {"date": f"{current_year}-06-05", "reason": "準備期間を考慮"},
                {"date": f"{current_year}-06-10", "reason": "気象条件の安定を待つ"},
                {"date": f"{current_year}-06-15", "reason": "遅めの安全な開始"}
            ]
        }
    
    def set_user_selected_season_start(self, selected_date):
        """ユーザーが選択した漁期開始日を設定"""
        try:
            # 日付形式の検証
            if isinstance(selected_date, str):
                if len(selected_date) == 10:  # YYYY-MM-DD
                    parsed_date = datetime.strptime(selected_date, "%Y-%m-%d")
                    month_day = parsed_date.strftime("%m-%d")
                elif len(selected_date) == 5:  # MM-DD
                    month_day = selected_date
                    parsed_date = datetime.strptime(f"{datetime.now().year}-{month_day}", "%Y-%m-%d")
                else:
                    return {"status": "error", "message": "無効な日付形式です"}
            else:
                return {"status": "error", "message": "日付は文字列で指定してください"}
            
            # 有効な範囲内かチェック（6月1日〜9月30日）
            month = parsed_date.month
            day = parsed_date.day
            
            if not ((month == 6 and day >= 1) or (month in [7, 8]) or (month == 9 and day <= 30)):
                return {"status": "error", "message": "漁期開始日は6月1日〜9月30日の範囲で選択してください"}
            
            # 設定を更新
            current_year = datetime.now().year
            self.config['season_start'] = month_day
            if 'season_start_setting' not in self.config:
                self.config['season_start_setting'] = {}
            
            self.config['season_start_setting']['user_selected_start'] = selected_date
            self.config['season_start_setting']['last_prompted_year'] = current_year
            
            # 通知の一時停止を解除（開始日が設定されたため）
            self.config['season_start_setting']['notification_suspended'] = False
            
            self.save_config()
            
            return {
                "status": "success",
                "message": f"漁期開始日を{parsed_date.strftime('%m月%d日')}に設定しました",
                "selected_date": selected_date,
                "season_start": month_day,
                "notification_resumed": True
            }
            
        except ValueError as e:
            return {"status": "error", "message": f"日付解析エラー: {str(e)}"}
        except Exception as e:
            return {"status": "error", "message": f"設定エラー: {str(e)}"}
    
    def suspend_notifications_until_season(self):
        """漁期開始まで通知を一時停止"""
        if 'season_start_setting' not in self.config:
            self.config['season_start_setting'] = {}
        
        self.config['season_start_setting']['notification_suspended'] = True
        self.config['season_start_setting']['last_prompted_year'] = datetime.now().year
        self.save_config()
        
        return {
            "status": "success",
            "message": "漁期開始まで通知を一時停止しました",
            "suspended_until": f"{datetime.now().year}-{self.config['season_start']}"
        }
    
    def should_send_notifications(self):
        """現在通知を送信すべきかどうかを判定"""
        # 通知一時停止中かチェック
        setting = self.config.get('season_start_setting', {})
        if setting.get('notification_suspended', False):
            # 漁期開始日になったら自動的に通知再開
            if self.is_fishing_season():
                setting['notification_suspended'] = False
                self.save_config()
                return True
            else:
                return False
        
        return True
    
    def get_notification_status(self):
        """通知状況の詳細を取得"""
        setting = self.config.get('season_start_setting', {})
        season_status = self.get_season_status()
        
        return {
            "notifications_enabled": self.config.get('notifications', {}).get('weather_alert', True),
            "suspended_until_season": setting.get('notification_suspended', False),
            "season_status": season_status['status'],
            "suspension_reason": "ユーザーが漁期開始まで通知停止を選択" if setting.get('notification_suspended') else None,
            "resume_date": f"{datetime.now().year}-{self.config['season_start']}" if setting.get('notification_suspended') else None,
            "auto_prompt_enabled": setting.get('auto_prompt_enabled', True),
            "last_prompted_year": setting.get('last_prompted_year')
        }
    
    def reset_season_start_prompt(self):
        """漁期開始プロンプトの設定をリセット（テスト用）"""
        if 'season_start_setting' not in self.config:
            self.config['season_start_setting'] = {}
        
        self.config['season_start_setting']['last_prompted_year'] = None
        self.config['season_start_setting']['notification_suspended'] = False
        self.save_config()
        
        return {"status": "success", "message": "漁期開始プロンプト設定をリセットしました"}

if __name__ == "__main__":
    # テスト実行
    print("=== 利尻島昆布漁期管理システム テスト ===")
    
    fsm = FishingSeasonManager()
    
    # 現在の漁期状況
    status = fsm.get_season_status()
    print(f"\n現在の漁期状況: {status}")
    
    # 本日のスケジュール
    today_schedule = fsm.get_work_schedule()
    print(f"\n本日のスケジュール:")
    print(f"日付: {today_schedule['date']} ({today_schedule['day_of_week']})")
    print(f"作業可能: {today_schedule['work_permitted']}")
    print(f"作業時間: {today_schedule['work_hours']['start']} ～ {today_schedule['work_hours']['end']}")
    
    # 今週のスケジュール
    weekly = fsm.get_weekly_schedule()
    print(f"\n今週のスケジュール:")
    for day in weekly:
        status_text = "○" if day['work_permitted'] else "×"
        print(f"{day['date']} ({day['day_of_week'][:3]}): {status_text}")
    
    print("\n=== テスト完了 ===")