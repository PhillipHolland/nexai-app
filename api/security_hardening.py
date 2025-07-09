#!/usr/bin/env python3
"""
Security Hardening Module
Production-ready security enhancements for LexAI deployment
"""

import os
import re
import time
import hmac
import hashlib
import secrets
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from functools import wraps
from collections import defaultdict, deque
import ipaddress
import bleach
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

class RateLimiter:
    """Advanced rate limiting with multiple strategies."""
    
    def __init__(self):
        self.request_history = defaultdict(lambda: deque(maxlen=1000))
        self.blocked_ips = {}
        self.rate_limits = {
            'default': {'requests': 100, 'window': 3600},      # 100 req/hour
            'api': {'requests': 1000, 'window': 3600},         # 1000 req/hour for API
            'auth': {'requests': 10, 'window': 900},           # 10 auth attempts per 15 min
            'upload': {'requests': 50, 'window': 3600},        # 50 uploads per hour
            'search': {'requests': 200, 'window': 3600}        # 200 searches per hour
        }
    
    def is_rate_limited(self, identifier: str, endpoint_type: str = 'default') -> Tuple[bool, Dict[str, Any]]:
        """Check if request should be rate limited."""
        now = time.time()
        
        # Check if IP is blocked
        if identifier in self.blocked_ips:
            if now < self.blocked_ips[identifier]['until']:
                return True, {
                    'blocked': True,
                    'reason': 'IP temporarily blocked',
                    'retry_after': self.blocked_ips[identifier]['until'] - now
                }
            else:
                # Unblock expired blocks
                del self.blocked_ips[identifier]
        
        # Get rate limit configuration
        limit_config = self.rate_limits.get(endpoint_type, self.rate_limits['default'])
        window_start = now - limit_config['window']
        
        # Clean old requests
        request_times = self.request_history[identifier]
        while request_times and request_times[0] < window_start:
            request_times.popleft()
        
        # Check if limit exceeded
        if len(request_times) >= limit_config['requests']:
            # Check for aggressive behavior (block IP)
            if len(request_times) >= limit_config['requests'] * 1.5:
                self.blocked_ips[identifier] = {
                    'until': now + 3600,  # Block for 1 hour
                    'reason': 'Aggressive rate limit violation'
                }
                logger.warning(f"IP {identifier} blocked for aggressive behavior")
            
            return True, {
                'rate_limited': True,
                'limit': limit_config['requests'],
                'window': limit_config['window'],
                'retry_after': request_times[0] + limit_config['window'] - now
            }
        
        # Record this request
        request_times.append(now)
        
        return False, {
            'remaining': limit_config['requests'] - len(request_times),
            'reset_time': window_start + limit_config['window']
        }

