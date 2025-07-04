"""
LexAI Practice Partner - Enhanced Serverless Version
Matches localhost:5002 functionality with modern templates and full feature set
Includes comprehensive security middleware and input validation
"""

import os
import json
import requests
import logging
import re
import hashlib
import time
from datetime import datetime, timedelta
from functools import wraps
from typing import Dict, Any, Optional, List
from flask import Flask, request, jsonify, render_template_string, url_for, g
from dotenv import load_dotenv

try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    logging.warning("Redis not available - conversation persistence disabled")

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create Flask app with template folder support
app = Flask(__name__, 
           static_folder='../static',
           template_folder='../templates')
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'lexai-serverless-enhanced-2025')

# API configuration (from working local version)
XAI_API_KEY = (os.environ.get('XAI_API_KEY') or os.environ.get('xai_api_key') or '').strip()
REDIS_URL = os.environ.get('REDIS_URL')
DATABASE_URL = os.environ.get('DATABASE_URL')

if not XAI_API_KEY:
    logger.warning("XAI_API_KEY not set - AI features will not work")
else:
    logger.info(f"XAI_API_KEY loaded: {XAI_API_KEY[:10]}...{XAI_API_KEY[-4:]}")

if REDIS_URL:
    logger.info("Redis URL configured - conversation storage available")
if DATABASE_URL:
    logger.info("Neon database URL configured - full database features available")

# Redis connection for conversation persistence
redis_client = None
if REDIS_AVAILABLE and REDIS_URL:
    try:
        redis_client = redis.from_url(REDIS_URL, decode_responses=True)
        redis_client.ping()
        logger.info("✅ Redis connected successfully")
    except Exception as e:
        logger.error(f"Redis connection failed: {e}")
        redis_client = None

# Security configuration
MAX_MESSAGE_LENGTH = 5000
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

# Rate limiting storage (in memory for serverless)
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

class RateLimiter:
    """Rate limiting functionality"""
    
    @staticmethod
    def get_client_id(request) -> str:
        """Get unique client identifier"""
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
        "script-src 'self' 'unsafe-inline'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; "
        "connect-src 'self' https://api.x.ai"
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

class ConversationManager:
    """Redis-based conversation persistence with fallback to in-memory storage"""
    
    def __init__(self, redis_client=None):
        self.redis_client = redis_client
        self.memory_storage = {}  # Fallback for when Redis is unavailable
        self.conversation_ttl = 86400  # 24 hours
        
    def _get_conversation_key(self, client_id: str, practice_area: str) -> str:
        """Generate conversation key for Redis"""
        return f"conversation:{client_id}:{practice_area}"
    
    def save_message(self, client_id: str, practice_area: str, role: str, content: str) -> bool:
        """Save a message to the conversation history"""
        try:
            message = {
                'role': role,
                'content': content,
                'timestamp': datetime.utcnow().isoformat(),
                'practice_area': practice_area
            }
            
            if self.redis_client:
                key = self._get_conversation_key(client_id, practice_area)
                # Store as JSON list in Redis
                conversation = self.get_conversation(client_id, practice_area)
                conversation.append(message)
                
                # Keep only last 20 messages to manage memory
                if len(conversation) > 20:
                    conversation = conversation[-20:]
                
                self.redis_client.setex(key, self.conversation_ttl, json.dumps(conversation))
                logger.info(f"💾 Saved to Redis: {client_id[:8]}... | {role} | {len(content)} chars")
                return True
            else:
                # Fallback to memory storage
                key = self._get_conversation_key(client_id, practice_area)
                if key not in self.memory_storage:
                    self.memory_storage[key] = []
                self.memory_storage[key].append(message)
                
                # Keep only last 10 messages in memory
                if len(self.memory_storage[key]) > 10:
                    self.memory_storage[key] = self.memory_storage[key][-10:]
                
                logger.info(f"📝 Saved to memory: {client_id[:8]}... | {role} | {len(content)} chars")
                return True
                
        except Exception as e:
            logger.error(f"Failed to save message: {e}")
            return False
    
    def get_conversation(self, client_id: str, practice_area: str) -> List[Dict]:
        """Retrieve conversation history"""
        try:
            key = self._get_conversation_key(client_id, practice_area)
            
            if self.redis_client:
                conversation_data = self.redis_client.get(key)
                if conversation_data:
                    return json.loads(conversation_data)
            else:
                # Fallback to memory storage
                return self.memory_storage.get(key, [])
                
        except Exception as e:
            logger.error(f"Failed to retrieve conversation: {e}")
            
        return []
    
    def get_conversation_summary(self, client_id: str, practice_area: str) -> Dict[str, Any]:
        """Get conversation metadata and summary"""
        conversation = self.get_conversation(client_id, practice_area)
        
        if not conversation:
            return {
                'message_count': 0,
                'last_activity': None,
                'practice_area': practice_area,
                'status': 'new'
            }
        
        return {
            'message_count': len(conversation),
            'last_activity': conversation[-1]['timestamp'],
            'practice_area': practice_area,
            'status': 'active',
            'last_message_preview': conversation[-1]['content'][:100] + '...' if len(conversation[-1]['content']) > 100 else conversation[-1]['content']
        }
    
    def clear_conversation(self, client_id: str, practice_area: str) -> bool:
        """Clear conversation history"""
        try:
            key = self._get_conversation_key(client_id, practice_area)
            
            if self.redis_client:
                self.redis_client.delete(key)
            else:
                self.memory_storage.pop(key, None)
                
            logger.info(f"🗑️ Cleared conversation: {client_id[:8]}... | {practice_area}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to clear conversation: {e}")
            return False

