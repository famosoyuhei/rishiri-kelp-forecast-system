# 統合海洋予報のWebUI統合ガイド

## 完成したシステム

以下のAPIエンドポイントが`konbu_flask_final.py`に追加されました：

- `/api/ocean_integrated_forecast` - SST大雨リスク予報
- `/api/fog_dissipation_forecast` - 海霧消散予測
- `/api/viable_drying_hours` - **連続作業可能時間予報**（メイン）
- `/api/sst_precipitation_correlation` - SST-降水量相関
- `/api/ezo_tsuyu_analysis` - 蝦夷梅雨解析
- `/api/sst_comparison` - SST年間比較

## kelp_drying_map.html への統合手順

### ステップ1: HTMLセクションの追加

`kelp_drying_map.html`の**行604**（エリア絞り込みセクションの前）に以下を追加：

```html
    <!-- 統合海洋予報セクション -->
    <div class="ocean-forecast-section" style="margin: 20px 0; padding: 15px; background: white; border-radius: 10px; box-shadow: 0 2px 8px rgba(0,0,0,0.1);">
        <h3 style="color: #1e40af; border-bottom: 2px solid #3b82f6; padding-bottom: 10px;">
            🌊 統合海洋予報 - 連続作業可能時間
        </h3>
        <p style="color: #666; font-size: 14px; margin: 10px 0;">
            海水温・海霧・降水リスクを統合した実用的な作業時間予報
        </p>
        <div id="oceanForecastContainer">
            <p style="text-align: center; color: #999;">読み込み中...</p>
        </div>
    </div>
```

### ステップ2: JavaScriptの追加

`kelp_drying_map.html`の`<script>`セクション（ファイル末尾付近）に以下を追加：

```html
<script src="/ocean_forecast_integration.js"></script>
```

または、`ocean_forecast_integration.js`の内容を直接`<script>`タグ内にコピー＆ペースト。

### ステップ3: Flaskサーバーの再起動

```bash
# サーバーを停止（Ctrl+C）
# 再起動
python konbu_flask_final.py
```

### ステップ4: アクセス

ブラウザで`http://localhost:5000/kelp_drying_map.html`を開く。

## 表示内容

### 週間サマリー

```
📊 週間作業可能率
     85.7%
作業可能日: 6/7日
● 理想的: 4日  ● ギリギリ: 2日  ● 不適: 1日
```

### 日別予報（例：8月26日）

```
2025-08-26 (火) [UNSUITABLE]

作業可能時間: 10:00-14:00  4時間

霧消散: 10:00 🌫️ (朝霧)
降水リスク: HIGH

[UNSUITABLE] Do not attempt outdoor drying

No viable outdoor drying time
```

## スタイルのカスタマイズ

カラーコードを変更したい場合は、`ocean_forecast_integration.js`内の：

```javascript
const colorMap = {
    'green': '#28a745',   // 理想的（EXCELLENT）
    'yellow': '#ffc107',  // ギリギリ（ACCEPTABLE）
    'orange': '#fd7e14',  // 不十分（INSUFFICIENT）
    'red': '#dc3545'      // 不適（UNSUITABLE）
};
```

を編集してください。

## 実データの更新

1. **データ取得スクリプトの実行**：

```bash
# 毎日実行（自動化推奨）
python fetch_era5_ocean_data_2025.py  # 海洋データ
python fetch_era5_precipitation_2024_2025.py  # 降水量データ

# 解析実行
python integrated_ocean_forecast.py
python predict_fog_dissipation.py
python calculate_viable_drying_hours.py
```

2. **cronジョブ設定例**（Linux/Mac）：

```cron
# 毎日09:00 JSTに実行
0 9 * * * cd /path/to/rishiri_konbu_weather_tool && python integrated_ocean_forecast.py
5 9 * * * cd /path/to/rishiri_konbu_weather_tool && python predict_fog_dissipation.py
10 9 * * * cd /path/to/rishiri_konbu_weather_tool && python calculate_viable_drying_hours.py
```

3. **Windowsタスクスケジューラ**：
   - タスクスケジューラを開く
   - 「基本タスクの作成」
   - トリガー: 毎日09:00
   - アクション: プログラムの開始
   - プログラム: `python`
   - 引数: `C:\path\to\calculate_viable_drying_hours.py`

## トラブルシューティング

### エラー: "Ocean forecast data not available"

→ JSONファイルが生成されていません。以下を実行：

```bash
python calculate_viable_drying_hours.py
```

### データが古い

→ 最新データを取得：

```bash
python fetch_era5_ocean_data_2025.py
python integrated_ocean_forecast.py
python predict_fog_dissipation.py
python calculate_viable_drying_hours.py
```

### 表示が崩れる

→ ブラウザのキャッシュをクリア（Ctrl+Shift+R）

## システムの価値

- **作業可否の明確化**: 4時間しかない日は「不適」と明示
- **経済的判断**: 室内乾燥コスト（50,000円/日）を回避
- **実務基準**: 最低8時間、理想10時間（実際の漁業者の感覚）
- **月別日照時間対応**: 6月は4時～、8月は5時～

## 次のステップ

1. リアルタイムSST取得（NOAA/JAXA衛星データ）
2. JMA予報API統合（降水量予測）
3. 通知機能（作業不適日の前日アラート）
4. モバイルアプリ化（PWA）