class InputSanitizer:
    """Comprehensive input sanitization and validation."""
    
    def __init__(self):
        # Dangerous patterns for various injection types
        self.dangerous_patterns = {
            'sql_injection': [
                r"(\bunion\b.*\bselect\b)",
                r"(\bdrop\b.*\btable\b)",
                r"(\bdelete\b.*\bfrom\b)",
                r"(\binsert\b.*\binto\b)",
                r"(\bupdate\b.*\bset\b)",
                r"(\bexec\b.*\()",
                r"(\bexecute\b.*\()",
                r"(\bsp_\w+)",
                r"(\bxp_\w+)",
                r"('.*'.*=.*'.*')",
                r"(;\s*--)",
                r"(/*.**/)"
            ],
            'xss': [
                r"(<script[^>]*>)",
                r"(</script>)",
                r"(javascript:)",
                r"(vbscript:)",
                r"(onload\s*=)",
                r"(onerror\s*=)",
                r"(onclick\s*=)",
                r"(onmouseover\s*=)",
                r"(<iframe[^>]*>)",
                r"(<object[^>]*>)",
                r"(<embed[^>]*>)",
                r"(<link[^>]*>)",
                r"(<meta[^>]*>)"
            ],
            'path_traversal': [
                r"(\.\.[\\/])",
                r"([\\/]\.\.)",
                r"(\.\.%2f)",
                r"(\.\.%5c)",
                r"(%2e%2e)",
                r"(\/etc\/passwd)",
                r"(\/proc\/)",
                r"(C:\\Windows)",
                r"(\.\.\\)",
                r"(\.\.\/)"
            ],
            'command_injection': [
                r"(;\s*\w+)",
                r"(\|\s*\w+)",
                r"(&\s*\w+)",
                r"(\$\([^)]*\))",
                r"(`[^`]*`)",
                r"(>\s*\/)",
                r"(<\s*\/)",
                r"(nc\s+-)",
                r"(wget\s+)",
                r"(curl\s+)"
            ],
            'ldap_injection': [
                r"(\*\))",
                r"(\|\()",
                r"(&\()",
                r"(\)\()",
                r"(!\()"
            ]
        }
        
        # Allowed HTML tags and attributes for rich text
        self.allowed_tags = [
            'p', 'br', 'strong', 'b', 'em', 'i', 'u', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
            'ul', 'ol', 'li', 'blockquote', 'a', 'img'
        ]
        
        self.allowed_attributes = {
            'a': ['href', 'title'],
            'img': ['src', 'alt', 'title', 'width', 'height'],
            '*': ['class']
        }
    
    def sanitize_html(self, content: str) -> str:
        """Sanitize HTML content to prevent XSS."""
        if not content:
            return content
        
        return bleach.clean(
            content,
            tags=self.allowed_tags,
            attributes=self.allowed_attributes,
            strip=True
        )
    
    def validate_input(self, input_data: str, input_type: str = 'general') -> Tuple[bool, List[str]]:
        """Validate input for malicious patterns."""
        if not input_data:
            return True, []
        
        threats_detected = []
        input_lower = input_data.lower()
        
        # Check all dangerous patterns
        for threat_type, patterns in self.dangerous_patterns.items():
            for pattern in patterns:
                if re.search(pattern, input_lower, re.IGNORECASE | re.MULTILINE):
                    threats_detected.append(threat_type)
                    logger.warning(f"Detected {threat_type} pattern in input: {pattern}")
                    break
        
        # Additional validation based on input type
        if input_type == 'email':
            if not self._validate_email(input_data):
                threats_detected.append('invalid_email')
        
        elif input_type == 'url':
            if not self._validate_url(input_data):
                threats_detected.append('invalid_url')
        
        elif input_type == 'filename':
            if not self._validate_filename(input_data):
                threats_detected.append('invalid_filename')
        
        return len(threats_detected) == 0, threats_detected
    
    def _validate_email(self, email: str) -> bool:
        """Validate email format."""
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return re.match(pattern, email) is not None
    
    def _validate_url(self, url: str) -> bool:
        """Validate URL format and scheme."""
        try:
            parsed = urlparse(url)
            return parsed.scheme in ['http', 'https'] and parsed.netloc
        except:
            return False
    
    def _validate_filename(self, filename: str) -> bool:
        """Validate filename for security."""
        # Check for path traversal
        if '..' in filename or '/' in filename or '\\' in filename:
            return False
        
        # Check for dangerous extensions
        dangerous_extensions = [
            '.exe', '.bat', '.cmd', '.com', '.pif', '.scr', '.vbs', '.js',
            '.jar', '.sh', '.py', '.pl', '.php', '.asp', '.aspx', '.jsp'
        ]
        
        file_ext = os.path.splitext(filename)[1].lower()
        return file_ext not in dangerous_extensions
    
    def sanitize_for_database(self, input_data: str) -> str:
        """Sanitize input for database storage."""
        if not input_data:
            return input_data
        
        # Remove null bytes and control characters
        sanitized = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', input_data)
        
        # Normalize whitespace
        sanitized = ' '.join(sanitized.split())
        
        return sanitized

