# 相当温位保存による気象補正の実装案

## 概要

風上地点のエマグラムから風下地点の気温・湿度を物理的に補正する機能。
相当温位（θₑ）の保存則を利用し、地形による昇降を考慮した高精度補正。

## 物理的原理

### 1. 相当温位の定義

```
θₑ = θ × exp(Lq / CpT)

where:
- θ: 温位
- L: 蒸発潜熱（2.5×10⁶ J/kg）
- q: 混合比
- Cp: 定圧比熱（1005 J/kg/K）
- T: 温度（K）
```

### 2. 保存則

**湿潤断熱過程（凝結を含む）でも相当温位は保存される**

```
風上の空気塊 → 上昇（凝結） → 山頂 → 下降（蒸発） → 風下
    θₑ₁                                              θₑ₂

θₑ₁ = θₑ₂  （保存！）
```

### 3. 利尻島での適用

```
沓形（風上・西側）
  ↓
  ↓ θₑ保存
  ↓ 利尻山越え（標高1721m）
  ↓ 下降流500m
  ↓
鴛泊（風下・東側）
  - 気温: +3~5°C上昇（フェーン効果）
  - 露点温度: -3~-6°C低下（乾燥）
  - 相対湿度: -15~-25%低下
  → 昆布乾燥に有利！
```

## 実装方法

### オプション1: `/api/emagram`に補正機能を追加（推奨）

```python
@app.route('/api/emagram')
def get_emagram_data():
    """
    エマグラムデータ取得 + 相当温位補正（オプション）

    Parameters:
        lat: 緯度
        lon: 経度
        time: 予報時刻オフセット
        apply_theta_e_correction: 補正を適用（true/false、デフォルトfalse）
        wind_direction: 風向（度）※補正時必須
        terrain_descent: 地形下降高度（m、デフォルト500）
        rh_reduction: 相対湿度低下（0-1、デフォルト0.15）

    Returns:
        通常のエマグラムデータ + correction_applied, corrected_values
    """
    pass
```

**利点:**
- 既存エンドポイントの拡張で実装が簡単
- パラメータで補正ON/OFFを切り替え可能
- 後方互換性を保持

### オプション2: 新しいエンドポイント `/api/emagram_corrected`

```python
@app.route('/api/emagram_corrected')
def get_corrected_emagram():
    """
    相当温位補正を適用したエマグラムデータ

    Parameters:
        lat: 風下地点の緯度
        lon: 風下地点の経度
        wind_direction: 現在の風向（度）
        time: 予報時刻オフセット

    Returns:
        original: APIからの生データ
        corrected: 補正後のデータ
        windward_location: 使用した風上地点
        correction_params: 補正パラメータ
    """
    pass
```

**利点:**
- 既存APIに影響なし
- 補正専用の詳細情報を返せる
- 風上地点の自動選定が可能

## 風上地点の自動選定ロジック

### 1. 風向から風上地点を決定

```python
def select_windward_spot(target_lat, target_lon, wind_direction, spots_df):
    """
    風向に基づいて風上地点を選定

    Args:
        target_lat, target_lon: 補正対象地点
        wind_direction: 風向（度、北を0度）
        spots_df: 干場データベース

    Returns:
        最適な風上地点の情報
    """
    # 風向の逆方向（風上方向）を計算
    windward_direction = (wind_direction + 180) % 360

    # 利尻山（45.18°N, 141.24°E）からの方位角を計算
    rishiri_peak = (45.18, 141.24)

    for _, spot in spots_df.iterrows():
        # 対象地点から見た各干場の方位角
        bearing = calculate_bearing(target_lat, target_lon, spot['lat'], spot['lon'])

        # 風上方向との角度差
        angle_diff = abs(windward_direction - bearing)
        if angle_diff > 180:
            angle_diff = 360 - angle_diff

        # 距離
        distance = haversine(target_lat, target_lon, spot['lat'], spot['lon'])

    # 風上方向で最も近い地点を選択
    # 角度差30度以内、距離5-15km
    candidates = filter(lambda s: angle_diff < 30 and 5 < distance < 15)

    return best_candidate
```