# Initialize conversation manager
conversation_manager = ConversationManager(redis_client)

# Register security headers middleware
@app.after_request
def apply_security_headers(response):
    return security_headers(response)

# Practice areas (from working local version)
PRACTICE_AREAS = {
    'family': {
        'name': 'Family Law',
        'icon': 'family',
        'color': '#8B5CF6',
        'prompts': [
            'Draft a custody agreement',
            'Calculate child support',
            'Prepare divorce petition',
            'Analyze property division',
            'Draft prenuptial agreement'
        ]
    },
    'personal_injury': {
        'name': 'Personal Injury',
        'icon': 'shield',
        'color': '#EF4444',
        'prompts': [
            'Calculate damages',
            'Draft demand letter',
            'Analyze medical records',
            'Prepare settlement agreement',
            'Research similar cases'
        ]
    },
    'corporate': {
        'name': 'Corporate Law',
        'icon': 'building',
        'color': '#3B82F6',
        'prompts': [
            'Draft contract terms',
            'Review agreement',
            'Analyze compliance',
            'Prepare entity documents',
            'Research regulations'
        ]
    },
    'criminal': {
        'name': 'Criminal Defense',
        'icon': 'scale',
        'color': '#F59E0B',
        'prompts': [
            'Research precedents',
            'Draft motion',
            'Analyze evidence',
            'Prepare defense strategy',
            'Review plea options'
        ]
    },
    'real_estate': {
        'name': 'Real Estate',
        'icon': 'home',
        'color': '#10B981',
        'prompts': [
            'Review purchase agreement',
            'Analyze title issues',
            'Draft lease terms',
            'Check zoning compliance',
            'Prepare closing documents'
        ]
    },
    'immigration': {
        'name': 'Immigration',
        'icon': 'globe',
        'color': '#6366F1',
        'prompts': [
            'Prepare visa application',
            'Analyze eligibility',
            'Draft petition',
            'Review documentation',
            'Check status updates'
        ]
    }
}

# Mock data for serverless version
def get_mock_clients():
    return [
        {'id': 1, 'name': 'John Smith', 'practice_area': 'family', 'status': 'active', 'last_contact': '2025-01-03'},
        {'id': 2, 'name': 'Sarah Johnson', 'practice_area': 'corporate', 'status': 'active', 'last_contact': '2025-01-02'},
        {'id': 3, 'name': 'Mike Davis', 'practice_area': 'personal_injury', 'status': 'pending', 'last_contact': '2025-01-01'},
    ]

def get_mock_stats():
    return {
        'total_clients': 3,
        'active_cases': 2,
        'pending_cases': 1,
        'completed_cases': 5,
        'revenue_ytd': 125000,
        'ai_interactions': 47,
        'documents_processed': 23
    }

def build_system_prompt(practice_area):
    """Build specialized system prompt for practice area"""
    base_prompt = "You are LexAI, a professional legal AI assistant. Provide accurate, practical legal guidance while noting this is not formal legal advice. Keep responses concise and professional."
    
    if practice_area == 'family':
        return f"{base_prompt} You specialize in family law matters including divorce, custody, child support, and domestic relations."
    elif practice_area == 'personal_injury':
        return f"{base_prompt} You specialize in personal injury law including accidents, medical malpractice, and insurance claims."
    elif practice_area == 'corporate':
        return f"{base_prompt} You specialize in corporate law including contracts, compliance, business formation, and commercial transactions."
    elif practice_area == 'criminal':
        return f"{base_prompt} You specialize in criminal defense including charges, procedures, rights, and court processes."
    elif practice_area == 'real_estate':
        return f"{base_prompt} You specialize in real estate law including transactions, contracts, zoning, and property disputes."
    elif practice_area == 'immigration':
        return f"{base_prompt} You specialize in immigration law including visas, citizenship, deportation defense, and family reunification."
    
    return base_prompt

