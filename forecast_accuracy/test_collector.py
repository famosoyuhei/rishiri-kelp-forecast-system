"""
Test script for forecast collector
"""

import sys
from datetime import date
from daily_forecast_collector import fetch_forecast_for_spot, save_forecast_to_db
from config import IZUMI_SPOTS

# Test with first spot only
test_spot = IZUMI_SPOTS[0]
print(f"Testing forecast collection for: {test_spot['name']}")
print(f"Location: lat={test_spot['lat']}, lon={test_spot['lon']}")

# Fetch forecast
print("\nFetching forecast data...")
forecast_data = fetch_forecast_for_spot(test_spot)

if forecast_data:
    print("OK - Forecast data fetched successfully")
    print(f"  Status: {forecast_data.get('status')}")
    print(f"  Forecasts available: {len(forecast_data.get('forecasts', []))} days")

    # Save to database
    print("\nSaving to database...")
    forecast_date = date.today()
    saved_count = save_forecast_to_db(test_spot['name'], forecast_date, forecast_data)
    print(f"OK - Saved {saved_count} forecast records")

else:
    print("ERROR - Failed to fetch forecast data")
    sys.exit(1)

print("\nOK - Test completed successfully")
