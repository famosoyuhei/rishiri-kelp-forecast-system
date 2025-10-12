"""
Accuracy Analyzer

予報と実測を比較して精度分析

実行タイミング: 毎日 23:00 (cron: 0 23 * * *)
"""

import sqlite3
import logging
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional

from config import IZUMI_SPOTS, DRYING_THRESHOLDS, DB_PATH, LOG_FORMAT, LOG_LEVEL
from database import get_connection

# ロギング設定
logging.basicConfig(level=getattr(logging, LOG_LEVEL), format=LOG_FORMAT)
logger = logging.getLogger(__name__)


def get_actual_data(target_date: date) -> Optional[Dict]:
    """
    指定日の実測データを取得

    Parameters:
        target_date: 対象日

    Returns:
        実測データまたはNone
    """
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute('''
            SELECT observation_date, temp_max, temp_min, humidity_min,
                   wind_speed_avg, wind_speed_max, precipitation, sunshine_hours
            FROM amedas_actual
            WHERE observation_date = ?
        ''', (target_date.isoformat(),))

        row = cursor.fetchone()

        if row:
            return {
                'observation_date': row[0],
                'temp_max': row[1],
                'temp_min': row[2],
                'humidity_min': row[3],
                'wind_speed_avg': row[4],
                'wind_speed_max': row[5],
                'precipitation': row[6],
                'sunshine_hours': row[7],
            }
        else:
            logger.warning(f"No actual data found for {target_date}")
            return None

    except Exception as e:
        logger.error(f"Error fetching actual data: {e}")
        return None

    finally:
        conn.close()


def get_forecast_data(spot_name: str, target_date: date, days_ahead: int) -> Optional[Dict]:
    """
    指定干場・対象日・日数先の予報データを取得

    Parameters:
        spot_name: 干場名
        target_date: 対象日
        days_ahead: 何日先の予報か（1-6）

    Returns:
        予報データまたはNone
    """
    conn = get_connection()
    cursor = conn.cursor()

    # 予報発表日を計算
    forecast_date = target_date - timedelta(days=days_ahead)

    try:
        cursor.execute('''
            SELECT forecast_date, target_date, days_ahead,
                   temp_max, temp_min, humidity_min, wind_speed_avg,
                   precipitation, drying_score, risk_level
            FROM forecast_archive
            WHERE spot_name = ? AND target_date = ? AND days_ahead = ?
        ''', (spot_name, target_date.isoformat(), days_ahead))

        row = cursor.fetchone()

        if row:
            return {
                'forecast_date': row[0],
                'target_date': row[1],
                'days_ahead': row[2],
                'temp_max': row[3],
                'temp_min': row[4],
                'humidity_min': row[5],
                'wind_speed_avg': row[6],
                'precipitation': row[7],
                'drying_score': row[8],
                'risk_level': row[9],
            }
        else:
            logger.debug(f"No forecast found for {spot_name}, {target_date}, {days_ahead}d ahead")
            return None

    except Exception as e:
        logger.error(f"Error fetching forecast data: {e}")
        return None

    finally:
        conn.close()


def calculate_errors(forecast: Dict, actual: Dict) -> Dict:
    """
    予報と実測の誤差を計算

    Parameters:
        forecast: 予報データ
        actual: 実測データ

    Returns:
        誤差データ
    """
    errors = {}

    # 気温誤差（最高気温）
    if forecast['temp_max'] is not None and actual['temp_max'] is not None:
        errors['temp_max_error'] = abs(forecast['temp_max'] - actual['temp_max'])
    else:
        errors['temp_max_error'] = None

    # 気温誤差（最低気温）
    if forecast['temp_min'] is not None and actual['temp_min'] is not None:
        errors['temp_min_error'] = abs(forecast['temp_min'] - actual['temp_min'])
    else:
        errors['temp_min_error'] = None

    # 湿度誤差
    if forecast['humidity_min'] is not None and actual['humidity_min'] is not None:
        errors['humidity_error'] = abs(forecast['humidity_min'] - actual['humidity_min'])
    else:
        errors['humidity_error'] = None

    # 風速誤差
    if forecast['wind_speed_avg'] is not None and actual['wind_speed_avg'] is not None:
        errors['wind_error'] = abs(forecast['wind_speed_avg'] - actual['wind_speed_avg'])
    else:
        errors['wind_error'] = None

    # 降水有無の的中判定
    forecast_precip = forecast['precipitation'] if forecast['precipitation'] is not None else 0.0
    actual_precip = actual['precipitation'] if actual['precipitation'] is not None else 0.0

    # 降水有無（0mm = 無、>0mm = 有）
    forecast_has_rain = forecast_precip > 0
    actual_has_rain = actual_precip > 0

    errors['precipitation_forecast'] = forecast_precip
    errors['precipitation_actual'] = actual_precip
    errors['precipitation_hit'] = (forecast_has_rain == actual_has_rain)

    return errors


