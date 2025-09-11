// Service Worker for Rishiri Kelp Forecast System - Offline Functionality
// Version 1.0.0 - Production Ready

// Production configuration
const CACHE_NAME = 'rishiri-kelp-v1-prod';
const STATIC_CACHE_NAME = 'rishiri-kelp-static-v1-prod';
const WEATHER_CACHE_NAME = 'rishiri-kelp-weather-v1-prod';

// Determine base URL based on environment
const BASE_URL = self.location.origin;
const API_BASE = BASE_URL;

// Resources to cache for offline use
const STATIC_RESOURCES = [
    '/',
    '/static/css/main.css',
    '/static/js/main.js',
    'hoshiba_map_complete.html',
    'dashboard.html',
    // Essential offline pages
    '/offline.html',
    // Leaflet map dependencies
    'https://unpkg.com/leaflet@1.9.4/dist/leaflet.css',
    'https://unpkg.com/leaflet@1.9.4/dist/leaflet.js'
];

// Weather API endpoints to cache
const WEATHER_ENDPOINTS = [
    '/weather/forecast',
    '/sea_fog/predict',
    '/visualization/dashboard'
];

// Install event - Cache static resources
self.addEventListener('install', event => {
    console.log('Service Worker: Installing...');
    
    event.waitUntil(
        Promise.all([
            // Cache static resources
            caches.open(STATIC_CACHE_NAME).then(cache => {
                console.log('Service Worker: Caching static resources');
                return cache.addAll(STATIC_RESOURCES.map(url => {
                    return new Request(url, { mode: 'no-cors' });
                })).catch(error => {
                    console.log('Service Worker: Failed to cache some static resources', error);
                });
            }),
            
            // Initialize weather cache
            caches.open(WEATHER_CACHE_NAME).then(cache => {
                console.log('Service Worker: Weather cache initialized');
                return cache;
            })
        ]).then(() => {
            console.log('Service Worker: Installation complete');
            return self.skipWaiting();
        })
    );
});

// Activate event - Clean up old caches
self.addEventListener('activate', event => {
    console.log('Service Worker: Activating...');
    
    event.waitUntil(
        caches.keys().then(cacheNames => {
            return Promise.all(
                cacheNames.map(cacheName => {
                    if (cacheName !== STATIC_CACHE_NAME && 
                        cacheName !== WEATHER_CACHE_NAME &&
                        cacheName !== CACHE_NAME) {
                        console.log('Service Worker: Deleting old cache', cacheName);
                        return caches.delete(cacheName);
                    }
                })
            );
        }).then(() => {
            console.log('Service Worker: Activation complete');
            return self.clients.claim();
        })
    );
});

// Fetch event - Handle offline requests
self.addEventListener('fetch', event => {
    const { request } = event;
    const url = new URL(request.url);
    
    // Handle weather API requests
    if (WEATHER_ENDPOINTS.some(endpoint => url.pathname.includes(endpoint))) {
        event.respondWith(handleWeatherRequest(request));
        return;
    }
    
    // Handle static resources
    if (request.destination === 'document' || 
        request.destination === 'script' || 
        request.destination === 'style' ||
        request.destination === 'image') {
        event.respondWith(handleStaticRequest(request));
        return;
    }
    
    // Handle map tile requests
    if (url.hostname.includes('openstreetmap') || 
        url.hostname.includes('tile.openstreetmap')) {
        event.respondWith(handleMapTileRequest(request));
        return;
    }
    
    // Default: network first, cache fallback
    event.respondWith(
        fetch(request).catch(() => {
            return caches.match(request);
        })
    );
});

// Handle weather API requests with cache strategy
async function handleWeatherRequest(request) {
    const cache = await caches.open(WEATHER_CACHE_NAME);
    
    try {
        // Try network first
        const response = await fetch(request);
        
        if (response.ok) {
            // Cache successful responses with timestamp
            const responseClone = response.clone();
            const data = await responseClone.json();
            
            // Add cache timestamp
            data.cached_at = new Date().toISOString();
            data.cache_expires_at = new Date(Date.now() + 6 * 60 * 60 * 1000).toISOString(); // 6 hours
            
            const modifiedResponse = new Response(JSON.stringify(data), {
                status: response.status,
                statusText: response.statusText,
                headers: response.headers
            });
            
            cache.put(request, modifiedResponse.clone());
            console.log('Service Worker: Weather data cached', request.url);
            
            return modifiedResponse;
        }
        
        throw new Error('Network response not ok');
        
    } catch (error) {
        console.log('Service Worker: Network failed, trying cache', error);
        
        // Try cache
        const cachedResponse = await cache.match(request);
        if (cachedResponse) {
            const cachedData = await cachedResponse.json();
            
            // Check if cache is still valid (6 hours)
            const cacheExpiry = new Date(cachedData.cache_expires_at);
            const now = new Date();
            
            if (now < cacheExpiry) {
                console.log('Service Worker: Serving valid cached weather data');
                // Add offline indicator
                cachedData.offline_mode = true;
                cachedData.data_age_hours = Math.round((now - new Date(cachedData.cached_at)) / (1000 * 60 * 60));
                
                return new Response(JSON.stringify(cachedData), {
                    status: 200,
                    statusText: 'OK (Cached)',
                    headers: { 'Content-Type': 'application/json' }
                });
            } else {
                console.log('Service Worker: Cached weather data expired');
            }
        }
        
        // Return offline fallback
        return new Response(JSON.stringify({
            error: 'Offline mode - weather data unavailable',
            offline_mode: true,
            message: 'インターネット接続がありません。キャッシュされた天気データも利用できません。'
        }), {
            status: 503,
            statusText: 'Service Unavailable',
            headers: { 'Content-Type': 'application/json' }
        });
    }
}

