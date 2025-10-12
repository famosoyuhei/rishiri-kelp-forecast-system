#!/usr/bin/env python3
"""
Open-Meteo APIの空間解像度を検証

仮説: 下層の偏差が小さいのは、APIの格子解像度が粗く、
      利尻島の全干場が同じ格子点に丸められているため
"""
import requests
import json

def test_api_resolution():
    """
    非常に近い3地点でエマグラムを取得し、
    同じ値が返されるか確認
    """

    # 利尻島内の3地点（約5km離れた地点）
    test_points = [
        {"name": "鴛泊（北部）", "lat": 45.242, "lon": 141.242},
        {"name": "沓形（西部）", "lat": 45.163, "lon": 141.143},
        {"name": "仙法志（南部）", "lat": 45.118, "lon": 141.226}
    ]

    # 距離計算
    from math import radians, cos, sin, asin, sqrt

    def haversine(lat1, lon1, lat2, lon2):
        """2点間の距離を計算（km）"""
        R = 6371  # 地球の半径（km）

        lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
        dlat = lat2 - lat1
        dlon = lon2 - lon1

        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
        c = 2 * asin(sqrt(a))

        return R * c

    print("=" * 80)
    print("Open-Meteo API 空間解像度検証")
    print("=" * 80)
    print()

    # 地点間距離を表示
    print("【検証地点】")
    for i, p in enumerate(test_points):
        print(f"{i+1}. {p['name']}: ({p['lat']:.3f}, {p['lon']:.3f})")

    print("\n【地点間距離】")
    for i in range(len(test_points)):
        for j in range(i+1, len(test_points)):
            p1 = test_points[i]
            p2 = test_points[j]
            dist = haversine(p1['lat'], p1['lon'], p2['lat'], p2['lon'])
            print(f"{p1['name']} - {p2['name']}: {dist:.2f} km")

    print("\n" + "=" * 80)
    print("エマグラムデータ取得中...")
    print("=" * 80)
    print()

    # 各地点のデータを取得
    results = []

    for point in test_points:
        url = f"https://rishiri-kelp-forecast-system.onrender.com/api/emagram"
        params = {
            'lat': point['lat'],
            'lon': point['lon'],
            'time': 0
        }

        try:
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()

            if data.get('status') == 'success':
                results.append({
                    'name': point['name'],
                    'lat': point['lat'],
                    'lon': point['lon'],
                    'data': data['data']
                })
                print(f"✓ {point['name']}: 取得成功")
            else:
                print(f"✗ {point['name']}: {data.get('message')}")

        except Exception as e:
            print(f"✗ {point['name']}: エラー - {e}")

    if len(results) < 2:
        print("\n少なくとも2地点のデータが必要です")
        return

    # 比較分析
    print("\n" + "=" * 80)
    print("【気圧面ごとの地点間差異】")
    print("=" * 80)
    print()

    pressure_levels = results[0]['data']['pressure']

    print(f"{'気圧':>8} {'高度':>8} | ", end="")
    for r in results:
        print(f"{r['name']:>12} | ", end="")
    print("最大差")
    print("-" * 80)

    for p_idx, pressure in enumerate(pressure_levels):
        temps = []
        heights = []

        for r in results:
            temps.append(r['data']['temperature'][p_idx])
            heights.append(r['data']['height'][p_idx])

        temp_range = max(temps) - min(temps)
        height_mean = sum(heights) / len(heights)

        print(f"{pressure:>8.0f} {height_mean:>8.0f} | ", end="")
        for temp in temps:
            print(f"{temp:>12.2f} | ", end="")
        print(f"{temp_range:>6.2f}°C")

    # 結論
    print("\n" + "=" * 80)
    print("【結論】")
    print("=" * 80)
    print()

    # 下層（1000hPa）の差をチェック
    temps_1000 = [r['data']['temperature'][0] for r in results]
    diff_1000 = max(temps_1000) - min(temps_1000)

    # 上層（500hPa）の差をチェック
    idx_500 = pressure_levels.index(500)
    temps_500 = [r['data']['temperature'][idx_500] for r in results]
    diff_500 = max(temps_500) - min(temps_500)

    print(f"1000hPa（地上付近）の最大気温差: {diff_1000:.2f}°C")
    print(f"500hPa（上層）の最大気温差: {diff_500:.2f}°C")
    print()

    if diff_1000 < 0.5 and diff_500 < 0.5:
        print("✓ 仮説支持: API解像度が粗く、利尻島内の地点間差を解像できていない")
        print("  → 全地点がほぼ同じ格子点の値を返している可能性が高い")
    elif diff_1000 > 1.0:
        print("✗ 仮説不支持: 下層で有意な地点間差が検出された")
        print("  → APIは地点間の違いを解像している")
    else:
        print("△ 不明: 中間的な結果")

    print()
    print("【参考】気象学的に期待される差:")
    print("  - 地上付近: 海岸vs内陸で1-3°C")
    print("  - 地形効果（標高100m差）: 約0.6°C")
    print("  - 上層（500hPa）: 15km四方では0.1°C以下であるべき")
    print()

if __name__ == '__main__':
    test_api_resolution()