class CSRFProtection:
    """CSRF token generation and validation."""
    
    def __init__(self, secret_key: str):
        self.secret_key = secret_key.encode() if isinstance(secret_key, str) else secret_key
    
    def generate_token(self, session_id: str) -> str:
        """Generate CSRF token for session."""
        timestamp = str(int(time.time()))
        token_data = f"{session_id}:{timestamp}"
        
        signature = hmac.new(
            self.secret_key,
            token_data.encode(),
            hashlib.sha256
        ).hexdigest()
        
        return f"{timestamp}.{signature}"
    
    def validate_token(self, token: str, session_id: str, max_age: int = 3600) -> bool:
        """Validate CSRF token."""
        try:
            timestamp_str, signature = token.split('.', 1)
            timestamp = int(timestamp_str)
            
            # Check token age
            if time.time() - timestamp > max_age:
                return False
            
            # Verify signature
            token_data = f"{session_id}:{timestamp_str}"
            expected_signature = hmac.new(
                self.secret_key,
                token_data.encode(),
                hashlib.sha256
            ).hexdigest()
            
            return hmac.compare_digest(signature, expected_signature)
            
        except (ValueError, TypeError):
            return False

class IPWhitelist:
    """IP address whitelisting and blacklisting."""
    
    def __init__(self):
        self.whitelist = set()
        self.blacklist = set()
        self.whitelist_networks = []
        self.blacklist_networks = []
    
    def add_to_whitelist(self, ip_or_network: str):
        """Add IP address or network to whitelist."""
        try:
            network = ipaddress.ip_network(ip_or_network, strict=False)
            if network.num_addresses == 1:
                self.whitelist.add(str(network.network_address))
            else:
                self.whitelist_networks.append(network)
        except ValueError:
            logger.error(f"Invalid IP/network format: {ip_or_network}")
    
    def add_to_blacklist(self, ip_or_network: str):
        """Add IP address or network to blacklist."""
        try:
            network = ipaddress.ip_network(ip_or_network, strict=False)
            if network.num_addresses == 1:
                self.blacklist.add(str(network.network_address))
            else:
                self.blacklist_networks.append(network)
        except ValueError:
            logger.error(f"Invalid IP/network format: {ip_or_network}")
    
    def is_allowed(self, ip_address: str) -> bool:
        """Check if IP address is allowed."""
        try:
            ip = ipaddress.ip_address(ip_address)
            
            # Check blacklist first
            if ip_address in self.blacklist:
                return False
            
            for network in self.blacklist_networks:
                if ip in network:
                    return False
            
            # If whitelist is empty, allow all (except blacklisted)
            if not self.whitelist and not self.whitelist_networks:
                return True
            
            # Check whitelist
            if ip_address in self.whitelist:
                return True
            
            for network in self.whitelist_networks:
                if ip in network:
                    return True
            
            return False
            
        except ValueError:
            logger.error(f"Invalid IP address: {ip_address}")
            return False

class SecurityHeaders:
    """Security headers management."""
    
    @staticmethod
    def get_security_headers(is_production: bool = True) -> Dict[str, str]:
        """Get recommended security headers."""
        headers = {
            'X-Content-Type-Options': 'nosniff',
            'X-Frame-Options': 'DENY',
            'X-XSS-Protection': '1; mode=block',
            'Referrer-Policy': 'strict-origin-when-cross-origin',
            'X-Permitted-Cross-Domain-Policies': 'none'
        }
        
        if is_production:
            headers.update({
                'Strict-Transport-Security': 'max-age=31536000; includeSubDomains; preload',
                'Content-Security-Policy': (
                    "default-src 'self'; "
                    "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
                    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
                    "font-src 'self' https://fonts.gstatic.com; "
                    "img-src 'self' data: https:; "
                    "connect-src 'self'; "
                    "frame-ancestors 'none'; "
                    "base-uri 'self'; "
                    "form-action 'self'"
                )
            })
        
        return headers

