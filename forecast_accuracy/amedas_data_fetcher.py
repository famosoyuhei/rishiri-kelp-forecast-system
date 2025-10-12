"""
Amedas Data Fetcher

アメダス沓形の実測データを取得してデータベースに保存

実行タイミング: 毎日 16:00 (cron: 0 16 * * *)
              ※16時時点で当日4:00-16:00のデータが揃うため
"""

import requests
import sqlite3
import json
import logging
from datetime import datetime, date, timedelta
from typing import Dict, Optional
import time

from config import AMEDAS_KUTSUGATA, DB_PATH, LOG_FORMAT, LOG_LEVEL
from database import get_connection

# ロギング設定
logging.basicConfig(level=getattr(logging, LOG_LEVEL), format=LOG_FORMAT)
logger = logging.getLogger(__name__)

# cultivationdata.net API endpoint (より信頼性の高いサードパーティAPI)
CULTIVATION_API_BASE = 'https://api.cultivationdata.net/amds'


def fetch_amedas_hourly_data(observation_date: date, amedas_id: str, max_retries: int = 3) -> Dict:
    """
    cultivationdata.net APIからアメダスの乾燥予報時間帯（4:00-16:00）のデータを取得

    予報システムに合わせて、昆布乾燥に重要な時間帯のみ取得：
    - 換気段階: 4:00-10:00 (7時間)
    - 熱供給段階: 10:00-16:00 (7時間)
    合計13時間のデータで、API呼び出しを削減しながら精度分析に必要なデータを確保

    Parameters:
        observation_date: 観測日
        amedas_id: アメダスID (5桁)
        max_retries: 最大リトライ回数

    Returns:
        時間別データの辞書、エラー時は空の辞書
    """
    hourly_data = {}

    # 乾燥予報の対象時間帯のみ取得（4:00-16:00）
    TARGET_HOURS = list(range(4, 17))  # 4時から16時まで（13時間）

    for hour in TARGET_HOURS:
        dt_str = observation_date.strftime(f'%Y%m%d{hour:02d}00')
        url = f"{CULTIVATION_API_BASE}?no={amedas_id}&dt={dt_str}"

        for attempt in range(max_retries):
            try:
                logger.debug(f"Fetching hour {hour:02d}:00 (attempt {attempt + 1})")
                response = requests.get(url, timeout=30)
                response.raise_for_status()

                data = response.json()
                time_key = f"{hour:02d}:00"
                hourly_data[time_key] = data
                logger.debug(f"Successfully fetched data for {time_key}")

                # API rate limit対策: 成功したら短い待機
                time.sleep(0.5)
                break

            except requests.exceptions.HTTPError as e:
                if e.response.status_code == 404:
                    logger.warning(f"Data not found for hour {hour:02d}:00")
                    break
                elif e.response.status_code == 429:
                    # Rate limit exceeded - wait longer
                    wait_time = 2 ** attempt
                    logger.warning(f"Rate limit (429) for hour {hour}, waiting {wait_time}s")
                    time.sleep(wait_time)
                else:
                    logger.warning(f"HTTP error for hour {hour}: {e}")
                    if attempt < max_retries - 1:
                        time.sleep(1)

            except requests.exceptions.Timeout:
                logger.warning(f"Timeout for hour {hour} (attempt {attempt + 1})")
                if attempt < max_retries - 1:
                    time.sleep(1)

            except Exception as e:
                logger.error(f"Error fetching hour {hour}: {e}")
                break

    if hourly_data:
        logger.info(f"Successfully fetched {len(hourly_data)}/{len(TARGET_HOURS)} hours (4:00-16:00) for {observation_date}")
    else:
        logger.error(f"Failed to fetch any data for {observation_date}")

    return hourly_data


def calculate_daily_statistics(hourly_data: Dict) -> Dict:
    """
    時間別データから日次統計を計算

    cultivationdata.net APIデータフォーマット:
    {
        "HH:MM": {
            "temp": [気温, 0],              # 0=正常値
            "humidity": [湿度, 0],
            "wind": [風速, 0],
            "precipitation1h": [降水量, 0],
            "sun1h": [日照時間, 0],
            "dataTime": ["2025/10/05 06:30"]
        },
        ...
    }

    Parameters:
        hourly_data: 時間別アメダスデータ

    Returns:
        日次統計データ
    """
    temps = []
    humidities = []
    winds = []
    precipitations = []
    sunshine_hours = []

    for time_str, data in hourly_data.items():
        # 気温
        if 'temp' in data and isinstance(data['temp'], list) and len(data['temp']) >= 1:
            if data['temp'][0] is not None:
                temps.append(data['temp'][0])

        # 湿度
        if 'humidity' in data and isinstance(data['humidity'], list) and len(data['humidity']) >= 1:
            if data['humidity'][0] is not None:
                humidities.append(data['humidity'][0])

        # 風速
        if 'wind' in data and isinstance(data['wind'], list) and len(data['wind']) >= 1:
            if data['wind'][0] is not None:
                winds.append(data['wind'][0])

        # 降水量（1時間値）
        if 'precipitation1h' in data and isinstance(data['precipitation1h'], list) and len(data['precipitation1h']) >= 1:
            if data['precipitation1h'][0] is not None:
                precipitations.append(data['precipitation1h'][0])

        # 日照時間（1時間値）
        if 'sun1h' in data and isinstance(data['sun1h'], list) and len(data['sun1h']) >= 1:
            if data['sun1h'][0] is not None:
                sunshine_hours.append(data['sun1h'][0])

    # 統計計算
    stats = {
        'temp_max': max(temps) if temps else None,
        'temp_min': min(temps) if temps else None,
        'humidity_min': min(humidities) if humidities else None,
        'wind_speed_avg': round(sum(winds) / len(winds), 1) if winds else None,
        'wind_speed_max': max(winds) if winds else None,
        'precipitation': round(sum(precipitations), 1) if precipitations else 0.0,  # 日降水量
        'sunshine_hours': round(sum(sunshine_hours), 1) if sunshine_hours else 0.0,  # 日照時間
    }

    logger.debug(f"Calculated daily statistics: {stats}")
    return stats


