# 等値線解析タブ刷新 提案書

作成日: 2026-05-20  
対象: 利尻島昆布干場予報システム v2.6.x  
対象ファイル: `start.py`, `kelp_drying_map.html`, `system_specification.md`

## 1. 結論

推奨方式は **C: ハイブリッド（Pythonで計算、Leaflet/Canvasで描画）**。

現行の `GET /api/analysis/contours` は `start.py` の `generate_contour_map()` で matplotlib PNG を生成している。これは専門気象図としては作れるが、Render無料プランではCPU/メモリ負荷が大きく、フロント側では画像を貼るだけなので、干場ごとの値確認やタップ操作に弱い。

刷新後は、バックエンドが「判断に必要な計算済みデータ」だけをJSONで返し、フロントが Leaflet 上に軽量描画する。これにより、サーバーは画像生成をやめ、利用者は地図上でスコア、風、気温、日射を同じ操作感で確認できる。

## 2. レンダリング方式比較

| 方式 | 評価 | このプロジェクトでの判断 |
|---|---|---|
| A: サーバーサイドmatplotlib | 既存実装を使えるが、PNG生成が重く、表示後の操作性が低い | 非推奨。旧APIは互換用に残し、新UIでは使わない |
| B: フロントエンドCanvasのみ | サーバー負荷は最小。ただし334地点分の予報計算や地形補正をJSへ移植する必要がある | 非推奨。既存の科学計算ロジックと二重管理になる |
| C: ハイブリッド | Pythonの既存予報ロジックを活かしつつ、描画は軽量・インタラクティブ | 推奨。品質と実装コストのバランスが最良 |

推奨描画:

- 乾燥スコア: Leaflet `CircleMarker` + 数値ラベル `DivIcon`
- 風: 代表グリッド点の `Polyline` 矢印 + 色分け
- 気温: 代表点/グリッド点の半透明円、必要ならCanvasで補間風ヒートマップ
- 日射: 半透明円または粗いCanvasヒートマップ

等値線らしい滑らかな線は、島内5kmメッシュでは「見た目だけ精密」になりやすい。初期実装では「点・粗い面」で表現し、補間は補助表現に留める。

## 3. 一括データ取得の設計

### 推奨

Open-Meteoへの実リクエストは、1回の画面表示につき **1〜3回** に抑える。

Open-Meteo Forecast API は `latitude=...,...&longitude=...,...` の複数座標リクエストに対応しているため、334地点を1地点ずつ呼ぶ必要はない。ただし334地点 x hourly 7日分を一括で返すとレスポンスが大きいので、用途別に分ける。

### データ取得単位

1. **乾燥スコア分布**
   - 対象: 334地点すべて
   - Open-Meteo呼び出し: 1回、複数座標リクエスト
   - 取得変数: `temperature_2m`, `relative_humidity_2m`, `wind_speed_10m`, `wind_direction_10m`, `cloud_cover`, `shortwave_radiation`, `precipitation`, `precipitation_probability`, `dewpoint_2m`, `surface_pressure`
   - 集計: 日中 04:00〜16:00 JST の代表値をPythonで算出
   - 注意: 334地点は同じ5kmグリッドに多く重なるため、値は似る。地形補正・海岸/森林補正・onshore判定で差を出す。

2. **風・気温・日射分布**
   - 対象: 5x5または7x7の代表グリッド
   - Open-Meteo呼び出し: 1回、複数座標リクエスト
   - 理由: 334地点の矢印やヒート点は見づらい。島全体傾向は25〜49点で十分。

3. **選択干場の詳細**
   - 既存 `/api/forecast?lat=...&lon=...` を継続利用
   - 新しい4図とは別に、カード/チャートで詳細を出す。

### キャッシュ

`/api/analysis/field` にメモリキャッシュまたはファイルキャッシュを入れる。

- キー: `type`, `day`, `hour`, `dataset_version`
- TTL: 30〜60分
- 保存先: まずはプロセスメモリ。Render再起動で消えてよい
- 将来: `forecast_cache/analysis_field_YYYYMMDDHH_type_day.json`

Open-Meteo JMA MSM/GSMは短時間に何度も変わるものではないため、利用者が複数人いても同じJSONを返せばよい。

## 4. 新APIエンドポイント仕様

### エンドポイント

`GET /api/analysis/field?type=score|wind|humidity|temperature|solar&day=0&hour=10`

パラメータ:

| name | required | default | 説明 |
|---|---:|---|---|
| `type` | yes | なし | `score`, `wind`, `temperature`, `solar` |
| `day` | no | `0` | 0=今日、1=明日、最大6 |
| `hour` | no | type別 | 表示対象JST時刻。scoreは04〜16集計なので省略可 |
| `mode` | no | `auto` | `spots`, `grid`, `both`, `auto` |

