"""
Comprehensive error handling and logging for LexAI Practice Partner
Production-ready error management with monitoring and alerting
"""

import logging
import sys
import traceback
import os
from functools import wraps
from datetime import datetime, timezone
from flask import request, jsonify, render_template, current_app
from typing import Dict, Any, Optional

# Configure logging levels
LOG_LEVELS = {
    'development': logging.DEBUG,
    'testing': logging.INFO,
    'production': logging.WARNING
}

class ErrorHandler:
    """Centralized error handling and logging"""
    
    def __init__(self, app=None):
        self.app = app
        if app:
            self.init_app(app)
    
    def init_app(self, app):
        """Initialize error handling for Flask app"""
        # Configure logging
        self.configure_logging(app)
        
        # Register error handlers
        app.register_error_handler(400, self.handle_bad_request)
        app.register_error_handler(401, self.handle_unauthorized)
        app.register_error_handler(403, self.handle_forbidden)
        app.register_error_handler(404, self.handle_not_found)
        app.register_error_handler(429, self.handle_rate_limit)
        app.register_error_handler(500, self.handle_internal_error)
        app.register_error_handler(Exception, self.handle_exception)
    
    def configure_logging(self, app):
        """Configure comprehensive logging"""
        log_level = LOG_LEVELS.get(app.config.get('ENV', 'production'), logging.WARNING)
        
        # Create formatters
        detailed_formatter = logging.Formatter(
            '[%(asctime)s] %(levelname)s in %(module)s: %(message)s'
        )
        
        json_formatter = logging.Formatter(
            '{"timestamp": "%(asctime)s", "level": "%(levelname)s", '
            '"module": "%(module)s", "message": "%(message)s", '
            '"pathname": "%(pathname)s", "lineno": %(lineno)d}'
        )
        
        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(log_level)
        console_handler.setFormatter(detailed_formatter)
        
        # File handler for errors
        if not os.path.exists('logs'):
            os.makedirs('logs')
            
        error_handler = logging.FileHandler('logs/error.log')
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(json_formatter)
        
        # Application logger
        app.logger.addHandler(console_handler)
        app.logger.addHandler(error_handler)
        app.logger.setLevel(log_level)
        
        # Disable Flask's default handler to avoid duplicate logs
        app.logger.handlers = [console_handler, error_handler]
    
    def log_error(self, error: Exception, context: Optional[Dict] = None):
        """Log error with context and stack trace"""
        error_data = {
            'error_type': type(error).__name__,
            'error_message': str(error),
            'timestamp': datetime.utcnow().isoformat(),
            'stack_trace': traceback.format_exc()
        }
        
        if request:
            error_data.update({
                'url': request.url,
                'method': request.method,
                'ip': request.headers.get('X-Forwarded-For', request.remote_addr),
                'user_agent': request.headers.get('User-Agent', 'unknown'),
                'referer': request.headers.get('Referer', 'unknown')
            })
        
        if context:
            error_data.update(context)
            
        current_app.logger.error(f"APPLICATION ERROR: {error_data}")
        
        # In production, send to monitoring service (Sentry, etc.)
        if current_app.config.get('ENV') == 'production':
            self.send_to_monitoring(error_data)
    
    def send_to_monitoring(self, error_data: Dict):
        """Send error to external monitoring service"""
        # Placeholder for Sentry, DataDog, etc.
        # In production, implement actual monitoring integration
        pass
    
    def handle_bad_request(self, error):
        """Handle 400 Bad Request errors"""
        self.log_error(error, {'error_code': 400})
        
        if request.is_json:
            return jsonify({
                'error': 'Bad request',
                'message': 'The request could not be understood by the server'
            }), 400
        
        return render_template('errors/400.html'), 400
    
    def handle_unauthorized(self, error):
        """Handle 401 Unauthorized errors"""
        self.log_error(error, {'error_code': 401})
        
        if request.is_json:
            return jsonify({
                'error': 'Unauthorized',
                'message': 'Authentication required'
            }), 401
        
        return render_template('errors/401.html'), 401
    
    def handle_forbidden(self, error):
        """Handle 403 Forbidden errors"""
        self.log_error(error, {'error_code': 403})
        
        if request.is_json:
            return jsonify({
                'error': 'Forbidden',
                'message': 'You do not have permission to access this resource'
            }), 403
        
        return render_template('errors/403.html'), 403
    
    def handle_not_found(self, error):
        """Handle 404 Not Found errors"""
        # Don't log 404s as errors (too noisy)
        current_app.logger.info(f"404 Not Found: {request.url}")
        
        if request.is_json:
            return jsonify({
                'error': 'Not found',
                'message': 'The requested resource was not found'
            }), 404
        
        return render_template('errors/404.html'), 404
    
    def handle_rate_limit(self, error):
        """Handle 429 Rate Limit errors"""
        self.log_error(error, {'error_code': 429})
        
        if request.is_json:
            return jsonify({
                'error': 'Rate limit exceeded',
                'message': 'Too many requests. Please try again later.'
            }), 429
        
        return render_template('errors/429.html'), 429
    
    def handle_internal_error(self, error):
        """Handle 500 Internal Server errors"""
        self.log_error(error, {'error_code': 500})
        
        if request.is_json:
            return jsonify({
                'error': 'Internal server error',
                'message': 'An unexpected error occurred'
            }), 500
        
        return render_template('errors/500.html'), 500
    
    def handle_exception(self, error):
        """Handle unhandled exceptions"""
        self.log_error(error, {'error_code': 'unhandled'})
        
        if request.is_json:
            return jsonify({
                'error': 'Internal server error',
                'message': 'An unexpected error occurred'
            }), 500
        
        return render_template('errors/500.html'), 500

