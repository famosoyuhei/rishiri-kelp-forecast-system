# クイックスタートガイド

予報精度分析システムの簡単な使い方

## ⚡ 即座に試す

### 1. 予報データを収集（テスト）

```bash
cd forecast_accuracy
python test_collector.py
```

**期待される結果**:
```
Testing forecast collection for: H_1782_1394
Location: lat=45.1782154, lon=141.1394976

Fetching forecast data...
OK - Forecast data fetched successfully
  Status: success
  Forecasts available: 7 days

Saving to database...
OK - Saved 6 forecast records

OK - Test completed successfully
```

### 2. 全12干場の予報を収集

```bash
python daily_forecast_collector.py
```

**期待される結果**:
```
Total spots: 12
Successful: 12
Failed: 0
Total records saved: 72
```

**実行時間**: 約1-2分（API呼び出し12回 + 待機時間）

### 3. データベース確認

```bash
python -c "import sqlite3; conn = sqlite3.connect('forecast_accuracy.db'); cursor = conn.cursor(); cursor.execute('SELECT COUNT(*) FROM forecast_archive'); print(f'Forecast records: {cursor.fetchone()[0]}'); conn.close()"
```

**期待される結果**:
```
Forecast records: 72
```

## 🔧 アメダスデータ取得の設定

### 重要: アメダスIDの確認が必要

現在の設定ではアメダスIDが正しくないため、実測データの取得ができません。

**対処方法**:
1. `AMEDAS_ID_GUIDE.md` を参照
2. 正しい沓形のアメダスIDを確認
3. `config.py` の `AMEDAS_KUTSUGATA['id']` を更新

### テスト実行

IDを更新したら:

```bash
python test_amedas.py
```

または、特定の日付を指定:

```bash
python amedas_data_fetcher.py 2025-10-03
```

## 📊 精度分析の実行

アメダスデータが蓄積されたら、精度分析が可能になります:

```bash
python accuracy_analyzer.py
```

または、特定の日付を分析:

```bash
python accuracy_analyzer.py 2025-10-03
```

## 🔄 毎日の運用フロー

### 理想的な実行順序

1. **朝6時**: 予報データ収集
   ```bash
   python daily_forecast_collector.py
   ```

2. **夜22時**: アメダスデータ取得
   ```bash
   python amedas_data_fetcher.py
   ```

3. **夜23時**: 精度分析
   ```bash
   python accuracy_analyzer.py
   ```

### Cron設定例

```cron
# 予報精度分析システム
0 6 * * * cd /path/to/forecast_accuracy && python daily_forecast_collector.py >> logs/collector.log 2>&1
0 22 * * * cd /path/to/forecast_accuracy && python amedas_data_fetcher.py >> logs/amedas.log 2>&1
0 23 * * * cd /path/to/forecast_accuracy && python accuracy_analyzer.py >> logs/analyzer.log 2>&1
```

## 📈 データの確認

### SQLiteでデータベースを直接確認

```bash
sqlite3 forecast_accuracy.db
```

```sql
-- 予報データの件数
SELECT COUNT(*) FROM forecast_archive;

-- 最新の予報データ
SELECT spot_name, target_date, days_ahead, temp_max, humidity_min, wind_speed_avg
FROM forecast_archive
ORDER BY created_at DESC
LIMIT 10;

-- 実測データの件数
SELECT COUNT(*) FROM amedas_actual;

-- 精度分析結果の件数
SELECT COUNT(*) FROM accuracy_analysis;

-- 日数別の予報精度
SELECT days_ahead,
       COUNT(*) as total,
       SUM(CASE WHEN forecast_correct = 1 THEN 1 ELSE 0 END) as correct,
       ROUND(100.0 * SUM(CASE WHEN forecast_correct = 1 THEN 1 ELSE 0 END) / COUNT(*), 1) as accuracy_pct
FROM accuracy_analysis
GROUP BY days_ahead
ORDER BY days_ahead;
```

## 🐛 トラブルシューティング

### エラー: "Connection refused"

**原因**: 予報APIサーバー（start.py）が起動していない

**解決**:
```bash
cd ..
python start.py
```

### エラー: "404 Not Found" (Amedas)

**原因**: アメダスIDが間違っている

**解決**: `AMEDAS_ID_GUIDE.md` を参照してIDを修正

### エラー: "No actual data available"

**原因**: アメダスデータが取得できていない

**解決**:
1. アメダスデータを先に取得
2. `python amedas_data_fetcher.py [日付]`

### Unicode文字表示エラー

**原因**: Windows環境の文字エンコーディング

**影響**: なし（ログには記録される）

**解決**: 気にしなくてOK

## 📊 期待される成果

### 1週間後
- 7日分の予報データ（12干場 × 6日先 × 7日 = 504件）
- 7日分の実測データ（7件）
- 7日分の精度分析（12干場 × 6日先 × 7日 = 504件）

### 1ヶ月後
- 予報日数ごとの精度傾向が見えてくる
- 乾燥判定の的中率が計算できる
- 問題のある気象要素（気温/湿度/風速）の特定

### 3ヶ月後
- 統計的に有意な精度データ
- 季節による精度変動の分析
- 閾値の最適化の検討が可能

## 📝 次のステップ

1. ✅ 予報データ収集の自動化
2. ⚠️ アメダスIDの確認・修正
3. ⏳ データの蓄積（最低1週間）
4. ⏳ 精度分析レポートの作成
5. ⏳ Webダッシュボードの統合

---

**質問・問題がある場合**: README.md の詳細ドキュメントを参照
