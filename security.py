"""
Security configurations for Rishiri Kelp Forecast System
利尻島昆布干場予報システム - セキュリティ設定
"""

import os
from flask import request, jsonify
from functools import wraps
import time
from collections import defaultdict
import hashlib

class SecurityManager:
    """Security manager for production deployment"""
    
    def __init__(self, app=None):
        self.app = app
        self.rate_limits = defaultdict(list)
        self.blocked_ips = set()
        
        if app:
            self.init_app(app)
    
    def init_app(self, app):
        """Initialize security configurations"""
        self.app = app
        
        # Configure CORS for production
        if app.config.get('FLASK_ENV') == 'production':
            allowed_origins = app.config.get('CORS_ORIGINS', ['https://rishiri-kelp.com'])
            app.config['CORS_ORIGINS'] = allowed_origins
    
    def rate_limit(self, max_requests=60, window=60):
        """Rate limiting decorator"""
        def decorator(f):
            @wraps(f)
            def decorated_function(*args, **kwargs):
                client_ip = self.get_client_ip()
                
                # Check if IP is blocked
                if client_ip in self.blocked_ips:
                    return jsonify({
                        'error': 'Access denied',
                        'message': 'Your IP has been temporarily blocked'
                    }), 429
                
                current_time = time.time()
                
                # Clean old requests
                self.rate_limits[client_ip] = [
                    req_time for req_time in self.rate_limits[client_ip]
                    if current_time - req_time < window
                ]
                
                # Check rate limit
                if len(self.rate_limits[client_ip]) >= max_requests:
                    # Block IP for repeated violations
                    if len(self.rate_limits[client_ip]) > max_requests * 2:
                        self.blocked_ips.add(client_ip)
                    
                    return jsonify({
                        'error': 'Rate limit exceeded',
                        'message': 'Too many requests. Please try again later.',
                        'retry_after': window
                    }), 429
                
                # Add current request
                self.rate_limits[client_ip].append(current_time)
                
                return f(*args, **kwargs)
            return decorated_function
        return decorator
    
    def get_client_ip(self):
        """Get client IP address"""
        # Check for forwarded headers (Railway, Heroku, etc.)
        forwarded_ips = request.headers.get('X-Forwarded-For', '')
        if forwarded_ips:
            return forwarded_ips.split(',')[0].strip()
        
        # Check for Railway specific header
        railway_ip = request.headers.get('X-Railway-Client-IP')
        if railway_ip:
            return railway_ip
        
        # Fallback to remote address
        return request.remote_addr or 'unknown'
    
    def validate_api_key(self, required_key_name):
        """Validate API key from environment"""
        def decorator(f):
            @wraps(f)
            def decorated_function(*args, **kwargs):
                # For development, skip API key validation
                if self.app.config.get('FLASK_ENV') == 'development':
                    return f(*args, **kwargs)
                
                required_key = os.environ.get(required_key_name)
                if not required_key:
                    return jsonify({
                        'error': 'Service configuration error',
                        'message': 'Required API key not configured'
                    }), 503
                
                provided_key = request.headers.get('X-API-Key') or request.args.get('api_key')
                
                if not provided_key or provided_key != required_key:
                    return jsonify({
                        'error': 'Authentication required',
                        'message': 'Valid API key required'
                    }), 401
                
                return f(*args, **kwargs)
            return decorated_function
        return decorator
    
    def secure_headers(self, response):
        """Add security headers to response"""
        if self.app.config.get('FLASK_ENV') == 'production':
            # HTTPS enforcement
            response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains; preload'
            
            # XSS Protection
            response.headers['X-Content-Type-Options'] = 'nosniff'
            response.headers['X-Frame-Options'] = 'DENY'
            response.headers['X-XSS-Protection'] = '1; mode=block'
            
            # Content Security Policy for PWA
            csp_policy = (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline' https://unpkg.com; "
                "style-src 'self' 'unsafe-inline' https://unpkg.com; "
                "img-src 'self' data: https:; "
                "connect-src 'self' https://api.open-meteo.com https://api.openweathermap.org; "
                "manifest-src 'self'; "
                "worker-src 'self'; "
                "font-src 'self' data:;"
            )
            response.headers['Content-Security-Policy'] = csp_policy
            
            # Referrer Policy
            response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
            
            # Permissions Policy
            response.headers['Permissions-Policy'] = 'geolocation=(self), camera=(), microphone=()'
        
        return response
    
    def validate_input(self, input_data, max_length=1000):
        """Validate and sanitize input data"""
        if not isinstance(input_data, str):
            return str(input_data)[:max_length]
        
        # Remove potentially dangerous characters
        dangerous_chars = ['<', '>', '"', "'", '&', ';', '(', ')', '|', '`']
        sanitized = input_data
        
        for char in dangerous_chars:
            sanitized = sanitized.replace(char, '')
        
        return sanitized[:max_length]
    
    def log_security_event(self, event_type, details=None):
        """Log security events"""
        if self.app:
            self.app.logger.warning(f"Security Event: {event_type} - {details}")
    
    def check_request_size(self, max_size_mb=10):
        """Check request size to prevent large payload attacks"""
        def decorator(f):
            @wraps(f)
            def decorated_function(*args, **kwargs):
                content_length = request.content_length
                
                if content_length and content_length > max_size_mb * 1024 * 1024:
                    self.log_security_event('Large request blocked', f'Size: {content_length}')
                    return jsonify({
                        'error': 'Request too large',
                        'message': f'Request size exceeds {max_size_mb}MB limit'
                    }), 413
                
                return f(*args, **kwargs)
            return decorated_function
        return decorator

# Global security manager instance
security_manager = SecurityManager()

def init_security(app):
    """Initialize security for the Flask app"""
    security_manager.init_app(app)
    
    # Add security headers to all responses
    @app.after_request
    def add_security_headers(response):
        return security_manager.secure_headers(response)
    
    # Force HTTPS in production
    if app.config.get('FLASK_ENV') == 'production':
        @app.before_request
        def force_https():
            if not request.is_secure and request.headers.get('X-Forwarded-Proto') != 'https':
                # Allow health checks without HTTPS
                if request.endpoint in ['health_check', 'readiness_check']:
                    return
                
                return redirect(request.url.replace('http://', 'https://'), code=301)
    
    return security_manager