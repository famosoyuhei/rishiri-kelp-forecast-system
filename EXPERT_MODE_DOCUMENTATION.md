# 専門家向けモード実装ドキュメント

**実施日**: 2025年12月2日
**バージョン**: v2.4.1
**問題番号**: 問題6

---

## 📋 問題の発見

### 仕様書の記載

`system_specification.md` において、「専門家向けタブ」という用語が複数箇所で使用されていたが、以下の点が不明確でした：

- **どこにあるのか？** - UI上のどこに専門家向け機能があるのか
- **何を表示するのか？** - どのパラメータが専門家向けなのか
- **どう切り替えるのか？** - 一般モードとの切り替え方法は？

### 仕様書での曖昧な記載

**lines 142, 147-149, 188** に以下のような記載:
```markdown
- 風向（利尻島伝統風名表示） ✅ 実装済み（専門家向けタブで16方位併記）
- 鉛直p速度（700hPa） ✅ 実装済み（Pa/s、気温・風速・湿度傾向から推定、専門家向けタブ）
- SSI（ショワルター安定指数） ✅ 実装済み（数値・カテゴリー表示、専門家向けタブ）
- 相当温位（850hPa） ✅ 実装済み（K単位、Bolton公式、専門家向けタブ）
- **表示場所**: 専門家向けタブ「🌪️ 高度気象パラメータ」テーブル
```

**問題点**:
- 「専門家向けタブ」の正確な場所・実装が不明
- UIの切り替え方法が説明されていない
- どのパラメータが専門家向けか一覧化されていない

---

## 🔍 実装の発見（kelp_drying_map.html）

### 1. モード切り替えボタン（lines 1971-1979）

**実装箇所**: 各日の予報タブ内「時間別詳細」セクション

```html
<!-- 一般/専門家向けタブ -->
<div class="view-mode-tabs">
    <button class="view-mode-tab active" onclick="switchViewMode('${tabId}', 'general')">
        🌤️ 一般漁師向け
    </button>
    <button class="view-mode-tab" onclick="switchViewMode('${tabId}', 'expert')">
        🌪️ 気象専門家向け
    </button>
</div>
```

**特徴**:
- ✅ 2つのボタンで切り替え
- ✅ デフォルトは「🌤️ 一般漁師向け」が選択状態
- ✅ 各日のタブごとに独立して切り替え可能

---

### 2. 専門家向け専用パラメータ（lines 2069-2133）

#### 実装されている5つのパラメータ

**HTML実装**:
```html
<!-- 専門家向け項目 -->
<tr class="expert-row">
    <td class="time-cell">☁️ 雲量(%)</td>
    <td class="hour-data">${hourData.cloud_cover !== null ? hourData.cloud_cover : '---'}</td>
    <!-- ... 13時間分の列 -->
</tr>

<tr class="expert-row">
    <td class="time-cell">📐 風向-山頂角差(°)</td>
    <td class="hour-data">${hourData.wind_mountain_angle_diff || '---'}</td>
    <!-- ... -->
</tr>

<tr class="expert-row">
    <td class="time-cell">⬆️ 鉛直p速度 700hPa (Pa/s)</td>
    <td class="hour-data">${hourData.vertical_velocity_700 || '---'}</td>
    <!-- ... -->
</tr>

<tr class="expert-row">
    <td class="time-cell">📊 SSI</td>
    <td class="hour-data">${hourData.ssi || '---'}</td>
    <!-- ... -->
</tr>

<tr class="expert-row">
    <td class="time-cell">🌡️ 相当温位 850hPa (K)</td>
    <td class="hour-data">${hourData.equivalent_potential_temp_850 || '---'}</td>
    <!-- ... -->
</tr>
```

#### パラメータ一覧

