# 🚀 本番デプロイメントガイド - 利尻島昆布干場予報システム v2.1.0

## 📋 デプロイメント完了チェックリスト

### ✅ システム準備状況（v2.1.0）

- [x] **メインアプリケーション** - `start.py` (1,034行、実装率97%)
- [x] **実測データ閾値** - H_1631_1434基準（21件記録検証済み）
- [x] **13 APIエンドポイント** - 天気・予報・地形・分析・検証
- [x] **331干場データベース** - `hoshiba_spots.csv` 完全統合
- [x] **PWAオフライン対応** - Service Worker完全実装
- [x] **削除制限機能** - 4条件制限（記録・お気に入り・通知・ロック）
- [x] **風向角度差表示** - 気象風向とθ値の角度差計算
- [x] **WSGI エントリーポイント** - `wsgi.py` 本番用
- [x] **環境別設定** - `config.py` (Development/Production/Testing)
- [x] **依存関係管理** - `requirements.txt` 完全版

## 🎯 デプロイ構成オプション

### 最小構成（開発・テスト環境）
```bash
start.py
wsgi.py
config.py
hoshiba_spots.csv
requirements.txt
/ui/ (HTMLファイル5個 + JSファイル4個)
```

### 推奨構成（本番環境）
```bash
上記 +
hoshiba_records.csv
/data/*.json (設定ファイル)
DEPLOYMENT.md
PROJECT_STRUCTURE.md
THRESHOLD_UPDATE_SUMMARY.md
```

## 🌊 クイックデプロイ: Render.com

### Step 1: リポジトリ準備

```bash
# Gitリポジトリが最新か確認
git status
git log --oneline -3

# 必要に応じてプッシュ
git push origin main
```

### Step 2: Render.com 設定

1. **新規Webサービス作成**
   - Repository: このGitリポジトリを選択
   - Name: `rishiri-kelp-forecast`
   - Environment: `Python 3`
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `gunicorn wsgi:app`

2. **環境変数設定**
```bash
FLASK_ENV=production
SECRET_KEY=your_secure_random_key_min_32_chars
PORT=8000
```

### Step 3: デプロイ実行

Render.comが自動的に:
1. 依存関係をインストール
2. Gunicornでアプリケーション起動
3. HTTPS証明書を自動設定
4. URLを発行: `https://rishiri-kelp-forecast.onrender.com`

## 🔧 詳細設定手順

### 1. 環境変数設定

| 変数名 | 必須度 | デフォルト値 | 説明 |
|--------|--------|------------|------|
| `FLASK_ENV` | 推奨 | `development` | `production`に設定 |
| `SECRET_KEY` | 推奨 | `dev-secret-key...` | セッション暗号化キー（本番では必ず変更） |
| `PORT` | オプション | `8000` | アプリケーションポート |

**注意**: このシステムは外部APIキー不要で動作します（Open-Meteo APIは無料・認証不要）

### 2. セキュリティ設定

```python
# 自動的に適用される設定
- HTTPS 強制リダイレクト
- セキュリティヘッダー自動追加
- CSP (Content Security Policy)
- レート制限
- XSS 保護
```

### 3. PWA 最適化

```javascript
// 自動的に設定される項目
- Service Worker 本番最適化
- HTTPS 必須設定
- キャッシュ戦略
- オフライン対応
```

## 📊 モニタリング設定

### ヘルスチェックエンドポイント

- `GET /health` - 基本ヘルスチェック
- `GET /` - システム情報（バージョン、API一覧、機能一覧）

### APIエンドポイント確認（v2.1.0）

デプロイ後、以下のエンドポイントが正常動作するか確認:

```bash
# システム情報
curl https://your-app.onrender.com/

# ヘルスチェック
curl https://your-app.onrender.com/health

# 7日間予報（サンプル干場）
curl "https://your-app.onrender.com/api/forecast?lat=45.242&lon=141.242&name=神居"

# 干場リスト
curl https://your-app.onrender.com/api/spots

# 地形情報
curl https://your-app.onrender.com/api/terrain/神居
```

### ログ監視

```bash
# Render.com でログ確認
Dashboard → Logs タブ

# または CLI
render logs -f
```

## 🔗 外部サービス連携

### 推奨モニタリングツール

1. **UptimeRobot** (無料)
   - URL: https://uptimerobot.com
   - エンドポイント: `https://your-app.railway.app/health`

2. **Sentry** (エラー追跡)
   ```bash
   SENTRY_DSN=your_sentry_dsn_here
   ```

3. **Google Analytics** (アクセス解析)
   - PWA 対応設定済み

## 🌐 カスタムドメイン設定

### Railway でドメイン設定

1. Railway ダッシュボードでドメイン追加
2. DNS レコード設定:
   ```
   Type: CNAME
   Name: www
   Value: your-app.railway.app
   ```

