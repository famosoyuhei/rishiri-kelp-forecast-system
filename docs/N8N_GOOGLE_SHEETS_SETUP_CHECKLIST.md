# n8n Google Sheets同期 セットアップチェックリスト

## 1. Google Sheetsを準備

- [ ] 新しいGoogle Sheetsを作成する
- [ ] Apps Scriptに `docs/google_sheets_accuracy_dashboard_apps_script.gs` を貼り付ける
- [ ] `setupRishiriAccuracyDashboard()` を実行する
- [ ] 以下のタブが自動作成されたことを確認する
  - `Dashboard`
  - `spot_master`
  - `spot_detail`
  - `forecast_snapshot`
  - `amedas_observation`
  - `nowcast_observation`
  - `nowcast_precip_daily_summary`
  - `forecast_precip_accuracy_by_horizon`
  - `raw_feedback`
  - `summary_by_day`
  - `summary_by_days_ahead`
  - `summary_by_area`
  - `summary_by_buraku`
  - `n8n_setup`

## 2. n8n認証を準備

- [ ] n8nでGoogle Sheets credentialを作成する
- [ ] 対象Google Sheetsへの編集権限を確認する
- [ ] Spreadsheet IDを控える

## 3. 予報履歴スナップショット同期ワークフロー

- [ ] Schedule Triggerを作る
  - Timezone: `Asia/Tokyo`
  - 時刻: `16:20`
  - アプリ本体のRedis保存（16:05 JST）の後に実行する
- [ ] HTTP Request nodeを作る
  - Method: `GET`
  - URL: `https://rishiri-kelp-forecast-system.onrender.com/api/forecast/snapshots/sheets?max_days_ahead=6`
  - Response Format: `JSON`
- [ ] Code nodeを作る
  - `rows` 配列をn8n itemへ展開する
  - Code:

```javascript
const rows = $json.rows || [];
return rows.map(row => ({ json: row }));
```

- [ ] Google Sheets nodeを作る
  - Operation: `Append or Update Row`
  - Sheet tab: `forecast_snapshot`
  - Matching Column: `upsert_key`
- [ ] 手動実行して `summary.coverage_pct` と `summary.missing_rows` を確認する
- [ ] n8nから `/api/forecast` を334地点へ連続呼び出ししていない

## 4. アメダス実測同期ワークフロー

- [ ] Schedule Triggerを作る
  - Timezone: `Asia/Tokyo`
  - 時刻: `03:35`
  - アプリ本体の前日アメダス収集（03:00 JST）の後に実行する
- [ ] HTTP Request nodeを作る
  - Method: `GET`
  - URL: `https://rishiri-kelp-forecast-system.onrender.com/api/observations/amedas/sheets`
  - Response Format: `JSON`
- [ ] Code nodeで `rows` 配列をn8n itemへ展開する
- [ ] Google Sheets nodeを作る
  - Operation: `Append or Update Row`
  - Sheet tab: `amedas_observation`
  - Matching Column: `upsert_key`
- [ ] 手動実行して `summary.total_rows` が26行になることを確認する

## 5. ナウキャストメッシュ実測同期ワークフロー

- [ ] Schedule Triggerを作る
  - Timezone: `Asia/Tokyo`
  - 時刻: `16:15`
  - アプリ本体の04:00-16:00 JSTナウキャスト保存後に実行する
- [ ] HTTP Request nodeを作る
  - Method: `GET`
  - URL: `https://rishiri-kelp-forecast-system.onrender.com/api/observations/nowcast/sheets`
  - Response Format: `JSON`
- [ ] Code nodeで `rows` 配列をn8n itemへ展開する
- [ ] Google Sheets nodeを作る
  - Operation: `Append or Update Row`
  - Sheet tab: `nowcast_observation`
  - Matching Column: `upsert_key`
- [ ] 手動実行して `summary.snapshot_count` と `summary.total_rows` を確認する

## 6. ナウキャスト日次降水要約同期ワークフロー

- [ ] Schedule Triggerを作る
  - Timezone: `Asia/Tokyo`
  - 時刻: `16:25`
  - 04:00-16:00 JSTのナウキャスト保存後に実行する
- [ ] HTTP Request nodeを作る
  - Method: `GET`
  - URL: `https://rishiri-kelp-forecast-system.onrender.com/api/observations/nowcast/daily-summary/sheets`
  - Response Format: `JSON`
- [ ] Code nodeで `rows` 配列をn8n itemへ展開する
- [ ] Google Sheets nodeを作る
  - Operation: `Append or Update Row`
  - Sheet tab: `nowcast_precip_daily_summary`
  - Matching Column: `upsert_key`
- [ ] 手動実行して `summary.complete=true` と `summary.coverage_pct=100` を確認する

## 7. 降水予報の何日前別精度同期ワークフロー

