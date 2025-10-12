#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
予報補正アルゴリズム

ERA5実測ベースの相関を使ってOpen-Meteo予報モデルを補正
"""

import json
import numpy as np
from datetime import datetime

def load_correlation_results():
    """各手法の相関結果を読み込み"""

    # 予報モデル
    with open('temporal_robustness_kutsugata.json', 'r', encoding='utf-8') as f:
        forecast_data = json.load(f)

    # ERA5実測
    with open('era5_contour_correlation_results.json', 'r', encoding='utf-8') as f:
        era5_data = json.load(f)

    # ラジオゾンデ
    with open('radiosonde_correlation_results.json', 'r', encoding='utf-8') as f:
        radiosonde_data = json.load(f)

    return {
        'forecast': forecast_data,
        'era5': era5_data,
        'radiosonde': radiosonde_data
    }

def calculate_bias_correction():
    """予報モデルのバイアスを計算"""

    results = load_correlation_results()

    # 相関係数の取得
    fc_vort = results['forecast']['forecast_data']['correlations']['cos_angle_vs_vorticity_500hPa']
    fc_omega = results['forecast']['forecast_data']['correlations']['cos_angle_vs_omega_700hPa']

    era5_vort = results['era5']['correlations']['cos_angle_vs_vorticity_500hPa_spatial']
    era5_omega = results['era5']['correlations']['cos_angle_vs_omega_700hPa']

    rs_vort = results['radiosonde']['correlations']['cos_angle_vs_vorticity_500hPa']
    rs_omega = results['radiosonde']['correlations']['cos_angle_vs_omega_700hPa']

    # バイアス計算（予報 - 実測）
    bias_vort_era5 = fc_vort - era5_vort
    bias_omega_era5 = fc_omega - era5_omega

    bias_vort_rs = fc_vort - rs_vort
    bias_omega_rs = fc_omega - rs_omega

    # 真の相関値（ERA5とラジオゾンデの平均）
    true_vort = (era5_vort + rs_vort) / 2
    true_omega = (era5_omega + rs_omega) / 2

    print("="*70)
    print("FORECAST BIAS CORRECTION")
    print("="*70)

    print(f"\ncos(angle) vs vorticity_500hPa:")
    print(f"  Forecast:     r = {fc_vort:+.3f}")
    print(f"  ERA5 (true):  r = {era5_vort:+.3f}")
    print(f"  Radiosonde:   r = {rs_vort:+.3f}")
    print(f"  True (avg):   r = {true_vort:+.3f}")
    print(f"  Bias:         dr = {bias_vort_era5:+.3f}")

    print(f"\ncos(angle) vs omega_700hPa:")
    print(f"  Forecast:     r = {fc_omega:+.3f}")
    print(f"  ERA5 (true):  r = {era5_omega:+.3f}")
    print(f"  Radiosonde:   r = {rs_omega:+.3f}")
    print(f"  True (avg):   r = {true_omega:+.3f}")
    print(f"  Bias:         dr = {bias_omega_era5:+.3f}")

    return {
        'bias': {
            'vorticity_500hPa': bias_vort_era5,
            'omega_700hPa': bias_omega_era5
        },
        'true_correlation': {
            'vorticity_500hPa': true_vort,
            'omega_700hPa': true_omega
        },
        'forecast_correlation': {
            'vorticity_500hPa': fc_vort,
            'omega_700hPa': fc_omega
        }
    }

def apply_calibration_weight(forecast_value, bias, method='linear'):
    """
    予報値にバイアス補正重みを適用

    Args:
        forecast_value: 予報モデルの相関ベース予測値
        bias: 予報モデルのバイアス
        method: 補正手法（linear, sigmoid, none）

    Returns:
        calibrated_value: 補正後の値
    """

    if method == 'none':
        return forecast_value

    elif method == 'linear':
        # 線形補正：予報値からバイアス分を減算
        correction_factor = 1.0 - abs(bias) / 1.0  # バイアスが大きいほど信頼度低下
        return forecast_value * correction_factor

    elif method == 'sigmoid':
        # シグモイド補正：バイアスが大きいほど非線形に減衰
        import math
        correction_factor = 1.0 / (1.0 + math.exp(abs(bias) - 0.5))
        return forecast_value * correction_factor

    else:
        raise ValueError(f"Unknown calibration method: {method}")

def calibrate_forecast_system():
    """予報システム全体のキャリブレーション"""

    print("\n" + "="*70)
    print("FORECAST CALIBRATION SYSTEM")
    print("="*70)

    # バイアス計算
    calibration = calculate_bias_correction()

    # 補正係数の計算
    print(f"\n{'='*70}")
    print("CALIBRATION COEFFICIENTS")
    print(f"{'='*70}")

    bias_vort = calibration['bias']['vorticity_500hPa']
    bias_omega = calibration['bias']['omega_700hPa']

    # 重み付け係数（バイアスが大きいほど予報への依存度を下げる）
    weight_vort = max(0, 1.0 - abs(bias_vort) / 2.0)
    weight_omega = max(0, 1.0 - abs(bias_omega) / 2.0)

    print(f"\nVorticity 500hPa:")
    print(f"  Bias:   {bias_vort:+.3f}")
    print(f"  Weight: {weight_vort:.3f} (0=no trust, 1=full trust)")

    print(f"\nOmega 700hPa:")
    print(f"  Bias:   {bias_omega:+.3f}")
    print(f"  Weight: {weight_omega:.3f}")

    # 推奨設定
    print(f"\n{'='*70}")
    print("RECOMMENDED FORECAST USAGE")
    print(f"{'='*70}")

    if weight_vort < 0.3:
        print("\n[WARNING] Vorticity-based forecast is UNRELIABLE")
        print("  -> Do NOT use 500hPa vorticity for synoptic scale prediction")
        print("  -> Rely on local observations instead")
    elif weight_vort < 0.6:
        print("\n[CAUTION] Vorticity-based forecast has MODERATE bias")
        print("  -> Use with caution, cross-check with observations")
    else:
        print("\n[OK] Vorticity-based forecast is reasonably accurate")

    if weight_omega < 0.3:
        print("\n[WARNING] Omega-based forecast is UNRELIABLE")
        print("  -> Do NOT use 700hPa omega for vertical motion prediction")
    elif weight_omega < 0.6:
        print("\n[CAUTION] Omega-based forecast has MODERATE bias")
        print("  -> Use with caution")
    else:
        print("\n[OK] Omega-based forecast is reasonably accurate")

    # 総合推奨
    print(f"\n{'='*70}")
    print("OVERALL RECOMMENDATION")
    print(f"{'='*70}")

    if weight_vort < 0.5 and weight_omega < 0.5:
        print("\n[CRITICAL] Forecast model shows large bias in BOTH parameters")
        print("\nRecommended approach:")
        print("  1. Use LOCAL wind observations (AMeDAS, spot data)")
        print("  2. Use simple wind-mountain angle difference")
        print("  3. Do NOT rely on forecast model's synoptic indicators")
        print("  4. Develop empirical relationships from historical data")
    else:
        print("\nRecommended approach:")
        print("  1. Use forecast as initial estimate")
        print(f"  2. Apply calibration weights: vorticity={weight_vort:.2f}, omega={weight_omega:.2f}")
        print("  3. Cross-validate with local observations")

    # 結果保存
    output = {
        'timestamp': datetime.now().isoformat(),
        'calibration': calibration,
        'weights': {
            'vorticity_500hPa': float(weight_vort),
            'omega_700hPa': float(weight_omega)
        },
        'recommendation': {
            'use_forecast_vorticity': weight_vort >= 0.5,
            'use_forecast_omega': weight_omega >= 0.5,
            'primary_method': 'local_observations' if (weight_vort < 0.5 and weight_omega < 0.5) else 'calibrated_forecast'
        }
    }

    with open('forecast_calibration_results.json', 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\nCalibration results saved to: forecast_calibration_results.json")

    return output

if __name__ == '__main__':
    calibrate_forecast_system()
