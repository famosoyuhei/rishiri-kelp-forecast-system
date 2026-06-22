# 無料Google Sheets セットアップ

Microsoft Excelの契約は不要です。Googleアカウントと無料のGoogle Sheetsだけで利用できます。

## 手順

1. ブラウザで `https://sheets.new` を開く。
2. シート名を「利尻島昆布干場 予報精度ダッシュボード」に変更する。
3. 「拡張機能」→「Apps Script」を開く。
4. `docs/google_sheets_accuracy_dashboard_apps_script.gs` の内容を貼り付ける。
5. `setupRishiriAccuracyDashboard()` を実行し、Googleの実行許可を承認する。

これにより、地点マスター、干場別詳細、Rawログ、4種類の集計、Dashboard、n8n設定タブが自動作成されます。

## n8n接続

作成したGoogle SheetsのURLからSpreadsheet IDを取得し、n8nのGoogle Sheets credentialへ設定します。

```text
https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/edit
```

同期手順は `docs/N8N_GOOGLE_SHEETS_SETUP_CHECKLIST.md` を参照してください。
