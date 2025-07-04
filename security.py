"""
Security middleware and validation for LexAI Practice Partner
Comprehensive input validation, rate limiting, and security headers
"""

import re
import logging
from functools import wraps
from flask import request, jsonify, g
from datetime import datetime, timedelta
import hashlib
import time
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)

# Security configuration
MAX_MESSAGE_LENGTH = 5000
MAX_UPLOAD_SIZE = 50 * 1024 * 1024  # 50MB
ALLOWED_FILE_TYPES = {'pdf', 'doc', 'docx', 'txt', 'rtf', 'odt'}
RATE_LIMIT_REQUESTS = 100  # requests per window
RATE_LIMIT_WINDOW = 3600  # 1 hour in seconds

# Security patterns
SQL_INJECTION_PATTERNS = [
    r"(\bUNION\b.*\bSELECT\b)",
    r"(\bSELECT\b.*\bFROM\b)",
    r"(\bINSERT\b.*\bINTO\b)",
    r"(\bUPDATE\b.*\bSET\b)",
    r"(\bDELETE\b.*\bFROM\b)",
    r"(\bDROP\b.*\bTABLE\b)",
    r"(\';.*--)",
    r"(\bOR\b.*=.*)",
    r"(\bAND\b.*=.*)"
]

XSS_PATTERNS = [
    r"<script[^>]*>.*?</script>",
    r"<iframe[^>]*>.*?</iframe>",
    r"javascript:",
    r"vbscript:",
    r"onload\s*=",
    r"onerror\s*=",
    r"onclick\s*=",
    r"onmouseover\s*="
]

# Rate limiting storage (in production, use Redis)
rate_limit_storage: Dict[str, List[float]] = {}

class SecurityValidator:
    """Input validation and security checks"""
    
    @staticmethod
    def validate_message(message: str) -> Dict[str, Any]:
        """Validate chat message input"""
        errors = []
        
        # Length check
        if not message or len(message.strip()) == 0:
            errors.append("Message cannot be empty")
            
        if len(message) > MAX_MESSAGE_LENGTH:
            errors.append(f"Message too long (max {MAX_MESSAGE_LENGTH} characters)")
            
        # SQL injection check
        message_upper = message.upper()
        for pattern in SQL_INJECTION_PATTERNS:
            if re.search(pattern, message_upper, re.IGNORECASE):
                errors.append("Potentially malicious content detected")
                logger.warning(f"SQL injection attempt: {message[:100]}")
                break
                
        # XSS check
        for pattern in XSS_PATTERNS:
            if re.search(pattern, message, re.IGNORECASE):
                errors.append("Potentially malicious content detected")
                logger.warning(f"XSS attempt: {message[:100]}")
                break
                
        return {
            'valid': len(errors) == 0,
            'errors': errors,
            'sanitized': SecurityValidator.sanitize_input(message)
        }
    
    @staticmethod
    def validate_file_upload(filename: str, file_size: int) -> Dict[str, Any]:
        """Validate file upload"""
        errors = []
        
        if not filename:
            errors.append("Filename is required")
            return {'valid': False, 'errors': errors}
            
        # File extension check
        ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
        if ext not in ALLOWED_FILE_TYPES:
            errors.append(f"File type not allowed. Allowed: {', '.join(ALLOWED_FILE_TYPES)}")
            
        # File size check
        if file_size > MAX_UPLOAD_SIZE:
            errors.append(f"File too large (max {MAX_UPLOAD_SIZE // 1024 // 1024}MB)")
            
        # Filename security check
        if re.search(r'[<>:"/\\|?*]', filename):
            errors.append("Filename contains invalid characters")
            
        return {
            'valid': len(errors) == 0,
            'errors': errors,
            'safe_filename': SecurityValidator.sanitize_filename(filename)
        }
    
    @staticmethod
    def sanitize_input(text: str) -> str:
        """Sanitize user input"""
        if not text:
            return ""
            
        # Remove control characters
        text = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', text)
        
        # Normalize whitespace
        text = re.sub(r'\s+', ' ', text)
        
        # Trim
        return text.strip()
    
    @staticmethod
    def sanitize_filename(filename: str) -> str:
        """Sanitize filename for safe storage"""
        if not filename:
            return "untitled"
            
        # Remove path components
        filename = filename.split('/')[-1].split('\\')[-1]
        
        # Remove dangerous characters
        filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
        
        # Ensure reasonable length
        if len(filename) > 255:
            name, ext = filename.rsplit('.', 1) if '.' in filename else (filename, '')
            filename = name[:250] + ('.' + ext if ext else '')
            
        return filename

