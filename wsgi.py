"""
WSGI entry point for production deployment
利尻島昆布干場予報システム - 本番環境エントリーポイント
"""

import os
import logging
from konbu_flask_final import app
from config import get_config

# Load configuration
config_class = get_config()
app.config.from_object(config_class)

# Configure logging for production
if app.config['FLASK_ENV'] == 'production':
    # Set up structured logging
    logging.basicConfig(
        level=getattr(logging, app.config['LOG_LEVEL']),
        format='%(asctime)s %(levelname)s %(name)s %(message)s',
        handlers=[
            logging.StreamHandler()
        ]
    )
    
    # Disable Flask's default logger in production
    log = logging.getLogger('werkzeug')
    log.setLevel(logging.ERROR)

# Health check endpoint for deployment platforms
@app.route('/health')
def health_check():
    """Health check endpoint for load balancers"""
    return {
        'status': 'healthy',
        'version': '1.0.0',
        'environment': app.config['FLASK_ENV'],
        'timestamp': '2025-07-21T13:15:00Z'
    }, 200

# Readiness check endpoint
@app.route('/ready')
def readiness_check():
    """Readiness check for Kubernetes/Railway"""
    try:
        # Check if critical components are working
        from konbu_flask_final import offline_cache
        cache_status = offline_cache.get_cache_status()
        
        return {
            'status': 'ready',
            'cache_status': 'ok' if 'error' not in cache_status else 'error',
            'timestamp': '2025-07-21T13:15:00Z'
        }, 200
    except Exception as e:
        return {
            'status': 'not_ready',
            'error': str(e),
            'timestamp': '2025-07-21T13:15:00Z'
        }, 503

# Configure security headers for production
if app.config['FLASK_ENV'] == 'production':
    @app.after_request
    def add_security_headers(response):
        """Add security headers for production"""
        # HTTPS redirect
        response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
        
        # XSS protection
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['X-XSS-Protection'] = '1; mode=block'
        
        # CSP for PWA
        response.headers['Content-Security-Policy'] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' https://unpkg.com; "
            "style-src 'self' 'unsafe-inline' https://unpkg.com; "
            "img-src 'self' data: https:; "
            "connect-src 'self' https://api.open-meteo.com; "
            "manifest-src 'self';"
        )
        
        # PWA cache control
        if request.endpoint in ['service_worker', 'manifest']:
            response.headers['Cache-Control'] = 'no-cache'
        elif request.endpoint == 'static':
            response.headers['Cache-Control'] = 'public, max-age=86400'
        
        return response

# Error handlers for production
@app.errorhandler(404)
def not_found_error(error):
    """Handle 404 errors gracefully"""
    if app.config['FLASK_ENV'] == 'production':
        return {
            'error': 'Resource not found',
            'message': 'The requested resource could not be found.',
            'timestamp': '2025-07-21T13:15:00Z'
        }, 404
    return str(error), 404

@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors gracefully"""
    if app.config['FLASK_ENV'] == 'production':
        app.logger.error(f'Server Error: {error}')
        return {
            'error': 'Internal server error',
            'message': 'An internal error occurred. Please try again later.',
            'timestamp': '2025-07-21T13:15:00Z'
        }, 500
    return str(error), 500

@app.errorhandler(503)
def service_unavailable(error):
    """Handle 503 errors gracefully"""
    return {
        'error': 'Service unavailable',
        'message': 'The service is temporarily unavailable. Please try again later.',
        'timestamp': '2025-07-21T13:15:00Z'
    }, 503

# Production optimizations
if app.config['FLASK_ENV'] == 'production':
    # Disable debug mode
    app.debug = False
    
    # Configure session settings
    app.config.update(
        SESSION_COOKIE_SECURE=True,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE='Lax',
    )

# Application factory pattern for different environments
def create_app(config_name=None):
    """Create and configure the Flask application"""
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'development')
    
    app.config.from_object(get_config())
    
    # Initialize extensions here if needed
    # db.init_app(app)
    # cache.init_app(app)
    
    return app

if __name__ == '__main__':
    # This is for local development only
    port = int(os.environ.get('PORT', 8000))
    app.run(host='0.0.0.0', port=port, debug=app.config['DEBUG'])