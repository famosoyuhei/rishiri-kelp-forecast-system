#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
昆布干し連続可能時間の計算

実用的な判定基準:
1. 最低6時間の連続作業時間が必要
2. 時間帯別リスク評価（朝霧・午後の雨）
3. 作業可否の実用的判定
"""

import json
from datetime import datetime, timedelta

# 昆布干しに必要な最低時間（実務に基づく）
# 干し開始: 5-6時, 回収開始: 13-15時
MINIMUM_DRYING_HOURS = 8   # 最低8時間（5時→13時、6時→14時）
IDEAL_DRYING_HOURS = 10    # 理想10時間以上（余裕を持った作業）

# 作業可能時間帯（JST）- 月別で異なる
def get_work_hours(date_str):
    """月別の作業可能時間を取得（日照時間に基づく）"""
    month = int(date_str.split('-')[1])

    if month == 6:
        # 6月：4時台から明るい、夏至前後で最も日が長い
        return 4, 19  # 04:00-19:00 (15時間)
    elif month == 7:
        # 7月：5時台から明るい
        return 5, 19  # 05:00-19:00 (14時間)
    elif month == 8:
        # 8月：5時台から明るい
        return 5, 18  # 05:00-18:00 (13時間)
    else:
        # デフォルト
        return 6, 18  # 06:00-18:00 (12時間)

def calculate_viable_drying_hours():
    """連続作業可能時間の計算"""

    print("="*70)
    print("VIABLE CONTINUOUS DRYING HOURS ANALYSIS")
    print("="*70)

    # データ読み込み
    try:
        with open('integrated_ocean_forecast.json', 'r', encoding='utf-8') as f:
            ocean_forecast = json.load(f)

        with open('fog_dissipation_forecast.json', 'r', encoding='utf-8') as f:
            fog_forecast = json.load(f)

        print("\nForecast data loaded successfully")
    except FileNotFoundError as e:
        print(f"\nError: {e}")
        return

    # 最新7日間の予報を統合
    print(f"\n{'='*70}")
    print("7-DAY VIABLE DRYING HOURS FORECAST")
    print(f"{'='*70}")

    viable_forecast = []

    # 海洋予報から日付を取得
    for ocean_day in ocean_forecast['forecasts']:
        date = ocean_day['date']

        # 月別の作業可能時間を取得
        WORK_START_HOUR, WORK_END_HOUR = get_work_hours(date)

        # 霧予報から同じ日付を検索
        fog_day = next((f for f in fog_forecast['forecasts'] if f['date'] == date), None)

        if not fog_day:
            continue

        # 時間帯別リスク評価
        # 早朝-朝（start-10時）: 霧リスク
        # 昼（10-14時）: 低リスク
        # 午後（14-end時）: 降水リスク

        # 1. 朝霧による制約
        if fog_day['dissipation_type'] == 'MORNING_FOG':
            morning_blocked_hours = 10 - WORK_START_HOUR  # start-10:00
            morning_available = False
            fog_clear_time = "10:00"
        elif fog_day['dissipation_type'] == 'ALL_DAY_FOG':
            morning_blocked_hours = WORK_END_HOUR - WORK_START_HOUR  # 全時間帯
            morning_available = False
            fog_clear_time = "Never"
        else:
            morning_blocked_hours = 0
            morning_available = True
            fog_clear_time = f"{WORK_START_HOUR:02d}:00"

        # 2. 降水による制約
        precip_risk = ocean_day['risk_factors']['precipitation']
        sst_rain_risk = ocean_day['risk_factors']['sst_rain_potential']

        if precip_risk == 'CRITICAL' or precip_risk == 'HIGH':
            # 大雨リスク → 午後全ブロック
            afternoon_blocked_hours = WORK_END_HOUR - 14  # 14:00-end
            afternoon_available = False
        elif sst_rain_risk == 'CRITICAL':
            # SST高温 → 夕方ブロック（夕立リスク）
            afternoon_blocked_hours = WORK_END_HOUR - 16  # 16:00-end
            afternoon_available = True  # 14-16時は可能
        else:
            afternoon_blocked_hours = 0
            afternoon_available = True

        # 3. 連続作業可能時間の計算
        total_work_hours = WORK_END_HOUR - WORK_START_HOUR
        blocked_hours = morning_blocked_hours + afternoon_blocked_hours
        available_hours = total_work_hours - blocked_hours

        # 4. 作業可能時間帯の特定
        if morning_blocked_hours == 0 and afternoon_blocked_hours == 0:
            work_window = f"{WORK_START_HOUR:02d}:00-{WORK_END_HOUR:02d}:00"
            continuous_hours = total_work_hours
        elif morning_blocked_hours > 0 and afternoon_blocked_hours == 0:
            work_window = f"{fog_clear_time}-{WORK_END_HOUR:02d}:00"
            continuous_hours = WORK_END_HOUR - 10  # 10:00以降
        elif morning_blocked_hours == 0 and afternoon_blocked_hours > 0:
            work_window = f"{WORK_START_HOUR:02d}:00-14:00"
            continuous_hours = 14 - WORK_START_HOUR  # 14:00まで
        elif morning_blocked_hours > 0 and afternoon_blocked_hours > 0:
            work_window = "10:00-14:00"
            continuous_hours = 4
        else:
            work_window = "N/A"
            continuous_hours = 0

        # 5. 実用的な判定
        if continuous_hours >= IDEAL_DRYING_HOURS:
            viability = 'EXCELLENT'
            recommendation = 'Ideal conditions - 10+ hours for full drying with margin'
            action = '[OK] Full drying recommended (05:00-15:00+ possible)'
            color = 'green'
        elif continuous_hours >= MINIMUM_DRYING_HOURS:
            viability = 'ACCEPTABLE'
            recommendation = 'Minimum viable - 8-9 hours for basic drying'
            action = '[CAUTION] Tight schedule (06:00-14:00 or 05:00-13:00)'
            color = 'yellow'
        elif continuous_hours >= 6:
            viability = 'INSUFFICIENT'
            recommendation = 'NOT enough time for complete outdoor drying'
            action = '[WARNING] Partial drying only - indoor finish required'
            color = 'orange'
        else:
            viability = 'UNSUITABLE'
            recommendation = 'No viable outdoor drying time'
            action = '[UNSUITABLE] Do not attempt outdoor drying'
            color = 'red'

        # 記録
        day_forecast = {
            'date': date,
            'fog_clear_time': fog_clear_time,
            'morning_available': morning_available,
            'afternoon_available': afternoon_available,
            'work_window': work_window,
            'continuous_hours': continuous_hours,
            'available_hours': available_hours,
            'viability': viability,
            'recommendation': recommendation,
            'action': action,
            'color': color,
            'risk_score': ocean_day['risk_score'],
            'fog_type': fog_day['dissipation_type'],
            'precipitation_risk': precip_risk
        }

        viable_forecast.append(day_forecast)

        # コンソール出力
        print(f"\n{date}:")
        print(f"  Fog clears: {fog_clear_time} | Rain risk: {precip_risk}")
        print(f"  Work window: {work_window}")
        print(f"  Continuous hours: {continuous_hours}h (Available: {available_hours}h)")
        print(f"  Viability: {viability}")
        print(f"  {action}")
        print(f"  {recommendation}")

    # 週間サマリー
    print(f"\n{'='*70}")
    print("WEEKLY VIABILITY SUMMARY")
    print(f"{'='*70}")

    excellent_days = sum(1 for f in viable_forecast if f['viability'] == 'EXCELLENT')
    acceptable_days = sum(1 for f in viable_forecast if f['viability'] == 'ACCEPTABLE')
    insufficient_days = sum(1 for f in viable_forecast if f['viability'] == 'INSUFFICIENT')
    unsuitable_days = sum(1 for f in viable_forecast if f['viability'] == 'UNSUITABLE')

    total_days = len(viable_forecast)

    print(f"\nTotal days: {total_days}")
    print(f"  EXCELLENT (>={IDEAL_DRYING_HOURS}h): {excellent_days} days ({excellent_days/total_days*100:.1f}%)")
    print(f"  ACCEPTABLE ({MINIMUM_DRYING_HOURS}-{IDEAL_DRYING_HOURS-1}h): {acceptable_days} days ({acceptable_days/total_days*100:.1f}%)")
    print(f"  INSUFFICIENT (6-{MINIMUM_DRYING_HOURS-1}h): {insufficient_days} days ({insufficient_days/total_days*100:.1f}%)")
    print(f"  UNSUITABLE (<6h): {unsuitable_days} days ({unsuitable_days/total_days*100:.1f}%)")

    workable_days = excellent_days + acceptable_days
    print(f"\n>>> Workable days this week: {workable_days}/{total_days} ({workable_days/total_days*100:.1f}%)")

    if workable_days == 0:
        print("\n[ALERT] No suitable drying days this week!")
        print("        Consider indoor drying or wait for better conditions.")
    elif workable_days <= 2:
        print("\n[WARNING] Limited drying opportunities this week.")
        print("          Plan carefully and monitor conditions closely.")

    # 経済的影響評価
    indoor_drying_days = insufficient_days + unsuitable_days
    if indoor_drying_days > 0:
        print(f"\n{'='*70}")
        print("ECONOMIC IMPACT")
        print(f"{'='*70}")
        print(f"\nIndoor drying required: {indoor_drying_days} days")
        print(f"  Estimated additional cost: {indoor_drying_days * 50000:.0f} JPY")
        print(f"  (Assuming 50,000 JPY/day for indoor drying facility)")

    # JSON保存
    output = {
        'analysis_date': datetime.now().isoformat(),
        'minimum_drying_hours': MINIMUM_DRYING_HOURS,
        'ideal_drying_hours': IDEAL_DRYING_HOURS,
        'work_hours': f"{WORK_START_HOUR:02d}:00-{WORK_END_HOUR:02d}:00",
        'forecasts': viable_forecast,
        'summary': {
            'total_days': total_days,
            'excellent_days': excellent_days,
            'acceptable_days': acceptable_days,
            'insufficient_days': insufficient_days,
            'unsuitable_days': unsuitable_days,
            'workable_days': workable_days,
            'workable_rate_pct': round(workable_days/total_days*100, 1)
        }
    }

    with open('viable_drying_hours_forecast.json', 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\nSaved: viable_drying_hours_forecast.json")

    print(f"\n{'='*70}")
    print("ANALYSIS COMPLETE")
    print(f"{'='*70}")

    return output

if __name__ == '__main__':
    calculate_viable_drying_hours()
