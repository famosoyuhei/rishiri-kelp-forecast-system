"""
予報精度検証システム - 毎日の予報データ収集
13干場×1-6日先の予報を取得してデータベースに保存
実行: 毎日06:00 JST (cron: 0 6 * * *)
"""

import requests
import json
from datetime import datetime, timedelta
from forecast_accuracy_db import save_forecast_data, init_database
import time

# API設定
API_BASE = "http://localhost:8000"  # 本番環境では適切なURLに変更

def load_target_spots():
    """検証対象13干場を読み込み"""
    try:
        with open('kutsugata_nearby_spots.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data['spots']
    except Exception as e:
        print(f"干場リスト読み込みエラー: {e}")
        return []


def fetch_spot_forecast(lat, lon, days=7):
    """特定干場の予報を取得

    Args:
        lat: 緯度
        lon: 経度
        days: 予報日数（デフォルト7日）

    Returns:
        dict: 予報データ、エラー時はNone
    """
    try:
        url = f"{API_BASE}/api/forecast?lat={lat}&lon={lon}&days={days}"
        response = requests.get(url, timeout=30)

        if response.status_code == 200:
            return response.json()
        else:
            print(f"予報取得失敗 ({lat}, {lon}): HTTP {response.status_code}")
            return None

    except Exception as e:
        print(f"予報取得エラー ({lat}, {lon}): {e}")
        return None


def extract_daily_summary(day_forecast):
    """日別予報データから必要な統計値を抽出

    Args:
        day_forecast: 日別予報データ

    Returns:
        dict: 統計値（最高/最低気温、湿度、風速、降水量等）
    """
    hourly_data = day_forecast.get('hourly', [])

    if not hourly_data:
        return None

    # 温度統計
    temps = [h['temperature'] for h in hourly_data if h.get('temperature') is not None]
    temp_max = max(temps) if temps else None
    temp_min = min(temps) if temps else None
    temp_avg = sum(temps) / len(temps) if temps else None

    # 湿度統計
    humidities = [h['humidity'] for h in hourly_data if h.get('humidity') is not None]
    humidity_min = min(humidities) if humidities else None
    humidity_avg = sum(humidities) / len(humidities) if humidities else None

    # 風速統計
    wind_speeds = [h['wind_speed'] for h in hourly_data if h.get('wind_speed') is not None]
    wind_speed_avg = sum(wind_speeds) / len(wind_speeds) if wind_speeds else None
    wind_speed_max = max(wind_speeds) if wind_speeds else None

    # 降水量（日合計）
    precipitation = day_forecast.get('total_precipitation', 0.0)

    # 日照時間（推定：雲量から計算）
    cloud_covers = [h.get('cloud_cover', 100) for h in hourly_data]
    # 簡易推定: 雲量20%以下を日照とカウント
    sunshine_hours = sum(1 for c in cloud_covers if c < 20) * (1 / len(cloud_covers) if cloud_covers else 0) * 12

    # 乾燥スコアと可否判定
    drying_score = day_forecast.get('drying_score', 0)
    viability = day_forecast.get('viability', '不明')

    return {
        'temp_max': temp_max,
        'temp_min': temp_min,
        'temp_avg': temp_avg,
        'humidity_min': humidity_min,
        'humidity_avg': humidity_avg,
        'wind_speed_avg': wind_speed_avg,
        'wind_speed_max': wind_speed_max,
        'precipitation': precipitation,
        'sunshine_hours': sunshine_hours,
        'drying_score': drying_score,
        'viability': viability
    }


def collect_daily_forecasts():
    """全13干場の1-6日先予報を収集してデータベースに保存"""
    print(f"=== 予報データ収集開始: {datetime.now()} ===")

    # データベース初期化
    init_database()

    # 対象干場読み込み
    spots = load_target_spots()
    if not spots:
        print("エラー: 干場リストが空です")
        return

    forecast_date = datetime.now().date()
    print(f"予報発表日: {forecast_date}")
    print(f"対象干場数: {len(spots)}")

    success_count = 0
    error_count = 0

    for spot in spots:
        spot_name = spot['name']
        lat = spot['lat']
        lon = spot['lon']

        print(f"\n処理中: {spot_name} ({lat}, {lon})")

        # 予報取得
        forecast_data = fetch_spot_forecast(lat, lon, days=7)

        if not forecast_data or 'daily' not in forecast_data:
            print(f"  ✗ 予報データ取得失敗")
            error_count += 1
            continue

        daily_forecasts = forecast_data['daily']

        # 1日後～6日後の予報を保存
        for days_ahead in range(1, 7):
            if days_ahead >= len(daily_forecasts):
                print(f"  ⚠ {days_ahead}日後の予報データなし")
                continue

            day_forecast = daily_forecasts[days_ahead]
            target_date = (forecast_date + timedelta(days=days_ahead)).isoformat()

            # 統計値抽出
            summary = extract_daily_summary(day_forecast)

            if summary:
                # データベースに保存
                result = save_forecast_data(
                    spot_name=spot_name,
                    forecast_date=forecast_date.isoformat(),
                    target_date=target_date,
                    days_ahead=days_ahead,
                    forecast_data=summary
                )

                if result:
                    print(f"  ✓ {days_ahead}日後予報保存成功 (対象日: {target_date})")
                    success_count += 1
                else:
                    print(f"  ✗ {days_ahead}日後予報保存失敗")
                    error_count += 1
            else:
                print(f"  ✗ {days_ahead}日後の統計値抽出失敗")
                error_count += 1

        # API負荷軽減のため短時間待機
        time.sleep(1)

    print(f"\n=== 予報データ収集完了 ===")
    print(f"成功: {success_count}件")
    print(f"失敗: {error_count}件")
    print(f"完了時刻: {datetime.now()}")


if __name__ == "__main__":
    collect_daily_forecasts()