| アイコン | パラメータ名 | 説明 | データキー |
|---------|------------|------|-----------|
| ☁️ | 雲量(%) | 全雲量の予報値 | `cloud_cover` |
| 📐 | 風向-山頂角差(°) | 風が向かう方向と山頂方位角の差（山岳効果判定） | `wind_mountain_angle_diff` |
| ⬆️ | 鉛直p速度 700hPa (Pa/s) | 上昇流/下降流の強さ | `vertical_velocity_700` |
| 📊 | SSI | ショワルター安定指数（大気安定度） | `ssi` |
| 🌡️ | 相当温位 850hPa (K) | 潜熱を含む温位 | `equivalent_potential_temp_850` |

---

### 3. CSS実装（lines 310-322）

**デフォルト状態**: 専門家向けパラメータは非表示
```css
.hourly-table .expert-row {
    display: none;  /* 初期状態で非表示 */
}

.hourly-table.show-expert .expert-row {
    display: table-row;  /* 専門家モード時に表示 */
}
```

**動作原理**:
- `.expert-row` クラスの行はデフォルトで `display: none`
- テーブルに `.show-expert` クラスが追加されると `display: table-row`
- CSSのみで表示/非表示を切り替え（JavaScript不要）

---

### 4. JavaScript切り替え関数（lines 2155-2165）

**関数名**: `switchViewMode(tabId, mode)`

**実装**:
```javascript
function switchViewMode(tabId, mode) {
    const tabsContainer = document.querySelector(`#${tabId} .view-mode-tabs`);
    const buttons = tabsContainer.querySelectorAll('.view-mode-tab');
    const table = document.querySelector(`#${tabId} .hourly-table`);

    // ボタンのアクティブ状態を切り替え
    buttons.forEach(btn => {
        btn.classList.remove('active');
    });
    event.target.classList.add('active');

    // テーブルの表示モードを切り替え
    if (mode === 'expert') {
        table.classList.add('show-expert');
    } else {
        table.classList.remove('show-expert');
    }
}
```

**動作フロー**:
1. ユーザーがボタンをクリック
2. 全ボタンから `active` クラスを削除
3. クリックされたボタンに `active` クラスを追加
4. `mode` が `'expert'` なら → テーブルに `.show-expert` クラス追加
5. `mode` が `'general'` なら → テーブルから `.show-expert` クラス削除
6. CSS規則により専門家向けパラメータの表示/非表示が切り替わる

---

## ✅ 仕様書への反映内容

### 修正箇所1: line 142

**変更前**:
```markdown
- 風向（利尻島伝統風名表示） ✅ 実装済み（専門家向けタブで16方位併記）
```

**変更後**:
```markdown
- 風向（利尻島伝統風名表示） ✅ 実装済み（🌪️ 気象専門家向けモードで16方位併記）
```

---

### 修正箇所2: lines 147-149

**変更前**:
```markdown
- 鉛直p速度（700hPa） ✅ 実装済み（Pa/s、気温・風速・湿度傾向から推定、専門家向けタブ）
- SSI（ショワルター安定指数） ✅ 実装済み（数値・カテゴリー表示、専門家向けタブ）
- 相当温位（850hPa） ✅ 実装済み（K単位、Bolton公式、専門家向けタブ）
```

**変更後**:
```markdown
- 鉛直p速度（700hPa） ✅ 実装済み（Pa/s、気温・風速・湿度傾向から推定、🌪️ 気象専門家向けモード）
- SSI（ショワルター安定指数） ✅ 実装済み（数値・カテゴリー表示、🌪️ 気象専門家向けモード）
- 相当温位（850hPa） ✅ 実装済み（K単位、Bolton公式、🌪️ 気象専門家向けモード）
```

---

### 修正箇所3: line 188（大幅拡充）

**変更前**:
```markdown
- **表示場所**: 専門家向けタブ「🌪️ 高度気象パラメータ」テーブル
```

**変更後**:
```markdown
- **表示場所**: 🌪️ 気象専門家向けモード（ボタン切り替え、kelp_drying_map.html lines 1971-2165）
  - **切り替え**: 各日の予報タブ内で「🌤️ 一般漁師向け」⇔「🌪️ 気象専門家向け」ボタンを押下
  - **デフォルト表示**: 一般漁師向けモード（専門家向けパラメータは非表示）
  - **専門家向けモードで表示される追加パラメータ**:
    - ☁️ 雲量(%) - 全雲量の予報値
    - 📐 風向-山頂角差(°) - 風が向かう方向と山頂方位角の差（山岳効果判定）
    - ⬆️ 鉛直p速度 700hPa (Pa/s) - 上昇流/下降流の強さ
    - 📊 SSI（ショワルター安定指数） - 大気安定度指標
    - 🌡️ 相当温位 850hPa (K) - 潜熱を含む温位
