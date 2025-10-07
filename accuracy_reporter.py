"""
予報精度検証システム - 精度レポート生成
週次・月次で精度データを集計してレポート生成
実行: 毎週日曜 00:00 JST (cron: 0 0 * * 0)
"""

import sqlite3
import json
from datetime import datetime, timedelta
from forecast_accuracy_db import get_connection, get_accuracy_summary


def generate_accuracy_report(period_days=30):
    """精度レポートを生成

    Args:
        period_days: 集計期間（日数、デフォルト30日）

    Returns:
        dict: 精度レポート
    """
    print(f"=== 予報精度レポート生成開始: {datetime.now()} ===")
    print(f"集計期間: 直近{period_days}日")

    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=period_days)

    conn = get_connection()
    cursor = conn.cursor()

    # 全体サマリー
    print("\n【全体サマリー】")
    overall_summary = get_accuracy_summary(
        start_date=start_date.isoformat(),
        end_date=end_date.isoformat()
    )

    if overall_summary:
        print(f"総予報数: {overall_summary['total_forecasts']}件")
        print(f"平均気温誤差: ±{overall_summary['temp_mae']:.1f}°C" if overall_summary['temp_mae'] else "平均気温誤差: データなし")
        print(f"平均湿度誤差: ±{overall_summary['humidity_mae']:.0f}%" if overall_summary['humidity_mae'] else "平均湿度誤差: データなし")
        print(f"平均風速誤差: ±{overall_summary['wind_mae']:.1f}m/s" if overall_summary['wind_mae'] else "平均風速誤差: データなし")
        print(f"降水的中率: {overall_summary['precipitation_hit_rate']:.1f}%" if overall_summary['precipitation_hit_rate'] else "降水的中率: データなし")
        print(f"乾燥可否的中率: {overall_summary['forecast_accuracy']:.1f}%" if overall_summary['forecast_accuracy'] else "乾燥可否的中率: データなし")

    # 予報日数別精度
    print("\n【予報日数別精度】")
    days_ahead_summary = {}
    for days_ahead in range(1, 7):
        summary = get_accuracy_summary(
            days_ahead=days_ahead,
            start_date=start_date.isoformat(),
            end_date=end_date.isoformat()
        )

        if summary:
            days_ahead_summary[f"{days_ahead}日前"] = summary
            print(f"\n{days_ahead}日前予報:")
            print(f"  予報数: {summary['total_forecasts']}件")
            print(f"  気温誤差: ±{summary['temp_mae']:.1f}°C" if summary['temp_mae'] else "  気温誤差: データなし")
            print(f"  湿度誤差: ±{summary['humidity_mae']:.0f}%" if summary['humidity_mae'] else "  湿度誤差: データなし")
            print(f"  風速誤差: ±{summary['wind_mae']:.1f}m/s" if summary['wind_mae'] else "  風速誤差: データなし")
            print(f"  降水的中率: {summary['precipitation_hit_rate']:.1f}%" if summary['precipitation_hit_rate'] else "  降水的中率: データなし")
            print(f"  乾燥可否的中率: {summary['forecast_accuracy']:.1f}%" if summary['forecast_accuracy'] else "  乾燥可否的中率: データなし")

    # 干場別精度（上位5干場・下位5干場）
    print("\n【干場別精度（直近30日平均スコア）】")
    cursor.execute('''
        SELECT spot_name,
               COUNT(*) as total_forecasts,
               AVG(overall_score) as avg_score,
               AVG(temp_avg_error) as avg_temp_error,
               AVG(humidity_min_error) as avg_humidity_error,
               AVG(wind_avg_error) as avg_wind_error,
               SUM(CASE WHEN forecast_correct = 1 THEN 1 ELSE 0 END) * 100.0 / COUNT(*) as accuracy_rate
        FROM accuracy_analysis
        WHERE target_date >= ? AND target_date <= ?
        GROUP BY spot_name
        ORDER BY avg_score DESC
    ''', (start_date.isoformat(), end_date.isoformat()))

    spot_results = cursor.fetchall()

    if spot_results:
        print("\n上位5干場:")
        for i, row in enumerate(spot_results[:5], 1):
            print(f"{i}. {row[0]}: スコア{row[2]:.1f}点 (的中率{row[6]:.1f}%, 予報数{row[1]}件)")

        print("\n下位5干場:")
        for i, row in enumerate(spot_results[-5:][::-1], 1):
            print(f"{i}. {row[0]}: スコア{row[2]:.1f}点 (的中率{row[6]:.1f}%, 予報数{row[1]}件)")

    # 日別精度トレンド（直近7日）
    print("\n【直近7日間の精度トレンド】")
    for i in range(7):
        day = end_date - timedelta(days=i)
        cursor.execute('''
            SELECT AVG(overall_score) as avg_score,
                   SUM(CASE WHEN forecast_correct = 1 THEN 1 ELSE 0 END) * 100.0 / COUNT(*) as accuracy_rate
            FROM accuracy_analysis
            WHERE target_date = ?
        ''', (day.isoformat(),))

        result = cursor.fetchone()
        if result and result[0]:
            print(f"{day}: スコア{result[0]:.1f}点 / 的中率{result[1]:.1f}%")
        else:
            print(f"{day}: データなし")

    conn.close()

    # レポート作成
    report = {
        'generated_at': datetime.now().isoformat(),
        'period': {
            'start_date': start_date.isoformat(),
            'end_date': end_date.isoformat(),
            'days': period_days
        },
        'overall_summary': overall_summary,
        'days_ahead_summary': days_ahead_summary,
        'spot_rankings': [
            {
                'spot_name': row[0],
                'avg_score': row[2],
                'accuracy_rate': row[6],
                'total_forecasts': row[1]
            }
            for row in spot_results
        ] if spot_results else []
    }

    # レポートをJSON形式で保存
    report_filename = f"accuracy_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(report_filename, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(f"\n✓ レポート保存完了: {report_filename}")
    print(f"=== 予報精度レポート生成完了: {datetime.now()} ===")

    return report