def evaluate_drying_possibility(data: Dict) -> bool:
    """
    乾燥可能かどうかを評価（閾値判定）

    Parameters:
        data: 気象データ（予報または実測）

    Returns:
        乾燥可能ならTrue
    """
    # 絶対条件（STAGE_WEIGHT_ANALYSIS.mdから）
    # 1. 降水量 = 0mm
    # 2. 最低湿度 ≤ 94%
    # 3. 平均風速 ≥ 2.0m/s

    precip = data.get('precipitation', 0) if data.get('precipitation') is not None else 0
    humidity = data.get('humidity_min', 100) if data.get('humidity_min') is not None else 100
    wind = data.get('wind_speed_avg', 0) if data.get('wind_speed_avg') is not None else 0

    # すべての条件を満たす必要がある
    is_possible = (
        precip <= DRYING_THRESHOLDS['precipitation'] and
        humidity <= DRYING_THRESHOLDS['min_humidity'] and
        wind >= DRYING_THRESHOLDS['avg_wind_speed']
    )

    return is_possible


def save_analysis_to_db(spot_name: str, target_date: date, days_ahead: int,
                        errors: Dict, forecast: Dict, actual: Dict) -> bool:
    """
    分析結果をデータベースに保存

    Parameters:
        spot_name: 干場名
        target_date: 対象日
        days_ahead: 何日先の予報か
        errors: 誤差データ
        forecast: 予報データ
        actual: 実測データ

    Returns:
        成功時True
    """
    conn = get_connection()
    cursor = conn.cursor()

    try:
        # 乾燥可能判定
        drying_possible_forecast = evaluate_drying_possibility(forecast)
        drying_possible_actual = evaluate_drying_possibility(actual)
        forecast_correct = (drying_possible_forecast == drying_possible_actual)

        # 分析日
        analysis_date = date.today()

        # データベースに保存（重複時は更新）
        cursor.execute('''
            INSERT OR REPLACE INTO accuracy_analysis (
                analysis_date, spot_name, target_date, days_ahead,
                temp_max_error, temp_min_error, humidity_error, wind_error,
                precipitation_forecast, precipitation_actual, precipitation_hit,
                drying_forecast_score, drying_possible_forecast,
                drying_possible_actual, forecast_correct
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            analysis_date.isoformat(),
            spot_name,
            target_date.isoformat(),
            days_ahead,
            errors['temp_max_error'],
            errors['temp_min_error'],
            errors['humidity_error'],
            errors['wind_error'],
            errors['precipitation_forecast'],
            errors['precipitation_actual'],
            errors['precipitation_hit'],
            forecast.get('drying_score'),
            drying_possible_forecast,
            drying_possible_actual,
            forecast_correct
        ))

        conn.commit()
        logger.debug(f"Saved analysis: {spot_name}, {target_date}, {days_ahead}d ahead")
        return True

    except Exception as e:
        logger.error(f"Error saving analysis to database: {e}")
        conn.rollback()
        return False

    finally:
        conn.close()


def analyze_accuracy(target_date: date = None, spots: List[Dict] = None) -> Dict:
    """
    指定日の予報精度を分析

    Parameters:
        target_date: 対象日（Noneの場合は昨日）
        spots: 干場リスト（Noneの場合はconfig.IZUMI_SPOTSを使用）

    Returns:
        分析結果の統計情報
    """
    if target_date is None:
        target_date = date.today() - timedelta(days=1)

    if spots is None:
        spots = IZUMI_SPOTS

    logger.info(f"Starting accuracy analysis for {target_date}")

    # 実測データを取得
    actual = get_actual_data(target_date)

    if not actual:
        logger.error(f"No actual data available for {target_date}")
        return {
            'target_date': target_date.isoformat(),
            'status': 'error',
            'message': 'No actual data available'
        }

    stats = {
        'target_date': target_date.isoformat(),
        'total_analyses': 0,
        'successful_analyses': 0,
        'failed_analyses': 0,
        'by_days_ahead': {},
    }

    # 各干場、各予報日数（1-6日先）について分析
    for spot in spots:
        for days_ahead in range(1, 7):
            # 予報データを取得
            forecast = get_forecast_data(spot['name'], target_date, days_ahead)

            if not forecast:
                logger.debug(f"No forecast for {spot['name']}, {days_ahead}d ahead")
                stats['failed_analyses'] += 1
                continue

            # 誤差計算
            errors = calculate_errors(forecast, actual)

            # 分析結果を保存
            success = save_analysis_to_db(spot['name'], target_date, days_ahead, errors, forecast, actual)

            if success:
                stats['successful_analyses'] += 1

                # 日数別統計
                if days_ahead not in stats['by_days_ahead']:
                    stats['by_days_ahead'][days_ahead] = {
                        'count': 0,
                        'correct_forecasts': 0,
                        'precipitation_hits': 0,
                    }

                stats['by_days_ahead'][days_ahead]['count'] += 1

                if errors['precipitation_hit']:
                    stats['by_days_ahead'][days_ahead]['precipitation_hits'] += 1

                # 乾燥可否予報の的中判定
                drying_possible_forecast = evaluate_drying_possibility(forecast)
                drying_possible_actual = evaluate_drying_possibility(actual)
                if drying_possible_forecast == drying_possible_actual:
                    stats['by_days_ahead'][days_ahead]['correct_forecasts'] += 1

            else:
                stats['failed_analyses'] += 1

            stats['total_analyses'] += 1

    stats['status'] = 'success'
    logger.info(f"Analysis completed: {stats}")

    return stats


def main():
    """メイン実行"""
    logger.info("=" * 60)
    logger.info("Accuracy Analyzer - Starting")
    logger.info("=" * 60)

    import sys

    # コマンドライン引数で日付指定可能（オプション）
    target_date = None
    if len(sys.argv) > 1:
        try:
            target_date = datetime.strptime(sys.argv[1], '%Y-%m-%d').date()
            logger.info(f"Using specified date: {target_date}")
        except ValueError:
            logger.error(f"Invalid date format: {sys.argv[1]}. Expected: YYYY-MM-DD")
            return 1

    try:
        stats = analyze_accuracy(target_date)

        print("\n" + "=" * 60)
        print(f"Accuracy Analysis - {stats['target_date']}")
        print("=" * 60)
        print(f"Status: {stats['status']}")
        if stats['status'] == 'error':
            print(f"Error: {stats['message']}")
        else:
            print(f"Total analyses: {stats['total_analyses']}")
            print(f"Successful: {stats['successful_analyses']}")
            print(f"Failed: {stats['failed_analyses']}")

            if stats['by_days_ahead']:
                print("\nAccuracy by Forecast Days:")
                for days_ahead in sorted(stats['by_days_ahead'].keys()):
                    data = stats['by_days_ahead'][days_ahead]
                    accuracy = (data['correct_forecasts'] / data['count'] * 100) if data['count'] > 0 else 0
                    precip_accuracy = (data['precipitation_hits'] / data['count'] * 100) if data['count'] > 0 else 0

                    print(f"  {days_ahead}d ahead: {data['count']} analyses, "
                          f"{accuracy:.1f}% drying forecast accuracy, "
                          f"{precip_accuracy:.1f}% precipitation accuracy")

        print("=" * 60)

        if stats['status'] == 'error' or stats['failed_analyses'] > 0:
            return 1

        return 0

    except Exception as e:
        logger.error(f"Fatal error in main: {e}", exc_info=True)
        return 1


if __name__ == '__main__':
    exit(main())
