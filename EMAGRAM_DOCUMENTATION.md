# エマグラム機能 完全仕様書

**作成日**: 2025年12月7日
**バージョン**: v2.4.2
**対象問題**: 問題4 - エマグラム機能の仕様詳細

---

## 📋 目次

1. [概要](#概要)
2. [データソース](#データソース)
3. [物理計算アルゴリズム](#物理計算アルゴリズム)
4. [雲層高度検出](#雲層高度検出)
5. [UI表示仕様](#ui表示仕様)
6. [θₑ補正機能](#θₑ補正機能)
7. [技術詳細](#技術詳細)

---

## 概要

### 目的

利尻島昆布干場予報システムの一部として、大気の鉛直構造を可視化し、以下の情報を提供する：

- **気温・露点温度プロファイル**: 地上から上層（1000hPa～100hPa）までの気温・露点温度の垂直分布
- **雲層高度**: LCL（雲底）、LFC（自由対流高度）、EL（雲頂）の自動検出
- **断熱プロセス**: 乾燥断熱線・湿潤断熱線の表示
- **大気安定度**: 逆転層・大気不安定度の解析

### システム位置づけ

**表示場所**: kelp_drying_map.html内、干場選択時に自動表示
**アクセス方法**: 干場を選択すると「📊 簡易エマグラム」セクションが表示
**更新頻度**: 時刻選択ドロップダウンから任意の時刻を選択可能（6:00-18:00 JST、3時間間隔）

---

## データソース

### 1. バックエンドAPI

**エンドポイント**: `/api/emagram`

**実装場所**: `start.py` lines 1737-1943

**リクエストパラメータ**:
```
lat: 緯度（float、デフォルト: 45.242）
lon: 経度（float、デフォルト: 141.242）
time: 予報時刻オフセット（int、デフォルト: 0、時間単位）
apply_theta_e_correction: θₑ補正適用フラグ（'true'/'false'、デフォルト: 'false'）
wind_direction: 風向（float、度、北を0度）※補正時必須
```

**レスポンス構造**:
```json
{
  "status": "success",
  "data": {
    "pressure": [1000, 975, 950, ..., 100],  // 気圧面リスト（hPa）
    "temperature": [-2.5, -1.8, ...],        // 各気圧面の気温（℃）
    "dewpoint": [-5.2, -4.3, ...],           // 各気圧面の露点温度（℃）
    "height": [120, 350, ...],               // 各気圧面の高度（m）
    "time": "2025-12-07T09:00"               // 予報時刻（JST）
  },
  "location": {"lat": 45.242, "lon": 141.242},
  "message": "16気圧面のデータを取得（2025-12-07T09:00）",
  "correction_applied": false,
  "correction_info": null  // θₑ補正時のみ情報を含む
}
```

### 2. Open-Meteo Pressure Level API

**データ取得元**: `https://api.open-meteo.com/v1/forecast`

**取得気圧面**: 16面（1000, 975, 950, 925, 900, 850, 800, 700, 600, 500, 400, 300, 250, 200, 150, 100 hPa）

**取得変数**:
- `temperature_{pressure}hPa`: 気温（℃）
- `dewpoint_{pressure}hPa`: 露点温度（℃）
- `geopotential_height_{pressure}hPa`: ジオポテンシャル高度（m）

**予報期間**: 7日間（168時間）

**時刻基準**: Asia/Tokyo（JST、UTC+9）

**実装**: `start.py` lines 1768-1819

---

## 物理計算アルゴリズム

### 1. 乾燥断熱線（Dry Adiabat）

**物理式**:
```
T = T0 × (P / P0)^(Rd/cp)
```

**定数**:
- `Rd = 287 J/(kg·K)`: 乾燥空気の気体定数
- `cp = 1004 J/(kg·K)`: 定圧比熱
- `Rd/cp ≈ 0.286`: ポアソン指数

**実装**: `kelp_drying_map.html` lines 3382-3394

```javascript
function calculateDryAdiabat(T0, P0, P) {
    const Rd_cp = 287 / 1004;
    return (T0 + 273.15) * Math.pow(P / P0, Rd_cp) - 273.15;
}
```

**用途**: 地上からLCL（雲底）までの気塊の断熱上昇を表現

---

### 2. 湿潤断熱線（Moist Adiabat）

**物理式**:
```
Γs = g(1 + Lws/RdT) / (cp + L²wsε/RdT²)
```

**記号**:
- `Γs`: 湿潤断熱減率（K/m）
- `g = 9.81 m/s²`: 重力加速度
- `L = 2.5×10⁶ J/kg`: 蒸発の潜熱
- `ws`: 飽和混合比（kg/kg）
- `Rd = 287 J/(kg·K)`: 乾燥空気の気体定数
- `cp = 1004 J/(kg·K)`: 定圧比熱
- `ε = 0.622`: 分子量比（水蒸気/乾燥空気）
- `T`: 絶対温度（K）

**実装**: `kelp_drying_map.html` lines 3403-3450

```javascript
function calculateMoistAdiabat(T0, P0, P1) {
    const g = 9.81, L = 2.5e6, Rd = 287, cp = 1004, epsilon = 0.622;

    let T = T0 + 273.15;  // K
    const numSteps = Math.abs(P0 - P1) / 10;
    const dP = (P1 - P0) / numSteps;

    for (let i = 0; i < numSteps; i++) {
        const P = P0 + i * dP;

        // 飽和混合比の計算
        const es = 6.112 * Math.exp(17.67 * (T - 273.15) / (T - 29.65));
        const ws = epsilon * es / (P - es);

        // 湿潤断熱減率の計算
        const numerator = g * (1 + (L * ws) / (Rd * T));
        const denominator = cp + (L * L * ws * epsilon) / (Rd * T * T);
        const gamma_s = numerator / denominator;

        // 気圧変化に対する温度変化
        const dT = -gamma_s * (dP / (P * g / (Rd * T)));
        T += dT;
    }

    return T - 273.15;  // ℃に変換
}
```

**用途**: LCL（雲底）から上空への飽和気塊の断熱上昇を表現

---

### 3. LCL（Lifting Condensation Level：雲底高度）

**物理的意味**: 地上の気塊を乾燥断熱的に持ち上げたとき、飽和（凝結開始）に達する高度

**計算手法**: 反復計算による探索

**アルゴリズム**:
1. 地上の気温（T_surface）、露点温度（Td_surface）、気圧（P_surface）を取得
2. 地上の飽和混合比（ws_surface）を計算
3. 気圧を10hPaずつ下げながら（P = P_surface - 10, P_surface - 20, ...）：
   - 乾燥断熱線に沿って気温を計算：`T_dry = T_surface × (P / P_surface)^0.286`
   - その気圧・気温での飽和混合比（ws）を計算
   - `ws ≈ ws_surface`となる気圧を発見 → LCL
4. 許容誤差1%以内でマッチする気圧・気温を返す

**実装**: `kelp_drying_map.html` lines 3452-3467

```javascript
function calculateLCL(Tsurface, Tdsurface, Psurface) {
    const ws_surface = calculateSaturationMixingRatio(Tdsurface, Psurface);

    for (let P = Psurface - 10; P >= 300; P -= 10) {
        const T_dry = calculateDryAdiabat(Tsurface, Psurface, P);
        const ws = calculateSaturationMixingRatio(T_dry, P);

        if (ws <= ws_surface * 1.01) {  // 1%の許容誤差
            return { pressure: P, temperature: T_dry };
        }
    }
    return null;
}
```

**出力**: `{pressure: 950, temperature: -3.2}`（例）

---

### 4. LFC（Level of Free Convection：自由対流高度）

**物理的意味**: 持ち上げられた気塊が環境より暖かくなり、自発的に上昇を開始する高度

**判定条件**: 湿潤断熱線が環境気温線を下から上に交差する点（負→正への符号変化）

**アルゴリズム**:
1. LCLから湿潤断熱線を10hPa刻みで計算
2. 各気圧で環境気温を線形補間で取得
3. `diff = T_moist - T_env`（気塊温度 - 環境気温）を計算
4. 前の気圧での`prevDiff`と比較：
   - `prevDiff < 0 && diff > 0` → **LFC検出**
   - 最初の交差点をLFCとして記録

**実装**: `kelp_drying_map.html` lines 3501-3526

```javascript
for (let P = lcl.pressure; P >= 100; P -= 10) {
    const T_moist = calculateMoistAdiabat(lcl.temperature, lcl.pressure, P);
    const envTemp = interpolateTemperature(pressures, temps, P);

    const diff = T_moist - envTemp;
    const prevDiff = prevMoist - prevEnvTemp;

    // LFC: 負→正への変化
    if (!lfc && prevDiff < 0 && diff > 0) {
        lfc = { pressure: P, temperature: T_moist };
        console.log(`LFC detected: ${P}hPa, prevDiff=${prevDiff.toFixed(2)}, diff=${diff.toFixed(2)}`);
    }
}
```

**出力**: `{pressure: 800, temperature: -8.5}`（例）

---

### 5. EL（Equilibrium Level：雲頂高度）

**物理的意味**: 持ち上げられた気塊が再び環境と同じ温度になり、上昇が停止する高度

**判定条件**: 湿潤断熱線が環境気温線を上から下に交差する点（正→負への符号変化）、**LFC検出後のみ**

**アルゴリズム**:
1. LFC検出後も湿潤断熱線の計算を継続
2. `diff = T_moist - T_env`の符号変化を監視
3. `prevDiff > 0 && diff < 0` → **EL検出**
4. EL検出後、ループを終了（それ以上の交差は無視）

**実装**: `kelp_drying_map.html` lines 3527-3532

```javascript
// EL: 正→負への変化（LFC検出後のみ）
else if (lfc && !el && prevDiff > 0 && diff < 0) {
    el = { pressure: P, temperature: T_moist };
    console.log(`EL detected: ${P}hPa, prevDiff=${prevDiff.toFixed(2)}, diff=${diff.toFixed(2)}`);
    break;
}
```

**出力**: `{pressure: 300, temperature: -35.2}`（例）

**特殊ケース**: ELが100hPa以上にある場合、検出不可として表示

---

### 6. 飽和混合比の計算

**実装**: `kelp_drying_map.html` lines 3361-3380

```javascript
function calculateSaturationMixingRatio(T_celsius, P_hPa) {
    const T = T_celsius;  // ℃
    const P = P_hPa;      // hPa

    // Tetensの式で飽和蒸気圧を計算（hPa）
    const es = 6.112 * Math.exp(17.67 * T / (T + 243.5));

    // 飽和混合比: ws = ε × es / (P - es)
    const epsilon = 0.622;  // 分子量比（水蒸気/乾燥空気）
    const ws = epsilon * es / (P - es);

    return ws;  // kg/kg
}
```

---

## 雲層高度検出

### 検出フロー

```
地上データ取得（P_surface, T_surface, Td_surface）
    ↓
LCL計算（乾燥断熱線探索）
    ↓
乾燥断熱線描画（地上 → LCL）
    ↓
湿潤断熱線計算（LCL → 100hPa）
    ↓
環境気温線との交差判定
    ↓
LFC検出（負→正）
    ↓
EL検出（正→負）
```

### 実装関数

**関数名**: `calculateCloudLevels(pressures, temps, dewpoints)`

**場所**: `kelp_drying_map.html` lines 3469-3548

**入力**:
- `pressures`: 気圧配列（降順、例: [1000, 975, ..., 100]）
- `temps`: 気温配列（℃）
- `dewpoints`: 露点温度配列（℃）

**出力**:
```javascript
{
    lcl: {pressure: 950, temperature: -3.2},      // 雲底
    lfc: {pressure: 800, temperature: -8.5},      // 自由対流高度
    el: {pressure: 300, temperature: -35.2},      // 雲頂
    dryAdiabatLine: [{x: 5, y: 1000}, ...],      // 乾燥断熱線
    moistAdiabatLine: [{x: -3, y: 950}, ...]     // 湿潤断熱線
}
```

### 状態パターン

| 状態 | LCL | LFC | EL | 意味 |
|-----|-----|-----|-----|------|
| 安定成層 | ✅ | ❌ | ❌ | 雲は形成されるが対流は発生しない |
| 条件付き不安定 | ✅ | ✅ | ✅ | 通常の対流雲（積雲～積乱雲） |
| 強い不安定 | ✅ | ✅ | ❌ | 対流が100hPa以上に達する（対流圏界面突破） |

---

## UI表示仕様

### 1. 表示位置

**ファイル**: `kelp_drying_map.html`
**セクション**: lines 945-981（HTML構造）、3340-3740（JavaScript機能）

**表示タイミング**: 干場選択時に自動的に`emagramSection`が表示される

### 2. UI構成要素

#### (1) タイトル
```html
<h3>📊 簡易エマグラム - 気温・露点温度鉛直プロファイル</h3>
```

#### (2) 時刻選択ドロップダウン
```html
<select id="emagramTimeSelect" onchange="loadEmagramData()">
    <option value="2">06:00（始業前）</option>
    <option value="5" selected>09:00（作業開始）</option>
    <option value="8">12:00（正午）</option>
    <option value="11">15:00（午後）</option>
    <option value="14">18:00（終業）</option>
</select>
```

**選択肢の設計思想**: 昆布干場の作業時間帯（6:00-18:00）をカバー、3時間間隔

#### (3) キャンバス（Chart.js）
```html
<canvas id="emagramCanvas" style="max-width: 800px; height: 500px;"></canvas>
```

**サイズ**: 最大幅800px、高さ500px（レスポンシブ）

#### (4) 読み方説明
```html
<p style="font-size: 0.9em; color: #666;">
    <strong>読み方:</strong>
    赤線が気温、青線が露点温度を示します。
    2つの線が近いほど湿度が高く、離れているほど乾燥しています。
    雲底（LCL）、自由対流高度（LFC）、雲頂（EL）が自動検出されます。
</p>
```

### 3. Chart.js設定

**チャートタイプ**: `line`（折れ線グラフ）

**データセット構成**:
1. **気温線**（赤、実線、太さ3）
2. **露点温度線**（青、実線、太さ3）
3. **乾燥断熱線**（シアン、破線[10,5]、太さ2）
4. **湿潤断熱線**（緑、破線[5,5]、太さ2）
5. **LCLマーカー**（黄、三角、サイズ8）
6. **LFCマーカー**（オレンジ、回転四角、サイズ8）
7. **ELマーカー**（紫、星、サイズ8）

**軸設定**:
- **X軸**: 気温（℃）、リニアスケール
- **Y軸**: 気圧（hPa）、リニアスケール、**逆順表示**（上空ほど上に表示）

**実装**: `kelp_drying_map.html` lines 3672-3736

---

## θₑ補正機能

### 概要

エマグラムデータにθₑ（相当温位）保存補正を適用し、風上地点の影響を考慮した気温・露点温度プロファイルを提供する。

### 補正アルゴリズム

**実装**: `start.py` lines 37-259（`ThetaECorrector`クラス）、1821-1928（エマグラムAPI内の補正適用）

#### 1. 風上地点の選定

**関数**: `theta_e_corrector.select_windward_spot(lat, lon, wind_direction, spots_df)`

**ロジック**:
- 指定地点から上流方向（風向 ± 30°）にある干場を検索
- 距離5～50km範囲内の干場を候補とする
- 最も近い干場を風上地点として選定

#### 2. 層別補正戦略

| 気圧層 | 補正方法 | 理由 |
|-------|---------|------|
| **下層**（850hPa以上） | 風上θₑ + RHによるハイブリッド補正（100%適用） | 風上の気団特性が強く影響 |
| **中層**（500-850hPa） | API値をそのまま使用 | 遷移領域、簡易処理 |
| **上層**（500hPa未満） | 参照地点（鴛泊）の値を使用 | 広域の上層大気を代表 |

#### 3. ハイブリッド補正式

**実装**: `start.py` lines 163-259（`apply_hybrid_correction`メソッド）

```python
# 下層（850hPa以上）の場合
windward_theta_e = equivalent_potential_temperature(w_temp, w_dewpoint, p)
windward_rh = e / es  # 風上の相対湿度

# θₑ保存補正の適用
corr_temp, corr_dewpoint = apply_hybrid_correction(
    p, windward_theta_e, windward_rh,
    api_temp, api_dewpoint,
    ref_temp, ref_dewpoint
)
```

### 補正レスポンス

**補正適用時のレスポンス追加情報**:
```json
{
  "correction_applied": true,
  "correction_info": {
    "windward_spot": {
      "name": "利尻町沓形地区神居",
      "lat": 45.242,
      "lon": 141.242
    },
    "wind_direction": 270.0,
    "method": "Hybrid theta-e correction (lower: 100%, middle: decay, upper: reference)"
  }
}
```

---

## 技術詳細

### 1. フロントエンド実装

**ファイル**: `kelp_drying_map.html`

**主要関数一覧**:

| 関数名 | 行数 | 機能 |
|-------|------|------|
| `loadEmagramData()` | 3340-3359 | `/api/emagram`からデータ取得 |
| `calculateSaturationMixingRatio()` | 3361-3380 | 飽和混合比計算 |
| `calculateDryAdiabat()` | 3382-3394 | 乾燥断熱線計算 |
| `interpolateTemperature()` | 3396-3401 | 気温の線形補間 |
| `calculateMoistAdiabat()` | 3403-3450 | 湿潤断熱線計算（物理的厳密） |
| `calculateLCL()` | 3452-3467 | LCL（雲底）計算 |
| `calculateCloudLevels()` | 3469-3548 | 雲層高度総合計算 |
| `drawEmagram()` | 3551-3740 | Chart.jsによる描画 |
| `updateEmagramAnalysis()` | 3742+ | 逆転層など追加解析 |

### 2. バックエンド実装

**ファイル**: `start.py`

**主要部分**:

| 部分 | 行数 | 機能 |
|-----|------|------|
| `ThetaECorrector`クラス | 37-259 | θₑ補正システム全体 |
| `/api/emagram`エンドポイント | 1737-1943 | エマグラムデータ提供API |
| Open-Meteo API呼び出し | 1768-1819 | 16気圧面データ取得 |
| θₑ補正適用ロジック | 1821-1928 | 風上地点選定と補正計算 |

### 3. データフロー

```
[ユーザー操作: 干場選択 + 時刻選択]
    ↓
[フロントエンド: loadEmagramData()]
    ↓ HTTP GET /api/emagram?lat=X&lon=Y&time=Z
[バックエンド: get_emagram_data()]
    ↓ HTTP GET https://api.open-meteo.com/v1/forecast
[Open-Meteo API]
    ↓ JSON（16気圧面×3変数）
[バックエンド: データ整形]
    ↓ （オプション）θₑ補正適用
[バックエンド: JSONレスポンス]
    ↓
[フロントエンド: calculateCloudLevels()]
    ↓ LCL/LFC/EL計算
[フロントエンド: drawEmagram()]
    ↓ Chart.js描画
[ユーザー: エマグラム表示]
```

### 4. エラーハンドリング

**フロントエンド**:
```javascript
.catch(error => {
    console.error('エマグラムデータの取得に失敗しました:', error);
    alert('エマグラムデータを読み込めませんでした。');
});
```

**バックエンド**:
```python
except Exception as e:
    return jsonify({"status": "error", "message": str(e)}), 500
```

### 5. パフォーマンス最適化

**気圧刻み**: 10hPa刻みで計算（精度と速度のバランス）

**タイムアウト設定**:
- Open-Meteo API: 15秒
- 風上地点API: 10秒

**キャッシュ**: なし（リアルタイム性を重視）

---

## まとめ

### 実装済み機能

- ✅ **16気圧面データ取得**（1000-100hPa）
- ✅ **物理的に厳密な湿潤断熱線計算**
- ✅ **LCL自動検出**（雲底）
- ✅ **LFC自動検出**（自由対流高度）
- ✅ **EL自動検出**（雲頂）
- ✅ **Chart.js可視化**
- ✅ **θₑ補正機能**（オプション）
- ✅ **逆転層検出**（`updateEmagramAnalysis`）

### 未実装機能

- ❌ **CCL（Convective Condensation Level）**: 対流凝結高度は計算されていない
- ❌ **CAPE/CIN計算**: 対流有効位置エネルギー・対流抑制エネルギーは未実装
- ❌ **ショワルター指数**: 大気不安定度指数は未実装

### 今後の拡張可能性

- [ ] PNG画像エクスポート機能
- [ ] CAPE/CIN計算の追加
- [ ] 等温線・等飽和混合比線の背景表示
- [ ] 複数時刻のエマグラム比較表示
- [ ] CCL計算の追加

---

**文書終了**
