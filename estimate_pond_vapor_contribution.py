#!/usr/bin/env python3
"""
姫沼・オタドマリ沼からの水蒸気供給量の推定

気象学的影響範囲と、相当温位補正への影響を評価
"""
import numpy as np
import matplotlib.pyplot as plt
from matplotlib import rcParams

rcParams['font.sans-serif'] = ['DejaVu Sans']

def estimate_evaporation_rate(water_temp, air_temp, wind_speed, rh):
    """
    ダルトンの式による蒸発量推定（簡易版）

    E = (es - ea) × u × k

    Args:
        water_temp: 水温（℃）
        air_temp: 気温（℃）
        wind_speed: 風速（m/s）
        rh: 相対湿度（0-1）

    Returns:
        蒸発量（mm/day）
    """
    # Magnus式で飽和水蒸気圧
    def es(T):
        return 6.112 * np.exp(17.67 * T / (T + 243.5))

    es_water = es(water_temp)  # 水面の飽和水蒸気圧
    es_air = es(air_temp)      # 大気の飽和水蒸気圧
    ea = rh * es_air           # 実際の水蒸気圧

    # ダルトンの式（簡易版）
    # k: 経験的係数（0.13程度）
    k = 0.13
    E = k * (es_water - ea) * wind_speed  # mm/day

    return max(0, E)

