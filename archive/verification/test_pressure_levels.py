#!/usr/bin/env python3
"""
Test Open-Meteo API for pressure level data availability
"""
import requests

# Test coordinates (Rishiri Island)
lat = 45.178269
lon = 141.228528

# Test pressure level data availability
print("=== Testing Open-Meteo Pressure Level Data ===")

# Available pressure levels to test
test_levels = [500, 700, 850, 925, 1000]

for level in test_levels:
    url = f"https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": f"temperature_{level}hPa,relative_humidity_{level}hPa,wind_speed_{level}hPa",
        "forecast_days": 1,
        "timezone": "Asia/Tokyo"
    }

    try:
        response = requests.get(url, params=params, timeout=10)
        if response.status_code == 200:
            data = response.json()
            hourly = data.get('hourly', {})

            print(f"\n{level}hPa level:")
            print(f"  Temperature: {'OK' if f'temperature_{level}hPa' in hourly else 'NO'}")
            print(f"  Humidity: {'OK' if f'relative_humidity_{level}hPa' in hourly else 'NO'}")
            print(f"  Wind Speed: {'OK' if f'wind_speed_{level}hPa' in hourly else 'NO'}")

        else:
            print(f"{level}hPa level: API Error {response.status_code}")

    except Exception as e:
        print(f"{level}hPa level: Error - {e}")

# Test specific parameters we need
print("\n=== Testing Specific Parameters ===")

# Test vertical velocity (omega) at 700hPa
url = "https://api.open-meteo.com/v1/forecast"
params = {
    "latitude": lat,
    "longitude": lon,
    "hourly": "vertical_velocity_700hPa,omega_700hPa,vertical_motion_700hPa",
    "forecast_days": 1,
    "timezone": "Asia/Tokyo"
}

try:
    response = requests.get(url, params=params, timeout=10)
    print(f"Vertical velocity test: Status {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        hourly = data.get('hourly', {})
        for param in ["vertical_velocity_700hPa", "omega_700hPa", "vertical_motion_700hPa"]:
            print(f"  {param}: {'OK' if param in hourly else 'NO'}")
except Exception as e:
    print(f"Vertical velocity test: Error - {e}")

# Test vorticity at 500hPa
params = {
    "latitude": lat,
    "longitude": lon,
    "hourly": "vorticity_500hPa,relative_vorticity_500hPa,absolute_vorticity_500hPa",
    "forecast_days": 1,
    "timezone": "Asia/Tokyo"
}

try:
    response = requests.get(url, params=params, timeout=10)
    print(f"Vorticity test: Status {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        hourly = data.get('hourly', {})
        for param in ["vorticity_500hPa", "relative_vorticity_500hPa", "absolute_vorticity_500hPa"]:
            print(f"  {param}: {'OK' if param in hourly else 'NO'}")
except Exception as e:
    print(f"Vorticity test: Error - {e}")

print("\n=== Testing Complete ===")