/**
 * Kelp Forecast API Integration
 * Enhanced Atmospheric Stability System Interface
 */

class KelpForecastAPI {
    constructor(baseUrl = 'http://localhost:8001') {
        this.baseUrl = baseUrl;
        this.cache = new Map();
        this.cacheTimeout = 10 * 60 * 1000; // 10 minutes
    }
    
    /**
     * Get enhanced forecast for specified location and days ahead
     */
    async getForecast(lat, lon, daysAhead = 1) {
        const cacheKey = `${lat}_${lon}_${daysAhead}`;
        
        // Check cache first
        if (this.cache.has(cacheKey)) {
            const cached = this.cache.get(cacheKey);
            if (Date.now() - cached.timestamp < this.cacheTimeout) {
                return cached.data;
            }
        }
        
        try {
            const targetDate = this.calculateTargetDate(daysAhead);
            const url = `${this.baseUrl}/enhanced_forecast?lat=${lat}&lon=${lon}&start_date=${targetDate}`;
            
            const response = await fetch(url);
            if (!response.ok) {
                throw new Error(`API request failed: ${response.status}`);
            }
            
            const data = await response.json();
            const processedData = this.processAPIResponse(data, daysAhead);
            
            // Cache the result
            this.cache.set(cacheKey, {
                data: processedData,
                timestamp: Date.now()
            });
            
            return processedData;
            
        } catch (error) {
            console.error('Forecast API error:', error);
            return this.generateFallbackData(daysAhead);
        }
    }
    
    /**
     * Calculate target date for forecast
     */
    calculateTargetDate(daysAhead) {
        const target = new Date();
        target.setDate(target.getDate() + daysAhead);
        return target.toISOString().split('T')[0];
    }
    
    /**
     * Process API response into UI-friendly format
     */
    processAPIResponse(apiData, daysAhead) {
        const weather = apiData.traditional_weather;
        const stability = apiData.atmospheric_stability;
        const assessment = apiData.enhancement_info;
        
        // Generate hourly data (4:00-16:00)
        const hourlyData = this.generateHourlyData(weather, stability);
        
        return {
            daysAhead,
            date: new Date(Date.now() + daysAhead * 24 * 60 * 60 * 1000),
            
            // Summary data
            averages: {
                temperature: weather.temperature,
                humidity: weather.humidity,
                windSpeed: weather.wind_speed,
                cloudCover: weather.cloud_cover
            },
            
            // Hourly progression (4:00-16:00)
            hourly: hourlyData,
            
            // Atmospheric stability
            stability: {
                risk: stability.instability_risk,
                maxCape: stability.max_cape,
                minLiftedIndex: stability.min_lifted_index,
                warnings: stability.warnings,
                convectionTiming: stability.convection_timing
            },
            
            // Assessment
            judgment: {
                level: apiData.prediction,
                score: assessment.final_score,
                baseScore: assessment.base_score,
                stabilityPenalty: assessment.stability_penalty,
                message: apiData.recommendation,
                confidence: this.calculateConfidence(daysAhead, stability.instability_risk)
            }
        };
    }
    
