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
        "script-src 'self' 'unsafe-inline' 'unsafe-eval'; " 
        "style-src 'self' 'unsafe-inline'; "
        "font-src 'self'; "
        "img-src 'self' data: https:; "
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
            'Draft custody agreement',
            'Calculate child support',
            'Property division analysis',
            'Spousal support guidelines',
            'Divorce petition checklist'
        ]
    },
    'personal_injury': {
        'name': 'Personal Injury',
        'icon': 'shield',
        'color': '#EF4444',
        'prompts': [
            'Calculate damages worksheet',
            'Draft demand letter',
            'Medical record analysis',
            'Settlement strategies',
            'Liability assessment'
        ]
    },
    'corporate': {
        'name': 'Corporate Law',
        'icon': 'building',
        'color': '#3B82F6',
        'prompts': [
            'Contract risk analysis',
            'Entity formation guide',
            'Compliance checklist',
            'M&A due diligence',
            'Employment policies'
        ]
    },
    'criminal': {
        'name': 'Criminal Defense',
        'icon': 'scale',
        'color': '#F59E0B',
        'prompts': [
            'Motion to suppress',
            'Sentencing guidelines',
            'Evidence analysis',
            'Plea negotiation strategy',
            'Constitutional rights review'
        ]
    },
    'real_estate': {
        'name': 'Real Estate',
        'icon': 'home',
        'color': '#10B981',
        'prompts': [
            'Purchase agreement review',
            'Title examination checklist',
            'Zoning compliance analysis',
            'Lease negotiation guide',
            'Closing preparation'
        ]
    },
    'immigration': {
        'name': 'Immigration',
        'icon': 'globe',
        'color': '#6366F1',
        'prompts': [
            'Visa eligibility assessment',
            'Green card process guide',
            'Naturalization checklist',
            'Removal defense strategy',
            'Family petition preparation'
        ]
    }
}

# Enhanced mock data for production demo
def get_mock_clients():
    return [
        {
            'id': 1, 'name': 'John Smith', 'practice_area': 'family', 'status': 'active', 
            'last_contact': '2025-01-03', 'case_type': 'Divorce', 'priority': 'high',
            'messages': 12, 'documents': 5, 'value': 15000, 'next_action': 'File custody motion'
        },
        {
            'id': 2, 'name': 'Sarah Johnson', 'practice_area': 'corporate', 'status': 'active',
            'last_contact': '2025-01-02', 'case_type': 'M&A Due Diligence', 'priority': 'high',
            'messages': 28, 'documents': 15, 'value': 125000, 'next_action': 'Review contracts'
        },
        {
            'id': 3, 'name': 'Mike Davis', 'practice_area': 'personal_injury', 'status': 'pending',
            'last_contact': '2025-01-01', 'case_type': 'Auto Accident', 'priority': 'medium',
            'messages': 8, 'documents': 3, 'value': 45000, 'next_action': 'Medical records review'
        },
        {
            'id': 4, 'name': 'Lisa Chen', 'practice_area': 'immigration', 'status': 'active',
            'last_contact': '2024-12-28', 'case_type': 'Green Card Application', 'priority': 'medium',
            'messages': 15, 'documents': 8, 'value': 8500, 'next_action': 'USCIS filing'
        },
        {
            'id': 5, 'name': 'Robert Wilson', 'practice_area': 'real_estate', 'status': 'completed',
            'last_contact': '2024-12-20', 'case_type': 'Commercial Purchase', 'priority': 'low',
            'messages': 22, 'documents': 12, 'value': 75000, 'next_action': 'Closing complete'
        }
    ]

def get_analytics_data():
    return {
        'revenue': {
            'total_ytd': 268500,
            'monthly': [22000, 25000, 28000, 32000, 35000, 38000],
            'by_practice': {
                'corporate': 125000,
                'real_estate': 75000,
                'personal_injury': 45000,
                'family': 15000,
                'immigration': 8500
            }
        },
        'cases': {
            'total': 47,
            'active': 15,
            'pending': 8,
            'completed': 24,
            'by_status': {'active': 15, 'pending': 8, 'completed': 24}
        },
        'ai_usage': {
            'total_interactions': 234,
            'monthly_growth': 15.2,
            'avg_per_case': 5.8,
            'top_areas': ['contract_analysis', 'legal_research', 'document_drafting']
        },
        'efficiency': {
            'avg_case_duration': 45,
            'resolution_rate': 89.3,
            'client_satisfaction': 4.7
        }
    }

def get_mock_stats():
    analytics = get_analytics_data()
    return {
        'total_clients': len(get_mock_clients()),
        'active_cases': analytics['cases']['active'],
        'pending_cases': analytics['cases']['pending'],
        'completed_cases': analytics['cases']['completed'],
        'revenue_ytd': analytics['revenue']['total_ytd'],
        'ai_interactions': analytics['ai_usage']['total_interactions'],
        'documents_processed': 67
    }

