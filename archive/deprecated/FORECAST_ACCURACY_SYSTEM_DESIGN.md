# 予報精度分析システム設計書

## 📋 システム概要

アメダス沓形の実測データを使用して、12干場（泉町エリア）の予報精度を継続的に分析するシステム。

---

## 🎯 目的

1. **予報精度の定量評価**
   - 1日前～6日前の予報と実測値を比較
   - 予報日数ごとの精度を測定

2. **閾値の検証**
   - 降水量0mm、湿度≤94%、風速≥2.0m/sの妥当性確認
   - 実測データに基づく最適閾値の導出

3. **モデル改善**
   - 精度の低い要素を特定
   - 予報アルゴリズムの継続的改善

---

## 🏗️ システム構成

### データフロー

```
[1] 毎日のデータ取得
    ↓
[2] 予報データの保存（1-6日先の予報を記録）
    ↓
[3] 実測データの取得（アメダス沓形）
    ↓
[4] 予報vs実測の比較分析
    ↓
[5] 精度レポートの生成
```

---

## 📊 データベース設計

### テーブル1: forecast_archive
予報データを保存（発表日ごとに1-6日先の予報を記録）

| カラム名 | 型 | 説明 |
|---------|---|------|
| id | INTEGER | 主キー |
| spot_name | TEXT | 干場名（12干場のいずれか） |
| forecast_date | DATE | 予報発表日 |
| target_date | DATE | 予報対象日 |
| days_ahead | INTEGER | 何日先の予報か（1-6） |
| temp_max | REAL | 予報最高気温 |
| temp_min | REAL | 予報最低気温 |
| humidity_min | REAL | 予報最低湿度 |
| wind_speed_avg | REAL | 予報平均風速 |
| precipitation | REAL | 予報降水量 |
| drying_score | REAL | 乾燥適性スコア |
| created_at | TIMESTAMP | 記録日時 |

### テーブル2: amedas_actual
アメダス沓形の実測データ

| カラム名 | 型 | 説明 |
|---------|---|------|
| id | INTEGER | 主キー |
| observation_date | DATE | 観測日 |
| temp_max | REAL | 実測最高気温 |
| temp_min | REAL | 実測最低気温 |
| humidity_min | REAL | 実測最低湿度 |
| wind_speed_avg | REAL | 実測平均風速 |
| precipitation | REAL | 実測降水量 |
| sunshine_hours | REAL | 日照時間 |
| created_at | TIMESTAMP | 記録日時 |

### テーブル3: accuracy_analysis
精度分析結果

| カラム名 | 型 | 説明 |
|---------|---|------|
| id | INTEGER | 主キー |
| analysis_date | DATE | 分析日 |
| target_date | DATE | 対象日 |
| days_ahead | INTEGER | 何日前の予報か（1-6） |
| temp_max_error | REAL | 最高気温誤差 |
| humidity_error | REAL | 湿度誤差 |
| wind_error | REAL | 風速誤差 |
| precipitation_hit | BOOLEAN | 降水有無的中 |
| drying_success_forecast | BOOLEAN | 乾燥可能予報 |
| drying_success_actual | BOOLEAN | 実際に乾燥可能だったか |
| forecast_correct | BOOLEAN | 予報的中 |
| created_at | TIMESTAMP | 記録日時 |

---

## 🔧 実装コンポーネント

### 1. daily_forecast_collector.py
**機能**: 毎日の予報データを収集・保存

```python
# 毎日実行（cron: 0 6 * * *）
# 1. 12干場の1-6日先予報を取得
# 2. forecast_archiveテーブルに保存
```

### 2. amedas_data_fetcher.py
**機能**: アメダス沓形の実測データを取得

```python
# 毎日実行（cron: 0 22 * * *）
# 1. 気象庁APIから当日の実測データ取得
# 2. amedas_actualテーブルに保存
```

### 3. accuracy_analyzer.py
**機能**: 予報精度を分析

