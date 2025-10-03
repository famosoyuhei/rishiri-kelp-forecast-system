# 利尻島昆布干し予報システム - プロジェクト構成 (v2.1.0)

## 📁 ディレクトリ構成

```
rishiri_konbu_weather_tool/
├── start.py                          ⭐ メインアプリケーション
├── wsgi.py                           🚀 本番デプロイ用WSGIエントリーポイント
├── config.py                         ⚙️ システム設定
├── security.py                       🔒 セキュリティ設定
│
├── /core/                            # コア機能モジュール
│   ├── terrain_database.py          # 地形データベース
│   ├── kelp_drying_model.py         # 昆布乾燥モデル
│   ├── atmospheric_stability_analyzer.py  # 大気安定度解析
│   ├── multi_source_weather_api.py  # マルチソース天気API
│   └── isoline_analysis_engine.py   # 等値線解析エンジン
│
├── /ui/                              # Webインターフェース
│   ├── hoshiba_map_complete.html    # 干場マップ（完成版）
│   ├── kelp_drying_map.html         # 乾燥予報マップ
│   ├── dashboard.html               # ダッシュボード
│   ├── mobile_forecast_interface.html  # モバイル版
│   ├── offline.html                 # オフラインページ
│   ├── all_spots_array.js           # 干場データ
│   ├── rishiri_wind_names.js        # 伝統風名ライブラリ
│   ├── kelp_forecast_api.js         # API連携ライブラリ
│   └── service-worker.js            # PWA Service Worker
│
├── /data/                            # データファイル
│   ├── hoshiba_spots.csv            # 干場リスト（331地点）
│   ├── hoshiba_records.csv          # 乾燥記録データ
│   ├── user_favorites.json          # ユーザーお気に入り
│   ├── notification_users.json      # 通知設定
│   └── *.json                       # 各種設定ファイル
│
├── /modules/                         # 補助モジュール
│   ├── notification_system.py       # 通知システム
│   ├── favorites_manager.py         # お気に入り管理
│   ├── fishing_season_manager.py    # 漁期管理
│   ├── backup_system.py             # バックアップシステム
│   ├── monitoring.py                # モニタリング
│   └── data_visualization_system.py # データ可視化
│
├── /docs/                            # ドキュメント
│   ├── README.md                    # プロジェクト概要
│   ├── system_specification.md      # システム仕様書
│   ├── THRESHOLD_UPDATE_SUMMARY.md  # 閾値更新サマリー
│   ├── DEPLOYMENT.md                # デプロイメントガイド
│   └── PROJECT_STRUCTURE.md         # 本ファイル
│
└── /archive/                         # アーカイブ（開発・検証用）
    ├── /analysis/                   # 分析スクリプト（約30ファイル）
    ├── /verification/               # 検証スクリプト（約15ファイル）
    ├── /development/                # 開発中ファイル（約10ファイル）
    ├── /deprecated/                 # 旧版ファイル
    └── /temp_data/                  # 一時データ
```

## 🎯 本番稼働に必要なファイル

### 必須ファイル（13個）

#### アプリケーションコア
1. `start.py` - メインアプリケーション（1,034行、v2.1.0）
2. `wsgi.py` - 本番WSGIサーバー用
3. `config.py` - システム設定
4. `security.py` - セキュリティ設定

#### UIファイル（9個）
5. `hoshiba_map_complete.html` - 干場マップ
6. `kelp_drying_map.html` - 乾燥予報マップ
7. `dashboard.html` - ダッシュボード
8. `mobile_forecast_interface.html` - モバイル版
9. `offline.html` - オフライン対応ページ
10. `all_spots_array.js` - 干場データ（331地点）
11. `rishiri_wind_names.js` - 伝統風名（16方位）
12. `kelp_forecast_api.js` - API連携
13. `service-worker.js` - PWA機能

### コアモジュール（推奨、10個）
14. `terrain_database.py` - 地形データベース
15. `kelp_drying_model.py` - 乾燥モデル
16. `atmospheric_stability_analyzer.py` - 大気解析
17. `multi_source_weather_api.py` - マルチAPI
18. `isoline_analysis_engine.py` - 等値線解析
19. `notification_system.py` - 通知システム
20. `favorites_manager.py` - お気に入り
21. `fishing_season_manager.py` - 漁期管理
22. `backup_system.py` - バックアップ
23. `monitoring.py` - モニタリング

### データファイル（2個 + JSON設定）
24. `hoshiba_spots.csv` - 干場リスト
25. `hoshiba_records.csv` - 記録データ
26. 各種JSON設定ファイル

## 📊 ファイル統計

| カテゴリ | 整理前 | 整理後 | 削減率 |
|---------|-------|-------|--------|
| Pythonファイル | 約90 | 47 | 48% |
| HTMLファイル | 約10 | 9 | 10% |
| 総ファイル数 | 約140 | 約80 | 43% |

