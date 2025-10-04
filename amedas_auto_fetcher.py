#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
アメダス沓形（ID: 11151）の時別データ自動取得システム
毎日16時に4時～16時のデータを取得
"""
import requests
import json
import os
from datetime import datetime, timedelta
import logging

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('amedas_auto_fetcher.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

class AmedasAutoFetcher:
    """アメダス時別データ自動取得システム"""

    def __init__(self):
        self.amedas_id = "11151"  # 沓形
        self.data_dir = "amedas_data"
        self.ensure_data_directory()

    def ensure_data_directory(self):
        """データ保存ディレクトリの作成"""
        if not os.path.exists(self.data_dir):
            os.makedirs(self.data_dir)
            logging.info(f"Created data directory: {self.data_dir}")

    def fetch_hourly_data(self, target_date=None):
        """
        アメダス時別データを取得

        Args:
            target_date: 取得対象日（datetime）。Noneの場合は今日

        Returns:
            dict: 取得したデータ、エラー時はNone
        """
        if target_date is None:
            target_date = datetime.now()

        # 気象庁アメダスAPIのURL構築
        # 例: https://www.jma.go.jp/bosai/amedas/data/map/20251004.json
        date_str = target_date.strftime("%Y%m%d")
        url = f"https://www.jma.go.jp/bosai/amedas/data/map/{date_str}.json"

        try:
            logging.info(f"Fetching AMeDAS data from: {url}")
            response = requests.get(url, timeout=30)
            response.raise_for_status()

            all_data = response.json()

            # 沓形（11151）のデータを抽出
            if self.amedas_id in all_data:
                kutsugata_data = all_data[self.amedas_id]
                logging.info(f"Successfully fetched data for AMeDAS ID {self.amedas_id}")
                return kutsugata_data
            else:
                logging.warning(f"AMeDAS ID {self.amedas_id} not found in response")
                return None

        except requests.exceptions.RequestException as e:
            logging.error(f"Failed to fetch AMeDAS data: {e}")
            return None
        except json.JSONDecodeError as e:
            logging.error(f"Failed to parse JSON response: {e}")
            return None

    def fetch_time_series_data(self, target_date=None):
        """
        時系列データを取得（時刻ごとのデータ）

        Args:
            target_date: 取得対象日（datetime）。Noneの場合は今日

        Returns:
            dict: 時刻ごとのデータ
        """
        if target_date is None:
            target_date = datetime.now()

        hourly_data = {}

        # 4時から16時まで（作業時間帯）のデータを取得
        for hour in range(4, 17):  # 4時～16時
            try:
                # 時刻指定でデータ取得
                # 例: https://www.jma.go.jp/bosai/amedas/data/map/20251004040000.json
                timestamp = target_date.replace(hour=hour, minute=0, second=0)
                timestamp_str = timestamp.strftime("%Y%m%d%H0000")
                url = f"https://www.jma.go.jp/bosai/amedas/data/map/{timestamp_str}.json"

                logging.info(f"Fetching data for {hour}:00 from: {url}")
                response = requests.get(url, timeout=30)
                response.raise_for_status()

                all_data = response.json()

                if self.amedas_id in all_data:
                    hourly_data[f"{hour:02d}:00"] = all_data[self.amedas_id]
                    logging.info(f"Successfully fetched data for {hour}:00")
                else:
                    logging.warning(f"No data for {hour}:00")
                    hourly_data[f"{hour:02d}:00"] = None

            except Exception as e:
                logging.error(f"Failed to fetch data for {hour}:00: {e}")
                hourly_data[f"{hour:02d}:00"] = None

        return hourly_data

    def save_daily_data(self, data, target_date=None):
        """
        取得したデータをJSONファイルに保存

        Args:
            data: 保存するデータ
            target_date: 対象日（datetime）
        """
        if target_date is None:
            target_date = datetime.now()

        date_str = target_date.strftime("%Y%m%d")
        filename = os.path.join(self.data_dir, f"amedas_{self.amedas_id}_{date_str}.json")

        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump({
                    'date': date_str,
                    'amedas_id': self.amedas_id,
                    'location': 'kutsugata',
                    'fetched_at': datetime.now().isoformat(),
                    'data': data
                }, f, ensure_ascii=False, indent=2)

            logging.info(f"Saved data to: {filename}")
            return True

        except Exception as e:
            logging.error(f"Failed to save data: {e}")
            return False

    def run_daily_fetch(self):
        """
        毎日16時に実行される処理
        今日の4時～16時のデータを取得
        """
        logging.info("=" * 80)
        logging.info("Starting daily AMeDAS data fetch (4:00-16:00)")
        logging.info("=" * 80)

        today = datetime.now()

        # 時系列データを取得
        hourly_data = self.fetch_time_series_data(today)

        if hourly_data:
            # データを保存
            success = self.save_daily_data(hourly_data, today)

            if success:
                # 簡易統計を出力
                self.print_summary(hourly_data)
                logging.info("Daily fetch completed successfully")
                return True
            else:
                logging.error("Failed to save fetched data")
                return False
        else:
            logging.error("No data fetched")
            return False

    def print_summary(self, hourly_data):
        """取得データの簡易統計を出力"""
        logging.info("-" * 80)
        logging.info("Data Summary (4:00-16:00)")
        logging.info("-" * 80)

        valid_count = sum(1 for v in hourly_data.values() if v is not None)
        total_count = len(hourly_data)

        logging.info(f"Valid data points: {valid_count}/{total_count}")

        # サンプルデータを表示
        for time_str, data in list(hourly_data.items())[:3]:
            if data:
                temp = data.get('temp', ['N/A'])[0] if 'temp' in data else 'N/A'
                humidity = data.get('humidity', ['N/A'])[0] if 'humidity' in data else 'N/A'
                wind = data.get('wind', ['N/A'])[0] if 'wind' in data else 'N/A'
                logging.info(f"{time_str}: Temp={temp}°C, Humidity={humidity}%, Wind={wind}m/s")

        logging.info("-" * 80)

def main():
    """テスト実行"""
    fetcher = AmedasAutoFetcher()
    fetcher.run_daily_fetch()

if __name__ == '__main__':
    main()
