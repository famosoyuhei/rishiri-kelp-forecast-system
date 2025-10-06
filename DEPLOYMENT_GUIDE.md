# Renderデプロイガイド - 統合海洋予報システム

## 🚀 デプロイ手順

### ステップ1: Gitリポジトリの準備

```bash
cd C:\Users\ichry\OneDrive\Desktop\rishiri_konbu_weather_tool

# 統合海洋予報関連ファイルをコミット
git add konbu_flask_final.py
git add requirements.txt
git add ocean_forecast_integration.js
git add kelp_drying_map.html
git add integrated_ocean_forecast.py
git add predict_fog_dissipation.py
git add calculate_viable_drying_hours.py

# 既存のJSONデータファイルもコミット
git add integrated_ocean_forecast.json
git add fog_dissipation_forecast.json
git add viable_drying_hours_forecast.json

git commit -m "Add integrated ocean forecast system with SST analysis"
git push origin main
```

### ステップ2: Renderでの設定

1. **Render Dashboard** (https://dashboard.render.com/) にログイン

2. **New Web Service** をクリック

3. **Connect Repository**
   - GitHubリポジトリを接続
   - `rishiri_konbu_weather_tool` を選択

4. **設定**
   ```
   Name: rishiri-konbu-forecast
   Region: Oregon (US West)
   Branch: main
   Runtime: Python 3
   Build Command: pip install -r requirements.txt
   Start Command: gunicorn konbu_flask_final:app
   ```

5. **環境変数** (Environment Variables)
   ```
   OPENAI_API_KEY=<your-openai-api-key>
   PYTHON_VERSION=3.11.0
   ```

6. **Advanced Settings**
   - Instance Type: **Free** (または **Starter** for better performance)
   - Auto-Deploy: **Yes**

7. **Create Web Service** をクリック

### ステップ3: 初回デプロイ後の設定

デプロイが完了したら（5-10分）、以下のURLでアクセス可能：

```
https://rishiri-konbu-forecast.onrender.com
```

### ステップ4: データファイルの初期化

Renderは**ephemeral filesystem**（一時的なファイルシステム）を使用するため、JSONデータファイルは再起動時に消えます。

**解決策1: 永続化ストレージ（推奨）**

Render Disksを使用：

1. Render Dashboard → your service → **Disks**
2. **Add Disk**
   ```
   Name: forecast-data
   Mount Path: /opt/render/project/data
   Size: 1 GB
   ```

3. `konbu_flask_final.py`を修正してデータパスを`/opt/render/project/data/`に変更

**解決策2: 外部ストレージ（推奨）**

Amazon S3 または Cloudinary を使用：

```python
# konbu_flask_final.py に追加
import os
import boto3

s3 = boto3.client('s3',
    aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
    aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY')
)

def load_forecast_data(filename):
    """S3からJSONデータを取得"""
    try:
        obj = s3.get_object(Bucket='rishiri-forecast-data', Key=filename)
        return json.loads(obj['Body'].read())
    except:
        return {}
```

**解決策3: 定期実行（cron job）**

Render Cron Jobsを使用してデータを定期更新：

1. Render Dashboard → **New Cron Job**
2. 設定：
   ```
   Name: update-ocean-forecast
   Command: python calculate_viable_drying_hours.py && python integrated_ocean_forecast.py
   Schedule: 0 9 * * * (毎日09:00 UTC = 18:00 JST)
   ```

### ステップ5: 動作確認

デプロイ完了後、以下のエンドポイントにアクセス：

1. **メインUI**
   ```
   https://rishiri-konbu-forecast.onrender.com/kelp_drying_map.html
   ```

2. **統合海洋予報API**
   ```
   https://rishiri-konbu-forecast.onrender.com/api/viable_drying_hours
   https://rishiri-konbu-forecast.onrender.com/api/ocean_integrated_forecast
   https://rishiri-konbu-forecast.onrender.com/api/fog_dissipation_forecast
   ```

3. **ヘルスチェック**
   ```
   https://rishiri-konbu-forecast.onrender.com/health
   ```

## ⚠️ 重要な注意事項

### 1. ERA5データのダウンロード

Render環境では**CDSAPIキー**が必要です：

1. Copernicus CDS (https://cds.climate.copernicus.eu/) にアカウント登録
2. API Keyを取得
3. Render環境変数に追加：
   ```
   CDSAPI_URL=https://cds.climate.copernicus.eu/api/v2
   CDSAPI_KEY=<your-uid>:<your-api-key>
   ```

4. `.cdsapirc` を作成する代わりに、`fetch_era5_*.py`を修正：
   ```python
   import cdsapi
   import os

   c = cdsapi.Client(
       url=os.getenv('CDSAPI_URL'),
       key=os.getenv('CDSAPI_KEY')
   )
   ```

### 2. matplotlib のバックエンド

Renderはheadless環境なので、`matplotlib`のバックエンドを設定：

各解析スクリプト（`predict_fog_dissipation.py`など）の先頭に追加：

```python
import matplotlib
matplotlib.use('Agg')  # GUIなし環境用
import matplotlib.pyplot as plt
```

### 3. メモリ制限

Free tierは**512 MB RAM**制限があります。大きなデータセットを扱う場合：

- Starter ($7/month): 2 GB RAM
- Standard ($25/month): 4 GB RAM

## 🔄 継続的デプロイ

Gitにpushすると自動デプロイされます：

```bash
# ローカルで変更
git add .
git commit -m "Update ocean forecast algorithm"
git push origin main

# Renderが自動的に検知してデプロイ
```

## 📊 モニタリング

Render Dashboard で確認：

- **Logs**: リアルタイムログ
- **Metrics**: CPU/メモリ使用率
- **Events**: デプロイ履歴

## 🐛 トラブルシューティング

### エラー: "Module not found"

→ `requirements.txt`に依存関係を追加してreデプロイ

### エラー: "File not found: integrated_ocean_forecast.json"

→ データファイルが生成されていません：
1. Render Shellにアクセス
2. `python calculate_viable_drying_hours.py` を実行
3. または、S3/Disksを使用

### デプロイが遅い（10分以上）

→ 依存関係が多いため正常です。初回のみ時間がかかります

### メモリ不足でクラッシュ

→ Starter以上のプランにアップグレード

## 💰 コスト

- **Free tier**: $0/月（制限: 750時間/月、512 MB RAM、自動スリープ）
- **Starter**: $7/月（推奨: 2 GB RAM、常時稼働）
- **Standard**: $25/月（4 GB RAM、高トラフィック対応）

## 🎯 本番運用のベストプラクティス

1. **Starterプラン以上を使用**（Freeはスリープします）
2. **Render Disks**または**S3**で予報データを永続化
3. **Cron Jobs**で毎日データを更新
4. **環境変数**で機密情報を管理
5. **Custom Domain**を設定（例: `forecast.rishiri-kombu.jp`）
6. **Backup**を定期的に取得

## 📚 参考リンク

- Render公式ドキュメント: https://render.com/docs
- Python on Render: https://render.com/docs/deploy-flask
- Render Disks: https://render.com/docs/disks
- Cron Jobs: https://render.com/docs/cronjobs
