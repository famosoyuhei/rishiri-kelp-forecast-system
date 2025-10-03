#!/usr/bin/env python3
"""
Rishiri Kelp Forecast System - Production Version
"""
import os
import sys
import requests
from datetime import datetime
from flask import Flask, jsonify, request
from flask_cors import CORS

# Create Flask app
app = Flask(__name__)
CORS(app)

@app.route('/')
def home():
    return {
        'message': 'Rishiri Kelp Forecast System - Production Version', 
        'status': 'ok',
        'version': '2.0.0',
        'endpoints': {
            'weather': '/api/weather',
            'forecast': '/api/forecast', 
            'health': '/health'
        }
    }

@app.route('/health')
def health():
    return {'status': 'healthy', 'version': '2.0.0'}, 200

@app.route('/api/weather')
def get_weather():
    """Get current weather for Rishiri Island"""
    # Rishiri Island coordinates
    lat = request.args.get('lat', 45.178269)
    lon = request.args.get('lon', 141.228528)
    
    try:
        # Open-Meteo API for current weather
        url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current_weather=true&hourly=temperature_2m,relative_humidity_2m,wind_speed_10m,wind_direction_10m"
        
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        current = data.get('current_weather', {})
        
        return {
            'location': 'Rishiri Island',
            'coordinates': {'lat': float(lat), 'lon': float(lon)},
            'current': {
                'temperature': current.get('temperature'),
                'wind_speed': current.get('windspeed'),
                'wind_direction': current.get('winddirection'),
                'weather_code': current.get('weathercode')
            },
            'timestamp': datetime.now().isoformat(),
            'status': 'success'
        }
        
    except Exception as e:
        return {
            'error': 'Weather data unavailable',
            'message': str(e),
            'status': 'error'
        }, 503

@app.route('/api/forecast')
def get_forecast():
    """Get kelp drying forecast for Rishiri Island"""
    lat = request.args.get('lat', 45.178269)
    lon = request.args.get('lon', 141.228528)
    
    try:
        # Basic kelp drying conditions analysis
        url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&daily=temperature_2m_max,temperature_2m_min,wind_speed_10m_max,relative_humidity_2m_mean,precipitation_sum&timezone=Asia/Tokyo&forecast_days=7"
        
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        daily = data.get('daily', {})
        
        # Simple kelp drying suitability calculation
        forecasts = []
        for i in range(min(7, len(daily.get('time', [])))):
            temp_max = daily['temperature_2m_max'][i]
            humidity = daily['relative_humidity_2m_mean'][i]
            wind_speed = daily['wind_speed_10m_max'][i]
            precipitation = daily['precipitation_sum'][i]
            
            # Basic suitability score (0-100)
            score = 0
            if temp_max > 15: score += 25
            if temp_max > 20: score += 15
            if humidity < 70: score += 20
            if humidity < 60: score += 10
            if wind_speed > 3: score += 15
            if wind_speed > 5: score += 10
            if precipitation < 1: score += 15
            
            suitability = 'excellent' if score >= 80 else 'good' if score >= 60 else 'fair' if score >= 40 else 'poor'
            
            forecasts.append({
                'date': daily['time'][i],
                'temperature_max': temp_max,
                'humidity': humidity,
                'wind_speed': wind_speed,
                'precipitation': precipitation,
                'drying_score': score,
                'suitability': suitability
            })
        
        return {
            'location': 'Rishiri Island',
            'forecasts': forecasts,
            'timestamp': datetime.now().isoformat(),
            'status': 'success'
        }
        
    except Exception as e:
        return {
            'error': 'Forecast data unavailable',
            'message': str(e),
            'status': 'error'
        }, 503

# Simple startup function
def main():
    # Multiple fallback strategies for PORT
    port_env = os.environ.get('PORT')
    if port_env is None or port_env == '' or port_env == '$PORT':
        port = 8000
        print("WARNING: PORT not properly set, using default 8000", file=sys.stdout)
    else:
        try:
            port = int(port_env)
        except (ValueError, TypeError):
            port = 8000
            print(f"WARNING: Invalid PORT '{port_env}', using default 8000", file=sys.stdout)
    
    print(f"Starting Rishiri Kelp Forecast System on port {port}", file=sys.stdout)
    print(f"Environment PORT variable: '{os.environ.get('PORT', 'NOT SET')}'", file=sys.stdout)
    
    app.run(
        host='0.0.0.0', 
        port=port, 
        debug=False,
        threaded=True
    )

if __name__ == '__main__':
    main()