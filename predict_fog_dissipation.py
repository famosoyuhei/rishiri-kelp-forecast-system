#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
海霧消散予測システム

朝霧 vs 終日霧の判定:
1. 日射量（雲量）の影響
2. 風速による混合効果
3. SST-気温差の日変化
4. 露点温度の日変化率
"""

import matplotlib
matplotlib.use('Agg')  # GUIなし環境用（Render対応）

import xarray as xr
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime
import json

KUTSUGATA_LAT = 45.2422
KUTSUGATA_LON = 141.1088

# 霧消散判定閾値
WIND_MIXING_THRESHOLD = 4.0  # m/s - 風速がこれ以上なら混合効果
CLOUD_CLEAR_THRESHOLD = 0.3  # 0-1 - 雲量がこれ以下なら日射効果
TEMP_RISE_THRESHOLD = 3.0  # °C - 日中の気温上昇がこれ以上なら消散

def analyze_fog_dissipation_pattern():
    """海霧消散パターンの解析"""

    print("="*70)
    print("FOG DISSIPATION PREDICTION SYSTEM")
    print("="*70)

    # データ読み込み（時間解像度の高いデータが必要）
    try:
        # 2025年夏のデータ（3時間ごと）
        ocean_ds = xr.open_dataset('era5_rishiri_ocean_summer2025.nc')
        print("\nOcean data loaded successfully")

        # データの時間解像度を確認
        times = ocean_ds.valid_time.values
        print(f"Data points: {len(times)}")
        print(f"Time range: {str(times[0])[:19]} to {str(times[-1])[:19]}")

    except FileNotFoundError as e:
        print(f"\nError: {e}")
        return

    # 変数名特定
    sst_var = 'sst' if 'sst' in ocean_ds else 'sea_surface_temperature'
    t2m_var = 't2m' if 't2m' in ocean_ds else '2m_temperature'
    d2m_var = 'd2m' if 'd2m' in ocean_ds else '2m_dewpoint_temperature'

    # 風速成分
    u10_var = 'u10' if 'u10' in ocean_ds else '10m_u_component_of_wind'
    v10_var = 'v10' if 'v10' in ocean_ds else '10m_v_component_of_wind'

    # 雲量
    tcc_var = 'tcc' if 'tcc' in ocean_ds else 'total_cloud_cover'

    # 沓形地点
    lat = ocean_ds.latitude.values
    lon = ocean_ds.longitude.values
    lat_idx = np.abs(lat - KUTSUGATA_LAT).argmin()
    lon_idx = np.abs(lon - KUTSUGATA_LON).argmin()

    print(f"\nAnalysis point: Kutsugata ({KUTSUGATA_LAT:.2f}N, {KUTSUGATA_LON:.2f}E)")

    # データ抽出
    sst = ocean_ds[sst_var].isel(latitude=lat_idx, longitude=lon_idx).values - 273.15
    t2m = ocean_ds[t2m_var].isel(latitude=lat_idx, longitude=lon_idx).values - 273.15
    d2m = ocean_ds[d2m_var].isel(latitude=lat_idx, longitude=lon_idx).values - 273.15
    u10 = ocean_ds[u10_var].isel(latitude=lat_idx, longitude=lon_idx).values
    v10 = ocean_ds[v10_var].isel(latitude=lat_idx, longitude=lon_idx).values
    tcc = ocean_ds[tcc_var].isel(latitude=lat_idx, longitude=lon_idx).values

    # 風速計算
    wind_speed = np.sqrt(u10**2 + v10**2)

    # 霧リスク指数
    fog_risk = sst - d2m

    # 相対湿度の近似（Magnus式）
    def calculate_relative_humidity(T, Td):
        """相対湿度計算（T, Td: °C）"""
        def saturation_vapor_pressure(T):
            return 6.112 * np.exp(17.67 * T / (T + 243.5))

        es_T = saturation_vapor_pressure(T)
        es_Td = saturation_vapor_pressure(Td)
        RH = 100 * es_Td / es_T
        return np.clip(RH, 0, 100)

    rh = calculate_relative_humidity(t2m, d2m)

    print(f"\n{'='*70}")
    print("HOURLY FOG RISK AND DISSIPATION FACTORS")
    print(f"{'='*70}")

    # 時刻をUTC時間から抽出（JST = UTC+9）
    hours_utc = np.array([np.datetime64(t, 'h').astype(int) % 24 for t in times])

    # 日別に解析
    dates = np.array([np.datetime64(t, 'D') for t in times])
    unique_dates = np.unique(dates)

    fog_dissipation_forecast = []

    for date in unique_dates[-14:]:  # 最新2週間
        mask = dates == date
        if not np.any(mask):
            continue

        # その日のデータ
        day_sst = sst[mask]
        day_t2m = t2m[mask]
        day_d2m = d2m[mask]
        day_wind = wind_speed[mask]
        day_tcc = tcc[mask]
        day_rh = rh[mask]
        day_fog_risk = fog_risk[mask]
        day_hours = hours_utc[mask]

        # 朝（09:00 UTC = 18:00 JST）と昼（00:00 UTC = 09:00 JST）のインデックス
        # ERA5は09:00 UTCの1日1データなので、全時間データが必要
        # ここでは簡略化のため1日1点のデータとして扱う

        morning_fog_risk = day_fog_risk[0] if len(day_fog_risk) > 0 else np.nan
        morning_rh = day_rh[0] if len(day_rh) > 0 else np.nan
        morning_wind = day_wind[0] if len(day_wind) > 0 else np.nan
        morning_cloud = day_tcc[0] if len(day_tcc) > 0 else np.nan

        # 霧発生の判定
        fog_present = (morning_fog_risk < 2.0) and (morning_rh > 90)

        if not fog_present:
            dissipation_type = 'NO_FOG'
            confidence = 'HIGH'
            message = 'No fog expected'
        else:
            # 消散予測
            dissipation_score = 0
            factors = []

            # 1. 風による混合効果
            if morning_wind >= WIND_MIXING_THRESHOLD:
                dissipation_score += 40
                factors.append(f'Wind mixing (>{WIND_MIXING_THRESHOLD} m/s)')

            # 2. 日射効果（雲量が少ない）
            if morning_cloud < CLOUD_CLEAR_THRESHOLD:
                dissipation_score += 30
                factors.append(f'Solar radiation (cloud<{CLOUD_CLEAR_THRESHOLD*100:.0f}%)')

            # 3. SST-気温差が大きい（消散しにくい）
            sst_t2m_diff = day_sst[0] - day_t2m[0]
            if sst_t2m_diff < 1.0:
                dissipation_score += 20
                factors.append('Small SST-T2m difference')

            # 4. 相対湿度
            if morning_rh < 95:
                dissipation_score += 10
                factors.append('RH<95%')

            # 判定
            if dissipation_score >= 60:
                dissipation_type = 'MORNING_FOG'
                confidence = 'HIGH'
                message = 'Fog will dissipate by mid-morning. Kelp drying possible from 10:00 JST.'
            elif dissipation_score >= 40:
                dissipation_type = 'PARTIAL_DISSIPATION'
                confidence = 'MODERATE'
                message = 'Fog may partially dissipate by noon. Monitor conditions.'
            else:
                dissipation_type = 'ALL_DAY_FOG'
                confidence = 'HIGH'
                message = 'Fog will persist all day. Kelp drying not recommended.'

        # 記録
        forecast_entry = {
            'date': str(date),
            'fog_risk_index': float(morning_fog_risk),
            'relative_humidity_pct': float(morning_rh),
            'wind_speed_ms': float(morning_wind),
            'cloud_cover_fraction': float(morning_cloud),
            'fog_present': bool(fog_present),
            'dissipation_type': dissipation_type,
            'dissipation_score': int(dissipation_score) if fog_present else None,
            'confidence': confidence,
            'message': message,
            'factors': factors if fog_present else []
        }

        fog_dissipation_forecast.append(forecast_entry)

        # コンソール出力
        print(f"\n{str(date)[:10]}:")
        print(f"  Fog Risk: {morning_fog_risk:.2f}C | RH: {morning_rh:.1f}% | Wind: {morning_wind:.1f} m/s | Cloud: {morning_cloud*100:.0f}%")
        if fog_present:
            print(f"  Dissipation Score: {dissipation_score}/100")
            print(f"  => {dissipation_type} ({confidence} confidence)")
            print(f"  Factors: {', '.join(factors) if factors else 'None'}")
        print(f"  {message}")

    # 統計
    print(f"\n{'='*70}")
    print("DISSIPATION PATTERN STATISTICS")
    print(f"{'='*70}")

    fog_days = sum(1 for f in fog_dissipation_forecast if f['fog_present'])
    morning_fog_days = sum(1 for f in fog_dissipation_forecast if f['dissipation_type'] == 'MORNING_FOG')
    all_day_fog_days = sum(1 for f in fog_dissipation_forecast if f['dissipation_type'] == 'ALL_DAY_FOG')

    print(f"\nTotal days analyzed: {len(fog_dissipation_forecast)}")
    print(f"Fog days: {fog_days} ({fog_days/len(fog_dissipation_forecast)*100:.1f}%)")
    print(f"Morning fog (dissipates): {morning_fog_days} ({morning_fog_days/fog_days*100:.1f}% of fog days)" if fog_days > 0 else "Morning fog: N/A")
    print(f"All-day fog (persists): {all_day_fog_days} ({all_day_fog_days/fog_days*100:.1f}% of fog days)" if fog_days > 0 else "All-day fog: N/A")

    # 可視化
    print(f"\n{'='*70}")
    print("GENERATING VISUALIZATIONS")
    print(f"{'='*70}")

    fig, axes = plt.subplots(4, 1, figsize=(14, 12), sharex=True)

    days = np.arange(len(fog_dissipation_forecast))
    fog_risks = [f['fog_risk_index'] for f in fog_dissipation_forecast]
    wind_speeds = [f['wind_speed_ms'] for f in fog_dissipation_forecast]
    cloud_covers = [f['cloud_cover_fraction']*100 for f in fog_dissipation_forecast]
    rhs = [f['relative_humidity_pct'] for f in fog_dissipation_forecast]

    # 霧リスク指数
    ax1 = axes[0]
    colors = ['red' if f['dissipation_type'] == 'ALL_DAY_FOG' else
              'orange' if f['dissipation_type'] == 'PARTIAL_DISSIPATION' else
              'yellow' if f['dissipation_type'] == 'MORNING_FOG' else 'green'
              for f in fog_dissipation_forecast]
    ax1.bar(days, fog_risks, color=colors, alpha=0.7)
    ax1.axhline(2.0, color='red', linestyle='--', alpha=0.5, label='Fog risk threshold')
    ax1.set_ylabel('Fog Risk Index\\n(SST-Dewpoint, C)', fontsize=11)
    ax1.set_title('Fog Dissipation Prediction (14-day Analysis)', fontsize=14, fontweight='bold')
    ax1.legend(loc='upper right', fontsize=9)
    ax1.grid(True, alpha=0.3, axis='y')

    # 風速
    ax2 = axes[1]
    ax2.plot(days, wind_speeds, 'b-', linewidth=2)
    ax2.axhline(WIND_MIXING_THRESHOLD, color='green', linestyle='--', alpha=0.5,
                label=f'Mixing threshold ({WIND_MIXING_THRESHOLD} m/s)')
    ax2.set_ylabel('Wind Speed\\n(m/s)', fontsize=11)
    ax2.legend(loc='upper right', fontsize=9)
    ax2.grid(True, alpha=0.3)

    # 雲量
    ax3 = axes[2]
    ax3.fill_between(days, 0, cloud_covers, alpha=0.5, color='gray')
    ax3.axhline(CLOUD_CLEAR_THRESHOLD*100, color='orange', linestyle='--', alpha=0.5,
                label=f'Clear sky threshold ({CLOUD_CLEAR_THRESHOLD*100:.0f}%)')
    ax3.set_ylabel('Cloud Cover\\n(%)', fontsize=11)
    ax3.legend(loc='upper right', fontsize=9)
    ax3.grid(True, alpha=0.3)

    # 相対湿度
    ax4 = axes[3]
    ax4.plot(days, rhs, 'purple', linewidth=2)
    ax4.axhline(90, color='red', linestyle='--', alpha=0.5, label='High humidity threshold (90%)')
    ax4.set_ylabel('Relative\\nHumidity (%)', fontsize=11)
    ax4.set_xlabel('Days (most recent 14 days)', fontsize=11)
    ax4.legend(loc='upper right', fontsize=9)
    ax4.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig('fog_dissipation_analysis.png', dpi=150, bbox_inches='tight')
    print("  Saved: fog_dissipation_analysis.png")
    plt.close()

    # JSON保存
    output = {
        'analysis_date': datetime.now().isoformat(),
        'location': f"Kutsugata ({KUTSUGATA_LAT}N, {KUTSUGATA_LON}E)",
        'thresholds': {
            'wind_mixing_ms': WIND_MIXING_THRESHOLD,
            'cloud_clear_fraction': CLOUD_CLEAR_THRESHOLD,
            'temp_rise_C': TEMP_RISE_THRESHOLD
        },
        'forecasts': fog_dissipation_forecast,
        'statistics': {
            'total_days': len(fog_dissipation_forecast),
            'fog_days': fog_days,
            'morning_fog_days': morning_fog_days,
            'all_day_fog_days': all_day_fog_days,
            'fog_rate_pct': round(fog_days/len(fog_dissipation_forecast)*100, 1)
        }
    }

    with open('fog_dissipation_forecast.json', 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print("  Saved: fog_dissipation_forecast.json")

    print(f"\n{'='*70}")
    print("ANALYSIS COMPLETE")
    print(f"{'='*70}")

    return output

if __name__ == '__main__':
    analyze_fog_dissipation_pattern()
