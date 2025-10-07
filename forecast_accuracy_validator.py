#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
予報精度検証システム
- 過去予報データを保存（1日前～6日前の各予報）
- アメダス実測データと比較
- 予報精度をブラッシュアップ
"""
import json
import os
from datetime import datetime, timedelta
import requests
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('forecast_accuracy_validator.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

class ForecastAccuracyValidator:
    """予報精度検証システム"""

    def __init__(self):
        self.forecast_dir = "forecast_history"
        self.amedas_dir = "amedas_data"
        self.validation_dir = "validation_results"
        self.nearby_spots_file = "kutsugata_nearby_spots.json"

        self.ensure_directories()
        self.load_nearby_spots()

    def ensure_directories(self):
        """必要なディレクトリを作成"""
        for directory in [self.forecast_dir, self.amedas_dir, self.validation_dir]:
            if not os.path.exists(directory):
                os.makedirs(directory)
                logging.info(f"Created directory: {directory}")

    def load_nearby_spots(self):
        """アメダス沓形周辺500m以内の干場を読み込み"""
        try:
            with open(self.nearby_spots_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.nearby_spots = data['spots']
                self.amedas_location = data['amedas_info']
                logging.info(f"Loaded {len(self.nearby_spots)} nearby spots")
        except Exception as e:
            logging.error(f"Failed to load nearby spots: {e}")
            self.nearby_spots = []
            self.amedas_location = None

    def save_daily_forecast(self, date, spot_name, forecast_data):
        """
        毎日の予報データを保存（1～6日後の予報）

        Args:
            date: 予報取得日（datetime）
            spot_name: 干場名
            forecast_data: 7日間予報データ
        """
        date_str = date.strftime("%Y%m%d")

        # 干場ごとのディレクトリを作成
        spot_dir = os.path.join(self.forecast_dir, spot_name)
        if not os.path.exists(spot_dir):
            os.makedirs(spot_dir)

        # 1日後～6日後の予報を個別に保存
        for days_ahead in range(1, 7):
            target_date = date + timedelta(days=days_ahead)
            target_date_str = target_date.strftime("%Y%m%d")

            # ファイル名: forecast_YYYYMMDD_for_YYYYMMDD.json
            # (YYYYMMDD時点でのYYYYMMDD日の予報)
            filename = f"forecast_{date_str}_for_{target_date_str}.json"
            filepath = os.path.join(spot_dir, filename)

            # forecast_data の days_ahead 日目のデータを抽出
            if isinstance(forecast_data, dict) and 'daily' in forecast_data:
                daily_data = forecast_data['daily']
                if days_ahead - 1 < len(daily_data):
                    forecast_for_day = {
                        'forecast_date': date_str,
                        'target_date': target_date_str,
                        'days_ahead': days_ahead,
                        'spot_name': spot_name,
                        'forecast': daily_data[days_ahead - 1]
                    }

                    try:
                        with open(filepath, 'w', encoding='utf-8') as f:
                            json.dump(forecast_for_day, f, ensure_ascii=False, indent=2)
                        logging.info(f"Saved forecast: {filename}")
                    except Exception as e:
                        logging.error(f"Failed to save forecast {filename}: {e}")

    def validate_forecast_accuracy(self, target_date):
        """
        特定日の予報精度を検証

        Args:
            target_date: 検証対象日（datetime）

        Returns:
            dict: 検証結果
        """
        target_date_str = target_date.strftime("%Y%m%d")

        # アメダス実測データを読み込み
        amedas_file = os.path.join(self.amedas_dir, f"amedas_11151_{target_date_str}.json")

        if not os.path.exists(amedas_file):
            logging.warning(f"AMeDAS data not found for {target_date_str}")
            return None

        try:
            with open(amedas_file, 'r', encoding='utf-8') as f:
                amedas_data = json.load(f)
        except Exception as e:
            logging.error(f"Failed to load AMeDAS data: {e}")
            return None

        # 各干場・各予報日数の精度を検証
        validation_results = {
            'target_date': target_date_str,
            'amedas_actual': amedas_data,
            'spots_validation': []
        }

        for spot in self.nearby_spots:
            spot_name = spot['name']
            spot_dir = os.path.join(self.forecast_dir, spot_name)

            if not os.path.exists(spot_dir):
                continue

            spot_validation = {
                'spot_name': spot_name,
                'distance_to_amedas': spot['distance_to_amedas'],
                'forecasts': []
            }

            # 1～6日前の予報を取得
            for days_before in range(1, 7):
                forecast_date = target_date - timedelta(days=days_before)
                forecast_date_str = forecast_date.strftime("%Y%m%d")

                forecast_file = f"forecast_{forecast_date_str}_for_{target_date_str}.json"
                forecast_path = os.path.join(spot_dir, forecast_file)

                if os.path.exists(forecast_path):
                    try:
                        with open(forecast_path, 'r', encoding='utf-8') as f:
                            forecast_data = json.load(f)

                        # 予報と実測の比較
                        accuracy = self.calculate_accuracy(
                            forecast_data['forecast'],
                            amedas_data['data']
                        )

                        spot_validation['forecasts'].append({
                            'days_before': days_before,
                            'forecast_date': forecast_date_str,
                            'forecast': forecast_data['forecast'],
                            'accuracy': accuracy
                        })

                    except Exception as e:
                        logging.error(f"Failed to process {forecast_file}: {e}")

            if spot_validation['forecasts']:
                validation_results['spots_validation'].append(spot_validation)

        # 検証結果を保存
        result_file = os.path.join(self.validation_dir, f"validation_{target_date_str}.json")
        try:
            with open(result_file, 'w', encoding='utf-8') as f:
                json.dump(validation_results, f, ensure_ascii=False, indent=2)
            logging.info(f"Validation results saved: {result_file}")
        except Exception as e:
            logging.error(f"Failed to save validation results: {e}")

        return validation_results

    def calculate_accuracy(self, forecast, actual):
        """
        予報と実測の精度を計算

        Args:
            forecast: 予報データ
            actual: アメダス実測データ（時別）

        Returns:
            dict: 精度指標
        """
        accuracy = {}

        # 実測データから4時～16時の統計を計算
        actual_stats = self.calculate_actual_stats(actual)

        # 温度精度
        if 'temperature_max' in forecast and 'max_temp' in actual_stats:
            accuracy['temp_max_error'] = abs(forecast['temperature_max'] - actual_stats['max_temp'])

        if 'temperature_min' in forecast and 'min_temp' in actual_stats:
            accuracy['temp_min_error'] = abs(forecast['temperature_min'] - actual_stats['min_temp'])

        # 湿度精度
        if 'humidity_min' in forecast and 'min_humidity' in actual_stats:
            accuracy['humidity_min_error'] = abs(forecast['humidity_min'] - actual_stats['min_humidity'])

        # 風速精度
        if 'wind_speed_max' in forecast and 'max_wind' in actual_stats:
            accuracy['wind_max_error'] = abs(forecast['wind_speed_max'] - actual_stats['max_wind'])

        # 降水精度（絶対的な一致度）
        if 'precipitation_sum' in forecast and 'total_precip' in actual_stats:
            forecast_rain = forecast['precipitation_sum'] > 0
            actual_rain = actual_stats['total_precip'] > 0
            accuracy['precipitation_match'] = forecast_rain == actual_rain
            accuracy['precipitation_error'] = abs(forecast['precipitation_sum'] - actual_stats['total_precip'])

        # 総合スコア（誤差が小さいほど高スコア）
        total_error = sum([
            accuracy.get('temp_max_error', 0) * 0.2,
            accuracy.get('humidity_min_error', 0) * 0.3,
            accuracy.get('wind_max_error', 0) * 0.2,
            accuracy.get('precipitation_error', 0) * 0.3
        ])

        accuracy['total_error_score'] = total_error
        accuracy['accuracy_score'] = max(0, 100 - total_error)  # 0-100スケール

        return accuracy

    def calculate_actual_stats(self, actual_hourly_data):
        """
        アメダス時別データから統計値を計算（4:00-16:00）

        Args:
            actual_hourly_data: 時別データ（dict）

        Returns:
            dict: 統計値
        """
        stats = {}

        temps = []
        humidities = []
        winds = []
        precips = []

        # 4:00～16:00のデータを抽出
        for hour_str, data in actual_hourly_data.items():
            if data and ':' in hour_str:
                hour = int(hour_str.split(':')[0])
                if 4 <= hour <= 16:
                    if 'temp' in data and data['temp'][0] is not None:
                        temps.append(data['temp'][0])
                    if 'humidity' in data and data['humidity'][0] is not None:
                        humidities.append(data['humidity'][0])
                    if 'wind' in data and data['wind'][0] is not None:
                        winds.append(data['wind'][0])
                    if 'precipitation' in data and data['precipitation'][0] is not None:
                        precips.append(data['precipitation'][0])

        if temps:
            stats['max_temp'] = max(temps)
            stats['min_temp'] = min(temps)
            stats['avg_temp'] = sum(temps) / len(temps)

        if humidities:
            stats['max_humidity'] = max(humidities)
            stats['min_humidity'] = min(humidities)
            stats['avg_humidity'] = sum(humidities) / len(humidities)

        if winds:
            stats['max_wind'] = max(winds)
            stats['avg_wind'] = sum(winds) / len(winds)

        if precips:
            stats['total_precip'] = sum(precips)
        else:
            stats['total_precip'] = 0

        return stats

    def generate_accuracy_report(self, start_date, end_date):
        """
        期間の予報精度レポートを生成

        Args:
            start_date: 開始日（datetime）
            end_date: 終了日（datetime）

        Returns:
            dict: 総合精度レポート
        """
        report = {
            'period': {
                'start': start_date.strftime("%Y-%m-%d"),
                'end': end_date.strftime("%Y-%m-%d")
            },
            'by_days_ahead': {},  # 1日前予報、2日前予報...の精度
            'by_spot': {},  # 干場ごとの精度
            'overall_accuracy': {}
        }

        # 各日の検証結果を集計
        current_date = start_date
        while current_date <= end_date:
            date_str = current_date.strftime("%Y%m%d")
            validation_file = os.path.join(self.validation_dir, f"validation_{date_str}.json")

            if os.path.exists(validation_file):
                try:
                    with open(validation_file, 'r', encoding='utf-8') as f:
                        validation = json.load(f)

                    # データを集計
                    for spot_val in validation.get('spots_validation', []):
                        spot_name = spot_val['spot_name']

                        if spot_name not in report['by_spot']:
                            report['by_spot'][spot_name] = {
                                'forecasts': [],
                                'avg_accuracy': 0
                            }

                        for forecast in spot_val.get('forecasts', []):
                            days_before = forecast['days_before']
                            accuracy = forecast['accuracy']

                            if days_before not in report['by_days_ahead']:
                                report['by_days_ahead'][days_before] = {
                                    'scores': [],
                                    'avg_score': 0
                                }

                            if 'accuracy_score' in accuracy:
                                report['by_days_ahead'][days_before]['scores'].append(accuracy['accuracy_score'])
                                report['by_spot'][spot_name]['forecasts'].append(accuracy['accuracy_score'])

                except Exception as e:
                    logging.error(f"Failed to process validation {date_str}: {e}")

            current_date += timedelta(days=1)

        # 平均値を計算
        for days_before, data in report['by_days_ahead'].items():
            if data['scores']:
                data['avg_score'] = sum(data['scores']) / len(data['scores'])
                data['count'] = len(data['scores'])

        for spot_name, data in report['by_spot'].items():
            if data['forecasts']:
                data['avg_accuracy'] = sum(data['forecasts']) / len(data['forecasts'])
                data['count'] = len(data['forecasts'])

        # 総合精度
        all_scores = []
        for data in report['by_days_ahead'].values():
            all_scores.extend(data.get('scores', []))

        if all_scores:
            report['overall_accuracy'] = {
                'avg_score': sum(all_scores) / len(all_scores),
                'total_forecasts': len(all_scores)
            }

        # レポート保存
        report_file = os.path.join(
            self.validation_dir,
            f"accuracy_report_{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}.json"
        )

        try:
            with open(report_file, 'w', encoding='utf-8') as f:
                json.dump(report, f, ensure_ascii=False, indent=2)
            logging.info(f"Accuracy report saved: {report_file}")
        except Exception as e:
            logging.error(f"Failed to save accuracy report: {e}")

        return report

def main():
    """テスト実行"""
    validator = ForecastAccuracyValidator()

    # 今日の予報精度を検証（サンプル）
    today = datetime.now()
    # result = validator.validate_forecast_accuracy(today)

    logging.info("Forecast Accuracy Validator initialized")
    logging.info(f"Nearby spots: {len(validator.nearby_spots)}")

if __name__ == '__main__':
    main()