    /**
     * Generate hourly data for charts (4:00-16:00)
     */
    generateHourlyData(weather, stability) {
        const hours = [];
        const data = {
            labels: [],
            temperature: [],
            humidity: [],
            windSpeed: [],
            radiation: [],
            cape: [],
            precipitation: [],
            liftedIndex: []
        };
        
        // Generate 13 hours of data (4:00-16:00)
        for (let hour = 4; hour <= 16; hour++) {
            const label = `${hour.toString().padStart(2, '0')}:00`;
            data.labels.push(label);
            
            // Temperature curve (peaks around noon)
            const tempFactor = Math.sin((hour - 6) / 12 * Math.PI);
            const temp = weather.temperature + tempFactor * 6 + this.randomVariation(1);
            data.temperature.push(Math.max(5, temp));
            
            // Humidity curve (inverse of temperature)
            const humidity = weather.humidity - tempFactor * 15 + this.randomVariation(3);
            data.humidity.push(Math.max(30, Math.min(95, humidity)));
            
            // Wind speed with some variation
            const wind = weather.wind_speed + this.randomVariation(2);
            data.windSpeed.push(Math.max(0, wind));
            
            // Solar radiation curve
            const radiationFactor = Math.max(0, Math.sin((hour - 6) / 12 * Math.PI));
            const radiation = radiationFactor * 900 * (1 - weather.cloud_cover / 100);
            data.radiation.push(Math.max(0, radiation + this.randomVariation(50)));
            
            // CAPE values (higher during peak heating)
            const capeFactor = Math.max(0, Math.sin((hour - 8) / 10 * Math.PI));
            const cape = stability.max_cape * capeFactor + this.randomVariation(stability.max_cape * 0.1);
            data.cape.push(Math.max(0, cape));
            
            // Precipitation probability
            const precipBase = weather.precipitation_probability || 0;
            const precip = precipBase + (stability.instability_risk / 100 * 30) + this.randomVariation(5);
            data.precipitation.push(Math.max(0, Math.min(100, precip)));
            
            // Lifted Index variation
            const li = stability.min_lifted_index + this.randomVariation(0.5);
            data.liftedIndex.push(li);
        }
        
        return data;
    }
    
    /**
     * Generate random variation for more realistic data
     */
    randomVariation(amplitude) {
        return (Math.random() - 0.5) * amplitude * 2;
    }
    
    /**
     * Calculate confidence based on forecast distance and stability
     */
    calculateConfidence(daysAhead, instabilityRisk) {
        // Base confidence decreases with forecast distance
        const dayConfidence = Math.max(50, 100 - (daysAhead - 1) * 8);
        
        // Stability confidence
        const stabilityConfidence = Math.max(60, 100 - instabilityRisk * 0.8);
        
        // Overall accuracy
        const overallAccuracy = (dayConfidence + stabilityConfidence) / 2;
        
        return {
            overall: Math.round(overallAccuracy),
            daysAhead: Math.round(dayConfidence),
            stability: Math.round(stabilityConfidence)
        };
    }
    
    /**
     * Generate fallback data when API is unavailable
     */
    generateFallbackData(daysAhead) {
        console.warn('Using fallback data - API unavailable');
        
        const baseTemp = 18 + Math.random() * 10;
        const baseHumidity = 65 + Math.random() * 25;
        const baseWind = 3 + Math.random() * 12;
        const instabilityRisk = Math.random() * 60;
        
        return {
            daysAhead,
            date: new Date(Date.now() + daysAhead * 24 * 60 * 60 * 1000),
            
            averages: {
                temperature: baseTemp,
                humidity: baseHumidity,
                windSpeed: baseWind,
                cloudCover: 40 + Math.random() * 40
            },
            
            hourly: this.generateFallbackHourlyData(baseTemp, baseHumidity, baseWind, instabilityRisk),
            
            stability: {
                risk: instabilityRisk,
                maxCape: instabilityRisk * 15 + Math.random() * 200,
                minLiftedIndex: 2 - instabilityRisk / 25 + Math.random() * 2,
                warnings: instabilityRisk > 40 ? ['高い不安定性が予測されています'] : [],
                convectionTiming: { period: instabilityRisk > 30 ? 'afternoon' : 'morning' }
            },
            
            judgment: {
                level: instabilityRisk > 50 ? 'POOR' : instabilityRisk > 25 ? 'FAIR' : 'GOOD',
                score: Math.max(10, 80 - instabilityRisk),
                baseScore: Math.max(15, 85 - instabilityRisk * 0.5),
                stabilityPenalty: instabilityRisk * 0.3,
                message: 'フォールバックデータを使用しています',
                confidence: this.calculateConfidence(daysAhead, instabilityRisk)
            },
            
            fallback: true
        };
    }
    
