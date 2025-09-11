#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Forecast Performance Analyzer
Measure and optimize forecast retrieval speed
"""

import time
import asyncio
import requests
import statistics
from datetime import datetime, timedelta
import json
from concurrent.futures import ThreadPoolExecutor
import threading

class ForecastPerformanceAnalyzer:
    def __init__(self, base_url="http://localhost:8001"):
        self.base_url = base_url
        self.test_location = {"lat": 45.2065, "lon": 141.1368, "name": "H_2065_1368"}
        self.results = {}
        
    def measure_single_forecast_speed(self, days_ahead=1, iterations=5):
        """Measure speed of single forecast retrieval"""
        
        print(f"Testing single forecast speed ({days_ahead} days ahead, {iterations} iterations)")
        print("-" * 60)
        
        times = []
        errors = 0
        
        for i in range(iterations):
            start_time = time.time()
            
            try:
                target_date = (datetime.now() + timedelta(days=days_ahead)).strftime("%Y-%m-%d")
                url = f"{self.base_url}/enhanced_forecast"
                params = {
                    "lat": self.test_location["lat"],
                    "lon": self.test_location["lon"], 
                    "start_date": target_date
                }
                
                response = requests.get(url, params=params, timeout=30)
                end_time = time.time()
                
                if response.status_code == 200:
                    duration = end_time - start_time
                    times.append(duration)
                    print(f"  Attempt {i+1}: {duration:.2f}s - OK")
                else:
                    errors += 1
                    print(f"  Attempt {i+1}: ERROR (HTTP {response.status_code})")
                    
            except Exception as e:
                errors += 1
                end_time = time.time()
                duration = end_time - start_time
                print(f"  Attempt {i+1}: ERROR ({duration:.2f}s) - {str(e)[:50]}")
        
        if times:
            avg_time = statistics.mean(times)
            min_time = min(times)
            max_time = max(times)
            median_time = statistics.median(times)
            
            print(f"\nSingle Forecast Performance:")
            print(f"  Average: {avg_time:.2f}s")
            print(f"  Median:  {median_time:.2f}s") 
            print(f"  Min:     {min_time:.2f}s")
            print(f"  Max:     {max_time:.2f}s")
            print(f"  Success: {len(times)}/{iterations} ({len(times)/iterations*100:.1f}%)")
            print(f"  Errors:  {errors}")
            
            return {
                "average": avg_time,
                "median": median_time,
                "min": min_time,
                "max": max_time,
                "success_rate": len(times)/iterations*100,
                "errors": errors,
                "raw_times": times
            }
        else:
            print("All requests failed!")
            return None
    
    def measure_weekly_forecast_speed_sequential(self):
        """Measure speed of 7-day forecast (sequential requests)"""
        
        print(f"\nTesting weekly forecast speed (Sequential)")
        print("-" * 60)
        
        start_time = time.time()
        successful_days = 0
        individual_times = []
        
        for day in range(1, 8):
            day_start = time.time()
            
            try:
                target_date = (datetime.now() + timedelta(days=day)).strftime("%Y-%m-%d")
                url = f"{self.base_url}/enhanced_forecast"
                params = {
                    "lat": self.test_location["lat"],
                    "lon": self.test_location["lon"],
                    "start_date": target_date
                }
                
                response = requests.get(url, params=params, timeout=30)
                day_end = time.time()
                day_duration = day_end - day_start
                
                if response.status_code == 200:
                    successful_days += 1
                    individual_times.append(day_duration)
                    print(f"  Day {day}: {day_duration:.2f}s - OK")
                else:
                    print(f"  Day {day}: ERROR (HTTP {response.status_code})")
                    
            except Exception as e:
                day_end = time.time()
                day_duration = day_end - day_start
                print(f"  Day {day}: ERROR ({day_duration:.2f}s) - {str(e)[:50]}")
        
        total_time = time.time() - start_time
        
        print(f"\nSequential Weekly Forecast Performance:")
        print(f"  Total time: {total_time:.2f}s")
        print(f"  Successful days: {successful_days}/7")
        print(f"  Average per day: {statistics.mean(individual_times):.2f}s" if individual_times else "N/A")
        print(f"  Speed: {successful_days/total_time:.1f} forecasts/second")
        
        return {
            "total_time": total_time,
            "successful_days": successful_days,
            "individual_times": individual_times,
            "forecasts_per_second": successful_days/total_time if total_time > 0 else 0
        }
    
    def measure_weekly_forecast_speed_parallel(self, max_workers=7):
        """Measure speed of 7-day forecast (parallel requests)"""
        
        print(f"\nTesting weekly forecast speed (Parallel - {max_workers} workers)")
        print("-" * 60)
        
        def fetch_day_forecast(day):
            day_start = time.time()
            try:
                target_date = (datetime.now() + timedelta(days=day)).strftime("%Y-%m-%d")
                url = f"{self.base_url}/enhanced_forecast"
                params = {
                    "lat": self.test_location["lat"],
                    "lon": self.test_location["lon"],
                    "start_date": target_date
                }
                
                response = requests.get(url, params=params, timeout=30)
                day_end = time.time()
                day_duration = day_end - day_start
                
                if response.status_code == 200:
                    print(f"  Day {day}: {day_duration:.2f}s - OK")
                    return {"day": day, "time": day_duration, "success": True}
                else:
                    print(f"  Day {day}: ERROR (HTTP {response.status_code})")
                    return {"day": day, "time": day_duration, "success": False}
                    
            except Exception as e:
                day_end = time.time()
                day_duration = day_end - day_start
                print(f"  Day {day}: ERROR ({day_duration:.2f}s) - {str(e)[:50]}")
                return {"day": day, "time": day_duration, "success": False}
        
        start_time = time.time()
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(fetch_day_forecast, day) for day in range(1, 8)]
            results = [future.result() for future in futures]
        
        total_time = time.time() - start_time
        
        successful_results = [r for r in results if r["success"]]
        successful_days = len(successful_results)
        individual_times = [r["time"] for r in successful_results]
        
        print(f"\nParallel Weekly Forecast Performance:")
        print(f"  Total time: {total_time:.2f}s")
        print(f"  Successful days: {successful_days}/7")
        print(f"  Average per day: {statistics.mean(individual_times):.2f}s" if individual_times else "N/A")
        print(f"  Speed: {successful_days/total_time:.1f} forecasts/second")
        print(f"  Speedup vs Sequential: {self.results.get('sequential', {}).get('total_time', total_time)/total_time:.1f}x" if 'sequential' in self.results else "N/A")
        
        return {
            "total_time": total_time,
            "successful_days": successful_days,
            "individual_times": individual_times,
            "forecasts_per_second": successful_days/total_time if total_time > 0 else 0,
            "max_workers": max_workers
        }
    
    def measure_multiple_locations_speed(self, locations=None, parallel=True):
        """Measure speed for multiple locations"""
        
        if locations is None:
            locations = [
                {"lat": 45.2065, "lon": 141.1368, "name": "H_2065_1368"},
                {"lat": 45.2321, "lon": 141.2696, "name": "H_2321_2696"},
                {"lat": 45.1109, "lon": 141.2746, "name": "H_1109_2745"},
                {"lat": 45.0988, "lon": 141.2399, "name": "H_0988_2398"}
            ]
        
        print(f"\nTesting multiple locations speed ({'Parallel' if parallel else 'Sequential'})")
        print(f"Locations: {len(locations)}")
        print("-" * 60)
        
        def fetch_location_forecast(location):
            start_time = time.time()
            try:
                target_date = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
                url = f"{self.base_url}/enhanced_forecast"
                params = {
                    "lat": location["lat"],
                    "lon": location["lon"],
                    "start_date": target_date
                }
                
                response = requests.get(url, params=params, timeout=30)
                end_time = time.time()
                duration = end_time - start_time
                
                if response.status_code == 200:
                    print(f"  {location['name']}: {duration:.2f}s - OK")
                    return {"location": location["name"], "time": duration, "success": True}
                else:
                    print(f"  {location['name']}: ERROR (HTTP {response.status_code})")
                    return {"location": location["name"], "time": duration, "success": False}
                    
            except Exception as e:
                end_time = time.time()
                duration = end_time - start_time
                print(f"  {location['name']}: ERROR ({duration:.2f}s) - {str(e)[:50]}")
                return {"location": location["name"], "time": duration, "success": False}
        
        start_time = time.time()
        
        if parallel:
            with ThreadPoolExecutor(max_workers=len(locations)) as executor:
                futures = [executor.submit(fetch_location_forecast, loc) for loc in locations]
                results = [future.result() for future in futures]
        else:
            results = [fetch_location_forecast(loc) for loc in locations]
        
        total_time = time.time() - start_time
        
        successful_results = [r for r in results if r["success"]]
        successful_locations = len(successful_results)
        individual_times = [r["time"] for r in successful_results]
        
        print(f"\nMultiple Locations Performance:")
        print(f"  Total time: {total_time:.2f}s")
        print(f"  Successful locations: {successful_locations}/{len(locations)}")
        print(f"  Average per location: {statistics.mean(individual_times):.2f}s" if individual_times else "N/A")
        print(f"  Speed: {successful_locations/total_time:.1f} forecasts/second")
        
        return {
            "total_time": total_time,
            "successful_locations": successful_locations,
            "total_locations": len(locations),
            "individual_times": individual_times,
            "forecasts_per_second": successful_locations/total_time if total_time > 0 else 0,
            "method": "parallel" if parallel else "sequential"
        }
    
    def analyze_bottlenecks(self):
        """Analyze potential bottlenecks in the system"""
        
        print(f"\nBottleneck Analysis")
        print("-" * 60)
        
        # Test API availability
        start_time = time.time()
        try:
            response = requests.get(f"{self.base_url}/system_status", timeout=10)
            api_response_time = time.time() - start_time
            api_available = response.status_code == 200
            print(f"  API Availability: {'OK' if api_available else 'ERROR'} ({api_response_time:.2f}s)")
        except Exception as e:
            api_response_time = time.time() - start_time
            api_available = False
            print(f"  API Availability: ERROR ({api_response_time:.2f}s) - {e}")
        
        # Test external weather API (if we can determine the endpoint)
        print(f"  External Weather API: Testing Open-Meteo...")
        start_time = time.time()
        try:
            test_params = {
                "latitude": 45.2065,
                "longitude": 141.1368,
                "start_date": "2025-08-12",
                "end_date": "2025-08-12",
                "hourly": "temperature_2m,cape,lifted_index",
                "timezone": "Asia/Tokyo"
            }
            response = requests.get("https://api.open-meteo.com/v1/forecast", 
                                  params=test_params, timeout=15)
            external_api_time = time.time() - start_time
            external_api_available = response.status_code == 200
            print(f"    Open-Meteo API: {'OK' if external_api_available else 'ERROR'} ({external_api_time:.2f}s)")
        except Exception as e:
            external_api_time = time.time() - start_time
            external_api_available = False
            print(f"    Open-Meteo API: ERROR ({external_api_time:.2f}s) - {e}")
        
        # Network latency test
        print(f"  Network Tests:")
        for i in range(3):
            start_time = time.time()
            try:
                response = requests.get(f"{self.base_url}/", timeout=5)
                latency = time.time() - start_time
                print(f"    Ping {i+1}: {latency*1000:.0f}ms")
            except:
                latency = time.time() - start_time
                print(f"    Ping {i+1}: TIMEOUT ({latency*1000:.0f}ms)")
        
        return {
            "api_available": api_available,
            "api_response_time": api_response_time,
            "external_api_available": external_api_available,
            "external_api_time": external_api_time
        }
    
    def generate_performance_recommendations(self):
        """Generate performance optimization recommendations"""
        
        print(f"\nPerformance Optimization Recommendations")
        print("=" * 60)
        
        if not self.results:
            print("No performance data available. Run tests first.")
            return
        
        # Analyze results and generate recommendations
        single_forecast = self.results.get("single_forecast")
        sequential_weekly = self.results.get("sequential")
        parallel_weekly = self.results.get("parallel")
        multiple_locations = self.results.get("multiple_locations")
        bottlenecks = self.results.get("bottlenecks")
        
        recommendations = []
        
        # Single forecast speed analysis
        if single_forecast:
            avg_time = single_forecast["average"]
            if avg_time > 5.0:
                recommendations.append({
                    "priority": "HIGH",
                    "issue": "Slow single forecast retrieval",
                    "detail": f"Average: {avg_time:.2f}s (target: <2s)",
                    "solutions": [
                        "Optimize atmospheric stability calculations",
                        "Implement result caching",
                        "Parallelize internal computations",
                        "Use faster external weather API"
                    ]
                })
            elif avg_time > 2.0:
                recommendations.append({
                    "priority": "MEDIUM", 
                    "issue": "Moderate forecast latency",
                    "detail": f"Average: {avg_time:.2f}s (target: <2s)",
                    "solutions": [
                        "Implement caching for recent requests",
                        "Optimize database queries",
                        "Consider CDN for static resources"
                    ]
                })
            else:
                recommendations.append({
                    "priority": "LOW",
                    "issue": "Good single forecast performance",
                    "detail": f"Average: {avg_time:.2f}s (within target)",
                    "solutions": ["Monitor and maintain current performance"]
                })
        
        # Weekly forecast analysis
        if sequential_weekly and parallel_weekly:
            seq_time = sequential_weekly["total_time"]
            par_time = parallel_weekly["total_time"]
            speedup = seq_time / par_time if par_time > 0 else 1
            
            if speedup > 3:
                recommendations.append({
                    "priority": "LOW",
                    "issue": "Excellent parallelization efficiency",
                    "detail": f"{speedup:.1f}x speedup with parallel requests",
                    "solutions": ["Continue using parallel requests for weekly forecasts"]
                })
            elif speedup > 1.5:
                recommendations.append({
                    "priority": "MEDIUM",
                    "issue": "Good parallelization gains",
                    "detail": f"{speedup:.1f}x speedup with parallel requests",
                    "solutions": [
                        "Optimize parallel request handling",
                        "Consider connection pooling",
                        "Tune thread pool size"
                    ]
                })
            else:
                recommendations.append({
                    "priority": "HIGH",
                    "issue": "Poor parallelization efficiency",
                    "detail": f"Only {speedup:.1f}x speedup with parallel requests",
                    "solutions": [
                        "Investigate bottlenecks in parallel processing",
                        "Check for synchronization issues",
                        "Consider async/await pattern",
                        "Review thread pool configuration"
                    ]
                })
        
        # External API dependency analysis
        if bottlenecks:
            ext_api_time = bottlenecks.get("external_api_time", 0)
            if ext_api_time > 3.0:
                recommendations.append({
                    "priority": "HIGH",
                    "issue": "Slow external weather API",
                    "detail": f"Open-Meteo API: {ext_api_time:.2f}s response time",
                    "solutions": [
                        "Implement aggressive caching for weather data",
                        "Consider alternative weather APIs",
                        "Add timeout and retry mechanisms",
                        "Pre-fetch commonly requested forecasts"
                    ]
                })
        
        # Display recommendations
        for rec in sorted(recommendations, key=lambda x: {"HIGH": 3, "MEDIUM": 2, "LOW": 1}[x["priority"]], reverse=True):
            print(f"\n[{rec['priority']}] {rec['issue']}")
            print(f"  Details: {rec['detail']}")
            print(f"  Solutions:")
            for solution in rec['solutions']:
                print(f"    - {solution}")
        
        return recommendations
    
    def run_comprehensive_analysis(self):
        """Run comprehensive performance analysis"""
        
        print("=" * 80)
        print("COMPREHENSIVE FORECAST PERFORMANCE ANALYSIS")
        print("=" * 80)
        print(f"Test Location: {self.test_location['name']} ({self.test_location['lat']}, {self.test_location['lon']})")
        print(f"Test Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print()
        
        # 1. Single forecast speed
        self.results["single_forecast"] = self.measure_single_forecast_speed(days_ahead=1, iterations=3)
        
        # 2. Weekly forecast - sequential
        self.results["sequential"] = self.measure_weekly_forecast_speed_sequential()
        
        # 3. Weekly forecast - parallel
        self.results["parallel"] = self.measure_weekly_forecast_speed_parallel(max_workers=7)
        
        # 4. Multiple locations
        self.results["multiple_locations"] = self.measure_multiple_locations_speed(parallel=True)
        
        # 5. Bottleneck analysis
        self.results["bottlenecks"] = self.analyze_bottlenecks()
        
        # 6. Generate recommendations
        recommendations = self.generate_performance_recommendations()
        
        # 7. Summary
        print(f"\n" + "=" * 80)
        print("PERFORMANCE SUMMARY")
        print("=" * 80)
        
        if self.results.get("single_forecast"):
            sf = self.results["single_forecast"]
            print(f"Single Forecast: {sf['average']:.2f}s avg (success: {sf['success_rate']:.1f}%)")
        
        if self.results.get("sequential") and self.results.get("parallel"):
            seq = self.results["sequential"]
            par = self.results["parallel"]
            speedup = seq['total_time'] / par['total_time'] if par['total_time'] > 0 else 1
            print(f"Weekly Forecast: {seq['total_time']:.2f}s sequential, {par['total_time']:.2f}s parallel ({speedup:.1f}x faster)")
        
        if self.results.get("multiple_locations"):
            ml = self.results["multiple_locations"]
            print(f"Multiple Locations: {ml['total_time']:.2f}s for {ml['successful_locations']}/{ml['total_locations']} locations")
        
        high_priority_issues = len([r for r in recommendations if r["priority"] == "HIGH"])
        if high_priority_issues > 0:
            print(f"\n⚠️  {high_priority_issues} HIGH PRIORITY performance issues identified")
        else:
            print(f"\n✅ No critical performance issues detected")
        
        # Save results
        results_file = f"performance_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(results_file, 'w') as f:
            json.dump(self.results, f, indent=2, default=str)
        
        print(f"\nDetailed results saved to: {results_file}")
        
        return self.results

if __name__ == "__main__":
    analyzer = ForecastPerformanceAnalyzer()
    
    try:
        results = analyzer.run_comprehensive_analysis()
    except KeyboardInterrupt:
        print("\nAnalysis interrupted by user")
    except Exception as e:
        print(f"\nAnalysis failed: {e}")
        import traceback
        traceback.print_exc()