### SSL証明書

- Railway が自動で Let's Encrypt 証明書を設定
- HTTPS 自動リダイレクト有効

## 📱 PWA インストール確認

### テスト項目

- [x] Manifest.json 配信確認
- [x] Service Worker 登録確認
- [x] HTTPS 必須確認
- [x] アプリインストール可能確認
- [x] オフライン動作確認

### モバイルテスト

```bash
# Chrome DevTools でPWA監査
1. F12 → Lighthouse
2. Progressive Web App チェック実行
3. スコア 90+ 確認
```

## 🚨 トラブルシューティング

### よくある問題と解決法

#### 1. デプロイ失敗

```bash
# ログ確認
railway logs

# 再デプロイ
railway up --force
```

#### 2. 環境変数エラー

```bash
# 環境変数確認
railway variables

# 追加設定
railway variables set SECRET_KEY=your_key
```

#### 3. PWA 動作しない

- HTTPS 確認
- Service Worker エラーログ確認
- Manifest.json 構文確認

#### 4. パフォーマンス問題

```bash
# リソース使用量確認
railway status

# スケールアップ
railway scale --memory 1GB
```

## 📈 パフォーマンス最適化

### 自動適用される最適化

- Gunicorn マルチワーカー
- 静的ファイルキャッシュ
- Gzip 圧縮
- CDN 対応
- データベースコネクションプール

### 監視指標

- 平均レスポンス時間: < 500ms
- アップタイム: > 99.5%
- エラー率: < 1%
- PWA スコア: > 90

## 🔄 継続的改善

### 週次チェック項目

- [ ] ログ確認
- [ ] パフォーマンス監視
- [ ] セキュリティアップデート
- [ ] バックアップ確認

### 月次チェック項目

- [ ] 依存関係更新
- [ ] セキュリティ監査
- [ ] 容量使用量確認
- [ ] ユーザーフィードバック分析

## 📞 サポート体制

### 緊急時対応

1. **サービス停止時**
   - Railway ダッシュボード確認
   - ログ分析
   - ロールバック実行

2. **パフォーマンス低下時**
   - メトリクス確認
   - リソース監視
   - スケーリング検討

3. **セキュリティ問題時**
   - アクセスログ確認
   - 問題IP ブロック
   - セキュリティパッチ適用

---

## 🎯 デプロイ後の確認項目（v2.1.0）

### 即座確認 (5分以内)

- [ ] `GET /` でシステム情報表示（バージョン2.1.0確認）
- [ ] `GET /health` でヘルスチェックOK
- [ ] `GET /api/spots` で331干場リスト取得
- [ ] `GET /ui` で干場マップ表示
- [ ] `GET /drying-map` で乾燥予報マップ表示

### API機能確認 (30分以内)

- [ ] `GET /api/forecast` で7日間予報取得（風向角度差含む）
- [ ] `GET /api/terrain/<spot_name>` で地形情報取得
- [ ] `GET /api/analysis/spot-differences` で干場間差異分析
- [ ] `POST /add` で干場追加テスト
- [ ] `POST /delete` で削除制限動作確認（4条件チェック）

### PWA・オフライン確認 (1時間以内)

- [ ] `GET /service-worker.js` でService Worker配信確認
- [ ] Chrome DevToolsでPWAインストール可能確認
- [ ] オフライン時の動作確認
- [ ] キャッシュ動作確認

### データ整合性確認

- [ ] `hoshiba_spots.csv` 読み込み確認（331地点）
- [ ] `hoshiba_records.csv` が存在する場合は読み込み確認
- [ ] 実測閾値判定の動作確認（降水0mm、湿度≤94%、風速≥2.0m/s）
- [ ] 風向θ角度差計算の動作確認

### パフォーマンス確認

- [ ] API応答時間 < 500ms
- [ ] 7日間予報API応答時間 < 1秒
- [ ] 静的ファイル配信確認（HTML/JS/CSS）

---

## 📝 デプロイ完了レポート

デプロイ完了後、以下の情報を記録:

```
デプロイ日時: ____年__月__日 __:__
デプロイ先URL: https://________________
バージョン: 2.1.0
実装率: 97%
干場数: 331地点
APIエンドポイント数: 13個

動作確認結果:
- [ ] システム情報表示: OK / NG
- [ ] 7日間予報: OK / NG
- [ ] PWAインストール: OK / NG
- [ ] オフライン動作: OK / NG
```

---

**🌊 利尻島の昆布干し作業を科学的データでサポート 🌊**

**Version 2.1.0 - 実測データ基準の高精度予報システム**

*H_1631_1434の21件実測記録に基づく検証済み閾値により、信頼性の高い乾燥可否判定を提供します。*