# Enhanced embedded dashboard template matching local version
EMBEDDED_DASHBOARD_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>LexAI Practice Partner - Dashboard</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <style>
        :root {
            /* Logo-compatible colors (maintain for navbar) */
            --lexai-darkest-green: #09332C;
            --lexai-dark-green: #2E4B3C;
            --lexai-light-cream: #F7EDDA;
            --lexai-warm-cream: #F7DFBA;
            --lexai-warm-orange: #FFA74F;
            --lexai-bright-coral: #F0531C;

            /* Primary palette using LexAI colors */
            --primary-green: #2E4B3C;
            --primary-green-light: #4A6B57;
            --primary-green-dark: #09332C;
            --secondary-cream: #F7EDDA;
            --secondary-orange: #FFA74F;
            --accent-coral: #F0531C;
            
            /* Extended professional palette */
            --white: #ffffff;
            --gray-50: #f9fafb;
            --gray-100: #f3f4f6;
            --gray-200: #e5e7eb;
            --gray-600: #4b5563;
            --gray-700: #374151;
            --gray-900: #111827;
            --success: #10b981;
            --warning: #f59e0b;
            --error: #ef4444;
            
            /* Practice area colors matching local version */
            --family-law: #8b5cf6;
            --personal-injury: #ef4444;
            --corporate: #3b82f6;
            --criminal: #f59e0b;
            --real-estate: #10b981;
            --immigration: #6366f1;
        }

        * { margin: 0; padding: 0; box-sizing: border-box; }
        
        body {
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
            background: linear-gradient(135deg, var(--secondary-cream) 0%, var(--lexai-warm-cream) 100%);
            min-height: 100vh;
            color: var(--gray-900);
        }

        .layout-container {
            display: flex;
            min-height: 100vh;
        }

        .sidebar {
            width: 280px;
            background: var(--white);
            box-shadow: 2px 0 12px rgba(0, 0, 0, 0.1);
            transition: transform 0.3s ease;
        }

        .sidebar-header {
            padding: 24px;
            border-bottom: 1px solid var(--gray-200);
        }

        .sidebar-header h2 {
            font-size: 1.5rem;
            font-weight: 700;
            color: var(--primary-green);
        }

        .sidebar-nav {
            padding: 20px;
        }

        .nav-section {
            margin-bottom: 32px;
        }

        .nav-section-title {
            font-size: 0.75rem;
            font-weight: 600;
            text-transform: uppercase;
            color: var(--gray-600);
            margin-bottom: 12px;
            letter-spacing: 0.05em;
        }

        .nav-link {
            display: flex;
            align-items: center;
            padding: 12px 16px;
            margin-bottom: 4px;
            border-radius: 8px;
            text-decoration: none;
            color: var(--gray-700);
            font-weight: 500;
            transition: all 0.2s ease;
        }

        .nav-link:hover {
            background: var(--secondary-cream);
            color: var(--primary-green);
        }

        .nav-link.active {
            background: linear-gradient(135deg, var(--primary-green), var(--primary-green-light));
            color: var(--white);
        }

        .nav-icon {
            width: 20px;
            height: 20px;
            margin-right: 12px;
        }

        .main-content {
            flex: 1;
            display: flex;
            flex-direction: column;
        }

        .navbar {
            background: linear-gradient(135deg, var(--lexai-dark-green) 0%, var(--primary-green) 100%);
            padding: 16px 32px;
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
            display: flex;
            align-items: center;
            justify-content: space-between;
        }

        .navbar-brand {
            display: flex;
            align-items: center;
            gap: 16px;
        }

        .menu-toggle {
            display: none;
            background: none;
            border: none;
            cursor: pointer;
        }

        .hamburger {
            width: 24px;
            height: 18px;
            position: relative;
        }

        .hamburger span {
            display: block;
            position: absolute;
            height: 3px;
            width: 100%;
            background: var(--secondary-cream);
            border-radius: 1.5px;
            transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        }

        .hamburger span:nth-child(1) { top: 0; }
        .hamburger span:nth-child(2) { top: 7px; }
        .hamburger span:nth-child(3) { top: 14px; }

        .navbar-logo {
            height: 40px;
            width: auto;
            margin-right: 12px;
        }
        
        .navbar-text {
            color: var(--secondary-cream);
            font-weight: 600;
            font-size: 1.125rem;
        }

        .content-area {
            flex: 1;
            padding: 32px;
            overflow-y: auto;
        }

        .page-header {
            margin-bottom: 32px;
        }

        .page-title {
            font-size: 2.25rem;
            font-weight: 700;
            color: var(--primary-green-dark);
            margin-bottom: 8px;
        }

        .page-subtitle {
            font-size: 1.125rem;
            color: var(--primary-green);
        }

        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 24px;
            margin-bottom: 32px;
        }

        .stat-card {
            background: var(--white);
            padding: 24px;
            border-radius: 12px;
            box-shadow: 0 4px 16px rgba(0, 0, 0, 0.1);
            transition: transform 0.2s ease;
        }

        .stat-card:hover {
            transform: translateY(-2px);
        }

        .stat-header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 8px;
        }

        .stat-title {
            font-size: 0.875rem;
            font-weight: 500;
            color: var(--gray-600);
        }

        .stat-icon {
            width: 24px;
            height: 24px;
            color: var(--primary-green);
        }

        .stat-value {
            font-size: 2rem;
            font-weight: 700;
            color: var(--gray-900);
        }

        .practice-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
            gap: 24px;
            margin-bottom: 32px;
        }

        .practice-card {
            background: var(--white);
            border-radius: 12px;
            padding: 24px;
            box-shadow: 0 4px 16px rgba(0, 0, 0, 0.1);
            transition: all 0.3s ease;
            cursor: pointer;
            position: relative;
            overflow: hidden;
        }

        .practice-card:hover {
            transform: translateY(-4px);
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.15);
        }

        .practice-card::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 4px;
            background: var(--practice-color, var(--primary-green));
        }

        .practice-header {
            display: flex;
            align-items: center;
            margin-bottom: 16px;
        }

        .practice-icon {
            width: 48px;
            height: 48px;
            border-radius: 12px;
            display: flex;
            align-items: center;
            justify-content: center;
            margin-right: 16px;
            background: var(--practice-bg, rgba(46, 75, 60, 0.1));
        }

        .practice-title {
            font-size: 1.25rem;
            font-weight: 600;
            color: var(--gray-900);
            margin-bottom: 4px;
        }

        .practice-description {
            font-size: 0.875rem;
            color: var(--gray-600);
            line-height: 1.5;
        }

        .action-buttons {
            display: flex;
            gap: 16px;
            margin-top: 32px;
        }

        .btn {
            padding: 12px 24px;
            border-radius: 8px;
            font-weight: 600;
            text-decoration: none;
            transition: all 0.2s ease;
            cursor: pointer;
            border: none;
            font-size: 0.875rem;
        }

        .btn-primary {
            background: linear-gradient(135deg, var(--primary-green), var(--primary-green-light));
            color: var(--white);
        }

        .btn-primary:hover {
            transform: translateY(-1px);
            box-shadow: 0 4px 12px rgba(46, 75, 60, 0.3);
        }

        .recent-section {
            background: var(--white);
            border-radius: 12px;
            padding: 24px;
            box-shadow: 0 4px 16px rgba(0, 0, 0, 0.1);
        }

        .section-title {
            font-size: 1.25rem;
            font-weight: 600;
            color: var(--gray-900);
            margin-bottom: 20px;
        }

        .client-list {
            space-y: 12px;
        }

        .client-item {
            display: flex;
            align-items: center;
            justify-content: between;
            padding: 12px 0;
            border-bottom: 1px solid var(--gray-100);
        }

        .client-item:last-child {
            border-bottom: none;
        }

        .client-info {
            flex: 1;
        }

        .client-name {
            font-weight: 600;
            color: var(--gray-900);
        }

        .client-meta {
            font-size: 0.875rem;
            color: var(--gray-600);
        }

        .status-badge {
            padding: 4px 8px;
            border-radius: 4px;
            font-size: 0.75rem;
            font-weight: 500;
        }

        .status-active {
            background: rgba(16, 185, 129, 0.1);
            color: var(--success);
        }

        .status-pending {
            background: rgba(245, 158, 11, 0.1);
            color: var(--warning);
        }

        @media (max-width: 768px) {
            .sidebar {
                transform: translateX(-100%);
                position: fixed;
                z-index: 1000;
                height: 100vh;
            }

            .sidebar.open {
                transform: translateX(0);
            }

            .menu-toggle {
                display: block;
            }

            .stats-grid {
                grid-template-columns: 1fr;
            }

            .practice-grid {
                grid-template-columns: 1fr;
            }

            .content-area {
                padding: 20px;
            }
        }
    </style>
