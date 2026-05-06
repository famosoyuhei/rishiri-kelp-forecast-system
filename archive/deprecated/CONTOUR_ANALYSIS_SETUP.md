# 等値線解析セットアップガイド

## 必要なPythonパッケージ

```bash
pip install cdsapi xarray netCDF4 matplotlib cartopy
```

### パッケージ説明
- **cdsapi**: Copernicus Climate Data Store APIクライアント
- **xarray**: NetCDFデータ操作
- **netCDF4**: NetCDFファイルI/O
- **matplotlib**: グラフ・マップ作成
- **cartopy**: 地図投影・地理データ可視化

---

## CDS APIセットアップ

### 1. アカウント登録
https://cds.climate.copernicus.eu/user/register

### 2. APIキー取得
ログイン後、プロフィールページで確認：
https://cds.climate.copernicus.eu/user

### 3. 設定ファイル作成

**Windows:**
```
C:\Users\<username>\.cdsapirc
```

**内容:**
```
url: https://cds.climate.copernicus.eu/api/v2
key: <YOUR-UID>:<YOUR-API-KEY>
```

例:
```
url: https://cds.climate.copernicus.eu/api/v2
key: 12345:abcdef01-2345-6789-abcd-ef0123456789
```

---

## 実行手順

### Step 1: ERA5データ取得
```bash
python fetch_era5_data.py
```

- **処理時間**: 5-15分（データサイズ: 約100-500MB）
- **出力**: `era5_rishiri_summer2024.nc`

### Step 2: 等値線解析・相関計算
```bash
python analyze_era5_contours.py
```

- **処理内容**:
  - 500hPa高度場から空間微分で渦度計算
  - 700hPa鉛直p速度を取得
  - 風向-山角度差との相関を計算
  - 予報データ・ラジオゾンデとの比較

- **出力**: `era5_contour_correlation_results.json`

### Step 3: 等値線マップ可視化
```bash
python visualize_contour_maps.py
```

- **出力**:
  - `contour_500hpa_t0000.png` など（500hPa高度場・渦度）
  - `contour_700hpa_omega_t0000.png` など（700hPa鉛直速度）

---

## トラブルシューティング

### エラー: "cdsapi module not found"
```bash
pip install cdsapi
```

### エラー: "CDS API key not found"
- `.cdsapirc` ファイルが正しい場所にあるか確認
- UID:API-KEYの形式が正しいか確認

### エラー: "cartopy installation failed"
Windowsの場合、conda推奨：
```bash
conda install -c conda-forge cartopy
```

### データダウンロードが遅い
- CDS APIは混雑時に遅延する場合があります
- 数分～数十分かかることがあります

---

## 期待される結果

### 相関係数の比較

| データソース | cos vs 500hPa渦度 | cos vs 700hPa omega |
|-------------|------------------|-------------------|
| 予報モデル | r = +0.788 (強) | r = +0.539 (中) |
| ラジオゾンデ（時間微分） | r = -0.179 (弱) | r = -0.138 (弱) |
| **ERA5（空間微分）** | **r = ?** | **r = ?** |

**仮説:**
- ERA5空間微分による渦度は、ラジオゾンデ時間微分より正確
- 予報モデルとの中間的な相関が期待される
- シノプティックスケール支配度の真の値を推定可能

---

## 次のステップ

1. **ERA5解析実行** → 空間微分による渦度の精度確認
2. **予報モデルとの比較** → どちらが実測に近いか検証
3. **干場データとの照合** → 実際の乾燥条件との相関を確認
4. **WebUI統合** → リアルタイム等値線表示

---

## 参考資料

- **ERA5 Documentation**: https://confluence.ecmwf.int/display/CKB/ERA5
- **CDS API Guide**: https://cds.climate.copernicus.eu/api-how-to
- **xarray Tutorial**: https://docs.xarray.dev/en/stable/getting-started-guide/quick-overview.html