    /**
     * Generate fallback hourly data
     */
    generateFallbackHourlyData(baseTemp, baseHumidity, baseWind, instabilityRisk) {
        const data = {
            labels: [],
            temperature: [],
            humidity: [],
            windSpeed: [],
            radiation: [],
            cape: [],
            precipitation: [],
            liftedIndex: []
        };
        
        for (let hour = 4; hour <= 16; hour++) {
            data.labels.push(`${hour.toString().padStart(2, '0')}:00`);
            
            const tempFactor = Math.sin((hour - 6) / 12 * Math.PI);
            data.temperature.push(baseTemp + tempFactor * 7 + this.randomVariation(1.5));
            data.humidity.push(Math.max(40, Math.min(90, baseHumidity - tempFactor * 12 + this.randomVariation(4))));
            data.windSpeed.push(Math.max(0, baseWind + this.randomVariation(2.5)));
            
            const radiationFactor = Math.max(0, Math.sin((hour - 6) / 12 * Math.PI));
            data.radiation.push(radiationFactor * 800 + this.randomVariation(100));
            
            data.cape.push(Math.max(0, instabilityRisk * 10 * radiationFactor + this.randomVariation(100)));
            data.precipitation.push(Math.max(0, Math.min(100, instabilityRisk + this.randomVariation(10))));
            data.liftedIndex.push(2 - instabilityRisk / 30 + this.randomVariation(1));
        }
        
        return data;
    }
    
    /**
     * Get multiple days forecast using parallel backend optimization
     */
    async getWeeklyForecast(lat, lon) {
        const cacheKey = `weekly_${lat}_${lon}`;
        
        // Check cache first
        if (this.cache.has(cacheKey)) {
            const cached = this.cache.get(cacheKey);
            if (Date.now() - cached.timestamp < this.cacheTimeout) {
                console.log('Using cached weekly forecast');
                return cached.data;
            }
        }
        
        try {
            const startTime = performance.now();
            const url = `${this.baseUrl}/weekly_forecast_parallel?lat=${lat}&lon=${lon}`;
            
            const response = await fetch(url);
            if (!response.ok) {
                throw new Error(`Parallel API request failed: ${response.status}`);
            }
            
            const result = await response.json();
            const endTime = performance.now();
            
            if (result.status === 'success') {
                // Convert server format to UI format
                const forecasts = {};
                
                for (let day = 1; day <= 7; day++) {
                    const serverForecast = result.forecasts[day];
                    if (serverForecast && !serverForecast.error) {
                        forecasts[day] = this.processServerForecastData(serverForecast, day);
                    } else {
                        // Fallback for failed individual forecasts
                        forecasts[day] = this.generateFallbackData(day);
                        forecasts[day].fallback = true;
                    }
                }
                
                // Add performance metrics
                console.log(`Parallel weekly forecast completed in ${(endTime - startTime).toFixed(2)}ms`);
                console.log(`Server performance: ${result.performance_metrics.total_time}s total`);
                console.log(`Speedup: ${result.performance_metrics.speedup_vs_sequential}x vs sequential`);
                console.log(`Efficiency: ${result.performance_metrics.concurrent_efficiency}%`);
                
                // Cache the result
                this.cache.set(cacheKey, {
                    data: forecasts,
                    timestamp: Date.now()
                });
                
                return forecasts;
            } else {
                throw new Error(result.error || 'Parallel forecast failed');
            }
            
        } catch (error) {
            console.error('Parallel weekly forecast failed, falling back to individual requests:', error);
            
            // Fallback to individual requests (original method)
            return this.getWeeklyForecastFallback(lat, lon);
        }
    }
    
    /**
     * Convert server forecast data to UI format
     */
    processServerForecastData(serverForecast, daysAhead) {
        const weather = serverForecast.traditional_weather;
        const stability = serverForecast.atmospheric_stability;
        
        return {
            daysAhead,
            date: new Date(serverForecast.date),
            
            // Summary data
            averages: {
                temperature: weather.temperature,
                humidity: weather.humidity,
                windSpeed: weather.wind_speed,
                cloudCover: weather.cloud_cover
            },
            
            // Generate hourly data (since server doesn't provide it yet)
            hourly: this.generateHourlyData(weather, stability),
            
            // Atmospheric stability
            stability: {
                risk: stability.instability_risk,
                maxCape: stability.max_cape,
                minLiftedIndex: stability.min_lifted_index,
                warnings: stability.warnings,
                convectionTiming: { period: 'afternoon' }  // Default
            },
            
            // Assessment
            judgment: {
                level: serverForecast.prediction,
                score: serverForecast.final_score,
                baseScore: serverForecast.base_score,
                stabilityPenalty: serverForecast.stability_penalty,
                message: serverForecast.recommendation,
                confidence: this.calculateConfidence(daysAhead, stability.instability_risk)
            }
        };
    }
    