class FileUploadSecurity:
    """Secure file upload handling."""
    
    def __init__(self):
        self.allowed_extensions = {
            '.pdf', '.doc', '.docx', '.txt', '.rtf', '.odt',
            '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp'
        }
        
        self.max_file_size = 10 * 1024 * 1024  # 10MB
        
        self.dangerous_signatures = {
            'exe': [b'MZ\x90\x00'],
            'elf': [b'\x7fELF'],
            'script': [b'#!/'],
            'php': [b'<?php'],
            'asp': [b'<%'],
            'jsp': [b'<%@']
        }
    
    def validate_file(self, file_data: bytes, filename: str, content_type: str) -> Tuple[bool, List[str]]:
        """Validate uploaded file for security."""
        issues = []
        
        # Check file size
        if len(file_data) > self.max_file_size:
            issues.append(f"File too large: {len(file_data)} bytes")
        
        # Check filename
        if not self._validate_filename(filename):
            issues.append("Invalid filename")
        
        # Check file extension
        file_ext = os.path.splitext(filename)[1].lower()
        if file_ext not in self.allowed_extensions:
            issues.append(f"File type not allowed: {file_ext}")
        
        # Check file signature
        if self._check_dangerous_signature(file_data):
            issues.append("Dangerous file signature detected")
        
        # Verify content type matches extension
        if not self._verify_content_type(file_ext, content_type):
            issues.append("Content type mismatch")
        
        return len(issues) == 0, issues
    
    def _validate_filename(self, filename: str) -> bool:
        """Validate filename security."""
        # Check for path traversal
        if '..' in filename or '/' in filename or '\\' in filename:
            return False
        
        # Check for null bytes
        if '\x00' in filename:
            return False
        
        # Check length
        if len(filename) > 255:
            return False
        
        return True
    
    def _check_dangerous_signature(self, file_data: bytes) -> bool:
        """Check for dangerous file signatures."""
        file_start = file_data[:20]  # Check first 20 bytes
        
        for file_type, signatures in self.dangerous_signatures.items():
            for signature in signatures:
                if file_start.startswith(signature):
                    return True
        
        return False
    
    def _verify_content_type(self, file_ext: str, content_type: str) -> bool:
        """Verify content type matches file extension."""
        expected_types = {
            '.pdf': ['application/pdf'],
            '.doc': ['application/msword'],
            '.docx': ['application/vnd.openxmlformats-officedocument.wordprocessingml.document'],
            '.txt': ['text/plain'],
            '.rtf': ['application/rtf', 'text/rtf'],
            '.jpg': ['image/jpeg'],
            '.jpeg': ['image/jpeg'],
            '.png': ['image/png'],
            '.gif': ['image/gif'],
            '.bmp': ['image/bmp'],
            '.webp': ['image/webp']
        }
        
        expected = expected_types.get(file_ext, [])
        return content_type in expected if expected else True
    
    def sanitize_filename(self, filename: str) -> str:
        """Sanitize filename for safe storage."""
        # Remove path components
        filename = os.path.basename(filename)
        
        # Remove dangerous characters
        sanitized = re.sub(r'[^a-zA-Z0-9._-]', '', filename)
        
        # Ensure it's not empty
        if not sanitized:
            sanitized = f"file_{secrets.token_hex(8)}"
        
        # Limit length
        if len(sanitized) > 100:
            name, ext = os.path.splitext(sanitized)
            sanitized = name[:95] + ext
        
        return sanitized