### 共通レスポンス

```json
{
  "status": "success",
  "type": "score",
  "day": 0,
  "target_date": "2026-05-20",
  "timezone": "Asia/Tokyo",
  "generated_at": "2026-05-20T09:12:00+09:00",
  "cache": {
    "hit": false,
    "ttl_seconds": 3600
  },
  "data_resolution": {
    "source_model": "Open-Meteo JMA MSM/GSM",
    "source_grid_note": "利尻島内はMSMで概ね5kmメッシュ。干場間の細差は地形補正を含む推定値",
    "rendering": "client_leaflet"
  },
  "legend": {
    "unit": "score",
    "stops": [
      {"value": 80, "label": "干せる", "color": "#1f9d55"},
      {"value": 50, "label": "微妙", "color": "#f2c94c"},
      {"value": 0, "label": "厳しい", "color": "#d64545"}
    ]
  },
  "points": []
}
```

### `type=score`

334地点を返す。マーカー上に数値を出す前提。

```json
{
  "status": "success",
  "type": "score",
  "summary": {
    "total": 334,
    "excellent": 42,
    "good": 118,
    "fair": 91,
    "poor": 83,
    "best_spot": {"name": "H_1631_1434", "score": 86}
  },
  "points": [
    {
      "name": "H_1631_1434",
      "lat": 45.1631,
      "lon": 141.1434,
      "town": "利尻町",
      "district": "沓形",
      "buraku": "神居",
      "spot_type": "hoshiba",
      "value": 86,
      "category": "excellent",
      "metrics": {
        "precipitation": 0.0,
        "min_humidity": 82,
        "avg_wind": 2.8,
        "avg_solar_radiation": 520,
        "pop_max": 10
      },
      "color": "#1f9d55"
    }
  ]
}
```

### `type=wind`

5x5または7x7の代表グリッド点を返す。単位はフロントで m/s に統一。

```json
{
  "status": "success",
  "type": "wind",
  "hour": 10,
  "thresholds": {"drying_min_wind": 2.0},
  "vectors": [
    {
      "lat": 45.18,
      "lon": 141.20,
      "speed": 2.6,
      "direction": 285,
      "u": -2.51,
      "v": 0.67,
      "category": "good",
      "color": "#1f9d55"
    }
  ]
}
```

### `type=temperature`

代表グリッド点を返す。Open-Meteoの `temperature_2m` はAPI側の標高補正済み値として扱い、独自気温補正はしない。

```json
{
  "status": "success",
  "type": "temperature",
  "hour": 10,
  "legend": {"unit": "°C", "min": 10, "max": 24},
  "grid": [
    {"lat": 45.18, "lon": 141.20, "value": 18.4, "color": "#f2c94c"}
  ]
}
```

### `type=solar`

`shortwave_radiation` を使う。乾燥判断では 400 W/m² 以上を促進、50 W/m² 未満を困難として表示する。

```json
{
  "status": "success",
  "type": "solar",
  "hour": 10,
  "thresholds": {
    "good": 400,
    "poor": 50
  },
  "grid": [
    {"lat": 45.18, "lon": 141.20, "value": 510, "category": "good", "color": "#1f9d55"}
  ]
}
```

## 5. `shortwave_radiation` 追加方針

Open-Meteo JMA APIでは `shortwave_radiation` は hourly 変数として取得できる。値はGHI（全天日射量）で、単位は W/m²、直前1時間平均。

現行 `start.py` では `/api/forecast` のURLに `direct_radiation` が含まれており、`hour_data['solar_radiation']` に代入している。

現行:

```python
hourly=...,cloud_cover,direct_radiation,pressure_msl,...
...
'solar_radiation': hourly['direct_radiation'][h] if hourly['direct_radiation'][h] is not None else None,
```

推奨:

```python
hourly=...,cloud_cover,shortwave_radiation,direct_radiation,pressure_msl,...
...
'solar_radiation': (
    hourly['shortwave_radiation'][h]
    if h < len(hourly.get('shortwave_radiation', [])) and hourly['shortwave_radiation'][h] is not None
    else (
        hourly['direct_radiation'][h]
        if h < len(hourly.get('direct_radiation', [])) and hourly['direct_radiation'][h] is not None
        else None
    )
),
```

理由:

- 乾燥に効く地表への総日射は `shortwave_radiation` のほうが自然。
- `direct_radiation` は直達成分で、曇天時の散乱光を過小評価しやすい。
- 既存の `solar_radiation` フィールド名は維持し、フロントやスコア計算の影響を最小化する。

## 6. UI/UX設計

現行の「カテゴリ選択 → 時刻選択 → 解析実行」は廃止する。