</head>
<body>
    <div class="layout-container">
        <!-- Sidebar Navigation -->
        <aside class="sidebar" id="sidebar">
            <div class="sidebar-header">
                <h2>🏛️ LexAI Platform</h2>
            </div>
            
            <nav class="sidebar-nav">
                <div class="nav-section">
                    <h3 class="nav-section-title">Main</h3>
                    <a href="/" class="nav-link active">
                        <svg class="nav-icon" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2H5a2 2 0 00-2-2z"/>
                        </svg>
                        Dashboard
                    </a>
                    <a href="/chat" class="nav-link">
                        <svg class="nav-icon" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"/>
                        </svg>
                        AI Assistant
                    </a>
                </div>

                <div class="nav-section">
                    <h3 class="nav-section-title">Practice Areas</h3>
                    {% for area_id, area in practice_areas.items() %}
                    <a href="/chat?area={{ area_id }}" class="nav-link">
                        <div class="practice-icon" style="background: {{ area.color }}20; color: {{ area.color }};">
                            <svg class="nav-icon" fill="currentColor" viewBox="0 0 24 24">
                                <circle cx="12" cy="12" r="3"/>
                            </svg>
                        </div>
                        {{ area.name }}
                    </a>
                    {% endfor %}
                </div>
            </nav>
        </aside>

        <!-- Main Content -->
        <main class="main-content">
            <!-- Top Navigation -->
            <header class="navbar">
                <div class="navbar-brand">
                    <button id="sidebarToggle" class="menu-toggle">
                        <div class="hamburger">
                            <span></span>
                            <span></span>
                            <span></span>
                        </div>
                    </button>
                    <!-- LexAI Logo -->
                    <img src="/static/lexAI.png" alt="LexAI" class="navbar-logo">
                </div>
                
                <div style="display: flex; gap: 12px; align-items: center;">
                    <div style="padding: 6px 12px; background: var(--secondary-cream); border-radius: 6px; font-size: 0.875rem; color: var(--primary-green); font-weight: 500;">
                        ✅ {{ "API Connected" if api_status else "Demo Mode" }}
                    </div>
                </div>
            </header>

            <!-- Dashboard Content -->
            <div class="content-area">
                <div class="page-header">
                    <h1 class="page-title">Dashboard</h1>
                    <p class="page-subtitle">Professional AI-powered legal practice management</p>
                </div>

                <!-- Stats Grid -->
                <div class="stats-grid">
                    <div class="stat-card">
                        <div class="stat-header">
                            <span class="stat-title">Total Clients</span>
                            <svg class="stat-icon" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z"/>
                            </svg>
                        </div>
                        <div class="stat-value">{{ stats.total_clients }}</div>
                    </div>

                    <div class="stat-card">
                        <div class="stat-header">
                            <span class="stat-title">Active Cases</span>
                            <svg class="stat-icon" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/>
                            </svg>
                        </div>
                        <div class="stat-value">{{ stats.active_cases }}</div>
                    </div>

                    <div class="stat-card">
                        <div class="stat-header">
                            <span class="stat-title">AI Interactions</span>
                            <svg class="stat-icon" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z"/>
                            </svg>
                        </div>
                        <div class="stat-value">{{ stats.ai_interactions }}</div>
                    </div>

                    <div class="stat-card">
                        <div class="stat-header">
                            <span class="stat-title">Documents</span>
                            <svg class="stat-icon" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z"/>
                            </svg>
                        </div>
                        <div class="stat-value">{{ stats.documents_processed }}</div>
                    </div>
                </div>

                <!-- Practice Areas Grid -->
                <div class="practice-grid">
                    {% for area_id, area in practice_areas.items() %}
                    <div class="practice-card" onclick="window.location.href='/chat?area={{ area_id }}'" 
                         style="--practice-color: {{ area.color }}; --practice-bg: {{ area.color }}20;">
                        <div class="practice-header">
                            <div class="practice-icon" style="background: {{ area.color }}20; color: {{ area.color }};">
                                <svg width="24" height="24" fill="currentColor" viewBox="0 0 24 24">
                                    <circle cx="12" cy="12" r="3"/>
                                </svg>
                            </div>
                            <div>
                                <h3 class="practice-title">{{ area.name }}</h3>
                            </div>
                        </div>
                        <p class="practice-description">
                            Specialized AI assistance for {{ area.name.lower() }} matters with expert guidance and document automation.
                        </p>
                    </div>
                    {% endfor %}
                </div>

                <!-- Action Buttons -->
                <div class="action-buttons">
                    <a href="/chat" class="btn btn-primary">Start AI Consultation</a>
                    <a href="/health" class="btn" style="background: var(--gray-100); color: var(--gray-700);">System Health</a>
                </div>

                <!-- Recent Clients -->
                <div class="recent-section">
                    <h2 class="section-title">Recent Client Activity</h2>
                    <div class="client-list">
                        {% for client in recent_clients %}
                        <div class="client-item">
                            <div class="client-info">
                                <div class="client-name">{{ client.name }}</div>
                                <div class="client-meta">{{ practice_areas[client.practice_area].name }} • Last contact: {{ client.last_contact }}</div>
                            </div>
                            <span class="status-badge status-{{ client.status }}">{{ client.status.title() }}</span>
                        </div>
                        {% endfor %}
                    </div>
                </div>
            </div>
        </main>
    </div>

    <script>
        // Sidebar toggle
        document.getElementById('sidebarToggle').addEventListener('click', function() {
            document.getElementById('sidebar').classList.toggle('open');
        });

        // Close sidebar when clicking outside on mobile
        document.addEventListener('click', function(e) {
            const sidebar = document.getElementById('sidebar');
            const toggle = document.getElementById('sidebarToggle');
            
            if (window.innerWidth <= 768 && 
                !sidebar.contains(e.target) && 
                !toggle.contains(e.target) && 
                sidebar.classList.contains('open')) {
                sidebar.classList.remove('open');
            }
        });
    </script>
