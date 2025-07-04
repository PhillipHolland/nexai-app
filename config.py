"""
Production-ready configuration management for LexAI Practice Partner
Handles environment-specific settings, security, and deployment configurations
"""

import os
import secrets
import logging
from urllib.parse import urlparse
from typing import Optional, Dict, Any

class Config:
    """Base configuration class with common settings"""
    
    # Security
    SECRET_KEY = os.environ.get('SECRET_KEY') or secrets.token_urlsafe(32)
    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = 3600  # 1 hour
    
    # Session configuration
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    PERMANENT_SESSION_LIFETIME = 86400  # 24 hours
    
    # Database
    DATABASE_URL = os.environ.get('DATABASE_URL')
    SQLALCHEMY_DATABASE_URI = DATABASE_URL or 'sqlite:///lexai_platform.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,
        'pool_recycle': 300,
        'pool_timeout': 30,
        'max_overflow': 10
    }
    
    # File uploads
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB
    UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER', '/tmp/uploads')
    ALLOWED_EXTENSIONS = {'txt', 'pdf', 'doc', 'docx', 'rtf', 'odt'}
    
    # API Configuration
    XAI_API_KEY = os.environ.get('XAI_API_KEY')
    XAI_MODEL = os.environ.get('XAI_MODEL', 'grok-3-latest')
    API_TIMEOUT = int(os.environ.get('API_TIMEOUT', '30'))
    
    # Rate limiting
    RATELIMIT_STORAGE_URL = os.environ.get('REDIS_URL', 'memory://')
    RATELIMIT_DEFAULT = "100 per hour"
    
    # Logging
    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')
    LOG_FILE = os.environ.get('LOG_FILE', 'lexai.log')
    
    # Email configuration (for password resets, notifications)
    MAIL_SERVER = os.environ.get('MAIL_SERVER')
    MAIL_PORT = int(os.environ.get('MAIL_PORT', '587'))
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'true').lower() == 'true'
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER')
    
    # Feature flags
    ENABLE_REGISTRATION = os.environ.get('ENABLE_REGISTRATION', 'true').lower() == 'true'
    ENABLE_PASSWORD_RESET = os.environ.get('ENABLE_PASSWORD_RESET', 'true').lower() == 'true'
    ENABLE_DOCUMENT_UPLOAD = os.environ.get('ENABLE_DOCUMENT_UPLOAD', 'true').lower() == 'true'
    
    # Monitoring and analytics
    SENTRY_DSN = os.environ.get('SENTRY_DSN')
    GOOGLE_ANALYTICS_ID = os.environ.get('GOOGLE_ANALYTICS_ID')
    
    @staticmethod
    def init_app(app):
        """Initialize app-specific configuration"""
        pass
    
    @classmethod
    def validate_config(cls) -> Dict[str, Any]:
        """Validate configuration and return validation results"""
        errors = []
        warnings = []
        
        # Required environment variables (only XAI_API_KEY is truly required)
        required_vars = {
            'XAI_API_KEY': cls.XAI_API_KEY
        }
        
        # Recommended variables
        recommended_vars = {
            'SECRET_KEY': cls.SECRET_KEY,
            'DATABASE_URL': cls.DATABASE_URL
        }
        
        for var_name, var_value in required_vars.items():
            if not var_value:
                errors.append(f"Missing required environment variable: {var_name}")
        
        # Check recommended variables
        for var_name, var_value in recommended_vars.items():
            if not var_value:
                warnings.append(f"Recommended environment variable not set: {var_name}")
        
        # Database URL validation  
        database_url = cls.DATABASE_URL or cls.SQLALCHEMY_DATABASE_URI
        if database_url and database_url != 'sqlite:///lexai_platform.db':
            try:
                parsed = urlparse(database_url)
                if not parsed.scheme:
                    errors.append("DATABASE_URL must include a scheme (postgresql://, sqlite://, etc.)")
            except Exception as e:
                errors.append(f"Invalid DATABASE_URL format: {e}")
        
        # Upload folder validation
        if not os.path.exists(cls.UPLOAD_FOLDER):
            try:
                os.makedirs(cls.UPLOAD_FOLDER, exist_ok=True)
                warnings.append(f"Created upload folder: {cls.UPLOAD_FOLDER}")
            except Exception as e:
                errors.append(f"Cannot create upload folder {cls.UPLOAD_FOLDER}: {e}")
        
        # Email configuration warnings
        if not cls.MAIL_SERVER and cls.ENABLE_PASSWORD_RESET:
            warnings.append("Email server not configured, password reset will not work")
        
        return {
            'valid': len(errors) == 0,
            'errors': errors,
            'warnings': warnings
        }

