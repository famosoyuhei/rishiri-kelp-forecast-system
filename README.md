<div align="center">

<img src="app_icon.png" alt="利尻島昆布干場予報システム" width="200"/>

# 🌊 利尻島昆布干場予報システム
## Rishiri Island Kelp Drying Forecast System

![System Status](https://img.shields.io/badge/Status-Production%20Ready-brightgreen)
![Version](https://img.shields.io/badge/Version-2.6.0-blue)
![Python](https://img.shields.io/badge/Python-3.8+-blue)
![Flask](https://img.shields.io/badge/Flask-2.3+-red)
![Implementation](https://img.shields.io/badge/Implementation-99%25-success)

**北海道利尻島の334地点（331干場+3観測/基準点）を対象とした、実測データ基準の高精度昆布乾燥予報システム**

[クイックスタート](#-クイックスタート) • [機能](#-システム機能) • [API](#-api-リファレンス) • [ドキュメント](#-開発ガイド)

</div>

---

## 時刻表記について

**本システムで使用されるすべての時刻は日本標準時（JST, UTC+9）です。**

開発者が海外にいる場合でも、利尻島の現地時刻（JST）で統一されています。

## プロジェクト概要

利尻島での昆布干し作業を支援する、実測データ基準の科学的予報システムです。H_1631_1434地点の21件実測記録（2025年6-8月）に基づく検証済み閾値により、信頼性の高い乾燥可否判定を提供します。

### 主な特徴

- **実測データ基準閾値**: 降水量0mm・最低湿度≤94%・風速≥2.0m/sの科学的判定
- **334地点データベース**: 331干場 + アメダス2地点 + 利尻山頂（特別地点）
- **地形補正システム**: 森林減衰・海岸増強・onshore wind判定による干場スケールダウンスケーリング
- **通知システム**: 夕方16:00・早朝01:30・緊急アラートの多段階通知
- **チャットボット**: ルールベース「干場アシスタント」（AI不要・無料）
- **エマグラム**: 16気圧面の鉛直プロファイル・LCL/LFC/EL自動検出
- **等値線解析**: 気温・湿度・風速の空間分布可視化
- **利尻島伝統風名**: 16方位の地域固有風名（コタン風、ナイホ風等）
- **PWAオフライン対応**: Service Workerによる完全オフライン動作
- **昆布シーズン長期予報**: 月別見通し・ENSO状況表示

## クイックスタート

### 必要要件

- Python 3.8+
- pip
- インターネット接続（Open-Meteo API用）

### インストール

```bash
git clone https://github.com/famosoyuhei/rishiri-kelp-forecast-system.git
cd rishiri-kelp-forecast-system
pip install -r requirements.txt
python start.py
```

### アクセス

- メインUI: http://localhost:5000/
- ダッシュボード: http://localhost:5000/dashboard
- モバイル版: http://localhost:5000/mobile

## API エンドポイント

| カテゴリ | エンドポイント | 機能 |
|---------|--------------|------|
| 情報 | `GET /` | メインUI（kelp_drying_map.html） |
| 情報 | `GET /health` | ヘルスチェック |
| 情報 | `GET /api/info` | システム情報・API一覧 |
| 天気 | `GET /api/weather` | 現在天気取得 |
| 予報 | `GET /api/forecast` | 7日間乾燥予報 |
| 干場 | `GET /api/spots` | 干場リスト（334地点） |
| 連携 | `GET /api/integration/spots/sheets` | n8n / Google Sheets向け現在地点マスター |
| 干場 | `POST /add` | 干場追加 |
| 干場 | `POST /delete` | 干場削除（5条件制限付き） |
| 記録 | `POST /record` | 乾燥記録追加・更新 |
| 記録 | `GET /record/<name>/<date>` | 記録取得 |
| 地形 | `GET /api/terrain/<spot_name>` | 地形情報・補正値 |
| 分析 | `GET /api/analysis/contours` | 等値線解析 |
| 分析 | `GET /api/analysis/spot-differences` | 干場間気象差異 |
| 検証 | `GET /api/validation/accuracy` | 予報精度検証 |
| 検証 | `GET /api/validation/accuracy/sheets` | n8n / Google Sheets向け精度ログ行データ |
| 検証 | `GET /api/validation/accuracy/sheets/summary` | Google Sheetsダッシュボード向け集計データ |

## システム構成

```
rishiri-kelp-forecast-system/
├── start.py                    メインアプリケーション（4,363行）
├── wsgi.py                     本番デプロイ用WSGIエントリーポイント
├── requirements.txt
├── Procfile                    Render用起動設定
│
├── kelp_drying_map.html        統合版メインUI（6,235行）
├── dashboard.html              ダッシュボード
├── mobile_forecast_interface.html  モバイル版
├── offline.html                オフライン対応ページ
├── all_spots_array.js          干場データ（334地点）
├── service-worker.js           PWA Service Worker
├── app_icon.png                アプリロゴ
│
├── hoshiba_spots.csv           干場データベース（334地点）
├── hoshiba_spots_named.kml     Google Earth用KMLファイル
├── hoshiba_records.csv         乾燥記録データベース
│
└── archive/                    アーカイブ（開発・検証用）
    └── deprecated/
```

## 予報アルゴリズム

### 実測データ基準閾値（H_1631_1434、21件、2025年6-8月）

| 要因 | 閾値 | 根拠 |
|-----|------|------|
| 降水量 | 0mm（絶対条件） | 成功例は全て0mm |
| 最低湿度 | ≤94% | 94%まで成功、95%以上は困難 |
| 平均風速 | ≥2.0m/s（強風≥9.0m/sは減点） | 2.0m/sで成功例あり。9.0m/s以上は飛散注意 |

### 地形補正（Open-Meteo 5kmメッシュ → 干場スケールへのダウンスケーリング）

| 補正項目 | 内容 |
|---------|------|
| 風速補正（乗算型） | 森林: ×0.4 / 海岸: ×1.25（onshore時のみ） |
| 湿度補正（水蒸気圧ベース） | 森林: 季節・日射依存 / 海岸: onshore時のみ |
| onshore wind判定 | 利尻山頂を極とした放射方向で海の方向を計算 |

## 特別地点（3地点）

| 地点名 | 座標 | 役割 |
|-------|------|------|
| A_1783_1383（アメダス沓形） | 45.1783N, 141.1383E, 標高14m | 公式観測データで予報精度を検証 |
| A_2417_1867（アメダス本泊） | 45.2417N, 141.1867E, 標高39m | 利尻島北部の公式データ |
| R_1800_2392（利尻山頂） | 45.1800N, 141.2392E, 標高1,721m | 風上/風下効果の判定、フェーン現象の検出 |

## 干場削除の5条件制限

干場削除は以下の全条件をクリアする必要があります（`start.py:985-996`）：

1. 記録データが存在しない
2. お気に入り登録されていない
3. 通知設定で使用されていない
4. 同時編集ロックがかかっていない（5分間）
5. 機械学習の訓練データとして使用されていない

## デプロイ

- **本番環境**: Render
- **URL**: https://rishiri-kelp-forecast-system.onrender.com
- **GitHub**: https://github.com/famosoyuhei/rishiri-kelp-forecast-system（mainブランチ自動デプロイ）

詳細は [DEPLOYMENT.md](DEPLOYMENT.md) を参照してください。

## n8n / Google Sheets 精度可視化

Microsoft Excelの契約は不要です。無料のGoogle Sheetsとn8nで、予報精度のRawログ、日別・何日前予報別・地区別・部落別集計、干場選択式の個別ビューを運用できます。

セットアップ: [docs/GOOGLE_SHEETS_FREE_SETUP.md](docs/GOOGLE_SHEETS_FREE_SETUP.md)

## ドキュメント

### 開発者向け

- [CLAUDE.md](CLAUDE.md) - 開発ガイド（Claude Code向け）
- [system_specification.md](system_specification.md) - 詳細仕様書（2,000行超）
- [THRESHOLD_UPDATE_SUMMARY.md](THRESHOLD_UPDATE_SUMMARY.md) - 実測閾値の詳細
- [FOUR_FILE_SYNC_IMPLEMENTATION.md](FOUR_FILE_SYNC_IMPLEMENTATION.md) - 4ファイル同期システム
- [EMAGRAM_DOCUMENTATION.md](EMAGRAM_DOCUMENTATION.md) - エマグラム機能仕様
- [PWA_IMPLEMENTATION_COMPLETE.md](PWA_IMPLEMENTATION_COMPLETE.md) - PWA/オフライン機能
- [DEPLOYMENT.md](DEPLOYMENT.md) - デプロイ手順
- [ISLAND_METEOROLOGY_RESEARCH.md](ISLAND_METEOROLOGY_RESEARCH.md) - 円錐形孤立島の気象研究（フロード数・後流渦・海陸風・霧・地形性降水）
- [KOMBU_DRYING_RESEARCH.md](KOMBU_DRYING_RESEARCH.md) - 昆布乾燥メカニズム研究（Pageモデル・有効拡散係数・閾値の物理的根拠）
- [WINDY_RESEARCH.md](WINDY_RESEARCH.md) - Windyアプリ機能調査 & 当アプリとのギャップ分析（潮汐・CAPE・降水確率・SST等）

### 外部向け（docs/）

- [docs/USER_GUIDE.md](docs/USER_GUIDE.md) - アプリ使い方説明書（スマホ初心者向け）
- [docs/MARKETING.md](docs/MARKETING.md) - 営業・広告素材集（コピー・動画スクリプト・チラシ）

---

## LINE通知連携

### 概要

昆布作業者が普段使いしているLINEで予報確認・通知受信ができます。

| コマンド | 動作 |
|---------|------|
| `今日` | 登録済み干場の当日予報 |
| `明日` | 登録済み干場の翌日予報 |
| `今週` | 登録済み干場の7日間予報 |
| `H_1631_1434` | 指定干場の7日間予報 |
| `沓形` / `仙法志 明日` | 地区・部落の予報 |
| `通知登録 H_1631_1434` | 毎日16:00/01:30に通知 |
| `通知解除` | 通知をOFF |
| `ヘルプ` | コマンド一覧 |

### セットアップ手順

#### 1. LINE Developers Console で設定

1. [LINE Developers Console](https://developers.line.biz/) にログイン
2. 「プロバイダー作成」→「チャネル作成」→「Messaging API」を選択
3. チャネル基本設定から **Channel secret** を取得
4. Messaging API設定タブから **Channel access token（長期）** を発行
5. Webhook設定：
   - Webhook URL: `https://<本番ドメイン>/line/webhook`
   - 「Webhookの利用」をON
   - 「接続確認」で 200 OK を確認

#### 2. Render 環境変数に設定

| 変数名 | 値 | 説明 |
|--------|-----|------|
| `LINE_ENABLED` | `true` | LINE機能を有効化 |
| `LINE_CHANNEL_SECRET` | （Consoleで取得） | 署名検証用 |
| `LINE_CHANNEL_ACCESS_TOKEN` | （Consoleで発行） | メッセージ送信用 |
| `LINE_ADMIN_NOTIFY_SECRET` | （任意の長いランダム文字列） | 通知API認証用 |

#### 3. Render Cron Job 設定（UTC表記）

| JST | UTC | body例 |
|-----|-----|--------|
| 毎日 16:00 | 07:00 | `{"kind":"evening","secret":"<シークレット>"}` |
| 毎日 01:30 | 16:30（前日） | `{"kind":"morning","secret":"<シークレット>"}` |

```
POST https://<ドメイン>/api/line/notify
Content-Type: application/json
```

#### 4. Webアプリに友だち追加バナーを表示（オプション）

Render の環境変数 `LINE_ADD_FRIEND_URL` に LINE 友だち追加URL（例: `https://lin.ee/xxxxxxx`）を
設定すると、[kelp_drying_map.html](kelp_drying_map.html) が `/api/line/status` から自動取得して
下部にバナーを表示します。**HTMLへの手動追記は不要です。**

| 環境変数 | 説明 |
|---------|------|
| `LINE_ADD_FRIEND_URL` | LINEの友だち追加URL。未設定時はバナー非表示。 |

### エンドポイント

| メソッド | パス | 説明 |
|---------|------|------|
| `POST` | `/line/webhook` | LINE Platform からのWebhook受信 |
| `GET` | `/api/line/status` | LINE連携状態・友だち追加URL（秘密情報なし） |
| `POST` | `/api/line/notify` | 購読者への一斉Push通知 |

### 予報精度について（LINE簡易予報）

LINEメッセージ内の予報は Open-Meteo 直接呼び出しの**簡易版**です。
Webアプリの `/api/forecast`（地形補正・onshore判定・霧リスク等を含む）とは
スコアが ±10〜15点程度ずれる場合があります。
全メッセージに `※LINE簡易予報（Webアプリと値が異なる場合あり）` を付記しています。

### 購読データ

`line_subscriptions.json` に保存されます（`.gitignore` 登録済み・既存CSVとは分離）。
保存内容は source_id・source_type・登録干場・通知ON/OFFのみ。ユーザー名等は保存しません。

---

## バージョン履歴

### v2.6.0（2026年4月5日）
- 通知システム全機能実装（夕方16:00・早朝01:30・緊急アラート・音・バイブ・履歴）
- ルールベースチャットボット「干場アシスタント」実装（無料・AI不使用）
- 干場ニックネーム機能（localStorage・端末個別）
- 昆布シーズン長期予報タブ
- アプリロゴ（app_icon.png）を全UIページに統一追加

### v2.5.0（2026年1月8日）
- 特別地点システム（3地点: アメダス沓形・本泊、利尻山頂）
- 334地点体制への拡大（331干場 + 3観測/基準点）
- Open-Meteo Elevation API統合（Copernicus GLO-90 DEM）
- onshore wind判定システム実装

### v2.4.1（2025年12月）
- エマグラム機能完成（θₑ補正・LCL/LFC/EL自動検出）
- 等値線解析・時間解像度統一
- HTMLエンドポイント統合（v1/v2を統合版に一本化）

---

**最終更新**: 2026年4月5日 / Version 2.6.0 / 実装率 99%
