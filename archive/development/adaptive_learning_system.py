import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import requests
import os
import json
from sklearn.ensemble import RandomForestClassifier, VotingClassifier
from xgboost import XGBClassifier
from sklearn.model_selection import cross_val_score, train_test_split
from sklearn.metrics import classification_report, accuracy_score
import joblib
import warnings
warnings.filterwarnings('ignore')

class AdaptiveLearningSystem:
    """昆布乾燥記録の自動学習システム"""
    
    def __init__(self):
        self.record_file = "hoshiba_records.csv"
        self.spots_file = "hoshiba_spots.csv"
        self.weather_dataset = "weather_labeled_dataset.csv"
        self.model_file = "adaptive_model.pkl"
        self.quality_log = "data_quality_log.json"
        
        # データ品質基準
        self.quality_thresholds = {
            'min_radiation_for_success': 2500,    # 成功の最小日射量
            'max_radiation_for_failure': 5500,    # 失敗の最大日射量
            'min_wind_for_success': 1.0,          # 成功の最小風速
            'max_wind_for_failure': 15.0,         # 失敗の最大風速
            'suspicious_stop_radiation': 4000,    # この値以上で中止なら要注意
            'suspicious_stop_wind': 6.0           # この値以下で中止なら要注意
        }
    
    def get_weather_data_for_date(self, lat, lon, date):
        """指定日の気象データを取得"""
        try:
            url = "https://api.open-meteo.com/v1/forecast"
            params = {
                "latitude": lat,
                "longitude": lon,
                "start_date": date,
                "end_date": date,
                "hourly": "temperature_2m,relative_humidity_2m,precipitation_probability,precipitation,wind_speed_10m,wind_direction_10m,shortwave_radiation,cloud_cover",
                "timezone": "Asia/Tokyo"
            }
            
            response = requests.get(url, params=params, timeout=10)
            if response.status_code != 200:
                return None
                
            hourly_data = response.json()["hourly"]
            
            # 作業時間帯（4-16時）の気象データを集計
            work_hours = list(range(4, 17))
            
            # 朝の風（4-10時）
            morning_hours = list(range(4, 11))
            morning_winds = [hourly_data["wind_speed_10m"][h] for h in morning_hours]
            
            # 昼の日射（10-16時）
            afternoon_hours = list(range(10, 17))
            afternoon_radiation = [hourly_data["shortwave_radiation"][h] for h in afternoon_hours]
            
            # 全作業時間の気象条件
            work_temp = [hourly_data["temperature_2m"][h] for h in work_hours]
            work_humidity = [hourly_data["relative_humidity_2m"][h] for h in work_hours]
            work_precipitation = [hourly_data["precipitation_probability"][h] for h in work_hours]
            work_wind_dir = [hourly_data["wind_direction_10m"][h] for h in work_hours]
            
            weather_summary = {
                "radiation_mean": np.mean(afternoon_radiation),
                "radiation_sum": sum(afternoon_radiation),
                "windspeed_mean": np.mean(morning_winds),
                "winddirection_mean": np.mean(work_wind_dir),
                "temperature_mean": np.mean(work_temp),
                "humidity_max": max(work_humidity),
                "precipitation_max": max(work_precipitation),
                "work_hours_analyzed": len(work_hours)
            }
            
            return weather_summary
            
        except Exception as e:
            print(f"Weather data fetch error for {date}: {e}")
            return None
    
    def analyze_data_quality(self, record):
        """記録データの品質を分析"""
        quality_issues = []
        quality_score = 100
        weather = record.get('weather_data', {})
        
        if not weather:
            return {"quality_score": 0, "issues": ["No weather data available"], "recommendation": "exclude"}
        
        result = record['result']
        radiation = weather.get('radiation_sum', 0)
        wind = weather.get('windspeed_mean', 0)
        humidity = weather.get('humidity_max', 100)
        precipitation = weather.get('precipitation_max', 0)
        
        # 中止データの品質チェック
        if result == "中止":
            # 好条件での中止は疑わしい
            if (radiation > self.quality_thresholds['suspicious_stop_radiation'] and 
                wind < self.quality_thresholds['suspicious_stop_wind'] and
                humidity < 80 and precipitation < 30):
                quality_issues.append("Good conditions but stopped - possibly non-weather related")
                quality_score -= 40
            
            # 悪条件での中止は妥当
            elif (radiation < 2000 or wind > 12 or humidity > 90 or precipitation > 60):
                quality_issues.append("Stopped due to poor conditions - valid data")
                quality_score += 10
        
        # 完全乾燥データの品質チェック
        elif result == "完全乾燥":
            # 悪条件での成功は貴重なデータ
            if (radiation < 3000 or wind < 2 or humidity > 85):
                quality_issues.append("Success in challenging conditions - valuable data")
                quality_score += 20
            
            # 異常に悪い条件での成功は疑わしい
            if (radiation < 1500 or wind > 15 or humidity > 95 or precipitation > 50):
                quality_issues.append("Success in extremely poor conditions - verify accuracy")
                quality_score -= 30
        
        # 部分乾燥データは常に貴重
        elif "泣" in result:
            quality_issues.append("Partial drying - important boundary condition data")
            quality_score += 30
        
        # データの完整性チェック
        if radiation <= 0 or wind < 0:
            quality_issues.append("Invalid weather values")
            quality_score -= 50
        
        # 推奨行動の決定
        if quality_score >= 80:
            recommendation = "include_high_weight"
        elif quality_score >= 60:
            recommendation = "include_normal_weight" 
        elif quality_score >= 40:
            recommendation = "include_low_weight"
        else:
            recommendation = "exclude"
        
        return {
            "quality_score": quality_score,
            "issues": quality_issues,
            "recommendation": recommendation,
            "weather_summary": {
                "radiation": radiation,
                "wind": wind,
                "humidity": humidity,
                "precipitation": precipitation
            }
        }
    
    def process_new_records(self):
        """新しい記録を処理して学習データに追加"""
        print("Processing new records for adaptive learning...")
        
        try:
            # 既存の記録を読み込み
            if not os.path.exists(self.record_file):
                print("No records file found")
                return False
            
            records_df = pd.read_csv(self.record_file)
            spots_df = pd.read_csv(self.spots_file)
            
            # 既存の学習データセット
            if os.path.exists(self.weather_dataset):
                existing_df = pd.read_csv(self.weather_dataset)
                processed_records = set(zip(existing_df['date'], existing_df['name']))
            else:
                existing_df = pd.DataFrame()
                processed_records = set()
            
            new_data = []
            quality_log = []
            
            for _, record in records_df.iterrows():
                record_id = (record['date'], record['name'])
                
                # 既に処理済みの記録はスキップ
                if record_id in processed_records:
                    continue
                
                # 干場の座標を取得
                spot_info = spots_df[spots_df['name'] == record['name']]
                if len(spot_info) == 0:
                    print(f"Spot not found: {record['name']}")
                    continue
                
                lat = spot_info.iloc[0]['lat']
                lon = spot_info.iloc[0]['lon']
                
                # 気象データを取得
                weather_data = self.get_weather_data_for_date(lat, lon, record['date'])
                if weather_data is None:
                    print(f"Weather data not available for {record['date']}")
                    continue
                
                # データ品質を分析
                record_with_weather = dict(record)
                record_with_weather['weather_data'] = weather_data
                
                quality_analysis = self.analyze_data_quality(record_with_weather)
                
                # 品質ログに記録
                quality_log.append({
                    "date": record['date'],
                    "name": record['name'],
                    "result": record['result'],
                    "quality_score": quality_analysis['quality_score'],
                    "recommendation": quality_analysis['recommendation'],
                    "issues": quality_analysis['issues'],
                    "weather": quality_analysis['weather_summary']
                })
                
                # 学習データに追加するかどうかの判定
                if quality_analysis['recommendation'] != 'exclude':
                    new_record = {
                        "date": record['date'],
                        "name": record['name'],
                        "lat": lat,
                        "lon": lon,
                        "result": record['result'],
                        "quality_score": quality_analysis['quality_score'],
                        "data_weight": self._get_data_weight(quality_analysis['recommendation'])
                    }
                    new_record.update(weather_data)
                    new_data.append(new_record)
                    
                    print(f"Added record: {record['date']} {record['name']} - {record['result']} (Quality: {quality_analysis['quality_score']})")
            
            # 新しいデータを既存データセットに追加
            if new_data:
                new_df = pd.DataFrame(new_data)
                
                if len(existing_df) > 0:
                    combined_df = pd.concat([existing_df, new_df], ignore_index=True)
                else:
                    combined_df = new_df
                
                # 更新されたデータセットを保存
                combined_df.to_csv(self.weather_dataset, index=False)
                print(f"Added {len(new_data)} new records to training dataset")
                
                # 品質ログを保存
                self._save_quality_log(quality_log)
                
                return True
            else:
                print("No new valid records to add")
                return False
                
        except Exception as e:
            print(f"Error processing records: {e}")
            return False
    
    def _get_data_weight(self, recommendation):
        """推奨に基づいてデータの重みを設定"""
        weight_map = {
            "include_high_weight": 1.5,
            "include_normal_weight": 1.0,
            "include_low_weight": 0.5
        }
        return weight_map.get(recommendation, 1.0)
    
    def _save_quality_log(self, quality_log):
        """品質ログを保存"""
        try:
            # 既存ログの読み込み
            if os.path.exists(self.quality_log):
                with open(self.quality_log, 'r', encoding='utf-8') as f:
                    existing_log = json.load(f)
            else:
                existing_log = []
            
            # 新しいログを追加
            existing_log.extend(quality_log)
            
            # 保存
            with open(self.quality_log, 'w', encoding='utf-8') as f:
                json.dump(existing_log, f, ensure_ascii=False, indent=2)
                
        except Exception as e:
            print(f"Error saving quality log: {e}")
    
    def retrain_model(self):
        """データセットを使用してモデルを再訓練"""
        print("Retraining model with updated dataset...")
        
        try:
            if not os.path.exists(self.weather_dataset):
                print("No training dataset available")
                return False
            
            df = pd.read_csv(self.weather_dataset)
            
            if len(df) < 20:
                print(f"Insufficient data for training: {len(df)} records")
                return False
            
            # データクリーニング
            df = df.dropna(subset=["radiation_sum", "windspeed_mean", "result"])
            
            # 疑わしい中止データのフィルタリング（改良版）
            reference_df = df[df["result"].str.contains("泣", na=False)]
            if len(reference_df) > 0:
                ref_radiation = reference_df["radiation_sum"].median()
                ref_wind = reference_df["windspeed_mean"].median()
                
                # 品質スコアも考慮した高度なフィルタリング
                problematic_stops = df[
                    (df["result"] == "中止") &
                    (df["radiation_sum"] > ref_radiation * 1.2) &
                    (df["windspeed_mean"] < ref_wind * 0.8) &
                    (df.get("quality_score", 100) < 70)  # 品質スコアが低い
                ]
                
                if len(problematic_stops) > 0:
                    print(f"Filtering {len(problematic_stops)} problematic stop records")
                    df = df.drop(index=problematic_stops.index)
            
            # ラベル作成（改良版）
            df['target'] = 0  # デフォルトは失敗
            
            # 完全乾燥は成功
            df.loc[df['result'].str.contains('完全乾燥', na=False), 'target'] = 1
            
            # 部分乾燥は条件次第で成功とみなす（改良点）
            partial_df = df[df['result'].str.contains('泣', na=False)]
            if len(partial_df) > 0:
                # 部分乾燥の中でも比較的良い条件のものは成功とみなす
                good_partial = partial_df[
                    (partial_df['radiation_sum'] > partial_df['radiation_sum'].median()) &
                    (partial_df['windspeed_mean'] > partial_df['windspeed_mean'].median())
                ]
                df.loc[good_partial.index, 'target'] = 1
            
            # 特徴量の設定
            available_features = ["radiation_sum", "windspeed_mean"]
            if "radiation_mean" in df.columns:
                available_features.append("radiation_mean")
            if "winddirection_mean" in df.columns:
                available_features.append("winddirection_mean")
            if "humidity_max" in df.columns:
                available_features.append("humidity_max")
            if "temperature_mean" in df.columns:
                available_features.append("temperature_mean")
            
            X = df[available_features]
            y = df['target']
            
            # サンプル重みの適用
            sample_weights = df.get('data_weight', pd.Series([1.0] * len(df)))
            
            print(f"Training with {len(X)} samples, {len(available_features)} features")
            print(f"Success rate: {y.mean():.3f}")
            print(f"Features: {available_features}")
            
            # モデル訓練（重み付きサンプリング対応）
            rf_model = RandomForestClassifier(
                n_estimators=100,
                max_depth=7,
                min_samples_split=3,
                min_samples_leaf=2,
                random_state=42
            )
            
            xgb_model = XGBClassifier(
                n_estimators=100,
                max_depth=5,
                learning_rate=0.1,
                random_state=42,
                eval_metric='logloss'
            )
            
            # 重み付きで訓練
            rf_model.fit(X, y, sample_weight=sample_weights)
            xgb_model.fit(X, y, sample_weight=sample_weights)
            
            # アンサンブルモデル
            ensemble = VotingClassifier(
                estimators=[('rf', rf_model), ('xgb', xgb_model)],
                voting='soft'
            )
            ensemble.fit(X, y, sample_weight=sample_weights)
            
            # 性能評価
            cv_scores = cross_val_score(ensemble, X, y, cv=min(5, len(X)//4), scoring='accuracy')
            print(f"Cross-validation accuracy: {cv_scores.mean():.3f} (+/- {cv_scores.std()*2:.3f})")
            
            # モデルの保存
            model_data = {
                'model': ensemble,
                'features': available_features,
                'training_size': len(X),
                'success_rate': y.mean(),
                'cv_accuracy': cv_scores.mean(),
                'cv_std': cv_scores.std(),
                'last_updated': datetime.now().isoformat(),
                'adaptive_learning': True
            }
            
            joblib.dump(model_data, self.model_file)
            print(f"Model saved to {self.model_file}")
            
            return True
            
        except Exception as e:
            print(f"Error retraining model: {e}")
            return False
    
    def get_data_quality_summary(self):
        """データ品質の要約を取得"""
        try:
            if not os.path.exists(self.quality_log):
                return {"error": "No quality log available"}
            
            with open(self.quality_log, 'r', encoding='utf-8') as f:
                quality_log = json.load(f)
            
            if not quality_log:
                return {"error": "Empty quality log"}
            
            total_records = len(quality_log)
            high_quality = sum(1 for log in quality_log if log['quality_score'] >= 80)
            medium_quality = sum(1 for log in quality_log if 60 <= log['quality_score'] < 80)
            low_quality = sum(1 for log in quality_log if 40 <= log['quality_score'] < 60)
            excluded = sum(1 for log in quality_log if log['quality_score'] < 40)
            
            # 結果別の統計
            result_stats = {}
            for log in quality_log:
                result = log['result']
                if result not in result_stats:
                    result_stats[result] = {'count': 0, 'avg_quality': 0, 'total_quality': 0}
                result_stats[result]['count'] += 1
                result_stats[result]['total_quality'] += log['quality_score']
            
            for result in result_stats:
                result_stats[result]['avg_quality'] = result_stats[result]['total_quality'] / result_stats[result]['count']
            
            return {
                "total_records": total_records,
                "quality_distribution": {
                    "high_quality (80+)": high_quality,
                    "medium_quality (60-79)": medium_quality,
                    "low_quality (40-59)": low_quality,
                    "excluded (<40)": excluded
                },
                "result_statistics": result_stats,
                "latest_update": max(log.get('date', '') for log in quality_log)
            }
            
        except Exception as e:
            return {"error": f"Error reading quality log: {e}"}

def main():
    """自動学習システムのメイン実行"""
    print("=== Adaptive Learning System ===")
    
    learning_system = AdaptiveLearningSystem()
    
    # 新しい記録を処理
    print("Step 1: Processing new records...")
    new_data_added = learning_system.process_new_records()
    
    if new_data_added:
        print("Step 2: Retraining model...")
        retrain_success = learning_system.retrain_model()
        
        if retrain_success:
            print("✓ Model successfully retrained with new data")
        else:
            print("✗ Model retraining failed")
    else:
        print("No new data to process, skipping retraining")
    
    # データ品質要約を表示
    print("\nStep 3: Data quality summary...")
    quality_summary = learning_system.get_data_quality_summary()
    
    if "error" not in quality_summary:
        print(f"Total records processed: {quality_summary['total_records']}")
        print("Quality distribution:")
        for quality_level, count in quality_summary['quality_distribution'].items():
            print(f"  {quality_level}: {count}")
        
        print("Result statistics:")
        for result, stats in quality_summary['result_statistics'].items():
            print(f"  {result}: {stats['count']} records (avg quality: {stats['avg_quality']:.1f})")
    else:
        print(f"Quality summary error: {quality_summary['error']}")
    
    print("\n=== Adaptive Learning Complete ===")

if __name__ == "__main__":
    main()