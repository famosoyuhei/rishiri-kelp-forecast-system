"""
Test script for Amedas data fetcher
"""

import sys
from datetime import date, timedelta
from amedas_data_fetcher import fetch_amedas_data, calculate_daily_statistics
from config import AMEDAS_KUTSUGATA

# Test with a recent date (yesterday)
test_date = date.today() - timedelta(days=1)
print(f"Testing Amedas data fetch for: {test_date}")
print(f"Amedas ID: {AMEDAS_KUTSUGATA['id']}")
print(f"Location: Kutsugata")

# Fetch Amedas data
print("\nFetching Amedas data...")
raw_data = fetch_amedas_data(test_date, AMEDAS_KUTSUGATA['id'])

if raw_data:
    print("OK - Amedas data fetched successfully")
    print(f"  Data points: {len(raw_data)} hours")

    # Calculate statistics
    print("\nCalculating daily statistics...")
    stats = calculate_daily_statistics(raw_data)

    print("OK - Statistics calculated:")
    print(f"  Max Temp: {stats['temp_max']}C" if stats['temp_max'] else "  Max Temp: N/A")
    print(f"  Min Temp: {stats['temp_min']}C" if stats['temp_min'] else "  Min Temp: N/A")
    print(f"  Min Humidity: {stats['humidity_min']}%" if stats['humidity_min'] else "  Min Humidity: N/A")
    print(f"  Avg Wind: {stats['wind_speed_avg']:.1f} m/s" if stats['wind_speed_avg'] else "  Avg Wind: N/A")
    print(f"  Precipitation: {stats['precipitation']} mm")

else:
    print("ERROR - Failed to fetch Amedas data")
    print("Note: Amedas ID might be incorrect or data not available for this date")
    sys.exit(1)

print("\nOK - Test completed successfully")
