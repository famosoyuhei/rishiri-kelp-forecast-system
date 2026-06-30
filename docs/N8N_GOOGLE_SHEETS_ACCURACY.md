# n8n + Google Sheets 精度可視化導入メモ

## 目的

既存アプリの予報・通知・記録機能を壊さず、n8nから読み取り専用APIを呼び出してGoogle Sheetsへ精度ログを蓄積する。

## 第1段階の方針

- Flask本体の予報計算・記録保存・LINE通知ロジックは変更しない。
- n8nは外部オーケストレーターとして定時実行だけを担当する。
- 毎日16:05 JSTにアプリ本体が全334地点（全干場、アメダス、山頂）の予報履歴をRedisへ保存する。
- アメダス2地点の04:00-16:00実測は03:00 JSTに前日分をRedisへ保存する。
- 全地点メッシュのナウキャスト降水実測は04:00-16:00 JSTに10分間隔でRedisへ保存する。
- n8nは16:20 JST以降に保存済み予報履歴を読み取り、Google Sheetsの `forecast_snapshot` へ転記する。
- Google Sheetsには行データを保存し、ピボットテーブルやグラフで可視化する。
- 個別干場は1干場1シートにせず、`spot_detail` のプルダウンで切り替える。

## 同梱ファイル

- Google Sheets整形Apps Script: `docs/google_sheets_accuracy_dashboard_apps_script.gs`（推奨・無料）
- n8n構成ブループリント: `docs/n8n_accuracy_google_sheets_workflow_blueprint.json`
- Excel雛形: `outputs/n8n_google_sheets_template/rishiri_accuracy_dashboard_template.xlsx`（任意・Excel契約不要）
- ダッシュボードプレビュー: `outputs/n8n_google_sheets_template/accuracy_dashboard_preview.png`

Excelは必須ではない。無料のGoogle Sheetsで空のスプレッドシートを作成し、Apps Scriptの `setupRishiriAccuracyDashboard()` を実行すれば必要なタブとグラフを作成できる。

## 使用API

### 予報履歴スナップショット

```text
GET /api/forecast/snapshots/sheets?max_days_ahead=6
```

主なクエリ:

- `forecast_date`: 任意。`YYYY-MM-DD` または `YYYYMMDD`。省略時は今日。
- `max_days_ahead`: 0〜6。既定は6。
- `spot`: 任意。`H_1631_1434` など単一地点に絞る。

返却形式:

- `columns`: Google Sheetsに入れる列名
- `summary`: 期待行数、実際の行数、欠落数、カバレッジ
- `rows`: 1行1地点1予報日数の配列

このAPIはOpen-Meteoを呼ばず、すでにRedisまたはローカル履歴へ保存済みの予報だけを返す。n8nから `/api/forecast` を全地点へ連打しない。

### アメダス実測

```text
GET /api/observations/amedas/sheets
```

主なクエリ:

- `date`: 任意。`YYYY-MM-DD` または `YYYYMMDD`。省略時は昨日。

返却形式:

- 沓形、本泊の2地点
- 04:00-16:00 JSTの13時間
- 気温、湿度、風速、降水量
- 期待行数は `2地点 × 13時間 = 26行`

### ナウキャストメッシュ実測

```text
GET /api/observations/nowcast/sheets
```

主なクエリ:

- `date`: 任意。`YYYY-MM-DD` または `YYYYMMDD`。省略時は今日。
- `spot`: 任意。`H_1631_1434` など単一地点に絞る。

返却形式:

- 04:00-16:00 JSTにRedisへ保存されたナウキャストスナップショット
- 全地点の所属250mメッシュ降水強度 `precip_mmh`
- JMA nowcastはここでは過去アーカイブ取得しないため、当日の04:00-16:00にスケジューラーが動いていることが前提

### Raw 精度行データ

```text
GET /api/validation/accuracy/sheets?days=90
```