</body>
</html>
"""

@app.route('/')
def dashboard():
    """Enhanced dashboard matching localhost:5002 version"""
    try:
        # Get stats and data
        stats = get_mock_stats()
        recent_clients = get_mock_clients()[:3]  # Show last 3 clients
        
        # Try to render template first
        try:
            from flask import render_template
            return render_template('dashboard.html', 
                                 practice_areas=PRACTICE_AREAS,
                                 stats=stats,
                                 recent_clients=recent_clients,
                                 total_clients=stats['total_clients'])
        except Exception as template_error:
            logger.warning(f"Template render failed: {template_error}, using embedded template")
            # Enhanced fallback with modern styling matching local version
            return render_template_string(EMBEDDED_DASHBOARD_TEMPLATE, 
                                        practice_areas=PRACTICE_AREAS,
                                        stats=stats,
                                        recent_clients=recent_clients,
                                        api_status=bool(XAI_API_KEY))
    except Exception as e:
        logger.error(f"Dashboard error: {e}")
        # Minimal fallback
        return f"""<!DOCTYPE html>
<html><head><title>LexAI Dashboard</title></head>
<body><h1>🏛️ LexAI Practice Partner</h1>
<p>Dashboard loading error: {e}</p>
<a href="/chat">Continue to Chat</a></body></html>"""

@app.route('/chat')
@app.route('/chat/<client_id>')
def chat_interface(client_id=None):
    """Enhanced chat interface matching local version"""
    try:
        # Get practice area from query params
        practice_area = request.args.get('area', 'general')
        
        try:
            from flask import render_template
            return render_template('chat.html', 
                                 current_client=client_id,
                                 practice_areas=PRACTICE_AREAS,
                                 selected_area=practice_area)
        except Exception as template_error:
            logger.warning(f"Chat template render failed: {template_error}, using embedded template")
            # Enhanced fallback chat interface with modern styling
            selected_practice = PRACTICE_AREAS.get(practice_area, {'name': 'General Legal', 'color': '#1e40af'})
            
            return render_template_string("""
            <!DOCTYPE html>
            <html lang="en">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>LexAI Chat - {{ selected_practice['name'] }}</title>
                <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
                <style>
                    body {
                        font-family: 'Inter', system-ui, -apple-system, sans-serif;
                        background: linear-gradient(135deg, #F7EDDA 0%, #F7DFBA 100%);
                        margin: 0;
                        padding: 20px;
                        min-height: 100vh;
                        color: #1f2937;
                    }
                    .chat-container {
                        max-width: 1000px;
                        margin: 0 auto;
                        background: white;
                        border-radius: 16px;
                        overflow: hidden;
                        box-shadow: 0 20px 40px rgba(0,0,0,0.1);
                        display: flex;
                        flex-direction: column;
                        height: 80vh;
                    }
                    .chat-header {
                        background: linear-gradient(135deg, #2E4B3C, #4A6B57);
                        color: white;
                        padding: 20px 24px;
                        border-bottom: 1px solid rgba(255,255,255,0.1);
                    }
                    .chat-header h1 {
                        margin: 0;
                        font-size: 1.5rem;
                        font-weight: 600;
                    }
                    .chat-header p {
                        margin: 4px 0 0 0;
                        opacity: 0.9;
                        font-size: 0.875rem;
                    }
                    .chat-messages {
                        flex: 1;
                        padding: 24px;
                        overflow-y: auto;
                        background: #f9fafb;
                    }
                    .message {
                        margin-bottom: 16px;
                        display: flex;
                        align-items: flex-start;
                        gap: 12px;
                    }
                    .message.user {
                        justify-content: flex-end;
                    }
                    .message.user .message-content {
                        background: linear-gradient(135deg, #2E4B3C, #4A6B57);
                        color: white;
                    }
                    .message-avatar {
                        width: 32px;
                        height: 32px;
                        border-radius: 50%;
                        background: #e5e7eb;
                        display: flex;
                        align-items: center;
                        justify-content: center;
                        font-weight: 600;
                        font-size: 0.75rem;
                        color: #6b7280;
                    }
                    .message.user .message-avatar {
                        background: #2E4B3C;
                        color: white;
                    }
                    .message-content {
                        max-width: 70%;
                        padding: 12px 16px;
                        border-radius: 12px;
                        background: white;
                        box-shadow: 0 2px 8px rgba(0,0,0,0.05);
                        border: 1px solid #e5e7eb;
                    }
                    .chat-input {
                        border-top: 1px solid #e5e7eb;
                        padding: 20px 24px;
                        background: white;
                    }
                    .input-group {
                        display: flex;
                        gap: 12px;
                        align-items: flex-end;
                    }
                    .message-input {
                        flex: 1;
                        padding: 12px 16px;
                        border: 2px solid #e5e7eb;
                        border-radius: 12px;
                        font-size: 1rem;
                        resize: none;
                        min-height: 44px;
                        max-height: 120px;
                        font-family: inherit;
                        transition: border-color 0.2s ease;
                    }
                    .message-input:focus {
                        outline: none;
                        border-color: #2E4B3C;
                    }
                    .send-button {
                        padding: 12px 24px;
                        background: linear-gradient(135deg, #2E4B3C, #4A6B57);
                        color: white;
                        border: none;
                        border-radius: 12px;
                        font-weight: 600;
                        cursor: pointer;
                        transition: all 0.2s ease;
                    }
                    .send-button:hover {
                        transform: translateY(-1px);
                        box-shadow: 0 4px 12px rgba(46, 75, 60, 0.3);
                    }
                    .send-button:disabled {
                        opacity: 0.6;
                        cursor: not-allowed;
                        transform: none;
                    }
                    .back-link {
                        position: absolute;
                        top: 20px;
                        left: 20px;
                        background: #2E4B3C;
                        color: #F7EDDA;
                        padding: 8px 16px;
                        border-radius: 8px;
                        text-decoration: none;
                        font-size: 0.875rem;
                        font-weight: 600;
                        box-shadow: 0 2px 8px rgba(46, 75, 60, 0.3);
                        border: 1px solid rgba(46, 75, 60, 0.2);
                    }
                    .back-link:hover {
                        background: #4A6B57;
                        transform: translateY(-1px);
                        box-shadow: 0 4px 12px rgba(46, 75, 60, 0.4);
                    }
                    .typing-indicator {
                        display: none;
                        color: #6b7280;
                        font-style: italic;
                        font-size: 0.875rem;
                    }
                </style>
            </head>
            <body>
                <a href="/" class="back-link">← Dashboard</a>
                
                <div class="chat-container">
                    <div class="chat-header">
                        <div style="display: flex; align-items: center; margin-bottom: 8px;">
                            <img src="/static/lexAI.png" alt="LexAI" style="height: 32px; width: auto; margin-right: 12px;">
                            <h1 style="margin: 0; font-size: 1.5rem; font-weight: 600;">LexAI - {{ selected_practice['name'] }}</h1>
                        </div>
                        <p style="margin: 0; opacity: 0.9; font-size: 0.875rem;">Professional AI legal assistant specialized in {{ selected_practice['name'].lower() }}</p>
                    </div>
                    
                    <div class="chat-messages" id="chatMessages">
                        <div class="message assistant">
                            <div class="message-avatar">LA</div>
                            <div class="message-content">
                                Welcome to LexAI! I'm your AI legal assistant specializing in {{ selected_practice['name'].lower() }}. 
                                I can help with legal research, document analysis, and provide professional guidance. 
                                Please note this is not formal legal advice. How can I assist you today?
                            </div>
                        </div>
                    </div>
                    
                    <div class="chat-input">
                        <div class="input-group">
                            <textarea 
                                id="messageInput" 
                                class="message-input" 
                                placeholder="Ask a legal question about {{ selected_practice['name'].lower() }}..."
                                rows="1"
                            ></textarea>
                            <button id="sendButton" class="send-button" onclick="sendMessage()">
                                Send
                            </button>
                        </div>
                        <div id="typingIndicator" class="typing-indicator">LexAI is thinking...</div>
                    </div>
                </div>

                <script>
                    let currentClientId = 'client_' + Date.now();
                    let isTyping = false;
                    
                    // Auto-resize textarea
                    const messageInput = document.getElementById('messageInput');
                    messageInput.addEventListener('input', function() {
                        this.style.height = 'auto';
                        this.style.height = Math.min(this.scrollHeight, 120) + 'px';
                    });
                    
                    // Send on Enter (not Shift+Enter)
                    messageInput.addEventListener('keydown', function(e) {
                        if (e.key === 'Enter' && !e.shiftKey) {
                            e.preventDefault();
                            sendMessage();
                        }
                    });
                    
                    async function sendMessage() {
                        const input = document.getElementById('messageInput');
                        const sendButton = document.getElementById('sendButton');
                        const chatMessages = document.getElementById('chatMessages');
                        const typingIndicator = document.getElementById('typingIndicator');
                        const message = input.value.trim();
                        
                        if (!message || isTyping) return;
                        
                        // Disable input
                        isTyping = true;
                        input.disabled = true;
                        sendButton.disabled = true;
                        sendButton.textContent = 'Sending...';
                        
                        // Add user message
                        addMessage('user', message);
                        input.value = '';
                        input.style.height = 'auto';
                        
                        // Show typing indicator
                        typingIndicator.style.display = 'block';
                        
                        try {
                            const response = await fetch('/api/chat', {
                                method: 'POST',
                                headers: { 'Content-Type': 'application/json' },
                                body: JSON.stringify({ 
                                    message: message,
                                    practice_area: '{{ practice_area }}',
                                    client_id: currentClientId
                                })
                            });
                            
                            const data = await response.json();
                            
                            // Hide typing indicator
                            typingIndicator.style.display = 'none';
                            
                            if (data.choices && data.choices[0] && data.choices[0].delta) {
                                addMessage('assistant', data.choices[0].delta.content);
                            } else if (data.error) {
                                addMessage('assistant', `Error: ${data.error}`, true);
                            } else {
                                addMessage('assistant', 'Unexpected response format', true);
                            }
                        } catch (error) {
                            typingIndicator.style.display = 'none';
                            addMessage('assistant', 'Connection error. Please try again.', true);
                        }
                        
                        // Re-enable input
                        isTyping = false;
                        input.disabled = false;
                        sendButton.disabled = false;
                        sendButton.textContent = 'Send';
                        input.focus();
                    }
                    
                    function addMessage(sender, content, isError = false) {
                        const chatMessages = document.getElementById('chatMessages');
                        const messageDiv = document.createElement('div');
                        messageDiv.className = `message ${sender}`;
                        
                        const avatar = sender === 'user' ? 'YOU' : 'LA';
                        const errorStyle = isError ? 'color: #ef4444; font-style: italic;' : '';
                        
                        messageDiv.innerHTML = `
                            <div class="message-avatar">${avatar}</div>
                            <div class="message-content" style="${errorStyle}">${content}</div>
                        `;
                        
                        chatMessages.appendChild(messageDiv);
                        chatMessages.scrollTop = chatMessages.scrollHeight;
                    }
                    
                    // Focus input on load
                    document.addEventListener('DOMContentLoaded', function() {
                        messageInput.focus();
                    });
                </script>
            </body>
            </html>
            """, selected_practice=selected_practice, practice_area=practice_area)
    except Exception as e:
        logger.error(f"Chat interface error: {e}")
        return f"""<!DOCTYPE html>
<html><head><title>LexAI Chat</title></head>
<body><h1>🏛️ LexAI Chat</h1>
<p>Chat loading error: {e}</p>
<a href="/">← Back to Dashboard</a></body></html>"""

@app.route('/health')
@rate_limit_decorator
def health_check():
    """Health check endpoint with rate limiting"""
    try:
        return jsonify({
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "version": "serverless-enhanced-v2.0",
            "resources": {
                "xai_api": bool(XAI_API_KEY),
                "redis": bool(REDIS_URL),
                "neon_database": bool(DATABASE_URL)
            },
            "features": {
                "ai_chat": bool(XAI_API_KEY),
                "conversation_storage": bool(redis_client),
                "conversation_fallback": True,
                "practice_areas": True,
                "modern_ui": True,
                "security_validation": True,
                "rate_limiting": True,
                "xss_protection": True,
                "sql_injection_protection": True,
                "session_continuity": True
            },
            "security": {
                "rate_limit_window": RATE_LIMIT_WINDOW,
                "rate_limit_requests": RATE_LIMIT_REQUESTS,
                "max_message_length": MAX_MESSAGE_LENGTH,
                "active_rate_limits": len(rate_limit_storage)
            },
            "storage": {
                "redis_connected": bool(redis_client),
                "redis_available": REDIS_AVAILABLE,
                "memory_fallback": not bool(redis_client),
                "conversation_ttl_hours": 24,
                "max_messages_per_conversation": 20
            }
        })
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return jsonify({
            "status": "error",
            "error": str(e)
        }), 500

@app.route('/api/security-status')
@rate_limit_decorator
def security_status():
    """Security monitoring endpoint"""
    try:
        client_id = RateLimiter.get_client_id(request)
        
        # Get current rate limit status for this client
        now = time.time()
        window_start = now - RATE_LIMIT_WINDOW
        client_requests = []
        
        if client_id in rate_limit_storage:
            client_requests = [
                timestamp for timestamp in rate_limit_storage[client_id]
                if timestamp > window_start
            ]
        
        return jsonify({
            "status": "monitoring",
            "timestamp": datetime.utcnow().isoformat(),
            "client_id": client_id[:8] + "...",  # Partial for privacy
            "rate_limit": {
                "requests_in_window": len(client_requests),
                "max_requests": RATE_LIMIT_REQUESTS,
                "window_seconds": RATE_LIMIT_WINDOW,
                "remaining_requests": max(0, RATE_LIMIT_REQUESTS - len(client_requests))
            },
            "security_features": {
                "input_validation": True,
                "xss_protection": True,
                "sql_injection_protection": True,
                "security_headers": True,
                "rate_limiting": True
            },
            "total_active_sessions": len(rate_limit_storage)
        })
    except Exception as e:
        logger.error(f"Security status check failed: {e}")
        return jsonify({
            "status": "error",
            "error": str(e)
        }), 500

@app.route('/api/conversation/<client_id>')
@rate_limit_decorator
def get_conversation_history(client_id):
    """Get conversation history for a client"""
    try:
        practice_area = request.args.get('practice_area', 'general')
        conversation = conversation_manager.get_conversation(client_id, practice_area)
        summary = conversation_manager.get_conversation_summary(client_id, practice_area)
        
        return jsonify({
            "status": "success",
            "conversation": conversation,
            "summary": summary,
            "client_id": client_id,
            "practice_area": practice_area
        })
    except Exception as e:
        logger.error(f"Failed to get conversation history: {e}")
        return jsonify({
            "status": "error",
            "error": str(e)
        }), 500

@app.route('/api/conversation/<client_id>/clear', methods=['POST'])
@rate_limit_decorator
def clear_conversation_history(client_id):
    """Clear conversation history for a client"""
    try:
        practice_area = request.args.get('practice_area', 'general')
        success = conversation_manager.clear_conversation(client_id, practice_area)
        
        if success:
            return jsonify({
                "status": "success",
                "message": "Conversation history cleared",
                "client_id": client_id,
                "practice_area": practice_area
            })
        else:
            return jsonify({
                "status": "error",
                "error": "Failed to clear conversation"
            }), 500
            
    except Exception as e:
        logger.error(f"Failed to clear conversation: {e}")
        return jsonify({
            "status": "error",
            "error": str(e)
        }), 500

@app.route('/api/chat', methods=['POST'])
@rate_limit_decorator
@validate_json_input(['message'])
def api_chat():
    """Enhanced chat API with security validation"""
    try:
        data = g.validated_data
        message = data.get('message', '').strip()
        practice_area = data.get('practice_area', 'general')
        client_id = data.get('client_id', f'client_{datetime.utcnow().strftime("%Y%m%d_%H%M%S")}')
        
        # Security validation
        validation_result = SecurityValidator.validate_message(message)
        if not validation_result['valid']:
            logger.warning(f"Invalid message from {RateLimiter.get_client_id(request)}: {validation_result['errors']}")
            return jsonify({
                "error": "Invalid input: " + "; ".join(validation_result['errors'])
            }), 400
        
        # Use sanitized message
        message = validation_result['sanitized']

        if not XAI_API_KEY:
            return jsonify({"error": "AI service not configured"}), 503

        # Build specialized system prompt
        system_prompt = build_system_prompt(practice_area)
        
        # Get conversation history for context
        conversation_history = conversation_manager.get_conversation(client_id, practice_area)
        
        # Build messages array with conversation history
        messages = [{"role": "system", "content": system_prompt}]
        
        # Add conversation history (last 10 messages for context)
        recent_history = conversation_history[-10:] if conversation_history else []
        for msg in recent_history:
            messages.append({
                "role": msg["role"],
                "content": msg["content"]
            })
        
        # Add current user message
        messages.append({"role": "user", "content": message})
        
        # API call payload
        payload = {
            "model": "grok-3-latest",
            "messages": messages,
            "stream": False,
            "temperature": 0.7
        }

        headers = {
            "Authorization": f"Bearer {XAI_API_KEY}",
            "Content-Type": "application/json"
        }

        logger.info(f"Sending request to Grok API for practice area: {practice_area}")
        
        # Make API call (proven working pattern)
        response = requests.post(
            'https://api.x.ai/v1/chat/completions',
            headers=headers,
            json=payload,
            timeout=30
        )
        
        if response.status_code == 200:
            completion = response.json()
            if 'choices' in completion and len(completion['choices']) > 0:
                assistant_content = completion['choices'][0]['message']['content'].strip()
                logger.info(f"Received response: {len(assistant_content)} characters")
                
                # Save conversation to persistent storage
                try:
                    # Save user message
                    conversation_manager.save_message(client_id, practice_area, "user", message)
                    # Save assistant response
                    conversation_manager.save_message(client_id, practice_area, "assistant", assistant_content)
                    
                    # Get conversation summary for logging
                    summary = conversation_manager.get_conversation_summary(client_id, practice_area)
                    logger.info(f"💬 Conversation updated: {client_id[:8]}... | {practice_area} | Messages: {summary['message_count']}")
                    
                except Exception as e:
                    logger.error(f"Failed to save conversation: {e}")
                
                # Log conversation using available resources with security info
                try:
                    client_info = RateLimiter.get_client_id(request)
                    log_entry = f"Client: {client_info[:8]}... | Practice: {practice_area} | User: {message[:30]}... | AI: {assistant_content[:30]}..."
                    
                    if REDIS_URL:
                        logger.info(f"💾 [REDIS] Conversation: {log_entry}")
                    elif DATABASE_URL:
                        logger.info(f"🗄️ [NEON] Conversation: {log_entry}")
                    else:
                        logger.info(f"📝 [LOG] Conversation: {log_entry}")
                        
                    # Log successful interaction for security monitoring
                    logger.info(f"🔒 [SECURITY] Valid interaction from {client_info[:8]}... | Practice: {practice_area} | Message length: {len(message)}")
                except Exception as e:
                    logger.error(f"Conversation logging error: {e}")
                
                return jsonify({
                    "choices": [{"delta": {"content": assistant_content}}],
                    "client_id": client_id,
                    "practice_area": practice_area,
                    "conversation_summary": conversation_manager.get_conversation_summary(client_id, practice_area)
                })
        
        logger.error(f"XAI API error: {response.status_code} - {response.text}")
        return jsonify({"error": "AI service temporarily unavailable"}), 503
    
    except Exception as e:
        logger.error(f"Chat endpoint error: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500

# Error handlers
@app.errorhandler(404)
def not_found(e):
    return jsonify({"error": "Not found"}), 404

@app.errorhandler(500)
def server_error(e):
    logger.error(f"Server error: {str(e)}")
    return jsonify({"error": "Internal server error"}), 500

# For Vercel
app.debug = False

if __name__ == '__main__':
    app.run(debug=True, port=5000)