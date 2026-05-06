# デプロイメントガイド - 利尻島昆布干場予報システム v2.6.0

## 本番環境

- **サービス**: Render
- **URL**: https://rishiri-kelp-forecast-system.onrender.com
- **GitHub**: https://github.com/famosoyuhei/rishiri-kelp-forecast-system
- **デプロイ方法**: mainブランチへのpushで自動デプロイ

## クイックデプロイ

```bash
git add .
git commit -m "Update"
git push origin main
# Renderが自動的に検知してデプロイ（約2-5分）
```

## Render 設定

| 項目 | 値 |
|-----|-----|
| Runtime | Python 3 |
| Build Command | `pip install -r requirements.txt` |
| Start Command | `gunicorn wsgi:app` |
| Auto-Deploy | Yes（mainブランチ） |

### 環境変数

| 変数名 | 必須度 | 説明 |
|--------|--------|------|
| `FLASK_ENV` | 推奨 | `production` に設定 |
| `SECRET_KEY` | 推奨 | セッション暗号化キー（32文字以上のランダム文字列） |

**注意**: Open-Meteo APIは無料・認証不要のため、外部APIキーは不要です。

## デプロイ後の動作確認

```bash
# ヘルスチェック
curl https://rishiri-kelp-forecast-system.onrender.com/health

# システム情報
curl https://rishiri-kelp-forecast-system.onrender.com/api/info

# 干場リスト（334地点確認）
curl https://rishiri-kelp-forecast-system.onrender.com/api/spots

# 7日間予報
curl "https://rishiri-kelp-forecast-system.onrender.com/api/forecast?lat=45.1631&lon=141.1434&name=H_1631_1434"
```

### 確認チェックリスト

- [ ] `GET /health` → `{"status":"healthy"}` が返る
- [ ] `GET /` でメインUI（kelp_drying_map.html）が表示される
- [ ] `GET /api/spots` で334地点リストが取得できる
- [ ] `GET /api/forecast` で7日間予報が取得できる
- [ ] PWAインストール可能（Chrome DevTools > Lighthouse）
- [ ] オフライン時にoffline.htmlが表示される

## ローカル開発

```bash
python start.py
# または
gunicorn wsgi:app --bind 0.0.0.0:5000
```

アクセス: http://localhost:5000/

## トラブルシューティング

### デプロイが失敗する

Renderダッシュボードのログを確認:
- Dashboard → your service → Logs タブ

よくある原因:
- `requirements.txt` に依存パッケージが不足
- `hoshiba_spots.csv` が存在しない

### データファイルの永続化

Renderの無料プランはエフェメラルファイルシステムのため、再起動時にデータが失われます。

本番運用では Render Disks を使用してください:
1. Dashboard → your service → Disks
2. Add Disk（Mount Path: `/opt/render/project/src/data`）

### パフォーマンス

- Free tier: 512MB RAM（15分無操作でスリープ）
- Starter（$7/月）: 2GB RAM、常時稼働（推奨）

---

**最終更新**: 2026年4月5日 / v2.6.0