class DevelopmentConfig(Config):
    """Development configuration"""
    DEBUG = True
    TESTING = False
    
    # Less strict security for development
    SESSION_COOKIE_SECURE = False
    WTF_CSRF_ENABLED = False
    
    # Development database
    if not Config.DATABASE_URL:
        SQLALCHEMY_DATABASE_URI = 'sqlite:///lexai_dev.db'
    else:
        SQLALCHEMY_DATABASE_URI = Config.DATABASE_URL
    
    # Development logging
    LOG_LEVEL = 'DEBUG'
    
    @staticmethod
    def init_app(app):
        """Development-specific initialization"""
        logging.basicConfig(
            level=logging.DEBUG,
            format='%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
        )

class ProductionConfig(Config):
    """Production configuration"""
    DEBUG = False
    TESTING = False
    
    # Production database with connection pooling
    SQLALCHEMY_DATABASE_URI = Config.DATABASE_URL
    
    # Strict security settings
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Strict'
    
    # Production logging
    LOG_LEVEL = 'WARNING'
    
    @staticmethod
    def init_app(app):
        """Production-specific initialization"""
        # Configure logging for production
        import logging
        from logging.handlers import RotatingFileHandler, SMTPHandler
        
        # File handler
        if not os.path.exists('logs'):
            os.mkdir('logs')
        
        file_handler = RotatingFileHandler(
            'logs/lexai.log', maxBytes=10240000, backupCount=10
        )
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
        ))
        file_handler.setLevel(logging.INFO)
        app.logger.addHandler(file_handler)
        
        # Email error handler
        if Config.MAIL_SERVER:
            auth = None
            if Config.MAIL_USERNAME and Config.MAIL_PASSWORD:
                auth = (Config.MAIL_USERNAME, Config.MAIL_PASSWORD)
            
            secure = None
            if Config.MAIL_USE_TLS:
                secure = ()
            
            mail_handler = SMTPHandler(
                mailhost=(Config.MAIL_SERVER, Config.MAIL_PORT),
                fromaddr=Config.MAIL_DEFAULT_SENDER,
                toaddrs=[Config.MAIL_DEFAULT_SENDER],
                subject='LexAI Application Error',
                credentials=auth,
                secure=secure
            )
            mail_handler.setLevel(logging.ERROR)
            app.logger.addHandler(mail_handler)
        
        app.logger.setLevel(logging.INFO)
        app.logger.info('LexAI startup')

class TestingConfig(Config):
    """Testing configuration"""
    DEBUG = True
    TESTING = True
    
    # In-memory database for testing
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    
    # Disable CSRF for testing
    WTF_CSRF_ENABLED = False
    
    # Fast password hashing for tests
    BCRYPT_LOG_ROUNDS = 4
    
    @staticmethod
    def init_app(app):
        """Testing-specific initialization"""
        pass

# Configuration mapping
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}

def get_config(config_name: Optional[str] = None) -> Config:
    """Get configuration class based on environment"""
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'default')
    
    return config.get(config_name, config['default'])

def validate_environment() -> Dict[str, Any]:
    """Validate current environment configuration"""
    current_config = get_config()
    return current_config.validate_config()

# Security utilities
def generate_secret_key() -> str:
    """Generate a secure secret key"""
    return secrets.token_urlsafe(32)

def is_production() -> bool:
    """Check if running in production environment"""
    return os.environ.get('FLASK_ENV') == 'production'

def is_development() -> bool:
    """Check if running in development environment"""
    env = os.environ.get('FLASK_ENV', 'development')
    return env in ['development', 'default']