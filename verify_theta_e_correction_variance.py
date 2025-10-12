#!/usr/bin/env python3
"""
相当温位補正後の地点間偏差を検証

仮説:
1. 地上付近: θₑ補正により地形性の偏差が再現される
2. 上層: θₑは保存されるので、偏差は変わらない（API問題は残る）
"""
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib import rcParams
import json

rcParams['font.sans-serif'] = ['DejaVu Sans']

# 前回の解析結果を読み込み
def load_previous_analysis():
    """前回の全干場エマグラム解析結果を読み込み"""
    # 簡易版: 前回の統計値を使用
    stats = {
        'pressure': [1000, 975, 950, 925, 900, 850, 800, 700, 600, 500, 400, 300, 250, 200],
        'api_temp_std': [0.076, 0.069, 0.069, 0.050, 0.049, 0.109, 0.268, 0.109, 0.192, 0.410, 0.349, 0.192, 0.000, 0.162],
        'api_temp_range': [0.20, 0.20, 0.20, 0.10, 0.10, 0.30, 0.90, 0.30, 0.60, 1.10, 0.90, 0.50, 0.00, 0.50]
    }
    return pd.DataFrame(stats)

def simulate_theta_e_correction_effect():
    """相当温位補正が地点間偏差に与える影響をシミュレート"""

    print("=" * 80)
    print("相当温位補正後の地点間偏差シミュレーション")
    print("=" * 80)
    print()

    # 前回の解析結果
    stats_df = load_previous_analysis()

    # 利尻島の地形的多様性を考慮した「期待される偏差」
    # 各地点の特性を定義
    spot_characteristics = [
        # (標高m, 地形タイプ, 風上/風下係数)
        (20, 'coast', 1.0),      # 鴛泊（海岸・港）
        (10, 'coast', 1.0),      # 沓形（海岸平地）
        (150, 'forest', 0.7),    # 仙法志（高台・森林）
        (50, 'coast', 1.0),      # 北部海岸
        (100, 'forest', 0.8),    # 山麓森林
        (30, 'coast', 1.0),      # 南部海岸
        (200, 'mountain', 0.5),  # 山岳地帯
        (80, 'mixed', 0.9),      # 混合地域
    ]

    # 西風（270度）を仮定
    wind_direction = 270  # degrees

    # 各地点での相当温位補正効果をシミュレート
    results = []

    print("シミュレーション条件:")
    print("  - 風向: 西風（270度）")
    print("  - 地点数: 8地点（代表的な地形タイプ）")
    print("  - 補正方法: θₑ保存 + 地形下降\n")

    for i, (elev, terrain, windward_factor) in enumerate(spot_characteristics):
        spot_name = f"Spot_{i+1}_{terrain}"

        # 標高による気温逓減（0.6°C/100m）
        temp_correction_elevation = -elev * 0.006  # °C

        # 風上/風下効果（フェーン）
        # windward_factor: 1.0=完全風上（補正なし）, 0.5=完全風下（最大補正）
        foehn_effect = (1.0 - windward_factor) * 5.0  # °C（最大+5°C）

        # 地形タイプによる湿度効果
        terrain_humidity_effects = {
            'coast': -0.5,      # 海岸は相対的に湿潤→露点高い
            'forest': +1.0,     # 森林は蒸散→露点やや高い
            'mountain': -2.0,   # 山岳は乾燥→露点低い
            'mixed': 0.0
        }
        dewpoint_correction = terrain_humidity_effects.get(terrain, 0.0)

        # 相当温位補正による総合効果（地上）
        total_temp_correction = temp_correction_elevation + foehn_effect
        total_dewpoint_correction = dewpoint_correction + (foehn_effect * -0.5)  # フェーンで乾燥

        results.append({
            'spot': spot_name,
            'elevation': elev,
            'terrain': terrain,
            'windward_factor': windward_factor,
            'temp_correction': total_temp_correction,
            'dewpoint_correction': total_dewpoint_correction
        })

    results_df = pd.DataFrame(results)

    print("=" * 80)
    print("各地点の補正値")
    print("=" * 80)
    print(f"\n{'地点':20} {'標高':>6} {'地形':>10} {'気温補正':>10} {'露点補正':>10}")
    print("-" * 80)

    for _, row in results_df.iterrows():
        print(f"{row['spot']:20} {row['elevation']:>6.0f} {row['terrain']:>10} "
              f"{row['temp_correction']:>+10.2f} {row['dewpoint_correction']:>+10.2f}")

    # 補正後の偏差を計算
    temp_std_corrected = results_df['temp_correction'].std()
    temp_range_corrected = results_df['temp_correction'].max() - results_df['temp_correction'].min()

    print("\n" + "=" * 80)
    print("地上付近（1000hPa）の偏差比較")
    print("=" * 80)
    print()

    api_std = stats_df.loc[stats_df['pressure'] == 1000, 'api_temp_std'].values[0]
    api_range = stats_df.loc[stats_df['pressure'] == 1000, 'api_temp_range'].values[0]

    expected_std_min = 0.5    # 期待される最小標準偏差（°C）
    expected_std_max = 1.5    # 期待される最大標準偏差（°C）
    expected_range_min = 1.0  # 期待される最小範囲（°C）
    expected_range_max = 3.0  # 期待される最大範囲（°C）

    print(f"API生データ:")
    print(f"  標準偏差: {api_std:.3f}°C")
    print(f"  範囲: {api_range:.2f}°C")
    print()

    print(f"θₑ補正後（シミュレーション）:")
    print(f"  標準偏差: {temp_std_corrected:.3f}°C")
    print(f"  範囲: {temp_range_corrected:.2f}°C")
    print()

    print(f"期待値（気象学的）:")
    print(f"  標準偏差: {expected_std_min:.1f}-{expected_std_max:.1f}°C")
    print(f"  範囲: {expected_range_min:.1f}-{expected_range_max:.1f}°C")
    print()

    # 判定
    if expected_std_min <= temp_std_corrected <= expected_std_max:
        print("✓ 地上付近の偏差: 補正後は気象学的に妥当な範囲")
        ground_ok = True
    else:
        print("△ 地上付近の偏差: 補正後も期待値と乖離")
        ground_ok = False

    # 上層の問題
    print("\n" + "=" * 80)
    print("上層（500hPa）の偏差問題")
    print("=" * 80)
    print()

    api_std_500 = stats_df.loc[stats_df['pressure'] == 500, 'api_temp_std'].values[0]
    api_range_500 = stats_df.loc[stats_df['pressure'] == 500, 'api_temp_range'].values[0]

    print(f"API生データ（500hPa）:")
    print(f"  標準偏差: {api_std_500:.3f}°C")
    print(f"  範囲: {api_range_500:.2f}°C")
    print()

    print(f"気象学的期待値（15km四方）:")
    print(f"  標準偏差: <0.1°C")
    print(f"  範囲: <0.2°C")
    print()

    print("問題の性質:")
    print("  - θₑ補正は「地形による昇降」を補正")
    print("  - 上層の偏差は「APIの格子補間誤差」")
    print("  - θₑ補正では解決できない")
    print()

    # 上層の解決策
    print("=" * 80)
    print("上層偏差の解決策")
    print("=" * 80)
    print()

    solutions = [
        {
            'name': '解決策1: 平滑化フィルタ',
            'method': '上層（≥700hPa）は全地点で平均値を使用',
            'pros': '実装が簡単、計算コスト低い',
            'cons': '実際の気象場の変動も除去してしまう',
            'recommended': True
        },
        {
            'name': '解決策2: 参照地点の固定',
            'method': '代表地点（鴛泊）のデータを全地点で共用',
            'pros': '一貫性が保たれる',
            'cons': '実際の気象変動を無視',
            'recommended': True
        },
        {
            'name': '解決策3: 時空間補間の改善',
            'method': '複数時刻・周辺格子点からスムーズに補間',
            'pros': '物理的に最も正しい',
            'cons': '実装が複雑、計算コスト高い',
            'recommended': False
        },
        {
            'name': '解決策4: 高解像度モデルへの切替',
            'method': 'Open-Meteo以外の高解像度API使用',
            'pros': '根本的解決',
            'cons': 'API制限・コスト、利用可能性不明',
            'recommended': False
        }
    ]

    for i, sol in enumerate(solutions, 1):
        print(f"{i}. {sol['name']}")
        print(f"   方法: {sol['method']}")
        print(f"   利点: {sol['pros']}")
        print(f"   欠点: {sol['cons']}")
        print(f"   推奨: {'✓ Yes' if sol['recommended'] else '△ No'}")
        print()

    # 推奨実装
    print("=" * 80)
    print("推奨実装: ハイブリッドアプローチ")
    print("=" * 80)
    print()

    print("下層（1000-850hPa）:")
    print("  ✓ θₑ補正を適用")
    print("  ✓ 地形による昇降・フェーン効果を考慮")
    print("  → 地点間の物理的な差を再現")
    print()

    print("中層（800-600hPa）:")
    print("  ✓ θₑ補正を適用（弱めに）")
    print("  ✓ 地形影響を減衰（重み係数0.5程度）")
    print("  → 過度な補正を抑制")
    print()

    print("上層（500hPa以上）:")
    print("  ✓ 全地点で参照地点（鴛泊）の値を使用")
    print("  ✓ または5地点移動平均で平滑化")
    print("  → APIの補間誤差を除去")
    print()

    # 可視化
    fig, axes = plt.subplots(1, 2, figsize=(14, 8))

    # 左: 気圧面ごとの偏差（API vs 補正後）
    ax1 = axes[0]

    # API偏差（実データ）
    pressures = stats_df['pressure'].values
    api_stds = stats_df['api_temp_std'].values

    # 補正後偏差（シミュレーション）
    # 下層は補正で増加、上層は平滑化で減少
    corrected_stds = []
    for p, std in zip(pressures, api_stds):
        if p >= 850:  # 下層
            # 補正により偏差増加
            corrected_std = temp_std_corrected  # シミュレーション値
        elif p >= 600:  # 中層
            # 補正効果が弱まる
            corrected_std = temp_std_corrected * 0.3
        else:  # 上層
            # 平滑化により減少
            corrected_std = 0.05  # ほぼ一様
        corrected_stds.append(corrected_std)

    ax1.plot(api_stds, pressures, 'o-', color='#dc3545',
            linewidth=2, markersize=6, label='API (before)')
    ax1.plot(corrected_stds, pressures, 's-', color='#10b981',
            linewidth=2, markersize=6, label='After theta_e correction')
    ax1.axvline(0.5, color='orange', linestyle='--', alpha=0.5,
               label='Expected range (0.5-1.5C)')
    ax1.axvline(1.5, color='orange', linestyle='--', alpha=0.5)
    ax1.axhline(850, color='gray', linestyle=':', alpha=0.5)
    ax1.axhline(600, color='gray', linestyle=':', alpha=0.5)

    ax1.set_xlabel('Temperature Std Dev (C)', fontsize=12, weight='bold')
    ax1.set_ylabel('Pressure (hPa)', fontsize=12, weight='bold')
    ax1.set_title('Spatial Variance: API vs Corrected', fontsize=13, weight='bold')
    ax1.invert_yaxis()
    ax1.grid(True, alpha=0.3)
    ax1.legend()
    ax1.set_xlim(0, 0.5)

    # 右: 各地点の補正量
    ax2 = axes[1]

    spot_names = results_df['spot'].str.replace('Spot_', 'S').str.replace('_', '\n')
    temp_corrections = results_df['temp_correction']

    colors = ['#3b82f6' if w > 0.7 else '#dc3545'
             for w in results_df['windward_factor']]

    bars = ax2.bar(range(len(spot_names)), temp_corrections, color=colors)
    ax2.axhline(0, color='black', linestyle='-', linewidth=0.5)
    ax2.set_xlabel('Spot (terrain type)', fontsize=12, weight='bold')
    ax2.set_ylabel('Temperature Correction (C)', fontsize=12, weight='bold')
    ax2.set_title('Theta_e Correction by Spot\n(Blue=Windward, Red=Leeward)',
                 fontsize=13, weight='bold')
    ax2.set_xticks(range(len(spot_names)))
    ax2.set_xticklabels(spot_names, fontsize=8)
    ax2.grid(True, alpha=0.3, axis='y')

    plt.tight_layout()

    output_file = 'theta_e_correction_variance_analysis.png'
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    print(f"✓ グラフを保存: {output_file}\n")

    # 結果をまとめ
    summary = {
        'ground_level': {
            'api_std': float(api_std),
            'corrected_std': float(temp_std_corrected),
            'expected_range': [expected_std_min, expected_std_max],
            'physically_reasonable': ground_ok
        },
        'upper_level': {
            'api_std_500hpa': float(api_std_500),
            'expected_std': 0.1,
            'problem': 'API grid interpolation error',
            'solution': 'Use reference point or spatial smoothing'
        },
        'recommended_approach': {
            'lower_atmosphere': 'Apply theta_e correction',
            'middle_atmosphere': 'Apply weak theta_e correction (weight=0.5)',
            'upper_atmosphere': 'Use reference point or smoothing'
        }
    }

    with open('theta_e_correction_variance_summary.json', 'w', encoding='utf-8') as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    print("✓ 結果を保存: theta_e_correction_variance_summary.json\n")

    return summary

if __name__ == '__main__':
    simulate_theta_e_correction_effect()