```python
# 毎日実行（cron: 0 23 * * *）
# 1. 1-6日前の予報を実測と比較
# 2. 誤差を計算
# 3. accuracy_analysisテーブルに保存
```

### 4. accuracy_reporter.py
**機能**: 精度レポートを生成

```python
# 週次実行（cron: 0 0 * * 0）
# 1. 直近30日の精度データを集計
# 2. 予報日数別の精度レポート生成
# 3. 改善提案の出力
```

---

## 📈 評価指標

### 1. 基本統計
- **MAE (Mean Absolute Error)**: 平均絶対誤差
  - 気温誤差: |予報値 - 実測値|の平均
  - 湿度誤差: |予報値 - 実測値|の平均
  - 風速誤差: |予報値 - 実測値|の平均

### 2. 降水予報精度
- **適中率**: (的中数 / 総予報数) × 100%
- **見逃し率**: (降水あったのに予報なし / 降水日数) × 100%
- **空振り率**: (降水予報したが降水なし / 予報日数) × 100%

### 3. 乾燥可否予報精度
- **正解率**: (正しい予報数 / 総予報数) × 100%
- **False Positive**: 乾燥可能と予報したが実際は不可
- **False Negative**: 乾燥不可と予報したが実際は可能

---

## 🎯 対象干場（12干場）

泉町エリアの近傍干場（距離500m以内）:

1. H_1782_1394 - 距離21m ⭐
2. H_1795_1393 - 距離123m
3. H_1795_1395 - 距離125m
4. H_1790_1377 - 距離156m
5. H_1798_1396 - 距離160m
6. H_1799_1392 - 距離170m
7. H_1788_1372 - 距離183m
8. H_1804_1404 - 距離236m
9. H_1762_1377 - 距離277m
10. H_1811_1399 - 距離302m
11. H_1817_1402 - 距離375m
12. H_1818_1416 - 420m

---

## 🚀 実装ステップ

### Phase 1: データ収集基盤（1週間）
- [ ] SQLiteデータベース設計・作成
- [ ] daily_forecast_collector.py 実装
- [ ] amedas_data_fetcher.py 実装
- [ ] データ取得の自動化（cron設定）

### Phase 2: 分析機能（1週間）
- [ ] accuracy_analyzer.py 実装
- [ ] 精度指標の計算ロジック
- [ ] 統計分析機能

### Phase 3: レポート機能（3日）
- [ ] accuracy_reporter.py 実装
- [ ] 可視化（グラフ生成）
- [ ] Webダッシュボード

### Phase 4: 運用・改善（継続）
- [ ] 30日間のデータ蓄積
- [ ] 精度分析レポート
- [ ] 閾値の最適化
- [ ] 予報モデルの改善

---

## 📊 期待される成果

### 短期（1ヶ月後）
- 1-6日先予報の精度データ（30日分）
- 予報日数ごとの誤差傾向の把握
- 問題点の特定

### 中期（3ヶ月後）
- 季節による精度変動の分析
- 最適閾値の導出
- 予報アルゴリズムの改善

### 長期（1年後）
- 年間を通じた精度データ
- 昆布漁期（6-8月）の高精度予報
- 他エリアへの展開

---

## 🔒 データ保持ポリシー

- **予報データ**: 永久保存（分析用）
- **実測データ**: 永久保存（気象記録）
- **分析結果**: 永久保存（精度改善用）
- **バックアップ**: 週次（日曜0時）

---

## 🌐 API仕様

### 気象庁API（アメダスデータ取得）
```
https://www.jma.go.jp/bosai/amedas/data/point/{AMEDAS_ID}/{YYYYMMDD}.json
```

### 内部予報API
```
GET /api/forecast?lat=45.1784&lon=141.1395&days=6
```

---

**作成日**: 2025-10-04
**バージョン**: 1.0
**想定運用開始**: 2025年昆布漁期（6月～）
