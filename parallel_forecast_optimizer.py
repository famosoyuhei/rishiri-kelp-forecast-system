#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Parallel Forecast Optimizer
Enhanced kelp drying forecast system with parallel processing optimization
"""

import asyncio
import aiohttp
import time
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
from functools import wraps
import json
import logging
from typing import Dict, List, Optional, Any, Tuple

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class ParallelWeatherAPI:
    """Enhanced weather API with parallel processing capabilities"""
    
    def __init__(self, max_concurrent_requests=10, timeout=30):
        self.max_concurrent_requests = max_concurrent_requests
        self.timeout = timeout
        self.session = None
        self._session_lock = threading.Lock()
        
        # Connection pooling configuration
        self.connector_config = {
            'limit': 100,
            'limit_per_host': 20,
            'ttl_dns_cache': 300,
            'enable_cleanup_closed': True
        }
    
    async def _get_session(self):
        """Get or create aiohttp session with connection pooling"""
        if self.session is None or self.session.closed:
            with self._session_lock:
                if self.session is None or self.session.closed:
                    connector = aiohttp.TCPConnector(**self.connector_config)
                    timeout = aiohttp.ClientTimeout(total=self.timeout)
                    self.session = aiohttp.ClientSession(
                        connector=connector,
                        timeout=timeout,
                        headers={'User-Agent': 'Rishiri-Kelp-Forecast/1.0'}
                    )
        return self.session
    
    async def fetch_weather_data(self, lat: float, lon: float, date: str) -> Dict[str, Any]:
        """Fetch weather data for a single date asynchronously"""
        session = await self._get_session()
        
        params = {
            "latitude": lat,
            "longitude": lon,
            "start_date": date,
            "end_date": date,
            "hourly": "temperature_2m,relative_humidity_2m,wind_speed_10m,wind_direction_10m,"
                     "shortwave_radiation,cloud_cover,precipitation_probability,"
                     "cape,lifted_index,convective_inhibition",
            "timezone": "Asia/Tokyo"
        }
        
        url = "https://api.open-meteo.com/v1/forecast"
        
        try:
            start_time = time.time()
            async with session.get(url, params=params) as response:
                duration = time.time() - start_time
                
                if response.status == 200:
                    data = await response.json()
                    logger.info(f"Weather data fetched for {date} in {duration:.2f}s")
                    return {
                        'success': True,
                        'data': data,
                        'date': date,
                        'duration': duration,
                        'lat': lat,
                        'lon': lon
                    }
                else:
                    logger.error(f"API error {response.status} for {date}")
                    return {
                        'success': False,
                        'error': f"HTTP {response.status}",
                        'date': date,
                        'duration': duration
                    }
                    
        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"Request failed for {date}: {e}")
            return {
                'success': False,
                'error': str(e),
                'date': date,
                'duration': duration
            }
    
    async def fetch_multiple_dates_async(self, lat: float, lon: float, dates: List[str]) -> Dict[str, Any]:
        """Fetch weather data for multiple dates in parallel using asyncio"""
        logger.info(f"Starting parallel fetch for {len(dates)} dates using asyncio")
        start_time = time.time()
        
        # Create semaphore to limit concurrent requests
        semaphore = asyncio.Semaphore(self.max_concurrent_requests)
        
        async def fetch_with_semaphore(date):
            async with semaphore:
                return await self.fetch_weather_data(lat, lon, date)
        
        # Execute all requests in parallel
        tasks = [fetch_with_semaphore(date) for date in dates]
        results = await asyncio.gather(*tasks)
        
        total_time = time.time() - start_time
        
        # Process results
        successful_results = [r for r in results if r['success']]
        failed_results = [r for r in results if not r['success']]
        
        logger.info(f"Asyncio parallel fetch completed: {len(successful_results)}/{len(dates)} successful in {total_time:.2f}s")
        
        return {
            'method': 'asyncio',
            'total_requests': len(dates),
            'successful_requests': len(successful_results),
            'failed_requests': len(failed_results),
            'total_time': total_time,
            'average_time_per_request': total_time / len(dates),
            'results': {result['date']: result for result in results},
            'performance_metrics': {
                'requests_per_second': len(dates) / total_time,
                'speedup_vs_sequential': self._estimate_sequential_time(len(dates)) / total_time,
                'concurrent_efficiency': len(successful_results) / (total_time * self.max_concurrent_requests) * 100
            }
        }
    
    def fetch_multiple_dates_threaded(self, lat: float, lon: float, dates: List[str]) -> Dict[str, Any]:
        """Fetch weather data for multiple dates in parallel using ThreadPoolExecutor"""
        logger.info(f"Starting parallel fetch for {len(dates)} dates using ThreadPoolExecutor")
        start_time = time.time()
        
        def sync_fetch(date):
            # Run async function in new event loop
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                return loop.run_until_complete(self.fetch_weather_data(lat, lon, date))
            finally:
                loop.close()
        
        # Use ThreadPoolExecutor for parallel execution
        results = []
        with ThreadPoolExecutor(max_workers=min(self.max_concurrent_requests, len(dates))) as executor:
            future_to_date = {executor.submit(sync_fetch, date): date for date in dates}
            
            for future in as_completed(future_to_date):
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    date = future_to_date[future]
                    logger.error(f"Thread execution failed for {date}: {e}")
                    results.append({
                        'success': False,
                        'error': str(e),
                        'date': date,
                        'duration': 0
                    })
        
        total_time = time.time() - start_time
        
        successful_results = [r for r in results if r['success']]
        failed_results = [r for r in results if not r['success']]
        
        logger.info(f"ThreadPool parallel fetch completed: {len(successful_results)}/{len(dates)} successful in {total_time:.2f}s")
        
        return {
            'method': 'threadpool',
            'total_requests': len(dates),
            'successful_requests': len(successful_results),
            'failed_requests': len(failed_results),
            'total_time': total_time,
            'average_time_per_request': total_time / len(dates),
            'results': {result['date']: result for result in results},
            'performance_metrics': {
                'requests_per_second': len(dates) / total_time,
                'speedup_vs_sequential': self._estimate_sequential_time(len(dates)) / total_time,
                'thread_efficiency': len(successful_results) / (total_time * min(self.max_concurrent_requests, len(dates))) * 100
            }
        }
    
    async def fetch_sequential(self, lat: float, lon: float, dates: List[str]) -> Dict[str, Any]:
        """Fetch weather data sequentially for comparison"""
        logger.info(f"Starting sequential fetch for {len(dates)} dates")
        start_time = time.time()
        
        results = []
        
        for date in dates:
            result = await self.fetch_weather_data(lat, lon, date)
            results.append(result)
        
        total_time = time.time() - start_time
        successful_results = [r for r in results if r['success']]
        
        logger.info(f"Sequential fetch completed: {len(successful_results)}/{len(dates)} successful in {total_time:.2f}s")
        
        return {
            'method': 'sequential',
            'total_requests': len(dates),
            'successful_requests': len(successful_results),
            'failed_requests': len(dates) - len(successful_results),
            'total_time': total_time,
            'average_time_per_request': total_time / len(dates),
            'results': {result['date']: result for result in results}
        }
    
    def _estimate_sequential_time(self, num_requests: int) -> float:
        """Estimate sequential time based on average request duration"""
        # Based on previous analysis: ~1.43s per request
        return num_requests * 1.43
    
    async def close(self):
        """Close the aiohttp session"""
        if self.session and not self.session.closed:
            await self.session.close()


class EnhancedKelpForecastSystem:
    """Enhanced kelp forecast system with parallel processing"""
    
    def __init__(self):
        self.weather_api = ParallelWeatherAPI(max_concurrent_requests=7)
        self.cache = {}
        self.cache_ttl = 600  # 10 minutes
    
    def generate_forecast_dates(self, days_ahead: int = 7) -> List[str]:
        """Generate list of forecast dates"""
        dates = []
        for day in range(1, days_ahead + 1):
            target_date = datetime.now() + timedelta(days=day)
            dates.append(target_date.strftime("%Y-%m-%d"))
        return dates
    
    def process_weather_data_to_forecast(self, weather_result: Dict[str, Any]) -> Dict[str, Any]:
        """Convert raw weather data to kelp forecast format"""
        if not weather_result['success']:
            return {
                'success': False,
                'error': weather_result.get('error', 'Unknown error'),
                'date': weather_result['date']
            }
        
        try:
            hourly = weather_result['data']['hourly']
            
            # Extract work hours (6-16, indices 6-16 in hourly data)
            work_hours = slice(6, 17)  # 6:00-16:00
            
            # Calculate averages for work hours
            temp_avg = sum(hourly['temperature_2m'][work_hours]) / 11
            humidity_avg = sum(hourly['relative_humidity_2m'][work_hours]) / 11
            wind_avg = sum(hourly['wind_speed_10m'][work_hours]) / 11
            cloud_avg = sum(hourly['cloud_cover'][work_hours]) / 11
            
            # Atmospheric stability analysis
            cape_values = hourly['cape'][work_hours]
            li_values = hourly['lifted_index'][work_hours]
            max_cape = max(cape_values)
            min_li = min(li_values)
            
            # Calculate instability risk
            instability_risk = 0
            if max_cape > 1000:
                instability_risk += min(40, max_cape / 50)
            if min_li < 0:
                instability_risk += min(30, abs(min_li) * 10)
            
            # Base drying score calculation
            base_score = 100
            
            # Temperature factor (optimal: 20-30°C)
            if temp_avg < 15:
                base_score -= (15 - temp_avg) * 2
            elif temp_avg > 35:
                base_score -= (temp_avg - 35) * 1.5
            
            # Humidity factor (lower is better)
            if humidity_avg > 70:
                base_score -= (humidity_avg - 70) * 0.5
            
            # Wind factor (optimal: 3-12 m/s)
            if wind_avg < 2:
                base_score -= (2 - wind_avg) * 5
            elif wind_avg > 15:
                base_score -= (wind_avg - 15) * 2
            
            # Cloud cover factor
            base_score -= cloud_avg * 0.3
            
            # Apply atmospheric stability penalty
            stability_penalty = instability_risk * 0.7
            final_score = max(0, base_score - stability_penalty)
            
            # Determine prediction level
            if final_score >= 70:
                prediction = "GOOD"
                recommendation = "Optimal kelp drying conditions"
            elif final_score >= 50:
                prediction = "FAIR" 
                recommendation = "Acceptable conditions with monitoring"
            elif final_score >= 30:
                prediction = "POOR"
                recommendation = "Unsuitable conditions - postpone work"
            else:
                prediction = "VERY_POOR"
                recommendation = "Dangerous conditions - cancel all work"
            
            return {
                'success': True,
                'date': weather_result['date'],
                'prediction': prediction,
                'final_score': final_score,
                'base_score': base_score,
                'stability_penalty': stability_penalty,
                'recommendation': recommendation,
                'traditional_weather': {
                    'temperature': temp_avg,
                    'humidity': humidity_avg,
                    'wind_speed': wind_avg,
                    'cloud_cover': cloud_avg
                },
                'atmospheric_stability': {
                    'instability_risk': instability_risk,
                    'max_cape': max_cape,
                    'min_lifted_index': min_li,
                    'warnings': self._generate_stability_warnings(instability_risk, max_cape, min_li)
                },
                'processing_time': weather_result.get('duration', 0)
            }
            
        except Exception as e:
            logger.error(f"Error processing weather data for {weather_result['date']}: {e}")
            return {
                'success': False,
                'error': f"Processing error: {str(e)}",
                'date': weather_result['date']
            }
    
    def _generate_stability_warnings(self, risk: float, cape: float, li: float) -> List[str]:
        """Generate atmospheric stability warnings"""
        warnings = []
        
        if risk > 50:
            warnings.append("High atmospheric instability detected")
        if cape > 2000:
            warnings.append("Strong convection potential")
        if li < -3:
            warnings.append("Very unstable atmospheric conditions")
        if risk > 30:
            warnings.append("Monitor weather conditions closely")
            
        return warnings
    
    async def get_weekly_forecast_parallel_async(self, lat: float, lon: float) -> Dict[str, Any]:
        """Get 7-day forecast using asyncio parallel processing"""
        dates = self.generate_forecast_dates(7)
        
        # Fetch weather data in parallel
        weather_results = await self.weather_api.fetch_multiple_dates_async(lat, lon, dates)
        
        # Process each result into forecast format
        forecasts = {}
        processing_start = time.time()
        
        for date, weather_result in weather_results['results'].items():
            forecast = self.process_weather_data_to_forecast(weather_result)
            day_number = dates.index(date) + 1
            forecasts[day_number] = forecast
        
        processing_time = time.time() - processing_start
        
        return {
            'forecasts': forecasts,
            'performance_metrics': {
                'method': 'asyncio_parallel',
                'total_time': weather_results['total_time'] + processing_time,
                'weather_fetch_time': weather_results['total_time'],
                'processing_time': processing_time,
                'successful_forecasts': len([f for f in forecasts.values() if f['success']]),
                'total_forecasts': len(forecasts),
                **weather_results['performance_metrics']
            }
        }
    
    def get_weekly_forecast_parallel_threaded(self, lat: float, lon: float) -> Dict[str, Any]:
        """Get 7-day forecast using ThreadPoolExecutor parallel processing"""
        dates = self.generate_forecast_dates(7)
        
        # Fetch weather data in parallel
        weather_results = self.weather_api.fetch_multiple_dates_threaded(lat, lon, dates)
        
        # Process each result into forecast format
        forecasts = {}
        processing_start = time.time()
        
        for date, weather_result in weather_results['results'].items():
            forecast = self.process_weather_data_to_forecast(weather_result)
            day_number = dates.index(date) + 1
            forecasts[day_number] = forecast
        
        processing_time = time.time() - processing_start
        
        return {
            'forecasts': forecasts,
            'performance_metrics': {
                'method': 'threadpool_parallel',
                'total_time': weather_results['total_time'] + processing_time,
                'weather_fetch_time': weather_results['total_time'],
                'processing_time': processing_time,
                'successful_forecasts': len([f for f in forecasts.values() if f['success']]),
                'total_forecasts': len(forecasts),
                **weather_results['performance_metrics']
            }
        }
    
    async def get_weekly_forecast_sequential(self, lat: float, lon: float) -> Dict[str, Any]:
        """Get 7-day forecast using sequential processing (for comparison)"""
        dates = self.generate_forecast_dates(7)
        
        # Fetch weather data sequentially
        weather_results = await self.weather_api.fetch_sequential(lat, lon, dates)
        
        # Process each result into forecast format
        forecasts = {}
        processing_start = time.time()
        
        for date, weather_result in weather_results['results'].items():
            forecast = self.process_weather_data_to_forecast(weather_result)
            day_number = dates.index(date) + 1
            forecasts[day_number] = forecast
        
        processing_time = time.time() - processing_start
        
        return {
            'forecasts': forecasts,
            'performance_metrics': {
                'method': 'sequential',
                'total_time': weather_results['total_time'] + processing_time,
                'weather_fetch_time': weather_results['total_time'],
                'processing_time': processing_time,
                'successful_forecasts': len([f for f in forecasts.values() if f['success']]),
                'total_forecasts': len(forecasts)
            }
        }
    
    async def close(self):
        """Clean up resources"""
        await self.weather_api.close()


async def compare_parallel_methods():
    """Compare different parallel processing methods"""
    print("=" * 80)
    print("PARALLEL PROCESSING PERFORMANCE COMPARISON")
    print("=" * 80)
    
    # Test location
    lat, lon = 45.2065, 141.1368
    
    forecast_system = EnhancedKelpForecastSystem()
    
    try:
        print(f"Testing location: {lat}°N, {lon}°E")
        print(f"Forecast period: 7 days ahead")
        print(f"Max concurrent requests: {forecast_system.weather_api.max_concurrent_requests}")
        print()
        
        # Test 1: Sequential (baseline)
        print("1. SEQUENTIAL PROCESSING (Baseline)")
        print("-" * 50)
        sequential_result = await forecast_system.get_weekly_forecast_sequential(lat, lon)
        seq_metrics = sequential_result['performance_metrics']
        print(f"   Total time: {seq_metrics['total_time']:.2f}s")
        print(f"   Weather fetch: {seq_metrics['weather_fetch_time']:.2f}s")
        print(f"   Processing: {seq_metrics['processing_time']:.2f}s")
        print(f"   Success rate: {seq_metrics['successful_forecasts']}/{seq_metrics['total_forecasts']}")
        print(f"   Avg per request: {seq_metrics['weather_fetch_time']/7:.2f}s")
        
        # Test 2: Asyncio Parallel
        print(f"\n2. ASYNCIO PARALLEL PROCESSING")
        print("-" * 50)
        asyncio_result = await forecast_system.get_weekly_forecast_parallel_async(lat, lon)
        async_metrics = asyncio_result['performance_metrics']
        print(f"   Total time: {async_metrics['total_time']:.2f}s")
        print(f"   Weather fetch: {async_metrics['weather_fetch_time']:.2f}s")
        print(f"   Processing: {async_metrics['processing_time']:.2f}s")
        print(f"   Success rate: {async_metrics['successful_forecasts']}/{async_metrics['total_forecasts']}")
        print(f"   Requests/sec: {async_metrics['requests_per_second']:.2f}")
        print(f"   Speedup vs Sequential: {seq_metrics['total_time']/async_metrics['total_time']:.1f}x")
        print(f"   Concurrent efficiency: {async_metrics['concurrent_efficiency']:.1f}%")
        
        # Test 3: ThreadPool Parallel  
        print(f"\n3. THREADPOOL PARALLEL PROCESSING")
        print("-" * 50)
        thread_result = forecast_system.get_weekly_forecast_parallel_threaded(lat, lon)
        thread_metrics = thread_result['performance_metrics']
        print(f"   Total time: {thread_metrics['total_time']:.2f}s")
        print(f"   Weather fetch: {thread_metrics['weather_fetch_time']:.2f}s")
        print(f"   Processing: {thread_metrics['processing_time']:.2f}s")
        print(f"   Success rate: {thread_metrics['successful_forecasts']}/{thread_metrics['total_forecasts']}")
        print(f"   Requests/sec: {thread_metrics['requests_per_second']:.2f}")
        print(f"   Speedup vs Sequential: {seq_metrics['total_time']/thread_metrics['total_time']:.1f}x")
        print(f"   Thread efficiency: {thread_metrics['thread_efficiency']:.1f}%")
        
        # Summary
        print(f"\n" + "=" * 80)
        print("PERFORMANCE SUMMARY")
        print("=" * 80)
        
        best_method = "asyncio" if async_metrics['total_time'] < thread_metrics['total_time'] else "threadpool"
        best_time = min(async_metrics['total_time'], thread_metrics['total_time'])
        best_speedup = seq_metrics['total_time'] / best_time
        
        print(f"Sequential baseline: {seq_metrics['total_time']:.2f}s")
        print(f"Best parallel method: {best_method} ({best_time:.2f}s)")
        print(f"Maximum speedup achieved: {best_speedup:.1f}x")
        print(f"Time saved per weekly forecast: {seq_metrics['total_time'] - best_time:.2f}s")
        print(f"Performance improvement: {((seq_metrics['total_time'] - best_time) / seq_metrics['total_time'] * 100):.1f}%")
        
        # User Experience Analysis
        print(f"\nUSER EXPERIENCE IMPACT:")
        ux_categories = [
            (0.5, "Instant", "Excellent"),
            (2.0, "Fast", "Very Good"), 
            (5.0, "Acceptable", "Good"),
            (10.0, "Slow", "Fair"),
            (float('inf'), "Very Slow", "Poor")
        ]
        
        for time_limit, category, satisfaction in ux_categories:
            if best_time <= time_limit:
                print(f"   Weekly forecast speed: {category} ({satisfaction} user experience)")
                break
        
        # Recommendations
        print(f"\nRECOMMENDATIONS:")
        print(f"   - Implement {best_method} parallel processing in production")
        print(f"   - Expected {best_speedup:.1f}x improvement in weekly forecast speed")
        print(f"   - Reduces user wait time from {seq_metrics['total_time']:.1f}s to {best_time:.1f}s")
        
        return {
            'sequential': sequential_result,
            'asyncio': asyncio_result,
            'threadpool': thread_result,
            'best_method': best_method,
            'speedup': best_speedup
        }
        
    except Exception as e:
        print(f"Performance comparison failed: {e}")
        import traceback
        traceback.print_exc()
        return None
        
    finally:
        await forecast_system.close()


if __name__ == "__main__":
    # Run the comparison
    results = asyncio.run(compare_parallel_methods())
    
    if results:
        print(f"\n" + "=" * 80)
        print("INTEGRATION READY")
        print("=" * 80)
        print("Parallel processing optimization is ready for Flask integration.")
        print("Use the best performing method for production deployment.")