主なクエリ:

- `days`: 取得対象日数。1〜365日。既定は90。
- `spot`: 任意。`H_1631_1434` など単一干場に絞る。
- `has_record`: 任意。`true` で乾燥記録ありの行のみ、`false` で記録なしのみ。

返却形式:

- `columns`: Google Sheetsに入れる列名
- `summary`: 件数、降水的中率、乾燥判定的中率
- `rows`: 1行1レコードの配列

### 集計済みデータ

```text
GET /api/validation/accuracy/sheets/summary?days=90
```

返却される `tables`:

- `by_day`: 日別の的中率推移
- `by_days_ahead`: 何日前予報ごとの精度
- `by_area`: 町・地区別の精度
- `by_buraku`: 町・地区・部落別の精度

### 現在地点マスター

```text
GET /api/integration/spots/sheets
```

- `spot_master` は毎回現在スナップショットで置き換える。
- 干場追加は次回同期で自動追加される。
- 干場削除は次回同期で現在候補から除外される。
- `raw_feedback` の過去履歴は削除しない。
- 過去行には作成時点の町・地区・部落を保存するため、削除後も集計可能。

## Google Sheets 推奨列

Forecast snapshotタブは `upsert_key` をMatching Columnにする。

```text
upsert_key
forecast_date
target_date
spot_name
spot_type
town
district
buraku
days_ahead
max_temp
min_humidity
avg_wind
precipitation
precipitation_0416
forecast_rain_0416
drying_score
suitability
data_source
synced_at_jst
```

AMEDAS observationタブは `upsert_key` をMatching Columnにする。

```text
upsert_key
date
observed_time_jst
station_id
station_name
spot_name
temperature
humidity
wind_speed
precipitation
data_source
collected_at
synced_at_jst
```

Nowcast observationタブは `upsert_key` をMatching Columnにする。

```text
upsert_key
date
observed_time_jst
spot_name
spot_type
town
district
buraku
precip_mmh
any_rain
basetime
data_source
synced_at_jst
```

Rawタブは `upsert_key` をMatching Columnにする。

```text
upsert_key
date
spot_name
town
district
buraku
days_ahead
actual_precip_0416_mm
actual_precip_total_mm
actual_rain_0416
forecast_precip_mm
forecast_rain
precip_forecast_correct
forecast_score
forecast_suitability
forecast_label
actual_result
actual_label
judgment_correct
has_drying_record
data_source
recorded_at
```

## n8n ワークフロー案

n8n標準ノードだけで構成する。HTTP Request nodeはResponse FormatをJSONにし、Google Sheets nodeは「Append or Update Row」を使う。

### Workflow 0: 予報履歴スナップショット同期

1. Schedule Trigger
   - 毎日 16:20 JST 以降に実行。
   - 既存アプリの予報履歴保存が16:05 JST想定なので、少し後ろにずらす。

2. HTTP Request
   - Method: `GET`
   - URL: `https://rishiri-kelp-forecast-system.onrender.com/api/forecast/snapshots/sheets?max_days_ahead=6`
   - Response: JSON

3. Item Lists / Code
   - `rows` 配列をGoogle Sheets用の複数アイテムに展開する。
   - 重複防止キーは `forecast_date + spot_name + days_ahead`。

4. Google Sheets
   - 既存行があれば更新、なければ追加。
   - Sheet tabは `forecast_snapshot`。
   - Matching Columnは `upsert_key`。

### Workflow 0A: アメダス実測同期

1. Schedule Trigger
   - 毎日 03:35 JST 以降に実行。
   - 既存アプリの前日アメダス収集が03:00 JST想定なので、少し後ろにずらす。

2. HTTP Request
   - Method: `GET`
   - URL: `https://rishiri-kelp-forecast-system.onrender.com/api/observations/amedas/sheets`
   - Response: JSON

3. Google Sheets
   - Sheet tabは `amedas_observation`。
   - Matching Columnは `upsert_key`。