### 2. 地形下降高度の自動計算

```python
def estimate_terrain_descent(windward_spot, leeward_spot, wind_direction):
    """
    利尻山の標高と風向から下降高度を推定

    Args:
        windward_spot: 風上地点
        leeward_spot: 風下地点
        wind_direction: 風向

    Returns:
        推定下降高度（m）
    """
    rishiri_peak_elevation = 1721  # m

    # 風上・風下の標高差
    elevation_diff = windward_spot['elevation'] - leeward_spot['elevation']

    # 利尻山を越える場合の追加下降
    if crosses_rishiri_mountain(windward_spot, leeward_spot, wind_direction):
        # 山頂までの上昇を考慮
        max_ascent = rishiri_peak_elevation - windward_spot['elevation']
        descent = max_ascent + elevation_diff
    else:
        # 山を迂回する場合は標高差のみ
        descent = elevation_diff

    return max(0, descent)  # 負の値は0に
```

## 実装の優先度

### Phase 1: 検証と調整（現在）✓完了

- [x] `theta_e_correction.py`で原理検証
- [x] 沓形→鴛泊での補正値確認（+2.9°C、-3~-6°C露点低下）
- [x] 物理的妥当性の確認

### Phase 2: APIエンドポイント実装

- [ ] `/api/emagram`に`apply_theta_e_correction`パラメータ追加
- [ ] 風向情報の取得（既存の`/api/forecast`から）
- [ ] 風上地点の自動選定ロジック
- [ ] 地形下降高度の自動計算

### Phase 3: UIへの統合

- [ ] エマグラムUIに「補正表示」チェックボックス追加
- [ ] 補正前/後の比較表示
- [ ] 風向と風上地点の表示
- [ ] 補正パラメータの表示

### Phase 4: 検証と改善

- [ ] 実測データとの比較検証
- [ ] 複数の風向パターンでの検証
- [ ] 補正パラメータの最適化

## 期待される効果

### 1. 昆布乾燥予報の精度向上

```
従来（APIデータのみ）:
  - 地形効果を考慮できない
  - 風下での乾燥効果を過小評価

補正後（θₑ補正適用）:
  - フェーン効果による気温上昇: +3°C
  - 相対湿度低下: -20%
  - → より正確な乾燥可否判定
```

### 2. 風向による干場選定の最適化

```
西風時:
  - 風上（沓形）: 湿潤、乾燥不利
  - 風下（鴛泊）: 乾燥、乾燥有利 ← 補正で定量化

東風時:
  - 逆転
```

### 3. 気象学的に正しい予報

- 経験的補正ではなく、熱力学第一法則に基づく
- 相当温位保存は厳密に成立
- 説明可能なAI（XAI）の観点でも優れている

## 技術的課題と対策

### 課題1: 風向情報の取得

**解決策:**
- 既存の`/api/forecast`から地上風向を取得
- アメダス実測風向データがあればさらに精度向上

### 課題2: 複雑な地形での適用

**解決策:**
- 利尻山の標高と位置を考慮した簡易モデル
- 初期は「山を越える/越えない」の二値判定
- 将来的にはDEMデータで精密化

### 課題3: 計算コスト

**解決策:**
- θₑ計算は軽量（数値計算のみ）
- キャッシュ機能で同じ風向・時刻は再利用
- 必要時のみ適用（パラメータで制御）

## まとめ

**相当温位補正は実装可能で、非常に有効です！**

✓ 物理的に正しい
✓ 計算コスト低い
✓ 既存システムへの統合が容易
✓ 昆布乾燥予報の精度が大幅向上

**次のステップ:**
1. `/api/emagram`にオプションパラメータを追加
2. 風向情報の取得ロジック実装
3. UIに補正表示機能を追加