```

---

## 🎯 解決された問題

### Before（修正前）

❌ **曖昧な記載**:
- 「専門家向けタブ」がどこにあるのか不明
- 切り替え方法が説明されていない
- 専門家向けパラメータが分散して記載

### After（修正後）

✅ **明確な記載**:
- UI上の正確な位置を明記（kelp_drying_map.html lines 1971-2165）
- 切り替え方法を詳細に説明（ボタンクリック）
- 専門家向けパラメータを一覧化（5つのパラメータ）
- デフォルト動作を明記（一般漁師向けモード）
- 実装の仕組みを文書化（CSS + JavaScript）

---

## 📊 ユーザー体験フロー

### 一般漁師の場合

1. ページを開く → **デフォルト**: 🌤️ 一般漁師向けモード
2. 表示されるパラメータ:
   - 気温、湿度、風向、風速、日射量
   - 基本的な気象情報のみ
3. シンプルで分かりやすい表示

### 気象専門家の場合

1. ページを開く → デフォルトは一般漁師向け
2. **🌪️ 気象専門家向け** ボタンをクリック
3. 追加で表示される専門パラメータ:
   - ☁️ 雲量(%)
   - 📐 風向-山頂角差(°)
   - ⬆️ 鉛直p速度 700hPa
   - 📊 SSI（安定指数）
   - 🌡️ 相当温位 850hPa
4. より詳細な大気状態を分析可能

---

## 📁 更新されたファイル

### 新規作成
- ✅ `EXPERT_MODE_DOCUMENTATION.md` - この実装ドキュメント

### 更新済み
- ✅ `system_specification.md` (lines 142, 147-149, 188-196)
  - 「専門家向けタブ」→「🌪️ 気象専門家向けモード」に統一
  - UI位置・切り替え方法・パラメータ一覧を追加
  - 実装ファイル・行番号を明記

---

## 🌟 改善点

### ドキュメント品質

✅ **具体性**: 曖昧な「タブ」から明確な「モード切り替えボタン」へ
✅ **トレーサビリティ**: 実装ファイル・行番号を明記
✅ **完全性**: UI、CSS、JavaScript、パラメータすべてを文書化
✅ **ユーザー視点**: 切り替え方法を明確に説明

### 保守性

✅ **一覧化**: 専門家向けパラメータを1箇所にまとめて記載
✅ **一貫性**: 全箇所で同じ用語「🌪️ 気象専門家向けモード」を使用
✅ **検証可能性**: 実装コードとの対応が明確

---

## 🎯 問題6「専門家向けタブの特定」- 完全解決

### 解決項目

✅ **実装の発見**: kelp_drying_map.html内の専門家モード機能を特定
✅ **UI位置の明記**: lines 1971-2165に実装されていることを文書化
✅ **切り替え方法の説明**: ボタンクリックでモード切り替えと明記
✅ **パラメータ一覧化**: 5つの専門家向けパラメータをリスト化
✅ **仕様書更新**: 全3箇所で曖昧な記載を詳細な説明に置換

---

**実装完了日**: 2025年12月2日
**バージョン**: v2.4.1
**状態**: ✅ 完全解決・文書化完了