def save_amedas_to_db(observation_date: date, stats: Dict, raw_data: Dict) -> bool:
    """
    アメダスデータをデータベースに保存

    Parameters:
        observation_date: 観測日
        stats: 日次統計データ
        raw_data: 生データ（JSON保存用）

    Returns:
        成功時True、失敗時False
    """
    conn = get_connection()
    cursor = conn.cursor()

    try:
        # データベースに保存（重複時は更新）
        cursor.execute('''
            INSERT OR REPLACE INTO amedas_actual (
                observation_date, temp_max, temp_min, humidity_min,
                wind_speed_avg, wind_speed_max, precipitation,
                sunshine_hours, amedas_data_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            observation_date.isoformat(),
            stats['temp_max'],
            stats['temp_min'],
            stats['humidity_min'],
            stats['wind_speed_avg'],
            stats['wind_speed_max'],
            stats['precipitation'],
            stats['sunshine_hours'],
            json.dumps(raw_data, ensure_ascii=False)
        ))

        conn.commit()
        logger.info(f"Saved Amedas data for {observation_date}")
        return True

    except Exception as e:
        logger.error(f"Error saving Amedas data to database: {e}")
        conn.rollback()
        return False

    finally:
        conn.close()


def fetch_and_save_amedas(observation_date: date = None) -> bool:
    """
    アメダスデータを取得して保存

    Parameters:
        observation_date: 観測日（Noneの場合は当日）
                        ※16時実行時、当日4:00-16:00のデータを取得

    Returns:
        成功時True、失敗時False
    """
    if observation_date is None:
        # デフォルトは当日（16時実行時に4:00-16:00のデータが揃っている）
        observation_date = date.today()

    logger.info(f"Fetching Amedas data for {observation_date}")

    # アメダスデータ取得（1日分の時間別データ）
    hourly_data = fetch_amedas_hourly_data(observation_date, AMEDAS_KUTSUGATA['id'])

    if not hourly_data:
        logger.error(f"Failed to fetch Amedas data for {observation_date}")
        return False

    # 日次統計を計算
    stats = calculate_daily_statistics(hourly_data)

    # データベースに保存
    success = save_amedas_to_db(observation_date, stats, hourly_data)

    if success:
        print(f"\n{'='*60}")
        print(f"Amedas Data - {observation_date} (Station: Kutsugata 11151)")
        print(f"{'='*60}")
        print(f"Data Coverage: {len(hourly_data)}/24 hours")
        print(f"Max Temp: {stats['temp_max']}°C" if stats['temp_max'] is not None else "Max Temp: N/A")
        print(f"Min Temp: {stats['temp_min']}°C" if stats['temp_min'] is not None else "Min Temp: N/A")
        print(f"Min Humidity: {stats['humidity_min']}%" if stats['humidity_min'] is not None else "Min Humidity: N/A")
        print(f"Avg Wind: {stats['wind_speed_avg']} m/s" if stats['wind_speed_avg'] is not None else "Avg Wind: N/A")
        print(f"Max Wind: {stats['wind_speed_max']} m/s" if stats['wind_speed_max'] is not None else "Max Wind: N/A")
        print(f"Precipitation: {stats['precipitation']} mm")
        print(f"Sunshine Hours: {stats['sunshine_hours']} h")
        print(f"{'='*60}\n")

    return success


def main():
    """メイン実行"""
    logger.info("=" * 60)
    logger.info("Amedas Data Fetcher - Starting")
    logger.info("=" * 60)

    import sys

    # コマンドライン引数で日付指定可能（オプション）
    observation_date = None
    if len(sys.argv) > 1:
        try:
            observation_date = datetime.strptime(sys.argv[1], '%Y-%m-%d').date()
            logger.info(f"Using specified date: {observation_date}")
        except ValueError:
            logger.error(f"Invalid date format: {sys.argv[1]}. Expected: YYYY-MM-DD")
            return 1

    try:
        success = fetch_and_save_amedas(observation_date)

        if success:
            logger.info("Amedas data fetch completed successfully")
            return 0
        else:
            logger.error("Amedas data fetch failed")
            return 1

    except Exception as e:
        logger.error(f"Fatal error in main: {e}", exc_info=True)
        return 1


if __name__ == '__main__':
    exit(main())
