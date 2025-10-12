#!/usr/bin/env python3
"""
風上・風下での温位・相当温位の比較

仮説: 温位（θ）と相当温位（θₑ）は風上・風下で保存されるが、
      気温と露点温度は変化する
"""
import requests
import numpy as np
import matplotlib.pyplot as plt
from matplotlib import rcParams

# 日本語フォント設定（警告を回避）
rcParams['font.sans-serif'] = ['DejaVu Sans']

def calculate_potential_temperature(T, P):
    """
    温位を計算

    θ = T × (P₀/P)^(R/Cp)

    Args:
        T: 気温（℃）
        P: 気圧（hPa）

    Returns:
        温位（K）
    """
    T_kelvin = T + 273.15
    P0 = 1000.0  # 基準気圧（hPa）
    kappa = 0.286  # R/Cp（乾燥空気）

    theta = T_kelvin * (P0 / P) ** kappa
    return theta

def calculate_mixing_ratio(T, Td, P):
    """
    混合比を計算（簡易版）

    Args:
        T: 気温（℃）
        Td: 露点温度（℃）
        P: 気圧（hPa）

    Returns:
        混合比（kg/kg）
    """
    # Magnus式で飽和水蒸気圧を計算
    def es(temp):
        return 6.112 * np.exp(17.67 * temp / (temp + 243.5))

    e = es(Td)  # 実際の水蒸気圧
    epsilon = 0.622  # 水蒸気と乾燥空気の分子量比

    q = epsilon * e / (P - e)
    return q

def calculate_equivalent_potential_temperature(T, Td, P):
    """
    相当温位を計算（簡易版）

    θₑ ≈ θ × exp(Lq / CpT)

    Args:
        T: 気温（℃）
        Td: 露点温度（℃）
        P: 気圧（hPa）

    Returns:
        相当温位（K）
    """
    theta = calculate_potential_temperature(T, P)
    q = calculate_mixing_ratio(T, Td, P)

    T_kelvin = T + 273.15
    L = 2.5e6  # 蒸発潜熱（J/kg）
    Cp = 1005  # 定圧比熱（J/kg/K）

    theta_e = theta * np.exp(L * q / (Cp * T_kelvin))
    return theta_e

def fetch_emagram(lat, lon):
    """エマグラムデータを取得"""
    url = "https://rishiri-kelp-forecast-system.onrender.com/api/emagram"
    params = {'lat': lat, 'lon': lon, 'time': 0}

    response = requests.get(url, params=params, timeout=30)
    response.raise_for_status()
    data = response.json()

    return data['data']