**アーカイブ移動**: 約60ファイル
- 分析スクリプト: 約30ファイル
- 検証スクリプト: 約15ファイル
- 開発中ファイル: 約10ファイル
- 一時データ: 約5ファイル

## 🚀 デプロイメント

### 最小構成（開発環境）
```bash
# 必須ファイルのみ
start.py
wsgi.py
config.py
*.html (5ファイル)
*.js (4ファイル)
*.csv (2ファイル)
```

### 推奨構成（本番環境）
```bash
# 上記 + コアモジュール
/core/ (5モジュール)
/modules/ (5モジュール)
/data/ (全JSONファイル)
```

### 完全構成（フル機能）
```bash
# 全ての本番ファイル + ドキュメント
/docs/ (全MDファイル)
/archive/ (開発・検証用、オプション)
```

## 🔧 主要機能とファイル対応

| 機能 | ファイル |
|------|---------|
| **7日間予報** | `start.py` (lines 201-398) |
| **実測閾値判定** | `start.py` (lines 1084-1215) |
| **風向θ角度差** | `start.py` (lines 74-103, 270-271) |
| **干場削除制限** | `start.py` (lines 547-658) |
| **地形補正** | `start.py` (lines 392-450), `terrain_database.py` |
| **等値線解析** | `start.py` (lines 893-921), `isoline_analysis_engine.py` |
| **伝統風名** | `rishiri_wind_names.js` |
| **オフライン** | `service-worker.js`, `offline.html` |
| **通知システム** | `notification_system.py` |
| **お気に入り** | `favorites_manager.py` |

## 📡 APIエンドポイント（13個）

```
GET  /                                # システム情報
GET  /health                          # ヘルスチェック
GET  /api/weather                     # 現在天気
GET  /api/forecast                    # 7日間予報
GET  /api/spots                       # 干場リスト
GET  /api/terrain/<spot_name>         # 地形情報
GET  /api/analysis/contours           # 等値線解析
GET  /api/analysis/spot-differences   # 干場間差異
GET  /api/validation/accuracy         # 予報精度
POST /add                             # 干場追加
POST /delete                          # 干場削除
POST /record                          # 記録追加/更新
GET  /record/<name>/<date>            # 記録取得
```

## 🎨 Webインターフェース（10ページ）

```
GET  /                                # API情報
GET  /ui                              # メインUI
GET  /dashboard                       # ダッシュボード
GET  /mobile                          # モバイル版
GET  /map                             # 干場マップ
GET  /drying-map                      # 乾燥予報マップ
GET  /offline.html                    # オフライン
GET  /service-worker.js               # Service Worker
GET  /all_spots_array.js              # 干場データ
GET  /rishiri_wind_names.js           # 伝統風名
```

## 📈 バージョン履歴

### v2.1.0 (2025-10-03) - Current
- ✅ 地形情報API追加
- ✅ 等値線解析API追加
- ✅ 予報精度検証API追加
- ✅ 干場間気象差異API追加
- ✅ プロジェクト構成整理（43%ファイル削減）

### v2.0.0 (2025-10-03)
- ✅ 実測データ閾値完全統合（H_1631_1434基準）
- ✅ 干場削除4条件制限実装
- ✅ 風向θ角度差表示実装
- ✅ PWA/オフライン機能完全統合

### v1.0.0 (2025-09-XX)
- ✅ 基本予報機能
- ✅ 7日間予報UI
- ✅ 伝統風名16方位
- ✅ 記録機能

## 📝 保守・開発ガイドライン

### ファイル追加時のルール
1. **本番機能** → ルートディレクトリまたは適切なサブディレクトリ
2. **開発・実験** → `/archive/development/`
3. **分析スクリプト** → `/archive/analysis/`
4. **検証スクリプト** → `/archive/verification/`
5. **一時データ** → `/archive/temp_data/`

### コードレビューポイント
- `start.py`の行数が1500行を超えたらモジュール分割を検討
- 新規APIエンドポイントは必ずドキュメント更新
- 仕様書との対応関係を明記

### バックアップポリシー
- `hoshiba_records.csv` - 毎日自動バックアップ
- `hoshiba_spots.csv` - 変更時バックアップ
- JSON設定ファイル - 週次バックアップ

## 🔗 関連ドキュメント

- [README.md](README.md) - プロジェクト概要
- [system_specification.md](system_specification.md) - システム仕様書（詳細）
- [THRESHOLD_UPDATE_SUMMARY.md](THRESHOLD_UPDATE_SUMMARY.md) - 実測閾値サマリー
- [DEPLOYMENT.md](DEPLOYMENT.md) - デプロイメントガイド

---

**最終更新**: 2025-10-03
**バージョン**: v2.1.0
**総実装率**: 97%