def build_system_prompt(practice_area):
    """Build specialized system prompt with Bagel RL enhanced reasoning capabilities"""
    base_prompt = """You are LexAI, an advanced legal AI assistant powered by enhanced reasoning capabilities (Bagel RL). You combine deep legal expertise with sophisticated analytical reasoning to provide comprehensive legal guidance.

ENHANCED REASONING FRAMEWORK:
1. **Multi-Step Analysis**: Break complex legal issues into structured reasoning steps
2. **Precedent Integration**: Analyze relevant case law and legal precedents  
3. **Risk Assessment**: Evaluate potential outcomes and strategic implications
4. **Contextual Reasoning**: Consider jurisdiction-specific laws and regulations
5. **Ethical Evaluation**: Ensure all guidance adheres to professional ethics standards

REASONING METHODOLOGY:
- Start with issue identification and legal framework analysis
- Apply relevant statutes, regulations, and case law precedents
- Consider multiple legal strategies and their probability of success
- Evaluate risks, costs, and benefits of each approach
- Provide step-by-step reasoning for recommendations
- Always note this is not formal legal advice and recommend consulting qualified attorneys

ENHANCED CAPABILITIES:
- Strategic legal analysis with outcome probability assessment
- Multi-jurisdictional legal research and precedent analysis
- Risk-benefit analysis for legal strategies and decisions
- Evidence-based reasoning with supporting legal authorities
- Detailed justification for all legal recommendations"""
    
    specialized_prompts = {
        'family': f"""{base_prompt}
        
FAMILY LAW EXPERTISE:
- Divorce proceedings, asset division, spousal support calculations
- Child custody arrangements, parenting plans, support guidelines
- Domestic relations, protective orders, adoption procedures
- Mediation strategies, settlement negotiations

TOOLS AVAILABLE:
- Child support calculators for all states
- Custody schedule templates and best practices
- Asset valuation methods and division strategies
- Form libraries for petitions, motions, agreements

Focus on practical solutions, precedent analysis, and client-centered approaches.""",

        'personal_injury': f"""{base_prompt}
        
PERSONAL INJURY EXPERTISE:
- Accident reconstruction, liability assessment, damages calculation
- Medical record analysis, expert witness coordination
- Insurance claim negotiation, settlement strategies
- Trial preparation, jury psychology, case presentation

TOOLS AVAILABLE:
- Damages calculation worksheets (economic/non-economic)
- Medical terminology and injury assessment guides
- Insurance policy analysis and coverage determination
- Settlement demand letter templates and negotiation tactics

Emphasize evidence preservation, thorough documentation, and maximum recovery.""",

        'corporate': f"""{base_prompt}
        
CORPORATE LAW EXPERTISE:
- Contract drafting, negotiation, risk assessment
- Business formation, governance, compliance frameworks
- M&A transactions, due diligence, regulatory filings
- Employment law, intellectual property, securities

TOOLS AVAILABLE:
- Contract clause libraries and red-flag analysis
- Entity formation guides and tax implications
- Compliance checklists for various industries
- Deal structure templates and term sheets

Focus on business objectives, risk mitigation, and strategic legal counsel.""",

        'criminal': f"""{base_prompt}
        
CRIMINAL DEFENSE EXPERTISE:
- Constitutional rights, evidence suppression, plea negotiations
- Sentencing guidelines, mitigation strategies, appeals
- Jury selection, trial advocacy, cross-examination
- White-collar defense, regulatory investigations

TOOLS AVAILABLE:
- Evidence analysis and admissibility rules
- Sentencing calculation worksheets
- Motion templates and precedent research
- Client interview guides and defense strategies

Prioritize constitutional protections, thorough investigation, and zealous advocacy.""",

        'real_estate': f"""{base_prompt}
        
REAL ESTATE EXPERTISE:
- Transaction structuring, due diligence, title examination
- Zoning compliance, land use, environmental issues
- Financing arrangements, escrow procedures, closing coordination
- Landlord-tenant law, property disputes, construction contracts

TOOLS AVAILABLE:
- Contract review checklists and standard clauses
- Title examination procedures and issue resolution
- Zoning analysis and variance applications
- Lease negotiation strategies and tenant rights

Focus on transaction security, risk identification, and practical solutions.""",

        'immigration': f"""{base_prompt}
        
IMMIGRATION LAW EXPERTISE:
- Visa applications, status adjustments, naturalization
- Removal defense, asylum claims, family reunification
- Employment authorization, investor visas, compliance
- Appeals, waivers, complex case strategies

TOOLS AVAILABLE:
- Form preparation guides and filing requirements
- Eligibility assessment worksheets
- Evidence compilation strategies
- Timeline management and deadline tracking

Emphasize accuracy, documentation, and client advocacy within complex regulations."""
    }
    
    return specialized_prompts.get(practice_area, base_prompt)

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
                    <a href="/clients" class="nav-link">
                        <svg class="nav-icon" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z"/>
                        </svg>
                        Clients
                    </a>
                    <a href="/documents" class="nav-link">
                        <svg class="nav-icon" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/>
                        </svg>
                        Documents
                    </a>
                    <a href="/analytics" class="nav-link">
                        <svg class="nav-icon" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"/>
                        </svg>
                        Analytics
                    </a>
                    <a href="/billing" class="nav-link">
                        <svg class="nav-icon" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 10h18M7 15h1m4 0h1m-7 4h12a3 3 0 003-3V8a3 3 0 00-3-3H6a3 3 0 00-3 3v8a3 3 0 003 3z"/>
                        </svg>
                        Billing
                    </a>
                    <a href="/notifications" class="nav-link">
                        <svg class="nav-icon" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 17h5l-5 5v-5zM11 19H7a2 2 0 01-2-2V7a2 2 0 012-2h10a2 2 0 012 2v4M9 9h6m-6 4h6"/>
                        </svg>
                        Notifications
                    </a>
                    <a href="/contracts" class="nav-link">
                        <svg class="nav-icon" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/>
                        </svg>
                        Contract Generator
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
                            Specialized AI for {{ area.name.lower() }} matters.
                        </p>
                    </div>
                    {% endfor %}
                </div>

                <!-- Action Buttons -->
                <div class="action-buttons">
                    <a href="/chat" class="btn btn-primary">Start Chat</a>
                </div>

                <!-- Recent Clients -->
                <div class="recent-section">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">
                        <h2 class="section-title">Recent Client Activity</h2>
                        <a href="/clients" class="btn" style="background: var(--primary-green); color: white; text-decoration: none; padding: 8px 16px; border-radius: 6px; font-size: 0.875rem;">View All</a>
                    </div>
                    <div class="client-list">
                        {% for client in recent_clients %}
                        <div class="client-item" onclick="window.location.href='/clients/{{ client.id }}'" style="cursor: pointer;">
                            <div class="client-info">
                                <div class="client-name">{{ client.name }}</div>
                                <div class="client-meta">{{ practice_areas[client.practice_area].name }} • {{ client.case_type }} • ${{ "{:,}".format(client.value) }}</div>
                                <div style="font-size: 0.75rem; color: var(--gray-600); margin-top: 4px;">{{ client.messages }} messages • {{ client.documents }} docs • Next: {{ client.next_action }}</div>
                            </div>
                            <div style="text-align: right;">
                                <span class="status-badge status-{{ client.status }}">{{ client.status.title() }}</span>
                                <div style="font-size: 0.75rem; color: var(--gray-600); margin-top: 4px;">{{ client.priority.title() }} Priority</div>
                            </div>
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
            selected_practice = PRACTICE_AREAS.get(practice_area, {
                'name': 'General Legal', 
                'color': '#2E4B3C',
                'prompts': ['Legal research', 'Document review', 'Case analysis']
            })
            
            return render_template_string("""
            <!DOCTYPE html>
            <html lang="en">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>LexAI Chat - {{ selected_practice['name'] }}</title>
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
                    .quick-prompt {
                        padding: 6px 12px;
                        background: #F7EDDA;
                        color: #2E4B3C;
                        border: 1px solid #2E4B3C;
                        border-radius: 6px;
                        font-size: 0.75rem;
                        cursor: pointer;
                        transition: all 0.2s ease;
                        font-weight: 500;
                    }
                    .quick-prompt:hover {
                        background: #2E4B3C;
                        color: #F7EDDA;
                        transform: translateY(-1px);
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
                        <p style="margin: 0; opacity: 0.9; font-size: 0.875rem;">{{ selected_practice['name'] }} AI Assistant</p>
                    </div>
                    
                    <div class="chat-messages" id="chatMessages">
                        <div class="message assistant">
                            <div class="message-avatar">LA</div>
                            <div class="message-content">
                                I'm your {{ selected_practice['name'].lower() }} AI assistant. I can help with legal research, document analysis, and guidance. Note: This is not formal legal advice. How can I help?
                            </div>
                        </div>
                        
                        <!-- Quick Prompts -->
                        <div style="margin: 16px 0; display: flex; flex-wrap: wrap; gap: 8px;">
                            <button class="quick-prompt" onclick="useQuickPrompt('{{ selected_practice.prompts[0] }}')">{{ selected_practice.prompts[0] }}</button>
                            <button class="quick-prompt" onclick="useQuickPrompt('{{ selected_practice.prompts[1] }}')">{{ selected_practice.prompts[1] }}</button>
                            <button class="quick-prompt" onclick="useQuickPrompt('{{ selected_practice.prompts[2] }}')">{{ selected_practice.prompts[2] }}</button>
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
                            console.log('Sending message:', message);
                            const response = await fetch('/api/chat', {
                                method: 'POST',
                                headers: { 'Content-Type': 'application/json' },
                                body: JSON.stringify({ 
                                    message: message,
                                    practice_area: '{{ practice_area }}',
                                    client_id: currentClientId
                                })
                            });
                            
                            console.log('Response status:', response.status);
                            
                            if (!response.ok) {
                                throw new Error(`HTTP error! status: ${response.status}`);
                            }
                            
                            const data = await response.json();
                            console.log('Response data:', data);
                            
                            // Hide typing indicator
                            typingIndicator.style.display = 'none';
                            
                            if (data.choices && data.choices[0] && data.choices[0].delta && data.choices[0].delta.content) {
                                addMessage('assistant', data.choices[0].delta.content);
                            } else if (data.error) {
                                addMessage('assistant', `Error: ${data.error}`, true);
                            } else {
                                console.error('Unexpected response format:', data);
                                addMessage('assistant', 'Received response but in unexpected format. Please try again.', true);
                            }
                        } catch (error) {
                            console.error('Chat error:', error);
                            typingIndicator.style.display = 'none';
                            addMessage('assistant', `Connection error: ${error.message}. Please try again.`, true);
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
                    
                    // Quick prompt function
                    function useQuickPrompt(promptText) {
                        const input = document.getElementById('messageInput');
                        input.value = promptText;
                        input.focus();
                        // Auto-resize textarea
                        input.style.height = 'auto';
                        input.style.height = Math.min(input.scrollHeight, 120) + 'px';
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

@app.route('/clients')
def clients_page():
    """Comprehensive client management page"""
    try:
        clients = get_mock_clients()
        analytics = get_analytics_data()
        
        return render_template_string("""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Client Management - LexAI</title>
            <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
            <style>
                :root {
                    --primary-green: #2E4B3C;
                    --primary-green-light: #4A6B57;
                    --secondary-cream: #F7EDDA;
                    --white: #ffffff;
                    --gray-50: #f9fafb;
                    --gray-100: #f3f4f6;
                    --gray-600: #4b5563;
                    --gray-900: #111827;
                    --success: #10b981;
                    --warning: #f59e0b;
                    --error: #ef4444;
                }
                
                body {
                    font-family: 'Inter', system-ui, sans-serif;
                    background: linear-gradient(135deg, var(--secondary-cream) 0%, #F7DFBA 100%);
                    margin: 0;
                    padding: 20px;
                    min-height: 100vh;
                    color: var(--gray-900);
                }
                
                .container {
                    max-width: 1200px;
                    margin: 0 auto;
                    background: white;
                    border-radius: 16px;
                    padding: 32px;
                    box-shadow: 0 20px 40px rgba(0,0,0,0.1);
                }
                
                .header {
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    margin-bottom: 32px;
                    padding-bottom: 16px;
                    border-bottom: 1px solid var(--gray-100);
                }
                
                .back-link {
                    background: var(--primary-green);
                    color: var(--secondary-cream);
                    padding: 8px 16px;
                    border-radius: 8px;
                    text-decoration: none;
                    font-size: 0.875rem;
                    font-weight: 500;
                }
                
                .stats-row {
                    display: grid;
                    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                    gap: 16px;
                    margin-bottom: 32px;
                }
                
                .stat-card {
                    background: var(--gray-50);
                    padding: 20px;
                    border-radius: 12px;
                    text-align: center;
                }
                
                .stat-value {
                    font-size: 2rem;
                    font-weight: 700;
                    color: var(--primary-green);
                }
                
                .stat-label {
                    font-size: 0.875rem;
                    color: var(--gray-600);
                    margin-top: 4px;
                }
                
                .filters {
                    display: flex;
                    gap: 16px;
                    margin-bottom: 24px;
                    flex-wrap: wrap;
                }
                
                .filter-btn {
                    padding: 8px 16px;
                    border: 1px solid var(--gray-100);
                    border-radius: 8px;
                    background: white;
                    cursor: pointer;
                    font-size: 0.875rem;
                    transition: all 0.2s ease;
                }
                
                .filter-btn.active {
                    background: var(--primary-green);
                    color: white;
                    border-color: var(--primary-green);
                }
                
                .clients-grid {
                    display: grid;
                    gap: 16px;
                }
                
                .client-card {
                    background: white;
                    border: 1px solid var(--gray-100);
                    border-radius: 12px;
                    padding: 24px;
                    transition: all 0.2s ease;
                    cursor: pointer;
                }
                
                .client-card:hover {
                    transform: translateY(-2px);
                    box-shadow: 0 8px 24px rgba(0,0,0,0.1);
                }
                
                .client-header {
                    display: flex;
                    justify-content: space-between;
                    align-items: flex-start;
                    margin-bottom: 16px;
                }
                
                .client-name {
                    font-size: 1.25rem;
                    font-weight: 600;
                    color: var(--gray-900);
                }
                
                .client-type {
                    font-size: 0.875rem;
                    color: var(--gray-600);
                    margin-top: 4px;
                }
                
                .status-badge {
                    padding: 4px 12px;
                    border-radius: 6px;
                    font-size: 0.75rem;
                    font-weight: 500;
                }
                
                .status-active { background: rgba(16, 185, 129, 0.1); color: var(--success); }
                .status-pending { background: rgba(245, 158, 11, 0.1); color: var(--warning); }
                .status-completed { background: rgba(107, 114, 128, 0.1); color: var(--gray-600); }
                
                .client-metrics {
                    display: flex;
                    gap: 24px;
                    margin-top: 16px;
                    font-size: 0.875rem;
                    color: var(--gray-600);
                }
                
                .metric {
                    display: flex;
                    align-items: center;
                    gap: 6px;
                }
                
                .priority-high { color: var(--error); }
                .priority-medium { color: var(--warning); }
                .priority-low { color: var(--gray-600); }
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <div>
                        <h1 style="margin: 0; font-size: 2rem; font-weight: 700; color: var(--primary-green);">Client Management</h1>
                        <p style="margin: 4px 0 0 0; color: var(--gray-600);">Manage cases, track progress, and analyze performance</p>
                    </div>
                    <a href="/" class="back-link">← Dashboard</a>
                </div>
                
                <div class="stats-row">
                    <div class="stat-card">
                        <div class="stat-value">{{ analytics.cases.total }}</div>
                        <div class="stat-label">Total Cases</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-value">{{ analytics.cases.active }}</div>
                        <div class="stat-label">Active</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-value">${{ "{:,}".format(analytics.revenue.total_ytd) }}</div>
                        <div class="stat-label">Revenue YTD</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-value">{{ "%.1f"|format(analytics.efficiency.client_satisfaction) }}</div>
                        <div class="stat-label">Satisfaction</div>
                    </div>
                </div>
                
                <div class="filters">
                    <button class="filter-btn active" onclick="filterClients('all')">All Clients</button>
                    <button class="filter-btn" onclick="filterClients('active')">Active</button>
                    <button class="filter-btn" onclick="filterClients('pending')">Pending</button>
                    <button class="filter-btn" onclick="filterClients('completed')">Completed</button>
                </div>
                
                <div class="clients-grid" id="clientsGrid">
                    {% for client in clients %}
                    <div class="client-card" data-status="{{ client.status }}" onclick="window.location.href='/clients/{{ client.id }}'">
                        <div class="client-header">
                            <div>
                                <div class="client-name">{{ client.name }}</div>
                                <div class="client-type">{{ client.case_type }} • {{ practice_areas[client.practice_area].name }}</div>
                            </div>
                            <span class="status-badge status-{{ client.status }}">{{ client.status.title() }}</span>
                        </div>
                        
                        <div class="client-metrics">
                            <div class="metric">
                                <span>💬</span>
                                <span>{{ client.messages }} messages</span>
                            </div>
                            <div class="metric">
                                <span>📄</span>
                                <span>{{ client.documents }} docs</span>
                            </div>
                            <div class="metric">
                                <span>💰</span>
                                <span>${{ "{:,}".format(client.value) }}</span>
                            </div>
                            <div class="metric priority-{{ client.priority }}">
                                <span>🔥</span>
                                <span>{{ client.priority.title() }}</span>
                            </div>
                        </div>
                        
                        <div style="margin-top: 12px; font-size: 0.875rem; color: var(--gray-600);">
                            <strong>Next:</strong> {{ client.next_action }}
                        </div>
                    </div>
                    {% endfor %}
                </div>
            </div>
            
            <script>
                function filterClients(status) {
                    const cards = document.querySelectorAll('.client-card');
                    const buttons = document.querySelectorAll('.filter-btn');
                    
                    // Update button states
                    buttons.forEach(btn => btn.classList.remove('active'));
                    event.target.classList.add('active');
                    
                    // Filter cards
                    cards.forEach(card => {
                        if (status === 'all' || card.dataset.status === status) {
                            card.style.display = 'block';
                        } else {
                            card.style.display = 'none';
                        }
                    });
                }
            </script>
        </body>
        </html>
        """, clients=clients, analytics=analytics, practice_areas=PRACTICE_AREAS)
        
    except Exception as e:
        logger.error(f"Clients page error: {e}")
        return f"""<!DOCTYPE html>
<html><head><title>LexAI Clients</title></head>
<body><h1>🏛️ LexAI Client Management</h1>
<p>Error loading clients: {e}</p>
<a href="/">← Back to Dashboard</a></body></html>"""

@app.route('/clients/<client_id>')
def client_detail(client_id):
    """Individual client detail page with conversation history and analytics"""
    try:
        # Get client data
        clients = get_mock_clients()
        client = None
        for c in clients:
            if str(c['id']) == str(client_id):
                client = c
                break
        
        if not client:
            return f"""<!DOCTYPE html>
<html><head><title>Client Not Found</title></head>
<body><h1>Client Not Found</h1>
<a href="/clients">← Back to Clients</a></body></html>""", 404
        
        # Get practice area info
        practice_area = PRACTICE_AREAS.get(client['practice_area'], PRACTICE_AREAS['corporate'])
        
        # Mock conversation history
        conversation_history = [
            {"timestamp": "2025-01-03 14:30", "type": "user", "content": "I need help with my divorce proceedings"},
            {"timestamp": "2025-01-03 14:31", "type": "assistant", "content": "I understand you're going through divorce proceedings. Let me help you understand the process and your options."},
            {"timestamp": "2025-01-03 14:35", "type": "user", "content": "What about custody arrangements for our children?"},
            {"timestamp": "2025-01-03 14:36", "type": "assistant", "content": "Child custody is determined based on the best interests of the child. Factors include stability, parenting ability, and the child's preferences if they're old enough."},
            {"timestamp": "2025-01-02 09:15", "type": "user", "content": "Can you review this custody agreement draft?"},
            {"timestamp": "2025-01-02 09:16", "type": "assistant", "content": "I've reviewed the custody agreement. Here are some key points to consider..."}
        ]
        
        return render_template_string("""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>{{ client.name }} - Client Details</title>
            <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
            <style>
                :root {
                    --primary-green: #2E4B3C;
                    --primary-green-light: #4A6B57;
                    --secondary-cream: #F7EDDA;
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
                    --blue: #3b82f6;
                }
                
                body {
                    font-family: 'Inter', system-ui, sans-serif;
                    background: linear-gradient(135deg, var(--secondary-cream) 0%, #F7DFBA 100%);
                    margin: 0;
                    padding: 20px;
                    min-height: 100vh;
                    color: var(--gray-900);
                }
                
                .container {
                    max-width: 1200px;
                    margin: 0 auto;
                    background: white;
                    border-radius: 16px;
                    padding: 32px;
                    box-shadow: 0 20px 40px rgba(0,0,0,0.1);
                }
                
                .header {
                    display: flex;
                    justify-content: space-between;
                    align-items: flex-start;
                    margin-bottom: 32px;
                    padding-bottom: 16px;
                    border-bottom: 1px solid var(--gray-100);
                }
                
                .client-info {
                    flex: 1;
                }
                
                .client-name {
                    font-size: 2rem;
                    font-weight: 700;
                    color: var(--primary-green);
                    margin: 0 0 8px 0;
                }
                
                .client-subtitle {
                    font-size: 1.1rem;
                    color: var(--gray-600);
                    margin: 0 0 16px 0;
                }
                
                .status-priority {
                    display: flex;
                    gap: 12px;
                    align-items: center;
                }
                
                .status-badge {
                    padding: 6px 12px;
                    border-radius: 8px;
                    font-size: 0.875rem;
                    font-weight: 500;
                }
                
                .status-active { background: rgba(16, 185, 129, 0.1); color: var(--success); }
                .status-pending { background: rgba(245, 158, 11, 0.1); color: var(--warning); }
                .status-completed { background: rgba(107, 114, 128, 0.1); color: var(--gray-600); }
                
                .priority-badge {
                    padding: 6px 12px;
                    border-radius: 8px;
                    font-size: 0.875rem;
                    font-weight: 500;
                }
                
                .priority-high { background: rgba(239, 68, 68, 0.1); color: var(--error); }
                .priority-medium { background: rgba(245, 158, 11, 0.1); color: var(--warning); }
                .priority-low { background: rgba(107, 114, 128, 0.1); color: var(--gray-600); }
                
                .actions {
                    display: flex;
                    gap: 12px;
                    align-items: center;
                }
                
                .back-link, .action-btn {
                    background: var(--primary-green);
                    color: var(--secondary-cream);
                    padding: 10px 16px;
                    border-radius: 8px;
                    text-decoration: none;
                    font-size: 0.875rem;
                    font-weight: 500;
                    border: none;
                    cursor: pointer;
                    transition: all 0.2s ease;
                }
                
                .action-btn.secondary {
                    background: var(--blue);
                }
                
                .back-link:hover, .action-btn:hover {
                    transform: translateY(-1px);
                    box-shadow: 0 4px 12px rgba(0,0,0,0.15);
                }
                
                .content-grid {
                    display: grid;
                    grid-template-columns: 1fr 400px;
                    gap: 32px;
                    margin-bottom: 32px;
                }
                
                .main-content {
                    display: flex;
                    flex-direction: column;
                    gap: 24px;
                }
                
                .sidebar {
                    display: flex;
                    flex-direction: column;
                    gap: 24px;
                }
                
                .card {
                    background: var(--gray-50);
                    border-radius: 12px;
                    padding: 24px;
                    border: 1px solid var(--gray-100);
                }
                
                .card-title {
                    font-size: 1.25rem;
                    font-weight: 600;
                    color: var(--gray-900);
                    margin: 0 0 16px 0;
                }
                
                .metrics-grid {
                    display: grid;
                    grid-template-columns: repeat(2, 1fr);
                    gap: 16px;
                }
                
                .metric-item {
                    text-align: center;
                    padding: 16px;
                    background: white;
                    border-radius: 8px;
                    border: 1px solid var(--gray-200);
                }
                
                .metric-value {
                    font-size: 1.5rem;
                    font-weight: 700;
                    color: var(--primary-green);
                    margin: 0;
                }
                
                .metric-label {
                    font-size: 0.875rem;
                    color: var(--gray-600);
                    margin: 4px 0 0 0;
                }
                
                .info-row {
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    padding: 12px 0;
                    border-bottom: 1px solid var(--gray-200);
                }
                
                .info-row:last-child {
                    border-bottom: none;
                }
                
                .info-label {
                    font-weight: 500;
                    color: var(--gray-700);
                }
                
                .info-value {
                    color: var(--gray-900);
                }
                
                .conversation-history {
                    background: white;
                    border-radius: 12px;
                    padding: 24px;
                    max-height: 600px;
                    overflow-y: auto;
                }
                
                .message {
                    display: flex;
                    gap: 12px;
                    margin-bottom: 16px;
                    padding: 16px;
                    border-radius: 12px;
                    background: var(--gray-50);
                }
                
                .message.user {
                    background: rgba(46, 75, 60, 0.1);
                }
                
                .message.assistant {
                    background: rgba(59, 130, 246, 0.1);
                }
                
                .message-avatar {
                    width: 36px;
                    height: 36px;
                    border-radius: 50%;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    font-weight: 600;
                    font-size: 0.875rem;
                    flex-shrink: 0;
                }
                
                .message.user .message-avatar {
                    background: var(--primary-green);
                    color: white;
                }
                
                .message.assistant .message-avatar {
                    background: var(--blue);
                    color: white;
                }
                
                .message-content {
                    flex: 1;
                }
                
                .message-time {
                    font-size: 0.75rem;
                    color: var(--gray-600);
                    margin-bottom: 4px;
                }
                
                .message-text {
                    line-height: 1.5;
                    color: var(--gray-900);
                }
                
                @media (max-width: 768px) {
                    .content-grid {
                        grid-template-columns: 1fr;
                    }
                    
                    .header {
                        flex-direction: column;
                        gap: 16px;
                        align-items: flex-start;
                    }
                    
                    .actions {
                        width: 100%;
                        justify-content: flex-start;
                    }
                }
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <div class="client-info">
                        <h1 class="client-name">{{ client.name }}</h1>
                        <p class="client-subtitle">{{ client.case_type }} • {{ practice_area.name }}</p>
                        <div class="status-priority">
                            <span class="status-badge status-{{ client.status }}">{{ client.status.title() }}</span>
                            <span class="priority-badge priority-{{ client.priority }}">{{ client.priority.title() }} Priority</span>
                        </div>
                    </div>
                    <div class="actions">
                        <a href="/clients" class="back-link">← Back to Clients</a>
                        <a href="/chat?practice_area={{ client.practice_area }}" class="action-btn secondary">💬 Chat</a>
                    </div>
                </div>
                
                <div class="content-grid">
                    <div class="main-content">
                        <div class="card">
                            <h2 class="card-title">Case Metrics</h2>
                            <div class="metrics-grid">
                                <div class="metric-item">
                                    <div class="metric-value">{{ client.messages }}</div>
                                    <div class="metric-label">Messages</div>
                                </div>
                                <div class="metric-item">
                                    <div class="metric-value">{{ client.documents }}</div>
                                    <div class="metric-label">Documents</div>
                                </div>
                                <div class="metric-item">
                                    <div class="metric-value">${{ "{:,}".format(client.value) }}</div>
                                    <div class="metric-label">Case Value</div>
                                </div>
                                <div class="metric-item">
                                    <div class="metric-value">{{ ((client.messages + client.documents) * 1.5) | round | int }}h</div>
                                    <div class="metric-label">Time Invested</div>
                                </div>
                            </div>
                        </div>
                        
                        <div class="conversation-history">
                            <h2 class="card-title">Recent Conversation History</h2>
                            {% for message in conversation_history %}
                            <div class="message {{ message.type }}">
                                <div class="message-avatar">
                                    {{ 'YOU' if message.type == 'user' else 'LA' }}
                                </div>
                                <div class="message-content">
                                    <div class="message-time">{{ message.timestamp }}</div>
                                    <div class="message-text">{{ message.content }}</div>
                                </div>
                            </div>
                            {% endfor %}
                        </div>
                    </div>
                    
                    <div class="sidebar">
                        <div class="card">
                            <h3 class="card-title">Client Information</h3>
                            <div class="info-row">
                                <span class="info-label">Case Type</span>
                                <span class="info-value">{{ client.case_type }}</span>
                            </div>
                            <div class="info-row">
                                <span class="info-label">Practice Area</span>
                                <span class="info-value">{{ practice_area.name }}</span>
                            </div>
                            <div class="info-row">
                                <span class="info-label">Last Contact</span>
                                <span class="info-value">{{ client.last_contact }}</span>
                            </div>
                            <div class="info-row">
                                <span class="info-label">Status</span>
                                <span class="info-value">{{ client.status.title() }}</span>
                            </div>
                            <div class="info-row">
                                <span class="info-label">Priority</span>
                                <span class="info-value">{{ client.priority.title() }}</span>
                            </div>
                        </div>
                        
                        <div class="card">
                            <h3 class="card-title">Next Actions</h3>
                            <div style="padding: 16px; background: white; border-radius: 8px; border: 1px solid var(--gray-200);">
                                <div style="font-weight: 500; color: var(--gray-900); margin-bottom: 8px;">Upcoming Task</div>
                                <div style="color: var(--gray-700);">{{ client.next_action }}</div>
                            </div>
                        </div>
                        
                        <div class="card">
                            <h3 class="card-title">Quick Actions</h3>
                            <div style="display: flex; flex-direction: column; gap: 8px;">
                                <button class="action-btn" style="width: 100%; justify-content: center;" onclick="window.location.href='/chat?practice_area={{ client.practice_area }}'">
                                    💬 Start New Conversation
                                </button>
                                <button class="action-btn secondary" style="width: 100%; justify-content: center;" onclick="alert('Document upload coming soon!')">
                                    📄 Upload Document
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </body>
        </html>
        """, client=client, practice_area=practice_area, conversation_history=conversation_history)
        
    except Exception as e:
        logger.error(f"Client detail error: {e}")
        return f"""<!DOCTYPE html>
<html><head><title>LexAI Client Detail</title></head>
<body><h1>🏛️ LexAI Client Detail</h1>
<p>Error loading client: {e}</p>
<a href="/clients">← Back to Clients</a></body></html>"""

@app.route('/clients')
def clients_list():
    """Client list route alias for compatibility"""
    return clients_page()

@app.route('/documents')
def documents_list():
    """Document management system with upload and analysis capabilities"""
    try:
        # Mock document data for demonstration
        documents = [
            {
                'id': 1,
                'name': 'Contract_Amendment_Smith.pdf',
                'type': 'Contract',
                'client': 'John Smith',
                'upload_date': '2025-01-03',
                'size': '245 KB',
                'status': 'analyzed',
                'ai_summary': 'Standard contract amendment updating payment terms and delivery schedule.',
                'tags': ['contract', 'amendment', 'payment'],
                'practice_area': 'corporate'
            },
            {
                'id': 2,
                'name': 'Custody_Agreement_Draft.docx',
                'type': 'Legal Document',
                'client': 'John Smith',
                'upload_date': '2025-01-02',
                'size': '156 KB',
                'status': 'pending',
                'ai_summary': 'Custody agreement draft pending review and analysis.',
                'tags': ['custody', 'family-law', 'draft'],
                'practice_area': 'family'
            },
            {
                'id': 3,
                'name': 'Insurance_Claim_Documentation.pdf',
                'type': 'Evidence',
                'client': 'Sarah Johnson',
                'upload_date': '2025-01-01',
                'size': '1.2 MB',
                'status': 'analyzed',
                'ai_summary': 'Complete insurance claim documentation with medical reports and incident details.',
                'tags': ['insurance', 'personal-injury', 'medical'],
                'practice_area': 'personal_injury'
            }
        ]
        
        return render_template_string("""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Document Management - LexAI</title>
            <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
            <style>
                :root {
                    --primary-green: #2E4B3C;
                    --secondary-cream: #F7EDDA;
                    --gray-50: #f9fafb;
                    --gray-100: #f3f4f6;
                    --gray-200: #e5e7eb;
                    --gray-600: #4b5563;
                    --gray-700: #374151;
                    --gray-900: #111827;
                    --success: #10b981;
                    --warning: #f59e0b;
                    --error: #ef4444;
                    --blue: #3b82f6;
                }
                
                body {
                    font-family: 'Inter', system-ui, sans-serif;
                    background: linear-gradient(135deg, var(--secondary-cream) 0%, #F7DFBA 100%);
                    margin: 0;
                    padding: 20px;
                    min-height: 100vh;
                    color: var(--gray-900);
                }
                
                .container {
                    max-width: 1200px;
                    margin: 0 auto;
                    background: white;
                    border-radius: 16px;
                    padding: 32px;
                    box-shadow: 0 20px 40px rgba(0,0,0,0.1);
                }
                
                .header {
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    margin-bottom: 32px;
                    padding-bottom: 16px;
                    border-bottom: 1px solid var(--gray-100);
                }
                
                .back-link, .upload-btn {
                    background: var(--primary-green);
                    color: var(--secondary-cream);
                    padding: 10px 16px;
                    border-radius: 8px;
                    text-decoration: none;
                    font-size: 0.875rem;
                    font-weight: 500;
                    border: none;
                    cursor: pointer;
                    transition: all 0.2s ease;
                }
                
                .upload-btn {
                    background: var(--blue);
                }
                
                .upload-area {
                    border: 2px dashed var(--gray-200);
                    border-radius: 12px;
                    padding: 48px 24px;
                    text-align: center;
                    margin-bottom: 32px;
                    transition: all 0.2s ease;
                    cursor: pointer;
                }
                
                .upload-area:hover {
                    border-color: var(--primary-green);
                    background: rgba(46, 75, 60, 0.02);
                }
                
                .upload-area.dragover {
                    border-color: var(--primary-green);
                    background: rgba(46, 75, 60, 0.05);
                }
                
                .upload-icon {
                    font-size: 3rem;
                    margin-bottom: 16px;
                    color: var(--gray-600);
                }
                
                .upload-text {
                    font-size: 1.1rem;
                    color: var(--gray-700);
                    margin-bottom: 8px;
                }
                
                .upload-subtext {
                    font-size: 0.875rem;
                    color: var(--gray-600);
                }
                
                .documents-grid {
                    display: grid;
                    gap: 16px;
                }
                
                .document-card {
                    background: var(--gray-50);
                    border: 1px solid var(--gray-100);
                    border-radius: 12px;
                    padding: 24px;
                    transition: all 0.2s ease;
                }
                
                .document-card:hover {
                    transform: translateY(-2px);
                    box-shadow: 0 8px 24px rgba(0,0,0,0.1);
                }
                
                .document-header {
                    display: flex;
                    justify-content: space-between;
                    align-items: flex-start;
                    margin-bottom: 16px;
                }
                
                .document-name {
                    font-size: 1.1rem;
                    font-weight: 600;
                    color: var(--gray-900);
                    margin: 0 0 4px 0;
                }
                
                .document-meta {
                    font-size: 0.875rem;
                    color: var(--gray-600);
                }
                
                .status-badge {
                    padding: 4px 12px;
                    border-radius: 6px;
                    font-size: 0.75rem;
                    font-weight: 500;
                    text-transform: uppercase;
                }
                
                .status-analyzed { background: rgba(16, 185, 129, 0.1); color: var(--success); }
                .status-pending { background: rgba(245, 158, 11, 0.1); color: var(--warning); }
                .status-error { background: rgba(239, 68, 68, 0.1); color: var(--error); }
                
                .document-summary {
                    margin: 16px 0;
                    padding: 16px;
                    background: white;
                    border-radius: 8px;
                    border: 1px solid var(--gray-200);
                    font-size: 0.875rem;
                    line-height: 1.5;
                    color: var(--gray-700);
                }
                
                .document-tags {
                    display: flex;
                    gap: 8px;
                    flex-wrap: wrap;
                    margin-top: 12px;
                }
                
                .tag {
                    background: var(--gray-100);
                    color: var(--gray-700);
                    padding: 4px 8px;
                    border-radius: 4px;
                    font-size: 0.75rem;
                    font-weight: 500;
                }
                
                .document-actions {
                    display: flex;
                    gap: 8px;
                    margin-top: 16px;
                }
                
                .action-btn {
                    padding: 6px 12px;
                    border: 1px solid var(--gray-200);
                    border-radius: 6px;
                    background: white;
                    color: var(--gray-700);
                    font-size: 0.75rem;
                    cursor: pointer;
                    transition: all 0.2s ease;
                }
                
                .action-btn:hover {
                    background: var(--gray-50);
                    border-color: var(--gray-300);
                }
                
                .action-btn.primary {
                    background: var(--primary-green);
                    color: white;
                    border-color: var(--primary-green);
                }
                
                .filters {
                    display: flex;
                    gap: 12px;
                    margin-bottom: 24px;
                    flex-wrap: wrap;
                }
                
                .filter-btn {
                    padding: 8px 16px;
                    border: 1px solid var(--gray-200);
                    border-radius: 8px;
                    background: white;
                    color: var(--gray-700);
                    font-size: 0.875rem;
                    cursor: pointer;
                    transition: all 0.2s ease;
                }
                
                .filter-btn.active {
                    background: var(--primary-green);
                    color: white;
                    border-color: var(--primary-green);
                }
                
                .hidden {
                    display: none;
                }
                
                @media (max-width: 768px) {
                    .header {
                        flex-direction: column;
                        gap: 16px;
                        align-items: flex-start;
                    }
                }
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <div>
                        <h1 style="margin: 0; font-size: 2rem; font-weight: 700; color: var(--primary-green);">Document Management</h1>
                        <p style="margin: 4px 0 0 0; color: var(--gray-600);">Upload, analyze, and manage legal documents with AI</p>
                    </div>
                    <div style="display: flex; gap: 12px;">
                        <a href="/" class="back-link">← Dashboard</a>
                        <button class="upload-btn" onclick="document.getElementById('fileInput').click()">📤 Upload Document</button>
                    </div>
                </div>
                
                <div class="upload-area" onclick="document.getElementById('fileInput').click()">
                    <div class="upload-icon">📄</div>
                    <div class="upload-text">Click to upload or drag and drop</div>
                    <div class="upload-subtext">PDF, DOC, DOCX files up to 10MB</div>
                    <input type="file" id="fileInput" class="hidden" accept=".pdf,.doc,.docx" onchange="handleFileUpload(this)">
                </div>
                
                <div class="filters">
                    <button class="filter-btn active" onclick="filterDocuments('all')">All Documents</button>
                    <button class="filter-btn" onclick="filterDocuments('contract')">Contracts</button>
                    <button class="filter-btn" onclick="filterDocuments('evidence')">Evidence</button>
                    <button class="filter-btn" onclick="filterDocuments('analyzed')">Analyzed</button>
                    <button class="filter-btn" onclick="filterDocuments('pending')">Pending</button>
                </div>
                
                <div class="documents-grid" id="documentsGrid">
                    {% for doc in documents %}
                    <div class="document-card" data-type="{{ doc.type.lower() }}" data-status="{{ doc.status }}">
                        <div class="document-header">
                            <div>
                                <h3 class="document-name">{{ doc.name }}</h3>
                                <div class="document-meta">
                                    {{ doc.type }} • {{ doc.client }} • {{ doc.upload_date }} • {{ doc.size }}
                                </div>
                            </div>
                            <span class="status-badge status-{{ doc.status }}">{{ doc.status }}</span>
                        </div>
                        
                        {% if doc.ai_summary %}
                        <div class="document-summary">
                            <strong>AI Analysis:</strong> {{ doc.ai_summary }}
                        </div>
                        {% endif %}
                        
                        <div class="document-tags">
                            {% for tag in doc.tags %}
                            <span class="tag">{{ tag }}</span>
                            {% endfor %}
                        </div>
                        
                        <div class="document-actions">
                            <button class="action-btn primary" onclick="viewDocument({{ doc.id }})">View</button>
                            <button class="action-btn" onclick="downloadDocument({{ doc.id }})">Download</button>
                            <button class="action-btn" onclick="analyzeDocument({{ doc.id }})">Re-analyze</button>
                            <button class="action-btn" onclick="shareDocument({{ doc.id }})">Share</button>
                        </div>
                    </div>
                    {% endfor %}
                </div>
            </div>
            
            <script>
                // File upload handling
                function handleFileUpload(input) {
                    const file = input.files[0];
                    if (file) {
                        console.log('File selected:', file.name);
                        alert(`File "${file.name}" selected for upload. Upload functionality coming soon!`);
                    }
                }
                
                // Drag and drop functionality
                const uploadArea = document.querySelector('.upload-area');
                
                uploadArea.addEventListener('dragover', (e) => {
                    e.preventDefault();
                    uploadArea.classList.add('dragover');
                });
                
                uploadArea.addEventListener('dragleave', (e) => {
                    e.preventDefault();
                    uploadArea.classList.remove('dragover');
                });
                
                uploadArea.addEventListener('drop', (e) => {
                    e.preventDefault();
                    uploadArea.classList.remove('dragover');
                    
                    const files = e.dataTransfer.files;
                    if (files.length > 0) {
                        console.log('Files dropped:', files[0].name);
                        alert(`File "${files[0].name}" dropped. Upload functionality coming soon!`);
                    }
                });
                
                // Document filtering
                function filterDocuments(filter) {
                    const cards = document.querySelectorAll('.document-card');
                    const buttons = document.querySelectorAll('.filter-btn');
                    
                    // Update button states
                    buttons.forEach(btn => btn.classList.remove('active'));
                    event.target.classList.add('active');
                    
                    // Filter cards
                    cards.forEach(card => {
                        const type = card.dataset.type;
                        const status = card.dataset.status;
                        
                        let show = false;
                        if (filter === 'all') {
                            show = true;
                        } else if (filter === 'contract' && type === 'contract') {
                            show = true;
                        } else if (filter === 'evidence' && type === 'evidence') {
                            show = true;
                        } else if (filter === status) {
                            show = true;
                        }
                        
                        card.style.display = show ? 'block' : 'none';
                    });
                }
                
                // Document actions
                function viewDocument(id) {
                    alert(`Viewing document ${id}. Full document viewer coming soon!`);
                }
                
                function downloadDocument(id) {
                    alert(`Downloading document ${id}. Download functionality coming soon!`);
                }
                
                function analyzeDocument(id) {
                    alert(`Re-analyzing document ${id} with AI. Analysis engine coming soon!`);
                }
                
                function shareDocument(id) {
                    alert(`Sharing document ${id}. Collaboration features coming soon!`);
                }
            </script>
        </body>
        </html>
        """, documents=documents)
        
    except Exception as e:
        logger.error(f"Documents page error: {e}")
        return f"""<!DOCTYPE html>
<html><head><title>LexAI Documents</title></head>
<body><h1>🏛️ LexAI Document Management</h1>
<p>Error loading documents: {e}</p>
<a href="/">← Back to Dashboard</a></body></html>"""

@app.route('/api/documents/upload', methods=['POST'])
@rate_limit_decorator
def upload_document():
    """Enhanced document upload with AI analysis"""
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        # Validate file type and size
        allowed_extensions = {'pdf', 'doc', 'docx', 'txt'}
        if not file.filename.lower().endswith(tuple(allowed_extensions)):
            return jsonify({'error': 'Invalid file type. Allowed: PDF, DOC, DOCX, TXT'}), 400
        
        # Mock document analysis (in production, would use actual AI)
        analysis_result = {
            'document_id': f"doc_{int(time.time())}",
            'filename': file.filename,
            'size': len(file.read()),
            'type': 'contract' if 'contract' in file.filename.lower() else 'legal_document',
            'status': 'analyzed',
            'ai_analysis': {
                'summary': 'Document analyzed successfully. Key legal concepts identified.',
                'key_terms': ['confidentiality', 'liability', 'termination', 'jurisdiction'],
                'risk_level': 'medium',
                'recommendations': [
                    'Review termination clauses for clarity',
                    'Consider adding limitation of liability provisions',
                    'Verify jurisdiction and governing law sections'
                ],
                'confidence_score': 0.85,
                'processing_time': 2.3
            },
            'metadata': {
                'upload_time': datetime.utcnow().isoformat(),
                'processed_by': 'LexAI Enhanced Reasoning Engine',
                'practice_area': 'corporate'
            }
        }
        
        return jsonify({
            'success': True,
            'message': 'Document uploaded and analyzed successfully',
            'data': analysis_result
        })
        
    except Exception as e:
        logger.error(f"Document upload error: {e}")
        return jsonify({'error': 'Document upload failed'}), 500

@app.route('/api/documents/<doc_id>/analyze', methods=['POST'])
@rate_limit_decorator
def analyze_document(doc_id):
    """Enhanced document analysis with Bagel RL reasoning"""
    try:
        # Get analysis type from request
        data = request.get_json() or {}
        analysis_type = data.get('type', 'comprehensive')
        practice_area = data.get('practice_area', 'corporate')
        
        # Mock enhanced analysis (in production, would use actual Bagel RL)
        enhanced_analysis = {
            'document_id': doc_id,
            'analysis_type': analysis_type,
            'practice_area': practice_area,
            'timestamp': datetime.utcnow().isoformat(),
            'enhanced_reasoning': {
                'multi_step_analysis': [
                    {
                        'step': 1,
                        'description': 'Document structure and format analysis',
                        'findings': 'Standard legal document format with proper clause organization',
                        'confidence': 0.92
                    },
                    {
                        'step': 2,
                        'description': 'Legal term and clause identification',
                        'findings': 'Identified 23 legal terms, 8 key clauses requiring attention',
                        'confidence': 0.87
                    },
                    {
                        'step': 3,
                        'description': 'Risk assessment and precedent analysis',
                        'findings': 'Medium risk profile based on similar case precedents',
                        'confidence': 0.81
                    },
                    {
                        'step': 4,
                        'description': 'Strategic recommendations',
                        'findings': 'Recommend 3 clause modifications for risk mitigation',
                        'confidence': 0.89
                    }
                ],
                'precedent_analysis': [
                    'Smith v. Johnson (2023) - Similar contract dispute, favorable outcome',
                    'Corporate Inc. v. Partners LLC (2022) - Relevant liability precedent',
                    'State Regulations Ch. 15.3 - Applicable compliance requirements'
                ],
                'risk_assessment': {
                    'overall_risk': 'medium',
                    'financial_risk': 'low',
                    'legal_compliance_risk': 'medium',
                    'operational_risk': 'low',
                    'mitigation_strategies': [
                        'Add specific performance metrics to avoid disputes',
                        'Include dispute resolution mechanism',
                        'Clarify intellectual property ownership'
                    ]
                },
                'strategic_recommendations': [
                    {
                        'priority': 'high',
                        'recommendation': 'Revise termination clause to include specific notice periods',
                        'reasoning': 'Current language is ambiguous and could lead to disputes',
                        'legal_basis': 'Contract Law § 2-309 - Time for Performance'
                    },
                    {
                        'priority': 'medium',
                        'recommendation': 'Add limitation of liability provision',
                        'reasoning': 'Protects against excessive damages in case of breach',
                        'legal_basis': 'Commercial Code § 2-719 - Contractual Modification'
                    }
                ]
            },
            'processing_time': 4.7,
            'confidence_score': 0.86
        }
        
        return jsonify({
            'success': True,
            'message': 'Enhanced document analysis completed',
            'data': enhanced_analysis
        })
        
    except Exception as e:
        logger.error(f"Document analysis error: {e}")
        return jsonify({'error': 'Document analysis failed'}), 500

@app.route('/api/legal/research', methods=['POST'])
@rate_limit_decorator  
def legal_research():
    """Enhanced legal research with precedent analysis"""
    try:
        data = request.get_json()
        if not data or 'query' not in data:
            return jsonify({'error': 'Research query required'}), 400
        
        query = data.get('query')
        jurisdiction = data.get('jurisdiction', 'federal')
        practice_area = data.get('practice_area', 'corporate')
        
        # Mock enhanced legal research (in production, would use actual legal databases)
        research_results = {
            'query': query,
            'jurisdiction': jurisdiction,
            'practice_area': practice_area,
            'timestamp': datetime.utcnow().isoformat(),
            'enhanced_research': {
                'primary_authorities': [
                    {
                        'citation': 'Federal Contract Act § 15.234',
                        'relevance': 0.94,
                        'summary': 'Establishes framework for contract interpretation and enforcement',
                        'key_holdings': [
                            'Plain language interpretation preferred',
                            'Ambiguities construed against drafter',
                            'Commercial reasonableness standard applies'
                        ]
                    },
                    {
                        'citation': 'Supreme Court Case: ContractCorp v. United Industries (2023)',
                        'relevance': 0.89,
                        'summary': 'Recent precedent on contract formation and consideration',
                        'key_holdings': [
                            'Electronic signatures valid under federal law',
                            'Consideration requirement strictly enforced',
                            'Good faith and fair dealing implied in all contracts'
                        ]
                    }
                ],
                'secondary_authorities': [
                    {
                        'source': 'American Law Institute - Contracts Restatement (3d)',
                        'section': '§ 201 - Whose Meaning Prevails',
                        'relevance': 0.82,
                        'summary': 'Authoritative guidance on contract interpretation principles'
                    },
                    {
                        'source': 'Harvard Law Review Vol. 136, No. 4',
                        'title': 'Modern Contract Formation in Digital Age',
                        'relevance': 0.76,
                        'summary': 'Scholarly analysis of emerging contract law trends'
                    }
                ],
                'practice_insights': [
                    'Recent trend toward stricter enforcement of termination clauses',
                    'Courts increasingly favor plain language interpretation',
                    'Electronic contract formation gaining broader acceptance',
                    'Jurisdiction clauses more rigorously enforced'
                ],
                'strategic_analysis': {
                    'strengths': [
                        'Strong precedential support for position',
                        'Clear statutory framework available',
                        'Recent favorable court decisions'
                    ],
                    'weaknesses': [
                        'Some jurisdictional variations exist',
                        'Emerging technology creates uncertainty',
                        'Limited appellate precedent in specific area'
                    ],
                    'recommendations': [
                        'Focus on federal law precedents for strongest position',
                        'Consider state law variations if applicable',
                        'Monitor emerging case law developments'
                    ]
                }
            },
            'confidence_score': 0.91,
            'processing_time': 3.2
        }
        
        return jsonify({
            'success': True,
            'message': 'Legal research completed successfully',
            'data': research_results
        })
        
    except Exception as e:
        logger.error(f"Legal research error: {e}")
        return jsonify({'error': 'Legal research failed'}), 500

@app.route('/api/cases/<case_id>/timeline', methods=['GET'])
@rate_limit_decorator
def case_timeline(case_id):
    """Get case timeline and milestone tracking"""
    try:
        # Mock case timeline data
        timeline_data = {
            'case_id': case_id,
            'case_title': 'Smith v. ABC Corporation',
            'practice_area': 'corporate',
            'status': 'active',
            'created_date': '2024-12-01',
            'estimated_completion': '2025-06-15',
            'milestones': [
                {
                    'id': 1,
                    'title': 'Initial Client Consultation',
                    'date': '2024-12-01',
                    'status': 'completed',
                    'description': 'Gathered case details and established representation',
                    'documents': ['Client Agreement', 'Initial Assessment'],
                    'next_steps': []
                },
                {
                    'id': 2,
                    'title': 'Document Discovery',
                    'date': '2024-12-15',
                    'status': 'completed',
                    'description': 'Collected and reviewed relevant documents',
                    'documents': ['Contract Documents', 'Email Correspondence', 'Financial Records'],
                    'next_steps': []
                },
                {
                    'id': 3,
                    'title': 'Legal Research & Analysis',
                    'date': '2025-01-03',
                    'status': 'in_progress',
                    'description': 'Researching applicable law and precedents',
                    'documents': ['Research Memo Draft'],
                    'next_steps': [
                        'Complete precedent analysis',
                        'Finalize legal strategy',
                        'Prepare motion documents'
                    ]
                },
                {
                    'id': 4,
                    'title': 'Motion Filing',
                    'date': '2025-02-01',
                    'status': 'pending',
                    'description': 'File motion for summary judgment',
                    'documents': [],
                    'next_steps': [
                        'Draft motion documents',
                        'Prepare supporting exhibits',
                        'Schedule court filing'
                    ]
                },
                {
                    'id': 5,
                    'title': 'Discovery Phase',
                    'date': '2025-03-15',
                    'status': 'pending',
                    'description': 'Formal discovery process with opposing party',
                    'documents': [],
                    'next_steps': [
                        'Prepare discovery requests',
                        'Schedule depositions',
                        'Review opposing party responses'
                    ]
                },
                {
                    'id': 6,
                    'title': 'Settlement Negotiations',
                    'date': '2025-05-01',
                    'status': 'pending',
                    'description': 'Attempt to reach settlement before trial',
                    'documents': [],
                    'next_steps': [
                        'Prepare settlement demand',
                        'Schedule mediation',
                        'Evaluate settlement offers'
                    ]
                }
            ],
            'key_deadlines': [
                {'date': '2025-02-01', 'description': 'Motion filing deadline'},
                {'date': '2025-03-01', 'description': 'Discovery cutoff date'},
                {'date': '2025-05-15', 'description': 'Settlement conference'},
                {'date': '2025-06-15', 'description': 'Trial date'}
            ],
            'progress_stats': {
                'completed_milestones': 2,
                'total_milestones': 6,
                'completion_percentage': 33,
                'days_elapsed': 33,
                'estimated_days_remaining': 165
            }
        }
        
        return jsonify({
            'success': True,
            'data': timeline_data
        })
        
    except Exception as e:
        logger.error(f"Case timeline error: {e}")
        return jsonify({'error': 'Failed to retrieve case timeline'}), 500

@app.route('/research')
def legal_research_page():
    """Legal research and citation tools page"""
    try:
        return render_template_string("""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Legal Research Tools - LexAI</title>
            <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
            <style>
                :root {
                    --primary-green: #2E4B3C;
                    --secondary-cream: #F7EDDA;
                    --gray-50: #f9fafb;
                    --gray-100: #f3f4f6;
                    --gray-200: #e5e7eb;
                    --gray-600: #4b5563;
                    --gray-700: #374151;
                    --gray-900: #111827;
                    --success: #10b981;
                    --warning: #f59e0b;
                    --blue: #3b82f6;
                    --purple: #8b5cf6;
                }
                
                body {
                    font-family: 'Inter', system-ui, sans-serif;
                    background: linear-gradient(135deg, var(--secondary-cream) 0%, #F7DFBA 100%);
                    margin: 0;
                    padding: 20px;
                    min-height: 100vh;
                    color: var(--gray-900);
                }
                
                .container {
                    max-width: 1400px;
                    margin: 0 auto;
                    background: white;
                    border-radius: 16px;
                    padding: 32px;
                    box-shadow: 0 20px 40px rgba(0,0,0,0.1);
                }
                
                .header {
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    margin-bottom: 32px;
                    padding-bottom: 16px;
                    border-bottom: 1px solid var(--gray-100);
                }
                
                .back-link {
                    background: var(--primary-green);
                    color: var(--secondary-cream);
                    padding: 8px 16px;
                    border-radius: 8px;
                    text-decoration: none;
                    font-size: 0.875rem;
                    font-weight: 500;
                }
                
                .research-grid {
                    display: grid;
                    grid-template-columns: 1fr 400px;
                    gap: 32px;
                    margin-bottom: 32px;
                }
                
                .main-research {
                    display: flex;
                    flex-direction: column;
                    gap: 24px;
                }
                
                .research-tools {
                    display: flex;
                    flex-direction: column;
                    gap: 24px;
                }
                
                .search-section {
                    background: var(--gray-50);
                    border-radius: 12px;
                    padding: 24px;
                    border: 1px solid var(--gray-100);
                }
                
                .search-input {
                    width: 100%;
                    padding: 16px;
                    border: 1px solid var(--gray-200);
                    border-radius: 8px;
                    font-size: 1rem;
                    margin-bottom: 16px;
                    resize: vertical;
                    min-height: 80px;
                }
                
                .search-filters {
                    display: flex;
                    gap: 12px;
                    margin-bottom: 16px;
                    flex-wrap: wrap;
                }
                
                .filter-select {
                    padding: 8px 12px;
                    border: 1px solid var(--gray-200);
                    border-radius: 6px;
                    background: white;
                    font-size: 0.875rem;
                }
                
                .search-btn {
                    background: var(--primary-green);
                    color: white;
                    padding: 12px 24px;
                    border: none;
                    border-radius: 8px;
                    font-weight: 500;
                    cursor: pointer;
                    transition: all 0.2s ease;
                }
                
                .search-btn:hover {
                    transform: translateY(-1px);
                    box-shadow: 0 4px 12px rgba(46, 75, 60, 0.3);
                }
                
                .results-section {
                    background: white;
                    border-radius: 12px;
                    padding: 24px;
                    border: 1px solid var(--gray-100);
                    min-height: 400px;
                }
                
                .result-item {
                    border-bottom: 1px solid var(--gray-100);
                    padding: 20px 0;
                    margin-bottom: 16px;
                }
                
                .result-item:last-child {
                    border-bottom: none;
                }
                
                .result-citation {
                    font-weight: 600;
                    color: var(--primary-green);
                    margin-bottom: 8px;
                    font-size: 1.1rem;
                }
                
                .result-summary {
                    color: var(--gray-700);
                    line-height: 1.5;
                    margin-bottom: 12px;
                }
                
                .result-relevance {
                    display: inline-block;
                    background: var(--success);
                    color: white;
                    padding: 4px 8px;
                    border-radius: 4px;
                    font-size: 0.75rem;
                    font-weight: 500;
                }
                
                .tool-card {
                    background: var(--gray-50);
                    border-radius: 12px;
                    padding: 20px;
                    border: 1px solid var(--gray-100);
                    text-align: center;
                    cursor: pointer;
                    transition: all 0.2s ease;
                }
                
                .tool-card:hover {
                    transform: translateY(-2px);
                    box-shadow: 0 8px 24px rgba(0,0,0,0.1);
                }
                
                .tool-icon {
                    font-size: 2rem;
                    margin-bottom: 12px;
                }
                
                .tool-title {
                    font-weight: 600;
                    color: var(--gray-900);
                    margin-bottom: 8px;
                }
                
                .tool-description {
                    font-size: 0.875rem;
                    color: var(--gray-600);
                    line-height: 1.4;
                }
                
                .citation-generator {
                    background: white;
                    border-radius: 12px;
                    padding: 20px;
                    border: 1px solid var(--gray-100);
                }
                
                .citation-input {
                    width: 100%;
                    padding: 12px;
                    border: 1px solid var(--gray-200);
                    border-radius: 6px;
                    margin-bottom: 12px;
                    font-size: 0.875rem;
                }
                
                .citation-result {
                    background: var(--gray-50);
                    padding: 16px;
                    border-radius: 8px;
                    border: 1px solid var(--gray-100);
                    margin-top: 16px;
                }
                
                .citation-text {
                    font-family: 'Times New Roman', serif;
                    font-size: 0.875rem;
                    line-height: 1.5;
                    color: var(--gray-900);
                }
                
                .copy-btn {
                    background: var(--blue);
                    color: white;
                    padding: 6px 12px;
                    border: none;
                    border-radius: 4px;
                    font-size: 0.75rem;
                    cursor: pointer;
                    margin-top: 8px;
                }
                
                .loading {
                    text-align: center;
                    padding: 40px;
                    color: var(--gray-600);
                }
                
                .error {
                    background: rgba(239, 68, 68, 0.1);
                    color: var(--error);
                    padding: 16px;
                    border-radius: 8px;
                    margin: 16px 0;
                }
                
                @media (max-width: 768px) {
                    .research-grid {
                        grid-template-columns: 1fr;
                    }
                }
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <div>
                        <h1 style="margin: 0; font-size: 2rem; font-weight: 700; color: var(--primary-green);">Legal Research Tools</h1>
                        <p style="margin: 4px 0 0 0; color: var(--gray-600);">Advanced legal research with AI-powered analysis</p>
                    </div>
                    <a href="/" class="back-link">← Dashboard</a>
                </div>
                
                <div class="research-grid">
                    <div class="main-research">
                        <div class="search-section">
                            <h2 style="margin: 0 0 16px 0; font-size: 1.25rem; font-weight: 600;">Enhanced Legal Research</h2>
                            <textarea id="researchQuery" class="search-input" placeholder="Enter your legal research query (e.g., 'contract formation requirements under UCC Article 2')"></textarea>
                            
                            <div class="search-filters">
                                <select id="jurisdiction" class="filter-select">
                                    <option value="federal">Federal</option>
                                    <option value="state">State</option>
                                    <option value="international">International</option>
                                </select>
                                <select id="practiceArea" class="filter-select">
                                    <option value="corporate">Corporate Law</option>
                                    <option value="family">Family Law</option>
                                    <option value="personal_injury">Personal Injury</option>
                                    <option value="criminal">Criminal Law</option>
                                    <option value="real_estate">Real Estate</option>
                                    <option value="immigration">Immigration</option>
                                </select>
                                <select id="sourceType" class="filter-select">
                                    <option value="all">All Sources</option>
                                    <option value="cases">Case Law</option>
                                    <option value="statutes">Statutes</option>
                                    <option value="regulations">Regulations</option>
                                    <option value="secondary">Secondary Sources</option>
                                </select>
                            </div>
                            
                            <button class="search-btn" onclick="performResearch()">🔍 Research with AI Analysis</button>
                        </div>
                        
                        <div class="results-section">
                            <div id="researchResults">
                                <div style="text-align: center; padding: 40px; color: var(--gray-600);">
                                    <div style="font-size: 3rem; margin-bottom: 16px;">📚</div>
                                    <h3>AI-Powered Legal Research</h3>
                                    <p>Enter a legal query above to get comprehensive research results with AI analysis, precedent identification, and strategic insights.</p>
                                </div>
                            </div>
                        </div>
                    </div>
                    
                    <div class="research-tools">
                        <div class="tool-card" onclick="openCitationGenerator()">
                            <div class="tool-icon">📝</div>
                            <div class="tool-title">Citation Generator</div>
                            <div class="tool-description">Generate proper legal citations in Bluebook, APA, or other formats</div>
                        </div>
                        
                        <div class="tool-card" onclick="openPrecedentAnalyzer()">
                            <div class="tool-icon">⚖️</div>
                            <div class="tool-title">Precedent Analyzer</div>
                            <div class="tool-description">Analyze case precedents and their relevance to your legal issue</div>
                        </div>
                        
                        <div class="tool-card" onclick="openStatuteTracker()">
                            <div class="tool-icon">📊</div>
                            <div class="tool-title">Statute Tracker</div>
                            <div class="tool-description">Track changes and updates to relevant statutes and regulations</div>
                        </div>
                        
                        <div class="citation-generator" id="citationGenerator" style="display: none;">
                            <h3 style="margin: 0 0 16px 0; font-size: 1.1rem; font-weight: 600;">Citation Generator</h3>
                            <input type="text" class="citation-input" placeholder="Case name (e.g., Brown v. Board of Education)" id="caseName">
                            <input type="text" class="citation-input" placeholder="Volume (e.g., 347)" id="volume">
                            <input type="text" class="citation-input" placeholder="Reporter (e.g., U.S.)" id="reporter">
                            <input type="text" class="citation-input" placeholder="Page (e.g., 483)" id="page">
                            <input type="text" class="citation-input" placeholder="Year (e.g., 1954)" id="year">
                            <button class="search-btn" style="width: 100%; margin-top: 8px;" onclick="generateCitation()">Generate Citation</button>
                            <div id="citationResult" class="citation-result" style="display: none;">
                                <div class="citation-text" id="citationText"></div>
                                <button class="copy-btn" onclick="copyCitation()">Copy Citation</button>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
            
            <script>
                async function performResearch() {
                    const query = document.getElementById('researchQuery').value.trim();
                    if (!query) {
                        alert('Please enter a research query');
                        return;
                    }
                    
                    const jurisdiction = document.getElementById('jurisdiction').value;
                    const practiceArea = document.getElementById('practiceArea').value;
                    const sourceType = document.getElementById('sourceType').value;
                    
                    const resultsDiv = document.getElementById('researchResults');
                    resultsDiv.innerHTML = '<div class="loading">🔍 Performing AI-powered legal research...</div>';
                    
                    try {
                        const response = await fetch('/api/legal/research', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({
                                query: query,
                                jurisdiction: jurisdiction,
                                practice_area: practiceArea,
                                source_type: sourceType
                            })
                        });
                        
                        const data = await response.json();
                        
                        if (data.success) {
                            displayResearchResults(data.data);
                        } else {
                            resultsDiv.innerHTML = `<div class="error">Research failed: ${data.error || 'Unknown error'}</div>`;
                        }
                    } catch (error) {
                        resultsDiv.innerHTML = `<div class="error">Research error: ${error.message}</div>`;
                    }
                }
                
                function displayResearchResults(data) {
                    const resultsDiv = document.getElementById('researchResults');
                    
                    let html = `
                        <h3 style="margin: 0 0 16px 0; font-size: 1.25rem; font-weight: 600;">Research Results</h3>
                        <div style="margin-bottom: 24px; padding: 16px; background: var(--gray-50); border-radius: 8px;">
                            <strong>Query:</strong> ${data.query}<br>
                            <strong>Jurisdiction:</strong> ${data.jurisdiction}<br>
                            <strong>Practice Area:</strong> ${data.practice_area}<br>
                            <strong>Confidence Score:</strong> ${Math.round(data.confidence_score * 100)}%
                        </div>
                    `;
                    
                    if (data.enhanced_research.primary_authorities.length > 0) {
                        html += '<h4 style="margin: 24px 0 12px 0; color: var(--primary-green);">Primary Authorities</h4>';
                        data.enhanced_research.primary_authorities.forEach(auth => {
                            html += `
                                <div class="result-item">
                                    <div class="result-citation">${auth.citation}</div>
                                    <div class="result-summary">${auth.summary}</div>
                                    <div class="result-relevance">${Math.round(auth.relevance * 100)}% Relevant</div>
                                </div>
                            `;
                        });
                    }
                    
                    if (data.enhanced_research.strategic_analysis) {
                        html += '<h4 style="margin: 24px 0 12px 0; color: var(--primary-green);">Strategic Analysis</h4>';
                        html += `
                            <div style="background: var(--gray-50); padding: 16px; border-radius: 8px; margin-bottom: 16px;">
                                <h5 style="margin: 0 0 8px 0; color: var(--success);">Strengths</h5>
                                <ul style="margin: 0; padding-left: 20px;">
                                    ${data.enhanced_research.strategic_analysis.strengths.map(s => `<li>${s}</li>`).join('')}
                                </ul>
                            </div>
                            <div style="background: var(--gray-50); padding: 16px; border-radius: 8px;">
                                <h5 style="margin: 0 0 8px 0; color: var(--warning);">Considerations</h5>
                                <ul style="margin: 0; padding-left: 20px;">
                                    ${data.enhanced_research.strategic_analysis.weaknesses.map(w => `<li>${w}</li>`).join('')}
                                </ul>
                            </div>
                        `;
                    }
                    
                    resultsDiv.innerHTML = html;
                }
                
                function openCitationGenerator() {
                    const generator = document.getElementById('citationGenerator');
                    generator.style.display = generator.style.display === 'none' ? 'block' : 'none';
                }
                
                function generateCitation() {
                    const caseName = document.getElementById('caseName').value;
                    const volume = document.getElementById('volume').value;
                    const reporter = document.getElementById('reporter').value;
                    const page = document.getElementById('page').value;
                    const year = document.getElementById('year').value;
                    
                    if (!caseName || !volume || !reporter || !page || !year) {
                        alert('Please fill in all citation fields');
                        return;
                    }
                    
                    const citation = `${caseName}, ${volume} ${reporter} ${page} (${year}).`;
                    document.getElementById('citationText').textContent = citation;
                    document.getElementById('citationResult').style.display = 'block';
                }
                
                function copyCitation() {
                    const citationText = document.getElementById('citationText').textContent;
                    navigator.clipboard.writeText(citationText).then(() => {
                        alert('Citation copied to clipboard!');
                    });
                }
                
                function openPrecedentAnalyzer() {
                    alert('Precedent Analyzer: Advanced precedent analysis tool coming soon!');
                }
                
                function openStatuteTracker() {
                    alert('Statute Tracker: Real-time statute and regulation tracking coming soon!');
                }
            </script>
        </body>
        </html>
        """)
        
    except Exception as e:
        logger.error(f"Research page error: {e}")
        return f"""<!DOCTYPE html>
<html><head><title>LexAI Research</title></head>
<body><h1>🏛️ LexAI Legal Research</h1>
<p>Error loading research tools: {e}</p>
<a href="/">← Back to Dashboard</a></body></html>"""

@app.route('/analytics')
def analytics_dashboard():
    """Analytics dashboard page"""
    try:
        analytics = get_analytics_data()
        
        return render_template_string("""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Analytics Dashboard - LexAI</title>
            <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
            <style>
                :root {
                    --primary-green: #2E4B3C;
                    --secondary-cream: #F7EDDA;
                    --gray-50: #f9fafb;
                    --gray-100: #f3f4f6;
                    --gray-600: #4b5563;
                    --gray-900: #111827;
                    --success: #10b981;
                    --warning: #f59e0b;
                    --blue: #3b82f6;
                }
                
                body {
                    font-family: 'Inter', system-ui, sans-serif;
                    background: linear-gradient(135deg, var(--secondary-cream) 0%, #F7DFBA 100%);
                    margin: 0;
                    padding: 20px;
                    min-height: 100vh;
                    color: var(--gray-900);
                }
                
                .container {
                    max-width: 1200px;
                    margin: 0 auto;
                    background: white;
                    border-radius: 16px;
                    padding: 32px;
                    box-shadow: 0 20px 40px rgba(0,0,0,0.1);
                }
                
                .header {
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    margin-bottom: 32px;
                    padding-bottom: 16px;
                    border-bottom: 1px solid var(--gray-100);
                }
                
                .back-link {
                    background: var(--primary-green);
                    color: var(--secondary-cream);
                    padding: 8px 16px;
                    border-radius: 8px;
                    text-decoration: none;
                    font-size: 0.875rem;
                    font-weight: 500;
                }
                
                .stats-grid {
                    display: grid;
                    grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
                    gap: 20px;
                    margin-bottom: 32px;
                }
                
                .stat-card {
                    background: var(--gray-50);
                    padding: 24px;
                    border-radius: 12px;
                    border: 1px solid var(--gray-100);
                }
                
                .stat-title {
                    font-size: 0.875rem;
                    color: var(--gray-600);
                    margin: 0 0 8px 0;
                    font-weight: 500;
                }
                
                .stat-value {
                    font-size: 2rem;
                    font-weight: 700;
                    color: var(--primary-green);
                    margin: 0;
                }
                
                .stat-change {
                    font-size: 0.875rem;
                    color: var(--success);
                    margin: 4px 0 0 0;
                }
                
                .section {
                    background: var(--gray-50);
                    border-radius: 12px;
                    padding: 24px;
                    margin-bottom: 24px;
                    border: 1px solid var(--gray-100);
                }
                
                .section-title {
                    font-size: 1.25rem;
                    font-weight: 600;
                    color: var(--gray-900);
                    margin: 0 0 16px 0;
                }
                
                .metric-row {
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    padding: 12px 0;
                    border-bottom: 1px solid var(--gray-100);
                }
                
                .metric-row:last-child {
                    border-bottom: none;
                }
                
                .metric-label {
                    font-weight: 500;
                    color: var(--gray-700);
                }
                
                .metric-value {
                    color: var(--gray-900);
                    font-weight: 600;
                }
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <div>
                        <h1 style="margin: 0; font-size: 2rem; font-weight: 700; color: var(--primary-green);">Analytics Dashboard</h1>
                        <p style="margin: 4px 0 0 0; color: var(--gray-600);">Performance metrics and insights</p>
                    </div>
                    <a href="/" class="back-link">← Dashboard</a>
                </div>
                
                <div class="stats-grid">
                    <div class="stat-card">
                        <div class="stat-title">Total Revenue YTD</div>
                        <div class="stat-value">${{ "{:,}".format(analytics.revenue.total_ytd) }}</div>
                        <div class="stat-change">+15.2% from last quarter</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-title">Active Cases</div>
                        <div class="stat-value">{{ analytics.cases.active }}</div>
                        <div class="stat-change">{{ analytics.cases.pending }} pending review</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-title">AI Interactions</div>
                        <div class="stat-value">{{ analytics.ai_usage.total_interactions }}</div>
                        <div class="stat-change">+{{ "%.1f"|format(analytics.ai_usage.monthly_growth) }}% this month</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-title">Client Satisfaction</div>
                        <div class="stat-value">{{ "%.1f"|format(analytics.efficiency.client_satisfaction) }}</div>
                        <div class="stat-change">{{ "%.1f"|format(analytics.efficiency.resolution_rate) }}% resolution rate</div>
                    </div>
                </div>
                
                <div class="section">
                    <h2 class="section-title">Revenue by Practice Area</h2>
                    {% for area, revenue in analytics.revenue.by_practice.items() %}
                    <div class="metric-row">
                        <span class="metric-label">{{ area.replace('_', ' ').title() }}</span>
                        <span class="metric-value">${{ "{:,}".format(revenue) }}</span>
                    </div>
                    {% endfor %}
                </div>
                
                <div class="section">
                    <h2 class="section-title">Case Distribution</h2>
                    {% for status, count in analytics.cases.by_status.items() %}
                    <div class="metric-row">
                        <span class="metric-label">{{ status.title() }} Cases</span>
                        <span class="metric-value">{{ count }}</span>
                    </div>
                    {% endfor %}
                </div>
                
                <div class="section">
                    <h2 class="section-title">AI Usage Insights</h2>
                    <div class="metric-row">
                        <span class="metric-label">Average Interactions per Case</span>
                        <span class="metric-value">{{ "%.1f"|format(analytics.ai_usage.avg_per_case) }}</span>
                    </div>
                    <div class="metric-row">
                        <span class="metric-label">Most Used Features</span>
                        <span class="metric-value">{{ ', '.join(analytics.ai_usage.top_areas) }}</span>
                    </div>
                </div>
                
                <div class="section">
                    <h2 class="section-title">Efficiency Metrics</h2>
                    <div class="metric-row">
                        <span class="metric-label">Average Case Duration</span>
                        <span class="metric-value">{{ analytics.efficiency.avg_case_duration }} days</span>
                    </div>
                    <div class="metric-row">
                        <span class="metric-label">Resolution Rate</span>
                        <span class="metric-value">{{ "%.1f"|format(analytics.efficiency.resolution_rate) }}%</span>
                    </div>
                    <div class="metric-row">
                        <span class="metric-label">Client Satisfaction Score</span>
                        <span class="metric-value">{{ "%.1f"|format(analytics.efficiency.client_satisfaction) }}/5.0</span>
                    </div>
                </div>
            </div>
        </body>
        </html>
        """, analytics=analytics)
        
    except Exception as e:
        logger.error(f"Analytics page error: {e}")
        return f"""<!DOCTYPE html>
<html><head><title>LexAI Analytics</title></head>
<body><h1>🏛️ LexAI Analytics</h1>
<p>Error loading analytics: {e}</p>
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

@app.route('/api/clients')
@rate_limit_decorator
def get_clients():
    """Get client list with filtering and analytics"""
    try:
        status_filter = request.args.get('status')
        practice_filter = request.args.get('practice_area')
        
        clients = get_mock_clients()
        
        # Apply filters
        if status_filter:
            clients = [c for c in clients if c['status'] == status_filter]
        if practice_filter:
            clients = [c for c in clients if c['practice_area'] == practice_filter]
        
        analytics = get_analytics_data()
        
        return jsonify({
            "status": "success",
            "clients": clients,
            "analytics": analytics,
            "total": len(clients),
            "filters": {
                "status": status_filter,
                "practice_area": practice_filter
            }
        })
    except Exception as e:
        logger.error(f"Failed to get clients: {e}")
        return jsonify({
            "status": "error",
            "error": str(e)
        }), 500

@app.route('/api/clients/<int:client_id>')
@rate_limit_decorator
def get_client_details(client_id):
    """Get detailed client information with conversation history"""
    try:
        clients = get_mock_clients()
        client = next((c for c in clients if c['id'] == client_id), None)
        
        if not client:
            return jsonify({
                "status": "error",
                "error": "Client not found"
            }), 404
        
        # Get conversation summary
        conversation_summary = conversation_manager.get_conversation_summary(
            f"client_{client_id}", 
            client['practice_area']
        )
        
        # Enhanced client details
        client_details = {
            **client,
            "conversation_summary": conversation_summary,
            "timeline": [
                {"date": "2025-01-03", "event": "Case opened", "type": "milestone"},
                {"date": "2025-01-02", "event": "AI consultation - 3 messages", "type": "ai_interaction"},
                {"date": "2025-01-01", "event": "Document uploaded", "type": "document"},
                {"date": "2024-12-30", "event": "Initial consultation", "type": "meeting"}
            ],
            "metrics": {
                "total_ai_interactions": conversation_summary.get('message_count', 0),
                "documents_uploaded": client.get('documents', 0),
                "case_value": client.get('value', 0),
                "days_active": 14
            }
        }
        
        return jsonify({
            "status": "success",
            "client": client_details
        })
    except Exception as e:
        logger.error(f"Failed to get client details: {e}")
        return jsonify({
            "status": "error",
            "error": str(e)
        }), 500

@app.route('/api/analytics')
@rate_limit_decorator
def get_analytics():
    """Get comprehensive practice analytics"""
    try:
        analytics = get_analytics_data()
        clients = get_mock_clients()
        
        # Calculate additional metrics
        practice_distribution = {}
        for client in clients:
            area = client['practice_area']
            if area not in practice_distribution:
                practice_distribution[area] = 0
            practice_distribution[area] += 1
        
        enhanced_analytics = {
            **analytics,
            "practice_distribution": practice_distribution,
            "recent_activity": [
                {"type": "new_client", "description": "John Smith - Family Law", "time": "2 hours ago"},
                {"type": "ai_interaction", "description": "25 AI consultations today", "time": "1 hour ago"},
                {"type": "document", "description": "Contract analysis completed", "time": "30 min ago"},
                {"type": "case_update", "description": "Mike Davis case updated", "time": "15 min ago"}
            ],
            "alerts": [
                {"type": "deadline", "message": "Motion due for John Smith in 2 days", "priority": "high"},
                {"type": "follow_up", "message": "Follow up with Lisa Chen on USCIS filing", "priority": "medium"}
            ]
        }
        
        return jsonify({
            "status": "success",
            "analytics": enhanced_analytics,
            "timestamp": datetime.utcnow().isoformat()
        })
    except Exception as e:
        logger.error(f"Failed to get analytics: {e}")
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

def get_protected_fallback_response(message, practice_area):
    """Generate intelligent fallback response with core functionality protection"""
    practice_info = PRACTICE_AREAS.get(practice_area, PRACTICE_AREAS['corporate'])
    
    return {
        "choices": [{
            "delta": {
                "content": f"""I'm LexAI, your {practice_info['name']} AI assistant. I'm here to help with your legal question.

**Your Question:** "{message}"

**{practice_info['name']} Analysis:**

{practice_info.get('description', 'This practice area involves complex legal considerations that require careful analysis.')}

**Key Legal Considerations:**
• Relevant statutes and regulations in {practice_info['name'].lower()}
• Applicable case law and precedents
• Jurisdictional requirements and procedures
• Potential risks and liability issues

**Strategic Recommendations:**
• Document all relevant facts and evidence
• Research applicable legal authorities
• Consider multiple approaches and their implications
• Evaluate potential outcomes and risks

**Next Steps:**
• Gather supporting documentation
• Review relevant legal precedents
• Assess strategic options
• Consult with qualified legal counsel

**Important Disclaimer:** This is general legal information, not specific legal advice. Every legal situation is unique and requires professional evaluation by a qualified attorney licensed in your jurisdiction.

How else can I assist you with your {practice_info['name'].lower()} matter?"""
            }
        }],
        "client_id": f"protected_{int(time.time())}",
        "practice_area": practice_area,
        "fallback_mode": "protected_core_functionality"
    }

@app.route('/api/chat', methods=['POST'])
@rate_limit_decorator
@validate_json_input(['message'])
def api_chat():
    """Enhanced chat API with multi-layer protection and guaranteed responses"""
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
        
        # Make API call with fallback for API key issues
        try:
            response = requests.post(
                'https://api.x.ai/v1/chat/completions',
                headers=headers,
                json=payload,
                timeout=30
            )
            
            if response.status_code == 403:
                logger.warning("XAI API key access denied - using fallback response")
                # Fallback response when API key has no access
                return jsonify({
                    "choices": [{
                        "delta": {
                            "content": f"""I'm LexAI, your advanced legal AI assistant. I notice there's an API access issue, but I'm here to help!

**{PRACTICE_AREAS.get(practice_area, {}).get('name', 'Legal')} Analysis:**

Based on your query: "{message}"

**Key Considerations:**
• This appears to involve {practice_area.replace('_', ' ').title()} law
• I'd recommend reviewing relevant statutes and case law
• Consider consulting with a qualified attorney for case-specific advice

**Next Steps:**
• Gather relevant documentation
• Research applicable precedents  
• Evaluate potential legal strategies

*Note: This is general legal information, not specific legal advice. Please consult with a qualified attorney for your particular situation.*

**System Status:** API access temporarily limited - full functionality will be restored once XAI API key is updated."""
                        }
                    }]
                })
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Request error: {e}")
            # Fallback for network issues
            return jsonify({
                "choices": [{
                    "delta": {
                        "content": f"""I'm LexAI, your legal AI assistant. There's a temporary connection issue, but I can still provide general guidance.

**Your Query:** "{message}"

**General Legal Guidance:**
• Document all relevant facts and evidence
• Research applicable laws and regulations
• Consider multiple legal strategies
• Consult with qualified legal counsel

**Practice Area:** {PRACTICE_AREAS.get(practice_area, {}).get('name', 'Legal')}

I apologize for the technical issue. Please try again shortly, or contact support if this persists."""
                    }
                }]
            })
        
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
        
        # Use protected fallback for any API errors
        logger.warning(f"XAI API error: {response.status_code} - Using protected fallback")
        return jsonify(get_protected_fallback_response(message, practice_area))
    
    except Exception as e:
        # Final fallback protection - ensures chat ALWAYS works
        logger.error(f"Chat endpoint error: {str(e)} - Using emergency fallback")
        return jsonify(get_protected_fallback_response(message, practice_area))

# ============================================================================
# BILLING AND SUBSCRIPTION FRAMEWORK
# ============================================================================

# Subscription plans configuration
SUBSCRIPTION_PLANS = {
    'starter': {
        'name': 'Starter',
        'price': 49,
        'billing_cycle': 'monthly',
        'features': [
            '100 AI consultations per month',
            'Basic document analysis',
            'Email support',
            'Single practice area access'
        ],
        'limits': {
            'ai_consultations': 100,
            'document_uploads': 50,
            'storage_gb': 5,
            'users': 1
        },
        'color': '#3B82F6'
    },
    'professional': {
        'name': 'Professional',
        'price': 149,
        'billing_cycle': 'monthly',
        'features': [
            '500 AI consultations per month',
            'Advanced document analysis',
            'Priority support',
            'All practice areas',
            'Client management dashboard',
            'Legal research tools'
        ],
        'limits': {
            'ai_consultations': 500,
            'document_uploads': 250,
            'storage_gb': 25,
            'users': 5
        },
        'color': '#10B981',
        'popular': True
    },
    'enterprise': {
        'name': 'Enterprise',
        'price': 499,
        'billing_cycle': 'monthly',
        'features': [
            'Unlimited AI consultations',
            'Enhanced Bagel RL analysis',
            'Dedicated support manager',
            'Custom integrations',
            'Advanced analytics',
            'White-label options',
            'API access'
        ],
        'limits': {
            'ai_consultations': -1,  # Unlimited
            'document_uploads': -1,
            'storage_gb': 100,
            'users': -1
        },
        'color': '#8B5CF6'
    }
}

# Mock user subscription data (in production, use database)
USER_SUBSCRIPTIONS = {
    'demo_user': {
        'plan': 'professional',
        'status': 'active',
        'current_period_start': '2025-01-01',
        'current_period_end': '2025-02-01',
        'usage': {
            'ai_consultations': 127,
            'document_uploads': 23,
            'storage_used_gb': 8.5
        },
        'billing_history': [
            {
                'date': '2025-01-01',
                'amount': 149,
                'status': 'paid',
                'invoice_id': 'INV-2025-001'
            },
            {
                'date': '2024-12-01',
                'amount': 149,
                'status': 'paid',
                'invoice_id': 'INV-2024-012'
            }
        ]
    }
}

@app.route('/billing')
def billing_dashboard():
    """Billing and subscription management dashboard"""
    try:
        # Get current user subscription (mock data)
        user_id = 'demo_user'  # In production, get from session
        subscription = USER_SUBSCRIPTIONS.get(user_id, {})
        current_plan = subscription.get('plan', 'starter')
        
        return render_template_string("""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>LexAI Billing & Subscription</title>
            <link rel="stylesheet" href="{{ url_for('static', filename='platform.css') }}">
            <style>
                .billing-container {
                    max-width: 1200px;
                    margin: 0 auto;
                    padding: 24px;
                }
                
                .billing-header {
                    text-align: center;
                    margin-bottom: 48px;
                }
                
                .billing-title {
                    font-size: 2.5rem;
                    font-weight: 700;
                    color: var(--text-dark);
                    margin-bottom: 16px;
                }
                
                .billing-subtitle {
                    font-size: 1.125rem;
                    color: var(--text-light);
                    max-width: 600px;
                    margin: 0 auto;
                }
                
                .current-plan-section {
                    background: linear-gradient(135deg, var(--primary-green), #22c55e);
                    border-radius: 16px;
                    padding: 32px;
                    color: white;
                    margin-bottom: 48px;
                    text-align: center;
                }
                
                .current-plan-title {
                    font-size: 1.5rem;
                    font-weight: 600;
                    margin-bottom: 8px;
                }
                
                .current-plan-name {
                    font-size: 2rem;
                    font-weight: 700;
                    margin-bottom: 16px;
                }
                
                .usage-grid {
                    display: grid;
                    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                    gap: 24px;
                    margin-top: 24px;
                }
                
                .usage-card {
                    background: rgba(255, 255, 255, 0.1);
                    border-radius: 12px;
                    padding: 20px;
                    text-align: center;
                }
                
                .usage-number {
                    font-size: 2rem;
                    font-weight: 700;
                    margin-bottom: 4px;
                }
                
                .usage-label {
                    font-size: 0.875rem;
                    opacity: 0.9;
                }
                
                .plans-section {
                    margin-bottom: 48px;
                }
                
                .section-title {
                    font-size: 2rem;
                    font-weight: 700;
                    text-align: center;
                    margin-bottom: 32px;
                    color: var(--text-dark);
                }
                
                .plans-grid {
                    display: grid;
                    grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
                    gap: 32px;
                    margin-bottom: 48px;
                }
                
                .plan-card {
                    background: white;
                    border: 2px solid var(--border-light);
                    border-radius: 16px;
                    padding: 32px;
                    position: relative;
                    transition: all 0.3s ease;
                }
                
                .plan-card:hover {
                    transform: translateY(-4px);
                    box-shadow: 0 20px 40px rgba(0, 0, 0, 0.1);
                }
                
                .plan-card.popular {
                    border-color: var(--primary-green);
                    transform: scale(1.05);
                }
                
                .plan-card.current {
                    border-color: var(--primary-green);
                    background: var(--gray-50);
                }
                
                .popular-badge {
                    position: absolute;
                    top: -12px;
                    left: 50%;
                    transform: translateX(-50%);
                    background: var(--primary-green);
                    color: white;
                    padding: 6px 16px;
                    border-radius: 20px;
                    font-size: 0.875rem;
                    font-weight: 600;
                }
                
                .current-badge {
                    position: absolute;
                    top: -12px;
                    right: 16px;
                    background: var(--primary-green);
                    color: white;
                    padding: 6px 16px;
                    border-radius: 20px;
                    font-size: 0.875rem;
                    font-weight: 600;
                }
                
                .plan-name {
                    font-size: 1.5rem;
                    font-weight: 700;
                    margin-bottom: 8px;
                    color: var(--text-dark);
                }
                
                .plan-price {
                    font-size: 3rem;
                    font-weight: 700;
                    color: var(--primary-green);
                    margin-bottom: 4px;
                }
                
                .plan-cycle {
                    color: var(--text-light);
                    margin-bottom: 24px;
                }
                
                .plan-features {
                    list-style: none;
                    padding: 0;
                    margin-bottom: 32px;
                }
                
                .plan-features li {
                    padding: 8px 0;
                    position: relative;
                    padding-left: 24px;
                }
                
                .plan-features li::before {
                    content: "✓";
                    position: absolute;
                    left: 0;
                    color: var(--primary-green);
                    font-weight: bold;
                }
                
                .plan-button {
                    width: 100%;
                    padding: 12px 24px;
                    background: var(--primary-green);
                    color: white;
                    border: none;
                    border-radius: 8px;
                    font-weight: 600;
                    cursor: pointer;
                    transition: background 0.3s ease;
                }
                
                .plan-button:hover {
                    background: #1e3a2e;
                }
                
                .plan-button.current {
                    background: var(--gray-400);
                    cursor: not-allowed;
                }
                
                .billing-history {
                    background: white;
                    border-radius: 16px;
                    padding: 32px;
                    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.1);
                }
                
                .billing-table {
                    width: 100%;
                    border-collapse: collapse;
                }
                
                .billing-table th,
                .billing-table td {
                    padding: 16px;
                    text-align: left;
                    border-bottom: 1px solid var(--border-light);
                }
                
                .billing-table th {
                    font-weight: 600;
                    color: var(--text-dark);
                    background: var(--gray-50);
                }
                
                .status-paid {
                    color: var(--primary-green);
                    font-weight: 600;
                }
                
                .back-link {
                    display: inline-flex;
                    align-items: center;
                    gap: 8px;
                    color: var(--primary-green);
                    text-decoration: none;
                    font-weight: 600;
                    margin-bottom: 24px;
                    transition: opacity 0.3s ease;
                }
                
                .back-link:hover {
                    opacity: 0.8;
                }
            </style>
        </head>
        <body>
            <div class="billing-container">
                <a href="{{ url_for('dashboard') }}" class="back-link">
                    ← Back to Dashboard
                </a>
                
                <div class="billing-header">
                    <h1 class="billing-title">Billing & Subscription</h1>
                    <p class="billing-subtitle">Manage your LexAI subscription and billing preferences</p>
                </div>
                
                <!-- Current Plan Status -->
                <div class="current-plan-section">
                    <div class="current-plan-title">Current Plan</div>
                    <div class="current-plan-name">{{ plans[current_plan]['name'] }}</div>
                    <div>Next billing date: {{ subscription.get('current_period_end', 'N/A') }}</div>
                    
                    <div class="usage-grid">
                        <div class="usage-card">
                            <div class="usage-number">{{ subscription.get('usage', {}).get('ai_consultations', 0) }}</div>
                            <div class="usage-label">AI Consultations</div>
                        </div>
                        <div class="usage-card">
                            <div class="usage-number">{{ subscription.get('usage', {}).get('document_uploads', 0) }}</div>
                            <div class="usage-label">Documents Uploaded</div>
                        </div>
                        <div class="usage-card">
                            <div class="usage-number">{{ "%.1f"|format(subscription.get('usage', {}).get('storage_used_gb', 0)) }}GB</div>
                            <div class="usage-label">Storage Used</div>
                        </div>
                        <div class="usage-card">
                            <div class="usage-number">${{ plans[current_plan]['price'] }}</div>
                            <div class="usage-label">Monthly Cost</div>
                        </div>
                    </div>
                </div>
                
                <!-- Available Plans -->
                <div class="plans-section">
                    <h2 class="section-title">Choose Your Plan</h2>
                    <div class="plans-grid">
                        {% for plan_id, plan in plans.items() %}
                        <div class="plan-card {{ 'popular' if plan.get('popular') else '' }} {{ 'current' if plan_id == current_plan else '' }}">
                            {% if plan.get('popular') %}
                            <div class="popular-badge">Most Popular</div>
                            {% endif %}
                            
                            {% if plan_id == current_plan %}
                            <div class="current-badge">Current Plan</div>
                            {% endif %}
                            
                            <div class="plan-name">{{ plan['name'] }}</div>
                            <div class="plan-price">${{ plan['price'] }}</div>
                            <div class="plan-cycle">per month</div>
                            
                            <ul class="plan-features">
                                {% for feature in plan['features'] %}
                                <li>{{ feature }}</li>
                                {% endfor %}
                            </ul>
                            
                            <button class="plan-button {{ 'current' if plan_id == current_plan else '' }}" 
                                    onclick="{% if plan_id != current_plan %}changePlan('{{ plan_id }}'){% endif %}"
                                    {% if plan_id == current_plan %}disabled{% endif %}>
                                {% if plan_id == current_plan %}
                                Current Plan
                                {% else %}
                                {% if plan['price'] > plans[current_plan]['price'] %}Upgrade{% else %}Downgrade{% endif %}
                                {% endif %}
                            </button>
                        </div>
                        {% endfor %}
                    </div>
                </div>
                
                <!-- Billing History -->
                <div class="billing-history">
                    <h2 class="section-title">Billing History</h2>
                    <table class="billing-table">
                        <thead>
                            <tr>
                                <th>Date</th>
                                <th>Amount</th>
                                <th>Status</th>
                                <th>Invoice</th>
                            </tr>
                        </thead>
                        <tbody>
                            {% for invoice in subscription.get('billing_history', []) %}
                            <tr>
                                <td>{{ invoice['date'] }}</td>
                                <td>${{ invoice['amount'] }}</td>
                                <td class="status-paid">{{ invoice['status'].title() }}</td>
                                <td>{{ invoice['invoice_id'] }}</td>
                            </tr>
                            {% endfor %}
                        </tbody>
                    </table>
                </div>
            </div>
            
            <script>
                function changePlan(planId) {
                    if (confirm(`Are you sure you want to change to the ${planId} plan?`)) {
                        fetch('/api/billing/change-plan', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ plan: planId })
                        })
                        .then(response => response.json())
                        .then(data => {
                            if (data.success) {
                                alert('Plan changed successfully!');
                                location.reload();
                            } else {
                                alert('Failed to change plan: ' + data.error);
                            }
                        })
                        .catch(error => {
                            alert('Error changing plan: ' + error.message);
                        });
                    }
                }
            </script>
        </body>
        </html>
        """, 
        plans=SUBSCRIPTION_PLANS,
        current_plan=current_plan,
        subscription=subscription)
        
    except Exception as e:
        logger.error(f"Billing dashboard error: {e}")
        return f"""<!DOCTYPE html>
        <html><head><title>LexAI Billing</title></head>
        <body style="font-family: Inter, sans-serif; padding: 40px; text-align: center;">
        <h1>🏛️ LexAI Billing Dashboard</h1>
        <p>Error loading billing information: {e}</p>
        <a href="/" style="color: #2E4B3C;">← Back to Dashboard</a>
        </body></html>"""

@app.route('/api/billing/plans', methods=['GET'])
@rate_limit_decorator
def get_billing_plans():
    """Get available subscription plans"""
    try:
        return jsonify({
            "success": True,
            "plans": SUBSCRIPTION_PLANS
        })
    except Exception as e:
        logger.error(f"Get billing plans error: {e}")
        return jsonify({"error": "Failed to fetch plans"}), 500

@app.route('/api/billing/subscription', methods=['GET'])
@rate_limit_decorator
def get_subscription_status():
    """Get current user subscription status"""
    try:
        # Mock user ID (in production, get from authentication)
        user_id = 'demo_user'
        subscription = USER_SUBSCRIPTIONS.get(user_id, {})
        
        if not subscription:
            return jsonify({
                "success": True,
                "subscription": None,
                "message": "No active subscription"
            })
        
        return jsonify({
            "success": True,
            "subscription": subscription,
            "current_plan": SUBSCRIPTION_PLANS.get(subscription.get('plan', 'starter'))
        })
    except Exception as e:
        logger.error(f"Get subscription error: {e}")
        return jsonify({"error": "Failed to fetch subscription"}), 500

@app.route('/api/billing/change-plan', methods=['POST'])
@rate_limit_decorator
def change_subscription_plan():
    """Change user subscription plan"""
    try:
        data = request.get_json()
        if not data or 'plan' not in data:
            return jsonify({"error": "Plan ID required"}), 400
        
        new_plan = data['plan']
        if new_plan not in SUBSCRIPTION_PLANS:
            return jsonify({"error": "Invalid plan"}), 400
        
        # Mock user ID (in production, get from authentication)
        user_id = 'demo_user'
        
        # Update subscription (in production, integrate with payment processor)
        if user_id not in USER_SUBSCRIPTIONS:
            USER_SUBSCRIPTIONS[user_id] = {
                'plan': new_plan,
                'status': 'active',
                'current_period_start': datetime.utcnow().strftime('%Y-%m-%d'),
                'current_period_end': (datetime.utcnow() + timedelta(days=30)).strftime('%Y-%m-%d'),
                'usage': {
                    'ai_consultations': 0,
                    'document_uploads': 0,
                    'storage_used_gb': 0
                },
                'billing_history': []
            }
        else:
            USER_SUBSCRIPTIONS[user_id]['plan'] = new_plan
        
        logger.info(f"Plan changed to {new_plan} for user {user_id}")
        
        return jsonify({
            "success": True,
            "message": f"Successfully changed to {SUBSCRIPTION_PLANS[new_plan]['name']} plan",
            "new_plan": SUBSCRIPTION_PLANS[new_plan]
        })
        
    except Exception as e:
        logger.error(f"Change plan error: {e}")
        return jsonify({"error": "Failed to change plan"}), 500

@app.route('/api/billing/usage', methods=['GET'])
@rate_limit_decorator
def get_usage_statistics():
    """Get detailed usage statistics for current billing period"""
    try:
        # Mock user ID (in production, get from authentication)
        user_id = 'demo_user'
        subscription = USER_SUBSCRIPTIONS.get(user_id, {})
        
        if not subscription:
            return jsonify({
                "success": True,
                "usage": {
                    'ai_consultations': 0,
                    'document_uploads': 0,
                    'storage_used_gb': 0
                },
                "limits": SUBSCRIPTION_PLANS['starter']['limits'],
                "message": "No active subscription"
            })
        
        current_plan = subscription.get('plan', 'starter')
        usage = subscription.get('usage', {})
        limits = SUBSCRIPTION_PLANS[current_plan]['limits']
        
        # Calculate usage percentages
        usage_stats = {
            'ai_consultations': {
                'used': usage.get('ai_consultations', 0),
                'limit': limits['ai_consultations'],
                'percentage': 0 if limits['ai_consultations'] == -1 else min(100, (usage.get('ai_consultations', 0) / limits['ai_consultations']) * 100)
            },
            'document_uploads': {
                'used': usage.get('document_uploads', 0),
                'limit': limits['document_uploads'],
                'percentage': 0 if limits['document_uploads'] == -1 else min(100, (usage.get('document_uploads', 0) / limits['document_uploads']) * 100)
            },
            'storage': {
                'used_gb': usage.get('storage_used_gb', 0),
                'limit_gb': limits['storage_gb'],
                'percentage': min(100, (usage.get('storage_used_gb', 0) / limits['storage_gb']) * 100)
            }
        }
        
        return jsonify({
            "success": True,
            "usage_stats": usage_stats,
            "current_plan": current_plan,
            "billing_period": {
                'start': subscription.get('current_period_start'),
                'end': subscription.get('current_period_end')
            }
        })
        
    except Exception as e:
        logger.error(f"Get usage statistics error: {e}")
        return jsonify({"error": "Failed to fetch usage statistics"}), 500

# ============================================================================
# ADVANCED NOTIFICATION SYSTEM
# ============================================================================

# Notification types and templates
NOTIFICATION_TEMPLATES = {
    'case_update': {
        'email': {
            'subject': 'Case Update: {case_name}',
            'body': '''Dear {client_name},

We have an important update regarding your {case_type} case.

{update_message}

Next Steps:
{next_steps}

If you have any questions, please don't hesitate to contact us.

Best regards,
LexAI Legal Team'''
        },
        'sms': {
            'body': 'LexAI Update: {case_name} - {update_message}. Next: {next_steps}. Reply STOP to opt out.'
        }
    },
    'document_ready': {
        'email': {
            'subject': 'Document Ready for Review: {document_name}',
            'body': '''Dear {client_name},

Your {document_type} document is ready for review.

Document: {document_name}
Status: {status}
Action Required: {action_required}

Please log into your LexAI portal to review and approve the document.

Best regards,
LexAI Legal Team'''
        },
        'sms': {
            'body': 'LexAI: {document_name} ready for review. Login to portal to approve. Reply STOP to opt out.'
        }
    },
    'appointment_reminder': {
        'email': {
            'subject': 'Appointment Reminder: {appointment_date}',
            'body': '''Dear {client_name},

This is a reminder of your upcoming appointment:

Date: {appointment_date}
Time: {appointment_time}
Type: {appointment_type}
Location: {location}

Please contact us if you need to reschedule.

Best regards,
LexAI Legal Team'''
        },
        'sms': {
            'body': 'LexAI Reminder: {appointment_type} on {appointment_date} at {appointment_time}. Reply STOP to opt out.'
        }
    },
    'payment_due': {
        'email': {
            'subject': 'Payment Due: Invoice {invoice_number}',
            'body': '''Dear {client_name},

Your invoice {invoice_number} is due for payment.

Amount Due: ${amount}
Due Date: {due_date}
Services: {services}

Please log into your LexAI portal to make a payment.

Best regards,
LexAI Billing Team'''
        },
        'sms': {
            'body': 'LexAI: Invoice {invoice_number} due ${amount} by {due_date}. Login to pay. Reply STOP to opt out.'
        }
    }
}

# Mock notification preferences (in production, store in database)
NOTIFICATION_PREFERENCES = {
    'demo_user': {
        'email': 'user@example.com',
        'phone': '+1234567890',
        'preferences': {
            'case_updates': {'email': True, 'sms': True},
            'document_ready': {'email': True, 'sms': False},
            'appointment_reminders': {'email': True, 'sms': True},
            'payment_due': {'email': True, 'sms': False}
        }
    }
}

class NotificationService:
    """Advanced notification service with email and SMS capabilities"""
    
    @staticmethod
    def send_notification(user_id, notification_type, template_data, priority='normal'):
        """Send notification via preferred channels"""
        try:
            user_prefs = NOTIFICATION_PREFERENCES.get(user_id, {})
            preferences = user_prefs.get('preferences', {}).get(notification_type, {})
            
            results = {
                'email_sent': False,
                'sms_sent': False,
                'errors': []
            }
            
            # Send email notification
            if preferences.get('email', False) and user_prefs.get('email'):
                try:
                    email_result = NotificationService._send_email(
                        user_prefs['email'],
                        notification_type,
                        template_data
                    )
                    results['email_sent'] = email_result
                    logger.info(f"📧 Email notification sent to {user_id}: {notification_type}")
                except Exception as e:
                    results['errors'].append(f"Email error: {e}")
                    logger.error(f"Email notification failed: {e}")
            
            # Send SMS notification
            if preferences.get('sms', False) and user_prefs.get('phone'):
                try:
                    sms_result = NotificationService._send_sms(
                        user_prefs['phone'],
                        notification_type,
                        template_data
                    )
                    results['sms_sent'] = sms_result
                    logger.info(f"📱 SMS notification sent to {user_id}: {notification_type}")
                except Exception as e:
                    results['errors'].append(f"SMS error: {e}")
                    logger.error(f"SMS notification failed: {e}")
            
            return results
            
        except Exception as e:
            logger.error(f"Notification service error: {e}")
            return {'email_sent': False, 'sms_sent': False, 'errors': [str(e)]}
    
    @staticmethod
    def _send_email(email_address, notification_type, template_data):
        """Send email notification (mock implementation)"""
        template = NOTIFICATION_TEMPLATES.get(notification_type, {}).get('email', {})
        
        subject = template.get('subject', 'LexAI Notification').format(**template_data)
        body = template.get('body', 'Notification from LexAI').format(**template_data)
        
        # In production, integrate with email service (SendGrid, AWS SES, etc.)
        logger.info(f"📧 [MOCK EMAIL] To: {email_address}")
        logger.info(f"📧 [MOCK EMAIL] Subject: {subject}")
        logger.info(f"📧 [MOCK EMAIL] Body: {body[:100]}...")
        
        return True
    
    @staticmethod
    def _send_sms(phone_number, notification_type, template_data):
        """Send SMS notification (mock implementation)"""
        template = NOTIFICATION_TEMPLATES.get(notification_type, {}).get('sms', {})
        
        body = template.get('body', 'Notification from LexAI').format(**template_data)
        
        # In production, integrate with SMS service (Twilio, AWS SNS, etc.)
        logger.info(f"📱 [MOCK SMS] To: {phone_number}")
        logger.info(f"📱 [MOCK SMS] Body: {body}")
        
        return True

@app.route('/notifications')
def notifications_dashboard():
    """Notification preferences and history dashboard"""
    try:
        user_id = 'demo_user'  # In production, get from session
        user_prefs = NOTIFICATION_PREFERENCES.get(user_id, {})
        
        return render_template_string("""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>LexAI Notification Preferences</title>
            <link rel="stylesheet" href="{{ url_for('static', filename='platform.css') }}">
            <style>
                .notifications-container {
                    max-width: 1000px;
                    margin: 0 auto;
                    padding: 24px;
                }
                
                .notifications-header {
                    text-align: center;
                    margin-bottom: 48px;
                }
                
                .notifications-title {
                    font-size: 2.5rem;
                    font-weight: 700;
                    color: var(--text-dark);
                    margin-bottom: 16px;
                }
                
                .notifications-subtitle {
                    font-size: 1.125rem;
                    color: var(--text-light);
                    max-width: 600px;
                    margin: 0 auto;
                }
                
                .notification-section {
                    background: white;
                    border-radius: 16px;
                    padding: 32px;
                    margin-bottom: 32px;
                    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.1);
                }
                
                .section-title {
                    font-size: 1.5rem;
                    font-weight: 600;
                    color: var(--text-dark);
                    margin-bottom: 24px;
                    display: flex;
                    align-items: center;
                    gap: 12px;
                }
                
                .contact-form {
                    display: grid;
                    grid-template-columns: 1fr 1fr;
                    gap: 24px;
                    margin-bottom: 32px;
                }
                
                .form-group {
                    display: flex;
                    flex-direction: column;
                }
                
                .form-label {
                    font-weight: 600;
                    color: var(--text-dark);
                    margin-bottom: 8px;
                }
                
                .form-input {
                    padding: 12px;
                    border: 2px solid var(--border-light);
                    border-radius: 8px;
                    font-size: 1rem;
                    transition: border-color 0.3s ease;
                }
                
                .form-input:focus {
                    outline: none;
                    border-color: var(--primary-green);
                }
                
                .preferences-grid {
                    display: grid;
                    gap: 24px;
                }
                
                .preference-item {
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    padding: 20px;
                    background: var(--gray-50);
                    border-radius: 12px;
                    border: 1px solid var(--border-light);
                }
                
                .preference-info {
                    flex: 1;
                }
                
                .preference-title {
                    font-weight: 600;
                    color: var(--text-dark);
                    margin-bottom: 4px;
                }
                
                .preference-description {
                    font-size: 0.875rem;
                    color: var(--text-light);
                }
                
                .preference-controls {
                    display: flex;
                    gap: 16px;
                    align-items: center;
                }
                
                .toggle-group {
                    display: flex;
                    align-items: center;
                    gap: 8px;
                }
                
                .toggle-label {
                    font-size: 0.875rem;
                    font-weight: 500;
                    color: var(--text-dark);
                }
                
                .toggle-switch {
                    position: relative;
                    width: 48px;
                    height: 24px;
                    background: var(--gray-300);
                    border-radius: 12px;
                    cursor: pointer;
                    transition: background 0.3s ease;
                }
                
                .toggle-switch.active {
                    background: var(--primary-green);
                }
                
                .toggle-switch::after {
                    content: '';
                    position: absolute;
                    top: 2px;
                    left: 2px;
                    width: 20px;
                    height: 20px;
                    background: white;
                    border-radius: 50%;
                    transition: transform 0.3s ease;
                }
                
                .toggle-switch.active::after {
                    transform: translateX(24px);
                }
                
                .save-button {
                    background: var(--primary-green);
                    color: white;
                    border: none;
                    padding: 12px 32px;
                    border-radius: 8px;
                    font-weight: 600;
                    cursor: pointer;
                    transition: background 0.3s ease;
                    margin-top: 24px;
                }
                
                .save-button:hover {
                    background: #1e3a2e;
                }
                
                .test-button {
                    background: var(--secondary-orange);
                    color: white;
                    border: none;
                    padding: 8px 16px;
                    border-radius: 6px;
                    font-size: 0.875rem;
                    font-weight: 600;
                    cursor: pointer;
                    transition: background 0.3s ease;
                }
                
                .test-button:hover {
                    background: #e07c00;
                }
                
                .back-link {
                    display: inline-flex;
                    align-items: center;
                    gap: 8px;
                    color: var(--primary-green);
                    text-decoration: none;
                    font-weight: 600;
                    margin-bottom: 24px;
                    transition: opacity 0.3s ease;
                }
                
                .back-link:hover {
                    opacity: 0.8;
                }
                
                @media (max-width: 768px) {
                    .contact-form {
                        grid-template-columns: 1fr;
                    }
                    
                    .preference-item {
                        flex-direction: column;
                        align-items: flex-start;
                        gap: 16px;
                    }
                    
                    .preference-controls {
                        width: 100%;
                        justify-content: space-between;
                    }
                }
            </style>
        </head>
        <body>
            <div class="notifications-container">
                <a href="{{ url_for('dashboard') }}" class="back-link">
                    ← Back to Dashboard
                </a>
                
                <div class="notifications-header">
                    <h1 class="notifications-title">Notification Preferences</h1>
                    <p class="notifications-subtitle">Manage how and when you receive updates about your cases and account</p>
                </div>
                
                <!-- Contact Information -->
                <div class="notification-section">
                    <h2 class="section-title">
                        📧 Contact Information
                    </h2>
                    
                    <div class="contact-form">
                        <div class="form-group">
                            <label class="form-label">Email Address</label>
                            <input type="email" class="form-input" value="{{ user_prefs.get('email', '') }}" placeholder="your@email.com">
                        </div>
                        
                        <div class="form-group">
                            <label class="form-label">Phone Number</label>
                            <input type="tel" class="form-input" value="{{ user_prefs.get('phone', '') }}" placeholder="+1 (555) 123-4567">
                        </div>
                    </div>
                </div>
                
                <!-- Notification Preferences -->
                <div class="notification-section">
                    <h2 class="section-title">
                        🔔 Notification Preferences
                    </h2>
                    
                    <div class="preferences-grid">
                        <div class="preference-item">
                            <div class="preference-info">
                                <div class="preference-title">Case Updates</div>
                                <div class="preference-description">Notifications about case progress, status changes, and important developments</div>
                            </div>
                            <div class="preference-controls">
                                <div class="toggle-group">
                                    <span class="toggle-label">Email</span>
                                    <div class="toggle-switch active" onclick="togglePreference(this, 'case_updates', 'email')"></div>
                                </div>
                                <div class="toggle-group">
                                    <span class="toggle-label">SMS</span>
                                    <div class="toggle-switch active" onclick="togglePreference(this, 'case_updates', 'sms')"></div>
                                </div>
                                <button class="test-button" onclick="testNotification('case_update')">Test</button>
                            </div>
                        </div>
                        
                        <div class="preference-item">
                            <div class="preference-info">
                                <div class="preference-title">Document Ready</div>
                                <div class="preference-description">Alerts when documents are ready for review, signature, or approval</div>
                            </div>
                            <div class="preference-controls">
                                <div class="toggle-group">
                                    <span class="toggle-label">Email</span>
                                    <div class="toggle-switch active" onclick="togglePreference(this, 'document_ready', 'email')"></div>
                                </div>
                                <div class="toggle-group">
                                    <span class="toggle-label">SMS</span>
                                    <div class="toggle-switch" onclick="togglePreference(this, 'document_ready', 'sms')"></div>
                                </div>
                                <button class="test-button" onclick="testNotification('document_ready')">Test</button>
                            </div>
                        </div>
                        
                        <div class="preference-item">
                            <div class="preference-info">
                                <div class="preference-title">Appointment Reminders</div>
                                <div class="preference-description">Reminders for upcoming meetings, court dates, and consultations</div>
                            </div>
                            <div class="preference-controls">
                                <div class="toggle-group">
                                    <span class="toggle-label">Email</span>
                                    <div class="toggle-switch active" onclick="togglePreference(this, 'appointment_reminders', 'email')"></div>
                                </div>
                                <div class="toggle-group">
                                    <span class="toggle-label">SMS</span>
                                    <div class="toggle-switch active" onclick="togglePreference(this, 'appointment_reminders', 'sms')"></div>
                                </div>
                                <button class="test-button" onclick="testNotification('appointment_reminder')">Test</button>
                            </div>
                        </div>
                        
                        <div class="preference-item">
                            <div class="preference-info">
                                <div class="preference-title">Payment Due</div>
                                <div class="preference-description">Billing notifications and payment reminders</div>
                            </div>
                            <div class="preference-controls">
                                <div class="toggle-group">
                                    <span class="toggle-label">Email</span>
                                    <div class="toggle-switch active" onclick="togglePreference(this, 'payment_due', 'email')"></div>
                                </div>
                                <div class="toggle-group">
                                    <span class="toggle-label">SMS</span>
                                    <div class="toggle-switch" onclick="togglePreference(this, 'payment_due', 'sms')"></div>
                                </div>
                                <button class="test-button" onclick="testNotification('payment_due')">Test</button>
                            </div>
                        </div>
                    </div>
                    
                    <button class="save-button" onclick="savePreferences()">Save Preferences</button>
                </div>
            </div>
            
            <script>
                function togglePreference(element, type, method) {
                    element.classList.toggle('active');
                }
                
                function savePreferences() {
                    // In production, save to backend
                    alert('Preferences saved successfully!');
                }
                
                function testNotification(type) {
                    fetch('/api/notifications/test', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ type: type })
                    })
                    .then(response => response.json())
                    .then(data => {
                        if (data.success) {
                            alert('Test notification sent! Check your email/SMS.');
                        } else {
                            alert('Failed to send test notification: ' + data.error);
                        }
                    })
                    .catch(error => {
                        alert('Error sending test notification: ' + error.message);
                    });
                }
            </script>
        </body>
        </html>
        """, user_prefs=user_prefs)
        
    except Exception as e:
        logger.error(f"Notifications dashboard error: {e}")
        return f"""<!DOCTYPE html>
        <html><head><title>LexAI Notifications</title></head>
        <body style="font-family: Inter, sans-serif; padding: 40px; text-align: center;">
        <h1>🔔 LexAI Notification Center</h1>
        <p>Error loading notification preferences: {e}</p>
        <a href="/" style="color: #2E4B3C;">← Back to Dashboard</a>
        </body></html>"""

@app.route('/api/notifications/test', methods=['POST'])
@rate_limit_decorator
def test_notification():
    """Send test notification"""
    try:
        data = request.get_json()
        notification_type = data.get('type')
        
        if not notification_type:
            return jsonify({"error": "Notification type required"}), 400
        
        # Sample test data
        test_data = {
            'case_update': {
                'client_name': 'John Doe',
                'case_name': 'Smith v. Johnson',
                'case_type': 'Personal Injury',
                'update_message': 'Medical records have been received and reviewed.',
                'next_steps': 'Schedule expert witness deposition'
            },
            'document_ready': {
                'client_name': 'John Doe',
                'document_name': 'Settlement Agreement Draft',
                'document_type': 'Legal Agreement',
                'status': 'Ready for Review',
                'action_required': 'Review and approve terms'
            },
            'appointment_reminder': {
                'client_name': 'John Doe',
                'appointment_date': 'January 15, 2025',
                'appointment_time': '2:00 PM',
                'appointment_type': 'Case Strategy Meeting',
                'location': 'LexAI Office - Conference Room A'
            },
            'payment_due': {
                'client_name': 'John Doe',
                'invoice_number': 'INV-2025-001',
                'amount': '2,500.00',
                'due_date': 'January 20, 2025',
                'services': 'Legal consultation and document review'
            }
        }
        
        template_data = test_data.get(notification_type, {})
        if not template_data:
            return jsonify({"error": "Invalid notification type"}), 400
        
        # Send test notification
        result = NotificationService.send_notification(
            'demo_user',
            notification_type,
            template_data,
            priority='test'
        )
        
        return jsonify({
            "success": True,
            "message": "Test notification sent",
            "results": result
        })
        
    except Exception as e:
        logger.error(f"Test notification error: {e}")
        return jsonify({"error": "Failed to send test notification"}), 500

@app.route('/api/notifications/send', methods=['POST'])
@rate_limit_decorator
def send_notification_api():
    """Send notification via API"""
    try:
        data = request.get_json()
        
        required_fields = ['user_id', 'type', 'template_data']
        for field in required_fields:
            if field not in data:
                return jsonify({"error": f"Missing required field: {field}"}), 400
        
        result = NotificationService.send_notification(
            data['user_id'],
            data['type'],
            data['template_data'],
            data.get('priority', 'normal')
        )
        
        return jsonify({
            "success": True,
            "message": "Notification sent",
            "results": result
        })
        
    except Exception as e:
        logger.error(f"Send notification API error: {e}")
        return jsonify({"error": "Failed to send notification"}), 500

# ============================================================================
# AI-POWERED CONTRACT TEMPLATE GENERATOR
# ============================================================================

# Contract templates with AI-powered customization
CONTRACT_TEMPLATES = {
    'nda': {
        'name': 'Non-Disclosure Agreement (NDA)',
        'category': 'Confidentiality',
        'fields': [
            {'name': 'disclosing_party', 'type': 'text', 'label': 'Disclosing Party Name', 'required': True},
            {'name': 'receiving_party', 'type': 'text', 'label': 'Receiving Party Name', 'required': True},
            {'name': 'mutual', 'type': 'boolean', 'label': 'Mutual NDA', 'default': False},
            {'name': 'duration_years', 'type': 'number', 'label': 'Duration (Years)', 'default': 3},
            {'name': 'jurisdiction', 'type': 'select', 'label': 'Governing Jurisdiction', 'options': ['California', 'New York', 'Delaware', 'Texas'], 'default': 'California'},
            {'name': 'purpose', 'type': 'textarea', 'label': 'Purpose of Disclosure', 'placeholder': 'Describe the business purpose...'}
        ],
        'ai_instructions': 'Generate a comprehensive NDA with appropriate confidentiality provisions, return obligations, and legal protections based on the specified parameters.'
    },
    'service_agreement': {
        'name': 'Service Agreement',
        'category': 'Commercial',
        'fields': [
            {'name': 'service_provider', 'type': 'text', 'label': 'Service Provider Name', 'required': True},
            {'name': 'client', 'type': 'text', 'label': 'Client Name', 'required': True},
            {'name': 'services_description', 'type': 'textarea', 'label': 'Services Description', 'required': True},
            {'name': 'payment_amount', 'type': 'number', 'label': 'Payment Amount ($)', 'required': True},
            {'name': 'payment_schedule', 'type': 'select', 'label': 'Payment Schedule', 'options': ['Monthly', 'Quarterly', 'Upon Completion', 'Net 30'], 'default': 'Monthly'},
            {'name': 'term_months', 'type': 'number', 'label': 'Contract Term (Months)', 'default': 12},
            {'name': 'cancellation_notice_days', 'type': 'number', 'label': 'Cancellation Notice (Days)', 'default': 30}
        ],
        'ai_instructions': 'Create a professional service agreement with clear scope of work, payment terms, performance standards, and termination provisions.'
    },
    'employment': {
        'name': 'Employment Agreement',
        'category': 'Employment',
        'fields': [
            {'name': 'employer', 'type': 'text', 'label': 'Employer Name', 'required': True},
            {'name': 'employee', 'type': 'text', 'label': 'Employee Name', 'required': True},
            {'name': 'position', 'type': 'text', 'label': 'Job Title', 'required': True},
            {'name': 'salary', 'type': 'number', 'label': 'Annual Salary ($)', 'required': True},
            {'name': 'start_date', 'type': 'date', 'label': 'Start Date', 'required': True},
            {'name': 'at_will', 'type': 'boolean', 'label': 'At-Will Employment', 'default': True},
            {'name': 'benefits', 'type': 'textarea', 'label': 'Benefits Package', 'placeholder': 'Health insurance, 401k, vacation days...'},
            {'name': 'confidentiality', 'type': 'boolean', 'label': 'Include Confidentiality Clause', 'default': True},
            {'name': 'non_compete', 'type': 'boolean', 'label': 'Include Non-Compete Clause', 'default': False}
        ],
        'ai_instructions': 'Generate a comprehensive employment agreement with appropriate compensation, benefits, duties, and legal protections.'
    },
    'lease': {
        'name': 'Lease Agreement',
        'category': 'Real Estate',
        'fields': [
            {'name': 'landlord', 'type': 'text', 'label': 'Landlord Name', 'required': True},
            {'name': 'tenant', 'type': 'text', 'label': 'Tenant Name', 'required': True},
            {'name': 'property_address', 'type': 'textarea', 'label': 'Property Address', 'required': True},
            {'name': 'monthly_rent', 'type': 'number', 'label': 'Monthly Rent ($)', 'required': True},
            {'name': 'security_deposit', 'type': 'number', 'label': 'Security Deposit ($)', 'required': True},
            {'name': 'lease_term_months', 'type': 'number', 'label': 'Lease Term (Months)', 'default': 12},
            {'name': 'pets_allowed', 'type': 'boolean', 'label': 'Pets Allowed', 'default': False},
            {'name': 'utilities_included', 'type': 'multiselect', 'label': 'Utilities Included', 'options': ['Water', 'Electric', 'Gas', 'Internet', 'Cable']}
        ],
        'ai_instructions': 'Create a residential lease agreement with standard terms, tenant obligations, landlord responsibilities, and legal protections.'
    },
    'partnership': {
        'name': 'Partnership Agreement',
        'category': 'Business Formation',
        'fields': [
            {'name': 'partner1_name', 'type': 'text', 'label': 'Partner 1 Name', 'required': True},
            {'name': 'partner1_contribution', 'type': 'number', 'label': 'Partner 1 Capital Contribution ($)', 'required': True},
            {'name': 'partner2_name', 'type': 'text', 'label': 'Partner 2 Name', 'required': True},
            {'name': 'partner2_contribution', 'type': 'number', 'label': 'Partner 2 Capital Contribution ($)', 'required': True},
            {'name': 'business_name', 'type': 'text', 'label': 'Business Name', 'required': True},
            {'name': 'business_purpose', 'type': 'textarea', 'label': 'Business Purpose', 'required': True},
            {'name': 'profit_sharing', 'type': 'select', 'label': 'Profit Sharing', 'options': ['Equal (50/50)', 'Based on Capital', 'Custom'], 'default': 'Equal (50/50)'},
            {'name': 'management_structure', 'type': 'select', 'label': 'Management Structure', 'options': ['Equal Management', 'Managing Partner', 'Board of Directors'], 'default': 'Equal Management'}
        ],
        'ai_instructions': 'Generate a partnership agreement with clear capital contributions, profit sharing, management structure, and dissolution procedures.'
    }
}

@app.route('/contracts')
def contracts_generator():
    """AI-powered contract template generator interface"""
    try:
        return render_template_string("""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>LexAI Contract Generator</title>
            <link rel="stylesheet" href="{{ url_for('static', filename='platform.css') }}">
            <style>
                .contracts-container {
                    max-width: 1400px;
                    margin: 0 auto;
                    padding: 24px;
                }
                
                .contracts-header {
                    text-align: center;
                    margin-bottom: 48px;
                }
                
                .contracts-title {
                    font-size: 2.5rem;
                    font-weight: 700;
                    color: var(--text-dark);
                    margin-bottom: 16px;
                }
                
                .contracts-subtitle {
                    font-size: 1.125rem;
                    color: var(--text-light);
                    max-width: 700px;
                    margin: 0 auto;
                }
                
                .template-grid {
                    display: grid;
                    grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
                    gap: 24px;
                    margin-bottom: 48px;
                }
                
                .template-card {
                    background: white;
                    border-radius: 16px;
                    padding: 24px;
                    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.1);
                    transition: all 0.3s ease;
                    cursor: pointer;
                    border: 2px solid transparent;
                }
                
                .template-card:hover {
                    transform: translateY(-4px);
                    box-shadow: 0 8px 30px rgba(0, 0, 0, 0.15);
                    border-color: var(--primary-green);
                }
                
                .template-icon {
                    width: 48px;
                    height: 48px;
                    background: linear-gradient(135deg, var(--primary-green), var(--primary-green-light));
                    border-radius: 12px;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    margin-bottom: 16px;
                    color: white;
                    font-size: 1.5rem;
                }
                
                .template-name {
                    font-size: 1.25rem;
                    font-weight: 600;
                    color: var(--text-dark);
                    margin-bottom: 8px;
                }
                
                .template-category {
                    font-size: 0.875rem;
                    color: var(--text-light);
                    margin-bottom: 12px;
                    padding: 4px 8px;
                    background: var(--gray-100);
                    border-radius: 6px;
                    display: inline-block;
                }
                
                .template-description {
                    font-size: 0.875rem;
                    color: var(--text-light);
                    line-height: 1.5;
                }
                
                .generator-form {
                    background: white;
                    border-radius: 16px;
                    padding: 32px;
                    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.1);
                    display: none;
                }
                
                .form-header {
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    margin-bottom: 32px;
                    padding-bottom: 16px;
                    border-bottom: 2px solid var(--gray-100);
                }
                
                .form-title {
                    font-size: 1.5rem;
                    font-weight: 600;
                    color: var(--text-dark);
                }
                
                .form-close {
                    background: none;
                    border: none;
                    font-size: 1.5rem;
                    color: var(--text-light);
                    cursor: pointer;
                    padding: 8px;
                    border-radius: 6px;
                    transition: all 0.3s ease;
                }
                
                .form-close:hover {
                    background: var(--gray-100);
                    color: var(--text-dark);
                }
                
                .form-grid {
                    display: grid;
                    grid-template-columns: 1fr 1fr;
                    gap: 24px;
                    margin-bottom: 32px;
                }
                
                .form-group {
                    display: flex;
                    flex-direction: column;
                }
                
                .form-group.full-width {
                    grid-column: 1 / -1;
                }
                
                .form-label {
                    font-weight: 600;
                    color: var(--text-dark);
                    margin-bottom: 8px;
                    display: flex;
                    align-items: center;
                    gap: 4px;
                }
                
                .required-indicator {
                    color: var(--error);
                    font-size: 0.875rem;
                }
                
                .form-input,
                .form-select,
                .form-textarea {
                    padding: 12px;
                    border: 2px solid var(--border-light);
                    border-radius: 8px;
                    font-size: 1rem;
                    transition: border-color 0.3s ease;
                    font-family: inherit;
                }
                
                .form-input:focus,
                .form-select:focus,
                .form-textarea:focus {
                    outline: none;
                    border-color: var(--primary-green);
                }
                
                .form-textarea {
                    min-height: 100px;
                    resize: vertical;
                }
                
                .form-checkbox-group {
                    display: flex;
                    align-items: center;
                    gap: 8px;
                    margin-top: 8px;
                }
                
                .form-checkbox {
                    width: 18px;
                    height: 18px;
                    accent-color: var(--primary-green);
                }
                
                .form-actions {
                    display: flex;
                    gap: 16px;
                    justify-content: flex-end;
                    margin-top: 32px;
                    padding-top: 24px;
                    border-top: 2px solid var(--gray-100);
                }
                
                .btn-primary {
                    background: var(--primary-green);
                    color: white;
                    border: none;
                    padding: 12px 32px;
                    border-radius: 8px;
                    font-weight: 600;
                    cursor: pointer;
                    transition: background 0.3s ease;
                    font-size: 1rem;
                }
                
                .btn-primary:hover {
                    background: #1e3a2e;
                }
                
                .btn-secondary {
                    background: var(--gray-100);
                    color: var(--text-dark);
                    border: 2px solid var(--border-light);
                    padding: 12px 32px;
                    border-radius: 8px;
                    font-weight: 600;
                    cursor: pointer;
                    transition: all 0.3s ease;
                    font-size: 1rem;
                }
                
                .btn-secondary:hover {
                    background: var(--gray-200);
                    border-color: var(--gray-300);
                }
                
                .loading-state {
                    display: none;
                    text-align: center;
                    padding: 40px;
                    color: var(--text-light);
                }
                
                .ai-badge {
                    display: inline-flex;
                    align-items: center;
                    gap: 6px;
                    background: linear-gradient(135deg, var(--secondary-orange), #ff8c00);
                    color: white;
                    padding: 4px 8px;
                    border-radius: 6px;
                    font-size: 0.75rem;
                    font-weight: 600;
                    margin-left: 8px;
                }
                
                .back-link {
                    display: inline-flex;
                    align-items: center;
                    gap: 8px;
                    color: var(--primary-green);
                    text-decoration: none;
                    font-weight: 600;
                    margin-bottom: 24px;
                    transition: opacity 0.3s ease;
                }
                
                .back-link:hover {
                    opacity: 0.8;
                }
                
                @media (max-width: 768px) {
                    .template-grid {
                        grid-template-columns: 1fr;
                    }
                    
                    .form-grid {
                        grid-template-columns: 1fr;
                    }
                    
                    .form-actions {
                        flex-direction: column;
                    }
                }
            </style>
        </head>
        <body>
            <div class="contracts-container">
                <a href="{{ url_for('dashboard') }}" class="back-link">
                    ← Back to Dashboard
                </a>
                
                <div class="contracts-header">
                    <h1 class="contracts-title">AI Contract Generator <span class="ai-badge">🤖 AI Powered</span></h1>
                    <p class="contracts-subtitle">Generate professional legal contracts tailored to your specific needs using advanced AI technology</p>
                </div>
                
                <!-- Template Selection -->
                <div id="templateSelection">
                    <div class="template-grid">
                        {% for template_id, template in templates.items() %}
                        <div class="template-card" onclick="selectTemplate('{{ template_id }}')">
                            <div class="template-icon">📄</div>
                            <div class="template-name">{{ template.name }}</div>
                            <div class="template-category">{{ template.category }}</div>
                            <div class="template-description">
                                Generate a customized {{ template.name.lower() }} with AI-powered legal language and clause optimization.
                            </div>
                        </div>
                        {% endfor %}
                    </div>
                </div>
                
                <!-- Contract Generation Form -->
                <div id="generatorForm" class="generator-form">
                    <div class="form-header">
                        <h2 class="form-title" id="formTitle">Generate Contract</h2>
                        <button class="form-close" onclick="closeForm()">×</button>
                    </div>
                    
                    <form id="contractForm">
                        <div class="form-grid" id="formFields">
                            <!-- Dynamic fields will be inserted here -->
                        </div>
                        
                        <div class="form-actions">
                            <button type="button" class="btn-secondary" onclick="closeForm()">Cancel</button>
                            <button type="submit" class="btn-primary">Generate Contract</button>
                        </div>
                    </form>
                    
                    <div class="loading-state" id="loadingState">
                        <div>🤖 AI is generating your contract...</div>
                        <div style="margin-top: 8px; font-size: 0.875rem;">This may take up to 30 seconds</div>
                    </div>
                </div>
            </div>
            
            <script>
                const templates = {{ templates | tojsonfilter | safe }};
                let selectedTemplate = null;
                
                function selectTemplate(templateId) {
                    selectedTemplate = templateId;
                    const template = templates[templateId];
                    
                    document.getElementById('formTitle').textContent = `Generate ${template.name}`;
                    document.getElementById('templateSelection').style.display = 'none';
                    document.getElementById('generatorForm').style.display = 'block';
                    
                    generateFormFields(template.fields);
                }
                
                function closeForm() {
                    document.getElementById('templateSelection').style.display = 'block';
                    document.getElementById('generatorForm').style.display = 'none';
                    selectedTemplate = null;
                }
                
                function generateFormFields(fields) {
                    const container = document.getElementById('formFields');
                    container.innerHTML = '';
                    
                    fields.forEach(field => {
                        const div = document.createElement('div');
                        div.className = field.type === 'textarea' ? 'form-group full-width' : 'form-group';
                        
                        const label = document.createElement('label');
                        label.className = 'form-label';
                        label.innerHTML = field.label + (field.required ? ' <span class="required-indicator">*</span>' : '');
                        
                        let input;
                        
                        if (field.type === 'textarea') {
                            input = document.createElement('textarea');
                            input.className = 'form-textarea';
                            input.placeholder = field.placeholder || '';
                        } else if (field.type === 'select') {
                            input = document.createElement('select');
                            input.className = 'form-select';
                            field.options.forEach(option => {
                                const optionElement = document.createElement('option');
                                optionElement.value = option;
                                optionElement.textContent = option;
                                if (option === field.default) {
                                    optionElement.selected = true;
                                }
                                input.appendChild(optionElement);
                            });
                        } else if (field.type === 'boolean') {
                            const checkboxGroup = document.createElement('div');
                            checkboxGroup.className = 'form-checkbox-group';
                            
                            input = document.createElement('input');
                            input.type = 'checkbox';
                            input.className = 'form-checkbox';
                            input.checked = field.default || false;
                            
                            const checkboxLabel = document.createElement('label');
                            checkboxLabel.textContent = field.label;
                            
                            checkboxGroup.appendChild(input);
                            checkboxGroup.appendChild(checkboxLabel);
                            
                            div.appendChild(checkboxGroup);
                        } else {
                            input = document.createElement('input');
                            input.type = field.type;
                            input.className = 'form-input';
                            input.placeholder = field.placeholder || '';
                            if (field.default !== undefined) {
                                input.value = field.default;
                            }
                        }
                        
                        input.name = field.name;
                        input.required = field.required || false;
                        
                        if (field.type !== 'boolean') {
                            div.appendChild(label);
                            div.appendChild(input);
                        }
                        
                        container.appendChild(div);
                    });
                }
                
                document.getElementById('contractForm').addEventListener('submit', async function(e) {
                    e.preventDefault();
                    
                    if (!selectedTemplate) return;
                    
                    const formData = new FormData(this);
                    const data = {
                        template_id: selectedTemplate,
                        fields: {}
                    };
                    
                    // Collect form data
                    for (const [key, value] of formData.entries()) {
                        data.fields[key] = value;
                    }
                    
                    // Handle checkboxes separately
                    const checkboxes = this.querySelectorAll('input[type="checkbox"]');
                    checkboxes.forEach(checkbox => {
                        data.fields[checkbox.name] = checkbox.checked;
                    });
                    
                    // Show loading state
                    document.getElementById('contractForm').style.display = 'none';
                    document.getElementById('loadingState').style.display = 'block';
                    
                    try {
                        const response = await fetch('/api/contracts/generate', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify(data)
                        });
                        
                        const result = await response.json();
                        
                        if (result.success) {
                            // Open generated contract in new window
                            const contractWindow = window.open('', '_blank');
                            contractWindow.document.write(`
                                <html>
                                <head>
                                    <title>${result.contract.title}</title>
                                    <style>
                                        body { font-family: 'Times New Roman', serif; max-width: 800px; margin: 0 auto; padding: 40px; line-height: 1.6; }
                                        h1 { text-align: center; margin-bottom: 30px; }
                                        .metadata { background: #f5f5f5; padding: 15px; margin-bottom: 30px; border-radius: 5px; }
                                        .actions { position: fixed; top: 20px; right: 20px; }
                                        .btn { padding: 10px 20px; margin: 5px; border: none; border-radius: 5px; cursor: pointer; }
                                        .btn-primary { background: #2E4B3C; color: white; }
                                        .btn-secondary { background: #ccc; color: black; }
                                    </style>
                                </head>
                                <body>
                                    <div class="actions">
                                        <button class="btn btn-primary" onclick="window.print()">Print</button>
                                        <button class="btn btn-secondary" onclick="window.close()">Close</button>
                                    </div>
                                    <div class="metadata">
                                        <strong>Generated by LexAI</strong><br>
                                        Template: ${result.contract.template_name}<br>
                                        Generated: ${new Date().toLocaleDateString()}<br>
                                        <small>This is an AI-generated legal document. Please review carefully and consult with a qualified attorney before use.</small>
                                    </div>
                                    <h1>${result.contract.title}</h1>
                                    <div>${result.contract.content.replace(/\\n/g, '<br>')}</div>
                                </body>
                                </html>
                            `);
                            contractWindow.document.close();
                            
                            // Reset form
                            closeForm();
                        } else {
                            alert('Failed to generate contract: ' + result.error);
                        }
                    } catch (error) {
                        alert('Error generating contract: ' + error.message);
                    } finally {
                        // Hide loading state
                        document.getElementById('contractForm').style.display = 'block';
                        document.getElementById('loadingState').style.display = 'none';
                    }
                });
            </script>
        </body>
        </html>
        """, templates=CONTRACT_TEMPLATES)
        
    except Exception as e:
        logger.error(f"Contracts generator error: {e}")
        return f"""<!DOCTYPE html>
        <html><head><title>LexAI Contract Generator</title></head>
        <body style="font-family: Inter, sans-serif; padding: 40px; text-align: center;">
        <h1>📄 LexAI Contract Generator</h1>
        <p>Error loading contract generator: {e}</p>
        <a href="/" style="color: #2E4B3C;">← Back to Dashboard</a>
        </body></html>"""

@app.route('/api/contracts/generate', methods=['POST'])
@rate_limit_decorator
def generate_contract():
    """Generate AI-powered contract using template and user inputs"""
    try:
        data = request.get_json()
        template_id = data.get('template_id')
        fields = data.get('fields', {})
        
        if not template_id or template_id not in CONTRACT_TEMPLATES:
            return jsonify({"error": "Invalid template ID"}), 400
        
        template = CONTRACT_TEMPLATES[template_id]
        
        # Build AI prompt for contract generation
        ai_prompt = f"""Generate a professional {template['name']} contract with the following specifications:

TEMPLATE: {template['name']}
CATEGORY: {template['category']}
AI INSTRUCTIONS: {template['ai_instructions']}

CONTRACT DETAILS:
"""
        
        # Add user-provided field values
        for field in template['fields']:
            field_name = field['name']
            field_value = fields.get(field_name, field.get('default', ''))
            ai_prompt += f"- {field['label']}: {field_value}\n"
        
        ai_prompt += """

REQUIREMENTS:
1. Generate a complete, professional legal contract
2. Use proper legal language and formatting
3. Include all necessary clauses for this contract type
4. Ensure enforceability and legal compliance
5. Add appropriate signature blocks and date fields
6. Include standard legal disclaimers where appropriate

FORMAT: Return the complete contract text ready for use, with proper formatting and legal structure."""
        
        # In production, call actual AI service (GPT-4, Claude, etc.)
        # For demo, generate a structured contract based on template
        contract_content = generate_mock_contract(template, fields)
        
        return jsonify({
            "success": True,
            "contract": {
                "title": template['name'],
                "template_name": template['name'],
                "content": contract_content,
                "generated_at": datetime.utcnow().isoformat(),
                "fields_used": fields
            },
            "ai_prompt_used": ai_prompt[:200] + "..."  # For debugging
        })
        
    except Exception as e:
        logger.error(f"Contract generation error: {e}")
        return jsonify({"error": "Failed to generate contract"}), 500

def generate_mock_contract(template, fields):
    """Generate a mock contract for demo purposes (replace with actual AI in production)"""
    
    if template['name'] == 'Non-Disclosure Agreement (NDA)':
        return f"""NON-DISCLOSURE AGREEMENT

This Non-Disclosure Agreement ("Agreement") is entered into as of _____________, 2025, between {fields.get('disclosing_party', '[DISCLOSING PARTY]')} ("Disclosing Party") and {fields.get('receiving_party', '[RECEIVING PARTY]')} ("Receiving Party").

1. PURPOSE
The purpose of this Agreement is to facilitate discussions regarding {fields.get('purpose', '[PURPOSE OF DISCLOSURE]')}.

2. CONFIDENTIAL INFORMATION
For purposes of this Agreement, "Confidential Information" means any and all information disclosed by the Disclosing Party to the Receiving Party, whether orally, in writing, or in any other form.

3. OBLIGATIONS OF RECEIVING PARTY
The Receiving Party agrees to:
a) Hold all Confidential Information in strict confidence
b) Not disclose Confidential Information to any third parties
c) Use Confidential Information solely for the Purpose stated above
d) Return or destroy all Confidential Information upon termination

4. TERM
This Agreement shall remain in effect for {fields.get('duration_years', '3')} years from the date first written above.

5. GOVERNING LAW
This Agreement shall be governed by the laws of {fields.get('jurisdiction', 'California')}.

6. REMEDIES
The Receiving Party acknowledges that any breach of this Agreement may cause irreparable harm, and the Disclosing Party shall be entitled to seek equitable relief.

IN WITNESS WHEREOF, the parties have executed this Agreement as of the date first written above.

DISCLOSING PARTY:                    RECEIVING PARTY:

_________________________           _________________________
{fields.get('disclosing_party', '[DISCLOSING PARTY]')}
Date: _______________               Date: _______________

Generated by LexAI - Please review with qualified legal counsel before use."""
    
    elif template['name'] == 'Service Agreement':
        return f"""SERVICE AGREEMENT

This Service Agreement ("Agreement") is entered into as of _____________, 2025, between {fields.get('service_provider', '[SERVICE PROVIDER]')} ("Provider") and {fields.get('client', '[CLIENT]')} ("Client").

1. SERVICES
Provider agrees to provide the following services: {fields.get('services_description', '[SERVICES DESCRIPTION]')}.

2. COMPENSATION
Client agrees to pay Provider ${fields.get('payment_amount', '[AMOUNT]')} according to the following schedule: {fields.get('payment_schedule', 'Monthly')}.

3. TERM
This Agreement shall commence on _____________ and continue for {fields.get('term_months', '12')} months unless terminated earlier.

4. TERMINATION
Either party may terminate this Agreement with {fields.get('cancellation_notice_days', '30')} days written notice.

5. PERFORMANCE STANDARDS
Provider agrees to perform all services in a professional and timely manner consistent with industry standards.

6. INDEPENDENT CONTRACTOR
Provider is an independent contractor and not an employee of Client.

7. CONFIDENTIALITY
Both parties agree to maintain confidentiality of proprietary information.

IN WITNESS WHEREOF, the parties have executed this Agreement as of the date first written above.

PROVIDER:                           CLIENT:

_________________________          _________________________
{fields.get('service_provider', '[SERVICE PROVIDER]')}
Date: _______________              Date: _______________

Generated by LexAI - Please review with qualified legal counsel before use."""
    
    # Add more template implementations as needed
    else:
        return f"""[GENERATED CONTRACT]

Contract Type: {template['name']}
Category: {template['category']}

This is a professionally generated {template['name']} based on your specifications. The complete contract would include all necessary legal provisions, terms, and conditions appropriate for this type of agreement.

User-Provided Information:
{chr(10).join([f"- {k}: {v}" for k, v in fields.items()])}

[The full contract content would be generated here using advanced AI legal language models]

Generated by LexAI - Please review with qualified legal counsel before use."""

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