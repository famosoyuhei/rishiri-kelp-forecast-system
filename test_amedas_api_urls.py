"""
Test different Amedas API URL patterns for ID 11151 (Kutsugata)
"""
import requests
import json

amedas_id = '11151'

# Test multiple URL patterns
url_patterns = [
    # Pattern 1: Point data by date
    f"https://www.jma.go.jp/bosai/amedas/data/point/{amedas_id}/20251004.json",

    # Pattern 2: Map data (all stations for a date)
    f"https://www.jma.go.jp/bosai/amedas/data/map/20251004.json",

    # Pattern 3: Latest map data
    "https://www.jma.go.jp/bosai/amedas/data/map/latest.json",

    # Pattern 4: Point latest
    f"https://www.jma.go.jp/bosai/amedas/data/point/{amedas_id}.json",
]

print(f"Testing Amedas API URLs for ID {amedas_id} (Kutsugata)")
print("=" * 80)

for i, url in enumerate(url_patterns, 1):
    print(f"\n[Test {i}] URL: {url}")
    response = requests.get(url)
    print(f"Status: {response.status_code}")

    if response.status_code == 200:
        print(f"SUCCESS!")

        # Parse and show sample data
        try:
            data = response.json()

            # For map data (all stations)
            if 'map' in url or 'latest' in url:
                if amedas_id in data:
                    print(f"Station {amedas_id} found in map data!")
                    station_data = data[amedas_id]
                    print(f"Sample data:")
                    print(f"  Temperature: {station_data.get('temp', ['N/A'])[0] if 'temp' in station_data else 'N/A'}°C")
                    print(f"  Humidity: {station_data.get('humidity', ['N/A'])[0] if 'humidity' in station_data else 'N/A'}%")
                    print(f"  Wind speed: {station_data.get('wind', ['N/A'])[0] if 'wind' in station_data else 'N/A'} m/s")
                else:
                    print(f"Station {amedas_id} NOT found in map data")
                    print(f"Total stations in data: {len(data)}")
                    # Show some station IDs
                    sample_ids = list(data.keys())[:10]
                    print(f"Sample station IDs: {sample_ids}")

            # For point data
            else:
                if isinstance(data, dict):
                    # Hourly data
                    if data:
                        first_key = list(data.keys())[0]
                        print(f"Data type: Hourly data")
                        print(f"First hour: {first_key}")
                        print(f"Sample hour data:")
                        hour_data = data[first_key]
                        print(f"  Temperature: {hour_data.get('temp', ['N/A'])[0] if 'temp' in hour_data else 'N/A'}°C")
                        print(f"  Humidity: {hour_data.get('humidity', ['N/A'])[0] if 'humidity' in hour_data else 'N/A'}%")
                    else:
                        print("Empty data returned")
        except Exception as e:
            print(f"Error parsing JSON: {e}")
    else:
        print(f"FAILED - HTTP {response.status_code}")

print("\n" + "=" * 80)
print("\nCONCLUSION:")
print("Check which URL pattern successfully returned data for station 11151")
