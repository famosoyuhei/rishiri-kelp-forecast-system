"""
予報精度検証システム - アメダス実測データ取得
気象庁APIから沓形アメダス（ID: 11151）の当日データを取得
実行: 毎日22:00 JST (cron: 0 22 * * *)
"""

import requests
import json
from datetime import datetime, timedelta
from forecast_accuracy_db import save_amedas_data, init_database

# アメダスID
AMEDAS_ID = "11151"  # 沓形

# 気象庁API
JMA_AMEDAS_API = "https://www.jma.go.jp/bosai/amedas/data/point"


def fetch_amedas_hourly_data(target_date):
    """気象庁APIから特定日のアメダスデータを取得

    Args:
        target_date: 対象日 (datetime.date)

    Returns:
        dict: 時別データ、エラー時はNone
    """
    try:
        # 気象庁APIのURL形式: https://www.jma.go.jp/bosai/amedas/data/point/11151/20251008.json
        date_str = target_date.strftime("%Y%m%d")
        url = f"{JMA_AMEDAS_API}/{AMEDAS_ID}/{date_str}.json"

        print(f"アメダスAPI: {url}")
        response = requests.get(url, timeout=30)

        if response.status_code == 200:
            return response.json()
        else:
            print(f"アメダスデータ取得失敗: HTTP {response.status_code}")
            return None

    except Exception as e:
        print(f"アメダスデータ取得エラー: {e}")
        return None


def parse_amedas_data(hourly_data, target_date):
    """アメダス時別データを解析して統計値を計算

    Args:
        hourly_data: 時別データ（気象庁API形式）
        target_date: 対象日

    Returns:
        dict: 統計値（最高/最低気温、湿度、風速、降水量等）
    """
    if not hourly_data:
        return None

    # 作業時間帯（4:00-16:00）のデータを抽出
    work_hours = []
    for hour_str, data in hourly_data.items():
        hour = int(hour_str[:2])  # "04:00:00" -> 4
        if 4 <= hour <= 16:
            work_hours.append(data)

    if not work_hours:
        print("作業時間帯のデータが見つかりません")
        return None

    # 気温統計 (気象庁API: temp = [値, 品質情報])
    temps = [h['temp'][0] for h in work_hours if h.get('temp') and h['temp'][0] is not None]
    temp_max = max(temps) if temps else None
    temp_min = min(temps) if temps else None
    temp_avg = sum(temps) / len(temps) if temps else None

    # 湿度統計 (気象庁API: humidity = [値, 品質情報])
    humidities = [h['humidity'][0] for h in work_hours if h.get('humidity') and h['humidity'][0] is not None]
    humidity_min = min(humidities) if humidities else None
    humidity_avg = sum(humidities) / len(humidities) if humidities else None

    # 風速統計 (気象庁API: wind = [風速, 風向, 品質情報])
    wind_speeds = [h['wind'][0] for h in work_hours if h.get('wind') and h['wind'][0] is not None]
    wind_speed_avg = sum(wind_speeds) / len(wind_speeds) if wind_speeds else None
    wind_speed_max = max(wind_speeds) if wind_speeds else None

    # 降水量（日合計） (気象庁API: precipitation1h = [値, 品質情報])
    precip_values = []
    for hour_str, data in hourly_data.items():
        if data.get('precipitation1h') and data['precipitation1h'][0] is not None:
            precip_values.append(data['precipitation1h'][0])

    precipitation = sum(precip_values) if precip_values else 0.0

    # 日照時間（日合計） (気象庁API: sun1h = [値, 品質情報])
    sunshine_values = []
    for hour_str, data in hourly_data.items():
        if data.get('sun1h') and data['sun1h'][0] is not None:
            sunshine_values.append(data['sun1h'][0])

    sunshine_hours = sum(sunshine_values) if sunshine_values else 0.0

    return {
        'temp_max': temp_max,
        'temp_min': temp_min,
        'temp_avg': temp_avg,
        'humidity_min': humidity_min,
        'humidity_avg': humidity_avg,
        'wind_speed_avg': wind_speed_avg,
        'wind_speed_max': wind_speed_max,
        'precipitation': precipitation,
        'sunshine_hours': sunshine_hours
    }


def fetch_and_save_amedas():
    """当日のアメダスデータを取得してデータベースに保存"""
    print(f"=== アメダスデータ取得開始: {datetime.now()} ===")

    # データベース初期化
    init_database()

    # 対象日（当日）
    target_date = datetime.now().date()
    print(f"対象日: {target_date}")
    print(f"アメダス地点: 沓形 (ID: {AMEDAS_ID})")

    # アメダスデータ取得
    hourly_data = fetch_amedas_hourly_data(target_date)

    if not hourly_data:
        print("✗ アメダスデータ取得失敗")
        return

    # データ解析
    amedas_summary = parse_amedas_data(hourly_data, target_date)

    if not amedas_summary:
        print("✗ アメダスデータ解析失敗")
        return

    print(f"解析結果:")
    print(f"  最高気温: {amedas_summary['temp_max']}°C")
    print(f"  最低気温: {amedas_summary['temp_min']}°C")
    print(f"  最低湿度: {amedas_summary['humidity_min']}%")
    print(f"  平均風速: {amedas_summary['wind_speed_avg']:.1f}m/s")
    print(f"  降水量: {amedas_summary['precipitation']}mm")
    print(f"  日照時間: {amedas_summary['sunshine_hours']:.1f}h")

    # データベースに保存
    result = save_amedas_data(
        observation_date=target_date.isoformat(),
        amedas_data=amedas_summary
    )

    if result:
        print(f"✓ アメダスデータ保存成功")
    else:
        print(f"✗ アメダスデータ保存失敗")

    print(f"=== アメダスデータ取得完了: {datetime.now()} ===")


if __name__ == "__main__":
    fetch_and_save_amedas()