// Handle static resource requests
async function handleStaticRequest(request) {
    // Try cache first for static resources
    const cachedResponse = await caches.match(request);
    if (cachedResponse) {
        return cachedResponse;
    }
    
    try {
        // Try network
        const response = await fetch(request);
        
        if (response.ok) {
            // Cache successful responses
            const cache = await caches.open(STATIC_CACHE_NAME);
            cache.put(request, response.clone());
        }
        
        return response;
        
    } catch (error) {
        console.log('Service Worker: Failed to fetch static resource', request.url);
        
        // Return offline page for document requests
        if (request.destination === 'document') {
            const offlineResponse = await caches.match('/offline.html');
            if (offlineResponse) {
                return offlineResponse;
            }
        }
        
        throw error;
    }
}

// Handle map tile requests with limited caching
async function handleMapTileRequest(request) {
    const cache = await caches.open('map-tiles-cache');
    
    // Try cache first for map tiles
    const cachedResponse = await cache.match(request);
    if (cachedResponse) {
        return cachedResponse;
    }
    
    try {
        const response = await fetch(request);
        
        if (response.ok) {
            // Cache map tiles with size limit (store only essential tiles)
            const cacheKeys = await cache.keys();
            if (cacheKeys.length < 100) { // Limit to 100 tiles
                cache.put(request, response.clone());
            }
        }
        
        return response;
        
    } catch (error) {
        console.log('Service Worker: Map tile unavailable offline', request.url);
        
        // Return placeholder tile or cached fallback
        return new Response('', {
            status: 404,
            statusText: 'Map tile unavailable offline'
        });
    }
}

// Background sync for data updates when connection restored
self.addEventListener('sync', event => {
    console.log('Service Worker: Background sync triggered');
    
    if (event.tag === 'weather-data-sync') {
        event.waitUntil(syncWeatherData());
    }
});

// Sync weather data when connection is restored
async function syncWeatherData() {
    console.log('Service Worker: Syncing weather data...');
    
    try {
        // Update weather forecasts for key locations
        const keyLocations = [
            { lat: 45.242, lon: 141.242, name: 'oshidomari' },
            { lat: 45.183, lon: 141.250, name: 'kutsugata' },
            { lat: 45.217, lon: 141.183, name: 'funadomari' }
        ];
        
        const updatePromises = keyLocations.map(location => {
            const url = `/weather/forecast?lat=${location.lat}&lon=${location.lon}`;
            return fetch(url).then(response => {
                if (response.ok) {
                    console.log(`Service Worker: Updated weather data for ${location.name}`);
                }
            }).catch(error => {
                console.log(`Service Worker: Failed to update weather data for ${location.name}`, error);
            });
        });
        
        await Promise.all(updatePromises);
        console.log('Service Worker: Weather data sync complete');
        
    } catch (error) {
        console.log('Service Worker: Weather data sync failed', error);
    }
}

// Push notification handling for alerts
self.addEventListener('push', event => {
    console.log('Service Worker: Push notification received');
    
    if (event.data) {
        const data = event.data.json();
        
        event.waitUntil(
            self.registration.showNotification(data.title || '利尻昆布予報', {
                body: data.body || '新しい予報情報があります',
                icon: '/static/icons/icon-192x192.png',
                badge: '/static/icons/badge-72x72.png',
                tag: 'weather-alert',
                requireInteraction: data.urgent || false,
                actions: [
                    {
                        action: 'view',
                        title: '詳細を見る'
                    },
                    {
                        action: 'dismiss',
                        title: '閉じる'
                    }
                ]
            })
        );
    }
});

// Handle notification clicks
self.addEventListener('notificationclick', event => {
    console.log('Service Worker: Notification clicked');
    
    event.notification.close();
    
    if (event.action === 'view') {
        event.waitUntil(
            clients.openWindow('/')
        );
    }
});

console.log('Service Worker: Script loaded successfully');