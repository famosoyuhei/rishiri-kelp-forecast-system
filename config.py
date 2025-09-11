"""
Configuration settings for Rishiri Kelp Forecast System
利尻島昆布干場予報システム設定
"""

import os
from datetime import timedelta

class Config:
    """Base configuration"""
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    
    # Flask settings
    FLASK_ENV = os.environ.get('FLASK_ENV', 'development')
    DEBUG = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    
    # API Keys
    OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')
    WEATHER_API_KEY = os.environ.get('WEATHER_API_KEY')
    
    # Database
    DATABASE_URL = os.environ.get('DATABASE_URL')
    REDIS_URL = os.environ.get('REDIS_URL')
    
    # CORS settings
    CORS_ORIGINS = os.environ.get('CORS_ORIGINS', '*').split(',')
    
    # Rate limiting
    RATE_LIMIT_PER_MINUTE = int(os.environ.get('RATE_LIMIT_PER_MINUTE', '60'))
    
    # Cache settings
    CACHE_EXPIRE_HOURS = int(os.environ.get('CACHE_EXPIRE_HOURS', '6'))
    MAX_CACHE_SIZE_MB = int(os.environ.get('MAX_CACHE_SIZE_MB', '100'))
    
    # Geography settings (Rishiri Island)
    DEFAULT_LAT = float(os.environ.get('DEFAULT_LAT', '45.178269'))
    DEFAULT_LON = float(os.environ.get('DEFAULT_LON', '141.228528'))
    SERVICE_AREA_RADIUS_KM = int(os.environ.get('SERVICE_AREA_RADIUS_KM', '50'))
    
    # PWA settings
    PWA_MANIFEST_START_URL = os.environ.get('PWA_MANIFEST_START_URL', '/')
    PWA_MANIFEST_SCOPE = os.environ.get('PWA_MANIFEST_SCOPE', '/')
    PWA_THEME_COLOR = os.environ.get('PWA_THEME_COLOR', '#667eea')
    PWA_BACKGROUND_COLOR = os.environ.get('PWA_BACKGROUND_COLOR', '#ffffff')
    
    # Logging
    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')
    
    # Performance
    MAX_WORKERS = int(os.environ.get('MAX_WORKERS', '2'))
    WORKER_TIMEOUT = int(os.environ.get('WORKER_TIMEOUT', '120'))
    STATIC_FILE_CACHE_SECONDS = int(os.environ.get('STATIC_FILE_CACHE_SECONDS', '86400'))
    
    # External services
    EMAIL_SMTP_SERVER = os.environ.get('EMAIL_SMTP_SERVER', 'smtp.gmail.com')
    EMAIL_SMTP_PORT = int(os.environ.get('EMAIL_SMTP_PORT', '587'))
    EMAIL_USERNAME = os.environ.get('EMAIL_USERNAME')
    EMAIL_PASSWORD = os.environ.get('EMAIL_PASSWORD')
    
    # Monitoring
    SENTRY_DSN = os.environ.get('SENTRY_DSN')
    
    # Notification settings
    NOTIFICATION_RATE_LIMIT = int(os.environ.get('NOTIFICATION_RATE_LIMIT', '10'))
    SMS_API_KEY = os.environ.get('SMS_API_KEY')
    LINE_CHANNEL_SECRET = os.environ.get('LINE_CHANNEL_SECRET')
    LINE_CHANNEL_ACCESS_TOKEN = os.environ.get('LINE_CHANNEL_ACCESS_TOKEN')


class DevelopmentConfig(Config):
    """Development configuration"""
    DEBUG = True
    FLASK_ENV = 'development'
    
    # More verbose logging for development
    LOG_LEVEL = 'DEBUG'
    
    # Relaxed CORS for development
    CORS_ORIGINS = ['*']


class ProductionConfig(Config):
    """Production configuration"""
    DEBUG = False
    FLASK_ENV = 'production'
    
    # Strict CORS for production
    CORS_ORIGINS = os.environ.get('CORS_ORIGINS', 'https://rishiri-kelp.com').split(',')
    
    # Enhanced security
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    
    # Performance optimizations
    SEND_FILE_MAX_AGE_DEFAULT = timedelta(hours=24)
    
    # Reduced rate limiting for production
    RATE_LIMIT_PER_MINUTE = int(os.environ.get('RATE_LIMIT_PER_MINUTE', '30'))


class TestingConfig(Config):
    """Testing configuration"""
    TESTING = True
    WTF_CSRF_ENABLED = False
    
    # Use in-memory database for testing
    DATABASE_URL = 'sqlite:///:memory:'
    
    # Disable external API calls during testing
    OPENAI_API_KEY = 'test-key'
    WEATHER_API_KEY = 'test-key'


# Configuration dictionary
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}

def get_config():
    """Get configuration based on environment"""
    env = os.environ.get('FLASK_ENV', 'development')
    return config.get(env, config['default'])