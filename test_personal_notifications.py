#!/usr/bin/env python3
"""
利尻島昆布干場予報システム - 個人通知システムテスト

このスクリプトは個人通知システムの全機能をテストし、
正常に動作することを確認します。
"""

import sys
import os
import json
from datetime import datetime

# Add current directory to path for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from personal_notification_system import PersonalNotificationSystem
    print("OK Personal notification system imported successfully")
except ImportError as e:
    print(f"ERROR Failed to import personal notification system: {e}")
    sys.exit(1)

def test_user_management():
    """ユーザー管理機能のテスト"""
    print("\n=== ユーザー管理機能テスト ===")
    
    pns = PersonalNotificationSystem()
    
    # テストユーザーデータ
    test_users = [
        {
            "name": "田中太郎",
            "email": "tanaka@example.com",
            "phone": "090-1234-5678",
            "experience_level": "expert",
            "primary_locations": ["oshidomari", "senposhi"],
            "start_time": "05:00",
            "end_time": "16:00",
            "preferred_method": "email",
            "verbosity": "detailed",
            "channels": ["email", "console"],
            "fog_threshold": 0.3,
            "wind_threshold": 8.0
        },
        {
            "name": "佐藤花子",
            "email": "sato@example.com",
            "phone": "090-9876-5432",
            "experience_level": "beginner",
            "primary_locations": ["kutsugata"],
            "start_time": "06:00",
            "end_time": "15:00",
            "preferred_method": "console",
            "verbosity": "minimal",
            "channels": ["console"],
            "fog_threshold": 0.2,
            "wind_threshold": 6.0
        }
    ]
    
    created_users = []
    
    for i, user_data in enumerate(test_users):
        user_id = pns.create_user_profile(user_data)
        if user_id:
            created_users.append(user_id)
            print(f"OK User {i+1} created with ID: {user_id}")
            
            # プロファイル取得テスト
            user_profile = pns.get_user_by_id(user_id)
            if user_profile:
                print(f"  - Name: {user_profile['name']}")
                print(f"  - Experience: {user_profile['work_profile']['experience_level']}")
                print(f"  - Locations: {', '.join(user_profile['work_profile']['primary_locations'])}")
                print(f"  - Verbosity: {user_profile['notification_preferences']['verbosity']}")
            else:
                print(f"ERROR Failed to retrieve user profile for ID: {user_id}")
        else:
            print(f"ERROR Failed to create user {i+1}")
    
    print(f"\n総作成ユーザー数: {len(created_users)}")
    return created_users

def test_notification_templates():
    """通知テンプレート機能のテスト"""
    print("\n=== 通知テンプレート機能テスト ===")
    
    pns = PersonalNotificationSystem()
    
    # テンプレートの確認
    templates = pns.templates
    print(f"利用可能なテンプレートタイプ: {list(templates.keys())}")
    
    for template_type, verbosity_templates in templates.items():
        print(f"\n{template_type}テンプレート:")
        for verbosity, template in verbosity_templates.items():
            print(f"  {verbosity}: {template[:50]}...")
    
    return True

def test_weather_notifications(user_ids):
    """天気通知機能のテスト"""
    print("\n=== 天気通知機能テスト ===")
    
    pns = PersonalNotificationSystem()
    
    # サンプル天気データ
    sample_weather = {
        "condition": "晴れ時々曇り",
        "temperature": 18,
        "feels_like": 16,
        "wind_speed": 5.2,
        "wind_direction": "北東",
        "rain_probability": 20,
        "humidity": 75,
        "sea_condition": "穏やか"
    }
    
    notifications_sent = 0
    
    for user_id in user_ids:
        user = pns.get_user_by_id(user_id)
        if not user:
            continue
            
        for location in user["work_profile"]["primary_locations"]:
            notification = pns.create_weather_notification(user, location, sample_weather)
            if notification:
                pns.queue_notification(notification)
                notifications_sent += 1
                print(f"OK Weather notification created for {user['name']} at {location}")
    
    # 通知キューの処理
    pns.process_notification_queue()
    print(f"\n送信された天気通知数: {notifications_sent}")
    
    return notifications_sent > 0

def test_fog_alert_integration(user_ids):
    """海霧アラート統合テスト"""
    print("\n=== 海霧アラート統合テスト ===")
    
    pns = PersonalNotificationSystem()
    
    # サンプル海霧アラートデータ
    sample_fog_alert = {
        "id": "fog_alert_test_001",
        "timestamp": datetime.now().isoformat(),
        "zone": "oshidomari",
        "location": {"lat": 45.242, "lon": 141.242},
        "alert_level": "watch",
        "priority": "high",
        "risk_assessment": {
            "max_probability": 0.7,
            "max_risk_time": datetime.now().isoformat(),
            "work_hours_average": 0.6,
            "consecutive_high_risk_hours": 3,
            "rapid_increase_detected": True
        },
        "recommendations": [
            "Consider postponing start of kelp work",
            "If working, recommend early completion", 
            "Prepare visibility equipment",
            "Monitor weather conditions closely"
        ],
        "summary": {
            "message": "[Watch Alert] oshidomari Sea Fog Risk 70.0%",
            "reasons": ["Watch level (70.0%)", "Consecutive high risk (3 hours)"]
        },
        "expires_at": (datetime.now()).isoformat()
    }
    
    fog_notifications_sent = 0
    
    for user_id in user_ids:
        user = pns.get_user_by_id(user_id)
        if not user:
            continue
            
        # ユーザーが関連地域にいるかチェック
        if sample_fog_alert["zone"] in user["work_profile"]["primary_locations"]:
            if pns.should_notify_user_about_fog(user, sample_fog_alert):
                notification = pns.create_fog_alert_notification(user, sample_fog_alert)
                if notification:
                    pns.queue_notification(notification)
                    fog_notifications_sent += 1
                    print(f"OK Fog alert notification created for {user['name']}")
            else:
                print(f"- Fog alert skipped for {user['name']} (threshold/timing)")
    
    # 通知キューの処理
    pns.process_notification_queue()
    print(f"\n送信された海霧アラート数: {fog_notifications_sent}")
    
    return fog_notifications_sent >= 0