class RateLimiter:
    """Rate limiting functionality"""
    
    @staticmethod
    def get_client_id(request) -> str:
        """Get unique client identifier"""
        # In production, consider using user ID if authenticated
        ip = request.headers.get('X-Forwarded-For', request.remote_addr)
        user_agent = request.headers.get('User-Agent', '')
        return hashlib.md5(f"{ip}:{user_agent}".encode()).hexdigest()
    
    @staticmethod
    def is_rate_limited(client_id: str) -> bool:
        """Check if client is rate limited"""
        now = time.time()
        window_start = now - RATE_LIMIT_WINDOW
        
        # Clean old entries
        if client_id in rate_limit_storage:
            rate_limit_storage[client_id] = [
                timestamp for timestamp in rate_limit_storage[client_id]
                if timestamp > window_start
            ]
        else:
            rate_limit_storage[client_id] = []
        
        # Check rate limit
        request_count = len(rate_limit_storage[client_id])
        if request_count >= RATE_LIMIT_REQUESTS:
            logger.warning(f"Rate limit exceeded for client: {client_id}")
            return True
            
        # Add current request
        rate_limit_storage[client_id].append(now)
        return False

def security_headers(response):
    """Add security headers to response"""
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    response.headers['Content-Security-Policy'] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.jsdelivr.net https://unpkg.com https://cdnjs.cloudflare.com; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://cdn.jsdelivr.net https://unpkg.com https://cdnjs.cloudflare.com; "
        "font-src 'self' https://fonts.gstatic.com https://fonts.googleapis.com; "
        "img-src 'self' data: https:; "
        "connect-src 'self' https://api.x.ai https://fonts.googleapis.com https://fonts.gstatic.com"
    )
    return response

def rate_limit_decorator(f):
    """Rate limiting decorator"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        client_id = RateLimiter.get_client_id(request)
        
        if RateLimiter.is_rate_limited(client_id):
            return jsonify({
                'error': 'Rate limit exceeded. Please try again later.',
                'retry_after': RATE_LIMIT_WINDOW
            }), 429
            
        return f(*args, **kwargs)
    return decorated_function

def validate_json_input(required_fields: List[str] = None):
    """Decorator for JSON input validation"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not request.is_json:
                return jsonify({'error': 'Content-Type must be application/json'}), 400
                
            data = request.get_json()
            if not data:
                return jsonify({'error': 'No JSON data provided'}), 400
                
            # Check required fields
            if required_fields:
                missing_fields = [field for field in required_fields if field not in data]
                if missing_fields:
                    return jsonify({
                        'error': f'Missing required fields: {", ".join(missing_fields)}'
                    }), 400
            
            # Store validated data in g for use in route
            g.validated_data = data
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def log_security_event(event_type: str, details: str, client_info: Optional[Dict] = None):
    """Log security events for monitoring"""
    log_data = {
        'timestamp': datetime.utcnow().isoformat(),
        'event_type': event_type,
        'details': details,
        'ip': request.headers.get('X-Forwarded-For', request.remote_addr) if request else 'unknown',
        'user_agent': request.headers.get('User-Agent', 'unknown') if request else 'unknown'
    }
    
    if client_info:
        log_data.update(client_info)
        
    logger.warning(f"SECURITY EVENT: {log_data}")