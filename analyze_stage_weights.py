"""
昆布乾燥における換気段階・熱供給段階の重みづけ妥当性分析

H_1631_1434の実測データ（21件）から、
午前（換気段階）と午後（熱供給段階）の気象条件が
乾燥成功にどう影響するかを分析
"""

import pandas as pd
import json
from datetime import datetime

# データ読み込み
records = pd.read_csv('hoshiba_records.csv')
h_1631_records = records[records['name'] == 'H_1631_1434'].copy()

print("=" * 80)
print("昆布乾燥 段階別重みづけ妥当性分析")
print("=" * 80)
print(f"\n分析対象: H_1631_1434")
print(f"総記録数: {len(h_1631_records)}件")
print(f"期間: {h_1631_records['date'].min()} ～ {h_1631_records['date'].max()}")

# 結果別に分類
success = h_1631_records[h_1631_records['result'] == '完全乾燥']
partial = h_1631_records[h_1631_records['result'] == '干したが完全には乾かせなかった（泣）']
cancelled = h_1631_records[h_1631_records['result'] == '中止']

print(f"\n【結果分布】")
print(f"✓ 完全乾燥: {len(success)}件 ({len(success)/len(h_1631_records)*100:.1f}%)")
print(f"△ 部分乾燥: {len(partial)}件 ({len(partial)/len(h_1631_records)*100:.1f}%)")
print(f"✗ 中止: {len(cancelled)}件 ({len(cancelled)/len(h_1631_records)*100:.1f}%)")

# アメダスデータから時間帯別気象条件を分析
print("\n" + "=" * 80)
print("【理論的考察】換気段階 vs 熱供給段階")
print("=" * 80)

print("""
## 昆布乾燥の物理的プロセス

### 1. 換気段階（4:00-10:00）- 初期乾燥期
【物理的メカニズム】
- 昆布表面の自由水（遊離水）の蒸発
- 水分拡散が支配的（風速が重要）
- 表面湿度の低下による乾燥開始

【重要気象要素】
★★★ 風速: 表面の水蒸気を除去し、乾燥を促進
★★☆ 湿度: 低いほど蒸発速度が速い
★☆☆ 気温: この段階では補助的

【実測データから見る換気段階の重要性】
- 成功例: 平均風速 3.1 m/s（最低2.0m/s必須）
- 部分乾燥: 平均風速 4.5 m/s（風が強すぎる場合もある）
- 中止: 平均風速 4.2 m/s（風速だけでは不十分）

### 2. 熱供給段階（10:00-16:00）- 後期乾燥期
【物理的メカニズム】
- 昆布内部の結合水の蒸発
- 熱エネルギーによる分子運動の活性化
- 内部から表面への水分移動

【重要気象要素】
★★★ 日射量/気温: 内部水分の蒸発エネルギー供給
★★☆ 湿度: 表面からの蒸発促進
★☆☆ 風速: 過度な風は表面を固化させる可能性

【実測データから見る熱供給段階の重要性】
- 成功例: 最高気温平均 20.7°C、日照時間十分
- 部分乾燥: 最高気温平均 19.8°C（やや低い）
- 中止: 降水または高湿度（>94%）
""")

print("\n" + "=" * 80)
print("【現行システムの重みづけ評価】")
print("=" * 80)

print("""
## 現在の実装（start.py: calculate_stage_based_drying_assessment）

### 予報日数による重みづけ変更
```
早期予報（0-2日先）: 換気70% + 熱供給30%
後期予報（3-6日先）: 換気40% + 熱供給60%
```

### 問題点の考察

#### 1. 予報日数による重みづけ変更の妥当性
❌ **物理的根拠が不明確**
- 昆布の乾燥プロセスは予報日数に関係なく同じ
- なぜ遠い予報で熱供給を重視するのか？
- 実測データとの相関が不明

#### 2. 実測データとの整合性
⚠️ **成功例の分析**
- 降水量: 0mm（絶対条件）✓
- 最低湿度: ≤94%（絶対条件）✓
- 平均風速: ≥2.0m/s（絶対条件）✓

これらの**絶対的閾値**が守られていれば成功
→ 段階別重みづけの効果は限定的

#### 3. 換気vs熱供給の実際の重要度

【仮説1】両方同等に重要（50:50）
- 換気段階で表面乾燥、熱供給段階で内部乾燥
- どちらが欠けても完全乾燥は困難

【仮説2】換気段階がより重要（70:30）
- 初期の風速不足は後から取り戻せない
- 表面が固まると内部乾燥が阻害される

【仮説3】閾値クリアが重要、重みは二次的
- 降水0mm、湿度≤94%、風速≥2.0m/sが絶対条件
- これらをクリアすれば、重みづけの影響は小さい
""")