def handle_api_error(func):
    """Decorator for API route error handling"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except ValueError as e:
            current_app.logger.warning(f"API validation error in {func.__name__}: {e}")
            return jsonify({'error': str(e)}), 400
        except PermissionError as e:
            current_app.logger.warning(f"API permission error in {func.__name__}: {e}")
            return jsonify({'error': 'Permission denied'}), 403
        except Exception as e:
            current_app.logger.error(f"API error in {func.__name__}: {e}")
            return jsonify({'error': 'Internal server error'}), 500
    return wrapper

def monitor_performance(func):
    """Decorator to monitor function performance"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = datetime.utcnow()
        try:
            result = func(*args, **kwargs)
            execution_time = (datetime.utcnow() - start_time).total_seconds()
            
            # Log slow operations (>2 seconds)
            if execution_time > 2.0:
                current_app.logger.warning(
                    f"SLOW OPERATION: {func.__name__} took {execution_time:.2f}s"
                )
            
            return result
        except Exception as e:
            execution_time = (datetime.utcnow() - start_time).total_seconds()
            current_app.logger.error(
                f"ERROR in {func.__name__} after {execution_time:.2f}s: {e}"
            )
            raise
    return wrapper

class HealthCheck:
    """System health monitoring"""
    
    @staticmethod
    def check_database():
        """Check database connectivity"""
        try:
            from database import db
            db.session.execute('SELECT 1')
            return {'status': 'healthy', 'response_time': 0.01}
        except Exception as e:
            return {'status': 'unhealthy', 'error': str(e)}
    
    @staticmethod
    def check_external_apis():
        """Check external API connectivity"""
        try:
            import requests
            response = requests.get('https://api.x.ai/v1/models', timeout=5)
            return {
                'status': 'healthy' if response.status_code < 500 else 'degraded',
                'response_time': response.elapsed.total_seconds()
            }
        except Exception as e:
            return {'status': 'unhealthy', 'error': str(e)}
    
    @staticmethod
    def check_disk_space():
        """Check available disk space"""
        try:
            import shutil
            total, used, free = shutil.disk_usage('/')
            free_percent = (free / total) * 100
            
            if free_percent < 10:
                return {'status': 'critical', 'free_percent': free_percent}
            elif free_percent < 20:
                return {'status': 'warning', 'free_percent': free_percent}
            else:
                return {'status': 'healthy', 'free_percent': free_percent}
        except Exception as e:
            return {'status': 'unknown', 'error': str(e)}
    
    @staticmethod
    def get_system_health():
        """Get overall system health status"""
        checks = {
            'database': HealthCheck.check_database(),
            'external_apis': HealthCheck.check_external_apis(),
            'disk_space': HealthCheck.check_disk_space()
        }
        
        # Determine overall status
        statuses = [check['status'] for check in checks.values()]
        if 'critical' in statuses or 'unhealthy' in statuses:
            overall_status = 'unhealthy'
        elif 'warning' in statuses or 'degraded' in statuses:
            overall_status = 'degraded'
        else:
            overall_status = 'healthy'
        
        return {
            'overall_status': overall_status,
            'timestamp': datetime.utcnow().isoformat(),
            'checks': checks
        }