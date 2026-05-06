# 利尻島昆布干場予報システム - プロジェクト構成 (v2.6.0)

## ディレクトリ構成

```
rishiri-kelp-forecast-system/
│
├── start.py                         メインアプリケーション（4,363行）
│                                    Flask + 全API + 予報ロジック + 4ファイル同期
├── wsgi.py                          本番デプロイ用WSGIエントリーポイント
├── requirements.txt                 依存パッケージ
├── Procfile                         Render起動設定（gunicorn wsgi:app）
│
├── kelp_drying_map.html             統合版メインUI（6,235行）
│                                    地図・エマグラム・等値線・通知・チャットボット
├── dashboard.html                   ダッシュボード
├── mobile_forecast_interface.html  モバイル版
├── offline.html                     オフライン対応ページ
│
├── all_spots_array.js               干場データ（334地点、4ファイル同期対象）
├── rishiri_wind_names.js            利尻島伝統風名ライブラリ（16方位）
├── service-worker.js                PWA Service Worker
├── app_icon.png                     アプリロゴ
│
├── hoshiba_spots.csv                干場データベース（334地点、4ファイル同期対象）
│                                    331干場(H_XXXX_XXXX) + 3特別地点(A_/R_)
├── hoshiba_spots_named.kml          Google Earth用KMLファイル（4ファイル同期対象）
├── hoshiba_records.csv              乾燥記録データベース（干場のみ、特別地点除外）
│                                    （4ファイル同期対象）
│
├── *.json                           各種設定ファイル（お気に入り・通知・編集ロック等）
│
└── archive/                         アーカイブ（開発・検証・旧システム用）
    └── deprecated/                  用済みドキュメント・旧バージョン等
```

## 本番稼働に必要なファイル

### 必須（8ファイル）

| ファイル | 説明 |
|---------|------|
| `start.py` | メインアプリケーション（全機能）|
| `wsgi.py` | Gunicorn用エントリーポイント |
| `requirements.txt` | 依存パッケージ |
| `Procfile` | Render起動設定 |
| `kelp_drying_map.html` | 統合版メインUI |
| `all_spots_array.js` | 干場データ（JS配列形式） |
| `rishiri_wind_names.js` | 伝統風名ライブラリ |
| `service-worker.js` | PWA対応 |

### データファイル（必須）

| ファイル | 説明 |
|---------|------|
| `hoshiba_spots.csv` | 干場データベース（334地点） |
| `hoshiba_records.csv` | 乾燥記録データベース |
| `hoshiba_spots_named.kml` | Google Earth用KML |

### オプション

| ファイル | 説明 |
|---------|------|
| `dashboard.html` | ダッシュボード |
| `mobile_forecast_interface.html` | モバイル版 |
| `offline.html` | PWAオフライン表示 |
| `app_icon.png` | アプリロゴ |

## APIエンドポイント（13個）

```
GET  /                                メインUI（kelp_drying_map.html）
GET  /map, /drying-map                同上（リダイレクト）
GET  /dashboard                       ダッシュボード
GET  /mobile                          モバイル版
GET  /health                          ヘルスチェック
GET  /api/info                        システム情報・API一覧（JSON）
GET  /api/weather                     現在天気
GET  /api/forecast                    7日間乾燥予報
GET  /api/spots                       干場リスト（334地点）
GET  /api/terrain/<spot_name>         地形情報・補正値
GET  /api/analysis/contours           等値線解析
GET  /api/analysis/spot-differences   干場間気象差異
GET  /api/validation/accuracy         予報精度検証
POST /add                             干場追加
POST /delete                          干場削除（5条件制限）
POST /record                          乾燥記録追加・更新
GET  /record/<name>/<date>            記録取得
```

## 4ファイル自動同期システム

干場の追加・削除時に以下の4ファイルが自動的に同期されます：

| ファイル | 形式 | 用途 |
|---------|------|------|
| `hoshiba_spots.csv` | CSV | メインデータベース |
| `hoshiba_spots_named.kml` | KML | Google Earth表示 |
| `all_spots_array.js` | JS | 地図UI表示 |
| `hoshiba_records.csv` | CSV | 記録管理（干場のみ） |

詳細: [FOUR_FILE_SYNC_IMPLEMENTATION.md](FOUR_FILE_SYNC_IMPLEMENTATION.md)

## 地点命名規則

| 種別 | 形式 | 例 |
|-----|------|-----|
| 干場 | `H_(北緯小数部4桁)_(東経小数部4桁)` | H_1631_1434 |
| アメダス観測点 | `A_(北緯小数部4桁)_(東経小数部4桁)` | A_1783_1383（沓形）|
| 基準点 | `R_(北緯小数部4桁)_(東経小数部4桁)` | R_1800_2392（利尻山頂）|

## 開発ガイドライン

- `start.py` が4,500行を超えたらモジュール分割を検討
- `kelp_drying_map.html` が7,000行を超えたらJS分離を検討
- 新規APIエンドポイントは必ずREADME.mdとsystem_specification.mdを更新
- すべての時刻はJST（日本標準時）で統一

## バックアップポリシー

- `hoshiba_records.csv` — 毎日バックアップ
- `hoshiba_spots.csv` — 変更時バックアップ
- 4ファイル同期により自動整合性維持

## デプロイ

- **本番環境**: Render（mainブランチ自動デプロイ）
- **URL**: https://rishiri-kelp-forecast-system.onrender.com
- **起動コマンド**: `gunicorn wsgi:app`

詳細: [DEPLOYMENT.md](DEPLOYMENT.md)

---

**最終更新**: 2026年4月5日 / v2.6.0