    /**
     * Fallback to individual requests method
     */
    async getWeeklyForecastFallback(lat, lon) {
        console.log('Using fallback individual forecast method');
        const forecasts = {};
        const promises = [];
        
        for (let day = 1; day <= 7; day++) {
            promises.push(
                this.getForecast(lat, lon, day).then(data => {
                    forecasts[day] = data;
                })
            );
        }
        
        await Promise.all(promises);
        return forecasts;
    }
    
    /**
     * Clear cache
     */
    clearCache() {
        this.cache.clear();
    }
}

/**
 * Enhanced Forecast Display Controller
 */
class ForecastDisplay {
    constructor(apiBaseUrl) {
        this.api = new KelpForecastAPI(apiBaseUrl);
        this.currentDay = 1;
        this.currentLocation = { lat: 45.2065, lon: 141.1368, name: 'H_2065_1368' };
        this.charts = {};
        this.forecastData = {};
    }
    
    /**
     * Initialize the display
     */
    async initialize() {
        this.initializeTabs();
        await this.loadAllForecasts();
        this.updateDisplay();
        
        // Auto-refresh every 10 minutes
        setInterval(() => {
            this.refreshForecasts();
        }, 10 * 60 * 1000);
    }
    
    /**
     * Initialize tab functionality
     */
    initializeTabs() {
        const tabs = document.querySelectorAll('.day-tab');
        tabs.forEach(tab => {
            tab.addEventListener('click', (e) => {
                tabs.forEach(t => t.classList.remove('active'));
                tab.classList.add('active');
                
                this.currentDay = parseInt(tab.dataset.day);
                this.updateDisplay();
            });
        });
    }
    
    /**
     * Load all forecasts (1-7 days)
     */
    async loadAllForecasts() {
        const loading = this.showLoading();
        
        try {
            this.forecastData = await this.api.getWeeklyForecast(
                this.currentLocation.lat,
                this.currentLocation.lon
            );
        } catch (error) {
            console.error('Failed to load forecasts:', error);
            this.showError('予報データの読み込みに失敗しました');
        } finally {
            loading.hide();
        }
    }
    
    /**
     * Update display for current day
     */
    updateDisplay() {
        const data = this.forecastData[this.currentDay];
        if (!data) return;
        
        this.updateHeader(data);
        this.updateVisualIndicators(data);
        this.updateJudgment(data);
        this.updateConfidence(data);
        this.updateCharts(data);
    }
    
    /**
     * Update header information
     */
    updateHeader(data) {
        const dateStr = data.date.toLocaleDateString('ja-JP', {
            year: 'numeric',
            month: 'long',
            day: 'numeric',
            weekday: 'short'
        });
        
        document.getElementById('forecastDate').textContent = dateStr;
        document.getElementById('daysAhead').textContent = `${data.daysAhead}日後の予報`;
        
        if (data.fallback) {
            document.getElementById('daysAhead').textContent += ' (オフラインモード)';
        }
    }
    