def estimate_vapor_contribution():
    """姫沼・オタドマリ沼からの水蒸気供給量を推定"""

    print("=" * 80)
    print("姫沼・オタドマリ沼からの水蒸気供給量推定")
    print("=" * 80)
    print()

    # 沼の諸元
    ponds = {
        '姫沼': {
            'area_km2': 0.05,
            'area_m2': 50000,
            'lat': 45.195,
            'lon': 141.185,
            'elevation': 130,
            'depth': 2.0  # 推定平均水深（m）
        },
        'オタドマリ沼': {
            'area_km2': 0.25,
            'area_m2': 250000,
            'lat': 45.172,
            'lon': 141.138,
            'elevation': 20,
            'depth': 1.5  # 推定平均水深（m）
        }
    }

    # 気象条件（夏季・昆布乾燥時期の典型値）
    conditions = {
        'summer_calm': {
            'name': '夏季・穏やか',
            'water_temp': 18.0,  # 水温（℃）
            'air_temp': 15.0,    # 気温（℃）
            'wind_speed': 2.0,   # 風速（m/s）
            'rh': 0.75           # 相対湿度
        },
        'summer_windy': {
            'name': '夏季・強風',
            'water_temp': 18.0,
            'air_temp': 15.0,
            'wind_speed': 8.0,   # 強風時
            'rh': 0.70
        },
        'summer_dry': {
            'name': '夏季・乾燥',
            'water_temp': 20.0,
            'air_temp': 18.0,
            'wind_speed': 4.0,
            'rh': 0.60           # 乾燥時
        }
    }

    results = {}

    for cond_name, cond in conditions.items():
        print(f"\n{'='*60}")
        print(f"条件: {cond['name']}")
        print(f"{'='*60}")
        print(f"  水温: {cond['water_temp']}°C")
        print(f"  気温: {cond['air_temp']}°C")
        print(f"  風速: {cond['wind_speed']} m/s")
        print(f"  相対湿度: {cond['rh']*100:.0f}%")
        print()

        cond_results = {}

        for pond_name, pond in ponds.items():
            # 蒸発量計算（mm/day）
            evap_rate = estimate_evaporation_rate(
                cond['water_temp'],
                cond['air_temp'],
                cond['wind_speed'],
                cond['rh']
            )

            # 総蒸発量（m³/day）
            total_evap_m3_day = evap_rate * pond['area_m2'] / 1000

            # 質量（kg/day、水の密度1000 kg/m³）
            mass_kg_day = total_evap_m3_day * 1000

            # 時間あたり（kg/h）
            mass_kg_hour = mass_kg_day / 24

            # 混合比への寄与を推定
            # 境界層の体積を仮定（沼の上空500m×水平5km範囲）
            boundary_layer_height = 500  # m
            horizontal_scale = 5000      # m（影響範囲の半径）
            volume = np.pi * (horizontal_scale ** 2) * boundary_layer_height  # m³

            # 空気の密度（kg/m³、15℃で約1.225）
            air_density = 1.225
            air_mass = volume * air_density  # kg

            # 混合比増加（kg/kg）
            # 1時間で境界層が完全に入れ替わると仮定
            mixing_ratio_increase = mass_kg_hour / air_mass

            # 露点温度上昇の推定（簡易）
            # Δq ≈ 0.622 × Δe / P
            # Δe ≈ (∂e/∂T) × ΔT ≈ 1 hPa/K （15℃付近）
            # ΔTd ≈ Δq × P / (0.622 × 1 hPa/K)
            P = 1000  # hPa（地上気圧）
            dewpoint_increase = mixing_ratio_increase * P / (0.622 * 1.0)  # K

            cond_results[pond_name] = {
                'evap_rate': evap_rate,
                'total_evap_m3_day': total_evap_m3_day,
                'mass_kg_day': mass_kg_day,
                'mass_kg_hour': mass_kg_hour,
                'mixing_ratio_increase': mixing_ratio_increase,
                'dewpoint_increase': dewpoint_increase
            }

            print(f"【{pond_name}】")
            print(f"  面積: {pond['area_km2']} km² ({pond['area_m2']:,} m²)")
            print(f"  蒸発速度: {evap_rate:.2f} mm/day")
            print(f"  総蒸発量: {total_evap_m3_day:.1f} m³/day ({mass_kg_day:.0f} kg/day)")
            print(f"  時間あたり: {mass_kg_hour:.1f} kg/h")
            print(f"  混合比増加: {mixing_ratio_increase*1e6:.2f} ppm (= {mixing_ratio_increase:.2e} kg/kg)")
            print(f"  推定露点温度上昇: {dewpoint_increase:.3f}°C")
            print()

        results[cond_name] = cond_results

    # 総合評価
    print("\n" + "=" * 80)
    print("総合評価")
    print("=" * 80)
    print()

    # 最大ケース（強風時）のオタドマリ沼
    max_case = results['summer_windy']['オタドマリ沼']
    dewpoint_increase_max = max_case['dewpoint_increase']

    print(f"最大影響（強風時のオタドマリ沼）:")
    print(f"  露点温度上昇: {dewpoint_increase_max:.3f}°C")
    print()

    # 相当温位補正との比較
    theta_e_correction_magnitude = 3.0  # °C（先の解析結果）

    ratio = dewpoint_increase_max / theta_e_correction_magnitude * 100

    print(f"相当温位補正（フェーン効果）との比較:")
    print(f"  θₑ補正による露点温度変化: 約{theta_e_correction_magnitude}°C")
    print(f"  沼からの寄与: {dewpoint_increase_max:.3f}°C")
    print(f"  比率: {ratio:.2f}%")
    print()

    if dewpoint_increase_max < 0.1:
        print("✓ 結論: 沼からの水蒸気供給は無視できる（<0.1°C）")
        print("  相当温位補正の精度に影響しない")
    elif dewpoint_increase_max < 0.5:
        print("△ 結論: 沼からの寄与は小さいが考慮可能（0.1-0.5°C）")
        print("  高精度予報では局所補正を追加してもよい")
    else:
        print("✗ 結論: 沼からの寄与が大きい（>0.5°C）")
        print("  相当温位補正に局所補正を組み込むべき")

    # 影響範囲の検討
    print("\n" + "=" * 80)
    print("影響範囲の検討")
    print("=" * 80)
    print()

    print("水蒸気の拡散範囲:")
    print("  - 水平スケール: 風速×滞留時間")
    print("  - 風速2 m/s × 1時間 = 7.2 km")
    print("  - 風速8 m/s × 1時間 = 28.8 km")
    print()
    print("干場への影響:")
    print("  - 沼から5km以内の風下干場: やや影響あり")
    print("  - 沼から10km以上: ほぼ影響なし（拡散・混合）")
    print()

    # 干場との位置関係を確認
    print("主要干場との距離:")
    print("  - 姫沼から沓形: 約8 km（南西）")
    print("  - オタドマリ沼から沓形: 約3 km（東）")
    print("  - オタドマリ沼から鴛泊: 約16 km（北東）")
    print()
    print("→ 沓形は西風時にオタドマリ沼の風下（3km）")
    print("  局所的に湿度+0.05~0.1°C程度の可能性")
    print()

    # 可視化
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))

    # 蒸発量の比較
    ax1 = axes[0]
    pond_names = list(ponds.keys())
    cond_labels = [cond['name'] for cond in conditions.values()]

    x = np.arange(len(cond_labels))
    width = 0.35

    evap_hime = [results[c]['姫沼']['evap_rate'] for c in conditions.keys()]
    evap_ota = [results[c]['オタドマリ沼']['evap_rate'] for c in conditions.keys()]

    ax1.bar(x - width/2, evap_hime, width, label='Hime-numa', color='#3b82f6')
    ax1.bar(x + width/2, evap_ota, width, label='Otadomari-numa', color='#10b981')

    ax1.set_xlabel('Conditions', fontsize=12, weight='bold')
    ax1.set_ylabel('Evaporation Rate (mm/day)', fontsize=12, weight='bold')
    ax1.set_title('Evaporation Rate Comparison', fontsize=13, weight='bold')
    ax1.set_xticks(x)
    ax1.set_xticklabels(cond_labels, rotation=15, ha='right')
    ax1.legend()
    ax1.grid(True, alpha=0.3, axis='y')

    # 露点温度上昇の比較
    ax2 = axes[1]

    dewpoint_hime = [results[c]['姫沼']['dewpoint_increase'] for c in conditions.keys()]
    dewpoint_ota = [results[c]['オタドマリ沼']['dewpoint_increase'] for c in conditions.keys()]

    ax2.bar(x - width/2, dewpoint_hime, width, label='Hime-numa', color='#3b82f6')
    ax2.bar(x + width/2, dewpoint_ota, width, label='Otadomari-numa', color='#10b981')

    # 0.1°Cの閾値線
    ax2.axhline(0.1, color='red', linestyle='--', alpha=0.5, label='Negligible threshold (0.1C)')

    ax2.set_xlabel('Conditions', fontsize=12, weight='bold')
    ax2.set_ylabel('Dewpoint Temperature Increase (C)', fontsize=12, weight='bold')
    ax2.set_title('Estimated Dewpoint Increase (5km downwind)', fontsize=13, weight='bold')
    ax2.set_xticks(x)
    ax2.set_xticklabels(cond_labels, rotation=15, ha='right')
    ax2.legend()
    ax2.grid(True, alpha=0.3, axis='y')

    plt.tight_layout()

    output_file = 'pond_vapor_contribution.png'
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    print(f"✓ グラフを保存: {output_file}\n")

    return results

if __name__ == '__main__':
    estimate_vapor_contribution()
