# Codex Scope: Accuracy Analysis

このworktreeは、利尻島昆布干場予報システムの「精度分析・検証・Google Sheets/n8n同期」だけを扱う。

## 対象

- 予報精度API、フィードバックログ、Google Sheets/n8n同期
- `forecast_history`、`amedas_data`、`feedback_log.csv`、`hoshiba_records.csv` を使う分析
- 閾値検証、降水有無の的中率、乾燥可否判定、日別/地区別/何日前予報別の集計
- 関連する自動収集、データ整合性、テスト

## 主要ファイル

- `start.py`
  - `/api/validation/accuracy`
  - `/api/validation/accuracy/sheets`
  - `/api/validation/accuracy/sheets/summary`
  - `_save_forecast_history`
  - `_record_forecast_feedback`
  - `_collect_amedas_from_openmeteo`
  - `_auto_compare_forecast_vs_actual`
- `forecast_accuracy/`
- `forecast_accuracy_db.py`
- `accuracy_analyzer.py`
- `accuracy_reporter.py`
- `validate_thresholds.py`
- `check_data_integrity.py`
- `tests/test_accuracy_sheets_api.py`
- `docs/GOOGLE_SHEETS_FREE_SETUP.md`
- `docs/N8N_GOOGLE_SHEETS_ACCURACY.md`
- `docs/N8N_GOOGLE_SHEETS_SETUP_CHECKLIST.md`
- `docs/google_sheets_accuracy_dashboard_apps_script.gs`
- `docs/n8n_accuracy_google_sheets_workflow_blueprint.json`

## 必ず守ること

- すべての時刻はJSTで扱う。
- Open-Meteoや本番APIなど現在値に依存する分析は、必要に応じて確認してから結論を出す。
- 乾燥判定の基準は、原則として `THRESHOLD_UPDATE_SUMMARY.md` と実装中の閾値に合わせる。
- 精度分析の作業では、LP、SNS、広告、販売資料、画像生成、マーケティング文章には触れない。
- フロントエンド全体やPWAなど、精度分析に直接関係しない巨大ファイルは必要になるまで読まない。

## 省トークン運用

- まず `rg` で対象関数や列名を絞る。
- `start.py` は該当関数周辺だけ読む。
- Google Sheetsを扱う場合は、最初に対象スプレッドシートのメタデータと必要なタブ/範囲だけ読む。
- 大きなCSV/JSONは全読みせず、日付・列・件数を絞って集計する。
