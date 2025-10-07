"""
予報精度検証システム - データベース管理
SQLiteデータベースの初期化とスキーマ定義
"""

import sqlite3
from datetime import datetime
import os

DB_PATH = "forecast_accuracy.db"

def init_database():
    """データベースを初期化し、必要なテーブルを作成"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # テーブル1: 予報アーカイブ
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS forecast_archive (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            spot_name TEXT NOT NULL,
            forecast_date DATE NOT NULL,
            target_date DATE NOT NULL,
            days_ahead INTEGER NOT NULL,
            temp_max REAL,
            temp_min REAL,
            temp_avg REAL,
            humidity_min REAL,
            humidity_avg REAL,
            wind_speed_avg REAL,
            wind_speed_max REAL,
            precipitation REAL,
            sunshine_hours REAL,
            drying_score REAL,
            viability TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(spot_name, forecast_date, target_date)
        )
    ''')

    # テーブル2: アメダス実測データ
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS amedas_actual (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            observation_date DATE NOT NULL UNIQUE,
            temp_max REAL,
            temp_min REAL,
            temp_avg REAL,
            humidity_min REAL,
            humidity_avg REAL,
            wind_speed_avg REAL,
            wind_speed_max REAL,
            precipitation REAL,
            sunshine_hours REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # テーブル3: 精度分析結果
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS accuracy_analysis (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            analysis_date DATE NOT NULL,
            spot_name TEXT NOT NULL,
            target_date DATE NOT NULL,
            days_ahead INTEGER NOT NULL,
            temp_max_error REAL,
            temp_min_error REAL,
            temp_avg_error REAL,
            humidity_min_error REAL,
            humidity_avg_error REAL,
            wind_avg_error REAL,
            wind_max_error REAL,
            precipitation_hit BOOLEAN,
            precipitation_forecast REAL,
            precipitation_actual REAL,
            drying_success_forecast BOOLEAN,
            drying_success_actual BOOLEAN,
            forecast_correct BOOLEAN,
            overall_score REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(spot_name, target_date, days_ahead)
        )
    ''')

    # インデックス作成
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_forecast_target ON forecast_archive(target_date, spot_name)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_forecast_days ON forecast_archive(days_ahead)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_amedas_date ON amedas_actual(observation_date)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_accuracy_target ON accuracy_analysis(target_date, days_ahead)')

    conn.commit()
    conn.close()

    print(f"[OK] Database initialized: {DB_PATH}")


def get_connection():
    """データベース接続を取得"""
    return sqlite3.connect(DB_PATH)


def save_forecast_data(spot_name, forecast_date, target_date, days_ahead, forecast_data):
    """予報データを保存

    Args:
        spot_name: 干場名
        forecast_date: 予報発表日
        target_date: 予報対象日
        days_ahead: 何日先の予報か（1-6）
        forecast_data: 予報データ辞書
    """
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute('''
            INSERT OR REPLACE INTO forecast_archive
            (spot_name, forecast_date, target_date, days_ahead,
             temp_max, temp_min, temp_avg,
             humidity_min, humidity_avg,
             wind_speed_avg, wind_speed_max,
             precipitation, sunshine_hours,
             drying_score, viability)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            spot_name, forecast_date, target_date, days_ahead,
            forecast_data.get('temp_max'),
            forecast_data.get('temp_min'),
            forecast_data.get('temp_avg'),
            forecast_data.get('humidity_min'),
            forecast_data.get('humidity_avg'),
            forecast_data.get('wind_speed_avg'),
            forecast_data.get('wind_speed_max'),
            forecast_data.get('precipitation'),
            forecast_data.get('sunshine_hours'),
            forecast_data.get('drying_score'),
            forecast_data.get('viability')
        ))
        conn.commit()
        return True
    except Exception as e:
        print(f"予報データ保存エラー: {e}")
        return False
    finally:
        conn.close()


def save_amedas_data(observation_date, amedas_data):
    """アメダス実測データを保存

    Args:
        observation_date: 観測日
        amedas_data: アメダスデータ辞書
    """
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute('''
            INSERT OR REPLACE INTO amedas_actual
            (observation_date, temp_max, temp_min, temp_avg,
             humidity_min, humidity_avg,
             wind_speed_avg, wind_speed_max,
             precipitation, sunshine_hours)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            observation_date,
            amedas_data.get('temp_max'),
            amedas_data.get('temp_min'),
            amedas_data.get('temp_avg'),
            amedas_data.get('humidity_min'),
            amedas_data.get('humidity_avg'),
            amedas_data.get('wind_speed_avg'),
            amedas_data.get('wind_speed_max'),
            amedas_data.get('precipitation'),
            amedas_data.get('sunshine_hours')
        ))
        conn.commit()
        return True
    except Exception as e:
        print(f"アメダスデータ保存エラー: {e}")
        return False
    finally:
        conn.close()


def save_accuracy_result(spot_name, target_date, days_ahead, accuracy_data):
    """精度分析結果を保存

    Args:
        spot_name: 干場名
        target_date: 対象日
        days_ahead: 何日前の予報か
        accuracy_data: 精度分析データ辞書
    """
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute('''
            INSERT OR REPLACE INTO accuracy_analysis
            (analysis_date, spot_name, target_date, days_ahead,
             temp_max_error, temp_min_error, temp_avg_error,
             humidity_min_error, humidity_avg_error,
             wind_avg_error, wind_max_error,
             precipitation_hit, precipitation_forecast, precipitation_actual,
             drying_success_forecast, drying_success_actual,
             forecast_correct, overall_score)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            datetime.now().date().isoformat(),
            spot_name, target_date, days_ahead,
            accuracy_data.get('temp_max_error'),
            accuracy_data.get('temp_min_error'),
            accuracy_data.get('temp_avg_error'),
            accuracy_data.get('humidity_min_error'),
            accuracy_data.get('humidity_avg_error'),
            accuracy_data.get('wind_avg_error'),
            accuracy_data.get('wind_max_error'),
            accuracy_data.get('precipitation_hit'),
            accuracy_data.get('precipitation_forecast'),
            accuracy_data.get('precipitation_actual'),
            accuracy_data.get('drying_success_forecast'),
            accuracy_data.get('drying_success_actual'),
            accuracy_data.get('forecast_correct'),
            accuracy_data.get('overall_score')
        ))
        conn.commit()
        return True
    except Exception as e:
        print(f"精度分析結果保存エラー: {e}")
        return False
    finally:
        conn.close()


def get_forecast_for_date(spot_name, target_date, days_ahead):
    """特定日の予報データを取得"""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute('''
        SELECT * FROM forecast_archive
        WHERE spot_name = ? AND target_date = ? AND days_ahead = ?
    ''', (spot_name, target_date, days_ahead))

    result = cursor.fetchone()
    conn.close()

    if result:
        columns = [desc[0] for desc in cursor.description]
        return dict(zip(columns, result))
    return None


def get_amedas_for_date(observation_date):
    """特定日のアメダス実測データを取得"""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute('''
        SELECT * FROM amedas_actual
        WHERE observation_date = ?
    ''', (observation_date,))

    result = cursor.fetchone()
    conn.close()

    if result:
        columns = [desc[0] for desc in cursor.description]
        return dict(zip(columns, result))
    return None


def get_accuracy_summary(days_ahead=None, start_date=None, end_date=None):
    """精度分析サマリーを取得

    Args:
        days_ahead: 特定の予報日数（1-6）でフィルタ（Noneの場合は全て）
        start_date: 開始日（Noneの場合は全て）
        end_date: 終了日（Noneの場合は全て）

    Returns:
        dict: 精度サマリー統計
    """
    conn = get_connection()
    cursor = conn.cursor()

    query = 'SELECT * FROM accuracy_analysis WHERE 1=1'
    params = []

    if days_ahead is not None:
        query += ' AND days_ahead = ?'
        params.append(days_ahead)

    if start_date:
        query += ' AND target_date >= ?'
        params.append(start_date)

    if end_date:
        query += ' AND target_date <= ?'
        params.append(end_date)

    cursor.execute(query, params)
    results = cursor.fetchall()
    conn.close()

    if not results:
        return None

    # 統計計算
    temp_errors = [r[5] for r in results if r[5] is not None]
    humidity_errors = [r[8] for r in results if r[8] is not None]
    wind_errors = [r[10] for r in results if r[10] is not None]
    precip_hits = [r[12] for r in results if r[12] is not None]
    forecast_corrects = [r[17] for r in results if r[17] is not None]

    return {
        'total_forecasts': len(results),
        'temp_mae': sum(temp_errors) / len(temp_errors) if temp_errors else None,
        'humidity_mae': sum(humidity_errors) / len(humidity_errors) if humidity_errors else None,
        'wind_mae': sum(wind_errors) / len(wind_errors) if wind_errors else None,
        'precipitation_hit_rate': sum(precip_hits) / len(precip_hits) * 100 if precip_hits else None,
        'forecast_accuracy': sum(forecast_corrects) / len(forecast_corrects) * 100 if forecast_corrects else None
    }


if __name__ == "__main__":
    # データベース初期化
    init_database()
    print("Forecast accuracy validation system - Database ready")