    /**
     * Update visual indicators
     */
    updateVisualIndicators(data) {
        const avg = data.averages;
        
        document.getElementById('avgTemp').textContent = Math.round(avg.temperature) + '°C';
        document.getElementById('avgHumidity').textContent = Math.round(avg.humidity) + '%';
        document.getElementById('avgWind').textContent = Math.round(avg.windSpeed) + 'm/s';
        
        // Stability indicator
        const stabilityLevel = data.stability.risk < 20 ? '低' : 
                              data.stability.risk < 50 ? '中' : '高';
        const stabilityClass = data.stability.risk < 20 ? 'stability-stable' : 
                              data.stability.risk < 50 ? 'stability-moderate' : 'stability-unstable';
        
        document.getElementById('stabilityRisk').textContent = stabilityLevel;
        const stabilityBar = document.getElementById('stabilityBar');
        stabilityBar.className = `stability-fill ${stabilityClass}`;
        stabilityBar.style.width = Math.max(10, 100 - data.stability.risk) + '%';
        
        // Temperature arrow
        const tempTrend = this.calculateTrend(data.hourly.temperature);
        document.getElementById('tempArrow').textContent = tempTrend > 5 ? '📈' : tempTrend < -5 ? '📉' : '➡️';
        
        // Humidity arrow
        const humidityTrend = this.calculateTrend(data.hourly.humidity);
        document.getElementById('humidityArrow').textContent = humidityTrend > 5 ? '💧⬆️' : humidityTrend < -5 ? '💧⬇️' : '💧➡️';
    }
    
    /**
     * Calculate trend for arrow indicators
     */
    calculateTrend(values) {
        if (values.length < 2) return 0;
        const start = values.slice(0, 3).reduce((a, b) => a + b) / 3;
        const end = values.slice(-3).reduce((a, b) => a + b) / 3;
        return end - start;
    }
    
    /**
     * Update judgment section
     */
    updateJudgment(data) {
        const judgment = data.judgment;
        let resultText, resultIcon;
        
        switch (judgment.level) {
            case 'GOOD':
                resultText = '優良な乾燥条件';
                resultIcon = '✅';
                break;
            case 'FAIR':
                resultText = '注意して干せる';
                resultIcon = '⚠️';
                break;
            case 'POOR':
                resultText = '干すには不適';
                resultIcon = '❌';
                break;
            default:
                resultText = '作業中止推奨';
                resultIcon = '🚨';
        }
        
        document.getElementById('judgmentResult').innerHTML = `${resultIcon} ${resultText}`;
        document.getElementById('judgmentScore').textContent = `総合スコア: ${Math.round(judgment.score)}/100点`;
        document.getElementById('judgmentMessage').textContent = judgment.message;
        
        // Show warnings if present
        const warningIcon = document.getElementById('warningIcon');
        if (data.stability.warnings && data.stability.warnings.length > 0) {
            warningIcon.style.display = 'inline';
            warningIcon.title = data.stability.warnings.join('; ');
        } else {
            warningIcon.style.display = 'none';
        }
    }
    
    /**
     * Update confidence indicators
     */
    updateConfidence(data) {
        const conf = data.judgment.confidence;
        
        document.getElementById('forecastAccuracy').textContent = conf.overall + '%';
        document.getElementById('forecastDays').textContent = data.daysAhead + '日後';
        document.getElementById('stabilityConfidence').textContent = conf.stability + '%';
        
        document.getElementById('accuracyBar').style.width = conf.overall + '%';
        document.getElementById('daysBar').style.width = conf.daysAhead + '%';
        document.getElementById('stabilityConfidenceBar').style.width = conf.stability + '%';
    }
    