新しい体験:

1. 利用者が干場を選ぶ
2. 予報パネルに「今日 / 明日 / 3日目...」の横スクロール日付チップを表示
3. 選んだ日の4図を自動読み込み
4. 各図は縦スクロールで確認

### モバイル優先レイアウト

```
[選択中の干場名・日付チップ]
[乾燥スコア分布]  高さ 260px
  - 選択干場を太枠
  - 80点以上: 緑、50〜79: 黄、50未満: 赤

[風向風速]  高さ 220px
  - 矢印の向きと長さ
  - 2.0m/s未満は灰/赤、2.0m/s以上は緑

[気温分布]  高さ 180px
  - 点/面の色
  - 選択干場の気温を大きく表示

[日射量期待値]  高さ 180px
  - 400 W/m²以上を緑、50未満を赤
```

デスクトップでは、サイドバー内に小さく押し込めず、地図上オーバーレイまたはサイドバー内2列カードにする。運用画面としてはカードの角丸は8px以下、凡例は小さく固定し、説明文を増やしすぎない。

### 操作

- タブ名は「等値線解析」から **「島内分布」** または **「干場判断マップ」** に変更。
- 初期表示は `score`。他の3図は下に続けて自動表示。
- 4図それぞれに「地図に重ねる」トグルを持たせる。
- 読み込み中はカードごとにスケルトン表示。
- API失敗時は「地図は更新できませんでした。個別予報は表示できます」と短く出す。

## 7. 実装ステップ計画

### Phase 1: データ基盤（1.5〜2.5日）

1. `shortwave_radiation` を `/api/forecast` のhourlyに追加し、`solar_radiation` の優先ソースにする。
2. `load_spots_data()` 相当の共通ヘルパーを整備する。
3. `build_analysis_grid_points()` で利尻島内5x5/7x7代表点を生成する。
4. Open-Meteo複数座標リクエスト関数を追加する。
5. 30〜60分TTLの簡易キャッシュを実装する。

### Phase 2: 新API（2〜3日）

1. `GET /api/analysis/field` を追加。
2. `type=score` で334地点のスコアを返す。
3. `type=wind|temperature|solar` で代表グリッドを返す。
4. レスポンスに凡例、閾値、注意書き、キャッシュ情報を含める。
5. 既存 `/api/analysis/contours` は互換用に残すが、新UIからは呼ばない。

### Phase 3: フロント描画（3〜5日）

1. 既存の等値線タブHTMLを「島内分布」カードに置換。
2. Leafletレイヤー管理を追加し、スコア/風/気温/日射を別レイヤーでON/OFF。
3. 乾燥スコアは334地点のCircleMarker + 数値ラベル。
4. 風は代表点の矢印Polyline。
5. 気温・日射は代表点の半透明円、必要ならCanvas補間へ拡張。
6. 日付チップ変更時に4図を再取得。

### Phase 4: 検証・整理（1〜2日）

1. `/api/analysis/field` の単体テストを追加。
2. 334地点レスポンスサイズと応答時間を計測。
3. モバイル/デスクトップで重なり・文字切れを確認。
4. `README.md` と `system_specification.md` を更新。
5. 古い専門カテゴリのUIを削除し、旧APIは非推奨扱いにする。

合計目安: **7.5〜12.5日**。最初のMVPは `score` と `wind` の2図だけなら **3〜5日** で可能。

## 8. 実装上の注意

- 334地点すべてに対して個別HTTP呼び出しはしない。
- 滑らかな等値線に見せすぎない。5kmメッシュの限界をUI上も明示する。
- スコアは `calculate_enhanced_drying_score()` を必ず流用する。
- 気温はOpen-Meteoが標高補正済みなので、独自気温補正を重ねない。
- 風速は km/h から m/s に統一する。
- 表示時刻はすべて JST。
- Render無料プランではmatplotlib生成を新UIから外す。

## 9. 旧機能の扱い

削除対象:

- 500hPa渦度
- 700hPa鉛直流
- 850hPa相当温位
- 300hPaジェット気流
- 200hPa高度偏差
- 有義波高
- 波向・波周期

これらは研究・管理者向けには有用な可能性があるため、完全削除ではなく、初回はUIから外してコードは残す。次の整理フェーズで `archive/` への移動または管理者専用化を検討する。

## 10. 推奨する最初のPR範囲

最初のPRは大きくしすぎない。

1. `shortwave_radiation` 追加
2. `/api/analysis/field?type=score|wind`
3. フロントの「島内分布」タブMVP
4. 旧 `/api/analysis/contours` は残す

`temperature` と `solar` の地図カードは、API設計だけ先に入れて、描画は第2PRでもよい。
