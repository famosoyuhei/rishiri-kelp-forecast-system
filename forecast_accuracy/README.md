# 予報精度分析システム

アメダス沓形の実測データを使って、12干場の予報精度を継続的に分析するシステムです。

## 📁 ファイル構成

```
forecast_accuracy/
├── config.py                      # 設定ファイル（干場リスト、閾値、API設定）
├── database.py                    # データベーススキーマ定義
├── daily_forecast_collector.py   # 毎日の予報データ収集
├── amedas_data_fetcher.py        # アメダス実測データ取得
├── accuracy_analyzer.py          # 予報精度分析
└── forecast_accuracy.db          # SQLiteデータベース
```

## 🚀 使用方法

### 1. 予報データの収集

毎日の予報データ（1-6日先）を収集してデータベースに保存します。

```bash
python daily_forecast_collector.py
```

**実行タイミング**: 毎日 6:00 (cron: `0 6 * * *`)

**処理内容**:
- 12干場の1-6日先予報を取得（`/api/forecast` エンドポイント使用）
- `forecast_archive` テーブルに保存
- 最高/最低気温、最低湿度、平均風速、降水量、乾燥スコアを記録

**出力例**:
```
Total spots: 12
Successful: 12
Failed: 0
Total records saved: 72  (12干場 × 6日分)
```

### 2. アメダス実測データの取得

アメダス沓形の実測データを取得してデータベースに保存します。

```bash
python amedas_data_fetcher.py [YYYY-MM-DD]
```

**実行タイミング**: 毎日 22:00 (cron: `0 22 * * *`)

**処理内容**:
- 気象庁APIから当日（または指定日）のアメダスデータ取得
- 時間別データから日次統計を計算
- `amedas_actual` テーブルに保存

**注意事項**:
- ⚠️ **アメダスIDの確認が必要**: 現在の設定（ID: 91196）では404エラーが発生
- 正しいアメダス沓形のIDを `config.py` で設定する必要があります
- 気象庁の公式サイトまたはアメダス観測所一覧で確認してください

**出力例**:
```
Amedas Data - 2025-10-03
Max Temp: 18.5°C
Min Temp: 12.3°C
Min Humidity: 65%
Avg Wind: 3.2 m/s
Max Wind: 5.8 m/s
Precipitation: 0.0 mm
Sunshine Hours: 8.5 h
```

### 3. 予報精度の分析

予報と実測を比較して精度を分析します。

```bash
python accuracy_analyzer.py [YYYY-MM-DD]
```

**実行タイミング**: 毎日 23:00 (cron: `0 23 * * *`)

**処理内容**:
- 指定日（デフォルトは昨日）の実測データを取得
- 1-6日前に発表された予報データと比較
- 誤差計算（気温、湿度、風速）
- 降水有無の的中判定
- 乾燥可否判定の的中/不的中
- `accuracy_analysis` テーブルに保存

**出力例**:
```
Accuracy Analysis - 2025-10-03
Total analyses: 72
Successful: 72
Failed: 0

Accuracy by Forecast Days:
  1d ahead: 12 analyses, 91.7% drying forecast accuracy, 100.0% precipitation accuracy
  2d ahead: 12 analyses, 83.3% drying forecast accuracy, 91.7% precipitation accuracy
  3d ahead: 12 analyses, 75.0% drying forecast accuracy, 83.3% precipitation accuracy
  4d ahead: 12 analyses, 66.7% drying forecast accuracy, 75.0% precipitation accuracy
  5d ahead: 12 analyses, 58.3% drying forecast accuracy, 66.7% precipitation accuracy
  6d ahead: 12 analyses, 50.0% drying forecast accuracy, 58.3% precipitation accuracy
```

## 📊 データベース構造

### forecast_archive（予報データ）
- spot_name: 干場名
- forecast_date: 予報発表日
- target_date: 予報対象日
- days_ahead: 何日先の予報か（1-6）
- temp_max, temp_min: 予報気温
- humidity_min: 予報最低湿度
- wind_speed_avg: 予報平均風速
- precipitation: 予報降水量
- drying_score: 乾燥適性スコア

### amedas_actual（実測データ）
- observation_date: 観測日
- temp_max, temp_min: 実測気温
- humidity_min: 実測最低湿度
- wind_speed_avg: 実測平均風速
- precipitation: 実測降水量
- sunshine_hours: 日照時間

### accuracy_analysis（精度分析）
- target_date: 対象日
- days_ahead: 何日前の予報か
- temp_max_error, temp_min_error: 気温誤差
- humidity_error: 湿度誤差
- wind_error: 風速誤差
- precipitation_hit: 降水有無的中
- forecast_correct: 乾燥可否予報的中

## 🎯 対象干場（12干場）

泉町エリアの近傍干場（アメダス沓形から500m以内）:

1. H_1782_1394 - 距離21m ⭐ 最優先
2. H_1795_1393 - 距離123m
3. H_1795_1395 - 距離125m
4. H_1790_1377 - 距離156m
5. H_1798_1396 - 距離160m
6. H_1799_1392 - 距離170m
7. H_1788_1372 - 距離183m
8. H_1804_1404 - 距離236m
9. H_1762_1377 - 距離277m
10. H_1811_1399 - 距離302m
11. H_1817_1402 - 375m
12. H_1818_1416 - 420m

## 📏 乾燥判定閾値

実測データ（H_1631_1434）に基づく絶対条件:

- **降水量**: 0mm（絶対条件）
- **最低湿度**: ≤ 94%（絶対条件）
- **平均風速**: ≥ 2.0m/s（絶対条件）

出典: `STAGE_WEIGHT_ANALYSIS.md`

## 🔧 テスト

### 予報収集のテスト
```bash
python test_collector.py
```

### アメダスデータ取得のテスト
```bash
python test_amedas.py
```

## ⚙️ 自動実行設定（cron）

```bash
# 毎日6時: 予報データ収集
0 6 * * * cd /path/to/forecast_accuracy && python daily_forecast_collector.py >> collector.log 2>&1

# 毎日22時: アメダスデータ取得
0 22 * * * cd /path/to/forecast_accuracy && python amedas_data_fetcher.py >> amedas.log 2>&1

# 毎日23時: 精度分析
0 23 * * * cd /path/to/forecast_accuracy && python accuracy_analyzer.py >> analyzer.log 2>&1
```

## 🐛 既知の問題

### アメダスID未確認
- 現在の設定（ID: 91196）では気象庁APIが404エラーを返します
- 正しいアメダス沓形のIDを確認して `config.py` を更新する必要があります
- 気象庁の公式サイトでアメダス観測所一覧を確認してください

### 文字エンコーディング
- Windows環境でUnicode文字（✓など）の出力時にエラーが発生する場合があります
- ログ出力には影響しませんが、コンソール出力が一部表示されない可能性があります

## 📝 今後の拡張

- [ ] 精度レポート自動生成（週次/月次）
- [ ] グラフ可視化（予報日数別の精度推移）
- [ ] Webダッシュボード統合
- [ ] 閾値の最適化（機械学習）
- [ ] 季節別精度分析

## 📚 参考ドキュメント

- `KUTSUGATA_ACCURATE_REPORT.md`: 12干場のリストと分析
- `STAGE_WEIGHT_ANALYSIS.md`: 乾燥判定閾値の根拠
- `FORECAST_ACCURACY_SYSTEM_DESIGN.md`: システム設計書
- `database.py`: データベーススキーマ

---

**作成日**: 2025-10-04
**バージョン**: 1.0
