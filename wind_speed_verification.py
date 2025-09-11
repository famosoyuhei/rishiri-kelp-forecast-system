#!/usr/bin/env python3
"""
Wind Speed Verification System
Verify the unusually high wind speed readings in historical data
"""

import requests
import json
import pandas as pd
from datetime import datetime

class WindSpeedVerifier:
    """風速データ検証システム"""
    
    def __init__(self):
        self.locations = {
            "Oshidomari": {"lat": 45.241667, "lon": 141.230833},
            "Kutsugata": {"lat": 45.118889, "lon": 141.176389}
        }
        
        # 参考：気象学的風速スケール
        self.wind_scale = {
            0: "Calm (0-0.2 m/s)",
            1: "Light air (0.3-1.5 m/s)",
            2: "Light breeze (1.6-3.3 m/s)",
            3: "Gentle breeze (3.4-5.4 m/s)",
            4: "Moderate breeze (5.5-7.9 m/s)",
            5: "Fresh breeze (8.0-10.7 m/s)",
            6: "Strong breeze (10.8-13.8 m/s)",
            7: "Near gale (13.9-17.1 m/s)",
            8: "Gale (17.2-20.7 m/s)",
            9: "Strong gale (20.8-24.4 m/s)",
            10: "Storm (24.5-28.4 m/s)",
            11: "Violent storm (28.5-32.6 m/s)",
            12: "Hurricane (32.7+ m/s)"
        }
    
    def get_wind_scale_description(self, wind_speed):
        """風速から風力階級を判定"""
        if wind_speed <= 0.2:
            return 0, self.wind_scale[0]
        elif wind_speed <= 1.5:
            return 1, self.wind_scale[1]
        elif wind_speed <= 3.3:
            return 2, self.wind_scale[2]
        elif wind_speed <= 5.4:
            return 3, self.wind_scale[3]
        elif wind_speed <= 7.9:
            return 4, self.wind_scale[4]
        elif wind_speed <= 10.7:
            return 5, self.wind_scale[5]
        elif wind_speed <= 13.8:
            return 6, self.wind_scale[6]
        elif wind_speed <= 17.1:
            return 7, self.wind_scale[7]
        elif wind_speed <= 20.7:
            return 8, self.wind_scale[8]
        elif wind_speed <= 24.4:
            return 9, self.wind_scale[9]
        elif wind_speed <= 28.4:
            return 10, self.wind_scale[10]
        elif wind_speed <= 32.6:
            return 11, self.wind_scale[11]
        else:
            return 12, self.wind_scale[12]
    
    def verify_suspicious_dates(self):
        """疑わしい風速値を記録した日付を検証"""
        
        # 異常に高い風速を記録した日付
        suspicious_dates = [
            "2025-07-25",  # 27.8 m/s
            "2025-07-15",  # 24.1 m/s
            "2025-07-12",  # 27.4 m/s
            "2025-06-22",  # 34.7 m/s
            "2025-06-23",  # 29.0 m/s
            "2025-06-25",  # 31.2 m/s
            "2025-06-29"   # 30.6 m/s
        ]
        
        print("=== Wind Speed Verification ===")
        print("Checking suspicious high wind speed readings")
        print()
        
        verification_results = []
        
        for date in suspicious_dates:
            print(f"Verifying date: {date}")
            
            # 両地点の詳細データを取得
            for location_name, coords in self.locations.items():
                result = self.get_detailed_weather_verification(date, coords, location_name)
                if result:
                    verification_results.append(result)
            print()
        
        return self.analyze_wind_verification(verification_results)
    
    def get_detailed_weather_verification(self, date, coords, location_name):
        """詳細な気象データ検証"""
        
        params = {
            "latitude": coords["lat"],
            "longitude": coords["lon"],
            "start_date": date,
            "end_date": date,
            "hourly": "temperature_2m,relative_humidity_2m,wind_speed_10m,wind_direction_10m,wind_gusts_10m,weather_code",
            "timezone": "Asia/Tokyo"
        }
        
        try:
            response = requests.get("https://api.open-meteo.com/v1/forecast", params=params, timeout=15)
            
            if response.status_code == 200:
                data = response.json()
                hourly = data["hourly"]
                
                # 作業時間（4-16時）の分析
                work_slice = slice(4, 17)
                
                # 風速統計
                wind_speeds = hourly["wind_speed_10m"][work_slice]
                wind_gusts = hourly.get("wind_gusts_10m", [0]*24)[work_slice] if "wind_gusts_10m" in hourly else None
                weather_codes = hourly["weather_code"][work_slice]
                
                wind_stats = {
                    "average": sum(wind_speeds) / len(wind_speeds),
                    "maximum": max(wind_speeds),
                    "minimum": min(wind_speeds),
                    "median": sorted(wind_speeds)[len(wind_speeds)//2]
                }
                
                # 突風データがある場合
                gust_stats = None
                if wind_gusts:
                    gust_stats = {
                        "average": sum(wind_gusts) / len(wind_gusts),
                        "maximum": max(wind_gusts),
                        "minimum": min(wind_gusts)
                    }
                
                # 気象コード分析（悪天候の確認）
                severe_weather_codes = [51, 53, 55, 61, 63, 65, 71, 73, 75, 77, 80, 81, 82, 95, 96, 99]
                severe_weather_hours = sum(1 for code in weather_codes if code in severe_weather_codes)
                
                # 風力階級判定
                avg_scale, avg_description = self.get_wind_scale_description(wind_stats["average"])
                max_scale, max_description = self.get_wind_scale_description(wind_stats["maximum"])
                
                print(f"  {location_name}:")
                print(f"    Average wind: {wind_stats['average']:.1f} m/s ({avg_description})")
                print(f"    Maximum wind: {wind_stats['maximum']:.1f} m/s ({max_description})")
                print(f"    Wind range: {wind_stats['minimum']:.1f} - {wind_stats['maximum']:.1f} m/s")
                
                if gust_stats:
                    print(f"    Max gust: {gust_stats['maximum']:.1f} m/s")
                
                print(f"    Severe weather hours: {severe_weather_hours}/13")
                
                # 異常判定
                is_abnormal = wind_stats["average"] > 25.0  # 25m/s以上は異常
                is_extreme = wind_stats["maximum"] > 30.0   # 30m/s以上は極異常
                
                if is_extreme:
                    print(f"    ⚠️  EXTREME: Hurricane-level wind speeds detected!")
                elif is_abnormal:
                    print(f"    ⚠️  ABNORMAL: Storm-level wind speeds")
                else:
                    print(f"    ✓ Normal wind range")
                
                return {
                    "date": date,
                    "location": location_name,
                    "coordinates": coords,
                    "wind_stats": wind_stats,
                    "gust_stats": gust_stats,
                    "severe_weather_hours": severe_weather_hours,
                    "wind_scale_avg": avg_scale,
                    "wind_scale_max": max_scale,
                    "is_abnormal": is_abnormal,
                    "is_extreme": is_extreme,
                    "hourly_winds": wind_speeds,
                    "weather_codes": weather_codes
                }
                
            else:
                print(f"  {location_name}: API error {response.status_code}")
                return None
                
        except Exception as e:
            print(f"  {location_name}: Error - {e}")
            return None
    
    def analyze_wind_verification(self, results):
        """風速検証結果の分析"""
        
        print("=" * 60)
        print("WIND SPEED VERIFICATION ANALYSIS")
        print("=" * 60)
        
        if not results:
            print("No verification data available")
            return None
        
        # 統計分析
        all_averages = [r["wind_stats"]["average"] for r in results]
        all_maximums = [r["wind_stats"]["maximum"] for r in results]
        
        abnormal_cases = [r for r in results if r["is_abnormal"]]
        extreme_cases = [r for r in results if r["is_extreme"]]
        
        print(f"Total verification cases: {len(results)}")
        print(f"Abnormal wind cases (>25 m/s avg): {len(abnormal_cases)}")
        print(f"Extreme wind cases (>30 m/s max): {len(extreme_cases)}")
        print()
        
        print(f"Wind speed statistics:")
        print(f"  Average wind range: {min(all_averages):.1f} - {max(all_averages):.1f} m/s")
        print(f"  Maximum wind range: {min(all_maximums):.1f} - {max(all_maximums):.1f} m/s")
        print(f"  Overall average: {sum(all_averages)/len(all_averages):.1f} m/s")
        print()
        
        # 風力階級分布
        scale_distribution = {}
        for result in results:
            scale = result["wind_scale_avg"]
            scale_distribution[scale] = scale_distribution.get(scale, 0) + 1
        
        print("Wind scale distribution (by average wind speed):")
        for scale in sorted(scale_distribution.keys()):
            count = scale_distribution[scale]
            description = self.wind_scale[scale]
            print(f"  Scale {scale}: {count} cases - {description}")
        
        # 異常ケースの詳細分析
        if extreme_cases:
            print(f"\nEXTREME CASES ANALYSIS:")
            for case in extreme_cases:
                print(f"  {case['date']} at {case['location']}:")
                print(f"    Average: {case['wind_stats']['average']:.1f} m/s")
                print(f"    Maximum: {case['wind_stats']['maximum']:.1f} m/s")
                print(f"    Severe weather hours: {case['severe_weather_hours']}/13")
        
        # 実用性への影響評価
        print(f"\nIMPLICATIONS FOR KELP DRYING:")
        
        reasonable_cases = [r for r in results if not r["is_abnormal"]]
        if reasonable_cases:
            reasonable_averages = [r["wind_stats"]["average"] for r in reasonable_cases]
            print(f"  Normal wind conditions ({len(reasonable_cases)} cases):")
            print(f"    Average wind: {sum(reasonable_averages)/len(reasonable_averages):.1f} m/s")
            print(f"    Range: {min(reasonable_averages):.1f} - {max(reasonable_averages):.1f} m/s")
        
        if abnormal_cases:
            abnormal_averages = [r["wind_stats"]["average"] for r in abnormal_cases]
            print(f"  Storm conditions ({len(abnormal_cases)} cases):")
            print(f"    Average wind: {sum(abnormal_averages)/len(abnormal_averages):.1f} m/s")
            print(f"    These conditions likely prevent kelp drying operations entirely")
        
        # 推奨修正
        print(f"\nRECOMMENDATIONS:")
        if len(abnormal_cases) > len(results) * 0.3:
            print("  ⚠️  High frequency of extreme wind conditions detected")
            print("  - Review API data source reliability")
            print("  - Consider filtering out storm days from normal analysis")
            print("  - Separate model for normal vs extreme weather conditions")
        
        corrected_average = sum(r["wind_stats"]["average"] for r in reasonable_cases) / len(reasonable_cases) if reasonable_cases else 0
        print(f"  - Corrected average wind speed (excluding storms): {corrected_average:.1f} m/s")
        
        return {
            "total_cases": len(results),
            "abnormal_cases": len(abnormal_cases),
            "extreme_cases": len(extreme_cases),
            "overall_average": sum(all_averages)/len(all_averages),
            "corrected_average": corrected_average,
            "wind_scale_distribution": scale_distribution,
            "detailed_results": results
        }

def main():
    """メイン実行"""
    verifier = WindSpeedVerifier()
    
    # 疑わしい風速データの検証
    results = verifier.verify_suspicious_dates()
    
    if results:
        # 結果をJSONで保存
        output_file = "wind_speed_verification_results.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        
        print(f"\nDetailed verification results saved to: {output_file}")

if __name__ == "__main__":
    main()