def print_summary_table(period_days=30):
    """簡易サマリーテーブルを表示

    Args:
        period_days: 集計期間（日数）
    """
    print("\n" + "="*80)
    print(f"予報精度サマリー（直近{period_days}日）")
    print("="*80)

    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=period_days)

    print(f"\n{'予報日数':<10} {'予報数':<8} {'気温誤差':<12} {'湿度誤差':<12} {'風速誤差':<12} {'的中率':<8}")
    print("-" * 80)

    for days_ahead in range(1, 7):
        summary = get_accuracy_summary(
            days_ahead=days_ahead,
            start_date=start_date.isoformat(),
            end_date=end_date.isoformat()
        )

        if summary:
            temp_str = f"±{summary['temp_mae']:.1f}°C" if summary['temp_mae'] else "---"
            humidity_str = f"±{summary['humidity_mae']:.0f}%" if summary['humidity_mae'] else "---"
            wind_str = f"±{summary['wind_mae']:.1f}m/s" if summary['wind_mae'] else "---"
            acc_str = f"{summary['forecast_accuracy']:.1f}%" if summary['forecast_accuracy'] else "---"

            print(f"{days_ahead}日前{'':<6} {summary['total_forecasts']:<8} {temp_str:<12} {humidity_str:<12} {wind_str:<12} {acc_str:<8}")
        else:
            print(f"{days_ahead}日前{'':<6} {'---':<8} {'---':<12} {'---':<12} {'---':<12} {'---':<8}")

    print("="*80 + "\n")


if __name__ == "__main__":
    # レポート生成
    report = generate_accuracy_report(period_days=30)

    # サマリーテーブル表示
    print_summary_table(period_days=30)

    # 推奨事項
    print("\n【推奨事項】")
    if report['overall_summary']:
        temp_mae = report['overall_summary'].get('temp_mae')
        humidity_mae = report['overall_summary'].get('humidity_mae')
        accuracy = report['overall_summary'].get('forecast_accuracy')

        if temp_mae and temp_mae > 2.0:
            print(f"⚠ 気温誤差が{temp_mae:.1f}°Cと大きいです。気温モデルの再調整を検討してください。")

        if humidity_mae and humidity_mae > 15:
            print(f"⚠ 湿度誤差が{humidity_mae:.0f}%と大きいです。湿度補正アルゴリズムの見直しが必要です。")

        if accuracy and accuracy < 70:
            print(f"⚠ 乾燥可否的中率が{accuracy:.1f}%と低いです。判定閾値の調整を推奨します。")

        if not (temp_mae and temp_mae > 2.0) and not (humidity_mae and humidity_mae > 15) and not (accuracy and accuracy < 70):
            print("✓ 予報精度は良好です。現在の設定を維持してください。")
