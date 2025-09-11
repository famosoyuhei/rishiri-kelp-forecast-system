"""
Monitoring and logging configuration for Rishiri Kelp Forecast System
利尻島昆布干場予報システム - モニタリング・ログ設定
"""

import os
import logging
import time
from datetime import datetime, timedelta
from flask import request, g
import json
from collections import defaultdict

class MonitoringManager:
    """Monitoring and metrics collection manager"""
    
    def __init__(self, app=None):
        self.app = app
        self.metrics = defaultdict(list)
        self.error_counts = defaultdict(int)
        self.response_times = defaultdict(list)
        
        if app:
            self.init_app(app)
    
    def init_app(self, app):
        """Initialize monitoring for Flask app"""
        self.app = app
        
        # Configure logging
        self.setup_logging()
        
        # Add request timing middleware
        @app.before_request
        def before_request():
            g.start_time = time.time()
            g.request_id = self.generate_request_id()
        
        @app.after_request
        def after_request(response):
            return self.log_request(response)
        
        # Add metrics endpoints
        @app.route('/metrics')
        def metrics_endpoint():
            return self.get_metrics()
        
        @app.route('/health/detailed')
        def detailed_health():
            return self.get_detailed_health()
    
    def setup_logging(self):
        """Configure structured logging"""
        log_level = getattr(logging, self.app.config.get('LOG_LEVEL', 'INFO'))
        
        # Create formatters
        if self.app.config.get('FLASK_ENV') == 'production':
            # JSON logging for production
            formatter = logging.Formatter(
                '{"timestamp": "%(asctime)s", "level": "%(levelname)s", '
                '"logger": "%(name)s", "message": "%(message)s", '
                '"module": "%(module)s", "function": "%(funcName)s"}'
            )
        else:
            # Human-readable logging for development
            formatter = logging.Formatter(
                '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
            )
        
        # Configure root logger
        logging.basicConfig(
            level=log_level,
            format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
            handlers=[logging.StreamHandler()]
        )
        
        # Configure Flask app logger
        if not self.app.logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(formatter)
            self.app.logger.addHandler(handler)
            self.app.logger.setLevel(log_level)
        
        # Suppress noisy loggers in production
        if self.app.config.get('FLASK_ENV') == 'production':
            logging.getLogger('werkzeug').setLevel(logging.WARNING)
            logging.getLogger('urllib3').setLevel(logging.WARNING)
    
    def generate_request_id(self):
        """Generate unique request ID"""
        return f"{int(time.time())}-{id(request)}"
    
    def log_request(self, response):
        """Log request details and metrics"""
        if hasattr(g, 'start_time'):
            response_time = (time.time() - g.start_time) * 1000  # Convert to ms
            
            # Store metrics
            endpoint = request.endpoint or 'unknown'
            self.response_times[endpoint].append(response_time)
            
            # Keep only recent metrics (last 1000 requests per endpoint)
            if len(self.response_times[endpoint]) > 1000:
                self.response_times[endpoint] = self.response_times[endpoint][-1000:]
            
            # Log request details
            log_data = {
                'request_id': getattr(g, 'request_id', 'unknown'),
                'method': request.method,
                'endpoint': endpoint,
                'path': request.path,
                'status_code': response.status_code,
                'response_time_ms': round(response_time, 2),
                'user_agent': request.headers.get('User-Agent', ''),
                'ip_address': request.remote_addr,
                'referer': request.headers.get('Referer', ''),
            }
            
            # Log based on status code
            if response.status_code >= 500:
                self.app.logger.error(f"Server Error: {json.dumps(log_data)}")
                self.error_counts['5xx'] += 1
            elif response.status_code >= 400:
                self.app.logger.warning(f"Client Error: {json.dumps(log_data)}")
                self.error_counts['4xx'] += 1
            elif response_time > 1000:  # Slow request
                self.app.logger.warning(f"Slow Request: {json.dumps(log_data)}")
            else:
                self.app.logger.info(f"Request: {json.dumps(log_data)}")
        
        return response
    
    def get_metrics(self):
        """Get current system metrics"""
        current_time = datetime.now()
        
        # Calculate response time statistics
        endpoint_stats = {}
        for endpoint, times in self.response_times.items():
            if times:
                endpoint_stats[endpoint] = {
                    'count': len(times),
                    'avg_response_time': round(sum(times) / len(times), 2),
                    'min_response_time': round(min(times), 2),
                    'max_response_time': round(max(times), 2),
                    'slow_requests': len([t for t in times if t > 1000])
                }
        
        metrics = {
            'timestamp': current_time.isoformat(),
            'uptime_seconds': int((current_time - datetime.now()).total_seconds()),
            'endpoints': endpoint_stats,
            'error_counts': dict(self.error_counts),
            'system': {
                'environment': self.app.config.get('FLASK_ENV'),
                'version': '1.0.0'
            }
        }
        
        return metrics
    
    def get_detailed_health(self):
        """Get detailed health check information"""
        try:
            # Check cache system
            from konbu_flask_final import offline_cache
            cache_status = offline_cache.get_cache_status()
            cache_healthy = 'error' not in cache_status
            
            # Check disk space (simplified)
            disk_healthy = True  # Add actual disk space check if needed
            
            # Check response times
            recent_times = []
            for times in self.response_times.values():
                recent_times.extend(times[-10:])  # Last 10 requests per endpoint
            
            avg_response_time = sum(recent_times) / len(recent_times) if recent_times else 0
            response_time_healthy = avg_response_time < 1000  # Less than 1 second
            
            # Overall health
            overall_healthy = cache_healthy and disk_healthy and response_time_healthy
            
            health_data = {
                'status': 'healthy' if overall_healthy else 'unhealthy',
                'timestamp': datetime.now().isoformat(),
                'checks': {
                    'cache_system': {
                        'status': 'healthy' if cache_healthy else 'unhealthy',
                        'details': cache_status
                    },
                    'response_time': {
                        'status': 'healthy' if response_time_healthy else 'unhealthy',
                        'avg_ms': round(avg_response_time, 2),
                        'threshold_ms': 1000
                    },
                    'error_rate': {
                        'status': 'healthy',  # Add actual error rate calculation
                        '4xx_count': self.error_counts.get('4xx', 0),
                        '5xx_count': self.error_counts.get('5xx', 0)
                    }
                },
                'version': '1.0.0',
                'environment': self.app.config.get('FLASK_ENV')
            }
            
            return health_data, 200 if overall_healthy else 503
            
        except Exception as e:
            self.app.logger.error(f"Health check failed: {str(e)}")
            return {
                'status': 'unhealthy',
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }, 503
    
    def log_business_event(self, event_type, details=None):
        """Log business-specific events"""
        event_data = {
            'event_type': event_type,
            'details': details or {},
            'timestamp': datetime.now().isoformat(),
            'request_id': getattr(g, 'request_id', 'no-request')
        }
        
        self.app.logger.info(f"Business Event: {json.dumps(event_data)}")
    
    def alert_on_error_threshold(self, threshold=10, window_minutes=5):
        """Check if error threshold is exceeded"""
        current_time = time.time()
        recent_errors = self.error_counts.get('5xx', 0)
        
        if recent_errors >= threshold:
            self.app.logger.critical(
                f"Error threshold exceeded: {recent_errors} errors in {window_minutes} minutes"
            )
            return True
        return False

# Global monitoring manager
monitoring_manager = MonitoringManager()

def init_monitoring(app):
    """Initialize monitoring for Flask app"""
    monitoring_manager.init_app(app)
    
    # Add custom log handlers for production
    if app.config.get('FLASK_ENV') == 'production':
        # Add Sentry for error tracking if configured
        sentry_dsn = app.config.get('SENTRY_DSN')
        if sentry_dsn:
            try:
                import sentry_sdk
                from sentry_sdk.integrations.flask import FlaskIntegration
                
                sentry_sdk.init(
                    dsn=sentry_dsn,
                    integrations=[FlaskIntegration()],
                    traces_sample_rate=0.1,
                    environment=app.config.get('FLASK_ENV')
                )
                app.logger.info("Sentry error tracking initialized")
            except ImportError:
                app.logger.warning("Sentry SDK not available")
    
    return monitoring_manager