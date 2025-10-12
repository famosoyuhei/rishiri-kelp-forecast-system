#!/usr/bin/env python3
"""
相当温位保存による風下地点の気象補正

原理:
1. 風上地点のエマグラムから相当温位θₑプロファイルを取得
2. 風下地点の気圧面で、風上と同じθₑを仮定
3. 断熱下降を考慮して、風下の気温・湿度を補正
"""
import numpy as np
import requests
from scipy.optimize import fsolve
import json

class ThetaECorrection:
    """相当温位保存による気象補正クラス"""

    def __init__(self):
        self.L = 2.5e6  # 蒸発潜熱（J/kg）
        self.Cp = 1005  # 定圧比熱（J/kg/K）
        self.kappa = 0.286  # R/Cp
        self.epsilon = 0.622  # 水蒸気と乾燥空気の分子量比

    def saturation_vapor_pressure(self, T):
        """飽和水蒸気圧（Magnus式）"""
        return 6.112 * np.exp(17.67 * T / (T + 243.5))

    def mixing_ratio(self, T, Td, P):
        """混合比を計算"""
        e = self.saturation_vapor_pressure(Td)
        return self.epsilon * e / (P - e)

    def potential_temperature(self, T, P):
        """温位を計算"""
        T_K = T + 273.15
        return T_K * (1000.0 / P) ** self.kappa

    def equivalent_potential_temperature(self, T, Td, P):
        """相当温位を計算"""
        theta = self.potential_temperature(T, P)
        q = self.mixing_ratio(T, Td, P)
        T_K = T + 273.15

        theta_e = theta * np.exp(self.L * q / (self.Cp * T_K))
        return theta_e

    def dewpoint_from_mixing_ratio(self, q, P):
        """混合比から露点温度を逆算"""
        e = q * P / (self.epsilon + q)
        # Magnus式の逆関数
        Td = 243.5 * np.log(e / 6.112) / (17.67 - np.log(e / 6.112))
        return Td

    def temperature_from_theta_e(self, theta_e_target, P, initial_guess=10.0):
        """
        相当温位と気圧から気温・露点温度を逆算

        仮定: 飽和状態（RH=100%）で下降
        """
        def objective(T):
            """目的関数: 計算したθₑと目標θₑの差"""
            Td = T  # 飽和状態を仮定
            theta_e_calc = self.equivalent_potential_temperature(T, Td, P)
            return theta_e_calc - theta_e_target

        # 数値的に解く
        T_solution = fsolve(objective, initial_guess)[0]
        return T_solution, T_solution  # 飽和状態なのでT=Td

    def temperature_from_theta_e_with_rh(self, theta_e_target, P, RH=0.7, initial_guess=10.0):
        """
        相当温位と気圧から気温・露点温度を逆算（相対湿度を指定）

        Args:
            theta_e_target: 目標相当温位（K）
            P: 気圧（hPa）
            RH: 相対湿度（0-1）
            initial_guess: 初期推定気温（℃）
        """
        def objective(T):
            """目的関数"""
            # 相対湿度から露点温度を計算
            es_T = self.saturation_vapor_pressure(T)
            e = RH * es_T
            Td = 243.5 * np.log(e / 6.112) / (17.67 - np.log(e / 6.112))

            theta_e_calc = self.equivalent_potential_temperature(T, Td, P)
            return theta_e_calc - theta_e_target

        try:
            T_solution = fsolve(objective, initial_guess)[0]
            # 露点温度を計算
            es_T = self.saturation_vapor_pressure(T_solution)
            e = RH * es_T
            Td_solution = 243.5 * np.log(e / 6.112) / (17.67 - np.log(e / 6.112))
            return T_solution, Td_solution
        except:
            return None, None

    def correct_leeward_profile(self, windward_data, leeward_pressure_levels,
                                terrain_descent_m=500, rh_reduction=0.15):
        """
        風上データから風下プロファイルを補正

        Args:
            windward_data: 風上のエマグラムデータ
            leeward_pressure_levels: 風下の気圧レベル
            terrain_descent_m: 地形による下降高度（m）
            rh_reduction: 下降による相対湿度低下（0-1）

        Returns:
            補正された気温・露点温度プロファイル
        """
        # 風上の相当温位プロファイルを計算
        windward_theta_e = []
        for i in range(len(windward_data['pressure'])):
            theta_e = self.equivalent_potential_temperature(
                windward_data['temperature'][i],
                windward_data['dewpoint'][i],
                windward_data['pressure'][i]
            )
            windward_theta_e.append(theta_e)

        # 高度から気圧への変換（簡易版: 標準大気）
        # ΔP ≈ -ρgΔz ≈ -12 hPa/100m（下層）
        pressure_increase = terrain_descent_m / 100.0 * 12.0  # hPa

        corrected_profile = {
            'pressure': [],
            'temperature_corrected': [],
            'dewpoint_corrected': [],
            'temperature_api': [],
            'dewpoint_api': [],
            'theta_e': []
        }

        for P_leeward in leeward_pressure_levels:
            # 風下の気圧に対応する「風上の等価気圧」
            # 下降流があるので、風上ではより高い高度（低い気圧）の空気が降りてくる
            P_windward_equivalent = P_leeward - pressure_increase

            # 風上のθₑプロファイルから内挿
            if P_windward_equivalent < min(windward_data['pressure']) or \
               P_windward_equivalent > max(windward_data['pressure']):
                # 範囲外の場合はスキップ
                continue

            theta_e_at_level = np.interp(
                P_windward_equivalent,
                windward_data['pressure'][::-1],  # 昇順に並べ替え
                windward_theta_e[::-1]
            )

            # 風下での相対湿度を推定（下降により乾燥）
            # 風上の湿度から一定量減少
            idx_windward = np.argmin(np.abs(np.array(windward_data['pressure']) - P_windward_equivalent))
            T_wind = windward_data['temperature'][idx_windward]
            Td_wind = windward_data['dewpoint'][idx_windward]

            es_wind = self.saturation_vapor_pressure(T_wind)
            e_wind = self.saturation_vapor_pressure(Td_wind)
            rh_wind = e_wind / es_wind if es_wind > 0 else 0.7

            rh_leeward = max(0.1, rh_wind - rh_reduction)  # 下降により乾燥

            # θₑとRHから気温・露点温度を逆算
            T_corrected, Td_corrected = self.temperature_from_theta_e_with_rh(
                theta_e_at_level, P_leeward, rh_leeward, initial_guess=T_wind
            )

            if T_corrected is not None:
                corrected_profile['pressure'].append(P_leeward)
                corrected_profile['temperature_corrected'].append(T_corrected)
                corrected_profile['dewpoint_corrected'].append(Td_corrected)
                corrected_profile['theta_e'].append(theta_e_at_level)

        return corrected_profile