- [ ] Schedule Triggerを作る
  - Timezone: `Asia/Tokyo`
  - 時刻: `16:30`
  - ナウキャスト日次降水要約同期の後に実行する
- [ ] HTTP Request nodeを作る
  - Method: `GET`
  - URL: `https://rishiri-kelp-forecast-system.onrender.com/api/validation/forecast-precip/accuracy-by-horizon/sheets?max_days_ahead=6`
  - Response Format: `JSON`
- [ ] Code nodeで `rows` 配列をn8n itemへ展開する
- [ ] Google Sheets nodeを作る
  - Operation: `Append or Update Row`
  - Sheet tab: `forecast_precip_accuracy_by_horizon`
  - Matching Column: `summary_key`
- [ ] 手動実行して `summary.complete_horizons` に0〜6日前が揃っていることを確認する

## 8. Raw同期ワークフロー

- [ ] Schedule Triggerを作る
  - Timezone: `Asia/Tokyo`
  - 時刻: `03:35`
- [ ] HTTP Request nodeを作る
  - Method: `GET`
  - URL: `https://rishiri-kelp-forecast-system.onrender.com/api/validation/accuracy/sheets?days=90`
  - Response Format: `JSON`
- [ ] Code nodeを作る
  - `rows` 配列をn8n itemへ展開する
  - Code:

```javascript
const rows = $json.rows || [];
return rows.map(row => ({ json: row }));
```

- [ ] Google Sheets nodeを作る
  - Operation: `Append or Update Row`
  - Sheet tab: `raw_feedback`
  - Matching Column: `upsert_key`
- [ ] 手動実行してエラーがないことを確認する

## 9. Summary同期ワークフロー

- [ ] Schedule Triggerを作る
  - Timezone: `Asia/Tokyo`
  - 時刻: `03:40`
- [ ] HTTP Request nodeを作る
  - Method: `GET`
  - URL: `https://rishiri-kelp-forecast-system.onrender.com/api/validation/accuracy/sheets/summary?days=90`
  - Response Format: `JSON`
- [ ] `tables.by_day` を `summary_by_day` へ同期する
- [ ] `tables.by_days_ahead` を `summary_by_days_ahead` へ同期する
- [ ] `tables.by_area` を `summary_by_area` へ同期する
- [ ] `tables.by_buraku` を `summary_by_buraku` へ同期する
- [ ] 各Google Sheets nodeのMatching Columnを `summary_key` にする
- [ ] 手動実行してエラーがないことを確認する

Summary用Code node例:

```javascript
const tableName = 'by_day'; // by_days_ahead / by_area / by_buraku に差し替え
const rows = $json.tables?.[tableName] || [];
return rows.map(row => ({ json: row }));
```

各Summaryタブの対応:

| tableName | Sheet tab | Matching Column |
|---|---|---|
| `by_day` | `summary_by_day` | `summary_key` |
| `by_days_ahead` | `summary_by_days_ahead` | `summary_key` |
| `by_area` | `summary_by_area` | `summary_key` |
| `by_buraku` | `summary_by_buraku` | `summary_key` |

## 10. Spot master同期ワークフロー

- [ ] HTTP Request nodeを作る
  - Method: `GET`
  - URL: `https://rishiri-kelp-forecast-system.onrender.com/api/integration/spots/sheets`
- [ ] `spot_master` の2行目以降をクリアする
- [ ] `rows` 配列をn8n itemへ展開する
- [ ] Google Sheets nodeで現在地点を追加する
- [ ] `spot_detail` のプルダウンに現在地点が表示されることを確認する
- [ ] 削除済み地点がプルダウン候補から消えることを確認する

## 11. ダッシュボード確認

- [ ] `forecast_snapshot` に同じ `upsert_key` の重複が増えていない
- [ ] `amedas_observation` に同じ `upsert_key` の重複が増えていない
- [ ] `nowcast_observation` に同じ `upsert_key` の重複が増えていない
- [ ] `nowcast_precip_daily_summary` に同じ `upsert_key` の重複が増えていない
- [ ] `forecast_precip_accuracy_by_horizon` に同じ `summary_key` の重複が増えていない
- [ ] `forecast_precip_accuracy_by_horizon` に0〜6日前の行が日別に揃っている
- [ ] DashboardタブのKPI値が表示される
- [ ] 日別 的中率推移グラフが表示される
- [ ] 何日前予報別 精度グラフが表示される
- [ ] `raw_feedback` に同じ `upsert_key` の重複が増えていない
- [ ] Summaryタブに同じ `summary_key` の重複が増えていない
- [ ] `spot_detail` で干場を切り替えられる

## 12. 安全確認

- [ ] n8nから `/api/forecast` を334地点へ連続呼び出ししていない
- [ ] LINE通知ワークフローはまだ有効化していない
- [ ] Scheduleは03:00 JSTのアメダス収集後に設定している
- [ ] 失敗時の通知先をn8n側に設定している
