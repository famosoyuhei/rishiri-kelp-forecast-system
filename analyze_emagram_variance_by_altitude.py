#!/usr/bin/env python3
"""
全干場のエマグラムデータを取得し、気圧面ごとの地点間偏差を分析

仮説: 下層ほど地形的要素による偏差が大きく、上層ほど一様
"""
import requests
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import json
from datetime import datetime
import time

# 設定
API_BASE_URL = "https://rishiri-kelp-forecast-system.onrender.com"
# API_BASE_URL = "http://localhost:5000"  # ローカルテスト用

def load_spots():
    """干場データを読み込み"""
    spots_df = pd.read_csv('hoshiba_spots.csv')
    print(f"Total spots loaded: {len(spots_df)}")
    return spots_df

def fetch_emagram_for_spot(lat, lon, time_offset=0, retries=3):
    """指定干場のエマグラムデータを取得"""
    url = f"{API_BASE_URL}/api/emagram?lat={lat}&lon={lon}&time={time_offset}"

    for attempt in range(retries):
        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            data = response.json()

            if data.get('status') == 'success':
                return data['data']
            else:
                print(f"Error for lat={lat}, lon={lon}: {data.get('message')}")
                return None

        except requests.exceptions.RequestException as e:
            print(f"Request failed (attempt {attempt+1}/{retries}): {e}")
            if attempt < retries - 1:
                time.sleep(2)
            else:
                return None