def compare_windward_leeward():
    """風上・風下の温位比較"""

    # 現在の風向を仮定（西風: 270度）
    # 風上: 沓形（西側）
    # 風下: 鴛泊（東側）

    locations = [
        {
            'name': '沓形（風上・西側）',
            'name_en': 'Kutsugata (Windward)',
            'lat': 45.163,
            'lon': 141.143,
            'color': '#007bff'
        },
        {
            'name': '鴛泊（風下・東側）',
            'name_en': 'Oshidomari (Leeward)',
            'lat': 45.242,
            'lon': 141.242,
            'color': '#dc3545'
        }
    ]

    print("=" * 80)
    print("風上・風下での温位・相当温位の比較")
    print("=" * 80)
    print("\n仮定: 西風（270度）が卓越")
    print("  - 風上: 沓形（西側、海岸）")
    print("  - 風下: 鴛泊（東側、利尻山の風下）\n")

    results = []

    for loc in locations:
        print(f"取得中: {loc['name']} ({loc['lat']:.3f}, {loc['lon']:.3f})")
        data = fetch_emagram(loc['lat'], loc['lon'])

        # 温位・相当温位を計算
        pressures = np.array(data['pressure'])
        temps = np.array(data['temperature'])
        dewpoints = np.array(data['dewpoint'])

        thetas = []
        theta_es = []

        for i in range(len(pressures)):
            theta = calculate_potential_temperature(temps[i], pressures[i])
            theta_e = calculate_equivalent_potential_temperature(temps[i], dewpoints[i], pressures[i])
            thetas.append(theta)
            theta_es.append(theta_e)

        results.append({
            'name': loc['name'],
            'name_en': loc['name_en'],
            'color': loc['color'],
            'pressure': pressures,
            'temperature': temps,
            'dewpoint': dewpoints,
            'theta': np.array(thetas),
            'theta_e': np.array(theta_es)
        })

        print(f"  ✓ 完了\n")

    # 比較分析
    print("=" * 80)
    print("気圧面ごとの比較")
    print("=" * 80)
    print(f"\n{'気圧':>8} | {'風上T':>7} {'風下T':>7} {'差':>6} | {'風上θ':>7} {'風下θ':>7} {'差':>6} | {'風上θe':>7} {'風下θe':>7} {'差':>6}")
    print("-" * 80)

    for i in range(len(results[0]['pressure'])):
        p = results[0]['pressure'][i]

        t_windward = results[0]['temperature'][i]
        t_leeward = results[1]['temperature'][i]
        t_diff = t_leeward - t_windward

        theta_windward = results[0]['theta'][i]
        theta_leeward = results[1]['theta'][i]
        theta_diff = theta_leeward - theta_windward

        theta_e_windward = results[0]['theta_e'][i]
        theta_e_leeward = results[1]['theta_e'][i]
        theta_e_diff = theta_e_leeward - theta_e_windward

        print(f"{p:>8.0f} | {t_windward:>7.1f} {t_leeward:>7.1f} {t_diff:>6.2f} | "
              f"{theta_windward:>7.1f} {theta_leeward:>7.1f} {theta_diff:>6.2f} | "
              f"{theta_e_windward:>7.1f} {theta_e_leeward:>7.1f} {theta_e_diff:>6.2f}")

    # 統計
    print("\n" + "=" * 80)
    print("統計（全気圧面の平均）")
    print("=" * 80)

    theta_diffs = results[1]['theta'] - results[0]['theta']
    theta_e_diffs = results[1]['theta_e'] - results[0]['theta_e']

    print(f"\n温位差（風下-風上）:")
    print(f"  平均: {np.mean(theta_diffs):.2f}K")
    print(f"  標準偏差: {np.std(theta_diffs):.2f}K")
    print(f"  最大: {np.max(np.abs(theta_diffs)):.2f}K")

    print(f"\n相当温位差（風下-風上）:")
    print(f"  平均: {np.mean(theta_e_diffs):.2f}K")
    print(f"  標準偏差: {np.std(theta_e_diffs):.2f}K")
    print(f"  最大: {np.max(np.abs(theta_e_diffs)):.2f}K")

    # 判定
    print("\n" + "=" * 80)
    print("結論")
    print("=" * 80)

    theta_conserved = np.max(np.abs(theta_diffs)) < 1.0
    theta_e_conserved = np.max(np.abs(theta_e_diffs)) < 1.0

    if theta_conserved:
        print("\n✓ 温位（θ）は風上・風下でほぼ保存されている")
    else:
        print(f"\n△ 温位（θ）に差がある（最大{np.max(np.abs(theta_diffs)):.1f}K）")

    if theta_e_conserved:
        print("✓ 相当温位（θₑ）は風上・風下でほぼ保存されている")
    else:
        print(f"△ 相当温位（θₑ）に差がある（最大{np.max(np.abs(theta_e_diffs)):.1f}K）")

    print("\n注: APIの空間解像度が粗いため、真の風上・風下の差が")
    print("    正確に表現されていない可能性があります。")

    # 可視化
    fig, axes = plt.subplots(1, 3, figsize=(18, 8))

    # 温位
    ax1 = axes[0]
    for r in results:
        ax1.plot(r['theta'], r['pressure'], 'o-',
                color=r['color'], linewidth=2, markersize=5,
                label=r['name_en'])
    ax1.set_xlabel('Potential Temperature (K)', fontsize=12, weight='bold')
    ax1.set_ylabel('Pressure (hPa)', fontsize=12, weight='bold')
    ax1.set_title('Potential Temperature (theta)', fontsize=13, weight='bold')
    ax1.invert_yaxis()
    ax1.grid(True, alpha=0.3)
    ax1.legend()

    # 相当温位
    ax2 = axes[1]
    for r in results:
        ax2.plot(r['theta_e'], r['pressure'], 'o-',
                color=r['color'], linewidth=2, markersize=5,
                label=r['name_en'])
    ax2.set_xlabel('Equivalent Potential Temperature (K)', fontsize=12, weight='bold')
    ax2.set_ylabel('Pressure (hPa)', fontsize=12, weight='bold')
    ax2.set_title('Equivalent Potential Temperature (theta_e)', fontsize=13, weight='bold')
    ax2.invert_yaxis()
    ax2.grid(True, alpha=0.3)
    ax2.legend()

    # 差分
    ax3 = axes[2]
    ax3.plot(theta_diffs, results[0]['pressure'], 'o-',
            color='purple', linewidth=2, markersize=5,
            label='Theta diff (Leeward - Windward)')
    ax3.plot(theta_e_diffs, results[0]['pressure'], 's-',
            color='orange', linewidth=2, markersize=5,
            label='Theta_e diff (Leeward - Windward)')
    ax3.axvline(0, color='gray', linestyle='--', alpha=0.5)
    ax3.set_xlabel('Difference (K)', fontsize=12, weight='bold')
    ax3.set_ylabel('Pressure (hPa)', fontsize=12, weight='bold')
    ax3.set_title('Windward-Leeward Difference', fontsize=13, weight='bold')
    ax3.invert_yaxis()
    ax3.grid(True, alpha=0.3)
    ax3.legend()

    plt.tight_layout()

    output_file = 'potential_temperature_comparison.png'
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    print(f"\n✓ グラフを保存: {output_file}\n")

if __name__ == '__main__':
    compare_windward_leeward()