### Workflow 0B: ナウキャストメッシュ実測同期

1. Schedule Trigger
   - 毎日 16:15 JST 以降に実行。
   - アプリ本体が04:00-16:00 JSTに10分間隔で保存したRedisスナップショットをまとめて転記する。

2. HTTP Request
   - Method: `GET`
   - URL: `https://rishiri-kelp-forecast-system.onrender.com/api/observations/nowcast/sheets`
   - Response: JSON

3. Google Sheets
   - Sheet tabは `nowcast_observation`。
   - Matching Columnは `upsert_key`。

### Workflow A: Rawログ同期

1. Schedule Trigger
   - 毎日 03:30 JST 以降に実行。
   - 既存アプリのアメダス収集が03:00 JST想定なので、少し後ろにずらす。

2. HTTP Request
   - Method: `GET`
   - URL: `https://rishiri-kelp-forecast-system.onrender.com/api/validation/accuracy/sheets?days=90`
   - Response: JSON

3. Item Lists / Code
   - `rows` 配列をGoogle Sheets用の複数アイテムに展開する。
   - 重複防止キーは `date + spot_name + days_ahead`。

4. Google Sheets
   - 既存行があれば更新、なければ追加。
   - Matching Columnは `upsert_key`。

### Workflow B: ダッシュボード集計同期

1. Schedule Trigger
   - Workflow Aの数分後に実行する。

2. HTTP Request
   - Method: `GET`
   - URL: `https://rishiri-kelp-forecast-system.onrender.com/api/validation/accuracy/sheets/summary?days=90`
   - Response: JSON

3. Google Sheets
   - `tables.by_day` → `summary_by_day`
   - `tables.by_days_ahead` → `summary_by_days_ahead`
   - `tables.by_area` → `summary_by_area`
   - `tables.by_buraku` → `summary_by_buraku`
   - 各SummaryタブのMatching Columnは `summary_key`。

4. Dashboardシート
   - `summary_by_day` から折れ線グラフを作る。
   - `summary_by_days_ahead` から棒グラフを作る。
   - `summary_by_buraku` から外れやすい部落ランキングを作る。

### Workflow C: 地点マスター同期

1. HTTP Requestで `/api/integration/spots/sheets` を取得する。
2. `spot_master` のデータ行をクリアする（ヘッダーは残す）。
3. `rows` を展開して現在地点を追加する。
4. `spot_detail` のプルダウンは `spot_master!B2:B` を参照する。

## 可視化アイデア

- 日別の降水予報的中率
- `days_ahead` 別の乾燥判定的中率
- 部落別の外れやすさ
- `forecast_score` と実際の `actual_label` の散布図
- false positive: 予報は「可」だが実際は「不可」
- false negative: 予報は「不可」だが実際は「可」

## Google Sheets整形スクリプト

Google Sheets上で `docs/google_sheets_accuracy_dashboard_apps_script.gs` をApps Scriptに貼り付け、`setupRishiriAccuracyDashboard()` を実行すると以下を自動整備する。

- 必要タブの作成
- Raw/Summaryタブのヘッダー作成
- DashboardタブのKPI表作成
- 日別・何日前予報別グラフ作成
- n8n設定メモタブ作成

## 安全上の注意

- このAPIは読み取り専用で、既存CSVや通知設定を書き換えない。
- `/api/forecast` を334地点ぶん直接連打する設計は避ける。既存のレート制限と外部API負荷を守るため。
- LINE通知のn8n化は第2段階で扱う。既存の内部スケジューラーと二重送信しないように設計する。

## 参考

- n8n Google Sheets node: https://docs.n8n.io/integrations/builtin/app-nodes/n8n-nodes-base.googlesheets/
- n8n HTTP Request node: https://docs.n8n.io/integrations/builtin/core-nodes/n8n-nodes-base.httprequest/
