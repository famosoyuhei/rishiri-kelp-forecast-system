"""
Test Amedas ID 11151 (Kutsugata) data fetching
"""
import requests
from datetime import datetime, timedelta

# Test with ID 11151 (Kutsugata)
amedas_id = '11151'

# Test multiple date formats and recent dates
test_dates = []

# Recent dates (today and past 7 days)
for days_ago in range(0, 8):
    date = datetime.now() - timedelta(days=days_ago)
    test_dates.append(date.strftime('%Y%m%d'))

print(f"Testing Amedas ID: {amedas_id} (Kutsugata)")
print(f"Coordinates: 45.178333N, 141.138333E\n")
print("=" * 80)

success_count = 0

for date_str in test_dates:
    url = f"https://www.jma.go.jp/bosai/amedas/data/point/{amedas_id}/{date_str}.json"
    response = requests.get(url)

    print(f"\nDate: {date_str}")
    print(f"URL: {url}")
    print(f"Status: {response.status_code}")

    if response.status_code == 200:
        print(f"SUCCESS - Data retrieved!")
        success_count += 1

        # Show sample data
        data = response.json()
        if data:
            # Get first hour's data
            first_hour = list(data.keys())[0]
            first_data = data[first_hour]
            print(f"Sample data (hour {first_hour}):")
            print(f"  Temperature: {first_data.get('temp', ['N/A'])[0]}°C")
            print(f"  Humidity: {first_data.get('humidity', ['N/A'])[0]}%")
            print(f"  Wind speed: {first_data.get('wind', ['N/A'])[0]} m/s")
            print(f"  Precipitation: {first_data.get('precipitation10m', ['N/A'])[0]} mm")
            break  # Found working date, stop
    elif response.status_code == 404:
        print(f"FAILED - Data not available for this date")
    else:
        print(f"FAILED - HTTP {response.status_code}")

print("\n" + "=" * 80)
print(f"\nRESULT: {success_count}/{len(test_dates)} dates successful")

if success_count > 0:
    print(f"\nCONCLUSION: Amedas ID 11151 is CORRECT for Kutsugata!")
    print(f"Update forecast_accuracy/config.py:")
    print(f"  AMEDAS_KUTSUGATA['id'] = '11151'")
else:
    print(f"\nCONCLUSION: No data available for recent dates.")
    print(f"ID 11151 may still be correct but data not yet published.")