def fetch_emagram(lat, lon):
    """エマグラムデータを取得"""
    url = "https://rishiri-kelp-forecast-system.onrender.com/api/emagram"
    params = {'lat': lat, 'lon': lon, 'time': 0}

    response = requests.get(url, params=params, timeout=30)
    response.raise_for_status()
    data = response.json()

    return data['data']


def demonstrate_correction():
    """相当温位補正のデモンストレーション"""

    print("=" * 80)
    print("相当温位保存による風下気象補正")
    print("=" * 80)
    print()

    # 風上: 沓形（西側）
    print("風上地点（沓形）のデータ取得中...")
    windward_data = fetch_emagram(45.163, 141.143)
    print("✓ 完了\n")

    # 風下: 鴛泊（東側）
    print("風下地点（鴛泊）のデータ取得中...")
    leeward_data = fetch_emagram(45.242, 141.242)
    print("✓ 完了\n")

    # 補正実行
    corrector = ThetaECorrection()

    print("=" * 80)
    print("補正計算実行")
    print("=" * 80)
    print()
    print("仮定:")
    print("  - 利尻山（標高1721m）を越える西風")
    print("  - 風下（鴛泊）では約500m下降")
    print("  - 下降により相対湿度15%低下（フェーン効果）")
    print()

    corrected = corrector.correct_leeward_profile(
        windward_data,
        leeward_data['pressure'],
        terrain_descent_m=500,
        rh_reduction=0.15
    )

    # 結果を表示
    print("=" * 80)
    print("補正結果")
    print("=" * 80)
    print()
    print(f"{'気圧':>8} | {'API気温':>8} {'補正気温':>8} {'差':>7} | {'API露点':>8} {'補正露点':>8} {'差':>7}")
    print("-" * 80)

    for i in range(len(corrected['pressure'])):
        P = corrected['pressure'][i]

        # API値を取得
        idx_api = np.argmin(np.abs(np.array(leeward_data['pressure']) - P))
        T_api = leeward_data['temperature'][idx_api]
        Td_api = leeward_data['dewpoint'][idx_api]

        T_corr = corrected['temperature_corrected'][i]
        Td_corr = corrected['dewpoint_corrected'][i]

        T_diff = T_corr - T_api
        Td_diff = Td_corr - Td_api

        print(f"{P:>8.0f} | {T_api:>8.2f} {T_corr:>8.2f} {T_diff:>+7.2f} | "
              f"{Td_api:>8.2f} {Td_corr:>8.2f} {Td_diff:>+7.2f}")

    # 統計
    T_diffs = [corrected['temperature_corrected'][i] - leeward_data['temperature'][
        np.argmin(np.abs(np.array(leeward_data['pressure']) - corrected['pressure'][i]))]
        for i in range(len(corrected['pressure']))]

    Td_diffs = [corrected['dewpoint_corrected'][i] - leeward_data['dewpoint'][
        np.argmin(np.abs(np.array(leeward_data['pressure']) - corrected['pressure'][i]))]
        for i in range(len(corrected['pressure']))]

    print("\n" + "=" * 80)
    print("統計")
    print("=" * 80)
    print(f"\n気温補正:")
    print(f"  平均: {np.mean(T_diffs):+.2f}°C")
    print(f"  範囲: {np.min(T_diffs):+.2f}°C ~ {np.max(T_diffs):+.2f}°C")

    print(f"\n露点温度補正:")
    print(f"  平均: {np.mean(Td_diffs):+.2f}°C")
    print(f"  範囲: {np.min(Td_diffs):+.2f}°C ~ {np.max(Td_diffs):+.2f}°C")

    print("\n" + "=" * 80)
    print("解釈")
    print("=" * 80)
    print("\n風下（鴛泊）での期待される変化:")
    print("  - 気温: 上昇（下降流による断熱圧縮）")
    print("  - 露点温度: 低下（下降による乾燥、フェーン効果）")
    print("  - 相対湿度: 大幅低下（昆布乾燥に有利）")
    print()

    # 結果を保存
    result = {
        'windward': {'name': '沓形', 'lat': 45.163, 'lon': 141.143},
        'leeward': {'name': '鴛泊', 'lat': 45.242, 'lon': 141.242},
        'assumptions': {
            'terrain_descent_m': 500,
            'rh_reduction': 0.15
        },
        'correction': corrected,
        'api_data': {
            'pressure': leeward_data['pressure'],
            'temperature': leeward_data['temperature'],
            'dewpoint': leeward_data['dewpoint']
        }
    }

    with open('theta_e_correction_result.json', 'w', encoding='utf-8') as f:
        # numpy配列をリストに変換
        result_serializable = {
            'windward': result['windward'],
            'leeward': result['leeward'],
            'assumptions': result['assumptions'],
            'correction': {k: (v.tolist() if isinstance(v, np.ndarray) else v)
                          for k, v in result['correction'].items()},
            'api_data': {k: (v if isinstance(v, list) else v)
                        for k, v in result['api_data'].items()}
        }
        json.dump(result_serializable, f, indent=2, ensure_ascii=False)

    print("✓ 結果を保存: theta_e_correction_result.json\n")

    return result


if __name__ == '__main__':
    demonstrate_correction()
