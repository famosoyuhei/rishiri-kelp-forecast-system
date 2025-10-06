#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
統合海洋-気象予報システム

海水温・降水量・海霧の総合リスク評価:
1. SST閾値による大雨リスク
2. 海霧リスク指数
3. 昆布干し適否の総合判定
"""

import xarray as xr
import numpy as np
from datetime import datetime, timedelta
import json

KUTSUGATA_LAT = 45.2422
KUTSUGATA_LON = 141.1088

# 閾値定義（解析結果に基づく）
SST_HIGH_RAIN_THRESHOLD = 24.0  # °C - 大雨リスク閾値
SST_MODERATE_RAIN_THRESHOLD = 19.0  # °C - 中程度の降水リスク
FOG_RISK_THRESHOLD = 2.0  # °C - 海霧高リスク閾値（SST-露点温度差）

def calculate_integrated_drying_risk(sst_C, dewpoint_C, precipitation_mm=0):
    """
    昆布干し総合リスク評価

    Parameters:
    -----------
    sst_C : float
        海面水温 (°C)
    dewpoint_C : float
        露点温度 (°C)
    precipitation_mm : float
        予想降水量 (mm)

    Returns:
    --------
    risk_score : float (0-100)
        リスクスコア。100が最悪、0が最良
    risk_factors : dict
        各リスク要因の詳細
    """

    risk_factors = {}
    total_risk = 0

    # 1. 降水リスク（0-40点）
    if precipitation_mm > 5.0:
        precip_risk = 40
        risk_factors['precipitation'] = 'CRITICAL'
    elif precipitation_mm > 1.0:
        precip_risk = 20
        risk_factors['precipitation'] = 'HIGH'
    elif precipitation_mm > 0.5:
        precip_risk = 10
        risk_factors['precipitation'] = 'MODERATE'
    else:
        precip_risk = 0
        risk_factors['precipitation'] = 'LOW'

    total_risk += precip_risk

    # 2. SST大雨リスク（0-30点）
    if sst_C >= SST_HIGH_RAIN_THRESHOLD:
        sst_rain_risk = 30
        risk_factors['sst_rain_potential'] = 'CRITICAL'
    elif sst_C >= SST_MODERATE_RAIN_THRESHOLD:
        sst_rain_risk = 15
        risk_factors['sst_rain_potential'] = 'MODERATE'
    else:
        sst_rain_risk = 5
        risk_factors['sst_rain_potential'] = 'LOW'

    total_risk += sst_rain_risk

    # 3. 海霧リスク（0-30点）
    fog_index = sst_C - dewpoint_C

    if fog_index < 0:
        fog_risk = 30
        risk_factors['fog_risk'] = 'CRITICAL'
    elif fog_index < FOG_RISK_THRESHOLD:
        fog_risk = 20
        risk_factors['fog_risk'] = 'HIGH'
    elif fog_index < 4.0:
        fog_risk = 10
        risk_factors['fog_risk'] = 'MODERATE'
    else:
        fog_risk = 0
        risk_factors['fog_risk'] = 'LOW'

    total_risk += fog_risk
    risk_factors['fog_index'] = float(round(fog_index, 2))

    return total_risk, risk_factors

def get_drying_recommendation(risk_score):
    """リスクスコアから昆布干し推奨度を判定"""

    if risk_score >= 60:
        return {
            'recommendation': 'NOT_SUITABLE',
            'label': 'Not Suitable',
            'color': 'red',
            'message': 'High risk of heavy rain or sea fog. Kelp drying should be avoided.'
        }
    elif risk_score >= 40:
        return {
            'recommendation': 'CAUTION',
            'label': 'Caution',
            'color': 'orange',
            'message': 'Moderate risk of precipitation or fog. Limited drying time recommended.'
        }
    elif risk_score >= 20:
        return {
            'recommendation': 'FAIR',
            'label': 'Fair',
            'color': 'yellow',
            'message': 'Some risk present. Kelp drying possible with monitoring.'
        }
    else:
        return {
            'recommendation': 'SUITABLE',
            'label': 'Suitable',
            'color': 'green',
            'message': 'Low risk of fog and precipitation. Good conditions for kelp drying.'
        }

def forecast_with_ocean_integration(forecast_date_str=None):
    """
    海洋データを統合した昆布干し予報

    Parameters:
    -----------
    forecast_date_str : str (optional)
        予報日時 'YYYY-MM-DD' 形式。Noneの場合は最新データ使用
    """

    print("="*70)
    print("INTEGRATED OCEAN-WEATHER FORECAST FOR KELP DRYING")
    print("="*70)

    # 最新の海洋データを読み込み
    try:
        ocean_ds = xr.open_dataset('era5_rishiri_ocean_summer2025.nc')
        print("\nOcean data loaded successfully")
    except FileNotFoundError:
        print("\nError: Ocean data not found")
        return None

    # 変数名特定
    sst_var = 'sst' if 'sst' in ocean_ds else 'sea_surface_temperature'
    d2m_var = 'd2m' if 'd2m' in ocean_ds else '2m_dewpoint_temperature'

    # 沓形地点
    lat = ocean_ds.latitude.values
    lon = ocean_ds.longitude.values
    lat_idx = np.abs(lat - KUTSUGATA_LAT).argmin()
    lon_idx = np.abs(lon - KUTSUGATA_LON).argmin()

    print(f"Analysis point: Kutsugata ({KUTSUGATA_LAT:.2f}N, {KUTSUGATA_LON:.2f}E)")

    # SST・露点温度を抽出
    sst = ocean_ds[sst_var].isel(latitude=lat_idx, longitude=lon_idx)
    d2m = ocean_ds[d2m_var].isel(latitude=lat_idx, longitude=lon_idx)

    sst_values = sst.values - 273.15  # K -> C
    d2m_values = d2m.values - 273.15

    # 日別予報を生成
    print(f"\n{'='*70}")
    print("7-DAY INTEGRATED FORECAST")
    print(f"{'='*70}")

    forecasts = []

    # 最新7日間の予報（実際はリアルタイムデータやJMA予報を使用）
    n_days = min(7, len(sst_values))
    start_idx = len(sst_values) - n_days

    for i in range(start_idx, len(sst_values)):
        day_num = i - start_idx + 1
        sst_c = sst_values[i]
        d2m_c = d2m_values[i]

        # 降水量予測（実際はJMA予報から取得、ここでは仮値）
        # 高SST時は降水リスクを上げる
        if sst_c >= SST_HIGH_RAIN_THRESHOLD:
            precip_forecast = 3.0  # 仮の予測値
        elif sst_c >= SST_MODERATE_RAIN_THRESHOLD:
            precip_forecast = 1.0
        else:
            precip_forecast = 0.5

        # 総合リスク評価
        risk_score, risk_factors = calculate_integrated_drying_risk(
            sst_c, d2m_c, precip_forecast
        )

        recommendation = get_drying_recommendation(risk_score)

        forecast_entry = {
            'day': day_num,
            'date': str(ocean_ds.valid_time.values[i])[:10],
            'sst_C': round(float(sst_c), 1),
            'dewpoint_C': round(float(d2m_c), 1),
            'precipitation_forecast_mm': round(precip_forecast, 1),
            'risk_score': int(risk_score),
            'risk_factors': risk_factors,
            'recommendation': recommendation['recommendation'],
            'label': recommendation['label'],
            'message': recommendation['message']
        }

        forecasts.append(forecast_entry)

        # コンソール出力
        print(f"\nDay {day_num} ({forecast_entry['date']}):")
        print(f"  SST: {forecast_entry['sst_C']}C | Dewpoint: {forecast_entry['dewpoint_C']}C")
        print(f"  Fog Risk: {risk_factors['fog_risk']} (Index: {risk_factors['fog_index']}C)")
        print(f"  SST Rain Potential: {risk_factors['sst_rain_potential']}")
        print(f"  Precipitation: {risk_factors['precipitation']}")
        print(f"  RISK SCORE: {risk_score}/100")
        print(f"  => {recommendation['label']}: {recommendation['message']}")

    # 統計サマリー
    suitable_days = sum(1 for f in forecasts if f['recommendation'] == 'SUITABLE')
    unsuitable_days = sum(1 for f in forecasts if f['recommendation'] == 'NOT_SUITABLE')

    print(f"\n{'='*70}")
    print("WEEKLY SUMMARY")
    print(f"{'='*70}")
    print(f"Suitable days: {suitable_days}/{n_days}")
    print(f"Unsuitable days: {unsuitable_days}/{n_days}")
    print(f"Success rate: {suitable_days/n_days*100:.1f}%")

    # JSON保存
    output = {
        'forecast_generated': datetime.now().isoformat(),
        'location': f"Kutsugata ({KUTSUGATA_LAT}N, {KUTSUGATA_LON}E)",
        'thresholds': {
            'sst_high_rain_C': SST_HIGH_RAIN_THRESHOLD,
            'sst_moderate_rain_C': SST_MODERATE_RAIN_THRESHOLD,
            'fog_risk_threshold_C': FOG_RISK_THRESHOLD
        },
        'forecasts': forecasts,
        'summary': {
            'suitable_days': suitable_days,
            'unsuitable_days': unsuitable_days,
            'total_days': n_days
        }
    }

    with open('integrated_ocean_forecast.json', 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print("\nSaved: integrated_ocean_forecast.json")

    print(f"\n{'='*70}")
    print("FORECAST COMPLETE")
    print(f"{'='*70}")

    return output

if __name__ == '__main__':
    forecast_with_ocean_integration()
