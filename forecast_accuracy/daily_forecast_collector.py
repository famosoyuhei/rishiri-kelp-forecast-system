"""
Daily Forecast Collector

毎日の予報データ（1-6日先）を収集してデータベースに保存

実行タイミング: 毎日 6:00 (cron: 0 6 * * *)
"""

import requests
import sqlite3
import json
import logging
from datetime import datetime, date, timedelta
from typing import List, Dict, Optional
import time

from config import IZUMI_SPOTS, FORECAST_API_BASE, DB_PATH, LOG_FORMAT, LOG_LEVEL
from database import get_connection

# ロギング設定
logging.basicConfig(level=getattr(logging, LOG_LEVEL), format=LOG_FORMAT)
logger = logging.getLogger(__name__)


def fetch_forecast_for_spot(spot: Dict[str, any], max_retries: int = 3) -> Optional[Dict]:
    """
    指定干場の予報データを取得

    Parameters:
        spot: 干場情報（name, lat, lon）
        max_retries: 最大リトライ回数

    Returns:
        予報データ（JSON）またはNone（エラー時）
    """
    url = f"{FORECAST_API_BASE}?lat={spot['lat']}&lon={spot['lon']}&name={spot['name']}"

    for attempt in range(max_retries):
        try:
            logger.info(f"Fetching forecast for {spot['name']} (attempt {attempt + 1}/{max_retries})")
            response = requests.get(url, timeout=30)
            response.raise_for_status()

            data = response.json()
            if data.get('status') == 'success':
                logger.info(f"Successfully fetched forecast for {spot['name']}")
                return data
            else:
                logger.warning(f"API returned non-success status: {data.get('status')}")

        except requests.exceptions.Timeout:
            logger.warning(f"Timeout fetching forecast for {spot['name']} (attempt {attempt + 1})")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)  # Exponential backoff

        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching forecast for {spot['name']}: {e}")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)

        except Exception as e:
            logger.error(f"Unexpected error fetching forecast for {spot['name']}: {e}")
            break

    return None


def extract_daily_summary(forecast_day: Dict) -> Dict:
    """
    予報データから日次サマリーを抽出

    Parameters:
        forecast_day: 1日分の予報データ

    Returns:
        抽出されたサマリーデータ
    """
    daily = forecast_day.get('daily_summary', {})

    # 時間別データから最低湿度を計算
    hourly = forecast_day.get('hourly_details', [])
    min_humidity = None
    if hourly:
        humidity_values = [h.get('humidity') for h in hourly if h.get('humidity') is not None]
        if humidity_values:
            min_humidity = min(humidity_values)

    # 時間別データから平均風速を計算
    avg_wind_speed = None
    if hourly:
        wind_values = [h.get('wind_speed') for h in hourly if h.get('wind_speed') is not None]
        if wind_values:
            avg_wind_speed = sum(wind_values) / len(wind_values)

    return {
        'temp_max': daily.get('temperature_max'),
        'temp_min': daily.get('temperature_min'),
        'humidity_min': min_humidity,
        'wind_speed_avg': avg_wind_speed,
        'precipitation': daily.get('precipitation'),
        'drying_score': daily.get('drying_score'),
        'risk_level': daily.get('stage_analysis', {}).get('risk_assessment', {}).get('risk_level'),
    }


def save_forecast_to_db(spot_name: str, forecast_date: date, forecast_data: Dict) -> int:
    """
    予報データをデータベースに保存

    Parameters:
        spot_name: 干場名
        forecast_date: 予報発表日
        forecast_data: 予報データ

    Returns:
        保存した件数
    """
    conn = get_connection()
    cursor = conn.cursor()
    saved_count = 0

    try:
        forecasts = forecast_data.get('forecasts', [])

        # 1-6日先の予報を保存（0日目は除外）
        for forecast_day in forecasts[1:7]:  # Index 1-6 (1-6日先)
            target_date_str = forecast_day.get('date')
            days_ahead = forecast_day.get('day_number')

            if not target_date_str or days_ahead is None:
                continue

            # 日次サマリーを抽出
            summary = extract_daily_summary(forecast_day)

            # データベースに保存（重複時は更新）
            cursor.execute('''
                INSERT OR REPLACE INTO forecast_archive (
                    spot_name, forecast_date, target_date, days_ahead,
                    temp_max, temp_min, humidity_min, wind_speed_avg,
                    precipitation, drying_score, risk_level, forecast_data_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                spot_name,
                forecast_date.isoformat(),
                target_date_str,
                days_ahead,
                summary['temp_max'],
                summary['temp_min'],
                summary['humidity_min'],
                summary['wind_speed_avg'],
                summary['precipitation'],
                summary['drying_score'],
                summary['risk_level'],
                json.dumps(forecast_day, ensure_ascii=False)
            ))

            saved_count += 1
            logger.debug(f"Saved forecast: {spot_name}, target={target_date_str}, days_ahead={days_ahead}")

        conn.commit()
        logger.info(f"Saved {saved_count} forecast records for {spot_name}")

    except Exception as e:
        logger.error(f"Error saving forecast to database: {e}")
        conn.rollback()
        raise

    finally:
        conn.close()

    return saved_count


def collect_daily_forecasts(spots: List[Dict] = None) -> Dict[str, int]:
    """
    全干場の予報データを収集

    Parameters:
        spots: 干場リスト（Noneの場合はconfig.IZUMI_SPOTSを使用）

    Returns:
        収集結果の統計情報
    """
    if spots is None:
        spots = IZUMI_SPOTS

    forecast_date = date.today()
    logger.info(f"Starting daily forecast collection for {len(spots)} spots (forecast_date={forecast_date})")

    stats = {
        'total_spots': len(spots),
        'successful_spots': 0,
        'failed_spots': 0,
        'total_records_saved': 0,
    }

    for spot in spots:
        logger.info(f"Processing spot: {spot['name']}")

        # 予報データ取得
        forecast_data = fetch_forecast_for_spot(spot)

        if forecast_data:
            # データベースに保存
            try:
                saved_count = save_forecast_to_db(spot['name'], forecast_date, forecast_data)
                stats['successful_spots'] += 1
                stats['total_records_saved'] += saved_count
            except Exception as e:
                logger.error(f"Failed to save forecast for {spot['name']}: {e}")
                stats['failed_spots'] += 1
        else:
            logger.error(f"Failed to fetch forecast for {spot['name']}")
            stats['failed_spots'] += 1

        # API負荷軽減のため少し待機
        time.sleep(1)

    logger.info(f"Collection completed: {stats}")
    return stats


def main():
    """メイン実行"""
    logger.info("=" * 60)
    logger.info("Daily Forecast Collector - Starting")
    logger.info("=" * 60)

    try:
        stats = collect_daily_forecasts()

        print("\n" + "=" * 60)
        print("Daily Forecast Collection - Results")
        print("=" * 60)
        print(f"Total spots: {stats['total_spots']}")
        print(f"Successful: {stats['successful_spots']}")
        print(f"Failed: {stats['failed_spots']}")
        print(f"Total records saved: {stats['total_records_saved']}")
        print("=" * 60)

        if stats['failed_spots'] > 0:
            logger.warning(f"{stats['failed_spots']} spots failed to collect")
            return 1

        return 0

    except Exception as e:
        logger.error(f"Fatal error in main: {e}", exc_info=True)
        return 1


if __name__ == '__main__':
    exit(main())