def analyze_variance_by_pressure_level(spots_df, time_offset=0, sample_size=None):
    """
    全干場のエマグラムを取得し、気圧面ごとの偏差を分析

    Args:
        spots_df: 干場データフレーム
        time_offset: 予報時刻オフセット（時間）
        sample_size: サンプル数制限（None=全干場）
    """
    print(f"\n{'='*60}")
    print(f"エマグラム地点間偏差分析（時刻オフセット: {time_offset}h）")
    print(f"{'='*60}\n")

    # サンプリング
    if sample_size and sample_size < len(spots_df):
        spots_sample = spots_df.sample(n=sample_size, random_state=42)
        print(f"Sampling {sample_size} spots from {len(spots_df)} total spots")
    else:
        spots_sample = spots_df
        print(f"Analyzing all {len(spots_df)} spots")

    # 各干場のデータを収集
    emagram_data = []

    for idx, row in spots_sample.iterrows():
        spot_name = row['name']
        lat = row['lat']
        lon = row['lon']

        print(f"Fetching {idx+1}/{len(spots_sample)}: {spot_name} ({lat:.4f}, {lon:.4f})")

        data = fetch_emagram_for_spot(lat, lon, time_offset)

        if data:
            emagram_data.append({
                'spot_name': spot_name,
                'lat': lat,
                'lon': lon,
                'pressure': data['pressure'],
                'temperature': data['temperature'],
                'dewpoint': data['dewpoint'],
                'height': data['height'],
                'time': data.get('time')
            })

        # API負荷軽減のため少し待機
        time.sleep(0.5)

    print(f"\n✓ Successfully fetched data for {len(emagram_data)} spots\n")

    if len(emagram_data) == 0:
        print("No data collected. Aborting analysis.")
        return None

    # 気圧面ごとの統計を計算
    pressure_levels = emagram_data[0]['pressure']  # 全地点で共通

    stats_by_pressure = []

    for p_idx, pressure in enumerate(pressure_levels):
        temps_at_p = []
        dewpoints_at_p = []
        heights_at_p = []

        for spot_data in emagram_data:
            if p_idx < len(spot_data['temperature']):
                temps_at_p.append(spot_data['temperature'][p_idx])
                dewpoints_at_p.append(spot_data['dewpoint'][p_idx])
                heights_at_p.append(spot_data['height'][p_idx])

        # 統計量を計算
        stats_by_pressure.append({
            'pressure': pressure,
            'height_mean': np.mean(heights_at_p),
            'temp_mean': np.mean(temps_at_p),
            'temp_std': np.std(temps_at_p),
            'temp_range': np.max(temps_at_p) - np.min(temps_at_p),
            'temp_min': np.min(temps_at_p),
            'temp_max': np.max(temps_at_p),
            'dewpoint_mean': np.mean(dewpoints_at_p),
            'dewpoint_std': np.std(dewpoints_at_p),
            'dewpoint_range': np.max(dewpoints_at_p) - np.min(dewpoints_at_p),
            'n_samples': len(temps_at_p)
        })

    stats_df = pd.DataFrame(stats_by_pressure)

    # 結果を表示
    print(f"\n{'='*80}")
    print("気圧面ごとの気温偏差分析")
    print(f"{'='*80}")
    print(f"{'気圧':>8} {'高度(m)':>8} {'気温平均':>9} {'標準偏差':>9} {'範囲':>9} {'最小値':>9} {'最大値':>9}")
    print(f"{'-'*80}")

    for _, row in stats_df.iterrows():
        print(f"{row['pressure']:>8.0f} {row['height_mean']:>8.0f} "
              f"{row['temp_mean']:>9.2f} {row['temp_std']:>9.3f} "
              f"{row['temp_range']:>9.2f} {row['temp_min']:>9.2f} {row['temp_max']:>9.2f}")

    print(f"\n{'='*80}")
    print("仮説検証: 下層ほど偏差が大きく、上層ほど一様か？")
    print(f"{'='*80}\n")

    # 下層（1000-850hPa）と上層（500-200hPa）で比較
    lower_levels = stats_df[stats_df['pressure'] >= 850]
    upper_levels = stats_df[stats_df['pressure'] <= 500]

    lower_std_mean = lower_levels['temp_std'].mean()
    upper_std_mean = upper_levels['temp_std'].mean()
    lower_range_mean = lower_levels['temp_range'].mean()
    upper_range_mean = upper_levels['temp_range'].mean()

    print(f"下層（≥850hPa）:")
    print(f"  平均標準偏差: {lower_std_mean:.3f}°C")
    print(f"  平均範囲: {lower_range_mean:.2f}°C")
    print(f"\n上層（≤500hPa）:")
    print(f"  平均標準偏差: {upper_std_mean:.3f}°C")
    print(f"  平均範囲: {upper_range_mean:.2f}°C")

    ratio_std = lower_std_mean / upper_std_mean if upper_std_mean > 0 else float('inf')
    ratio_range = lower_range_mean / upper_range_mean if upper_range_mean > 0 else float('inf')

    print(f"\n偏差比（下層/上層）:")
    print(f"  標準偏差比: {ratio_std:.2f}倍")
    print(f"  範囲比: {ratio_range:.2f}倍")

    if ratio_std > 1.5 and ratio_range > 1.5:
        print(f"\n✓ 仮説支持: 下層の偏差は上層の{ratio_std:.1f}倍で、地形的影響が顕著")
    elif ratio_std > 1.0:
        print(f"\n△ 仮説部分支持: 下層の偏差がやや大きい（{ratio_std:.1f}倍）")
    else:
        print(f"\n✗ 仮説不支持: 下層と上層で偏差に有意差なし")

    # 可視化
    fig, axes = plt.subplots(1, 2, figsize=(14, 8))

    # 左: 標準偏差の鉛直プロファイル
    ax1 = axes[0]
    ax1.plot(stats_df['temp_std'], stats_df['pressure'], 'o-', color='#dc3545', linewidth=2, markersize=6)
    ax1.set_xlabel('気温の標準偏差 (°C)', fontsize=12, weight='bold')
    ax1.set_ylabel('気圧 (hPa)', fontsize=12, weight='bold')
    ax1.set_title('気圧面ごとの気温標準偏差\n（全干場間のばらつき）', fontsize=13, weight='bold')
    ax1.invert_yaxis()
    ax1.grid(True, alpha=0.3)
    ax1.axhline(850, color='gray', linestyle='--', alpha=0.5, label='850hPa（下層境界）')
    ax1.axhline(500, color='blue', linestyle='--', alpha=0.5, label='500hPa（上層境界）')
    ax1.legend()

    # 右: 気温範囲の鉛直プロファイル
    ax2 = axes[1]
    ax2.plot(stats_df['temp_range'], stats_df['pressure'], 'o-', color='#007bff', linewidth=2, markersize=6)
    ax2.set_xlabel('気温の範囲 (最大-最小, °C)', fontsize=12, weight='bold')
    ax2.set_ylabel('気圧 (hPa)', fontsize=12, weight='bold')
    ax2.set_title('気圧面ごとの気温範囲\n（全干場間の最大差）', fontsize=13, weight='bold')
    ax2.invert_yaxis()
    ax2.grid(True, alpha=0.3)
    ax2.axhline(850, color='gray', linestyle='--', alpha=0.5, label='850hPa（下層境界）')
    ax2.axhline(500, color='blue', linestyle='--', alpha=0.5, label='500hPa（上層境界）')
    ax2.legend()

    plt.tight_layout()

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_file = f'emagram_variance_by_altitude_{timestamp}.png'
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    print(f"\n✓ グラフを保存: {output_file}")

    # 結果をJSONで保存
    result = {
        'timestamp': datetime.now().isoformat(),
        'time_offset_hours': time_offset,
        'n_spots': len(emagram_data),
        'analysis': {
            'lower_atmosphere_std_mean': float(lower_std_mean),
            'upper_atmosphere_std_mean': float(upper_std_mean),
            'lower_atmosphere_range_mean': float(lower_range_mean),
            'upper_atmosphere_range_mean': float(upper_range_mean),
            'std_ratio_lower_to_upper': float(ratio_std),
            'range_ratio_lower_to_upper': float(ratio_range),
            'hypothesis_supported': ratio_std > 1.5 and ratio_range > 1.5
        },
        'stats_by_pressure': stats_df.to_dict('records')
    }

    json_file = f'emagram_variance_analysis_{timestamp}.json'
    with open(json_file, 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    print(f"✓ 結果を保存: {json_file}\n")

    return stats_df, result

if __name__ == '__main__':
    # 干場データを読み込み
    spots_df = load_spots()

    # 全干場を分析（sample_size=Noneで全干場、sample_size=50で50地点サンプリング）
    # API負荷を考慮して、最初は50地点でテスト
    print("\n【分析開始】")
    print("注意: 331地点全てを取得すると時間がかかります（約3分）")
    print("最初は50地点でテストすることを推奨\n")

    sample_size = 20  # 全干場の場合はNoneに変更（API負荷考慮）

    stats_df, result = analyze_variance_by_pressure_level(
        spots_df,
        time_offset=0,  # 現在時刻
        sample_size=sample_size
    )

    print("\n分析完了！")