class SessionSecurity:
    """Secure session management."""
    
    def __init__(self, secret_key: str):
        self.secret_key = secret_key
        self.session_timeout = 3600  # 1 hour
        self.active_sessions = {}
    
    def create_session(self, user_id: str, ip_address: str, user_agent: str) -> str:
        """Create secure session."""
        session_id = secrets.token_urlsafe(32)
        
        session_data = {
            'user_id': user_id,
            'ip_address': ip_address,
            'user_agent': user_agent,
            'created_at': time.time(),
            'last_activity': time.time()
        }
        
        self.active_sessions[session_id] = session_data
        return session_id
    
    def validate_session(self, session_id: str, ip_address: str, user_agent: str) -> Tuple[bool, Optional[str]]:
        """Validate session security."""
        if session_id not in self.active_sessions:
            return False, "Session not found"
        
        session = self.active_sessions[session_id]
        current_time = time.time()
        
        # Check timeout
        if current_time - session['last_activity'] > self.session_timeout:
            del self.active_sessions[session_id]
            return False, "Session expired"
        
        # Check IP address consistency
        if session['ip_address'] != ip_address:
            logger.warning(f"Session hijacking attempt: {session_id}")
            del self.active_sessions[session_id]
            return False, "IP address mismatch"
        
        # Check user agent consistency
        if session['user_agent'] != user_agent:
            logger.warning(f"Suspicious session activity: {session_id}")
            # Don't invalidate immediately, but log for monitoring
        
        # Update last activity
        session['last_activity'] = current_time
        
        return True, session['user_id']
    
    def invalidate_session(self, session_id: str):
        """Invalidate session."""
        self.active_sessions.pop(session_id, None)
    
    def cleanup_expired_sessions(self):
        """Remove expired sessions."""
        current_time = time.time()
        expired_sessions = [
            sid for sid, session in self.active_sessions.items()
            if current_time - session['last_activity'] > self.session_timeout
        ]
        
        for sid in expired_sessions:
            del self.active_sessions[sid]
        
        return len(expired_sessions)

# Global security instances
rate_limiter = RateLimiter()
input_sanitizer = InputSanitizer()
ip_whitelist = IPWhitelist()
file_upload_security = FileUploadSecurity()

# Security decorator functions
def require_csrf_token(f):
    """Decorator to require CSRF token for state-changing operations."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        from flask import request, session, abort
        
        if request.method in ['POST', 'PUT', 'DELETE', 'PATCH']:
            token = request.headers.get('X-CSRF-Token') or request.form.get('csrf_token')
            
            if not token or not csrf_protection.validate_token(token, session.get('session_id', '')):
                logger.warning(f"CSRF token validation failed for {request.endpoint}")
                abort(403)
        
        return f(*args, **kwargs)
    return decorated_function

def rate_limit(endpoint_type='default'):
    """Decorator for rate limiting."""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            from flask import request, abort, jsonify
            
            # Get client identifier (IP address)
            client_ip = request.environ.get('HTTP_X_FORWARDED_FOR', request.remote_addr)
            if client_ip:
                client_ip = client_ip.split(',')[0].strip()
            
            # Check rate limit
            is_limited, limit_info = rate_limiter.is_rate_limited(client_ip, endpoint_type)
            
            if is_limited:
                logger.warning(f"Rate limit exceeded for IP {client_ip} on endpoint {request.endpoint}")
                
                response = jsonify({
                    'error': 'Rate limit exceeded',
                    'retry_after': limit_info.get('retry_after', 3600)
                })
                response.status_code = 429
                response.headers['Retry-After'] = str(int(limit_info.get('retry_after', 3600)))
                return response
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def validate_input_security(input_type='general'):
    """Decorator for input validation."""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            from flask import request, abort, jsonify
            
            # Validate JSON input
            if request.is_json:
                json_data = request.get_json()
                if json_data:
                    for key, value in json_data.items():
                        if isinstance(value, str):
                            is_valid, threats = input_sanitizer.validate_input(value, input_type)
                            if not is_valid:
                                logger.warning(f"Malicious input detected in {key}: {threats}")
                                return jsonify({'error': 'Invalid input detected'}), 400
            
            # Validate form input
            for key, value in request.form.items():
                if isinstance(value, str):
                    is_valid, threats = input_sanitizer.validate_input(value, input_type)
                    if not is_valid:
                        logger.warning(f"Malicious input detected in {key}: {threats}")
                        return jsonify({'error': 'Invalid input detected'}), 400
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# Initialize CSRF protection (will be initialized with app secret key)
csrf_protection = None

def init_security(app):
    """Initialize security components with Flask app."""
    global csrf_protection
    
    csrf_protection = CSRFProtection(app.config['SECRET_KEY'])
    
    # Add security headers to all responses
    @app.after_request
    def add_security_headers(response):
        is_production = not app.config.get('DEBUG', False)
        headers = SecurityHeaders.get_security_headers(is_production)
        
        for header, value in headers.items():
            response.headers[header] = value
        
        return response
    
    logger.info("Security hardening initialized")