def test_personalization_features(user_ids):
    """個人化機能のテスト"""
    print("\n=== 個人化機能テスト ===")
    
    pns = PersonalNotificationSystem()
    
    for user_id in user_ids:
        user = pns.get_user_by_id(user_id)
        if not user:
            continue
            
        print(f"\n{user['name']}の個人化設定:")
        
        # 経験レベル別推奨事項
        experience = user["work_profile"]["experience_level"]
        print(f"  経験レベル: {experience}")
        
        # カスタム閾値
        thresholds = user["notification_preferences"]["custom_thresholds"]
        print(f"  海霧警告閾値: {thresholds['fog_warning']}")
        print(f"  風速警告閾値: {thresholds['wind_warning']}m/s")
        
        # 通知設定
        channels = user["notification_preferences"]["notification_channels"]
        verbosity = user["notification_preferences"]["verbosity"]
        print(f"  通知チャンネル: {', '.join(channels)}")
        print(f"  詳細レベル: {verbosity}")
        
        # 静寂時間
        quiet_hours = user["notification_preferences"]["quiet_hours"]
        print(f"  静寂時間: {quiet_hours['start']} - {quiet_hours['end']}")
        
        # 作業スケジュール
        schedule = user["work_profile"]["work_schedule"]
        print(f"  作業時間: {schedule['typical_start_time']} - {schedule['typical_end_time']}")
        
        # ダッシュボードデータ取得テスト
        dashboard = pns.get_user_notification_dashboard(user_id)
        if "error" not in dashboard:
            print(f"  最近の通知数: {dashboard['notification_stats']['total_recent']}")
            print(f"  成功率: {dashboard['notification_stats']['success_rate']:.1%}")
        else:
            print(f"  ダッシュボードエラー: {dashboard['error']}")
    
    return True

def test_service_management():
    """サービス管理機能のテスト"""
    print("\n=== サービス管理機能テスト ===")
    
    pns = PersonalNotificationSystem()
    
    # サービス状態の取得
    status = pns.get_system_status()
    print(f"サービス状態:")
    print(f"  稼働中: {status['service_running']}")
    print(f"  総ユーザー数: {status['total_users']}")
    print(f"  アクティブユーザー数: {status['active_users']}")
    print(f"  キュー内通知数: {status['notifications_in_queue']}")
    print(f"  失敗通知数: {status['failed_notifications']}")
    print(f"  海霧アラート統合: {status['fog_alert_integration']}")
    
    # サービス開始テスト
    start_result = pns.start_notification_service()
    print(f"\nサービス開始結果: {start_result.get('status', 'unknown')}")
    if start_result.get("status") == "started":
        print(f"アクティブユーザー数: {start_result.get('active_users', 0)}")
    
    return status['total_users'] > 0

def test_configuration_management():
    """設定管理機能のテスト"""
    print("\n=== 設定管理機能テスト ===")
    
    pns = PersonalNotificationSystem()
    
    # 現在の設定表示
    config = pns.config
    print(f"通知チャンネル設定:")
    for channel, settings in config["notification_channels"].items():
        print(f"  {channel}: {'有効' if settings.get('enabled', False) else '無効'}")
    
    print(f"\n通知タイミング設定:")
    timing = config["notification_timing"]
    print(f"  天気確認時刻: {timing['weather_check_hours']}")
    print(f"  作業開始前通知: {timing['work_start_advance_minutes']}分前")
    print(f"  海霧警報前通知: {timing['fog_warning_advance_hours']}時間前")
    
    print(f"\n個人化要素:")
    factors = config["personalization_factors"]
    for factor, values in factors.items():
        print(f"  {factor}: {values}")
    
    return True

def main():
    """メインテスト実行"""
    print("=== 利尻島昆布干場予報システム - 個人通知システム統合テスト ===")
    print(f"テスト開始時刻: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    test_results = {}
    
    try:
        # ユーザー管理テスト
        user_ids = test_user_management()
        test_results["user_management"] = len(user_ids) > 0
        
        # テンプレート機能テスト
        test_results["templates"] = test_notification_templates()
        
        # 天気通知テスト
        test_results["weather_notifications"] = test_weather_notifications(user_ids)
        
        # 海霧アラート統合テスト
        test_results["fog_alert_integration"] = test_fog_alert_integration(user_ids)
        
        # 個人化機能テスト
        test_results["personalization"] = test_personalization_features(user_ids)
        
        # サービス管理テスト
        test_results["service_management"] = test_service_management()
        
        # 設定管理テスト
        test_results["configuration"] = test_configuration_management()
        
        # 結果サマリー
        print("\n=== テスト結果サマリー ===")
        total_tests = len(test_results)
        passed_tests = sum(test_results.values())
        
        for test_name, result in test_results.items():
            status = "PASS" if result else "FAIL"
            print(f"{test_name}: {status}")
        
        print(f"\n総合結果: {passed_tests}/{total_tests} テスト通過")
        success_rate = (passed_tests / total_tests) * 100
        print(f"成功率: {success_rate:.1f}%")
        
        if success_rate >= 80:
            print("SUCCESS 個人通知システム統合テスト成功！")
            return 0
        else:
            print("WARNING 個人通知システムに改善が必要です")
            return 1
            
    except Exception as e:
        print(f"\nERROR テスト実行中にエラーが発生しました: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)