    /**
     * Update all charts
     */
    updateCharts(data) {
        // Destroy existing charts
        Object.values(this.charts).forEach(chart => chart && chart.destroy());
        
        const hourly = data.hourly;
        
        // Temperature & Humidity Chart
        this.charts.tempHumidity = new Chart(document.getElementById('tempHumidityChart'), {
            type: 'line',
            data: {
                labels: hourly.labels,
                datasets: [{
                    label: '気温 (°C)',
                    data: hourly.temperature,
                    borderColor: '#FF6384',
                    backgroundColor: 'rgba(255, 99, 132, 0.1)',
                    yAxisID: 'y',
                    tension: 0.4
                }, {
                    label: '湿度 (%)',
                    data: hourly.humidity,
                    borderColor: '#36A2EB',
                    backgroundColor: 'rgba(54, 162, 235, 0.1)',
                    yAxisID: 'y1',
                    tension: 0.4
                }]
            },
            options: this.getChartOptions('気温 (°C)', '湿度 (%)')
        });
        
        // Wind & Radiation Chart
        this.charts.windRadiation = new Chart(document.getElementById('windRadiationChart'), {
            type: 'line',
            data: {
                labels: hourly.labels,
                datasets: [{
                    label: '風速 (m/s)',
                    data: hourly.windSpeed,
                    borderColor: '#4BC0C0',
                    backgroundColor: 'rgba(75, 192, 192, 0.1)',
                    yAxisID: 'y',
                    tension: 0.4
                }, {
                    label: '日射量 (W/m²)',
                    data: hourly.radiation,
                    borderColor: '#FFCE56',
                    backgroundColor: 'rgba(255, 206, 86, 0.1)',
                    yAxisID: 'y1',
                    tension: 0.4,
                    fill: true
                }]
            },
            options: this.getChartOptions('風速 (m/s)', '日射量 (W/m²)')
        });
        
        // Atmospheric Stability Chart
        this.charts.stability = new Chart(document.getElementById('stabilityChart'), {
            type: 'line',
            data: {
                labels: hourly.labels,
                datasets: [{
                    label: 'CAPE値',
                    data: hourly.cape,
                    borderColor: '#FF9F40',
                    backgroundColor: 'rgba(255, 159, 64, 0.2)',
                    fill: true,
                    tension: 0.4
                }, {
                    label: 'Lifted Index',
                    data: hourly.liftedIndex,
                    borderColor: '#C9CBCF',
                    backgroundColor: 'rgba(201, 203, 207, 0.1)',
                    yAxisID: 'y1',
                    tension: 0.4
                }]
            },
            options: this.getChartOptions('CAPE値', 'Lifted Index')
        });
        
        // Precipitation Chart
        this.charts.precipitation = new Chart(document.getElementById('precipitationChart'), {
            type: 'bar',
            data: {
                labels: hourly.labels,
                datasets: [{
                    label: '降水確率 (%)',
                    data: hourly.precipitation,
                    backgroundColor: hourly.precipitation.map(p => 
                        p > 70 ? 'rgba(244, 67, 54, 0.7)' :
                        p > 40 ? 'rgba(255, 152, 0, 0.7)' :
                        'rgba(76, 175, 80, 0.7)'
                    ),
                    borderColor: '#36A2EB',
                    borderWidth: 1
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    y: {
                        title: { display: true, text: '降水確率 (%)' },
                        beginAtZero: true,
                        max: 100
                    }
                },
                plugins: {
                    legend: { display: true }
                }
            }
        });
    }
    
    /**
     * Get standard chart options
     */
    getChartOptions(leftAxisLabel, rightAxisLabel) {
        return {
            responsive: true,
            maintainAspectRatio: false,
            interaction: {
                mode: 'index',
                intersect: false,
            },
            scales: {
                y: {
                    type: 'linear',
                    display: true,
                    position: 'left',
                    title: { display: true, text: leftAxisLabel }
                },
                y1: {
                    type: 'linear',
                    display: true,
                    position: 'right',
                    title: { display: true, text: rightAxisLabel },
                    grid: { drawOnChartArea: false }
                }
            },
            plugins: {
                legend: { display: true }
            }
        };
    }
    
    /**
     * Show loading indicator
     */
    showLoading() {
        const loading = document.createElement('div');
        loading.className = 'loading-overlay';
        loading.innerHTML = '<div class="spinner">読み込み中...</div>';
        document.body.appendChild(loading);
        
        return {
            hide: () => loading.remove()
        };
    }
    
    /**
     * Show error message
     */
    showError(message) {
        const error = document.createElement('div');
        error.className = 'error-message';
        error.textContent = message;
        document.body.appendChild(error);
        
        setTimeout(() => error.remove(), 5000);
    }
    
    /**
     * Refresh forecasts
     */
    async refreshForecasts() {
        this.api.clearCache();
        await this.loadAllForecasts();
        this.updateDisplay();
    }
    
    /**
     * Change location
     */
    async changeLocation(lat, lon, name) {
        this.currentLocation = { lat, lon, name };
        document.getElementById('locationName').textContent = name;
        document.getElementById('locationCoords').textContent = `${lat.toFixed(4)}°N, ${lon.toFixed(4)}°E`;
        
        await this.loadAllForecasts();
        this.updateDisplay();
    }
}