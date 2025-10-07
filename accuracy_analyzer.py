"""
予報精度検証システム - 精度分析
過去の予報と実測データを比較して精度を評価
実行: 毎日23:00 JST (cron: 0 23 * * *)
"""

import json
from datetime import datetime, timedelta
from forecast_accuracy_db import (
    get_forecast_for_date,
    get_amedas_for_date,
    save_accuracy_result,
    init_database
)


def load_target_spots():
    """検証対象13干場を読み込み"""
    try:
        with open('kutsugata_nearby_spots.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data['spots']
    except Exception as e:
        print(f"干場リスト読み込みエラー: {e}")
        return []


def calculate_drying_success(amedas_data):
    """アメダス実測データから実際に乾燥可能だったかを判定

    実測データ基準（H_1631_1434 神居/沓形アメダス分析結果）:
    - 降水量: 0mm（絶対条件）
    - 最低湿度: ≤94%（最重要）
    - 平均風速: ≥2.0m/s（重要）
    - 平均気温: ≥18.3°C（補助的）

    Args:
        amedas_data: アメダス実測データ

    Returns:
        bool: 乾燥可能だったか
    """
    # 降水があれば不可
    if amedas_data.get('precipitation', 0) > 0:
        return False

    # 最低湿度94%超えなら不可
    if amedas_data.get('humidity_min', 100) > 94:
        return False

    # 平均風速2.0m/s未満なら困難
    if amedas_data.get('wind_speed_avg', 0) < 2.0:
        return False

    # 上記すべてクリアなら乾燥可能
    return True


def analyze_forecast_accuracy(spot_name, target_date_str, days_ahead):
    """特定の予報と実測を比較して精度を計算

    Args:
        spot_name: 干場名
        target_date_str: 対象日 (ISO形式)
        days_ahead: 何日前の予報か（1-6）

    Returns:
        dict: 精度分析結果、エラー時はNone
    """
    # 予報データ取得
    forecast = get_forecast_for_date(spot_name, target_date_str, days_ahead)

    if not forecast:
        print(f"  予報データなし: {spot_name} / {target_date_str} / {days_ahead}日前")
        return None

    # 実測データ取得
    actual = get_amedas_for_date(target_date_str)

    if not actual:
        print(f"  実測データなし: {target_date_str}")
        return None

    # 誤差計算
    temp_max_error = abs(forecast['temp_max'] - actual['temp_max']) if forecast['temp_max'] and actual['temp_max'] else None
    temp_min_error = abs(forecast['temp_min'] - actual['temp_min']) if forecast['temp_min'] and actual['temp_min'] else None
    temp_avg_error = abs(forecast['temp_avg'] - actual['temp_avg']) if forecast['temp_avg'] and actual['temp_avg'] else None

    humidity_min_error = abs(forecast['humidity_min'] - actual['humidity_min']) if forecast['humidity_min'] and actual['humidity_min'] else None
    humidity_avg_error = abs(forecast['humidity_avg'] - actual['humidity_avg']) if forecast['humidity_avg'] and actual['humidity_avg'] else None

    wind_avg_error = abs(forecast['wind_speed_avg'] - actual['wind_speed_avg']) if forecast['wind_speed_avg'] and actual['wind_speed_avg'] else None
    wind_max_error = abs(forecast['wind_speed_max'] - actual['wind_speed_max']) if forecast['wind_speed_max'] and actual['wind_speed_max'] else None

    # 降水の的中判定
    forecast_precip = forecast['precipitation'] or 0
    actual_precip = actual['precipitation'] or 0

    # 降水有無で判定（閾値0.5mm）
    forecast_has_rain = forecast_precip > 0.5
    actual_has_rain = actual_precip > 0.5
    precipitation_hit = (forecast_has_rain == actual_has_rain)

    # 乾燥可否判定
    drying_success_forecast = (forecast['viability'] in ['理想的', 'ギリギリ可能'])
    drying_success_actual = calculate_drying_success(actual)

    forecast_correct = (drying_success_forecast == drying_success_actual)

    # 総合スコア計算（0-100点）
    score = 100.0

    # 気温誤差ペナルティ（最大-20点）
    if temp_avg_error:
        score -= min(temp_avg_error * 2, 20)

    # 湿度誤差ペナルティ（最大-30点）
    if humidity_min_error:
        score -= min(humidity_min_error * 0.3, 30)

    # 風速誤差ペナルティ（最大-20点）
    if wind_avg_error:
        score -= min(wind_avg_error * 4, 20)

    # 降水不的中ペナルティ（-15点）
    if not precipitation_hit:
        score -= 15

    # 乾燥可否誤判定ペナルティ（-15点）
    if not forecast_correct:
        score -= 15

    score = max(score, 0)  # 負にならないように

    return {
        'temp_max_error': temp_max_error,
        'temp_min_error': temp_min_error,
        'temp_avg_error': temp_avg_error,
        'humidity_min_error': humidity_min_error,
        'humidity_avg_error': humidity_avg_error,
        'wind_avg_error': wind_avg_error,
        'wind_max_error': wind_max_error,
        'precipitation_hit': precipitation_hit,
        'precipitation_forecast': forecast_precip,
        'precipitation_actual': actual_precip,
        'drying_success_forecast': drying_success_forecast,
        'drying_success_actual': drying_success_actual,
        'forecast_correct': forecast_correct,
        'overall_score': score
    }


def analyze_all_forecasts():
    """全干場・全日数の予報精度を分析"""
    print(f"=== 予報精度分析開始: {datetime.now()} ===")

    # データベース初期化
    init_database()

    # 対象干場読み込み
    spots = load_target_spots()
    if not spots:
        print("エラー: 干場リストが空です")
        return

    # 対象日（当日）
    target_date = datetime.now().date()
    target_date_str = target_date.isoformat()

    print(f"分析対象日: {target_date}")
    print(f"対象干場数: {len(spots)}")

    success_count = 0
    error_count = 0

    # 各干場について
    for spot in spots:
        spot_name = spot['name']
        print(f"\n分析中: {spot_name}")

        # 1日前～6日前の予報を分析
        for days_ahead in range(1, 7):
            forecast_date = target_date - timedelta(days=days_ahead)
            print(f"  {days_ahead}日前予報 (発表日: {forecast_date})")

            # 精度分析
            accuracy = analyze_forecast_accuracy(spot_name, target_date_str, days_ahead)

            if accuracy:
                # データベースに保存
                result = save_accuracy_result(
                    spot_name=spot_name,
                    target_date=target_date_str,
                    days_ahead=days_ahead,
                    accuracy_data=accuracy
                )

                if result:
                    print(f"    ✓ 精度スコア: {accuracy['overall_score']:.1f}点")
                    print(f"      気温誤差: ±{accuracy['temp_avg_error']:.1f}°C" if accuracy['temp_avg_error'] else "      気温誤差: データなし")
                    print(f"      湿度誤差: ±{accuracy['humidity_min_error']:.0f}%" if accuracy['humidity_min_error'] else "      湿度誤差: データなし")
                    print(f"      風速誤差: ±{accuracy['wind_avg_error']:.1f}m/s" if accuracy['wind_avg_error'] else "      風速誤差: データなし")
                    print(f"      降水的中: {'○' if accuracy['precipitation_hit'] else '×'}")
                    print(f"      乾燥判定的中: {'○' if accuracy['forecast_correct'] else '×'}")
                    success_count += 1
                else:
                    print(f"    ✗ 精度結果保存失敗")
                    error_count += 1
            else:
                error_count += 1

    print(f"\n=== 予報精度分析完了 ===")
    print(f"成功: {success_count}件")
    print(f"失敗: {error_count}件")
    print(f"完了時刻: {datetime.now()}")


if __name__ == "__main__":
    analyze_all_forecasts()
