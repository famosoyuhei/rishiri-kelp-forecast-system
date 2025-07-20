import requests
from datetime import datetime, timedelta

# Test Open-Meteo API
lat = 45.241667  # 鴛泊港周辺
lon = 141.230833
start_date = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
end_date = (datetime.now() + timedelta(days=2)).strftime("%Y-%m-%d")

url = "https://api.open-meteo.com/v1/forecast"
params = {
    "latitude": lat,
    "longitude": lon,
    "start_date": start_date,
    "end_date": end_date,
    "hourly": "temperature_2m,wind_speed_10m,shortwave_radiation,precipitation_probability",
    "timezone": "Asia/Tokyo"
}

print("Testing Open-Meteo API...")
print(f"URL: {url}")
print(f"Params: {params}")

try:
    response = requests.get(url, params=params)
    print(f"Status code: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        print(f"Response keys: {list(data.keys())}")
        
        if "hourly" in data:
            hourly = data["hourly"]
            print(f"Hourly data keys: {list(hourly.keys())}")
            print(f"Temperature data points: {len(hourly.get('temperature_2m', []))}")
        else:
            print("No hourly data in response")
            print(f"Full response: {data}")
    else:
        print(f"API error: {response.text}")
        
except Exception as e:
    print(f"Request error: {e}")

print("Test complete")