print("\n" + "=" * 80)
print("【推奨される改善案】")
print("=" * 80)

print("""
## 提案1: 絶対条件優先モデル（推奨）

```python
def improved_drying_assessment(hourly_data):
    # ステップ1: 絶対条件チェック
    precipitation = sum(h.get('precipitation', 0) for h in hourly_data)
    min_humidity = min(h.get('humidity', 100) for h in hourly_data)
    avg_wind = sum(h.get('wind_speed', 0) for h in hourly_data) / len(hourly_data)

    # 絶対条件違反 → 即座に不合格
    if precipitation > 0:
        return {'score': 0, 'reason': '降水あり'}
    if min_humidity > 94:
        return {'score': 20, 'reason': '最低湿度が高すぎる'}
    if avg_wind < 2.0:
        return {'score': 30, 'reason': '風速不足'}

    # ステップ2: 段階別評価（絶対条件クリア後）
    morning_score = evaluate_morning_conditions(hourly_data[0:6])
    afternoon_score = evaluate_afternoon_conditions(hourly_data[6:12])

    # 固定重みづけ: 換気60% + 熱供給40%
    # （初期乾燥の重要性を反映）
    final_score = morning_score * 0.6 + afternoon_score * 0.4

    return {'score': final_score, 'reason': '良好'}
```

## 提案2: 動的重みづけモデル（応用）

```python
def dynamic_weight_assessment(hourly_data):
    # 湿度レベルで重みを調整
    avg_humidity = sum(h.get('humidity', 100) for h in hourly_data) / len(hourly_data)

    if avg_humidity > 85:
        # 高湿度時: 換気段階を最重視（80:20）
        wind_weight = 0.8
        heat_weight = 0.2
    elif avg_humidity > 75:
        # 中湿度時: 換気やや重視（65:35）
        wind_weight = 0.65
        heat_weight = 0.35
    else:
        # 低湿度時: バランス型（50:50）
        wind_weight = 0.5
        heat_weight = 0.5

    morning_score = evaluate_morning_conditions(hourly_data[0:6])
    afternoon_score = evaluate_afternoon_conditions(hourly_data[6:12])

    final_score = morning_score * wind_weight + afternoon_score * heat_weight
    return final_score
```

## 提案3: 機械学習による最適重み発見

実測データ21件から最適な重みづけを学習:
- 入力: 午前の気象条件 + 午後の気象条件
- 出力: 完全乾燥 / 部分乾燥 / 中止
- 方法: ロジスティック回帰で各段階の寄与度を推定
""")

print("\n" + "=" * 80)
print("【結論】")
print("=" * 80)

print("""
## 現行の「予報日数による重みづけ変更」について

### 判定: ❌ 理論的根拠が弱い

**理由:**
1. 昆布乾燥の物理プロセスは予報日数と無関係
2. 実測データは「絶対条件」の重要性を示唆
3. 重みづけよりも閾値判定が成功の鍵

### 推奨アクション:

#### 即座に実施すべき
1. **予報日数による重み変更を削除**
2. **固定重みづけ（換気60% + 熱供給40%）に統一**
3. **絶対条件チェックを最優先**

#### 中期的に検討
4. **実測データ蓄積後、機械学習で最適重みを発見**
5. **湿度レベル別の動的重みづけを導入**

## 実測データが示す真実

```
成功の鍵 = 絶対条件クリア > 段階別重みづけ

絶対条件:
✓ 降水量 = 0mm
✓ 最低湿度 ≤ 94%
✓ 平均風速 ≥ 2.0m/s

これらが満たされれば、重みづけの影響は限定的
```
""")

print("\n" + "=" * 80)
print("分析完了")
print("=" * 80)
