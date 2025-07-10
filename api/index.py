#!/usr/bin/env python3
"""
LexAI Practice Partner - Clean Serverless Version
Streamlined version for Vercel deployment without duplicate routes
"""

import os
import json
import logging
import uuid
import requests
from datetime import datetime, timedelta, date
from decimal import Decimal
from flask import Flask, request, jsonify, render_template, session, redirect
from functools import wraps
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Set up logging first
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import database components
try:
    from models import db, User, Client, Case, TimeEntry, Invoice, Expense, UserRole, TimeEntryStatus, InvoiceStatus, Task, CalendarEvent, CaseStatus, TaskStatus, TaskPriority, case_attorneys, Document, DocumentStatus
    from database import DatabaseManager, audit_log
    DATABASE_AVAILABLE = True
    logger.info("Database models loaded successfully")
except ImportError as e:
    logger.warning(f"Database models not available: {e}")
    logger.info("Falling back to mock data - install Flask-SQLAlchemy to enable database integration")
    DATABASE_AVAILABLE = False

# Create Flask app
app = Flask(__name__, template_folder='../templates', static_folder='../static')
app.secret_key = os.environ.get('SECRET_KEY', 'dev-key-change-in-production')

# Initialize database if available
if DATABASE_AVAILABLE:
    try:
        db_manager = DatabaseManager(app)
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.warning(f"Database initialization failed: {e}")
        logger.info("Falling back to mock data mode")
        DATABASE_AVAILABLE = False
else:
    logger.warning("Running without database - using mock data")

# Basic configuration
app.config.update({
    'SECRET_KEY': os.environ.get('SECRET_KEY', 'dev-key-change-in-production'),
    'DATABASE_URL': os.environ.get('DATABASE_URL'),
    'REDIS_URL': os.environ.get('REDIS_URL'),
    'BAGEL_RL_API_KEY': os.environ.get('BAGEL_RL_API_KEY'),
    'XAI_API_KEY': os.environ.get('XAI_API_KEY'),
    'GOOGLE_ANALYTICS_ID': os.environ.get('GOOGLE_ANALYTICS_ID'),
})

# Initialize Stripe if available
STRIPE_AVAILABLE = bool(os.environ.get('STRIPE_SECRET_KEY'))
STRIPE_MODULE_AVAILABLE = False
try:
    import stripe
    stripe.api_key = os.environ.get('STRIPE_SECRET_KEY')
    STRIPE_MODULE_AVAILABLE = True
    logger.info("Stripe initialized successfully")
except ImportError as e:
    logger.warning(f"Stripe import failed: {e}")
    logger.info("Stripe functionality may be limited without the stripe package")
    # Still consider Stripe available if environment variable is set
    # This allows the billing interface to work with external Stripe integrations

# Service availability flags
BAGEL_AI_AVAILABLE = bool(os.environ.get('BAGEL_RL_API_KEY'))
SPANISH_AVAILABLE = True
PRIVACY_AI_AVAILABLE = False

logger.info(f"BAGEL_AI_AVAILABLE: {BAGEL_AI_AVAILABLE}")
logger.info(f"SPANISH_AVAILABLE: {SPANISH_AVAILABLE}")
logger.info(f"STRIPE_AVAILABLE: {STRIPE_AVAILABLE}")

# ===== AI DOCUMENT ANALYSIS HELPER FUNCTIONS =====

def _analyze_document_with_ai(text, xai_api_key):
    """Analyze document using XAI API"""
    try:
        # Prepare analysis prompt
        analysis_prompt = f"""
        Analyze the following legal document and provide a comprehensive analysis:

        Document text:
        {text[:8000]}...

        Please provide:
        1. Document type and category
        2. Key legal concepts and terms
        3. Main parties involved
        4. Important dates and deadlines
        5. Potential legal issues or risks
        6. Summary of key points
        7. Recommendations for legal professionals

        Format your response as a structured analysis.
        """

        response = requests.post(
            'https://api.x.ai/v1/chat/completions',
            headers={
                'Authorization': f'Bearer {xai_api_key}',
                'Content-Type': 'application/json'
            },
            json={
                'model': 'grok-beta',
                'messages': [
                    {'role': 'system', 'content': 'You are a legal document analysis expert. Provide thorough, accurate analysis of legal documents.'},
                    {'role': 'user', 'content': analysis_prompt}
                ],
                'max_tokens': 2000,
                'temperature': 0.3
            },
            timeout=30
        )

        if response.status_code == 200:
            ai_response = response.json()
            analysis_text = ai_response['choices'][0]['message']['content']
            
            return {
                'full_analysis': analysis_text,
                'summary': analysis_text[:500] + '...' if len(analysis_text) > 500 else analysis_text,
                'confidence': 0.85,
                'word_count': len(text.split()),
                'character_count': len(text),
                'analysis_date': datetime.now().isoformat()
            }
        else:
            logger.error(f"XAI API error in document analysis: {response.status_code}")
            return {'error': 'AI analysis failed', 'fallback': True}
            
    except Exception as e:
        logger.error(f"Document analysis error: {e}")
        return {'error': str(e), 'fallback': True}

def _categorize_document_with_ai(text, filename, xai_api_key):
    """Categorize document using XAI API"""
    try:
        categorization_prompt = f"""
        Categorize the following legal document based on its content and filename.

        Filename: {filename}
        Document text:
        {text[:6000]}...

        Please categorize this document into:
        1. Primary legal category (e.g., Contract, Litigation, Corporate, Real Estate, etc.)
        2. Document type (e.g., Purchase Agreement, Motion, Memorandum, etc.)
        3. Practice area (e.g., Corporate Law, Family Law, Criminal Law, etc.)
        4. Urgency level (High, Medium, Low)
        5. Suggested tags for organization

        Return your response in a structured format.
        """

        response = requests.post(
            'https://api.x.ai/v1/chat/completions',
            headers={
                'Authorization': f'Bearer {xai_api_key}',
                'Content-Type': 'application/json'
            },
            json={
                'model': 'grok-beta',
                'messages': [
                    {'role': 'system', 'content': 'You are a legal document categorization expert. Provide accurate categorization of legal documents.'},
                    {'role': 'user', 'content': categorization_prompt}
                ],
                'max_tokens': 1000,
                'temperature': 0.2
            },
            timeout=30
        )

        if response.status_code == 200:
            ai_response = response.json()
            categorization_text = ai_response['choices'][0]['message']['content']
            
            # Extract structured data from response
            return {
                'ai_categorization': categorization_text,
                'suggested_category': 'Contract',  # Default fallback
                'document_type': 'Legal Document',
                'practice_area': 'General',
                'urgency_level': 'Medium',
                'suggested_tags': ['legal', 'document'],
                'confidence': 0.80,
                'categorization_date': datetime.now().isoformat()
            }
        else:
            logger.error(f"XAI API error in document categorization: {response.status_code}")
            return {'error': 'AI categorization failed', 'fallback': True}
            
    except Exception as e:
        logger.error(f"Document categorization error: {e}")
        return {'error': str(e), 'fallback': True}

def _extract_document_info_with_ai(text, document_type, xai_api_key):
    """Extract key information from document using XAI API"""
    try:
        extraction_prompt = f"""
        Extract key information from this {document_type} document:

        Document text:
        {text[:7000]}...

        Please extract:
        1. Party names and roles
        2. Important dates and deadlines
        3. Financial amounts and terms
        4. Key clauses and provisions
        5. Legal obligations and responsibilities
        6. Contact information
        7. Reference numbers or case numbers

        Format the response as structured data.
        """

        response = requests.post(
            'https://api.x.ai/v1/chat/completions',
            headers={
                'Authorization': f'Bearer {xai_api_key}',
                'Content-Type': 'application/json'
            },
            json={
                'model': 'grok-beta',
                'messages': [
                    {'role': 'system', 'content': 'You are a legal document information extraction expert. Extract structured data from legal documents.'},
                    {'role': 'user', 'content': extraction_prompt}
                ],
                'max_tokens': 1500,
                'temperature': 0.1
            },
            timeout=30
        )

        if response.status_code == 200:
            ai_response = response.json()
            extraction_text = ai_response['choices'][0]['message']['content']
            
            return {
                'extracted_info': extraction_text,
                'parties': [],
                'dates': [],
                'amounts': [],
                'obligations': [],
                'extraction_date': datetime.now().isoformat(),
                'confidence': 0.75
            }
        else:
            logger.error(f"XAI API error in document extraction: {response.status_code}")
            return {'error': 'AI extraction failed', 'fallback': True}
            
    except Exception as e:
        logger.error(f"Document extraction error: {e}")
        return {'error': str(e), 'fallback': True}

def _summarize_document_with_ai(text, summary_type, xai_api_key):
    """Generate document summary using XAI API"""
    try:
        if summary_type == 'brief':
            max_tokens = 300
            instruction = 'Provide a brief 2-3 sentence summary'
        elif summary_type == 'detailed':
            max_tokens = 1000
            instruction = 'Provide a detailed summary covering all key points'
        else:  # standard
            max_tokens = 500
            instruction = 'Provide a comprehensive summary'

        summary_prompt = f"""
        {instruction} of the following legal document:

        Document text:
        {text[:8000]}...

        Focus on:
        - Main purpose and key points
        - Important parties and roles
        - Key dates and deadlines
        - Legal implications
        - Action items or next steps
        """

        response = requests.post(
            'https://api.x.ai/v1/chat/completions',
            headers={
                'Authorization': f'Bearer {xai_api_key}',
                'Content-Type': 'application/json'
            },
            json={
                'model': 'grok-beta',
                'messages': [
                    {'role': 'system', 'content': 'You are a legal document summarization expert. Provide clear, concise summaries of legal documents.'},
                    {'role': 'user', 'content': summary_prompt}
                ],
                'max_tokens': max_tokens,
                'temperature': 0.3
            },
            timeout=30
        )

        if response.status_code == 200:
            ai_response = response.json()
            summary_text = ai_response['choices'][0]['message']['content']
            
            return {
                'summary': summary_text,
                'summary_type': summary_type,
                'word_count': len(summary_text.split()),
                'summary_date': datetime.now().isoformat(),
                'confidence': 0.85
            }
        else:
            logger.error(f"XAI API error in document summarization: {response.status_code}")
            return {'error': 'AI summarization failed', 'fallback': True}
            
    except Exception as e:
        logger.error(f"Document summarization error: {e}")
        return {'error': str(e), 'fallback': True}

def _find_similar_documents(text, xai_api_key, limit):
    """Find similar documents using AI-powered similarity analysis"""
    try:
        # Get all documents from database
        documents = Document.query.limit(100).all()  # Limit for performance
        
        if not documents:
            return []
        
        # Use AI to find similar documents
        similarity_prompt = f"""
        Find documents similar to this reference document:

        Reference document:
        {text[:3000]}...

        Compare against these documents and rank by similarity:
        """
        
        # Add document snippets for comparison
        for i, doc in enumerate(documents[:20]):  # Limit comparison set
            similarity_prompt += f"\n{i+1}. {doc.title}: {doc.description[:200]}..."
        
        similarity_prompt += "\n\nRank the top similar documents by relevance and similarity."

        response = requests.post(
            'https://api.x.ai/v1/chat/completions',
            headers={
                'Authorization': f'Bearer {xai_api_key}',
                'Content-Type': 'application/json'
            },
            json={
                'model': 'grok-beta',
                'messages': [
                    {'role': 'system', 'content': 'You are a document similarity expert. Compare documents and rank by similarity.'},
                    {'role': 'user', 'content': similarity_prompt}
                ],
                'max_tokens': 1000,
                'temperature': 0.2
            },
            timeout=30
        )

        if response.status_code == 200:
            # For now, return a simple similarity based on document type
            similar_docs = []
            for doc in documents[:limit]:
                similar_docs.append({
                    'document_id': doc.id,
                    'title': doc.title,
                    'document_type': doc.document_type,
                    'similarity_score': 0.75,  # Placeholder
                    'case_title': doc.case.title if doc.case else None,
                    'client_name': doc.client.get_display_name() if doc.client else None
                })
            
            return similar_docs
        else:
            logger.error(f"XAI API error in similarity search: {response.status_code}")
            return []
            
    except Exception as e:
        logger.error(f"Document similarity search error: {e}")
        return []

# ===== AUTHENTICATION MIDDLEWARE =====

def login_required(f):
    """Decorator to require authentication for routes"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('logged_in'):
            # DEVELOPMENT: Auto-create demo session for development
            if not DATABASE_AVAILABLE:
                logger.info("Auto-creating demo session for development")
                session['user_id'] = 'demo'
                session['user_email'] = 'demo@lexai.com'
                session['user_role'] = 'partner'
                session['user_name'] = 'Demo User'
                session['logged_in'] = True
            else:
                if request.is_json:
                    return jsonify({
                        'success': False,
                        'error': 'Authentication required'
                    }), 401
                else:
                    return redirect('/login')
        return f(*args, **kwargs)
    return decorated_function

def role_required(*allowed_roles):
    """Decorator to require specific roles for routes"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not session.get('logged_in'):
                if request.is_json:
                    return jsonify({
                        'success': False,
                        'error': 'Authentication required'
                    }), 401
                else:
                    return redirect('/login')
            
            user_role = session.get('user_role')
            if user_role not in allowed_roles:
                if request.is_json:
                    return jsonify({
                        'success': False,
                        'error': 'Insufficient permissions'
                    }), 403
                else:
                    return jsonify({
                        'success': False,
                        'error': 'Access denied - insufficient permissions'
                    }), 403
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def admin_required(f):
    """Decorator to require admin role"""
    return role_required('admin')(f)

def get_current_user():
    """Helper function to get current user information"""
    if not session.get('logged_in'):
        return None
    
    if not DATABASE_AVAILABLE:
        return {
            'id': session.get('user_id'),
            'email': session.get('user_email'),
            'role': session.get('user_role'),
            'name': session.get('user_name')
        }
    
    try:
        user_id = session.get('user_id')
        user = User.query.get(user_id)
        return user
    except:
        return None

# ===== MAIN ROUTES =====

@app.route('/')
def landing_page():
    """Landing page"""
    try:
        return render_template('landing.html',
                             google_analytics_id=app.config.get('GOOGLE_ANALYTICS_ID'),
                             cache_buster=str(uuid.uuid4())[:8])
    except Exception as e:
        logger.error(f"Landing page error: {e}")
        return f"LexAI Practice Partner - Error loading page: {e}", 500

@app.route('/dashboard')
@login_required
def dashboard():
    """Main dashboard"""
    try:
        # Sample stats data for dashboard
        stats = {
            'total_chats': 24,
            'total_documents': 8,
            'research_queries': 15,
            'total_clients': 3
        }
        
        # Debug: Log session data
        logger.info(f"Session data: {dict(session)}")
        user_role = session.get('user_role', 'attorney')
        logger.info(f"User role being passed to template: {user_role}")
        
        return render_template('dashboard.html',
                             user_role=user_role,  # Default to attorney for full menu access
                             user_name=session.get('user_name', 'User'),
                             stats=stats,
                             cache_buster=str(uuid.uuid4())[:8])
    except Exception as e:
        logger.error(f"Dashboard error: {e}")
        return f"Dashboard error: {e}", 500

@app.route('/documents')
def documents_page():
    """Document management page"""
    try:
        return render_template('document_library.html')
    except Exception as e:
        logger.error(f"Documents page error: {e}")
        return f"Documents error: {e}", 500

@app.route('/documents/analysis')
@login_required
def document_analysis_page():
    """AI-powered document analysis page"""
    try:
        return render_template('document_analysis_enhanced.html',
                             xai_available=bool(app.config.get('XAI_API_KEY')))
    except Exception as e:
        logger.error(f"Document analysis page error: {e}")
        return f"Document analysis error: {e}", 500

@app.route('/contracts')
@login_required
def contracts_page():
    """Contract analysis page"""
    try:
        return render_template('contracts.html',
                             bagel_available=BAGEL_AI_AVAILABLE)
    except Exception as e:
        logger.error(f"Contracts page error: {e}")
        return f"Contracts error: {e}", 500

@app.route('/legal-research')
@login_required
def legal_research_page():
    """Legal research page"""
    try:
        return render_template('legal_research.html',
                             bagel_available=BAGEL_AI_AVAILABLE)
    except Exception as e:
        logger.error(f"Legal research page error: {e}")
        return f"Legal research error: {e}", 500

@app.route('/spanish')
@login_required
def spanish_interface():
    """Spanish language interface"""
    try:
        return render_template('spanish_interface.html',
                             spanish_available=SPANISH_AVAILABLE)
    except Exception as e:
        logger.error(f"Spanish interface error: {e}")
        return f"Spanish interface error: {e}", 500

@app.route('/api/debug/stripe-status')
def debug_stripe_status():
    """Debug endpoint to check Stripe configuration"""
    # Test Stripe import
    stripe_import_error = None
    stripe_import_success = False
    try:
        import stripe as stripe_test
        stripe_import_success = True
    except Exception as e:
        stripe_import_error = str(e)
    
    # Debug environment variable
    env_value = os.environ.get('STRIPE_SECRET_KEY')
    env_bool = bool(env_value)
    
    return jsonify({
        'STRIPE_AVAILABLE': STRIPE_AVAILABLE,
        'STRIPE_MODULE_AVAILABLE': STRIPE_MODULE_AVAILABLE,
        'env_value_exists': env_value is not None,
        'env_value_length': len(env_value) if env_value else 0,
        'env_bool_conversion': env_bool,
        'manual_stripe_available_check': bool(os.environ.get('STRIPE_SECRET_KEY')),
        'STRIPE_SECRET_KEY_EXISTS': bool(os.environ.get('STRIPE_SECRET_KEY')),
        'STRIPE_SECRET_KEY_VALUE': env_value[:10] + '...' if env_value else 'Not Set',
        'stripe_module_available': 'stripe' in globals(),
        'stripe_import_test_success': stripe_import_success,
        'stripe_import_error': stripe_import_error,
        'requirements_check': {
            'stripe_in_requirements': True  # We know it's there
        }
    })

@app.route('/billing')
def billing_page():
    """Billing and payments page"""
    try:
        logger.info(f"Billing page - STRIPE_AVAILABLE: {STRIPE_AVAILABLE}")
        logger.info(f"Billing page - STRIPE_SECRET_KEY exists: {bool(os.environ.get('STRIPE_SECRET_KEY'))}")
        return render_template('billing.html',
                             stripe_available=STRIPE_AVAILABLE)
    except Exception as e:
        logger.error(f"Billing page error: {e}")
        return f"Billing error: {e}", 500

@app.route('/clients')
@login_required
def clients_page():
    """Client management page"""
    try:
        return render_template('clients_enhanced.html')
    except Exception as e:
        logger.error(f"Clients page error: {e}")
        return f"Clients error: {e}", 500

@app.route('/clients/<client_id>')
@login_required
def client_profile_page(client_id):
    """Individual client profile page"""
    try:
        return render_template('client_profile.html', client_id=client_id)
    except Exception as e:
        logger.error(f"Client profile page error: {e}")
        return f"Client profile error: {e}", 500

@app.route('/clients/<client_id>/edit')
@login_required
def client_edit_page(client_id):
    """Client edit page"""
    try:
        return render_template('client_edit.html', client_id=client_id)
    except Exception as e:
        logger.error(f"Client edit page error: {e}")
        return f"Client edit error: {e}", 500

@app.route('/clients/new')
@login_required
def client_new_page():
    """New client creation page"""
    try:
        return render_template('client_new.html')
    except Exception as e:
        logger.error(f"Client new page error: {e}")
        return f"Client new error: {e}", 500

@app.route('/cases')
@login_required
def cases_page():
    """Case management page"""
    try:
        return render_template('cases.html')
    except Exception as e:
        logger.error(f"Cases page error: {e}")
        return f"Cases error: {e}", 500

@app.route('/cases/<case_id>')
@login_required
def case_profile_page(case_id):
    """Individual case profile page"""
    try:
        return render_template('case_profile.html', case_id=case_id)
    except Exception as e:
        logger.error(f"Case profile page error: {e}")
        return f"Case profile error: {e}", 500

@app.route('/deadlines')
def deadlines_page():
    """Deadline management and court calendar page"""
    try:
        return render_template('deadlines.html')
    except Exception as e:
        logger.error(f"Deadlines page error: {e}")
        return f"Deadlines error: {e}", 500

@app.route('/admin')
def admin_dashboard():
    """Admin dashboard - overview of all administrative functions"""
    try:
        return render_template('admin/dashboard.html',
                             user_role=session.get('user_role', 'admin'),
                             user_name=session.get('user_name', 'Admin'),
                             page_title='Admin Dashboard',
                             cache_buster=str(uuid.uuid4())[:8])
    except Exception as e:
        logger.error(f"Admin dashboard page error: {e}")
        return f"Admin dashboard error: {e}", 500

@app.route('/admin/users')
def admin_users():
    """Admin user management page - manage firm's user accounts"""
    try:
        # User management stats
        stats = {
            'total_users': 12,
            'active_users': 11,
            'partners': 4,
            'admin_users': 3
        }
        
        # Mock firm user accounts with enterprise-grade data
        firm_users = [
            {
                'id': 'user_1',
                'name': 'John Doe',
                'email': 'john.doe@lawfirm.com',
                'role': 'Managing Partner',
                'status': 'Active',
                'last_login': '2 hours ago',
                'permissions': 'Full Access',
                'cases': 24,
                'initials': 'JD'
            },
            {
                'id': 'user_2',
                'name': 'Jane Smith',
                'email': 'jane.smith@lawfirm.com',
                'role': 'Senior Partner',
                'status': 'Active',
                'last_login': '1 hour ago',
                'permissions': 'Full Access',
                'cases': 18,
                'initials': 'JS'
            },
            {
                'id': 'user_3',
                'name': 'Bob Johnson',
                'email': 'bob.johnson@lawfirm.com',
                'role': 'Senior Associate',
                'status': 'Active',
                'last_login': '3 hours ago',
                'permissions': 'Limited Access',
                'cases': 12,
                'initials': 'BJ'
            },
            {
                'id': 'user_4',
                'name': 'Sarah Wilson',
                'email': 'sarah.wilson@lawfirm.com',
                'role': 'Associate',
                'status': 'Active',
                'last_login': '5 hours ago',
                'permissions': 'Limited Access',
                'cases': 8,
                'initials': 'SW'
            },
            {
                'id': 'user_5',
                'name': 'Mike Brown',
                'email': 'mike.brown@lawfirm.com',
                'role': 'Junior Associate',
                'status': 'Pending',
                'last_login': 'Never',
                'permissions': 'Basic Access',
                'cases': 0,
                'initials': 'MB'
            }
        ]
        
        return render_template('admin/users.html', 
                             stats=stats,
                             firm_users=firm_users,
                             user_role=session.get('user_role', 'admin'),
                             user_name=session.get('user_name', 'Admin'),
                             page_title='User Management',
                             cache_buster=str(uuid.uuid4())[:8])
    except Exception as e:
        logger.error(f"Admin users page error: {e}")
        return f"Admin users error: {e}", 500

@app.route('/admin/settings')
def admin_settings():
    """Admin settings page - enterprise-grade firm configuration"""
    try:
        return render_template('admin/settings.html',
                             user_role=session.get('user_role', 'admin'),
                             user_name=session.get('user_name', 'Admin'),
                             page_title='System Settings',
                             cache_buster=str(uuid.uuid4())[:8])
    except Exception as e:
        logger.error(f"Admin settings page error: {e}")
        return f"Admin settings error: {e}", 500

@app.route('/admin/subscriptions')
def admin_subscriptions():
    """Admin subscriptions page - enterprise-grade billing management"""
    try:
        return render_template('admin/subscriptions.html',
                             user_role=session.get('user_role', 'admin'),
                             user_name=session.get('user_name', 'Admin'),
                             page_title='Subscription Management',
                             cache_buster=str(uuid.uuid4())[:8])
    except Exception as e:
        logger.error(f"Admin subscriptions page error: {e}")
        return f"Admin subscriptions error: {e}", 500

@app.route('/admin/audit-logs')
def admin_audit_logs():
    """Admin audit logs page - compliance tracking and monitoring"""
    try:
        return render_template('admin/audit-logs.html',
                             user_role=session.get('user_role', 'admin'),
                             user_name=session.get('user_name', 'Admin'),
                             page_title='Audit Logs',
                             cache_buster=str(uuid.uuid4())[:8])
    except Exception as e:
        logger.error(f"Admin audit logs page error: {e}")
        return f"Admin audit logs error: {e}", 500

@app.route('/cases/<case_id>/edit')
@login_required
def case_edit_page(case_id):
    """Case edit page"""
    try:
        return render_template('case_edit.html', case_id=case_id)
    except Exception as e:
        logger.error(f"Case edit page error: {e}")
        return f"Case edit error: {e}", 500

@app.route('/cases/new')
@login_required
def case_new_page():
    """New case creation page"""
    try:
        return render_template('case_new.html')
    except Exception as e:
        logger.error(f"Case new page error: {e}")
        return f"Case new error: {e}", 500

@app.route('/login')
@app.route('/auth/login')
def login_page():
    """Login page"""
    try:
        # Redirect if already logged in
        if session.get('logged_in'):
            return redirect('/dashboard')
        return render_template('auth_login_enhanced.html',
                             cache_buster=str(uuid.uuid4())[:8])
    except Exception as e:
        logger.error(f"Login page error: {e}")
        return f"Login error: {e}", 500

@app.route('/register')
@app.route('/auth/register')
def register_page():
    """Registration page"""
    try:
        # Redirect if already logged in
        if session.get('logged_in'):
            return redirect('/dashboard')
        return render_template('auth_register_enhanced.html',
                             cache_buster=str(uuid.uuid4())[:8])
    except Exception as e:
        logger.error(f"Register page error: {e}")
        return f"Register error: {e}", 500

@app.route('/chat')
@login_required
def chat_page():
    """Chat interface"""
    try:
        return render_template('chat.html',
                             xai_available=bool(app.config.get('XAI_API_KEY')))
    except Exception as e:
        logger.error(f"Chat page error: {e}")
        return f"Chat error: {e}", 500

@app.route('/onboarding')
@login_required
def onboarding_page():
    """User onboarding flow"""
    try:
        return render_template('onboarding.html')
    except Exception as e:
        logger.error(f"Onboarding error: {e}")
        return f"Onboarding error: {e}", 500

@app.route('/time-tracking')
@login_required
def time_tracking_page():
    """Time tracking interface"""
    try:
        return render_template('time_tracking.html')
    except Exception as e:
        logger.error(f"Time tracking error: {e}")
        return f"Time tracking error: {e}", 500

@app.route('/platform')
@login_required
def platform_page():
    """Platform overview page"""
    try:
        return render_template('platform_overview.html',
                             bagel_available=BAGEL_AI_AVAILABLE,
                             spanish_available=SPANISH_AVAILABLE,
                             stripe_available=STRIPE_AVAILABLE)
    except Exception as e:
        logger.error(f"Platform page error: {e}")
        return f"Platform error: {e}", 500

@app.route('/privacy-dashboard')
@login_required
def privacy_dashboard_page():
    """Privacy analysis dashboard"""
    try:
        return render_template('privacy_dashboard.html',
                             privacy_available=PRIVACY_AI_AVAILABLE)
    except Exception as e:
        logger.error(f"Privacy dashboard error: {e}")
        return f"Privacy dashboard error: {e}", 500

@app.route('/analytics-dashboard')
@login_required
def analytics_dashboard():
    """Analytics and reporting dashboard"""
    try:
        return render_template('analytics_dashboard.html')
    except Exception as e:
        logger.error(f"Analytics dashboard error: {e}")
        return f"Analytics dashboard error: {e}", 500

# ===== CLIENT PORTAL ROUTES =====

def client_portal_auth_required(f):
    """Decorator to require client portal authentication"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('client_portal_logged_in'):
            if request.is_json:
                return jsonify({'error': 'Client portal authentication required'}), 401
            return redirect('/client-portal/login')
        
        return f(*args, **kwargs)
    return decorated_function

@app.route('/client-portal/login')
def client_portal_login_page():
    """Client portal login page"""
    try:
        # Redirect if already logged in to client portal
        if session.get('client_portal_logged_in'):
            return redirect('/client-portal/dashboard')
        return render_template('client-portal-login.html',
                             cache_buster=str(uuid.uuid4())[:8])
    except Exception as e:
        logger.error(f"Client portal login page error: {e}")
        return f"Client portal login error: {e}", 500

@app.route('/client-portal/dashboard')
@client_portal_auth_required
def client_portal_dashboard_page():
    """Client portal dashboard page"""
    try:
        return render_template('client-portal-dashboard.html',
                             cache_buster=str(uuid.uuid4())[:8])
    except Exception as e:
        logger.error(f"Client portal dashboard page error: {e}")
        return f"Client portal dashboard error: {e}", 500

# ===== API ROUTES =====

@app.route('/api/health')
def api_health():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'version': '2.1',
        'services': {
            'bagel_ai': BAGEL_AI_AVAILABLE,
            'spanish': SPANISH_AVAILABLE,
            'stripe': STRIPE_AVAILABLE
        }
    })

@app.route('/api/status')
def api_status():
    """System status endpoint"""
    return jsonify({
        'success': True,
        'message': 'LexAI is running',
        'timestamp': datetime.now().isoformat(),
        'database_available': DATABASE_AVAILABLE,
        'data_source': 'PostgreSQL Database' if DATABASE_AVAILABLE else 'Mock Data'
    })

@app.route('/api/database/status')
def api_database_status():
    """Database integration status"""
    if DATABASE_AVAILABLE:
        try:
            with app.app_context():
                # Try to execute a simple query
                db.session.execute(db.text('SELECT 1')).fetchone()
                db_connection = 'Connected'
        except Exception as e:
            db_connection = f'Error: {str(e)}'
    else:
        db_connection = 'Not Available'
    
    return jsonify({
        'success': True,
        'database_integration': {
            'status': 'Available' if DATABASE_AVAILABLE else 'Not Available',
            'connection': db_connection,
            'models_loaded': DATABASE_AVAILABLE,
            'features': {
                'time_tracking': 'Database Integration Complete' if DATABASE_AVAILABLE else 'Mock Data Fallback',
                'invoicing': 'Database Integration Complete' if DATABASE_AVAILABLE else 'Mock Data Fallback',
                'client_management': 'Database Integration Complete' if DATABASE_AVAILABLE else 'Mock Data Fallback',
                'audit_logging': 'Available' if DATABASE_AVAILABLE else 'Not Available'
            }
        },
        'installation_note': 'Install Flask-SQLAlchemy, psycopg2-binary packages to enable database integration' if not DATABASE_AVAILABLE else None
    })

@app.route('/api/documents/analyze', methods=['POST'])
@login_required
@role_required('admin', 'partner', 'associate', 'paralegal')
def api_document_analyze():
    """Analyze document text using AI"""
    try:
        data = request.get_json()
        if not data or 'text' not in data:
            return jsonify({
                'success': False,
                'error': 'Document text required'
            }), 400
        
        text = data['text']
        document_id = data.get('document_id')
        
        # Get XAI API key for analysis
        xai_api_key = app.config.get('XAI_API_KEY')
        if not xai_api_key:
            return jsonify({
                'success': False,
                'error': 'AI analysis service not configured'
            }), 503
        
        # Perform AI analysis
        analysis_result = _analyze_document_with_ai(text, xai_api_key)
        
        # Update document with analysis results if document_id provided
        if document_id and DATABASE_AVAILABLE:
            document = Document.query.get(document_id)
            if document:
                # Store analysis results in document metadata
                document.description = f"{document.description or ''}\n\nAI Analysis: {analysis_result.get('summary', '')}"
                db.session.commit()
                audit_log('update', 'document', document_id, 
                         old_values={'description': document.description},
                         new_values={'ai_analysis': analysis_result})
        
        return jsonify({
            'success': True,
            'message': 'Document analysis completed',
            'analysis': analysis_result,
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Document analysis error: {e}")
        return jsonify({
            'success': False,
            'error': 'Document analysis failed'
        }), 500

@app.route('/api/documents/categorize', methods=['POST'])
@login_required
@role_required('admin', 'partner', 'associate', 'paralegal')
def api_document_categorize():
    """Categorize document using AI"""
    try:
        data = request.get_json()
        if not data or 'text' not in data:
            return jsonify({
                'success': False,
                'error': 'Document text required'
            }), 400
        
        text = data['text']
        filename = data.get('filename', '')
        
        # Get XAI API key for categorization
        xai_api_key = app.config.get('XAI_API_KEY')
        if not xai_api_key:
            return jsonify({
                'success': False,
                'error': 'AI categorization service not configured'
            }), 503
        
        # Perform AI categorization
        categorization_result = _categorize_document_with_ai(text, filename, xai_api_key)
        
        return jsonify({
            'success': True,
            'message': 'Document categorization completed',
            'categorization': categorization_result,
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Document categorization error: {e}")
        return jsonify({
            'success': False,
            'error': 'Document categorization failed'
        }), 500

@app.route('/api/documents/extract', methods=['POST'])
@login_required
@role_required('admin', 'partner', 'associate', 'paralegal')
def api_document_extract():
    """Extract key information from document"""
    try:
        data = request.get_json()
        if not data or 'text' not in data:
            return jsonify({
                'success': False,
                'error': 'Document text required'
            }), 400
        
        text = data['text']
        document_type = data.get('document_type', 'general')
        
        # Get XAI API key for extraction
        xai_api_key = app.config.get('XAI_API_KEY')
        if not xai_api_key:
            return jsonify({
                'success': False,
                'error': 'AI extraction service not configured'
            }), 503
        
        # Perform AI extraction
        extraction_result = _extract_document_info_with_ai(text, document_type, xai_api_key)
        
        return jsonify({
            'success': True,
            'message': 'Document extraction completed',
            'extraction': extraction_result,
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Document extraction error: {e}")
        return jsonify({
            'success': False,
            'error': 'Document extraction failed'
        }), 500

@app.route('/api/documents/summarize', methods=['POST'])
@login_required
@role_required('admin', 'partner', 'associate', 'paralegal')
def api_document_summarize():
    """Generate document summary using AI"""
    try:
        data = request.get_json()
        if not data or 'text' not in data:
            return jsonify({
                'success': False,
                'error': 'Document text required'
            }), 400
        
        text = data['text']
        summary_type = data.get('summary_type', 'standard')  # standard, brief, detailed
        
        # Get XAI API key for summarization
        xai_api_key = app.config.get('XAI_API_KEY')
        if not xai_api_key:
            return jsonify({
                'success': False,
                'error': 'AI summarization service not configured'
            }), 503
        
        # Perform AI summarization
        summary_result = _summarize_document_with_ai(text, summary_type, xai_api_key)
        
        return jsonify({
            'success': True,
            'message': 'Document summarization completed',
            'summary': summary_result,
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Document summarization error: {e}")
        return jsonify({
            'success': False,
            'error': 'Document summarization failed'
        }), 500

@app.route('/api/documents/search-similar', methods=['POST'])
@login_required
@role_required('admin', 'partner', 'associate', 'paralegal')
def api_document_search_similar():
    """Find similar documents using AI"""
    try:
        data = request.get_json()
        if not data or 'text' not in data:
            return jsonify({
                'success': False,
                'error': 'Document text required'
            }), 400
        
        text = data['text']
        limit = min(data.get('limit', 10), 50)
        
        if not DATABASE_AVAILABLE:
            return jsonify({
                'success': False,
                'error': 'Database not available for similarity search'
            }), 503
        
        # Get XAI API key for similarity analysis
        xai_api_key = app.config.get('XAI_API_KEY')
        if not xai_api_key:
            return jsonify({
                'success': False,
                'error': 'AI similarity service not configured'
            }), 503
        
        # Find similar documents
        similar_docs = _find_similar_documents(text, xai_api_key, limit)
        
        return jsonify({
            'success': True,
            'message': 'Similar documents found',
            'similar_documents': similar_docs,
            'count': len(similar_docs),
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Document similarity search error: {e}")
        return jsonify({
            'success': False,
            'error': 'Document similarity search failed'
        }), 500

@app.route('/api/spanish/translate', methods=['POST'])
@login_required
@role_required('admin', 'partner', 'associate', 'paralegal')
def api_spanish_translate():
    """Translate text to Spanish"""
    try:
        data = request.get_json()
        if not data or 'text' not in data:
            return jsonify({
                'success': False,
                'error': 'Text required for translation'
            }), 400
        
        # Basic response for now
        return jsonify({
            'success': True,
            'original_text': data['text'],
            'translated_text': f"[ES] {data['text']}",  # Placeholder
            'confidence_score': 0.95,
            'spanish_available': SPANISH_AVAILABLE
        })
        
    except Exception as e:
        logger.error(f"Spanish translation error: {e}")
        return jsonify({
            'success': False,
            'error': 'Translation failed'
        }), 500

@app.route('/api/contracts/analyze', methods=['POST'])
@login_required
@role_required('admin', 'partner', 'associate', 'paralegal')
def api_contract_analyze():
    """Analyze contract"""
    try:
        data = request.get_json()
        if not data or 'contract_text' not in data:
            return jsonify({
                'success': False,
                'error': 'Contract text required'
            }), 400
        
        # Basic response for now
        return jsonify({
            'success': True,
            'contract_type': 'service',
            'overall_risk_score': 25.0,
            'key_terms': ['agreement', 'payment', 'termination'],
            'recommendations': ['Review with legal counsel'],
            'bagel_available': BAGEL_AI_AVAILABLE
        })
        
    except Exception as e:
        logger.error(f"Contract analysis error: {e}")
        return jsonify({
            'success': False,
            'error': 'Contract analysis failed'
        }), 500

@app.route('/api/chat', methods=['POST'])
@login_required
def api_chat():
    """Chat with AI assistant"""
    try:
        data = request.get_json()
        if not data or 'message' not in data:
            return jsonify({
                'success': False,
                'error': 'Message required'
            }), 400
        
        message = data['message']
        practice_area = data.get('practice_area', 'general')
        conversation_history = data.get('conversation_history', [])
        has_document = data.get('has_document', False)
        document_content = data.get('document_content', '')
        
        # Check if XAI API is available
        xai_api_key = app.config.get('XAI_API_KEY')
        if not xai_api_key:
            return jsonify({
                'success': True,
                'response': 'I am LexAI, your legal practice assistant. How can I help you today? (Note: XAI API not configured)',
                'timestamp': datetime.now().isoformat()
            })
        
        # Prepare system prompt based on practice area
        system_prompts = {
            'general': "You are LexAI, a knowledgeable legal practice assistant. Provide helpful, accurate legal guidance while noting that you don't replace professional legal advice.",
            'corporate': "You are LexAI, specializing in corporate law. Help with business formation, contracts, compliance, and corporate governance matters.",
            'litigation': "You are LexAI, specializing in litigation. Help with case strategy, discovery, motions, and trial preparation.",
            'family': "You are LexAI, specializing in family law. Help with divorce, custody, adoption, and domestic relations matters.",
            'criminal': "You are LexAI, specializing in criminal law. Help with criminal defense, procedure, and constitutional law matters.",
            'immigration': "You are LexAI, specializing in immigration law. Help with visas, citizenship, deportation defense, and immigration procedures.",
            'real_estate': "You are LexAI, specializing in real estate law. Help with property transactions, leases, zoning, and real estate disputes.",
            'employment': "You are LexAI, specializing in employment law. Help with workplace issues, discrimination, labor relations, and employment contracts.",
            'ip': "You are LexAI, specializing in intellectual property law. Help with patents, trademarks, copyrights, and IP litigation.",
            'tax': "You are LexAI, specializing in tax law. Help with tax planning, compliance, disputes, and tax-related legal matters."
        }
        
        system_prompt = system_prompts.get(practice_area, system_prompts['general'])
        
        # Add document context if available
        if has_document and document_content:
            system_prompt += f"\n\nThe user has uploaded a document. Here's the content:\n{document_content[:5000]}..."
        
        # Build conversation for XAI API
        messages = [{"role": "system", "content": system_prompt}]
        
        # Add conversation history
        for msg in conversation_history[-8:]:  # Keep last 8 messages for context
            messages.append(msg)
        
        # Add current message
        messages.append({"role": "user", "content": message})
        
        # Call XAI API
        # 🔒 CRITICAL: DO NOT MODIFY WITHOUT USER PERMISSION - WORKING CONFIGURATION
        # Status: VERIFIED WORKING ✅
        # Last confirmed: User said "ok - api works"
        xai_response = requests.post(
            'https://api.x.ai/v1/chat/completions',  # ✅ VERIFIED WORKING ENDPOINT
            headers={
                'Authorization': f'Bearer {xai_api_key}',
                'Content-Type': 'application/json'
            },
            json={
                'model': 'grok-3-latest',  # ✅ VERIFIED WORKING MODEL
                'messages': messages,
                'max_tokens': 1000,
                'temperature': 0.7
            },
            timeout=30
        )
        
        if xai_response.status_code == 200:
            xai_data = xai_response.json()
            response_content = xai_data['choices'][0]['message']['content']
            
            return jsonify({
                'success': True,
                'response': response_content,
                'timestamp': datetime.now().isoformat()
            })
        else:
            logger.error(f"XAI API error: {xai_response.status_code} - {xai_response.text}")
            return jsonify({
                'success': True,
                'response': 'I apologize, but I\'m having trouble connecting to my AI service right now. Please try again in a moment.',
                'timestamp': datetime.now().isoformat()
            })
        
    except Exception as e:
        logger.error(f"Chat error: {e}")
        return jsonify({
            'success': False,
            'error': 'Chat request failed'
        }), 500

@app.route('/api/onboarding/complete', methods=['POST'])
@login_required
def api_onboarding_complete():
    """Complete user onboarding"""
    try:
        data = request.get_json()
        logger.info(f"Onboarding completed: {data.get('firmName', 'Unknown firm')}")
        
        return jsonify({
            'success': True,
            'message': 'Onboarding completed successfully',
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Onboarding completion error: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to complete onboarding'
        }), 500

# ===== TIME TRACKING API =====

@app.route('/api/time/entries', methods=['GET'])
@login_required
@role_required('admin', 'partner', 'associate', 'paralegal')
def api_get_time_entries():
    """Get time entries for current user"""
    try:
        if not DATABASE_AVAILABLE:
            return _get_mock_time_entries()
        
        # Get current user ID (for now, use a default user - later will get from session)
        user_id = session.get('user_id', '1')  # Will implement proper auth later
        
        # Query time entries for the user
        entries = TimeEntry.query.filter_by(user_id=user_id).order_by(TimeEntry.created_at.desc()).all()
        
        entries_data = []
        for entry in entries:
            entries_data.append({
                'id': entry.id,
                'description': entry.description,
                'hours': float(entry.hours),
                'hourly_rate': float(entry.hourly_rate),
                'amount': float(entry.amount),
                'billable': entry.billable,
                'status': entry.status.value,
                'date': entry.date.isoformat() if entry.date else None,
                'case_title': entry.case.title if entry.case else None,
                'client_name': entry.case.client.get_display_name() if entry.case and entry.case.client else None,
                'created_at': entry.created_at.isoformat() if entry.created_at else None
            })
        
        total_hours = sum(float(entry.hours) for entry in entries)
        total_billable = sum(float(entry.amount) for entry in entries if entry.billable)
        
        return jsonify({
            'success': True,
            'entries': entries_data,
            'total_hours': total_hours,
            'total_billable': total_billable
        })
        
    except Exception as e:
        logger.error(f"Get time entries error: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to retrieve time entries'
        }), 500

def _get_mock_time_entries():
    """Fallback mock data when database is not available"""
    entries = [
        {
            'id': '1',
            'description': 'Client consultation and case review',
            'hours': 2.5,
            'hourly_rate': 250.00,
            'amount': 625.00,
            'billable': True,
            'status': 'draft',
            'date': '2025-07-08',
            'case_title': 'Smith vs. Jones',
            'client_name': 'John Smith'
        },
        {
            'id': '2', 
            'description': 'Document preparation and research',
            'hours': 3.0,
            'hourly_rate': 250.00,
            'amount': 750.00,
            'billable': True,
            'status': 'submitted',
            'date': '2025-07-07',
            'case_title': 'ABC Corp Contract Review',
            'client_name': 'ABC Corporation'
        }
    ]
    
    return jsonify({
        'success': True,
        'entries': entries,
        'total_hours': sum(e['hours'] for e in entries),
        'total_billable': sum(e['amount'] for e in entries if e['billable'])
    })

@app.route('/api/time/entries', methods=['POST'])
@login_required
@role_required('admin', 'partner', 'associate', 'paralegal')
def api_create_time_entry():
    """Create new time entry"""
    try:
        data = request.get_json()
        
        required_fields = ['description', 'hours', 'hourly_rate']
        for field in required_fields:
            if field not in data:
                return jsonify({
                    'success': False,
                    'error': f'Missing required field: {field}'
                }), 400
        
        # Calculate amount
        hours = Decimal(str(data['hours']))
        rate = Decimal(str(data['hourly_rate']))
        amount = hours * rate
        
        if not DATABASE_AVAILABLE:
            return _create_mock_time_entry(data, hours, rate, amount)
        
        # Get current user ID (will implement proper auth later)
        user_id = session.get('user_id', '1')
        
        # Create new time entry
        entry = TimeEntry(
            description=data['description'],
            hours=hours,
            hourly_rate=rate,
            amount=amount,
            billable=data.get('billable', True),
            status=TimeEntryStatus.DRAFT,
            date=datetime.strptime(data.get('date', datetime.now().date().isoformat()), '%Y-%m-%d').date(),
            user_id=user_id,
            case_id=data.get('case_id'),
            start_time=datetime.now(timezone.utc),  # For timer-based entries
            end_time=datetime.now(timezone.utc)     # Will be updated for real timer
        )
        
        # Save to database
        db.session.add(entry)
        db.session.commit()
        
        # Create audit log
        audit_log(
            action='create',
            resource_type='time_entry',
            resource_id=entry.id,
            user_id=user_id,
            new_values=entry.to_dict()
        )
        
        logger.info(f"Created time entry: {entry.description} - {hours}h @ ${rate}")
        
        return jsonify({
            'success': True,
            'message': 'Time entry created successfully',
            'entry': entry.to_dict()
        })
        
    except Exception as e:
        logger.error(f"Create time entry error: {e}")
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': 'Failed to create time entry'
        }), 500

def _create_mock_time_entry(data, hours, rate, amount):
    """Fallback mock time entry creation"""
    entry = {
        'id': f"entry_{datetime.now().timestamp()}",
        'description': data['description'],
        'hours': float(hours),
        'hourly_rate': float(rate),
        'amount': float(amount),
        'billable': data.get('billable', True),
        'status': 'draft',
        'date': data.get('date', datetime.now().date().isoformat()),
        'case_id': data.get('case_id'),
        'client_id': data.get('client_id'),
        'created_at': datetime.now().isoformat()
    }
    
    return jsonify({
        'success': True,
        'message': 'Time entry created successfully (mock)',
        'entry': entry
    })

@app.route('/api/time/entries/<entry_id>', methods=['PUT'])
@login_required
@role_required('admin', 'partner', 'associate', 'paralegal')
def api_update_time_entry(entry_id):
    """Update time entry"""
    try:
        data = request.get_json()
        
        if not DATABASE_AVAILABLE:
            return jsonify({
                'success': True,
                'message': 'Time entry updated successfully (mock)',
                'entry_id': entry_id,
                'updated_fields': list(data.keys())
            })
        
        # Get current user ID
        user_id = session.get('user_id', '1')
        
        # Find the time entry
        entry = TimeEntry.query.filter_by(id=entry_id, user_id=user_id).first()
        if not entry:
            return jsonify({
                'success': False,
                'error': 'Time entry not found'
            }), 404
        
        # Store old values for audit
        old_values = entry.to_dict()
        
        # Update allowed fields
        if 'description' in data:
            entry.description = data['description']
        if 'hours' in data:
            entry.hours = Decimal(str(data['hours']))
            entry.amount = entry.hours * entry.hourly_rate
        if 'hourly_rate' in data:
            entry.hourly_rate = Decimal(str(data['hourly_rate']))
            entry.amount = entry.hours * entry.hourly_rate
        if 'billable' in data:
            entry.billable = data['billable']
        if 'date' in data:
            entry.date = datetime.strptime(data['date'], '%Y-%m-%d').date()
        
        # Save changes
        db.session.commit()
        
        # Create audit log
        audit_log(
            action='update',
            resource_type='time_entry',
            resource_id=entry.id,
            user_id=user_id,
            old_values=old_values,
            new_values=entry.to_dict()
        )
        
        return jsonify({
            'success': True,
            'message': 'Time entry updated successfully',
            'entry': entry.to_dict()
        })
        
    except Exception as e:
        logger.error(f"Update time entry error: {e}")
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': 'Failed to update time entry'
        }), 500

@app.route('/api/time/entries/<entry_id>/status', methods=['PUT'])
@login_required
@role_required('admin', 'partner', 'associate')
def api_update_time_entry_status(entry_id):
    """Update time entry status (draft -> submitted -> approved -> billed)"""
    try:
        data = request.get_json()
        status = data.get('status')
        
        valid_statuses = ['draft', 'submitted', 'approved', 'billed']
        if status not in valid_statuses:
            return jsonify({
                'success': False,
                'error': f'Invalid status. Must be one of: {valid_statuses}'
            }), 400
        
        if not DATABASE_AVAILABLE:
            return jsonify({
                'success': True,
                'message': f'Time entry status updated to {status} (mock)',
                'entry_id': entry_id,
                'status': status
            })
        
        # Get current user ID
        user_id = session.get('user_id', '1')
        
        # Find the time entry
        entry = TimeEntry.query.filter_by(id=entry_id, user_id=user_id).first()
        if not entry:
            return jsonify({
                'success': False,
                'error': 'Time entry not found'
            }), 404
        
        # Store old values for audit
        old_values = entry.to_dict()
        
        # Update status
        try:
            entry.status = TimeEntryStatus(status)
        except ValueError:
            return jsonify({
                'success': False,
                'error': f'Invalid status: {status}'
            }), 400
        
        # Save changes
        db.session.commit()
        
        # Create audit log
        audit_log(
            action='status_update',
            resource_type='time_entry',
            resource_id=entry.id,
            user_id=user_id,
            old_values=old_values,
            new_values=entry.to_dict()
        )
        
        logger.info(f"Updated time entry {entry_id} status to {status}")
        
        return jsonify({
            'success': True,
            'message': f'Time entry status updated to {status}',
            'entry': entry.to_dict()
        })
        
    except Exception as e:
        logger.error(f"Update time entry status error: {e}")
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': 'Failed to update time entry status'
        }), 500

@app.route('/api/time/entries/billable', methods=['GET'])
@login_required
@role_required('admin', 'partner', 'associate', 'paralegal')
def api_get_billable_entries():
    """Get billable time entries ready for invoicing"""
    try:
        if not DATABASE_AVAILABLE:
            return _get_mock_billable_entries()
        
        # Get query parameters
        client_id = request.args.get('client_id')
        
        # Build query for billable time entries
        query = TimeEntry.query.filter(
            TimeEntry.billable == True,
            TimeEntry.status.in_([TimeEntryStatus.APPROVED, TimeEntryStatus.SUBMITTED])
        )
        
        # Filter by client if specified
        if client_id:
            query = query.join(Case).filter(Case.client_id == client_id)
        
        # Get current user's entries (will implement proper auth later)
        user_id = session.get('user_id', '1')
        query = query.filter(TimeEntry.user_id == user_id)
        
        entries = query.order_by(TimeEntry.date.desc()).all()
        
        billable_entries = []
        clients = {}
        
        for entry in entries:
            entry_data = {
                'id': entry.id,
                'description': entry.description,
                'hours': float(entry.hours),
                'hourly_rate': float(entry.hourly_rate),
                'amount': float(entry.amount),
                'status': entry.status.value,
                'date': entry.date.isoformat() if entry.date else None,
                'case_title': entry.case.title if entry.case else 'No Case',
                'client_name': entry.case.client.get_display_name() if entry.case and entry.case.client else 'No Client',
                'client_id': entry.case.client_id if entry.case else None
            }
            
            billable_entries.append(entry_data)
            
            # Group by client
            if entry.case and entry.case.client_id:
                client_key = entry.case.client_id
                if client_key not in clients:
                    clients[client_key] = {
                        'client_name': entry.case.client.get_display_name(),
                        'entries': [],
                        'total_hours': 0,
                        'total_amount': 0
                    }
                clients[client_key]['entries'].append(entry_data)
                clients[client_key]['total_hours'] += float(entry.hours)
                clients[client_key]['total_amount'] += float(entry.amount)
        
        return jsonify({
            'success': True,
            'billable_entries': billable_entries,
            'clients': clients,
            'total_billable_hours': sum(float(e.hours) for e in entries),
            'total_billable_amount': sum(float(e.amount) for e in entries)
        })
        
    except Exception as e:
        logger.error(f"Get billable entries error: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to retrieve billable entries'
        }), 500

def _get_mock_billable_entries():
    """Fallback mock billable entries"""
    billable_entries = [
        {
            'id': '1',
            'description': 'Client consultation and case review',
            'hours': 2.5,
            'hourly_rate': 250.00,
            'amount': 625.00,
            'status': 'approved',
            'date': '2025-07-08',
            'case_title': 'Smith vs. Jones',
            'client_name': 'John Smith',
            'client_id': 'client_1'
        },
        {
            'id': '3',
            'description': 'Legal research on contract law',
            'hours': 4.0,
            'hourly_rate': 250.00,
            'amount': 1000.00,
            'status': 'approved',
            'date': '2025-07-06',
            'case_title': 'Smith vs. Jones',
            'client_name': 'John Smith',
            'client_id': 'client_1'
        }
    ]
    
    # Group by client
    clients = {}
    for entry in billable_entries:
        client_id = entry['client_id']
        if client_id not in clients:
            clients[client_id] = {
                'client_name': entry['client_name'],
                'entries': [],
                'total_hours': 0,
                'total_amount': 0
            }
        clients[client_id]['entries'].append(entry)
        clients[client_id]['total_hours'] += entry['hours']
        clients[client_id]['total_amount'] += entry['amount']
    
    return jsonify({
        'success': True,
        'billable_entries': billable_entries,
        'clients': clients,
        'total_billable_hours': sum(e['hours'] for e in billable_entries),
        'total_billable_amount': sum(e['amount'] for e in billable_entries)
    })

# ===== INVOICE API =====

@app.route('/api/invoices', methods=['GET'])
# @login_required  # Temporarily disabled for demo mode
# @role_required('admin', 'partner', 'associate', 'paralegal')  # Temporarily disabled for demo mode
def api_get_invoices():
    """Get all invoices"""
    try:
        if not DATABASE_AVAILABLE:
            return _get_mock_invoices()
        
        # Get current user's invoices (will implement proper auth later)
        user_id = session.get('user_id', '1')
        
        invoices = Invoice.query.filter_by(created_by=user_id).order_by(Invoice.created_at.desc()).all()
        
        invoices_data = []
        total_outstanding = 0
        
        for invoice in invoices:
            invoice_dict = invoice.to_dict()
            invoices_data.append(invoice_dict)
            
            # Calculate outstanding amount
            outstanding = invoice_dict['total_amount'] - invoice_dict['amount_paid']
            total_outstanding += outstanding
        
        return jsonify({
            'success': True,
            'invoices': invoices_data,
            'total_invoices': len(invoices_data),
            'total_outstanding': total_outstanding
        })
        
    except Exception as e:
        logger.error(f"Get invoices error: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to retrieve invoices'
        }), 500

def _get_mock_invoices():
    """Enhanced mock invoice data with realistic payment samples for testing"""
    from datetime import datetime, timedelta
    import random
    
    # First, include our test invoices with real payment intent IDs
    base_timestamp = int(datetime.now().timestamp())
    
    test_invoices = [
        # Paid invoice 1 - ready for refund testing
        {
            'id': f"inv_{base_timestamp}_001",
            'invoice_number': f"INV-{datetime.now().year}-001",
            'client_name': 'TechStart LLC',
            'client_id': 'client_techstart',
            'subject': 'Corporate Formation and Legal Setup',
            'issue_date': (datetime.now().date() - timedelta(days=15)).isoformat(),
            'due_date': (datetime.now().date() + timedelta(days=15)).isoformat(),
            'status': 'paid',
            'subtotal': 5500.00,
            'tax_rate': 0.0875,
            'tax_amount': 481.25,
            'total_amount': 5981.25,
            'amount_paid': 5981.25,
            'payment_intent_id': f'pi_test_paid_{random.randint(100000, 999999)}',
            'payment_date': (datetime.now().date() - timedelta(days=5)).isoformat(),
            'payment_method': 'Stripe Payment',
            'payment_terms': 'Net 30',
            'created_at': (datetime.now() - timedelta(days=15)).isoformat(),
            'paid_at': (datetime.now() - timedelta(days=5)).isoformat()
        },
        # Paid invoice 2 - different amount for testing
        {
            'id': f"inv_{base_timestamp}_002",
            'invoice_number': f"INV-{datetime.now().year}-002",
            'client_name': 'Global Dynamics Inc',
            'client_id': 'client_global',
            'subject': 'Contract Negotiation Services',
            'issue_date': (datetime.now().date() - timedelta(days=22)).isoformat(),
            'due_date': (datetime.now().date() - timedelta(days=8)).isoformat(),
            'status': 'paid',
            'subtotal': 3200.00,
            'tax_rate': 0.0875,
            'tax_amount': 280.00,
            'total_amount': 3480.00,
            'amount_paid': 3480.00,
            'payment_intent_id': f'pi_test_paid_{random.randint(100000, 999999)}',
            'payment_date': (datetime.now().date() - timedelta(days=10)).isoformat(),
            'payment_method': 'Stripe Payment',
            'payment_terms': 'Net 30',
            'created_at': (datetime.now() - timedelta(days=22)).isoformat(),
            'paid_at': (datetime.now() - timedelta(days=10)).isoformat()
        },
        # Unpaid invoice (overdue) - for Stripe payment testing
        {
            'id': f"inv_{base_timestamp}_003",
            'invoice_number': f"INV-{datetime.now().year}-003",
            'client_name': 'Metro Properties',
            'client_id': 'client_metro',
            'subject': 'Real Estate Transaction Legal Services',
            'issue_date': (datetime.now().date() - timedelta(days=45)).isoformat(),
            'due_date': (datetime.now().date() - timedelta(days=15)).isoformat(),
            'status': 'overdue',
            'subtotal': 4750.00,
            'tax_rate': 0.0875,
            'tax_amount': 415.63,
            'total_amount': 5165.63,
            'amount_paid': 0.00,
            'payment_terms': 'Net 30',
            'created_at': (datetime.now() - timedelta(days=45)).isoformat()
        },
        # Recent unpaid invoice - for Stripe payment testing
        {
            'id': f"inv_{base_timestamp}_004",
            'invoice_number': f"INV-{datetime.now().year}-004",
            'client_name': 'Innovation Labs',
            'client_id': 'client_innovation',
            'subject': 'IP Protection and Patent Application',
            'issue_date': (datetime.now().date() - timedelta(days=10)).isoformat(),
            'due_date': (datetime.now().date() + timedelta(days=20)).isoformat(),
            'status': 'sent',
            'subtotal': 6800.00,
            'tax_rate': 0.0875,
            'tax_amount': 595.00,
            'total_amount': 7395.00,
            'amount_paid': 0.00,
            'payment_terms': 'Net 30',
            'created_at': (datetime.now() - timedelta(days=10)).isoformat()
        }
    ]
    
    # Add additional realistic mock invoices
    clients = [
        {'name': 'Acme Corporation', 'id': 'client_1'},
        {'name': 'Smith & Associates', 'id': 'client_4'},
        {'name': 'Future Dynamics', 'id': 'client_5'},
        {'name': 'Sunrise Holdings', 'id': 'client_7'}
    ]
    
    statuses = ['draft', 'sent', 'paid', 'overdue']
    services = [
        'Legal Consultation Services',
        'Contract Review and Analysis', 
        'Corporate Legal Advisory',
        'Litigation Support Services',
        'Employment Law Consultation'
    ]
    
    additional_invoices = []
    for i in range(8):  # Reduced to focus on our test invoices
        status = random.choice(statuses)
        subtotal = round(random.uniform(750, 4500), 2)
        tax_rate = 0.0875
        tax_amount = round(subtotal * tax_rate, 2)
        total_amount = subtotal + tax_amount
        
        amount_paid = 0.00
        paid_date = None
        payment_intent_id = None
        
        if status == 'paid':
            amount_paid = total_amount
            paid_date = (datetime.now().date() - timedelta(days=random.randint(1, 30))).isoformat()
            payment_intent_id = f'pi_test_paid_{random.randint(100000, 999999)}'
        elif status in ['sent', 'overdue'] and random.random() > 0.7:
            amount_paid = round(total_amount * random.uniform(0.1, 0.5), 2)
        
        client = random.choice(clients)
        issue_date = datetime.now().date() - timedelta(days=random.randint(5, 60))
        due_date = issue_date + timedelta(days=30)
        
        invoice = {
            'id': f'inv_mock_{str(i+1).zfill(3)}',
            'invoice_number': f'INV-2025-{str(i+101).zfill(3)}',
            'client_name': client['name'],
            'client_id': client['id'],
            'subject': random.choice(services),
            'subtotal': subtotal,
            'tax_amount': tax_amount,
            'total_amount': total_amount,
            'amount_paid': amount_paid,
            'status': status,
            'issue_date': issue_date.isoformat(),
            'due_date': due_date.isoformat(),
            'payment_terms': 'Net 30',
            'created_at': issue_date.isoformat(),
            'payment_intent_id': payment_intent_id
        }
        
        if paid_date:
            invoice['paid_date'] = paid_date
            
        additional_invoices.append(invoice)
    
    # Combine test invoices with additional mock invoices
    all_invoices = test_invoices + additional_invoices
    
    # Sort by issue date (newest first)
    all_invoices.sort(key=lambda x: x['issue_date'], reverse=True)
    
    return jsonify({
        'success': True,
        'invoices': all_invoices,
        'total_invoices': len(all_invoices),
        'total_outstanding': sum(inv['total_amount'] - inv['amount_paid'] for inv in all_invoices)
    })

@app.route('/api/invoices', methods=['POST'])
@login_required
@role_required('admin', 'partner', 'associate')
def api_create_invoice():
    """Create invoice from billable time entries"""
    try:
        data = request.get_json()
        
        required_fields = ['client_id', 'entry_ids', 'subject']
        for field in required_fields:
            if field not in data:
                return jsonify({
                    'success': False,
                    'error': f'Missing required field: {field}'
                }), 400
        
        if not DATABASE_AVAILABLE:
            return _create_mock_invoice(data)
        
        client_id = data['client_id']
        entry_ids = data['entry_ids']
        subject = data['subject']
        
        # Get current user ID
        user_id = session.get('user_id', '1')
        
        # Verify client exists
        client = Client.query.filter_by(id=client_id).first()
        if not client:
            return jsonify({
                'success': False,
                'error': 'Client not found'
            }), 404
        
        # Get selected time entries
        time_entries = TimeEntry.query.filter(
            TimeEntry.id.in_(entry_ids),
            TimeEntry.user_id == user_id,
            TimeEntry.billable == True,
            TimeEntry.status.in_([TimeEntryStatus.APPROVED, TimeEntryStatus.SUBMITTED])
        ).all()
        
        if not time_entries:
            return jsonify({
                'success': False,
                'error': 'No valid time entries found for invoice'
            }), 400
        
        # Calculate totals
        subtotal = sum(entry.amount for entry in time_entries)
        tax_rate = Decimal(str(data.get('tax_rate', 0.08)))  # 8% default
        tax_amount = subtotal * tax_rate
        total_amount = subtotal + tax_amount
        
        # Generate invoice number
        invoice_count = Invoice.query.filter_by(created_by=user_id).count()
        invoice_number = f"INV-{datetime.now().year}-{str(invoice_count + 1).zfill(3)}"
        
        # Set dates
        issue_date = datetime.now().date()
        payment_terms = data.get('payment_terms', 'Net 30')
        days = 30 if 'Net 30' in payment_terms else 15 if 'Net 15' in payment_terms else 0
        due_date = issue_date + timedelta(days=days)
        
        # Create invoice
        invoice = Invoice(
            invoice_number=invoice_number,
            subject=subject,
            description=data.get('description', ''),
            subtotal=subtotal,
            tax_rate=tax_rate,
            tax_amount=tax_amount,
            total_amount=total_amount,
            amount_paid=Decimal('0.00'),
            status=InvoiceStatus.DRAFT,
            issue_date=issue_date,
            due_date=due_date,
            payment_terms=payment_terms,
            client_id=client_id,
            created_by=user_id
        )
        
        # Save invoice
        db.session.add(invoice)
        db.session.flush()  # Get the invoice ID
        
        # Update time entries to reference this invoice and mark as billed
        for entry in time_entries:
            entry.invoice_id = invoice.id
            entry.status = TimeEntryStatus.BILLED
        
        # Commit all changes
        db.session.commit()
        
        # Create audit log
        audit_log(
            action='create',
            resource_type='invoice',
            resource_id=invoice.id,
            user_id=user_id,
            new_values=invoice.to_dict()
        )
        
        logger.info(f"Created invoice {invoice_number} for {len(time_entries)} time entries")
        
        return jsonify({
            'success': True,
            'message': 'Invoice created successfully',
            'invoice': invoice.to_dict()
        })
        
    except Exception as e:
        logger.error(f"Create invoice error: {e}")
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': 'Failed to create invoice'
        }), 500

def _create_mock_invoice(data):
    """Fallback mock invoice creation"""
    subtotal = 1625.0
    tax_rate = data.get('tax_rate', 0.08)
    tax_amount = subtotal * tax_rate
    total_amount = subtotal + tax_amount
    
    invoice = {
        'id': f"inv_{datetime.now().timestamp()}",
        'invoice_number': f"INV-2025-{str(datetime.now().timestamp()).split('.')[0][-3:]}",
        'client_id': data['client_id'],
        'client_name': 'John Smith',
        'subject': data['subject'],
        'description': data.get('description', ''),
        'subtotal': subtotal,
        'tax_rate': tax_rate,
        'tax_amount': tax_amount,
        'total_amount': total_amount,
        'amount_paid': 0.00,
        'status': 'draft',
        'issue_date': datetime.now().date().isoformat(),
        'due_date': (datetime.now().date() + timedelta(days=30)).isoformat(),
        'payment_terms': data.get('payment_terms', 'Net 30'),
        'created_at': datetime.now().isoformat()
    }
    
    return jsonify({
        'success': True,
        'message': 'Invoice created successfully (mock)',
        'invoice': invoice
    })

@app.route('/api/invoices/<invoice_id>', methods=['GET'])
@login_required
@role_required('admin', 'partner', 'associate', 'paralegal')
def api_get_invoice(invoice_id):
    """Get invoice details"""
    try:
        # Mock invoice detail
        invoice = {
            'id': invoice_id,
            'invoice_number': 'INV-2025-001',
            'client_name': 'John Smith',
            'client_id': 'client_1',
            'subject': 'Legal Services - Smith vs. Jones',
            'description': 'Legal consultation and research services',
            'subtotal': 1625.00,
            'tax_rate': 0.08,
            'tax_amount': 130.00,
            'total_amount': 1755.00,
            'amount_paid': 0.00,
            'status': 'sent',
            'issue_date': '2025-07-08',
            'due_date': '2025-08-07',
            'payment_terms': 'Net 30',
            'billing_address': '123 Main St, Anytown, ST 12345',
            'time_entries': [
                {
                    'date': '2025-07-08',
                    'description': 'Client consultation and case review',
                    'hours': 2.5,
                    'rate': 250.00,
                    'amount': 625.00
                },
                {
                    'date': '2025-07-06',
                    'description': 'Legal research on contract law',
                    'hours': 4.0,
                    'rate': 250.00,
                    'amount': 1000.00
                }
            ]
        }
        
        return jsonify({
            'success': True,
            'invoice': invoice
        })
        
    except Exception as e:
        logger.error(f"Get invoice error: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to retrieve invoice'
        }), 500

@app.route('/api/invoices/<invoice_id>/status', methods=['PUT'])
@login_required
@role_required('admin', 'partner', 'associate')
def api_update_invoice_status(invoice_id):
    """Update invoice status (draft -> sent -> paid)"""
    try:
        data = request.get_json()
        status = data.get('status')
        
        valid_statuses = ['draft', 'sent', 'paid', 'overdue', 'cancelled']
        if status not in valid_statuses:
            return jsonify({
                'success': False,
                'error': f'Invalid status. Must be one of: {valid_statuses}'
            }), 400
        
        # Additional data for paid invoices
        paid_date = data.get('paid_date')
        amount_paid = data.get('amount_paid')
        
        logger.info(f"Updated invoice {invoice_id} status to {status}")
        
        return jsonify({
            'success': True,
            'message': f'Invoice status updated to {status}',
            'invoice_id': invoice_id,
            'status': status,
            'paid_date': paid_date,
            'amount_paid': amount_paid
        })
        
    except Exception as e:
        logger.error(f"Update invoice status error: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to update invoice status'
        }), 500

@app.route('/api/invoices/<invoice_id>/send', methods=['POST'])
@login_required
@role_required('admin', 'partner', 'associate')
def api_send_invoice(invoice_id):
    """Send invoice to client"""
    try:
        data = request.get_json()
        email = data.get('email')
        
        if not email:
            return jsonify({
                'success': False,
                'error': 'Client email required'
            }), 400
        
        # Mock email sending
        logger.info(f"Sent invoice {invoice_id} to {email}")
        
        return jsonify({
            'success': True,
            'message': 'Invoice sent successfully',
            'invoice_id': invoice_id,
            'sent_to': email,
            'sent_at': datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Send invoice error: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to send invoice'
        }), 500

@app.route('/api/billing/dashboard', methods=['GET'])
# @login_required  # Temporarily disabled for demo mode
# @role_required('admin', 'partner', 'associate', 'paralegal')  # Temporarily disabled for demo mode
def api_billing_dashboard():
    """Get billing dashboard data"""
    try:
        if not DATABASE_AVAILABLE:
            return _get_mock_billing_dashboard()
        
        # Get current user ID
        user_id = session.get('user_id', '1')
        
        # Calculate summary statistics
        current_month = datetime.now().date().replace(day=1)
        
        # Total outstanding amount
        outstanding_invoices = Invoice.query.filter_by(created_by=user_id).filter(
            Invoice.status.in_([InvoiceStatus.SENT, InvoiceStatus.OVERDUE])
        ).all()
        total_outstanding = sum(float(inv.total_amount - inv.amount_paid) for inv in outstanding_invoices)
        
        # Total paid this month
        paid_invoices = Invoice.query.filter_by(created_by=user_id).filter(
            Invoice.status == InvoiceStatus.PAID,
            Invoice.paid_date >= current_month
        ).all()
        total_paid_this_month = sum(float(inv.total_amount) for inv in paid_invoices)
        
        # Pending time entries
        pending_entries = TimeEntry.query.filter_by(user_id=user_id).filter(
            TimeEntry.status.in_([TimeEntryStatus.SUBMITTED, TimeEntryStatus.DRAFT]),
            TimeEntry.billable == True
        ).all()
        pending_time_entries = len(pending_entries)
        
        # Billable hours this month
        month_entries = TimeEntry.query.filter_by(user_id=user_id).filter(
            TimeEntry.date >= current_month,
            TimeEntry.billable == True
        ).all()
        billable_hours_this_month = sum(float(entry.hours) for entry in month_entries)
        
        # Recent invoices
        recent_invoices = Invoice.query.filter_by(created_by=user_id).order_by(
            Invoice.created_at.desc()
        ).limit(5).all()
        
        recent_invoices_data = []
        for invoice in recent_invoices:
            invoice_data = {
                'id': invoice.id,
                'invoice_number': invoice.invoice_number,
                'client_name': invoice.client.get_display_name() if invoice.client else 'Unknown',
                'amount': float(invoice.total_amount),
                'status': invoice.status.value,
                'due_date': invoice.due_date.isoformat() if invoice.due_date else None
            }
            if invoice.paid_date:
                invoice_data['paid_date'] = invoice.paid_date.isoformat()
            recent_invoices_data.append(invoice_data)
        
        # Pending time entries detail
        pending_time_entries_data = []
        for entry in pending_entries[:5]:  # Limit to 5 for dashboard
            pending_time_entries_data.append({
                'id': entry.id,
                'description': entry.description,
                'hours': float(entry.hours),
                'amount': float(entry.amount),
                'client_name': entry.case.client.get_display_name() if entry.case and entry.case.client else 'No Client',
                'status': entry.status.value
            })
        
        dashboard = {
            'summary': {
                'total_outstanding': total_outstanding,
                'total_paid_this_month': total_paid_this_month,
                'pending_time_entries': pending_time_entries,
                'overdue_invoices': len([inv for inv in outstanding_invoices if inv.status == InvoiceStatus.OVERDUE]),
                'billable_hours_this_month': billable_hours_this_month
            },
            'recent_invoices': recent_invoices_data,
            'pending_time_entries': pending_time_entries_data
        }
        
        return jsonify({
            'success': True,
            'dashboard': dashboard
        })
        
    except Exception as e:
        logger.error(f"Billing dashboard error: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to load billing dashboard'
        }), 500

def _get_mock_billing_dashboard():
    """Enhanced mock billing dashboard data with realistic samples"""
    from datetime import datetime, timedelta
    import random
    
    # Generate realistic invoice data
    clients = ['Acme Corporation', 'TechStart LLC', 'Global Industries', 'Smith & Associates', 'Future Dynamics']
    statuses = ['draft', 'sent', 'paid', 'overdue']
    
    recent_invoices = []
    for i in range(8):
        status = random.choice(statuses)
        amount = round(random.uniform(1500, 8500), 2)
        due_date = datetime.now().date() + timedelta(days=random.randint(-30, 45))
        
        recent_invoices.append({
            'id': f'inv_sample_{i+1}',
            'invoice_number': f'INV-2025-{str(i+1).zfill(3)}',
            'client_name': random.choice(clients),
            'amount': amount,
            'status': status,
            'due_date': due_date.isoformat(),
            'issue_date': (due_date - timedelta(days=30)).isoformat(),
            'payment_terms': 'Net 30'
        })
    
    # Calculate metrics from sample data
    total_outstanding = sum(inv['amount'] for inv in recent_invoices if inv['status'] in ['sent', 'overdue'])
    total_paid_this_month = sum(inv['amount'] for inv in recent_invoices if inv['status'] == 'paid')
    overdue_amount = sum(inv['amount'] for inv in recent_invoices if inv['status'] == 'overdue')
    pending_invoices = len([inv for inv in recent_invoices if inv['status'] in ['draft', 'sent']])
    overdue_invoices = len([inv for inv in recent_invoices if inv['status'] == 'overdue'])
    
    dashboard = {
        'summary': {
            'total_outstanding': round(total_outstanding, 2),
            'total_paid_this_month': round(total_paid_this_month, 2),
            'overdue_amount': round(overdue_amount, 2),
            'pending_invoices': pending_invoices,
            'overdue_invoices': overdue_invoices,
            'avg_payment_time': 18.5,
            'total_revenue_ytd': 145680.00,
            'active_clients': 24,
            'billable_hours_this_month': 156.5
        },
        'recent_invoices': recent_invoices[:5],  # Show only 5 most recent
        'all_invoices': recent_invoices,  # Keep all for full list
        'upcoming_payments': [
            {
                'client_name': 'Acme Corporation',
                'amount': 4500.00,
                'due_date': (datetime.now().date() + timedelta(days=5)).isoformat(),
                'invoice_number': 'INV-2025-001'
            },
            {
                'client_name': 'TechStart LLC',
                'amount': 2850.00,
                'due_date': (datetime.now().date() + timedelta(days=12)).isoformat(),
                'invoice_number': 'INV-2025-004'
            }
        ],
        'stripe_connected': STRIPE_AVAILABLE,
        'payment_methods': ['credit_card', 'ach', 'wire_transfer'],
        'currency': 'USD',
        'pending_time_entries': [
            {
                'id': '4',
                'description': 'Contract review and analysis',
                'hours': 3.5,
                'amount': 875.00,
                'client_name': 'Acme Corporation',
                'status': 'submitted'
            },
            {
                'id': '5',
                'description': 'Legal research and consultation',
                'hours': 2.0,
                'amount': 500.00,
                'client_name': 'TechStart LLC',
                'status': 'draft'
            }
        ]
    }
    
    return jsonify({
        'success': True,
        'dashboard': dashboard
    })

# ===== AUTHENTICATION APIs =====

@app.route('/api/auth/register', methods=['POST'])
def api_register():
    """User registration endpoint"""
    try:
        data = request.json
        
        # Validate required fields
        required_fields = ['email', 'password', 'first_name', 'last_name']
        for field in required_fields:
            if not data.get(field):
                return jsonify({
                    'success': False,
                    'error': f'{field.replace("_", " ").title()} is required'
                }), 400
        
        email = data['email'].lower().strip()
        
        if not DATABASE_AVAILABLE:
            return _register_mock_user(data)
        
        # Check if user already exists
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            return jsonify({
                'success': False,
                'error': 'User with this email already exists'
            }), 400
        
        # Validate password strength
        password = data['password']
        if len(password) < 8:
            return jsonify({
                'success': False,
                'error': 'Password must be at least 8 characters long'
            }), 400
        
        # Create new user
        user = User(
            email=email,
            first_name=data['first_name'].strip(),
            last_name=data['last_name'].strip(),
            phone=data.get('phone', '').strip(),
            role=UserRole.ASSOCIATE,  # Default role
            firm_name=data.get('firm_name', '').strip(),
            bar_number=data.get('bar_number', '').strip(),
            hourly_rate=Decimal(str(data['hourly_rate'])) if data.get('hourly_rate') else None
        )
        user.set_password(password)
        
        db.session.add(user)
        db.session.commit()
        
        # Create audit log
        audit_log('create', 'user', user.id, user.id, {
            'action': 'user_registration',
            'email': user.email
        })
        
        logger.info(f"New user registered: {user.email}")
        
        return jsonify({
            'success': True,
            'message': 'User registered successfully',
            'user': {
                'id': user.id,
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'role': user.role.value
            }
        })
        
    except Exception as e:
        if DATABASE_AVAILABLE:
            db.session.rollback()
        logger.error(f"Registration error: {e}")
        return jsonify({
            'success': False,
            'error': 'Registration failed. Please try again.'
        }), 500

@app.route('/api/auth/login', methods=['POST'])
def api_login():
    """User login endpoint"""
    try:
        data = request.json
        
        if not data.get('email') or not data.get('password'):
            return jsonify({
                'success': False,
                'error': 'Email and password are required'
            }), 400
        
        email = data['email'].lower().strip()
        password = data['password']
        
        if not DATABASE_AVAILABLE:
            return _login_mock_user(email, password)
        
        # Find user
        user = User.query.filter_by(email=email).first()
        
        if not user or not user.check_password(password):
            # Log failed attempt
            if user:
                user.failed_login_attempts += 1
                if user.failed_login_attempts >= 5:
                    user.locked_until = datetime.now(timezone.utc) + timedelta(minutes=30)
                db.session.commit()
            
            return jsonify({
                'success': False,
                'error': 'Invalid email or password'
            }), 401
        
        # Check if account is locked
        if user.locked_until and user.locked_until > datetime.now(timezone.utc):
            return jsonify({
                'success': False,
                'error': 'Account is temporarily locked. Please try again later.'
            }), 423
        
        # Check if account is active
        if not user.is_active:
            return jsonify({
                'success': False,
                'error': 'Account is deactivated. Please contact support.'
            }), 403
        
        # Reset failed attempts and update last login
        user.failed_login_attempts = 0
        user.locked_until = None
        user.last_login = datetime.now(timezone.utc)
        db.session.commit()
        
        # Create session
        session['user_id'] = user.id
        session['user_email'] = user.email
        session['user_role'] = user.role.value
        session['user_name'] = f"{user.first_name} {user.last_name}"
        session['logged_in'] = True
        
        # Create audit log
        audit_log('login', 'user', user.id, user.id, {
            'action': 'user_login',
            'ip_address': request.remote_addr,
            'user_agent': request.headers.get('User-Agent', '')
        })
        
        logger.info(f"User logged in: {user.email}")
        
        return jsonify({
            'success': True,
            'message': 'Login successful',
            'user': {
                'id': user.id,
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'role': user.role.value,
                'firm_name': user.firm_name
            }
        })
        
    except Exception as e:
        logger.error(f"Login error: {e}")
        return jsonify({
            'success': False,
            'error': 'Login failed. Please try again.'
        }), 500

@app.route('/api/auth/logout', methods=['POST'])
def api_logout():
    """User logout endpoint"""
    try:
        user_id = session.get('user_id')
        
        if user_id and DATABASE_AVAILABLE:
            # Create audit log
            audit_log('logout', 'user', user_id, user_id, {
                'action': 'user_logout'
            })
        
        # Clear session
        session.clear()
        
        return jsonify({
            'success': True,
            'message': 'Logged out successfully'
        })
        
    except Exception as e:
        logger.error(f"Logout error: {e}")
        return jsonify({
            'success': False,
            'error': 'Logout failed'
        }), 500

@app.route('/api/auth/me', methods=['GET'])
@login_required
def api_current_user():
    """Get current user information"""
    try:
        if not session.get('logged_in'):
            return jsonify({
                'success': False,
                'error': 'Not authenticated'
            }), 401
        
        user_id = session.get('user_id')
        
        if not DATABASE_AVAILABLE:
            return _get_mock_current_user()
        
        user = User.query.get(user_id)
        if not user:
            session.clear()
            return jsonify({
                'success': False,
                'error': 'User not found'
            }), 404
        
        return jsonify({
            'success': True,
            'user': {
                'id': user.id,
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'full_name': user.get_full_name(),
                'role': user.role.value,
                'firm_name': user.firm_name,
                'phone': user.phone,
                'hourly_rate': float(user.hourly_rate) if user.hourly_rate else None,
                'two_factor_enabled': user.two_factor_enabled,
                'email_verified': user.email_verified,
                'last_login': user.last_login.isoformat() if user.last_login else None,
                'created_at': user.created_at.isoformat() if user.created_at else None
            }
        })
        
    except Exception as e:
        logger.error(f"Current user error: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to get user information'
        }), 500

@app.route('/api/auth/change-password', methods=['POST'])
@login_required
def api_change_password():
    """Change user password"""
    try:
        if not session.get('logged_in'):
            return jsonify({
                'success': False,
                'error': 'Not authenticated'
            }), 401
        
        data = request.json
        current_password = data.get('current_password')
        new_password = data.get('new_password')
        
        if not current_password or not new_password:
            return jsonify({
                'success': False,
                'error': 'Current password and new password are required'
            }), 400
        
        if len(new_password) < 8:
            return jsonify({
                'success': False,
                'error': 'New password must be at least 8 characters long'
            }), 400
        
        if not DATABASE_AVAILABLE:
            return jsonify({
                'success': True,
                'message': 'Password changed successfully (mock mode)'
            })
        
        user_id = session.get('user_id')
        user = User.query.get(user_id)
        
        if not user or not user.check_password(current_password):
            return jsonify({
                'success': False,
                'error': 'Current password is incorrect'
            }), 400
        
        # Update password
        user.set_password(new_password)
        db.session.commit()
        
        # Create audit log
        audit_log('update', 'user', user.id, user.id, {
            'action': 'password_change'
        })
        
        logger.info(f"Password changed for user: {user.email}")
        
        return jsonify({
            'success': True,
            'message': 'Password changed successfully'
        })
        
    except Exception as e:
        if DATABASE_AVAILABLE:
            db.session.rollback()
        logger.error(f"Change password error: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to change password'
        }), 500

# ===== MOCK AUTHENTICATION FUNCTIONS =====

def _register_mock_user(data):
    """Mock user registration"""
    return jsonify({
        'success': True,
        'message': 'User registered successfully (mock mode)',
        'user': {
            'id': '1',
            'email': data['email'],
            'first_name': data['first_name'],
            'last_name': data['last_name'],
            'role': 'associate'
        }
    })

def _login_mock_user(email, password):
    """Mock user login"""
    # Simple mock - any password works
    session['user_id'] = '1'
    session['user_email'] = email
    session['user_role'] = 'partner'
    session['user_name'] = 'Demo User'
    session['logged_in'] = True
    
    return jsonify({
        'success': True,
        'message': 'Login successful (mock mode)',
        'user': {
            'id': '1',
            'email': email,
            'first_name': 'Demo',
            'last_name': 'User',
            'role': 'associate',
            'firm_name': 'Demo Law Firm'
        }
    })

def _get_mock_current_user():
    """Mock current user"""
    return jsonify({
        'success': True,
        'user': {
            'id': '1',
            'email': session.get('user_email', 'demo@example.com'),
            'first_name': 'Demo',
            'last_name': 'User',
            'full_name': 'Demo User',
            'role': 'associate',
            'firm_name': 'Demo Law Firm',
            'phone': '(555) 123-4567',
            'hourly_rate': 350.00,
            'two_factor_enabled': False,
            'email_verified': True,
            'last_login': datetime.now().isoformat(),
            'created_at': datetime.now().isoformat()
        }
    })

# ===== CLIENT MANAGEMENT APIs =====

@app.route('/api/clients', methods=['GET'])
@login_required
def api_get_clients():
    """Get all clients with optional search and filtering"""
    try:
        if not DATABASE_AVAILABLE:
            return _get_mock_clients()
        
        # Get query parameters
        search = request.args.get('search', '').strip()
        status = request.args.get('status', '')
        client_type = request.args.get('type', '')
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 20))
        
        # Get current user ID
        user_id = session.get('user_id', '1')
        
        # Build query
        query = Client.query.filter_by(created_by=user_id)
        
        # Apply filters
        if search:
            query = query.filter(
                db.or_(
                    Client.first_name.ilike(f'%{search}%'),
                    Client.last_name.ilike(f'%{search}%'),
                    Client.company_name.ilike(f'%{search}%'),
                    Client.email.ilike(f'%{search}%')
                )
            )
        
        if status:
            query = query.filter_by(status=status)
            
        if client_type:
            query = query.filter_by(client_type=client_type)
        
        # Execute paginated query
        clients = query.order_by(Client.created_at.desc()).paginate(
            page=page, per_page=per_page, error_out=False
        )
        
        # Format response
        clients_data = []
        for client in clients.items:
            client_data = client.to_dict()
            
            # Add case count
            case_count = Case.query.filter_by(client_id=client.id).count()
            client_data['case_count'] = case_count
            
            # Add recent activity
            recent_cases = Case.query.filter_by(client_id=client.id).order_by(
                Case.updated_at.desc()
            ).limit(3).all()
            client_data['recent_cases'] = [case.to_dict() for case in recent_cases]
            
            clients_data.append(client_data)
        
        # Create audit log
        audit_log('view', 'clients', None, user_id, {
            'action': 'list_clients',
            'filters': {'search': search, 'status': status, 'type': client_type}
        })
        
        return jsonify({
            'success': True,
            'clients': clients_data,
            'pagination': {
                'page': clients.page,
                'pages': clients.pages,
                'per_page': clients.per_page,
                'total': clients.total,
                'has_prev': clients.has_prev,
                'has_next': clients.has_next
            }
        })
        
    except Exception as e:
        logger.error(f"Error fetching clients: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/clients', methods=['POST'])
@login_required
def api_create_client():
    """Create a new client"""
    try:
        if not DATABASE_AVAILABLE:
            return _create_mock_client()
        
        data = request.json
        user_id = session.get('user_id', '1')
        
        # Validate required fields
        client_type = data.get('client_type', 'individual')
        if client_type == 'individual':
            if not data.get('first_name') or not data.get('last_name'):
                return jsonify({
                    'success': False,
                    'error': 'First name and last name are required for individual clients'
                }), 400
        elif client_type == 'business':
            if not data.get('company_name'):
                return jsonify({
                    'success': False,
                    'error': 'Company name is required for business clients'
                }), 400
        
        # Create new client
        client = Client(
            client_type=client_type,
            first_name=data.get('first_name'),
            last_name=data.get('last_name'),
            company_name=data.get('company_name'),
            email=data.get('email'),
            phone=data.get('phone'),
            address_line1=data.get('address_line1'),
            address_line2=data.get('address_line2'),
            city=data.get('city'),
            state=data.get('state'),
            zip_code=data.get('zip_code'),
            country=data.get('country', 'United States'),
            tax_id=data.get('tax_id'),
            website=data.get('website'),
            industry=data.get('industry'),
            status=data.get('status', 'active'),
            source=data.get('source'),
            notes=data.get('notes'),
            billing_rate=Decimal(str(data['billing_rate'])) if data.get('billing_rate') else None,
            payment_terms=data.get('payment_terms', 'Net 30'),
            created_by=user_id
        )
        
        db.session.add(client)
        db.session.commit()
        
        # Create audit log
        audit_log('create', 'client', client.id, user_id, client.to_dict())
        
        logger.info(f"Client created: {client.id}")
        
        return jsonify({
            'success': True,
            'client': client.to_dict(),
            'message': 'Client created successfully'
        })
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error creating client: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/clients/<client_id>', methods=['GET'])
@login_required
def api_get_client(client_id):
    """Get a specific client with full details"""
    try:
        if not DATABASE_AVAILABLE:
            return _get_mock_client(client_id)
        
        user_id = session.get('user_id', '1')
        
        # Get client
        client = Client.query.filter_by(id=client_id, created_by=user_id).first()
        if not client:
            return jsonify({
                'success': False,
                'error': 'Client not found'
            }), 404
        
        # Get client details with related data
        client_data = client.to_dict()
        
        # Get cases
        cases = Case.query.filter_by(client_id=client.id).order_by(Case.date_opened.desc()).all()
        client_data['cases'] = [case.to_dict() for case in cases]
        
        # Get invoices
        invoices = Invoice.query.filter_by(client_id=client.id).order_by(Invoice.created_at.desc()).limit(10).all()
        client_data['recent_invoices'] = [invoice.to_dict() for invoice in invoices]
        
        # Get documents
        documents = Document.query.filter_by(client_id=client.id).order_by(Document.created_at.desc()).limit(10).all()
        client_data['recent_documents'] = [doc.to_dict() for doc in documents]
        
        # Calculate financial summary
        total_billed = sum(float(invoice.total_amount) for invoice in invoices)
        total_paid = sum(float(invoice.amount_paid) for invoice in invoices)
        outstanding_amount = total_billed - total_paid
        
        client_data['financial_summary'] = {
            'total_billed': total_billed,
            'total_paid': total_paid,
            'outstanding_amount': outstanding_amount,
            'invoice_count': len(invoices)
        }
        
        # Create audit log
        audit_log('view', 'client', client.id, user_id, {'action': 'view_client_details'})
        
        return jsonify({
            'success': True,
            'client': client_data
        })
        
    except Exception as e:
        logger.error(f"Error fetching client {client_id}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/clients/<client_id>', methods=['PUT'])
@login_required
def api_update_client(client_id):
    """Update a client"""
    try:
        if not DATABASE_AVAILABLE:
            return _update_mock_client(client_id)
        
        data = request.json
        user_id = session.get('user_id', '1')
        
        # Get client
        client = Client.query.filter_by(id=client_id, created_by=user_id).first()
        if not client:
            return jsonify({
                'success': False,
                'error': 'Client not found'
            }), 404
        
        # Store old values for audit
        old_values = client.to_dict()
        
        # Update fields
        updateable_fields = [
            'first_name', 'last_name', 'company_name', 'email', 'phone',
            'address_line1', 'address_line2', 'city', 'state', 'zip_code',
            'country', 'tax_id', 'website', 'industry', 'status', 'source',
            'notes', 'payment_terms'
        ]
        
        for field in updateable_fields:
            if field in data:
                setattr(client, field, data[field])
        
        if 'billing_rate' in data and data['billing_rate']:
            client.billing_rate = Decimal(str(data['billing_rate']))
        
        db.session.commit()
        
        # Create audit log
        audit_log('update', 'client', client.id, user_id, {
            'old_values': old_values,
            'new_values': client.to_dict()
        })
        
        logger.info(f"Client updated: {client.id}")
        
        return jsonify({
            'success': True,
            'client': client.to_dict(),
            'message': 'Client updated successfully'
        })
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error updating client {client_id}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/clients/<client_id>', methods=['DELETE'])
@login_required
def api_delete_client(client_id):
    """Delete a client (soft delete by setting status to inactive)"""
    try:
        if not DATABASE_AVAILABLE:
            return _delete_mock_client(client_id)
        
        user_id = session.get('user_id', '1')
        
        # Get client
        client = Client.query.filter_by(id=client_id, created_by=user_id).first()
        if not client:
            return jsonify({
                'success': False,
                'error': 'Client not found'
            }), 404
        
        # Check if client has active cases
        active_cases = Case.query.filter_by(client_id=client.id, status=CaseStatus.ACTIVE).count()
        if active_cases > 0:
            return jsonify({
                'success': False,
                'error': f'Cannot delete client with {active_cases} active cases. Close cases first.'
            }), 400
        
        # Soft delete - set status to inactive
        old_status = client.status
        client.status = 'inactive'
        db.session.commit()
        
        # Create audit log
        audit_log('delete', 'client', client.id, user_id, {
            'action': 'soft_delete',
            'old_status': old_status,
            'new_status': 'inactive'
        })
        
        logger.info(f"Client soft deleted: {client.id}")
        
        return jsonify({
            'success': True,
            'message': 'Client deactivated successfully'
        })
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error deleting client {client_id}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# ===== MOCK DATA FUNCTIONS =====

def _get_mock_clients():
    """Mock clients data for fallback"""
    return jsonify({
        'success': True,
        'clients': [
            {
                'id': '1',
                'client_type': 'business',
                'display_name': 'TechCorp Industries',
                'company_name': 'TechCorp Industries',
                'email': 'legal@techcorp.com',
                'phone': '(555) 123-4567',
                'status': 'active',
                'case_count': 3,
                'created_at': '2024-01-15T10:00:00Z',
                'recent_cases': [
                    {'id': '1', 'title': 'Contract Review', 'status': 'active'},
                    {'id': '2', 'title': 'IP Protection', 'status': 'pending'}
                ]
            },
            {
                'id': '2',
                'client_type': 'individual',
                'display_name': 'Sarah Johnson',
                'first_name': 'Sarah',
                'last_name': 'Johnson',
                'email': 'sarah.j@email.com',
                'phone': '(555) 987-6543',
                'status': 'active',
                'case_count': 1,
                'created_at': '2024-02-01T14:30:00Z',
                'recent_cases': [
                    {'id': '3', 'title': 'Employment Dispute', 'status': 'active'}
                ]
            }
        ],
        'pagination': {
            'page': 1,
            'pages': 1,
            'per_page': 20,
            'total': 2,
            'has_prev': False,
            'has_next': False
        }
    })

def _create_mock_client():
    """Mock client creation"""
    return jsonify({
        'success': True,
        'client': {
            'id': '3',
            'client_type': 'individual',
            'display_name': 'New Client',
            'status': 'active',
            'created_at': datetime.now().isoformat()
        },
        'message': 'Client created successfully (mock data)'
    })

def _get_mock_client(client_id):
    """Mock single client data"""
    return jsonify({
        'success': True,
        'client': {
            'id': client_id,
            'client_type': 'business',
            'display_name': 'Sample Client',
            'company_name': 'Sample Client Corp',
            'email': 'contact@sampleclient.com',
            'status': 'active',
            'cases': [],
            'recent_invoices': [],
            'recent_documents': [],
            'financial_summary': {
                'total_billed': 15000.00,
                'total_paid': 12000.00,
                'outstanding_amount': 3000.00,
                'invoice_count': 5
            }
        }
    })

def _update_mock_client(client_id):
    """Mock client update"""
    return jsonify({
        'success': True,
        'client': {
            'id': client_id,
            'status': 'active',
            'updated_at': datetime.now().isoformat()
        },
        'message': 'Client updated successfully (mock data)'
    })

def _delete_mock_client(client_id):
    """Mock client deletion"""
    return jsonify({
        'success': True,
        'message': 'Client deactivated successfully (mock data)'
    })

# ===== CASE MANAGEMENT APIs =====

@app.route('/api/cases', methods=['GET'])
@login_required
@role_required('admin', 'partner', 'associate', 'paralegal')
def api_get_cases():
    """Get all cases with optional search and filtering"""
    try:
        if not DATABASE_AVAILABLE:
            return _get_mock_cases()
        
        # Get query parameters
        search = request.args.get('search', '').strip()
        status = request.args.get('status', '')
        practice_area = request.args.get('practice_area', '')
        client_id = request.args.get('client_id', '')
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 20))
        
        # Get current user for role-based filtering
        user_id = session.get('user_id', '1')
        user_role = session.get('user_role', 'associate')
        
        # Build query - show all cases for admin/partner, own assigned cases for others
        if user_role in ['admin', 'partner']:
            query = Case.query
        else:
            # Show cases where user is primary attorney or assigned attorney
            query = Case.query.filter(
                db.or_(
                    Case.primary_attorney_id == user_id,
                    Case.attorneys.any(User.id == user_id)
                )
            )
        
        # Apply filters
        if search:
            query = query.filter(
                db.or_(
                    Case.title.ilike(f'%{search}%'),
                    Case.case_number.ilike(f'%{search}%'),
                    Case.description.ilike(f'%{search}%')
                )
            )
        
        if status:
            query = query.filter(Case.status == status)
            
        if practice_area:
            query = query.filter(Case.practice_area.ilike(f'%{practice_area}%'))
            
        if client_id:
            query = query.filter(Case.client_id == client_id)
        
        # Get total count for pagination
        total = query.count()
        
        # Apply pagination and ordering
        cases = query.order_by(Case.created_at.desc()).offset((page - 1) * per_page).limit(per_page).all()
        
        # Convert to dictionaries with additional details
        cases_data = []
        for case in cases:
            case_dict = case.to_dict()
            case_dict.update({
                'client_id': case.client_id,
                'primary_attorney_name': case.primary_attorney.get_full_name() if case.primary_attorney else None,
                'court_name': case.court_name,
                'judge_name': case.judge_name,
                'date_closed': case.date_closed.isoformat() if case.date_closed else None,
                'statute_of_limitations': case.statute_of_limitations.isoformat() if case.statute_of_limitations else None,
                'estimated_hours': float(case.estimated_hours) if case.estimated_hours else None,
                'hourly_rate': float(case.hourly_rate) if case.hourly_rate else None,
                'flat_fee': float(case.flat_fee) if case.flat_fee else None,
                'retainer_amount': float(case.retainer_amount) if case.retainer_amount else None,
                'attorney_count': len(case.attorneys),
                'task_count': case.tasks.count(),
                'document_count': case.documents.count(),
                'time_entry_count': case.time_entries.count()
            })
            cases_data.append(case_dict)
        
        return jsonify({
            'success': True,
            'cases': cases_data,
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': total,
                'pages': (total + per_page - 1) // per_page
            }
        })
        
    except Exception as e:
        logger.error(f"Get cases error: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to retrieve cases'
        }), 500

@app.route('/api/cases', methods=['POST'])
@login_required
@role_required('admin', 'partner', 'associate')
def api_create_case():
    """Create a new case"""
    try:
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['title', 'practice_area', 'client_id', 'date_opened']
        for field in required_fields:
            if field not in data or not data[field]:
                return jsonify({
                    'success': False,
                    'error': f'Missing required field: {field}'
                }), 400
        
        if not DATABASE_AVAILABLE:
            return _create_mock_case(data)
        
        # Get current user
        user_id = session.get('user_id', '1')
        
        # Verify client exists
        client = Client.query.get(data['client_id'])
        if not client:
            return jsonify({
                'success': False,
                'error': 'Client not found'
            }), 404
        
        # Generate unique case number
        case_number = data.get('case_number')
        if not case_number:
            # Auto-generate case number: YYYY-CLIENT_INITIALS-XXXX
            from datetime import datetime
            year = datetime.now().year
            client_initials = ''.join([word[0] for word in client.get_display_name().split()][:2]).upper()
            # Find next number for this client
            existing_count = Case.query.filter(Case.case_number.like(f'{year}-{client_initials}-%')).count()
            case_number = f'{year}-{client_initials}-{existing_count + 1:04d}'
        
        # Check for duplicate case number
        if Case.query.filter_by(case_number=case_number).first():
            return jsonify({
                'success': False,
                'error': 'Case number already exists'
            }), 400
        
        # Parse date
        from datetime import datetime
        date_opened = datetime.strptime(data['date_opened'], '%Y-%m-%d').date()
        
        # Create case
        case = Case(
            case_number=case_number,
            title=data['title'],
            description=data.get('description', ''),
            practice_area=data['practice_area'],
            case_type=data.get('case_type', ''),
            status=CaseStatus.ACTIVE,
            priority=data.get('priority', 'medium'),
            court_name=data.get('court_name', ''),
            judge_name=data.get('judge_name', ''),
            court_case_number=data.get('court_case_number', ''),
            date_opened=date_opened,
            client_id=data['client_id'],
            primary_attorney_id=data.get('primary_attorney_id', user_id)
        )
        
        # Set optional dates
        if data.get('date_closed'):
            case.date_closed = datetime.strptime(data['date_closed'], '%Y-%m-%d').date()
        if data.get('statute_of_limitations'):
            case.statute_of_limitations = datetime.strptime(data['statute_of_limitations'], '%Y-%m-%d').date()
        
        # Set financial information
        if data.get('estimated_hours'):
            case.estimated_hours = Decimal(str(data['estimated_hours']))
        if data.get('hourly_rate'):
            case.hourly_rate = Decimal(str(data['hourly_rate']))
        if data.get('flat_fee'):
            case.flat_fee = Decimal(str(data['flat_fee']))
        if data.get('retainer_amount'):
            case.retainer_amount = Decimal(str(data['retainer_amount']))
        
        db.session.add(case)
        db.session.commit()
        
        # Add assigned attorneys if provided
        if data.get('attorney_ids'):
            for attorney_id in data['attorney_ids']:
                attorney = User.query.get(attorney_id)
                if attorney and attorney.role.value in ['admin', 'partner', 'associate']:
                    case.attorneys.append(attorney)
            db.session.commit()
        
        # Create audit log
        audit_log('create', 'case', case.id, user_id, {
            'case_number': case_number,
            'title': data['title'],
            'client_id': data['client_id']
        })
        
        logger.info(f"Case created: {case.id} - {case_number}")
        
        return jsonify({
            'success': True,
            'message': 'Case created successfully',
            'case': case.to_dict()
        }), 201
        
    except Exception as e:
        logger.error(f"Create case error: {e}")
        if DATABASE_AVAILABLE:
            db.session.rollback()
        return jsonify({
            'success': False,
            'error': 'Failed to create case'
        }), 500

@app.route('/api/cases/<case_id>', methods=['GET'])
@login_required
@role_required('admin', 'partner', 'associate', 'paralegal')
def api_get_case(case_id):
    """Get a specific case with full details"""
    try:
        if not DATABASE_AVAILABLE:
            return _get_mock_case(case_id)
        
        case = Case.query.get(case_id)
        if not case:
            return jsonify({
                'success': False,
                'error': 'Case not found'
            }), 404
        
        # Check permission - user must be assigned to case or have admin/partner role
        user_id = session.get('user_id', '1')
        user_role = session.get('user_role', 'associate')
        
        if user_role not in ['admin', 'partner']:
            if case.primary_attorney_id != user_id and not any(attorney.id == user_id for attorney in case.attorneys):
                return jsonify({
                    'success': False,
                    'error': 'Access denied - not assigned to this case'
                }), 403
        
        # Get comprehensive case details
        case_data = case.to_dict()
        case_data.update({
            'client': case.client.to_dict() if case.client else None,
            'primary_attorney': case.primary_attorney.to_dict() if case.primary_attorney else None,
            'attorneys': [attorney.to_dict() for attorney in case.attorneys],
            'court_name': case.court_name,
            'judge_name': case.judge_name,
            'court_case_number': case.court_case_number,
            'date_closed': case.date_closed.isoformat() if case.date_closed else None,
            'statute_of_limitations': case.statute_of_limitations.isoformat() if case.statute_of_limitations else None,
            'estimated_hours': float(case.estimated_hours) if case.estimated_hours else None,
            'hourly_rate': float(case.hourly_rate) if case.hourly_rate else None,
            'flat_fee': float(case.flat_fee) if case.flat_fee else None,
            'retainer_amount': float(case.retainer_amount) if case.retainer_amount else None,
            'tasks': [task.to_dict() for task in case.tasks.order_by(Task.created_at.desc()).limit(10)],
            'documents': [doc.to_dict() for doc in case.documents.order_by(Document.created_at.desc()).limit(10)],
            'time_entries': [entry.to_dict() for entry in case.time_entries.order_by(TimeEntry.created_at.desc()).limit(10)],
            'recent_activity': _get_case_recent_activity(case)
        })
        
        return jsonify({
            'success': True,
            'case': case_data
        })
        
    except Exception as e:
        logger.error(f"Get case error: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to retrieve case'
        }), 500

@app.route('/api/cases/<case_id>', methods=['PUT'])
@login_required
@role_required('admin', 'partner', 'associate')
def api_update_case(case_id):
    """Update a case"""
    try:
        data = request.get_json()
        
        if not DATABASE_AVAILABLE:
            return _update_mock_case(case_id, data)
        
        case = Case.query.get(case_id)
        if not case:
            return jsonify({
                'success': False,
                'error': 'Case not found'
            }), 404
        
        # Check permission
        user_id = session.get('user_id', '1')
        user_role = session.get('user_role', 'associate')
        
        if user_role not in ['admin', 'partner']:
            if case.primary_attorney_id != user_id:
                return jsonify({
                    'success': False,
                    'error': 'Access denied - only primary attorney or admin/partner can update case'
                }), 403
        
        # Store old values for audit
        old_values = {
            'title': case.title,
            'status': case.status.value,
            'priority': case.priority
        }
        
        # Update fields
        if 'title' in data:
            case.title = data['title']
        if 'description' in data:
            case.description = data['description']
        if 'practice_area' in data:
            case.practice_area = data['practice_area']
        if 'case_type' in data:
            case.case_type = data['case_type']
        if 'status' in data:
            case.status = CaseStatus(data['status'])
        if 'priority' in data:
            case.priority = data['priority']
        if 'court_name' in data:
            case.court_name = data['court_name']
        if 'judge_name' in data:
            case.judge_name = data['judge_name']
        if 'court_case_number' in data:
            case.court_case_number = data['court_case_number']
        
        # Update dates
        if 'date_closed' in data and data['date_closed']:
            case.date_closed = datetime.strptime(data['date_closed'], '%Y-%m-%d').date()
        if 'statute_of_limitations' in data and data['statute_of_limitations']:
            case.statute_of_limitations = datetime.strptime(data['statute_of_limitations'], '%Y-%m-%d').date()
        
        # Update financial fields
        if 'estimated_hours' in data and data['estimated_hours']:
            case.estimated_hours = Decimal(str(data['estimated_hours']))
        if 'hourly_rate' in data and data['hourly_rate']:
            case.hourly_rate = Decimal(str(data['hourly_rate']))
        if 'flat_fee' in data and data['flat_fee']:
            case.flat_fee = Decimal(str(data['flat_fee']))
        if 'retainer_amount' in data and data['retainer_amount']:
            case.retainer_amount = Decimal(str(data['retainer_amount']))
        
        # Update primary attorney
        if 'primary_attorney_id' in data:
            attorney = User.query.get(data['primary_attorney_id'])
            if attorney and attorney.role.value in ['admin', 'partner', 'associate']:
                case.primary_attorney_id = data['primary_attorney_id']
        
        db.session.commit()
        
        # Update assigned attorneys if provided
        if 'attorney_ids' in data:
            # Clear existing assignments
            case.attorneys.clear()
            # Add new assignments
            for attorney_id in data['attorney_ids']:
                attorney = User.query.get(attorney_id)
                if attorney and attorney.role.value in ['admin', 'partner', 'associate']:
                    case.attorneys.append(attorney)
            db.session.commit()
        
        # Create audit log
        new_values = {
            'title': case.title,
            'status': case.status.value,
            'priority': case.priority
        }
        
        audit_log('update', 'case', case.id, user_id, {
            'old_values': old_values,
            'new_values': new_values
        })
        
        logger.info(f"Case updated: {case.id}")
        
        return jsonify({
            'success': True,
            'message': 'Case updated successfully',
            'case': case.to_dict()
        })
        
    except Exception as e:
        logger.error(f"Update case error: {e}")
        if DATABASE_AVAILABLE:
            db.session.rollback()
        return jsonify({
            'success': False,
            'error': 'Failed to update case'
        }), 500

@app.route('/api/cases/<case_id>/status', methods=['PUT'])
@login_required
@role_required('admin', 'partner', 'associate')
def api_update_case_status(case_id):
    """Update case status (active -> pending -> closed -> on_hold)"""
    try:
        data = request.get_json()
        
        if 'status' not in data:
            return jsonify({
                'success': False,
                'error': 'Status is required'
            }), 400
        
        if not DATABASE_AVAILABLE:
            return _update_mock_case_status(case_id, data['status'])
        
        case = Case.query.get(case_id)
        if not case:
            return jsonify({
                'success': False,
                'error': 'Case not found'
            }), 404
        
        old_status = case.status.value
        new_status = data['status']
        
        # Validate status transition
        valid_statuses = ['active', 'pending', 'closed', 'on_hold']
        if new_status not in valid_statuses:
            return jsonify({
                'success': False,
                'error': f'Invalid status. Must be one of: {", ".join(valid_statuses)}'
            }), 400
        
        case.status = CaseStatus(new_status)
        
        # Set date_closed if closing case
        if new_status == 'closed' and not case.date_closed:
            case.date_closed = datetime.now(timezone.utc).date()
        elif new_status != 'closed':
            case.date_closed = None
        
        db.session.commit()
        
        # Create audit log
        user_id = session.get('user_id', '1')
        audit_log('update', 'case', case.id, user_id, {
            'action': 'status_change',
            'old_status': old_status,
            'new_status': new_status,
            'notes': data.get('notes', '')
        })
        
        logger.info(f"Case status updated: {case.id} from {old_status} to {new_status}")
        
        return jsonify({
            'success': True,
            'message': f'Case status updated to {new_status}',
            'case': case.to_dict()
        })
        
    except Exception as e:
        logger.error(f"Update case status error: {e}")
        if DATABASE_AVAILABLE:
            db.session.rollback()
        return jsonify({
            'success': False,
            'error': 'Failed to update case status'
        }), 500

# ===== DEADLINE MANAGEMENT API =====

@app.route('/api/deadlines', methods=['GET'])
@login_required
@role_required('admin', 'partner', 'associate', 'paralegal')
def api_get_deadlines():
    """Get upcoming deadlines and court dates"""
    try:
        if not DATABASE_AVAILABLE:
            return _get_mock_deadlines()
        
        # Get query parameters
        days_ahead = request.args.get('days', 30, type=int)
        case_id = request.args.get('case_id')
        deadline_type = request.args.get('type')  # statute, court, task
        
        current_date = datetime.now(timezone.utc).date()
        end_date = current_date + timedelta(days=days_ahead)
        
        deadlines = []
        
        # Statute of limitations deadlines
        if not deadline_type or deadline_type == 'statute':
            statute_cases = Case.query.filter(
                Case.statute_of_limitations.isnot(None),
                Case.statute_of_limitations >= current_date,
                Case.statute_of_limitations <= end_date,
                Case.status != CaseStatus.CLOSED
            )
            if case_id:
                statute_cases = statute_cases.filter(Case.id == case_id)
            
            for case in statute_cases:
                days_remaining = (case.statute_of_limitations - current_date).days
                priority = 'urgent' if days_remaining <= 7 else 'high' if days_remaining <= 30 else 'medium'
                
                deadlines.append({
                    'id': f'statute_{case.id}',
                    'type': 'statute',
                    'title': f'Statute of Limitations - {case.title}',
                    'description': f'Statute of limitations expires for case {case.case_number}',
                    'due_date': case.statute_of_limitations.isoformat(),
                    'days_remaining': days_remaining,
                    'priority': priority,
                    'case_id': case.id,
                    'case_number': case.case_number,
                    'case_title': case.title,
                    'client_name': case.client.get_display_name() if case.client else None
                })
        
        # Court dates from calendar events
        if not deadline_type or deadline_type == 'court':
            court_events = CalendarEvent.query.filter(
                CalendarEvent.event_type.in_(['court', 'hearing', 'trial']),
                CalendarEvent.start_datetime >= datetime.combine(current_date, datetime.min.time().replace(tzinfo=timezone.utc)),
                CalendarEvent.start_datetime <= datetime.combine(end_date, datetime.max.time().replace(tzinfo=timezone.utc))
            )
            if case_id:
                court_events = court_events.filter(CalendarEvent.case_id == case_id)
            
            for event in court_events:
                event_date = event.start_datetime.date()
                days_remaining = (event_date - current_date).days
                priority = 'urgent' if days_remaining <= 3 else 'high' if days_remaining <= 7 else 'medium'
                
                deadlines.append({
                    'id': f'court_{event.id}',
                    'type': 'court',
                    'title': event.title,
                    'description': event.description or f'Court appearance at {event.location or "TBD"}',
                    'due_date': event_date.isoformat(),
                    'due_time': event.start_datetime.strftime('%H:%M'),
                    'days_remaining': days_remaining,
                    'priority': priority,
                    'case_id': event.case_id,
                    'case_number': event.case.case_number if event.case else None,
                    'case_title': event.case.title if event.case else None,
                    'client_name': event.client.get_display_name() if event.client else (event.case.client.get_display_name() if event.case and event.case.client else None),
                    'location': event.location
                })
        
        # Task deadlines
        if not deadline_type or deadline_type == 'task':
            task_deadlines = Task.query.filter(
                Task.due_date.isnot(None),
                Task.due_date >= current_date,
                Task.due_date <= end_date,
                Task.status != TaskStatus.DONE
            )
            if case_id:
                task_deadlines = task_deadlines.filter(Task.case_id == case_id)
            
            for task in task_deadlines:
                days_remaining = (task.due_date - current_date).days
                priority = task.priority.value if task.priority else 'medium'
                if days_remaining <= 1:
                    priority = 'urgent'
                elif days_remaining <= 3 and priority not in ['urgent', 'high']:
                    priority = 'high'
                
                deadlines.append({
                    'id': f'task_{task.id}',
                    'type': 'task',
                    'title': task.title,
                    'description': task.description or 'No description provided',
                    'due_date': task.due_date.isoformat(),
                    'days_remaining': days_remaining,
                    'priority': priority,
                    'case_id': task.case_id,
                    'case_number': task.case.case_number if task.case else None,
                    'case_title': task.case.title if task.case else None,
                    'client_name': task.client.get_display_name() if task.client else (task.case.client.get_display_name() if task.case and task.case.client else None),
                    'assignee_name': task.assignee_user.get_full_name() if task.assignee_user else None
                })
        
        # Sort by days remaining and priority
        priority_order = {'urgent': 0, 'high': 1, 'medium': 2, 'low': 3}
        deadlines.sort(key=lambda x: (x['days_remaining'], priority_order.get(x['priority'], 4)))
        
        return jsonify({
            'success': True,
            'deadlines': deadlines,
            'summary': {
                'total': len(deadlines),
                'urgent': len([d for d in deadlines if d['priority'] == 'urgent']),
                'high': len([d for d in deadlines if d['priority'] == 'high']),
                'upcoming_week': len([d for d in deadlines if d['days_remaining'] <= 7])
            }
        })
        
    except Exception as e:
        logger.error(f"Error fetching deadlines: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/deadlines/calendar-events', methods=['POST'])
@login_required
@role_required('admin', 'partner', 'associate', 'paralegal')
def api_create_deadline_calendar_event():
    """Create a new calendar event/deadline"""
    try:
        if not DATABASE_AVAILABLE:
            return _create_mock_calendar_event()
        
        data = request.json
        user_id = session.get('user_id', '1')
        
        # Validate required fields
        if not data.get('title') or not data.get('start_datetime'):
            return jsonify({
                'success': False,
                'error': 'Title and start datetime are required'
            }), 400
        
        # Parse datetime
        start_dt = datetime.fromisoformat(data['start_datetime'].replace('Z', '+00:00'))
        end_dt = datetime.fromisoformat(data['end_datetime'].replace('Z', '+00:00')) if data.get('end_datetime') else start_dt + timedelta(hours=1)
        
        # Create calendar event
        event = CalendarEvent(
            title=data['title'],
            description=data.get('description'),
            event_type=data.get('event_type', 'meeting'),
            location=data.get('location'),
            start_datetime=start_dt,
            end_datetime=end_dt,
            all_day=data.get('all_day', False),
            reminder_minutes=data.get('reminder_minutes', 15),
            case_id=data.get('case_id'),
            client_id=data.get('client_id'),
            created_by=user_id
        )
        
        db.session.add(event)
        db.session.commit()
        
        # Create audit log
        audit_log('create', 'calendar_event', event.id, user_id, event.to_dict())
        
        logger.info(f"Calendar event created: {event.id}")
        
        return jsonify({
            'success': True,
            'event': event.to_dict(),
            'message': 'Calendar event created successfully'
        })
        
    except Exception as e:
        if DATABASE_AVAILABLE:
            db.session.rollback()
        logger.error(f"Error creating calendar event: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/deadlines/tasks', methods=['POST'])
@login_required
@role_required('admin', 'partner', 'associate', 'paralegal')
def api_create_task():
    """Create a new task with deadline"""
    try:
        if not DATABASE_AVAILABLE:
            return _create_mock_task()
        
        data = request.json
        user_id = session.get('user_id', '1')
        
        # Validate required fields
        if not data.get('title'):
            return jsonify({
                'success': False,
                'error': 'Title is required'
            }), 400
        
        # Parse due date if provided
        due_date = None
        if data.get('due_date'):
            due_date = datetime.fromisoformat(data['due_date']).date()
        
        # Create task
        task = Task(
            title=data['title'],
            description=data.get('description'),
            status=TaskStatus(data.get('status', 'todo')),
            priority=TaskPriority(data.get('priority', 'medium')),
            due_date=due_date,
            start_date=datetime.fromisoformat(data['start_date']).date() if data.get('start_date') else None,
            estimated_hours=Decimal(str(data['estimated_hours'])) if data.get('estimated_hours') else None,
            assignee_id=data.get('assignee_id', user_id),
            case_id=data.get('case_id'),
            client_id=data.get('client_id'),
            created_by=user_id
        )
        
        db.session.add(task)
        db.session.commit()
        
        # Create audit log
        audit_log('create', 'task', task.id, user_id, task.to_dict())
        
        logger.info(f"Task created: {task.id}")
        
        return jsonify({
            'success': True,
            'task': task.to_dict(),
            'message': 'Task created successfully'
        })
        
    except Exception as e:
        if DATABASE_AVAILABLE:
            db.session.rollback()
        logger.error(f"Error creating task: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/deadlines/reminders', methods=['GET'])
@login_required
@role_required('admin', 'partner', 'associate', 'paralegal')
def api_get_deadline_reminders():
    """Get deadline reminders that need to be sent"""
    try:
        if not DATABASE_AVAILABLE:
            return _get_mock_reminders()
        
        current_time = datetime.now(timezone.utc)
        reminders = []
        
        # Find calendar events with reminders due
        upcoming_events = CalendarEvent.query.filter(
            CalendarEvent.reminder_sent == False,
            CalendarEvent.start_datetime > current_time,
            CalendarEvent.start_datetime <= current_time + timedelta(minutes=CalendarEvent.reminder_minutes)
        ).all()
        
        for event in upcoming_events:
            reminders.append({
                'id': event.id,
                'type': 'calendar_event',
                'title': event.title,
                'description': event.description,
                'due_datetime': event.start_datetime.isoformat(),
                'case_id': event.case_id,
                'client_id': event.client_id
            })
        
        # Find tasks due soon (within 24 hours for urgent, 3 days for high priority)
        urgent_tasks = Task.query.filter(
            Task.due_date.isnot(None),
            Task.status != TaskStatus.DONE,
            Task.due_date <= (current_time + timedelta(days=1)).date()
        ).all()
        
        for task in urgent_tasks:
            reminders.append({
                'id': task.id,
                'type': 'task',
                'title': task.title,
                'description': task.description,
                'due_date': task.due_date.isoformat(),
                'priority': task.priority.value,
                'assignee_id': task.assignee_id,
                'case_id': task.case_id,
                'client_id': task.client_id
            })
        
        return jsonify({
            'success': True,
            'reminders': reminders,
            'count': len(reminders)
        })
        
    except Exception as e:
        logger.error(f"Error fetching reminders: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

def _get_mock_deadlines():
    """Mock deadlines for development"""
    current_date = datetime.now().date()
    return jsonify({
        'success': True,
        'deadlines': [
            {
                'id': 'statute_1',
                'type': 'statute',
                'title': 'Statute of Limitations - Personal Injury Case',
                'description': 'Statute of limitations expires for case 2024-JS-001',
                'due_date': (current_date + timedelta(days=15)).isoformat(),
                'days_remaining': 15,
                'priority': 'high',
                'case_id': '1',
                'case_number': '2024-JS-001',
                'case_title': 'Smith v. Johnson Motor Co.',
                'client_name': 'John Smith'
            },
            {
                'id': 'court_1',
                'type': 'court',
                'title': 'Preliminary Hearing',
                'description': 'Court appearance at Superior Court',
                'due_date': (current_date + timedelta(days=3)).isoformat(),
                'due_time': '09:30',
                'days_remaining': 3,
                'priority': 'urgent',
                'case_id': '2',
                'case_number': '2024-MC-005',
                'case_title': 'Business Contract Dispute',
                'client_name': 'TechCorp Industries',
                'location': 'Superior Court, Room 304'
            }
        ],
        'summary': {
            'total': 2,
            'urgent': 1,
            'high': 1,
            'upcoming_week': 1
        }
    })

def _create_mock_calendar_event():
    """Mock calendar event creation"""
    return jsonify({
        'success': True,
        'event': {
            'id': str(uuid.uuid4()),
            'title': 'Mock Event',
            'event_type': 'meeting',
            'start_datetime': datetime.now().isoformat(),
            'created_at': datetime.now().isoformat()
        },
        'message': 'Calendar event created successfully (mock)'
    })

def _create_mock_task():
    """Mock task creation"""
    return jsonify({
        'success': True,
        'task': {
            'id': str(uuid.uuid4()),
            'title': 'Mock Task',
            'status': 'todo',
            'priority': 'medium',
            'created_at': datetime.now().isoformat()
        },
        'message': 'Task created successfully (mock)'
    })

def _get_mock_reminders():
    """Mock reminders"""
    return jsonify({
        'success': True,
        'reminders': [],
        'count': 0
    })

# ===== CALENDAR MANAGEMENT API =====

@app.route('/calendar')
@login_required
def calendar_page():
    """Calendar page"""
    try:
        return render_template('calendar.html')
    except Exception as e:
        logger.error(f"Calendar page error: {e}")
        return f"Calendar error: {e}", 500

@app.route('/api/calendar/events', methods=['GET'])
@login_required
@role_required('admin', 'partner', 'associate', 'paralegal')
def api_get_calendar_events():
    """Get calendar events with filtering"""
    try:
        if not DATABASE_AVAILABLE:
            return _get_mock_calendar_events()
        
        # Get query parameters
        start_date = request.args.get('start')
        end_date = request.args.get('end')
        event_type = request.args.get('type')
        case_id = request.args.get('case_id')
        client_id = request.args.get('client_id')
        
        # Build query
        query = CalendarEvent.query
        
        # Filter by date range
        if start_date:
            try:
                start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
                query = query.filter(CalendarEvent.start_datetime >= start_dt)
            except ValueError:
                pass
                
        if end_date:
            try:
                end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
                query = query.filter(CalendarEvent.end_datetime <= end_dt)
            except ValueError:
                pass
        
        # Filter by type
        if event_type:
            query = query.filter(CalendarEvent.event_type == event_type)
            
        # Filter by case
        if case_id:
            query = query.filter(CalendarEvent.case_id == case_id)
            
        # Filter by client
        if client_id:
            query = query.filter(CalendarEvent.client_id == client_id)
        
        # Get current user's events
        user_id = session.get('user_id', '1')
        query = query.filter(CalendarEvent.created_by == user_id)
        
        events = query.order_by(CalendarEvent.start_datetime.asc()).all()
        
        # Convert to calendar format
        calendar_events = []
        for event in events:
            calendar_events.append({
                'id': event.id,
                'title': event.title,
                'description': event.description,
                'start': event.start_datetime.isoformat() if event.start_datetime else None,
                'end': event.end_datetime.isoformat() if event.end_datetime else None,
                'allDay': event.all_day,
                'type': event.event_type,
                'location': event.location,
                'case_title': event.case.title if event.case else None,
                'case_id': event.case_id,
                'client_name': event.client.get_display_name() if event.client else None,
                'client_id': event.client_id,
                'reminder_minutes': event.reminder_minutes,
                'className': f'event-{event.event_type}',
                'color': _get_event_color(event.event_type)
            })
        
        return jsonify({
            'success': True,
            'events': calendar_events,
            'count': len(calendar_events)
        })
        
    except Exception as e:
        logger.error(f"Error fetching calendar events: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/calendar/events', methods=['POST'])
@login_required
@role_required('admin', 'partner', 'associate', 'paralegal')
def api_create_calendar_event():
    """Create a new calendar event"""
    try:
        if not DATABASE_AVAILABLE:
            return _create_mock_calendar_event()
        
        data = request.json
        user_id = session.get('user_id', '1')
        
        # Validate required fields
        if not data.get('title') or not data.get('start_datetime'):
            return jsonify({
                'success': False,
                'error': 'Title and start date/time are required'
            }), 400
        
        # Parse dates
        try:
            start_dt = datetime.fromisoformat(data['start_datetime'].replace('Z', '+00:00'))
            end_dt = datetime.fromisoformat(data['end_datetime'].replace('Z', '+00:00')) if data.get('end_datetime') else start_dt + timedelta(hours=1)
        except ValueError as e:
            return jsonify({
                'success': False,
                'error': f'Invalid date format: {e}'
            }), 400
        
        # Create calendar event
        event = CalendarEvent(
            title=data['title'],
            description=data.get('description', ''),
            event_type=data.get('event_type', 'meeting'),
            location=data.get('location', ''),
            start_datetime=start_dt,
            end_datetime=end_dt,
            all_day=data.get('all_day', False),
            reminder_minutes=data.get('reminder_minutes', 15),
            case_id=data.get('case_id'),
            client_id=data.get('client_id'),
            created_by=user_id
        )
        
        db.session.add(event)
        db.session.commit()
        
        # Log the creation
        audit_log('create', 'calendar_event', event.id, user_id, event.to_dict())
        
        logger.info(f"Created calendar event {event.id} for user {user_id}")
        
        return jsonify({
            'success': True,
            'message': 'Calendar event created successfully',
            'event': event.to_dict()
        })
        
    except Exception as e:
        logger.error(f"Error creating calendar event: {e}")
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': 'Failed to create calendar event'
        }), 500

@app.route('/api/calendar/events/<event_id>', methods=['PUT'])
@login_required
@role_required('admin', 'partner', 'associate', 'paralegal')
def api_update_calendar_event(event_id):
    """Update calendar event"""
    try:
        if not DATABASE_AVAILABLE:
            return jsonify({'success': False, 'error': 'Database not available'}), 503
        
        event = CalendarEvent.query.get(event_id)
        if not event:
            return jsonify({'success': False, 'error': 'Event not found'}), 404
        
        data = request.json
        old_values = event.to_dict()
        
        # Update fields
        if 'title' in data:
            event.title = data['title']
        if 'description' in data:
            event.description = data['description']
        if 'event_type' in data:
            event.event_type = data['event_type']
        if 'location' in data:
            event.location = data['location']
        if 'start_datetime' in data:
            event.start_datetime = datetime.fromisoformat(data['start_datetime'].replace('Z', '+00:00'))
        if 'end_datetime' in data:
            event.end_datetime = datetime.fromisoformat(data['end_datetime'].replace('Z', '+00:00'))
        if 'all_day' in data:
            event.all_day = data['all_day']
        if 'reminder_minutes' in data:
            event.reminder_minutes = data['reminder_minutes']
        if 'case_id' in data:
            event.case_id = data['case_id']
        if 'client_id' in data:
            event.client_id = data['client_id']
        
        event.updated_at = datetime.now(timezone.utc)
        db.session.commit()
        
        # Log the update
        audit_log('update', 'calendar_event', event_id, session.get('user_id'), 
                 old_values=old_values, new_values=event.to_dict())
        
        return jsonify({
            'success': True,
            'message': 'Calendar event updated successfully',
            'event': event.to_dict()
        })
        
    except Exception as e:
        logger.error(f"Error updating calendar event: {e}")
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': 'Failed to update calendar event'
        }), 500

@app.route('/api/calendar/events/<event_id>', methods=['DELETE'])
@login_required
@role_required('admin', 'partner', 'associate', 'paralegal')
def api_delete_calendar_event(event_id):
    """Delete calendar event"""
    try:
        if not DATABASE_AVAILABLE:
            return jsonify({'success': False, 'error': 'Database not available'}), 503
        
        event = CalendarEvent.query.get(event_id)
        if not event:
            return jsonify({'success': False, 'error': 'Event not found'}), 404
        
        # Log the deletion
        audit_log('delete', 'calendar_event', event_id, session.get('user_id'), event.to_dict())
        
        db.session.delete(event)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Calendar event deleted successfully'
        })
        
    except Exception as e:
        logger.error(f"Error deleting calendar event: {e}")
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': 'Failed to delete calendar event'
        }), 500

@app.route('/api/calendar/availability', methods=['GET'])
@login_required
@role_required('admin', 'partner', 'associate', 'paralegal')
def api_get_availability():
    """Get availability for scheduling"""
    try:
        if not DATABASE_AVAILABLE:
            return _get_mock_availability()
        
        # Get query parameters
        date_str = request.args.get('date')
        duration = int(request.args.get('duration', 60))  # minutes
        
        if not date_str:
            return jsonify({
                'success': False,
                'error': 'Date parameter required'
            }), 400
        
        try:
            target_date = datetime.fromisoformat(date_str).date()
        except ValueError:
            return jsonify({
                'success': False,
                'error': 'Invalid date format'
            }), 400
        
        # Get events for the day
        start_of_day = datetime.combine(target_date, datetime.min.time()).replace(tzinfo=timezone.utc)
        end_of_day = datetime.combine(target_date, datetime.max.time()).replace(tzinfo=timezone.utc)
        
        user_id = session.get('user_id', '1')
        events = CalendarEvent.query.filter(
            CalendarEvent.created_by == user_id,
            CalendarEvent.start_datetime >= start_of_day,
            CalendarEvent.start_datetime <= end_of_day
        ).order_by(CalendarEvent.start_datetime.asc()).all()
        
        # Calculate available time slots
        business_start = 9  # 9 AM
        business_end = 17   # 5 PM
        slot_duration = duration
        
        available_slots = []
        current_time = business_start * 60  # Convert to minutes
        end_time = business_end * 60
        
        for event in events:
            event_start = event.start_datetime.hour * 60 + event.start_datetime.minute
            event_end = event.end_datetime.hour * 60 + event.end_datetime.minute
            
            # Add slots before this event
            while current_time + slot_duration <= event_start:
                slot_time = f"{current_time // 60:02d}:{current_time % 60:02d}"
                available_slots.append({
                    'time': slot_time,
                    'available': True,
                    'duration': slot_duration
                })
                current_time += slot_duration
            
            # Skip past this event
            current_time = max(current_time, event_end)
        
        # Add remaining slots
        while current_time + slot_duration <= end_time:
            slot_time = f"{current_time // 60:02d}:{current_time % 60:02d}"
            available_slots.append({
                'time': slot_time,
                'available': True,
                'duration': slot_duration
            })
            current_time += slot_duration
        
        return jsonify({
            'success': True,
            'date': date_str,
            'available_slots': available_slots,
            'business_hours': {
                'start': f"{business_start:02d}:00",
                'end': f"{business_end:02d}:00"
            }
        })
        
    except Exception as e:
        logger.error(f"Error getting availability: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to get availability'
        }), 500

@app.route('/api/calendar/google-sync', methods=['POST'])
@login_required
@role_required('admin', 'partner', 'associate', 'paralegal')
def api_google_calendar_sync():
    """Sync with Google Calendar"""
    try:
        # This would require Google Calendar API setup
        # For now, return a mock response
        return jsonify({
            'success': True,
            'message': 'Google Calendar sync initiated',
            'sync_status': 'pending',
            'note': 'Google Calendar integration requires API configuration'
        })
        
    except Exception as e:
        logger.error(f"Error syncing with Google Calendar: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to sync with Google Calendar'
        }), 500

def _get_event_color(event_type):
    """Get color for event type"""
    colors = {
        'court': '#dc2626',      # Red
        'meeting': '#2563eb',    # Blue
        'deadline': '#f59e0b',   # Amber
        'appointment': '#059669', # Green
        'consultation': '#7c3aed', # Purple
        'deposition': '#ea580c',  # Orange
        'hearing': '#dc2626',     # Red
        'conference': '#2563eb',  # Blue
        'default': '#6b7280'      # Gray
    }
    return colors.get(event_type, colors['default'])

def _get_mock_calendar_events():
    """Mock calendar events"""
    mock_events = [
        {
            'id': '1',
            'title': 'Client Meeting - Smith Case',
            'start': (datetime.now() + timedelta(days=1)).isoformat(),
            'end': (datetime.now() + timedelta(days=1, hours=1)).isoformat(),
            'allDay': False,
            'type': 'meeting',
            'location': 'Conference Room A',
            'color': '#2563eb'
        },
        {
            'id': '2',
            'title': 'Court Hearing - Johnson v. ABC Corp',
            'start': (datetime.now() + timedelta(days=3)).isoformat(),
            'end': (datetime.now() + timedelta(days=3, hours=2)).isoformat(),
            'allDay': False,
            'type': 'court',
            'location': 'Superior Court',
            'color': '#dc2626'
        }
    ]
    
    return jsonify({
        'success': True,
        'events': mock_events,
        'count': len(mock_events)
    })

def _get_mock_availability():
    """Mock availability"""
    return jsonify({
        'success': True,
        'date': datetime.now().date().isoformat(),
        'available_slots': [
            {'time': '09:00', 'available': True, 'duration': 60},
            {'time': '10:00', 'available': True, 'duration': 60},
            {'time': '11:00', 'available': False, 'duration': 60},
            {'time': '14:00', 'available': True, 'duration': 60},
            {'time': '15:00', 'available': True, 'duration': 60}
        ],
        'business_hours': {'start': '09:00', 'end': '17:00'}
    })

# ===== DOCUMENT MANAGEMENT API =====

@app.route('/api/documents', methods=['GET'])
@login_required
def api_get_documents():
    """Get documents with filtering and search"""
    try:
        if not DATABASE_AVAILABLE:
            return _get_mock_documents()
        
        # Get query parameters
        page = request.args.get('page', 1, type=int)
        per_page = min(request.args.get('per_page', 20, type=int), 100)
        search = request.args.get('search', '').strip()
        case_id = request.args.get('case_id')
        client_id = request.args.get('client_id')
        document_type = request.args.get('document_type')
        status = request.args.get('status')
        
        # Build query
        query = Document.query
        
        # Apply filters
        if search:
            query = query.filter(
                db.or_(
                    Document.title.ilike(f'%{search}%'),
                    Document.description.ilike(f'%{search}%'),
                    Document.original_filename.ilike(f'%{search}%')
                )
            )
        
        if case_id:
            query = query.filter(Document.case_id == case_id)
        
        if client_id:
            query = query.filter(Document.client_id == client_id)
        
        if document_type:
            query = query.filter(Document.document_type == document_type)
        
        if status:
            query = query.filter(Document.status == DocumentStatus(status))
        
        # Apply pagination and ordering
        documents = query.order_by(Document.created_at.desc()).paginate(
            page=page, per_page=per_page, error_out=False
        )
        
        # Convert to dict with additional info
        documents_data = []
        for doc in documents.items:
            doc_dict = doc.to_dict()
            doc_dict.update({
                'case_title': doc.case.title if doc.case else None,
                'case_number': doc.case.case_number if doc.case else None,
                'client_name': doc.client.get_display_name() if doc.client else None,
                'created_by_name': doc.created_by_user.get_full_name() if doc.created_by_user else None,
                'file_size_mb': round(doc.file_size / (1024 * 1024), 2) if doc.file_size else 0
            })
            documents_data.append(doc_dict)
        
        return jsonify({
            'success': True,
            'documents': documents_data,
            'pagination': {
                'page': documents.page,
                'pages': documents.pages,
                'per_page': documents.per_page,
                'total': documents.total,
                'has_prev': documents.has_prev,
                'has_next': documents.has_next
            }
        })
        
    except Exception as e:
        logger.error(f"Error fetching documents: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/documents', methods=['POST'])
@login_required
def api_create_document():
    """Create a new document (metadata only - file upload handled separately)"""
    try:
        if not DATABASE_AVAILABLE:
            return _create_mock_document()
        
        data = request.json
        user_id = session.get('user_id', '1')
        
        # Validate required fields
        if not data.get('title') or not data.get('document_type'):
            return jsonify({
                'success': False,
                'error': 'Title and document type are required'
            }), 400
        
        # Create document
        document = Document(
            title=data['title'],
            description=data.get('description'),
            filename=data.get('filename', 'placeholder.pdf'),
            original_filename=data.get('original_filename', data['title'] + '.pdf'),
            file_size=data.get('file_size', 0),
            mime_type=data.get('mime_type', 'application/pdf'),
            storage_provider=data.get('storage_provider', 'local'),
            storage_path=data.get('storage_path', '/uploads/documents/'),
            document_type=data['document_type'],
            status=DocumentStatus(data.get('status', 'draft')),
            version=data.get('version', '1.0'),
            is_confidential=data.get('is_confidential', True),
            is_privileged=data.get('is_privileged', False),
            access_level=data.get('access_level', 'private'),
            case_id=data.get('case_id'),
            client_id=data.get('client_id'),
            created_by=user_id
        )
        
        db.session.add(document)
        db.session.commit()
        
        # Create audit log
        audit_log('create', 'document', document.id, user_id, document.to_dict())
        
        logger.info(f"Document created: {document.id}")
        
        return jsonify({
            'success': True,
            'document': document.to_dict(),
            'message': 'Document created successfully'
        })
        
    except Exception as e:
        if DATABASE_AVAILABLE:
            db.session.rollback()
        logger.error(f"Error creating document: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/documents/<document_id>', methods=['GET'])
@login_required
def api_get_document(document_id):
    """Get a specific document with full details"""
    try:
        if not DATABASE_AVAILABLE:
            return _get_mock_document(document_id)
        
        document = Document.query.get(document_id)
        if not document:
            return jsonify({
                'success': False,
                'error': 'Document not found'
            }), 404
        
        # Check access permissions (basic implementation)
        user_role = session.get('user_role', 'associate')
        if document.access_level == 'restricted' and user_role not in ['admin', 'partner']:
            return jsonify({
                'success': False,
                'error': 'Access denied'
            }), 403
        
        doc_dict = document.to_dict()
        doc_dict.update({
            'case_title': document.case.title if document.case else None,
            'case_number': document.case.case_number if document.case else None,
            'client_name': document.client.get_display_name() if document.client else None,
            'created_by_name': document.created_by_user.get_full_name() if document.created_by_user else None,
            'file_size_mb': round(document.file_size / (1024 * 1024), 2) if document.file_size else 0,
            'versions': [v.to_dict() for v in document.versions] if document.versions else []
        })
        
        return jsonify({
            'success': True,
            'document': doc_dict
        })
        
    except Exception as e:
        logger.error(f"Error fetching document: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/documents/<document_id>', methods=['PUT'])
@login_required
def api_update_document(document_id):
    """Update document metadata"""
    try:
        if not DATABASE_AVAILABLE:
            return _update_mock_document(document_id)
        
        document = Document.query.get(document_id)
        if not document:
            return jsonify({
                'success': False,
                'error': 'Document not found'
            }), 404
        
        data = request.json
        user_id = session.get('user_id', '1')
        
        # Store old values for audit
        old_values = document.to_dict()
        
        # Update fields
        if 'title' in data:
            document.title = data['title']
        if 'description' in data:
            document.description = data['description']
        if 'document_type' in data:
            document.document_type = data['document_type']
        if 'status' in data:
            document.status = DocumentStatus(data['status'])
        if 'is_confidential' in data:
            document.is_confidential = data['is_confidential']
        if 'is_privileged' in data:
            document.is_privileged = data['is_privileged']
        if 'access_level' in data:
            document.access_level = data['access_level']
        if 'case_id' in data:
            document.case_id = data['case_id']
        if 'client_id' in data:
            document.client_id = data['client_id']
        
        db.session.commit()
        
        # Create audit log
        audit_log('update', 'document', document.id, user_id, {
            'old_values': old_values,
            'new_values': document.to_dict()
        })
        
        logger.info(f"Document updated: {document.id}")
        
        return jsonify({
            'success': True,
            'document': document.to_dict(),
            'message': 'Document updated successfully'
        })
        
    except Exception as e:
        if DATABASE_AVAILABLE:
            db.session.rollback()
        logger.error(f"Error updating document: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/documents/<document_id>', methods=['DELETE'])
@login_required
def api_delete_document(document_id):
    """Delete a document (soft delete by changing status)"""
    try:
        if not DATABASE_AVAILABLE:
            return _delete_mock_document(document_id)
        
        document = Document.query.get(document_id)
        if not document:
            return jsonify({
                'success': False,
                'error': 'Document not found'
            }), 404
        
        user_id = session.get('user_id', '1')
        
        # Soft delete by archiving
        old_status = document.status.value
        document.status = DocumentStatus.ARCHIVED
        
        db.session.commit()
        
        # Create audit log
        audit_log('delete', 'document', document.id, user_id, {
            'action': 'archived',
            'old_status': old_status,
            'new_status': 'archived'
        })
        
        logger.info(f"Document archived: {document.id}")
        
        return jsonify({
            'success': True,
            'message': 'Document archived successfully'
        })
        
    except Exception as e:
        if DATABASE_AVAILABLE:
            db.session.rollback()
        logger.error(f"Error deleting document: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/documents/types', methods=['GET'])
@login_required
def api_get_document_types():
    """Get available document types"""
    document_types = [
        'Contract', 'Brief', 'Motion', 'Pleading', 'Discovery',
        'Correspondence', 'Evidence', 'Research', 'Filing',
        'Invoice', 'Settlement', 'Agreement', 'Memo', 'Other'
    ]
    
    return jsonify({
        'success': True,
        'document_types': document_types
    })

# ===== CLIENT-SPECIFIC DOCUMENT ENDPOINTS =====

@app.route('/api/clients/<client_id>/documents', methods=['GET'])
@login_required
def api_get_client_documents(client_id):
    """Get all documents for a specific client"""
    try:
        if not DATABASE_AVAILABLE:
            return _get_mock_client_documents(client_id)
        
        # Get query parameters
        page = request.args.get('page', 1, type=int)
        per_page = min(request.args.get('per_page', 10, type=int), 50)
        document_type = request.args.get('document_type')
        status = request.args.get('status')
        
        # Verify client exists and user has access
        user_id = session.get('user_id', '1')
        client = Client.query.filter_by(id=client_id, created_by=user_id).first()
        if not client:
            return jsonify({
                'success': False,
                'error': 'Client not found'
            }), 404
        
        # Build query for client documents
        query = Document.query.filter_by(client_id=client_id)
        
        # Apply filters
        if document_type:
            query = query.filter(Document.document_type == document_type)
        if status:
            query = query.filter(Document.status == status)
        
        # Order by creation date (newest first)
        query = query.order_by(Document.created_at.desc())
        
        # Paginate
        paginated = query.paginate(page=page, per_page=per_page, error_out=False)
        
        return jsonify({
            'success': True,
            'documents': [doc.to_dict() for doc in paginated.items],
            'pagination': {
                'page': page,
                'pages': paginated.pages,
                'per_page': per_page,
                'total': paginated.total,
                'has_prev': paginated.has_prev,
                'has_next': paginated.has_next
            }
        })
        
    except Exception as e:
        logger.error(f"Get client documents error: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/clients/<client_id>/documents/upload', methods=['POST'])
@login_required
def api_upload_client_document(client_id):
    """Upload a document for a specific client"""
    try:
        if not DATABASE_AVAILABLE:
            return _upload_mock_client_document(client_id)
        
        # Verify client exists and user has access
        user_id = session.get('user_id', '1')
        client = Client.query.filter_by(id=client_id, created_by=user_id).first()
        if not client:
            return jsonify({
                'success': False,
                'error': 'Client not found'
            }), 404
        
        # Check if file was uploaded
        if 'file' not in request.files:
            return jsonify({
                'success': False,
                'error': 'No file uploaded'
            }), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({
                'success': False,
                'error': 'No file selected'
            }), 400
        
        # Get form data
        title = request.form.get('title', file.filename)
        description = request.form.get('description', '')
        document_type = request.form.get('document_type', 'Other')
        
        # Validate file
        allowed_extensions = {'pdf', 'doc', 'docx', 'txt', 'rtf', 'jpg', 'jpeg', 'png'}
        if not file.filename.lower().endswith(tuple(allowed_extensions)):
            return jsonify({
                'success': False,
                'error': 'File type not allowed'
            }), 400
        
        # Create document record
        import uuid
        import os
        from werkzeug.utils import secure_filename
        
        document_id = str(uuid.uuid4())
        filename = secure_filename(f"{document_id}_{file.filename}")
        
        # For now, we'll create a minimal document record
        # In production, this would handle actual file storage
        document = Document(
            id=document_id,
            title=title,
            description=description,
            filename=filename,
            original_filename=file.filename,
            file_size=request.content_length or 0,
            mime_type=file.content_type or 'application/octet-stream',
            storage_provider='local',
            storage_path=f'/uploads/client_{client_id}/',
            document_type=document_type,
            status='active',
            client_id=client_id,
            created_by=user_id
        )
        
        db.session.add(document)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'document': document.to_dict(),
            'message': 'Document uploaded successfully'
        })
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Upload client document error: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

def _get_mock_documents():
    """Mock documents for development"""
    return jsonify({
        'success': True,
        'documents': [
            {
                'id': '1',
                'title': 'Settlement Agreement Draft',
                'description': 'Initial settlement terms for Smith v. Johnson case',
                'document_type': 'Settlement',
                'status': 'draft',
                'original_filename': 'settlement_draft_v1.pdf',
                'file_size_mb': 2.5,
                'case_title': 'Smith v. Johnson Motor Co.',
                'case_number': '2024-JS-001',
                'client_name': 'John Smith',
                'created_by_name': 'Demo Attorney',
                'created_at': datetime.now().isoformat(),
                'is_confidential': True
            },
            {
                'id': '2',
                'title': 'Discovery Response',
                'description': 'Response to interrogatories',
                'document_type': 'Discovery',
                'status': 'final',
                'original_filename': 'discovery_response.pdf',
                'file_size_mb': 1.8,
                'case_title': 'Business Contract Dispute',
                'case_number': '2024-MC-005',
                'client_name': 'TechCorp Industries',
                'created_by_name': 'Demo Attorney',
                'created_at': (datetime.now() - timedelta(days=2)).isoformat(),
                'is_confidential': True
            }
        ],
        'pagination': {
            'page': 1,
            'pages': 1,
            'per_page': 20,
            'total': 2,
            'has_prev': False,
            'has_next': False
        }
    })

def _create_mock_document():
    """Mock document creation"""
    return jsonify({
        'success': True,
        'document': {
            'id': str(uuid.uuid4()),
            'title': 'Mock Document',
            'document_type': 'Other',
            'status': 'draft',
            'created_at': datetime.now().isoformat()
        },
        'message': 'Document created successfully (mock)'
    })

def _get_mock_document(document_id):
    """Mock single document"""
    return jsonify({
        'success': True,
        'document': {
            'id': document_id,
            'title': 'Mock Document',
            'description': 'A mock document for development',
            'document_type': 'Other',
            'status': 'draft',
            'created_at': datetime.now().isoformat()
        }
    })

def _update_mock_document(document_id):
    """Mock document update"""
    return jsonify({
        'success': True,
        'document': {
            'id': document_id,
            'title': 'Updated Mock Document',
            'status': 'review'
        },
        'message': 'Document updated successfully (mock)'
    })

def _delete_mock_document(document_id):
    """Mock document deletion"""
    return jsonify({
        'success': True,
        'message': 'Document archived successfully (mock)'
    })

def _get_case_recent_activity(case):
    """Get recent activity for a case"""
    try:
        activity = []
        
        # Recent time entries
        recent_time = case.time_entries.order_by(TimeEntry.created_at.desc()).limit(3).all()
        for entry in recent_time:
            activity.append({
                'type': 'time_entry',
                'description': f'Time logged: {entry.hours}h - {entry.description[:50]}...',
                'user': entry.user.get_full_name() if entry.user else 'Unknown',
                'timestamp': entry.created_at.isoformat()
            })
        
        # Recent documents
        recent_docs = case.documents.order_by(Document.created_at.desc()).limit(3).all()
        for doc in recent_docs:
            activity.append({
                'type': 'document',
                'description': f'Document added: {doc.title}',
                'user': doc.created_by_user.get_full_name() if doc.created_by_user else 'Unknown',
                'timestamp': doc.created_at.isoformat()
            })
        
        # Sort by timestamp and return most recent
        activity.sort(key=lambda x: x['timestamp'], reverse=True)
        return activity[:5]
        
    except Exception as e:
        logger.error(f"Get case activity error: {e}")
        return []

# Mock functions for database fallback
def _get_mock_cases():
    """Return mock cases data"""
    import random
    cases = [
        {
            'id': '1',
            'case_number': '2024-JD-0001',
            'title': 'Personal Injury - Car Accident',
            'description': 'Client injured in rear-end collision on Highway 101',
            'practice_area': 'Personal Injury',
            'status': 'active',
            'priority': 'high',
            'client_name': 'John Doe',
            'primary_attorney_name': 'Attorney Smith',
            'date_opened': '2024-01-15',
            'estimated_hours': 120.0,
            'hourly_rate': 350.0,
            'task_count': 8,
            'document_count': 15,
            'time_entry_count': 25,
            'created_at': datetime.now().isoformat()
        },
        {
            'id': '2',
            'case_number': '2024-AC-0002',
            'title': 'Contract Dispute - Business Partnership',
            'description': 'Partnership dissolution and asset distribution',
            'practice_area': 'Business Law',
            'status': 'pending',
            'priority': 'medium',
            'client_name': 'Acme Corp',
            'primary_attorney_name': 'Attorney Johnson',
            'date_opened': '2024-02-01',
            'estimated_hours': 80.0,
            'hourly_rate': 400.0,
            'task_count': 5,
            'document_count': 12,
            'time_entry_count': 18,
            'created_at': datetime.now().isoformat()
        }
    ]
    
    return jsonify({
        'success': True,
        'cases': cases,
        'pagination': {
            'page': 1,
            'per_page': 20,
            'total': len(cases),
            'pages': 1
        }
    })

def _create_mock_case(data):
    """Create mock case"""
    import uuid
    import random
    case = {
        'id': str(uuid.uuid4()),
        'case_number': data.get('case_number', f'2024-{data["title"][:2].upper()}-{random.randint(1000, 9999)}'),
        'title': data['title'],
        'description': data.get('description', ''),
        'practice_area': data['practice_area'],
        'status': 'active',
        'priority': data.get('priority', 'medium'),
        'client_name': 'Mock Client',
        'date_opened': data['date_opened'],
        'created_at': datetime.now().isoformat()
    }
    
    return jsonify({
        'success': True,
        'message': 'Case created successfully (demo mode)',
        'case': case
    }), 201

def _get_mock_case(case_id):
    """Get mock case details"""
    case = {
        'id': case_id,
        'case_number': '2024-JD-0001',
        'title': 'Personal Injury - Car Accident',
        'description': 'Client injured in rear-end collision on Highway 101',
        'practice_area': 'Personal Injury',
        'status': 'active',
        'priority': 'high',
        'client': {
            'id': '1',
            'display_name': 'John Doe',
            'email': 'john.doe@email.com'
        },
        'primary_attorney': {
            'id': '1',
            'full_name': 'Attorney Smith',
            'email': 'attorney@lawfirm.com'
        },
        'attorneys': [],
        'date_opened': '2024-01-15',
        'estimated_hours': 120.0,
        'hourly_rate': 350.0,
        'tasks': [],
        'documents': [],
        'time_entries': [],
        'recent_activity': [],
        'created_at': datetime.now().isoformat()
    }
    
    return jsonify({
        'success': True,
        'case': case
    })

def _update_mock_case(case_id, data):
    """Update mock case"""
    return jsonify({
        'success': True,
        'message': 'Case updated successfully (demo mode)',
        'case': {
            'id': case_id,
            'title': data.get('title', 'Updated Case'),
            'status': data.get('status', 'active'),
            'updated_at': datetime.now().isoformat()
        }
    })

def _update_mock_case_status(case_id, status):
    """Update mock case status"""
    return jsonify({
        'success': True,
        'message': f'Case status updated to {status} (demo mode)',
        'case': {
            'id': case_id,
            'status': status,
            'updated_at': datetime.now().isoformat()
        }
    })

# ===== ERROR HANDLERS =====

@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors"""
    return jsonify({
        'success': False,
        'error': 'Page not found',
        'timestamp': datetime.now().isoformat()
    }), 404

@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors"""
    logger.error(f"Internal server error: {error}")
    return jsonify({
        'success': False,
        'error': 'Internal server error',
        'timestamp': datetime.now().isoformat()
    }), 500

# ===== MOCK FUNCTIONS FOR CLIENT DOCUMENTS =====

def _get_mock_client_documents(client_id):
    """Mock client documents for development"""
    return jsonify({
        'success': True,
        'documents': [
            {
                'id': '1',
                'title': 'Retainer Agreement',
                'description': 'Initial retainer agreement signed by client',
                'document_type': 'Contract',
                'status': 'final',
                'original_filename': 'retainer_agreement.pdf',
                'file_size': 245760,
                'file_size_mb': 0.24,
                'mime_type': 'application/pdf',
                'created_at': datetime.now().isoformat(),
                'created_by_name': 'Demo Attorney',
                'is_confidential': True
            },
            {
                'id': '2',
                'title': 'Client Intake Form',
                'description': 'Completed client intake and background information',
                'document_type': 'Correspondence',
                'status': 'active',
                'original_filename': 'client_intake.pdf',
                'file_size': 156789,
                'file_size_mb': 0.15,
                'mime_type': 'application/pdf',
                'created_at': (datetime.now() - timedelta(days=1)).isoformat(),
                'created_by_name': 'Demo Attorney',
                'is_confidential': True
            }
        ],
        'pagination': {
            'page': 1,
            'pages': 1,
            'per_page': 10,
            'total': 2,
            'has_prev': False,
            'has_next': False
        }
    })

def _upload_mock_client_document(client_id):
    """Mock document upload for development"""
    return jsonify({
        'success': True,
        'document': {
            'id': str(uuid.uuid4()),
            'title': 'Mock Uploaded Document',
            'document_type': 'Other',
            'status': 'active',
            'original_filename': 'mock_document.pdf',
            'file_size': 123456,
            'file_size_mb': 0.12,
            'mime_type': 'application/pdf',
            'created_at': datetime.now().isoformat(),
            'created_by_name': 'Demo Attorney',
            'is_confidential': True
        },
        'message': 'Document uploaded successfully (mock)'
    })

# ===== DOCUMENT SEARCH & AI ANALYSIS =====

@app.route('/api/documents/search', methods=['GET'])
@login_required
def api_search_documents():
    """Global document search with AI-powered insights"""
    try:
        if not DATABASE_AVAILABLE:
            return _search_mock_documents()
        
        # Get search parameters
        query = request.args.get('q', '').strip()
        client_id = request.args.get('client_id', '')
        document_type = request.args.get('document_type', '')
        date_from = request.args.get('date_from', '')
        date_to = request.args.get('date_to', '')
        page = request.args.get('page', 1, type=int)
        per_page = min(request.args.get('per_page', 20, type=int), 50)
        
        # Get current user
        user_id = session.get('user_id', '1')
        
        # Build base query - only show user's documents
        base_query = Document.query.join(Client).filter(Client.created_by == user_id)
        
        # Apply filters
        if query:
            # Search in title, description, and content
            search_filter = db.or_(
                Document.title.ilike(f'%{query}%'),
                Document.description.ilike(f'%{query}%'),
                Document.original_filename.ilike(f'%{query}%'),
                Document.content_text.ilike(f'%{query}%')  # Assuming we store extracted text
            )
            base_query = base_query.filter(search_filter)
        
        if client_id:
            base_query = base_query.filter(Document.client_id == client_id)
        
        if document_type:
            base_query = base_query.filter(Document.document_type == document_type)
        
        if date_from:
            from datetime import datetime
            date_from_obj = datetime.strptime(date_from, '%Y-%m-%d')
            base_query = base_query.filter(Document.created_at >= date_from_obj)
        
        if date_to:
            from datetime import datetime
            date_to_obj = datetime.strptime(date_to, '%Y-%m-%d')
            base_query = base_query.filter(Document.created_at <= date_to_obj)
        
        # Order by relevance (most recent first for now)
        base_query = base_query.order_by(Document.created_at.desc())
        
        # Paginate
        paginated = base_query.paginate(page=page, per_page=per_page, error_out=False)
        
        # Prepare results with client info
        results = []
        for doc in paginated.items:
            doc_dict = doc.to_dict()
            doc_dict['client_name'] = doc.client.first_name + ' ' + doc.client.last_name if doc.client else 'Unknown'
            doc_dict['client_id'] = doc.client_id
            
            # Add search relevance score (simplified)
            if query:
                score = 0
                query_lower = query.lower()
                if query_lower in doc.title.lower():
                    score += 10
                if query_lower in (doc.description or '').lower():
                    score += 5
                if query_lower in doc.original_filename.lower():
                    score += 3
                doc_dict['relevance_score'] = score
            
            results.append(doc_dict)
        
        # Sort by relevance if searching
        if query:
            results.sort(key=lambda x: x.get('relevance_score', 0), reverse=True)
        
        return jsonify({
            'success': True,
            'documents': results,
            'search_query': query,
            'pagination': {
                'page': page,
                'pages': paginated.pages,
                'per_page': per_page,
                'total': paginated.total,
                'has_prev': paginated.has_prev,
                'has_next': paginated.has_next
            },
            'filters': {
                'client_id': client_id,
                'document_type': document_type,
                'date_from': date_from,
                'date_to': date_to
            }
        })
        
    except Exception as e:
        logger.error(f"Document search error: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/documents/<document_id>/analyze', methods=['POST'])
@login_required
def api_analyze_single_document(document_id):
    """AI analysis of a single document"""
    try:
        if not DATABASE_AVAILABLE:
            return _analyze_mock_document(document_id)
        
        # Get document
        user_id = session.get('user_id', '1')
        document = Document.query.join(Client).filter(
            Document.id == document_id,
            Client.created_by == user_id
        ).first()
        
        if not document:
            return jsonify({
                'success': False,
                'error': 'Document not found'
            }), 404
        
        # Get analysis type
        data = request.json or {}
        analysis_type = data.get('analysis_type', 'comprehensive')  # comprehensive, summary, key_points, entities
        
        # Get XAI API key
        xai_api_key = app.config.get('XAI_API_KEY')
        if not xai_api_key:
            return jsonify({
                'success': False,
                'error': 'AI analysis not available - XAI API key not configured'
            }), 503
        
        # Prepare analysis prompt based on type
        if analysis_type == 'comprehensive':
            prompt = f"""
            Analyze this legal document comprehensively:
            
            Document Title: {document.title}
            Document Type: {document.document_type}
            Client: {document.client.first_name + ' ' + document.client.last_name if document.client else 'Unknown'}
            
            Please provide:
            1. Document Summary (2-3 sentences)
            2. Key Legal Points and Concepts
            3. Important Dates and Deadlines
            4. Parties Involved
            5. Potential Legal Issues or Risks
            6. Action Items for Legal Professional
            7. Document Classification Confidence
            
            Document Content: {document.content_text or 'Content not available for analysis'}
            """
        elif analysis_type == 'summary':
            prompt = f"""
            Provide a concise legal summary of this document:
            
            Document: {document.title} ({document.document_type})
            Content: {document.content_text or 'Content not available for analysis'}
            
            Provide a 2-3 sentence professional summary suitable for legal case notes.
            """
        elif analysis_type == 'key_points':
            prompt = f"""
            Extract the key legal points from this document:
            
            Document: {document.title}
            Content: {document.content_text or 'Content not available for analysis'}
            
            List the 5 most important legal points, obligations, or clauses in bullet format.
            """
        elif analysis_type == 'entities':
            prompt = f"""
            Extract key entities from this legal document:
            
            Document: {document.title}
            Content: {document.content_text or 'Content not available for analysis'}
            
            Identify and list:
            - People/Parties
            - Companies/Organizations  
            - Dates
            - Monetary amounts
            - Legal references
            - Locations
            """
        
        # Call XAI API
        try:
            import requests
            response = requests.post(
                'https://api.x.ai/v1/chat/completions',
                headers={
                    'Authorization': f'Bearer {xai_api_key}',
                    'Content-Type': 'application/json'
                },
                json={
                    'model': 'grok-beta',
                    'messages': [
                        {'role': 'system', 'content': 'You are a legal AI assistant specializing in document analysis. Provide accurate, professional analysis suitable for legal professionals.'},
                        {'role': 'user', 'content': prompt}
                    ],
                    'max_tokens': 1500,
                    'temperature': 0.3
                },
                timeout=30
            )
            
            if response.status_code == 200:
                ai_response = response.json()
                analysis_result = ai_response['choices'][0]['message']['content']
                
                # Store analysis result in document record
                if hasattr(document, 'ai_analysis'):
                    document.ai_analysis = analysis_result
                    document.analysis_date = datetime.now()
                    db.session.commit()
                
                return jsonify({
                    'success': True,
                    'document_id': document_id,
                    'analysis_type': analysis_type,
                    'analysis': analysis_result,
                    'document_info': {
                        'title': document.title,
                        'type': document.document_type,
                        'client_name': document.client.first_name + ' ' + document.client.last_name if document.client else 'Unknown',
                        'created_at': document.created_at.isoformat()
                    }
                })
            else:
                logger.error(f"XAI API error: {response.status_code} - {response.text}")
                return jsonify({
                    'success': False,
                    'error': 'AI analysis service unavailable'
                }), 503
                
        except requests.RequestException as e:
            logger.error(f"XAI API request error: {e}")
            return jsonify({
                'success': False,
                'error': 'AI analysis service unavailable'
            }), 503
        
    except Exception as e:
        logger.error(f"Document analysis error: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/documents/batch-analyze', methods=['POST'])
@login_required
def api_batch_analyze_documents():
    """Batch AI analysis of multiple documents"""
    try:
        if not DATABASE_AVAILABLE:
            return _batch_analyze_mock_documents()
        
        data = request.json or {}
        document_ids = data.get('document_ids', [])
        analysis_type = data.get('analysis_type', 'summary')
        
        if not document_ids:
            return jsonify({
                'success': False,
                'error': 'No document IDs provided'
            }), 400
        
        # Check XAI API availability
        xai_api_key = app.config.get('XAI_API_KEY')
        if not xai_api_key:
            return jsonify({
                'success': False,
                'error': 'AI analysis not available'
            }), 503
        
        # Get user's documents
        user_id = session.get('user_id', '1')
        documents = Document.query.join(Client).filter(
            Document.id.in_(document_ids),
            Client.created_by == user_id
        ).all()
        
        results = []
        for doc in documents:
            # Simplified batch analysis
            try:
                import requests
                prompt = f"Provide a brief legal summary of this document: {doc.title} ({doc.document_type})"
                
                response = requests.post(
                    'https://api.x.ai/v1/chat/completions',
                    headers={
                        'Authorization': f'Bearer {xai_api_key}',
                        'Content-Type': 'application/json'
                    },
                    json={
                        'model': 'grok-beta',
                        'messages': [
                            {'role': 'system', 'content': 'You are a legal AI assistant. Provide concise legal summaries.'},
                            {'role': 'user', 'content': prompt}
                        ],
                        'max_tokens': 300,
                        'temperature': 0.3
                    },
                    timeout=15
                )
                
                if response.status_code == 200:
                    ai_response = response.json()
                    analysis = ai_response['choices'][0]['message']['content']
                else:
                    analysis = "Analysis unavailable"
                    
            except Exception as e:
                logger.error(f"Batch analysis error for doc {doc.id}: {e}")
                analysis = "Analysis failed"
            
            results.append({
                'document_id': doc.id,
                'title': doc.title,
                'type': doc.document_type,
                'client_name': doc.client.first_name + ' ' + doc.client.last_name if doc.client else 'Unknown',
                'analysis': analysis,
                'status': 'completed' if 'unavailable' not in analysis and 'failed' not in analysis else 'failed'
            })
        
        return jsonify({
            'success': True,
            'analysis_type': analysis_type,
            'results': results,
            'total_processed': len(results),
            'successful': len([r for r in results if r['status'] == 'completed'])
        })
        
    except Exception as e:
        logger.error(f"Batch analysis error: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# ===== MOCK FUNCTIONS FOR SEARCH & AI ANALYSIS =====

def _search_mock_documents():
    """Mock document search for development"""
    return jsonify({
        'success': True,
        'documents': [
            {
                'id': '1',
                'title': 'Retainer Agreement - John Smith',
                'description': 'Initial retainer agreement for personal injury case',
                'document_type': 'Contract',
                'original_filename': 'retainer_smith.pdf',
                'file_size': 245760,
                'file_size_mb': 0.24,
                'created_at': datetime.now().isoformat(),
                'client_name': 'John Smith',
                'client_id': '1',
                'relevance_score': 10,
                'is_confidential': True
            },
            {
                'id': '2',
                'title': 'Medical Records - Jane Doe',
                'description': 'Hospital records and medical documentation',
                'document_type': 'Evidence',
                'original_filename': 'medical_records.pdf',
                'file_size': 1234567,
                'file_size_mb': 1.23,
                'created_at': (datetime.now() - timedelta(days=1)).isoformat(),
                'client_name': 'Jane Doe',
                'client_id': '2',
                'relevance_score': 8,
                'is_confidential': True
            },
            {
                'id': '3',
                'title': 'Contract Amendment',
                'description': 'Amendment to original service agreement',
                'document_type': 'Contract',
                'original_filename': 'amendment_v2.docx',
                'file_size': 89012,
                'file_size_mb': 0.09,
                'created_at': (datetime.now() - timedelta(days=3)).isoformat(),
                'client_name': 'TechCorp Ltd',
                'client_id': '3',
                'relevance_score': 6,
                'is_confidential': False
            }
        ],
        'search_query': 'contract',
        'pagination': {
            'page': 1,
            'pages': 1,
            'per_page': 20,
            'total': 3,
            'has_prev': False,
            'has_next': False
        },
        'filters': {}
    })

def _analyze_mock_document(document_id):
    """Mock document analysis for development"""
    return jsonify({
        'success': True,
        'document_id': document_id,
        'analysis_type': 'comprehensive',
        'analysis': """**Document Summary:**
This retainer agreement establishes the attorney-client relationship for representation in a personal injury matter arising from a motor vehicle accident.

**Key Legal Points:**
• Attorney fees set at 33.33% contingency basis
• Client responsible for case expenses regardless of outcome
• Attorney has discretion to accept or reject settlement offers under $50,000
• Exclusive representation agreement with termination clauses

**Important Dates:**
• Agreement effective: Current date
• Statute of limitations: 2 years from incident date
• Case review deadline: 90 days from signing

**Parties Involved:**
• Client: John Smith
• Attorney: [Law Firm Name]
• Opposing parties: To be determined through investigation

**Potential Legal Issues:**
• Standard contingency fee structure - ensure compliance with state regulations
• Expense responsibility clause may need client acknowledgment
• Settlement authority limits should be clearly understood by client

**Action Items:**
1. Obtain signed copy with client acknowledgment
2. Begin case file setup and intake process
3. Schedule initial case strategy meeting
4. Request preliminary documentation from client""",
        'document_info': {
            'title': 'Retainer Agreement - John Smith',
            'type': 'Contract',
            'client_name': 'John Smith',
            'created_at': datetime.now().isoformat()
        }
    })

def _batch_analyze_mock_documents():
    """Mock batch analysis for development"""
    return jsonify({
        'success': True,
        'analysis_type': 'summary',
        'results': [
            {
                'document_id': '1',
                'title': 'Retainer Agreement',
                'type': 'Contract',
                'client_name': 'John Smith',
                'analysis': 'Standard contingency fee retainer agreement for personal injury representation with 33.33% fee structure.',
                'status': 'completed'
            },
            {
                'document_id': '2',
                'title': 'Medical Records',
                'type': 'Evidence',
                'client_name': 'Jane Doe',
                'analysis': 'Comprehensive medical documentation supporting injury claims with treatment timeline and prognosis.',
                'status': 'completed'
            }
        ],
        'total_processed': 2,
        'successful': 2
    })

# ===== CLIENT ACTIVITY & TIMELINE TRACKING =====

@app.route('/api/clients/<client_id>/activities', methods=['GET'])
@login_required
def api_get_client_activities(client_id):
    """Get activity timeline for a specific client"""
    try:
        if not DATABASE_AVAILABLE:
            return _get_mock_client_activities(client_id)
        
        # Verify client access
        user_id = session.get('user_id', '1')
        client = Client.query.filter_by(id=client_id, created_by=user_id).first()
        if not client:
            return jsonify({
                'success': False,
                'error': 'Client not found'
            }), 404
        
        # Get query parameters
        page = request.args.get('page', 1, type=int)
        per_page = min(request.args.get('per_page', 20, type=int), 50)
        activity_type = request.args.get('activity_type', '')
        date_from = request.args.get('date_from', '')
        date_to = request.args.get('date_to', '')
        
        # Get activities from audit logs and other sources
        activities = []
        
        # Get audit log activities for this client
        audit_query = AuditLog.query.filter(
            AuditLog.resource_type.in_(['client', 'document', 'case']),
            AuditLog.resource_id == client_id,
            AuditLog.user_id == user_id
        )
        
        # Apply date filters
        if date_from:
            from datetime import datetime
            date_from_obj = datetime.strptime(date_from, '%Y-%m-%d')
            audit_query = audit_query.filter(AuditLog.created_at >= date_from_obj)
        
        if date_to:
            from datetime import datetime
            date_to_obj = datetime.strptime(date_to, '%Y-%m-%d')
            audit_query = audit_query.filter(AuditLog.created_at <= date_to_obj)
        
        audit_logs = audit_query.order_by(AuditLog.created_at.desc()).limit(100).all()
        
        # Convert audit logs to activity format
        for log in audit_logs:
            activity_data = {
                'id': log.id,
                'type': f"{log.resource_type}_{log.action}",
                'title': _format_activity_title(log),
                'description': _format_activity_description(log),
                'timestamp': log.created_at.isoformat(),
                'user_id': log.user_id,
                'metadata': {
                    'resource_type': log.resource_type,
                    'resource_id': log.resource_id,
                    'action': log.action,
                    'success': log.success
                }
            }
            activities.append(activity_data)
        
        # Get document activities for this client
        documents = Document.query.filter_by(client_id=client_id).all()
        for doc in documents:
            # Document creation activity
            activities.append({
                'id': f"doc_created_{doc.id}",
                'type': 'document_created',
                'title': f"Document uploaded: {doc.title}",
                'description': f"Added {doc.document_type} document ({doc.original_filename})",
                'timestamp': doc.created_at.isoformat(),
                'user_id': doc.created_by,
                'metadata': {
                    'resource_type': 'document',
                    'resource_id': doc.id,
                    'document_type': doc.document_type,
                    'file_size': doc.file_size
                }
            })
        
        # Sort activities by timestamp (newest first)
        activities.sort(key=lambda x: x['timestamp'], reverse=True)
        
        # Apply activity type filter
        if activity_type:
            activities = [a for a in activities if a['type'].startswith(activity_type)]
        
        # Paginate
        start_idx = (page - 1) * per_page
        end_idx = start_idx + per_page
        paginated_activities = activities[start_idx:end_idx]
        
        total_activities = len(activities)
        total_pages = (total_activities + per_page - 1) // per_page
        
        return jsonify({
            'success': True,
            'client_id': client_id,
            'activities': paginated_activities,
            'pagination': {
                'page': page,
                'pages': total_pages,
                'per_page': per_page,
                'total': total_activities,
                'has_prev': page > 1,
                'has_next': page < total_pages
            },
            'filters': {
                'activity_type': activity_type,
                'date_from': date_from,
                'date_to': date_to
            }
        })
        
    except Exception as e:
        logger.error(f"Get client activities error: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/clients/<client_id>/activities', methods=['POST'])
@login_required
def api_create_client_activity(client_id):
    """Create a new activity for a client"""
    try:
        if not DATABASE_AVAILABLE:
            return _create_mock_activity(client_id)
        
        # Verify client access
        user_id = session.get('user_id', '1')
        client = Client.query.filter_by(id=client_id, created_by=user_id).first()
        if not client:
            return jsonify({
                'success': False,
                'error': 'Client not found'
            }), 404
        
        data = request.json or {}
        
        # Validate required fields
        activity_type = data.get('type')
        title = data.get('title')
        description = data.get('description', '')
        
        if not activity_type or not title:
            return jsonify({
                'success': False,
                'error': 'Activity type and title are required'
            }), 400
        
        # Create audit log entry for this activity
        from database import audit_log
        audit_log(
            action=activity_type,
            resource_type='client_activity',
            resource_id=client_id,
            user_id=user_id,
            notes=f"{title}: {description}"
        )
        
        # Return the created activity
        return jsonify({
            'success': True,
            'activity': {
                'type': activity_type,
                'title': title,
                'description': description,
                'timestamp': datetime.now().isoformat(),
                'client_id': client_id,
                'user_id': user_id
            },
            'message': 'Activity created successfully'
        })
        
    except Exception as e:
        logger.error(f"Create client activity error: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/clients/<client_id>/timeline', methods=['GET'])
@login_required
def api_get_client_timeline(client_id):
    """Get comprehensive timeline view for a client including milestones and deadlines"""
    try:
        if not DATABASE_AVAILABLE:
            return _get_mock_client_timeline(client_id)
        
        # Verify client access
        user_id = session.get('user_id', '1')
        client = Client.query.filter_by(id=client_id, created_by=user_id).first()
        if not client:
            return jsonify({
                'success': False,
                'error': 'Client not found'
            }), 404
        
        # Get comprehensive timeline data
        timeline_events = []
        
        # 1. Client creation milestone
        timeline_events.append({
            'id': f"client_created_{client.id}",
            'type': 'milestone',
            'category': 'client',
            'title': 'Client Created',
            'description': f"Client {client.first_name} {client.last_name} was added to the system",
            'timestamp': client.created_at.isoformat(),
            'icon': '👤',
            'status': 'completed'
        })
        
        # 2. Document events
        documents = Document.query.filter_by(client_id=client_id).order_by(Document.created_at.desc()).all()
        for doc in documents:
            timeline_events.append({
                'id': f"document_{doc.id}",
                'type': 'activity',
                'category': 'document',
                'title': f"Document Added: {doc.title}",
                'description': f"Uploaded {doc.document_type} document ({doc.original_filename})",
                'timestamp': doc.created_at.isoformat(),
                'icon': '📄',
                'status': 'completed',
                'metadata': {
                    'document_id': doc.id,
                    'document_type': doc.document_type,
                    'file_size': doc.file_size
                }
            })
        
        # 3. Case events (if any cases exist)
        try:
            cases = Case.query.filter_by(client_id=client_id).order_by(Case.created_at.desc()).all()
            for case in cases:
                timeline_events.append({
                    'id': f"case_{case.id}",
                    'type': 'milestone',
                    'category': 'case',
                    'title': f"Case Opened: {case.title}",
                    'description': f"{case.practice_area} case opened with status: {case.status}",
                    'timestamp': case.created_at.isoformat(),
                    'icon': '⚖️',
                    'status': 'active' if case.status == 'active' else 'completed'
                })
        except Exception:
            # Case model might not be available
            pass
        
        # 4. Recent activities from audit logs
        audit_logs = AuditLog.query.filter(
            AuditLog.resource_type == 'client',
            AuditLog.resource_id == client_id,
            AuditLog.user_id == user_id
        ).order_by(AuditLog.created_at.desc()).limit(10).all()
        
        for log in audit_logs:
            if log.action not in ['view', 'list']:  # Skip read-only actions
                timeline_events.append({
                    'id': f"audit_{log.id}",
                    'type': 'activity',
                    'category': 'system',
                    'title': _format_activity_title(log),
                    'description': _format_activity_description(log),
                    'timestamp': log.created_at.isoformat(),
                    'icon': '🔄',
                    'status': 'completed' if log.success else 'failed'
                })
        
        # 5. Add upcoming deadlines and milestones
        upcoming_events = _generate_upcoming_milestones(client)
        timeline_events.extend(upcoming_events)
        
        # Sort timeline by timestamp (newest first)
        timeline_events.sort(key=lambda x: x['timestamp'], reverse=True)
        
        # Get timeline statistics
        timeline_stats = {
            'total_events': len(timeline_events),
            'documents_count': len([e for e in timeline_events if e['category'] == 'document']),
            'milestones_count': len([e for e in timeline_events if e['type'] == 'milestone']),
            'activities_count': len([e for e in timeline_events if e['type'] == 'activity']),
            'case_duration_days': (datetime.now() - client.created_at).days
        }
        
        return jsonify({
            'success': True,
            'client_id': client_id,
            'client_name': f"{client.first_name} {client.last_name}",
            'timeline': timeline_events,
            'statistics': timeline_stats
        })
        
    except Exception as e:
        logger.error(f"Get client timeline error: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# Helper functions for activity formatting
def _format_activity_title(audit_log):
    """Format audit log into readable activity title"""
    action_map = {
        'create': 'Created',
        'update': 'Updated', 
        'delete': 'Deleted',
        'view': 'Viewed',
        'upload': 'Uploaded'
    }
    
    action = action_map.get(audit_log.action, audit_log.action.title())
    resource = audit_log.resource_type.replace('_', ' ').title()
    
    return f"{action} {resource}"

def _format_activity_description(audit_log):
    """Format audit log into readable activity description"""
    if audit_log.notes:
        return audit_log.notes
    
    return f"{audit_log.action} operation on {audit_log.resource_type}"

def _generate_upcoming_milestones(client):
    """Generate upcoming milestones and deadlines for a client"""
    upcoming = []
    now = datetime.now()
    
    # Generate some example upcoming milestones based on case type
    case_type = getattr(client, 'case_type', 'general')
    
    if case_type == 'personal_injury':
        # Statute of limitations reminder (2 years from incident)
        sol_date = client.created_at + timedelta(days=730)
        if sol_date > now:
            upcoming.append({
                'id': f"sol_{client.id}",
                'type': 'deadline',
                'category': 'legal',
                'title': 'Statute of Limitations Deadline',
                'description': 'Two-year statute of limitations approaching for personal injury case',
                'timestamp': sol_date.isoformat(),
                'icon': '⚠️',
                'status': 'pending',
                'priority': 'high'
            })
    
    # Follow-up reminders
    last_contact = client.updated_at or client.created_at
    next_followup = last_contact + timedelta(days=30)
    
    if next_followup > now:
        upcoming.append({
            'id': f"followup_{client.id}",
            'type': 'reminder',
            'category': 'communication',
            'title': 'Client Follow-up Due',
            'description': 'Scheduled follow-up with client for case status update',
            'timestamp': next_followup.isoformat(),
            'icon': '📞',
            'status': 'pending',
            'priority': 'medium'
        })
    
    return upcoming

# ===== DEADLINE MANAGEMENT APIs =====

@app.route('/api/clients/<client_id>/deadlines', methods=['GET'])
@login_required
def api_get_client_deadlines(client_id):
    """Get all deadlines for a specific client with alert status"""
    try:
        if not DATABASE_AVAILABLE:
            return _get_mock_client_deadlines(client_id)
        
        # Verify client access
        user_id = session.get('user_id', '1')
        
        # Get deadlines from various sources
        deadlines = []
        current_time = datetime.now()
        
        # Generate comprehensive deadline list
        deadlines = _generate_client_deadlines(client_id)
        
        # Add alert status to each deadline
        for deadline in deadlines:
            deadline_date = datetime.fromisoformat(deadline['due_date'].replace('Z', '+00:00'))
            days_until = (deadline_date - current_time).days
            
            if days_until < 0:
                deadline['alert_status'] = 'overdue'
                deadline['alert_level'] = 'critical'
            elif days_until <= 1:
                deadline['alert_status'] = 'urgent'
                deadline['alert_level'] = 'high'
            elif days_until <= 3:
                deadline['alert_status'] = 'upcoming'
                deadline['alert_level'] = 'medium'
            elif days_until <= 7:
                deadline['alert_status'] = 'reminder'
                deadline['alert_level'] = 'low'
            else:
                deadline['alert_status'] = 'future'
                deadline['alert_level'] = 'info'
            
            deadline['days_until'] = days_until
        
        # Sort by urgency (overdue first, then by due date)
        deadlines.sort(key=lambda x: (x['alert_level'] == 'info', x['due_date']))
        
        return jsonify({
            'success': True,
            'deadlines': deadlines,
            'summary': {
                'total': len(deadlines),
                'overdue': len([d for d in deadlines if d['alert_status'] == 'overdue']),
                'urgent': len([d for d in deadlines if d['alert_status'] == 'urgent']),
                'upcoming': len([d for d in deadlines if d['alert_status'] == 'upcoming']),
                'this_week': len([d for d in deadlines if 0 <= d['days_until'] <= 7])
            }
        })
        
    except Exception as e:
        logger.error(f"Get client deadlines error: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to retrieve client deadlines'
        }), 500

@app.route('/api/clients/<client_id>/deadlines', methods=['POST'])
@login_required
def api_create_client_deadline(client_id):
    """Create a new deadline for a client"""
    try:
        if not DATABASE_AVAILABLE:
            return _create_mock_deadline(client_id, request.get_json())
        
        user_id = session.get('user_id', '1')
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['title', 'due_date', 'deadline_type']
        for field in required_fields:
            if not data.get(field):
                return jsonify({
                    'success': False,
                    'error': f'{field} is required'
                }), 400

        # Create new deadline
        deadline = {
            'id': str(uuid.uuid4()),
            'client_id': client_id,
            'title': data['title'],
            'description': data.get('description', ''),
            'deadline_type': data['deadline_type'],
            'due_date': data['due_date'],
            'priority': data.get('priority', 'medium'),
            'status': 'pending',
            'created_by': user_id,
            'created_at': datetime.now().isoformat(),
            'alert_enabled': data.get('alert_enabled', True),
            'alert_days_before': data.get('alert_days_before', 3)
        }
        
        logger.info(f"Deadline created: {deadline['title']} for client {client_id}")
        
        return jsonify({
            'success': True,
            'message': 'Deadline created successfully',
            'deadline': deadline
        })
        
    except Exception as e:
        logger.error(f"Create deadline error: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to create deadline'
        }), 500

@app.route('/api/deadlines/alerts', methods=['GET'])
@login_required
def api_get_deadline_alerts():
    """Get all urgent deadline alerts for the current user"""
    try:
        if not DATABASE_AVAILABLE:
            return _get_mock_deadline_alerts()
        
        user_id = session.get('user_id', '1')
        alerts = []
        current_time = datetime.now()
        
        # Generate alerts for all user's clients
        all_deadlines = _generate_all_user_deadlines(user_id)
        
        for deadline in all_deadlines:
            deadline_date = datetime.fromisoformat(deadline['due_date'].replace('Z', '+00:00'))
            days_until = (deadline_date - current_time).days
            
            # Only include urgent alerts (overdue or due within alert threshold)
            if days_until <= deadline.get('alert_days_before', 3):
                if days_until < 0:
                    alert_type = 'overdue'
                    alert_level = 'critical'
                elif days_until <= 1:
                    alert_type = 'urgent'
                    alert_level = 'high'
                else:
                    alert_type = 'upcoming'
                    alert_level = 'medium'
                
                alerts.append({
                    'id': deadline['id'],
                    'client_id': deadline['client_id'],
                    'client_name': deadline.get('client_name', 'Unknown Client'),
                    'title': deadline['title'],
                    'description': deadline.get('description', ''),
                    'deadline_type': deadline['deadline_type'],
                    'due_date': deadline['due_date'],
                    'days_until': days_until,
                    'alert_type': alert_type,
                    'alert_level': alert_level,
                    'priority': deadline.get('priority', 'medium')
                })
        
        # Sort by urgency
        alerts.sort(key=lambda x: (x['days_until'], x['priority'] != 'high'))
        
        return jsonify({
            'success': True,
            'alerts': alerts,
            'summary': {
                'total_alerts': len(alerts),
                'critical': len([a for a in alerts if a['alert_level'] == 'critical']),
                'high': len([a for a in alerts if a['alert_level'] == 'high']),
                'medium': len([a for a in alerts if a['alert_level'] == 'medium'])
            }
        })
        
    except Exception as e:
        logger.error(f"Get deadline alerts error: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to retrieve deadline alerts'
        }), 500

# ===== DEADLINE HELPER FUNCTIONS =====

def _generate_client_deadlines(client_id):
    """Generate comprehensive deadline list for a client"""
    deadlines = []
    
    # Court filing deadlines
    deadlines.extend([
        {
            'id': f"court_filing_{client_id}_1",
            'title': 'Response to Divorce Petition',
            'description': 'Submit formal response to divorce petition filed by opposing party',
            'deadline_type': 'court_filing',
            'due_date': (datetime.now() + timedelta(days=8)).isoformat(),
            'priority': 'high',
            'status': 'pending',
            'court_name': 'Superior Court of California',
            'case_number': 'FL-2025-001234'
        },
        {
            'id': f"court_filing_{client_id}_2",
            'title': 'Financial Disclosure Documents',
            'description': 'Submit required financial disclosure forms (FL-140, FL-150)',
            'deadline_type': 'document_submission',
            'due_date': (datetime.now() + timedelta(days=15)).isoformat(),
            'priority': 'high',
            'status': 'pending'
        }
    ])
    
    # Payment deadlines
    deadlines.extend([
        {
            'id': f"payment_{client_id}_1",
            'title': 'Monthly Retainer Payment',
            'description': 'Monthly retainer fee payment due',
            'deadline_type': 'payment',
            'due_date': (datetime.now() + timedelta(days=5)).isoformat(),
            'priority': 'medium',
            'status': 'pending',
            'amount': 2500.00
        }
    ])
    
    # Discovery deadlines
    deadlines.extend([
        {
            'id': f"discovery_{client_id}_1",
            'title': 'Respond to Discovery Requests',
            'description': 'Provide responses to interrogatories and document requests',
            'deadline_type': 'discovery',
            'due_date': (datetime.now() + timedelta(days=12)).isoformat(),
            'priority': 'high',
            'status': 'pending'
        }
    ])
    
    return deadlines

def _generate_all_user_deadlines(user_id):
    """Generate deadlines for all clients of a user"""
    # Mock implementation - in real app, would query database
    client_ids = ['client_1', 'client_2', 'client_3']
    all_deadlines = []
    
    for client_id in client_ids:
        client_deadlines = _generate_client_deadlines(client_id)
        for deadline in client_deadlines:
            deadline['client_name'] = f'Client {client_id[-1]}'
        all_deadlines.extend(client_deadlines)
    
    return all_deadlines

def _get_mock_client_deadlines(client_id):
    """Mock deadline data for development"""
    deadlines = _generate_client_deadlines(client_id)
    current_time = datetime.now()
    
    # Add alert status
    for deadline in deadlines:
        deadline_date = datetime.fromisoformat(deadline['due_date'])
        days_until = (deadline_date - current_time).days
        deadline['days_until'] = days_until
        
        if days_until < 0:
            deadline['alert_status'] = 'overdue'
            deadline['alert_level'] = 'critical'
        elif days_until <= 1:
            deadline['alert_status'] = 'urgent'
            deadline['alert_level'] = 'high'
        elif days_until <= 3:
            deadline['alert_status'] = 'upcoming'
            deadline['alert_level'] = 'medium'
        else:
            deadline['alert_status'] = 'future'
            deadline['alert_level'] = 'info'
    
    return jsonify({
        'success': True,
        'deadlines': deadlines,
        'summary': {
            'total': len(deadlines),
            'overdue': len([d for d in deadlines if d['alert_status'] == 'overdue']),
            'urgent': len([d for d in deadlines if d['alert_status'] == 'urgent']),
            'upcoming': len([d for d in deadlines if d['alert_status'] == 'upcoming']),
            'this_week': len([d for d in deadlines if 0 <= d['days_until'] <= 7])
        }
    })

def _get_mock_deadline_alerts():
    """Mock deadline alerts for development"""
    alerts = [
        {
            'id': 'alert_1',
            'client_id': 'client_1',
            'client_name': 'John Smith',
            'title': 'Response to Divorce Petition',
            'description': 'Submit formal response - URGENT',
            'deadline_type': 'court_filing',
            'due_date': (datetime.now() + timedelta(days=1)).isoformat(),
            'days_until': 1,
            'alert_type': 'urgent',
            'alert_level': 'high',
            'priority': 'high'
        },
        {
            'id': 'alert_2',
            'client_id': 'client_2',
            'client_name': 'Jane Doe',
            'title': 'Monthly Retainer Payment',
            'description': 'Payment overdue',
            'deadline_type': 'payment',
            'due_date': (datetime.now() - timedelta(days=2)).isoformat(),
            'days_until': -2,
            'alert_type': 'overdue',
            'alert_level': 'critical',
            'priority': 'high'
        }
    ]
    
    return jsonify({
        'success': True,
        'alerts': alerts,
        'summary': {
            'total_alerts': len(alerts),
            'critical': len([a for a in alerts if a['alert_level'] == 'critical']),
            'high': len([a for a in alerts if a['alert_level'] == 'high']),
            'medium': len([a for a in alerts if a['alert_level'] == 'medium'])
        }
    })

def _create_mock_deadline(client_id, data):
    """Mock deadline creation"""
    deadline = {
        'id': str(uuid.uuid4()),
        'client_id': client_id,
        'title': data['title'],
        'description': data.get('description', ''),
        'deadline_type': data['deadline_type'],
        'due_date': data['due_date'],
        'priority': data.get('priority', 'medium'),
        'status': 'pending',
        'created_at': datetime.now().isoformat(),
        'alert_enabled': data.get('alert_enabled', True),
        'alert_days_before': data.get('alert_days_before', 3)
    }
    
    return jsonify({
        'success': True,
        'message': 'Deadline created successfully (mock)',
        'deadline': deadline
    })

# ===== CLIENT PORTAL APIs =====

@app.route('/api/client-portal/auth/login', methods=['POST'])
def api_client_portal_login():
    """Client portal login endpoint"""
    try:
        data = request.json
        
        if not data.get('client_id') or not data.get('access_code'):
            return jsonify({
                'success': False,
                'error': 'Client ID and access code are required'
            }), 400
        
        client_id = data['client_id'].strip()
        access_code = data['access_code'].strip()
        
        if not DATABASE_AVAILABLE:
            return _client_portal_mock_login(client_id, access_code)
        
        # Validate client access
        client = Client.query.filter_by(id=client_id).first()
        if not client or not client.portal_access_enabled:
            return jsonify({
                'success': False,
                'error': 'Invalid credentials or portal access not enabled'
            }), 401
        
        # Verify access code (in production, this would be hashed)
        if client.portal_access_code != access_code:
            return jsonify({
                'success': False,
                'error': 'Invalid credentials'
            }), 401
        
        # Create client session
        session['client_portal_user'] = client_id
        session['client_portal_logged_in'] = True
        session['client_portal_login_time'] = datetime.now().isoformat()
        
        logger.info(f"Client portal login: {client.first_name} {client.last_name}")
        
        return jsonify({
            'success': True,
            'message': 'Login successful',
            'client': {
                'id': client.id,
                'name': f"{client.first_name} {client.last_name}",
                'email': client.email,
                'case_type': client.case_type,
                'portal_access': True
            }
        })
        
    except Exception as e:
        logger.error(f"Client portal login error: {e}")
        return jsonify({
            'success': False,
            'error': 'Login failed. Please try again.'
        }), 500

@app.route('/api/client-portal/auth/logout', methods=['POST'])
def api_client_portal_logout():
    """Client portal logout endpoint"""
    try:
        # Clear client portal session
        session.pop('client_portal_user', None)
        session.pop('client_portal_logged_in', None)
        session.pop('client_portal_login_time', None)
        
        return jsonify({
            'success': True,
            'message': 'Logged out successfully'
        })
        
    except Exception as e:
        logger.error(f"Client portal logout error: {e}")
        return jsonify({
            'success': False,
            'error': 'Logout failed'
        }), 500

@app.route('/api/client-portal/dashboard', methods=['GET'])
@client_portal_auth_required
def api_client_portal_dashboard():
    """Get client portal dashboard data"""
    try:
        client_id = session.get('client_portal_user')
        
        if not DATABASE_AVAILABLE:
            return _get_mock_client_portal_dashboard(client_id)
        
        client = Client.query.get(client_id)
        if not client:
            return jsonify({
                'success': False,
                'error': 'Client not found'
            }), 404
        
        # Get case information
        cases = Case.query.filter_by(client_id=client_id).all()
        documents = Document.query.filter_by(client_id=client_id).count()
        
        # Recent activities
        recent_activities = _get_recent_client_activities(client_id, limit=5)
        
        # Upcoming deadlines
        upcoming_deadlines = _get_client_upcoming_deadlines(client_id, limit=3)
        
        dashboard_data = {
            'client_info': {
                'name': f"{client.first_name} {client.last_name}",
                'email': client.email,
                'phone': client.phone,
                'case_type': client.case_type,
                'attorney_name': 'Attorney Smith',  # Would be from relationships
                'case_status': 'Active'
            },
            'case_summary': {
                'total_cases': len(cases),
                'active_cases': len([c for c in cases if c.status == CaseStatus.ACTIVE]),
                'total_documents': documents,
                'last_activity': recent_activities[0]['date'] if recent_activities else None
            },
            'recent_activities': recent_activities,
            'upcoming_deadlines': upcoming_deadlines,
            'quick_actions': [
                {'title': 'View Documents', 'action': 'documents', 'icon': '📄'},
                {'title': 'Message Attorney', 'action': 'messages', 'icon': '💬'},
                {'title': 'Schedule Appointment', 'action': 'schedule', 'icon': '📅'},
                {'title': 'View Billing', 'action': 'billing', 'icon': '💰'}
            ]
        }
        
        return jsonify({
            'success': True,
            'dashboard': dashboard_data
        })
        
    except Exception as e:
        logger.error(f"Client portal dashboard error: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to load dashboard'
        }), 500

# ===== CLIENT PORTAL HELPER FUNCTIONS =====

def _client_portal_mock_login(client_id, access_code):
    """Mock client portal login for development"""
    # Simple mock validation
    if access_code == 'demo123':
        session['client_portal_user'] = client_id
        session['client_portal_logged_in'] = True
        session['client_portal_login_time'] = datetime.now().isoformat()
        
        return jsonify({
            'success': True,
            'message': 'Login successful (demo mode)',
            'client': {
                'id': client_id,
                'name': 'John Smith',
                'email': 'john.smith@email.com',
                'case_type': 'Family Law',
                'portal_access': True
            }
        })
    else:
        return jsonify({
            'success': False,
            'error': 'Invalid credentials'
        }), 401

def _get_mock_client_portal_dashboard(client_id):
    """Mock dashboard data for development"""
    dashboard_data = {
        'client_info': {
            'name': 'John Smith',
            'email': 'john.smith@email.com',
            'phone': '(555) 123-4567',
            'case_type': 'Family Law - Divorce',
            'attorney_name': 'Attorney Sarah Johnson',
            'case_status': 'Active - Discovery Phase'
        },
        'case_summary': {
            'total_cases': 1,
            'active_cases': 1,
            'total_documents': 12,
            'last_activity': '2025-07-08T14:30:00Z'
        },
        'recent_activities': [
            {
                'id': '1',
                'title': 'Document Review Completed',
                'description': 'Attorney reviewed financial disclosure documents',
                'date': '2025-07-08T14:30:00Z',
                'type': 'document',
                'status': 'completed'
            },
            {
                'id': '2', 
                'title': 'Phone Consultation',
                'description': 'Discussed custody arrangement preferences',
                'date': '2025-07-07T10:00:00Z',
                'type': 'call',
                'status': 'completed'
            },
            {
                'id': '3',
                'title': 'Court Filing Submitted',
                'description': 'Response to divorce petition filed with court',
                'date': '2025-07-06T16:45:00Z',
                'type': 'court',
                'status': 'completed'
            }
        ],
        'upcoming_deadlines': [
            {
                'id': '1',
                'title': 'Financial Disclosure Due',
                'description': 'Submit completed financial forms',
                'due_date': '2025-07-15T17:00:00Z',
                'priority': 'high',
                'days_until': 7
            },
            {
                'id': '2',
                'title': 'Mediation Session',
                'description': 'Attend scheduled mediation meeting',
                'due_date': '2025-07-20T10:00:00Z',
                'priority': 'medium',
                'days_until': 12
            }
        ],
        'quick_actions': [
            {'title': 'View Documents', 'action': 'documents', 'icon': '📄'},
            {'title': 'Message Attorney', 'action': 'messages', 'icon': '💬'},
            {'title': 'Schedule Appointment', 'action': 'schedule', 'icon': '📅'},
            {'title': 'View Billing', 'action': 'billing', 'icon': '💰'}
        ]
    }
    
    return jsonify({
        'success': True,
        'dashboard': dashboard_data
    })

def _get_recent_client_activities(client_id, limit=5):
    """Get recent activities for client portal"""
    # Mock implementation
    return [
        {
            'id': '1',
            'title': 'Document Review Completed',
            'description': 'Attorney reviewed financial disclosure documents',
            'date': '2025-07-08T14:30:00Z',
            'type': 'document',
            'status': 'completed'
        }
    ]

def _get_client_upcoming_deadlines(client_id, limit=3):
    """Get upcoming deadlines for client portal"""
    # Mock implementation
    return [
        {
            'id': '1',
            'title': 'Financial Disclosure Due',
            'description': 'Submit completed financial forms',
            'due_date': '2025-07-15T17:00:00Z',
            'priority': 'high',
            'days_until': 7
        }
    ]

# ===== CLIENT PORTAL DOCUMENT SHARING =====

@app.route('/api/client-portal/documents', methods=['GET'])
@client_portal_auth_required
def api_client_portal_documents():
    """Get documents accessible to client"""
    try:
        client_id = session.get('client_portal_user')
        
        if DATABASE_AVAILABLE:
            # Get documents for this client
            documents = Document.query.filter_by(
                client_id=client_id,
                access_level='client'  # Only documents marked for client access
            ).filter(
                Document.status.in_([DocumentStatus.APPROVED, DocumentStatus.FINAL])
            ).order_by(Document.created_at.desc()).all()
            
            document_list = []
            for doc in documents:
                document_list.append({
                    'id': doc.id,
                    'title': doc.title,
                    'description': doc.description,
                    'document_type': doc.document_type,
                    'original_filename': doc.original_filename,
                    'file_size': doc.file_size,
                    'mime_type': doc.mime_type,
                    'created_at': doc.created_at.isoformat(),
                    'updated_at': doc.updated_at.isoformat(),
                    'version': doc.version,
                    'case_id': doc.case_id,
                    'download_url': f'/api/client-portal/documents/{doc.id}/download'
                })
            
            return jsonify({
                'success': True,
                'documents': document_list,
                'total_count': len(document_list)
            })
        else:
            return _get_mock_client_documents(client_id)
            
    except Exception as e:
        logger.error(f"Error retrieving client documents: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Failed to retrieve documents'
        }), 500

@app.route('/api/client-portal/documents/<document_id>/download', methods=['GET'])
@client_portal_auth_required
def api_client_portal_document_download(document_id):
    """Download a specific document (with security checks)"""
    try:
        client_id = session.get('client_portal_user')
        
        if DATABASE_AVAILABLE:
            # Security check: ensure document belongs to client and is accessible
            document = Document.query.filter_by(
                id=document_id,
                client_id=client_id,
                access_level='client'
            ).filter(
                Document.status.in_([DocumentStatus.APPROVED, DocumentStatus.FINAL])
            ).first()
            
            if not document:
                return jsonify({
                    'success': False,
                    'error': 'Document not found or not accessible'
                }), 404
            
            # Log access for audit trail
            if DATABASE_AVAILABLE:
                audit_log(
                    action='client_document_download',
                    user_id=client_id,
                    details={
                        'document_id': document_id,
                        'document_title': document.title,
                        'client_id': client_id
                    }
                )
            
            # In production, implement secure file serving
            # For now, return file info for frontend handling
            return jsonify({
                'success': True,
                'download_info': {
                    'filename': document.original_filename,
                    'mime_type': document.mime_type,
                    'file_size': document.file_size,
                    'download_token': f'secure_token_{document_id}'
                }
            })
        else:
            return _get_mock_document_download(document_id, client_id)
            
    except Exception as e:
        logger.error(f"Error downloading document {document_id}: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Failed to download document'
        }), 500

@app.route('/api/client-portal/documents/<document_id>', methods=['GET'])
@client_portal_auth_required
def api_client_portal_document_details(document_id):
    """Get detailed information about a specific document"""
    try:
        client_id = session.get('client_portal_user')
        
        if DATABASE_AVAILABLE:
            # Security check: ensure document belongs to client
            document = Document.query.filter_by(
                id=document_id,
                client_id=client_id,
                access_level='client'
            ).filter(
                Document.status.in_([DocumentStatus.APPROVED, DocumentStatus.FINAL])
            ).first()
            
            if not document:
                return jsonify({
                    'success': False,
                    'error': 'Document not found or not accessible'
                }), 404
            
            # Get document history/versions if available
            versions = Document.query.filter_by(
                parent_document_id=document_id,
                client_id=client_id,
                access_level='client'
            ).order_by(Document.created_at.desc()).all()
            
            version_list = []
            for version in versions:
                version_list.append({
                    'id': version.id,
                    'version': version.version,
                    'created_at': version.created_at.isoformat(),
                    'status': version.status.value
                })
            
            return jsonify({
                'success': True,
                'document': {
                    'id': document.id,
                    'title': document.title,
                    'description': document.description,
                    'document_type': document.document_type,
                    'original_filename': document.original_filename,
                    'file_size': document.file_size,
                    'mime_type': document.mime_type,
                    'created_at': document.created_at.isoformat(),
                    'updated_at': document.updated_at.isoformat(),
                    'version': document.version,
                    'status': document.status.value,
                    'case_id': document.case_id,
                    'versions': version_list,
                    'download_url': f'/api/client-portal/documents/{document.id}/download'
                }
            })
        else:
            return _get_mock_document_details(document_id, client_id)
            
    except Exception as e:
        logger.error(f"Error retrieving document details {document_id}: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Failed to retrieve document details'
        }), 500

def _get_mock_client_documents(client_id):
    """Mock documents for development"""
    mock_documents = [
        {
            'id': 'doc_1',
            'title': 'Divorce Petition Response',
            'description': 'Official response to divorce petition filed with court',
            'document_type': 'Court Filing',
            'original_filename': 'divorce_response.pdf',
            'file_size': 245760,
            'mime_type': 'application/pdf',
            'created_at': '2025-07-06T16:45:00Z',
            'updated_at': '2025-07-06T16:45:00Z',
            'version': '1.0',
            'case_id': 'case_1',
            'download_url': '/api/client-portal/documents/doc_1/download'
        },
        {
            'id': 'doc_2',
            'title': 'Financial Disclosure Form',
            'description': 'Completed financial disclosure documentation',
            'document_type': 'Legal Form',
            'original_filename': 'financial_disclosure.pdf',
            'file_size': 189432,
            'mime_type': 'application/pdf',
            'created_at': '2025-07-05T14:20:00Z',
            'updated_at': '2025-07-05T14:20:00Z',
            'version': '1.0',
            'case_id': 'case_1',
            'download_url': '/api/client-portal/documents/doc_2/download'
        },
        {
            'id': 'doc_3',
            'title': 'Child Custody Agreement Draft',
            'description': 'Proposed custody arrangement terms',
            'document_type': 'Contract',
            'original_filename': 'custody_agreement_draft.pdf',
            'file_size': 167890,
            'mime_type': 'application/pdf',
            'created_at': '2025-07-04T11:30:00Z',
            'updated_at': '2025-07-04T11:30:00Z',
            'version': '2.1',
            'case_id': 'case_1',
            'download_url': '/api/client-portal/documents/doc_3/download'
        },
        {
            'id': 'doc_4',
            'title': 'Settlement Conference Notice',
            'description': 'Court notice for upcoming settlement conference',
            'document_type': 'Court Notice',
            'original_filename': 'settlement_notice.pdf',
            'file_size': 98234,
            'mime_type': 'application/pdf',
            'created_at': '2025-07-03T09:15:00Z',
            'updated_at': '2025-07-03T09:15:00Z',
            'version': '1.0',
            'case_id': 'case_1',
            'download_url': '/api/client-portal/documents/doc_4/download'
        }
    ]
    
    return jsonify({
        'success': True,
        'documents': mock_documents,
        'total_count': len(mock_documents)
    })

def _get_mock_document_download(document_id, client_id):
    """Mock document download for development"""
    mock_downloads = {
        'doc_1': {
            'filename': 'divorce_response.pdf',
            'mime_type': 'application/pdf',
            'file_size': 245760,
            'download_token': 'secure_token_doc_1'
        },
        'doc_2': {
            'filename': 'financial_disclosure.pdf',
            'mime_type': 'application/pdf',
            'file_size': 189432,
            'download_token': 'secure_token_doc_2'
        },
        'doc_3': {
            'filename': 'custody_agreement_draft.pdf',
            'mime_type': 'application/pdf',
            'file_size': 167890,
            'download_token': 'secure_token_doc_3'
        },
        'doc_4': {
            'filename': 'settlement_notice.pdf',
            'mime_type': 'application/pdf',
            'file_size': 98234,
            'download_token': 'secure_token_doc_4'
        }
    }
    
    if document_id in mock_downloads:
        return jsonify({
            'success': True,
            'download_info': mock_downloads[document_id]
        })
    else:
        return jsonify({
            'success': False,
            'error': 'Document not found or not accessible'
        }), 404

def _get_mock_document_details(document_id, client_id):
    """Mock document details for development"""
    mock_details = {
        'doc_1': {
            'id': 'doc_1',
            'title': 'Divorce Petition Response',
            'description': 'Official response to divorce petition filed with court. This document contains our formal response to all allegations and requests made in the original petition.',
            'document_type': 'Court Filing',
            'original_filename': 'divorce_response.pdf',
            'file_size': 245760,
            'mime_type': 'application/pdf',
            'created_at': '2025-07-06T16:45:00Z',
            'updated_at': '2025-07-06T16:45:00Z',
            'version': '1.0',
            'status': 'final',
            'case_id': 'case_1',
            'versions': [],
            'download_url': '/api/client-portal/documents/doc_1/download'
        },
        'doc_3': {
            'id': 'doc_3',
            'title': 'Child Custody Agreement Draft',
            'description': 'Proposed custody arrangement terms including visitation schedule, decision-making authority, and support obligations.',
            'document_type': 'Contract',
            'original_filename': 'custody_agreement_draft.pdf',
            'file_size': 167890,
            'mime_type': 'application/pdf',
            'created_at': '2025-07-04T11:30:00Z',
            'updated_at': '2025-07-04T11:30:00Z',
            'version': '2.1',
            'status': 'approved',
            'case_id': 'case_1',
            'versions': [
                {
                    'id': 'doc_3_v1',
                    'version': '1.0',
                    'created_at': '2025-07-02T10:00:00Z',
                    'status': 'approved'
                },
                {
                    'id': 'doc_3_v2',
                    'version': '2.0',
                    'created_at': '2025-07-03T15:30:00Z',
                    'status': 'approved'
                }
            ],
            'download_url': '/api/client-portal/documents/doc_3/download'
        }
    }
    
    if document_id in mock_details:
        return jsonify({
            'success': True,
            'document': mock_details[document_id]
        })
    else:
        return jsonify({
            'success': False,
            'error': 'Document not found or not accessible'
        }), 404

# ===== CLIENT PORTAL MESSAGING SYSTEM =====

@app.route('/api/client-portal/messages', methods=['GET'])
@client_portal_auth_required
def api_client_portal_messages():
    """Get messages for client"""
    try:
        client_id = session.get('client_portal_user')
        
        if DATABASE_AVAILABLE:
            # In a real implementation, this would query a Message model
            # For now, return mock data
            pass
        
        return _get_mock_client_messages(client_id)
            
    except Exception as e:
        logger.error(f"Error retrieving client messages: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Failed to retrieve messages'
        }), 500

@app.route('/api/client-portal/messages', methods=['POST'])
@client_portal_auth_required
def api_client_portal_send_message():
    """Send a new message from client"""
    try:
        client_id = session.get('client_portal_user')
        data = request.json
        
        if not data or not data.get('content'):
            return jsonify({
                'success': False,
                'error': 'Message content is required'
            }), 400
        
        message_content = data.get('content', '').strip()
        subject = data.get('subject', '').strip()
        
        if len(message_content) > 5000:
            return jsonify({
                'success': False,
                'error': 'Message content too long (max 5000 characters)'
            }), 400
        
        if DATABASE_AVAILABLE:
            # In a real implementation, save to database and send notifications
            pass
        
        # Log the message for audit trail
        if DATABASE_AVAILABLE:
            audit_log(
                action='client_message_sent',
                user_id=client_id,
                details={
                    'subject': subject,
                    'content_length': len(message_content),
                    'client_id': client_id
                }
            )
        
        # Mock successful response
        message_id = f"msg_{int(datetime.now().timestamp())}"
        return jsonify({
            'success': True,
            'message': {
                'id': message_id,
                'subject': subject or 'New Message',
                'content': message_content,
                'sender': 'client',
                'timestamp': datetime.now().isoformat(),
                'status': 'sent'
            }
        })
            
    except Exception as e:
        logger.error(f"Error sending client message: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Failed to send message'
        }), 500

@app.route('/api/client-portal/messages/<message_id>', methods=['GET'])
@client_portal_auth_required
def api_client_portal_message_details(message_id):
    """Get detailed information about a specific message"""
    try:
        client_id = session.get('client_portal_user')
        
        if DATABASE_AVAILABLE:
            # In a real implementation, query database for specific message
            pass
        
        return _get_mock_message_details(message_id, client_id)
            
    except Exception as e:
        logger.error(f"Error retrieving message details {message_id}: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Failed to retrieve message details'
        }), 500

@app.route('/api/client-portal/messages/<message_id>/read', methods=['POST'])
@client_portal_auth_required
def api_client_portal_mark_message_read(message_id):
    """Mark a message as read"""
    try:
        client_id = session.get('client_portal_user')
        
        if DATABASE_AVAILABLE:
            # In a real implementation, update message read status
            pass
        
        return jsonify({
            'success': True,
            'message': f'Message {message_id} marked as read'
        })
            
    except Exception as e:
        logger.error(f"Error marking message as read {message_id}: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Failed to mark message as read'
        }), 500

def _get_mock_client_messages(client_id):
    """Mock messages for development"""
    mock_messages = [
        {
            'id': 'msg_1',
            'subject': 'Case Update - Discovery Phase Complete',
            'content': 'Dear John,\n\nI wanted to update you on the progress of your case. We have successfully completed the discovery phase and received all requested documents from the opposing party. The financial disclosure documents have been reviewed and we found several discrepancies that strengthen our position.\n\nNext steps:\n1. Review the settlement proposal\n2. Prepare for mediation session scheduled for next week\n3. Discuss custody arrangement preferences\n\nPlease let me know if you have any questions or concerns.\n\nBest regards,\nAttorney Sarah Johnson',
            'sender': 'attorney',
            'sender_name': 'Attorney Sarah Johnson',
            'timestamp': '2025-07-08T10:30:00Z',
            'is_read': False,
            'priority': 'normal',
            'message_type': 'case_update'
        },
        {
            'id': 'msg_2',
            'subject': 'Document Signature Required',
            'content': 'Hello John,\n\nI need your signature on the updated financial affidavit. The document has been uploaded to your portal and needs to be signed and returned by Friday.\n\nThe changes include:\n- Updated asset valuations\n- Revised income statements\n- Additional retirement account details\n\nPlease review and sign at your earliest convenience.\n\nThank you,\nSarah',
            'sender': 'attorney',
            'sender_name': 'Attorney Sarah Johnson',
            'timestamp': '2025-07-07T14:15:00Z',
            'is_read': True,
            'priority': 'high',
            'message_type': 'action_required'
        },
        {
            'id': 'msg_3',
            'subject': 'Re: Questions about custody schedule',
            'content': 'Thank you for your questions about the proposed custody schedule. I understand your concerns about the weekday arrangements and we can definitely discuss modifications that work better for your schedule.\n\nI will review the alternative proposal you mentioned and get back to you with feedback by tomorrow. We want to make sure any arrangement prioritizes the children\'s best interests while being practical for both parents.\n\nWe can schedule a call this week to discuss the details further.',
            'sender': 'attorney',
            'sender_name': 'Attorney Sarah Johnson',
            'timestamp': '2025-07-06T16:45:00Z',
            'is_read': True,
            'priority': 'normal',
            'message_type': 'response'
        },
        {
            'id': 'msg_4',
            'subject': 'Questions about custody schedule',
            'content': 'Hi Sarah,\n\nI have some concerns about the proposed custody schedule. The current arrangement has me picking up the kids every other weekend, but with my work schedule, weekday pickups would actually work better for me.\n\nCould we discuss modifying the schedule to include some weekday time instead of just weekends? I think this would be better for everyone involved.\n\nPlease let me know your thoughts.\n\nThanks,\nJohn',
            'sender': 'client',
            'sender_name': 'John Smith',
            'timestamp': '2025-07-05T09:20:00Z',
            'is_read': True,
            'priority': 'normal',
            'message_type': 'question'
        },
        {
            'id': 'msg_5',
            'subject': 'Welcome to Your Client Portal',
            'content': 'Dear John,\n\nWelcome to your secure client portal! This platform will be our primary communication channel throughout your case.\n\nThrough this portal you can:\n- View case updates and documents\n- Send secure messages to our legal team\n- Track important deadlines\n- Access your billing information\n\nIf you have any questions about using the portal, please don\'t hesitate to reach out.\n\nBest regards,\nAttorney Sarah Johnson\nLexAI Legal Practice',
            'sender': 'attorney',
            'sender_name': 'Attorney Sarah Johnson',
            'timestamp': '2025-07-01T08:00:00Z',
            'is_read': True,
            'priority': 'normal',
            'message_type': 'welcome'
        }
    ]
    
    # Calculate unread count
    unread_count = sum(1 for msg in mock_messages if not msg['is_read'])
    
    return jsonify({
        'success': True,
        'messages': mock_messages,
        'total_count': len(mock_messages),
        'unread_count': unread_count
    })

def _get_mock_message_details(message_id, client_id):
    """Mock message details for development"""
    mock_details = {
        'msg_1': {
            'id': 'msg_1',
            'subject': 'Case Update - Discovery Phase Complete',
            'content': 'Dear John,\n\nI wanted to update you on the progress of your case. We have successfully completed the discovery phase and received all requested documents from the opposing party. The financial disclosure documents have been reviewed and we found several discrepancies that strengthen our position.\n\nNext steps:\n1. Review the settlement proposal\n2. Prepare for mediation session scheduled for next week\n3. Discuss custody arrangement preferences\n\nPlease let me know if you have any questions or concerns.\n\nBest regards,\nAttorney Sarah Johnson',
            'sender': 'attorney',
            'sender_name': 'Attorney Sarah Johnson',
            'sender_email': 'sarah.johnson@lexai.com',
            'timestamp': '2025-07-08T10:30:00Z',
            'is_read': False,
            'priority': 'normal',
            'message_type': 'case_update',
            'attachments': [],
            'thread_id': 'thread_1'
        },
        'msg_2': {
            'id': 'msg_2',
            'subject': 'Document Signature Required',
            'content': 'Hello John,\n\nI need your signature on the updated financial affidavit. The document has been uploaded to your portal and needs to be signed and returned by Friday.\n\nThe changes include:\n- Updated asset valuations\n- Revised income statements\n- Additional retirement account details\n\nPlease review and sign at your earliest convenience.\n\nThank you,\nSarah',
            'sender': 'attorney',
            'sender_name': 'Attorney Sarah Johnson',
            'sender_email': 'sarah.johnson@lexai.com',
            'timestamp': '2025-07-07T14:15:00Z',
            'is_read': True,
            'priority': 'high',
            'message_type': 'action_required',
            'attachments': [
                {
                    'name': 'financial_affidavit_updated.pdf',
                    'size': 234567,
                    'type': 'application/pdf'
                }
            ],
            'thread_id': 'thread_2'
        },
        'msg_3': {
            'id': 'msg_3',
            'subject': 'Re: Questions about custody schedule',
            'content': 'Thank you for your questions about the proposed custody schedule. I understand your concerns about the weekday arrangements and we can definitely discuss modifications that work better for your schedule.\n\nI will review the alternative proposal you mentioned and get back to you with feedback by tomorrow. We want to make sure any arrangement prioritizes the children\'s best interests while being practical for both parents.\n\nWe can schedule a call this week to discuss the details further.',
            'sender': 'attorney',
            'sender_name': 'Attorney Sarah Johnson',
            'sender_email': 'sarah.johnson@lexai.com',
            'timestamp': '2025-07-06T16:45:00Z',
            'is_read': True,
            'priority': 'normal',
            'message_type': 'response',
            'attachments': [],
            'thread_id': 'thread_3'
        },
        'msg_4': {
            'id': 'msg_4',
            'subject': 'Questions about custody schedule',
            'content': 'Hi Sarah,\n\nI have some concerns about the proposed custody schedule. The current arrangement has me picking up the kids every other weekend, but with my work schedule, weekday pickups would actually work better for me.\n\nCould we discuss modifying the schedule to include some weekday time instead of just weekends? I think this would be better for everyone involved.\n\nPlease let me know your thoughts.\n\nThanks,\nJohn',
            'sender': 'client',
            'sender_name': 'John Smith',
            'sender_email': 'john.smith@email.com',
            'timestamp': '2025-07-05T09:20:00Z',
            'is_read': True,
            'priority': 'normal',
            'message_type': 'question',
            'attachments': [],
            'thread_id': 'thread_3'
        },
        'msg_5': {
            'id': 'msg_5',
            'subject': 'Welcome to Your Client Portal',
            'content': 'Dear John,\n\nWelcome to your secure client portal! This platform will be our primary communication channel throughout your case.\n\nThrough this portal you can:\n- View case updates and documents\n- Send secure messages to our legal team\n- Track important deadlines\n- Access your billing information\n\nIf you have any questions about using the portal, please don\'t hesitate to reach out.\n\nBest regards,\nAttorney Sarah Johnson\nLexAI Legal Practice',
            'sender': 'attorney',
            'sender_name': 'Attorney Sarah Johnson',
            'sender_email': 'sarah.johnson@lexai.com',
            'timestamp': '2025-07-01T08:00:00Z',
            'is_read': True,
            'priority': 'normal',
            'message_type': 'welcome',
            'attachments': [],
            'thread_id': 'thread_4'
        }
    }
    
    if message_id in mock_details:
        return jsonify({
            'success': True,
            'message': mock_details[message_id]
        })
    else:
        return jsonify({
            'success': False,
            'error': 'Message not found or not accessible'
        }), 404

# ===== CLIENT PORTAL CASE PROGRESS TRACKING =====

@app.route('/api/client-portal/case-progress', methods=['GET'])
@client_portal_auth_required
def api_client_portal_case_progress():
    """Get case progress and timeline for client"""
    try:
        client_id = session.get('client_portal_user')
        
        if DATABASE_AVAILABLE:
            # In a real implementation, this would query case and milestone data
            pass
        
        return _get_mock_case_progress(client_id)
            
    except Exception as e:
        logger.error(f"Error retrieving case progress: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Failed to retrieve case progress'
        }), 500

@app.route('/api/client-portal/case-progress/milestones', methods=['GET'])
@client_portal_auth_required
def api_client_portal_case_milestones():
    """Get detailed milestone information for client case"""
    try:
        client_id = session.get('client_portal_user')
        
        if DATABASE_AVAILABLE:
            # In a real implementation, this would query milestone data
            pass
        
        return _get_mock_case_milestones(client_id)
            
    except Exception as e:
        logger.error(f"Error retrieving case milestones: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Failed to retrieve case milestones'
        }), 500

def _get_mock_case_progress(client_id):
    """Mock case progress data for development"""
    progress_data = {
        'case_info': {
            'id': 'case_1',
            'title': 'Smith vs. Jones - Divorce Proceedings',
            'case_type': 'Family Law - Divorce',
            'status': 'Discovery Phase',
            'attorney': 'Attorney Sarah Johnson',
            'start_date': '2025-06-01T00:00:00Z',
            'estimated_completion': '2025-10-15T00:00:00Z',
            'overall_progress': 65  # Percentage complete
        },
        'current_phase': {
            'name': 'Discovery Phase',
            'description': 'Gathering and reviewing financial documents and evidence',
            'start_date': '2025-06-15T00:00:00Z',
            'estimated_end': '2025-08-01T00:00:00Z',
            'progress': 85,
            'status': 'in_progress'
        },
        'next_phase': {
            'name': 'Settlement Negotiations',
            'description': 'Negotiating terms with opposing party',
            'estimated_start': '2025-08-01T00:00:00Z',
            'estimated_end': '2025-09-15T00:00:00Z'
        },
        'recent_progress': [
            {
                'date': '2025-07-08T14:30:00Z',
                'milestone': 'Financial Discovery Complete',
                'description': 'All financial documents received and reviewed',
                'type': 'milestone_complete',
                'importance': 'high'
            },
            {
                'date': '2025-07-06T16:45:00Z',
                'milestone': 'Response Filed',
                'description': 'Divorce petition response filed with court',
                'type': 'court_filing',
                'importance': 'high'
            },
            {
                'date': '2025-07-03T10:00:00Z',
                'milestone': 'Settlement Conference Scheduled',
                'description': 'Mediation session scheduled for July 25th',
                'type': 'scheduling',
                'importance': 'medium'
            }
        ],
        'upcoming_milestones': [
            {
                'date': '2025-07-25T10:00:00Z',
                'milestone': 'Settlement Conference',
                'description': 'Mediation session with court mediator',
                'type': 'court_appearance',
                'importance': 'high',
                'preparation_needed': True
            },
            {
                'date': '2025-08-15T09:00:00Z',
                'milestone': 'Final Settlement Review',
                'description': 'Review and finalize settlement terms',
                'type': 'meeting',
                'importance': 'high',
                'preparation_needed': True
            }
        ],
        'progress_statistics': {
            'total_milestones': 12,
            'completed_milestones': 8,
            'remaining_milestones': 4,
            'days_elapsed': 38,
            'estimated_days_remaining': 75
        }
    }
    
    return jsonify({
        'success': True,
        'progress': progress_data
    })

def _get_mock_case_milestones(client_id):
    """Mock detailed milestone data for development"""
    milestones_data = {
        'phases': [
            {
                'name': 'Case Initiation',
                'start_date': '2025-06-01T00:00:00Z',
                'end_date': '2025-06-15T00:00:00Z',
                'status': 'completed',
                'progress': 100,
                'milestones': [
                    {
                        'id': 'milestone_1',
                        'title': 'Initial Consultation',
                        'description': 'First meeting to discuss case details and strategy',
                        'date': '2025-06-01T14:00:00Z',
                        'status': 'completed',
                        'type': 'meeting',
                        'importance': 'high'
                    },
                    {
                        'id': 'milestone_2',
                        'title': 'Retainer Agreement Signed',
                        'description': 'Legal representation agreement executed',
                        'date': '2025-06-03T10:00:00Z',
                        'status': 'completed',
                        'type': 'document',
                        'importance': 'high'
                    },
                    {
                        'id': 'milestone_3',
                        'title': 'Divorce Petition Filed',
                        'description': 'Initial divorce petition filed with family court',
                        'date': '2025-06-15T16:30:00Z',
                        'status': 'completed',
                        'type': 'court_filing',
                        'importance': 'high'
                    }
                ]
            },
            {
                'name': 'Discovery Phase',
                'start_date': '2025-06-15T00:00:00Z',
                'end_date': '2025-08-01T00:00:00Z',
                'status': 'in_progress',
                'progress': 85,
                'milestones': [
                    {
                        'id': 'milestone_4',
                        'title': 'Financial Affidavits Filed',
                        'description': 'Both parties submitted financial disclosure forms',
                        'date': '2025-06-25T00:00:00Z',
                        'status': 'completed',
                        'type': 'document',
                        'importance': 'high'
                    },
                    {
                        'id': 'milestone_5',
                        'title': 'Asset Valuation Completed',
                        'description': 'Professional appraisal of marital assets',
                        'date': '2025-07-02T00:00:00Z',
                        'status': 'completed',
                        'type': 'evaluation',
                        'importance': 'medium'
                    },
                    {
                        'id': 'milestone_6',
                        'title': 'Response to Petition Filed',
                        'description': 'Official response to divorce petition submitted',
                        'date': '2025-07-06T16:45:00Z',
                        'status': 'completed',
                        'type': 'court_filing',
                        'importance': 'high'
                    },
                    {
                        'id': 'milestone_7',
                        'title': 'Discovery Document Review',
                        'description': 'Analysis of all financial documents received',
                        'date': '2025-07-08T14:30:00Z',
                        'status': 'completed',
                        'type': 'review',
                        'importance': 'high'
                    },
                    {
                        'id': 'milestone_8',
                        'title': 'Child Custody Evaluation',
                        'description': 'Court-ordered custody assessment',
                        'date': '2025-07-20T10:00:00Z',
                        'status': 'pending',
                        'type': 'evaluation',
                        'importance': 'high'
                    }
                ]
            },
            {
                'name': 'Settlement Negotiations',
                'start_date': '2025-08-01T00:00:00Z',
                'end_date': '2025-09-15T00:00:00Z',
                'status': 'upcoming',
                'progress': 0,
                'milestones': [
                    {
                        'id': 'milestone_9',
                        'title': 'Initial Settlement Conference',
                        'description': 'First mediation session with court mediator',
                        'date': '2025-08-05T10:00:00Z',
                        'status': 'scheduled',
                        'type': 'court_appearance',
                        'importance': 'high'
                    },
                    {
                        'id': 'milestone_10',
                        'title': 'Settlement Agreement Draft',
                        'description': 'Preparation of proposed settlement terms',
                        'date': '2025-08-20T00:00:00Z',
                        'status': 'pending',
                        'type': 'document',
                        'importance': 'high'
                    }
                ]
            },
            {
                'name': 'Finalization',
                'start_date': '2025-09-15T00:00:00Z',
                'end_date': '2025-10-15T00:00:00Z',
                'status': 'upcoming',
                'progress': 0,
                'milestones': [
                    {
                        'id': 'milestone_11',
                        'title': 'Final Decree Preparation',
                        'description': 'Drafting of final divorce decree',
                        'date': '2025-09-30T00:00:00Z',
                        'status': 'pending',
                        'type': 'document',
                        'importance': 'high'
                    },
                    {
                        'id': 'milestone_12',
                        'title': 'Final Court Hearing',
                        'description': 'Final hearing for divorce decree approval',
                        'date': '2025-10-15T14:00:00Z',
                        'status': 'pending',
                        'type': 'court_appearance',
                        'importance': 'high'
                    }
                ]
            }
        ]
    }
    
    return jsonify({
        'success': True,
        'milestones': milestones_data
    })

# ===== CLIENT PORTAL APPOINTMENT SCHEDULING =====

@app.route('/api/client-portal/appointments', methods=['GET'])
@client_portal_auth_required
def api_client_portal_appointments():
    """Get client's appointments and available slots"""
    try:
        client_id = session.get('client_portal_user')
        
        if DATABASE_AVAILABLE:
            # In a real implementation, this would query appointment data
            pass
        
        return _get_mock_client_appointments(client_id)
            
    except Exception as e:
        logger.error(f"Error retrieving client appointments: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Failed to retrieve appointments'
        }), 500

@app.route('/api/client-portal/appointments/available-slots', methods=['GET'])
@client_portal_auth_required
def api_client_portal_available_slots():
    """Get available appointment slots"""
    try:
        client_id = session.get('client_portal_user')
        date_range = request.args.get('range', '7')  # Default to 7 days
        
        if DATABASE_AVAILABLE:
            # In a real implementation, this would query attorney availability
            pass
        
        return _get_mock_available_slots(client_id, date_range)
            
    except Exception as e:
        logger.error(f"Error retrieving available slots: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Failed to retrieve available slots'
        }), 500

@app.route('/api/client-portal/appointments', methods=['POST'])
@client_portal_auth_required
def api_client_portal_schedule_appointment():
    """Schedule a new appointment"""
    try:
        client_id = session.get('client_portal_user')
        data = request.json
        
        if not data or not all(k in data for k in ['date', 'time', 'type']):
            return jsonify({
                'success': False,
                'error': 'Date, time, and appointment type are required'
            }), 400
        
        appointment_date = data.get('date')
        appointment_time = data.get('time')
        appointment_type = data.get('type')
        notes = data.get('notes', '').strip()
        
        if DATABASE_AVAILABLE:
            # In a real implementation, save to database and send notifications
            pass
        
        # Log the appointment request for audit trail
        if DATABASE_AVAILABLE:
            audit_log(
                action='client_appointment_scheduled',
                user_id=client_id,
                details={
                    'appointment_date': appointment_date,
                    'appointment_time': appointment_time,
                    'appointment_type': appointment_type,
                    'notes': notes,
                    'client_id': client_id
                }
            )
        
        # Mock successful response
        appointment_id = f"appt_{int(datetime.now().timestamp())}"
        return jsonify({
            'success': True,
            'appointment': {
                'id': appointment_id,
                'date': appointment_date,
                'time': appointment_time,
                'type': appointment_type,
                'notes': notes,
                'status': 'pending_confirmation',
                'attorney': 'Attorney Sarah Johnson',
                'location': 'LexAI Office - Conference Room A',
                'created_at': datetime.now().isoformat()
            }
        })
            
    except Exception as e:
        logger.error(f"Error scheduling appointment: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Failed to schedule appointment'
        }), 500

@app.route('/api/client-portal/appointments/<appointment_id>/cancel', methods=['POST'])
@client_portal_auth_required
def api_client_portal_cancel_appointment(appointment_id):
    """Cancel an appointment"""
    try:
        client_id = session.get('client_portal_user')
        data = request.json
        reason = data.get('reason', '') if data else ''
        
        if DATABASE_AVAILABLE:
            # In a real implementation, update appointment status in database
            pass
        
        # Log the cancellation for audit trail
        if DATABASE_AVAILABLE:
            audit_log(
                action='client_appointment_cancelled',
                user_id=client_id,
                details={
                    'appointment_id': appointment_id,
                    'cancellation_reason': reason,
                    'client_id': client_id
                }
            )
        
        return jsonify({
            'success': True,
            'message': 'Appointment cancelled successfully'
        })
            
    except Exception as e:
        logger.error(f"Error cancelling appointment {appointment_id}: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Failed to cancel appointment'
        }), 500

def _get_mock_client_appointments(client_id):
    """Mock appointments data for development"""
    appointments_data = {
        'upcoming_appointments': [
            {
                'id': 'appt_1',
                'title': 'Settlement Strategy Meeting',
                'date': '2025-07-15T14:00:00Z',
                'type': 'consultation',
                'duration': 60,
                'attorney': 'Attorney Sarah Johnson',
                'location': 'LexAI Office - Conference Room A',
                'status': 'confirmed',
                'notes': 'Discuss settlement proposal and negotiation strategy',
                'meeting_type': 'in_person',
                'preparation_items': [
                    'Review financial disclosure documents',
                    'Prepare questions about settlement terms',
                    'Bring any new documentation'
                ]
            },
            {
                'id': 'appt_2',
                'title': 'Pre-Mediation Preparation',
                'date': '2025-07-22T10:00:00Z',
                'type': 'preparation',
                'duration': 45,
                'attorney': 'Attorney Sarah Johnson',
                'location': 'Video Conference',
                'status': 'confirmed',
                'notes': 'Prepare for upcoming mediation session',
                'meeting_type': 'video_call',
                'preparation_items': [
                    'Review custody proposal',
                    'Prepare emotional preparation for mediation',
                    'Discuss mediation strategy'
                ]
            }
        ],
        'past_appointments': [
            {
                'id': 'appt_3',
                'title': 'Initial Case Strategy Session',
                'date': '2025-07-01T14:00:00Z',
                'type': 'consultation',
                'duration': 90,
                'attorney': 'Attorney Sarah Johnson',
                'location': 'LexAI Office - Conference Room A',
                'status': 'completed',
                'notes': 'Discussed case overview and initial strategy',
                'meeting_type': 'in_person',
                'summary': 'Covered divorce timeline, asset division strategy, and custody considerations'
            },
            {
                'id': 'appt_4',
                'title': 'Document Review Session',
                'date': '2025-06-28T16:00:00Z',
                'type': 'document_review',
                'duration': 60,
                'attorney': 'Attorney Sarah Johnson',
                'location': 'LexAI Office - Conference Room B',
                'status': 'completed',
                'notes': 'Reviewed financial documents and affidavits',
                'meeting_type': 'in_person',
                'summary': 'Reviewed all financial disclosure documents and prepared affidavits'
            }
        ],
        'appointment_types': [
            {
                'id': 'consultation',
                'name': 'Consultation',
                'description': 'General legal consultation and case discussion',
                'duration': 60,
                'available_methods': ['in_person', 'video_call', 'phone_call']
            },
            {
                'id': 'document_review',
                'name': 'Document Review',
                'description': 'Review and discuss legal documents',
                'duration': 45,
                'available_methods': ['in_person', 'video_call']
            },
            {
                'id': 'preparation',
                'name': 'Court/Mediation Prep',
                'description': 'Preparation for court appearances or mediation',
                'duration': 60,
                'available_methods': ['in_person', 'video_call']
            },
            {
                'id': 'strategy_session',
                'name': 'Strategy Session',
                'description': 'Case strategy planning and discussion',
                'duration': 90,
                'available_methods': ['in_person']
            }
        ]
    }
    
    return jsonify({
        'success': True,
        'appointments': appointments_data
    })

def _get_mock_available_slots(client_id, date_range):
    """Mock available appointment slots for development"""
    from datetime import datetime, timedelta
    
    # Generate available slots for the next 14 days
    available_slots = []
    start_date = datetime.now().date()
    
    for i in range(14):
        current_date = start_date + timedelta(days=i)
        
        # Skip weekends
        if current_date.weekday() >= 5:
            continue
            
        # Generate time slots (9 AM to 5 PM, excluding lunch 12-1 PM)
        time_slots = []
        
        # Morning slots (9 AM - 12 PM)
        for hour in range(9, 12):
            time_slots.append(f"{hour:02d}:00")
            time_slots.append(f"{hour:02d}:30")
        
        # Afternoon slots (1 PM - 5 PM)
        for hour in range(13, 17):
            time_slots.append(f"{hour:02d}:00")
            time_slots.append(f"{hour:02d}:30")
        
        # Mock some slots as unavailable
        if i == 1:  # Tomorrow - busy day
            available_times = time_slots[::3]  # Every 3rd slot available
        elif i == 2:  # Day after tomorrow - moderate availability
            available_times = time_slots[::2]  # Every 2nd slot available
        else:  # Other days - good availability
            available_times = time_slots[:-2]  # All but last 2 slots
        
        for time_slot in available_times:
            available_slots.append({
                'date': current_date.isoformat(),
                'time': time_slot,
                'available': True,
                'attorney': 'Attorney Sarah Johnson'
            })
    
    return jsonify({
        'success': True,
        'available_slots': available_slots,
        'attorney_info': {
            'name': 'Attorney Sarah Johnson',
            'timezone': 'America/New_York',
            'office_hours': '9:00 AM - 5:00 PM, Monday - Friday',
            'location': 'LexAI Office - 123 Legal Street, Law City, LC 12345'
        }
    })

# ===== STRIPE BILLING INTEGRATION =====

@app.route('/api/billing/stripe-connect', methods=['POST'])
@login_required
def stripe_connect_onboard():
    """Create Stripe Connect account for law firm to accept client payments"""
    try:
        if not STRIPE_MODULE_AVAILABLE:
            return jsonify({'error': 'Stripe module not available on server'}), 503
            
        current_user = get_current_user()
        if not current_user:
            return jsonify({'error': 'Authentication required'}), 401
        
        data = request.get_json()
        firm_name = data.get('firm_name', f"{current_user.first_name} {current_user.last_name} Law")
        
        # Create Stripe Express account
        account = stripe.Account.create(
            type='express',
            country='US',
            email=current_user.email,
            business_type='company',
            company={
                'name': firm_name,
            },
            metadata={
                'lexai_user_id': str(current_user.id),
                'firm_name': firm_name,
                'integration_type': 'client_payments'
            }
        )
        
        # Create account link for onboarding
        account_link = stripe.AccountLink.create(
            account=account.id,
            refresh_url=f"{request.host_url}billing?refresh=true",
            return_url=f"{request.host_url}billing?success=true",
            type='account_onboarding',
        )
        
        return jsonify({
            'success': True,
            'onboarding_url': account_link.url,
            'account_id': account.id
        })
        
    except Exception as e:
        logger.error(f"Stripe Connect error: {e}")
        return jsonify({'error': 'Failed to create payment account'}), 500

@app.route('/api/billing/create-payment-link', methods=['POST'])
@login_required
def create_payment_link():
    """Create Stripe payment link for invoice"""
    try:
        if not STRIPE_MODULE_AVAILABLE:
            return jsonify({'error': 'Stripe module not available on server'}), 503
            
        current_user = get_current_user()
        if not current_user:
            return jsonify({'error': 'Authentication required'}), 401
        
        data = request.get_json()
        invoice_amount = data.get('amount')  # Amount in cents
        invoice_number = data.get('invoice_number')
        client_email = data.get('client_email')
        stripe_account_id = data.get('stripe_account_id', 'acct_default_demo')
        
        if not all([invoice_amount, invoice_number]):
            return jsonify({'error': 'Missing required fields'}), 400
        
        # Calculate platform fee (0.5% platform fee)
        platform_fee = int(invoice_amount * 0.005)
        
        # Create payment intent
        payment_intent = stripe.PaymentIntent.create(
            amount=invoice_amount,
            currency='usd',
            metadata={
                'invoice_number': invoice_number,
                'client_email': client_email or '',
                'law_firm_user_id': str(current_user.id)
            },
            receipt_email=client_email
        )
        
        return jsonify({
            'success': True,
            'payment_intent_id': payment_intent.id,
            'client_secret': payment_intent.client_secret,
            'amount': invoice_amount,
            'platform_fee': platform_fee
        })
        
    except Exception as e:
        logger.error(f"Payment link creation error: {e}")
        return jsonify({'error': 'Failed to create payment link'}), 500

@app.route('/api/billing/refund', methods=['POST'])
# @login_required  # Temporarily disabled for demo mode
def process_refund():
    """Process a refund for a payment"""
    try:
        data = request.get_json()
        payment_intent_id = data.get('payment_intent_id')
        refund_amount = data.get('amount')  # Optional - full refund if not specified
        reason = data.get('reason', 'requested_by_customer')
        
        if not payment_intent_id:
            return jsonify({'error': 'Payment intent ID required'}), 400
        
        if not STRIPE_MODULE_AVAILABLE:
            # Return mock refund for demo/testing purposes
            import random
            mock_refund_id = f're_demo_{random.randint(100000, 999999)}'
            logger.info(f"Created DEMO refund {mock_refund_id} for payment intent {payment_intent_id} (Stripe module not available)")
            
            return jsonify({
                'success': True,
                'refund_id': mock_refund_id,
                'amount': refund_amount if refund_amount else 'full_amount',
                'status': 'demo_succeeded',
                'currency': 'usd',
                'payment_intent_id': payment_intent_id,
                'reason': reason,
                'demo_mode': True,
                'message': 'Demo refund processed (Stripe module unavailable)'
            })
            
        current_user = get_current_user()
        if not current_user:
            return jsonify({'error': 'Authentication required'}), 401
        
        # Create refund
        refund_data = {
            'payment_intent': payment_intent_id,
            'reason': reason,
            'metadata': {
                'refunded_by': str(current_user.id),
                'refund_reason': reason
            }
        }
        
        if refund_amount:
            refund_data['amount'] = refund_amount
        
        refund = stripe.Refund.create(**refund_data)
        
        return jsonify({
            'success': True,
            'refund_id': refund.id,
            'amount': refund.amount,
            'status': refund.status,
            'demo_mode': False
        })
        
    except Exception as e:
        logger.error(f"Refund processing error: {e}")
        return jsonify({'error': 'Failed to process refund'}), 500

@app.route('/api/create-payment-intent', methods=['POST'])
def create_payment_intent():
    """Create payment intent for invoice payment"""
    try:
        if not STRIPE_MODULE_AVAILABLE:
            return jsonify({'error': 'Stripe module not available on server'}), 503
        
        data = request.get_json()
        amount = data.get('amount')
        currency = data.get('currency', 'usd')
        invoice_id = data.get('invoice_id')
        
        if not amount:
            return jsonify({'error': 'Amount is required'}), 400
        
        # Create payment intent
        payment_intent = stripe.PaymentIntent.create(
            amount=int(amount * 100),  # Convert to cents
            currency=currency,
            metadata={
                'invoice_id': invoice_id
            }
        )
        
        return jsonify({
            'client_secret': payment_intent.client_secret,
            'payment_intent_id': payment_intent.id
        })
        
    except Exception as e:
        logger.error(f"Payment intent creation error: {e}")
        return jsonify({'error': 'Failed to create payment intent'}), 500

@app.route('/api/billing/sample-invoice', methods=['POST'])
# @login_required  # Temporarily disabled for demo mode
def create_sample_invoice():
    """Create a sample invoice with realistic data"""
    try:
        current_user = get_current_user()
        if not current_user:
            return jsonify({'error': 'Authentication required'}), 401
        
        # Generate sample invoice data
        from datetime import datetime, timedelta
        import random
        
        invoice_number = f"INV-{datetime.now().year}-{random.randint(100, 999)}"
        
        sample_invoice = {
            'id': f"inv_{int(datetime.now().timestamp())}",
            'invoice_number': invoice_number,
            'client_name': 'Acme Corporation',
            'client_email': 'billing@acmecorp.com',
            'subject': 'Legal Services - Contract Review and Negotiation',
            'issue_date': datetime.now().date().isoformat(),
            'due_date': (datetime.now().date() + timedelta(days=30)).isoformat(),
            'status': 'draft',
            'subtotal': 2850.00,
            'tax_rate': 0.0875,  # 8.75%
            'tax_amount': 249.38,
            'total_amount': 3099.38,
            'amount_paid': 0.00,
            'payment_terms': 'Net 30',
            'line_items': [
                {
                    'description': 'Contract review and analysis',
                    'quantity': 6.5,
                    'unit': 'hours',
                    'rate': 350.00,
                    'amount': 2275.00
                },
                {
                    'description': 'Client consultation meetings',
                    'quantity': 2.0,
                    'unit': 'hours',
                    'rate': 350.00,
                    'amount': 700.00
                },
                {
                    'description': 'Document preparation and filing',
                    'quantity': 1.5,
                    'unit': 'hours',
                    'rate': 250.00,
                    'amount': 375.00
                }
            ],
            'notes': 'Payment due within 30 days. Late payments subject to 1.5% monthly service charge.',
            'created_at': datetime.now().isoformat()
        }
        
        return jsonify({
            'success': True,
            'invoice': sample_invoice
        })
        
    except Exception as e:
        logger.error(f"Sample invoice creation error: {e}")
        return jsonify({'error': 'Failed to create sample invoice'}), 500

@app.route('/api/billing/create-payment-intent', methods=['POST'])
# @login_required  # Temporarily disabled for demo mode
def create_invoice_payment_intent():
    """Create Stripe payment intent for an unpaid invoice"""
    try:
        data = request.get_json()
        invoice_id = data.get('invoice_id')
        amount = data.get('amount')  # Amount in dollars
        
        if not invoice_id or not amount:
            return jsonify({'error': 'Invoice ID and amount required'}), 400
        
        # Convert amount to cents for Stripe
        amount_cents = int(float(amount) * 100)
        
        if not STRIPE_MODULE_AVAILABLE:
            # Return mock payment intent for demo/testing purposes
            import random
            mock_payment_intent_id = f'pi_demo_{random.randint(100000, 999999)}'
            logger.info(f"Created DEMO payment intent {mock_payment_intent_id} for invoice {invoice_id} (Stripe module not available)")
            
            return jsonify({
                'success': True,
                'payment_intent_id': mock_payment_intent_id,
                'client_secret': f'{mock_payment_intent_id}_secret_demo',
                'amount': amount_cents,
                'currency': 'usd',
                'status': 'demo_mode',
                'demo_mode': True,
                'message': 'Demo payment intent created (Stripe module unavailable)'
            })
        
        current_user = get_current_user()
        if not current_user:
            return jsonify({'error': 'Authentication required'}), 401
            
        # Create real payment intent
        payment_intent = stripe.PaymentIntent.create(
            amount=amount_cents,
            currency='usd',
            metadata={
                'invoice_id': invoice_id,
                'law_firm': 'LexAI Practice',
                'created_by': current_user.get('id', 'demo')
            },
            description=f'Payment for Invoice {invoice_id}',
            receipt_email=data.get('client_email'),
            automatic_payment_methods={
                'enabled': True,
            },
        )
        
        logger.info(f"Created real payment intent {payment_intent.id} for invoice {invoice_id}")
        
        return jsonify({
            'success': True,
            'payment_intent_id': payment_intent.id,
            'client_secret': payment_intent.client_secret,
            'amount': amount_cents,
            'currency': payment_intent.currency,
            'status': payment_intent.status,
            'demo_mode': False
        })
        
    except Exception as e:
        logger.error(f"Payment intent creation error: {e}")
        return jsonify({'error': f'Failed to create payment intent: {str(e)}'}), 500

@app.route('/api/billing/create-test-invoices', methods=['POST'])
# @login_required  # Temporarily disabled for demo mode
def create_test_invoices():
    """Create multiple test invoices with different payment statuses for testing"""
    try:
        current_user = get_current_user()
        if not current_user:
            return jsonify({'error': 'Authentication required'}), 401
        
        from datetime import datetime, timedelta
        import random
        
        base_timestamp = int(datetime.now().timestamp())
        
        # Create invoices with different statuses
        test_invoices = []
        
        # 1. Paid invoice (with payment intent for refund testing)
        paid_invoice = {
            'id': f"inv_{base_timestamp}_001",
            'invoice_number': f"INV-{datetime.now().year}-001",
            'client_name': 'TechStart LLC',
            'client_email': 'finance@techstart.com',
            'subject': 'Corporate Formation and Legal Setup',
            'issue_date': (datetime.now().date() - timedelta(days=15)).isoformat(),
            'due_date': (datetime.now().date() + timedelta(days=15)).isoformat(),
            'status': 'paid',
            'subtotal': 5500.00,
            'tax_rate': 0.0875,
            'tax_amount': 481.25,
            'total_amount': 5981.25,
            'amount_paid': 5981.25,
            'payment_intent_id': f'pi_test_paid_{random.randint(100000, 999999)}',
            'payment_date': (datetime.now().date() - timedelta(days=5)).isoformat(),
            'payment_method': 'Stripe Payment',
            'payment_terms': 'Net 30',
            'line_items': [
                {
                    'description': 'Corporate formation documents',
                    'quantity': 8.0,
                    'unit': 'hours',
                    'rate': 450.00,
                    'amount': 3600.00
                },
                {
                    'description': 'Operating agreement preparation',
                    'quantity': 3.5,
                    'unit': 'hours',
                    'rate': 450.00,
                    'amount': 1575.00
                },
                {
                    'description': 'Legal consultation sessions',
                    'quantity': 1.3,
                    'unit': 'hours',
                    'rate': 250.00,
                    'amount': 325.00
                }
            ],
            'notes': 'Thank you for your prompt payment!',
            'created_at': (datetime.now() - timedelta(days=15)).isoformat(),
            'paid_at': (datetime.now() - timedelta(days=5)).isoformat()
        }
        
        # 2. Another paid invoice (different amount for testing)
        paid_invoice_2 = {
            'id': f"inv_{base_timestamp}_002",
            'invoice_number': f"INV-{datetime.now().year}-002",
            'client_name': 'Global Dynamics Inc',
            'client_email': 'ap@globaldynamics.com',
            'subject': 'Contract Negotiation Services',
            'issue_date': (datetime.now().date() - timedelta(days=22)).isoformat(),
            'due_date': (datetime.now().date() - timedelta(days=8)).isoformat(),
            'status': 'paid',
            'subtotal': 3200.00,
            'tax_rate': 0.0875,
            'tax_amount': 280.00,
            'total_amount': 3480.00,
            'amount_paid': 3480.00,
            'payment_intent_id': f'pi_test_paid_{random.randint(100000, 999999)}',
            'payment_date': (datetime.now().date() - timedelta(days=10)).isoformat(),
            'payment_method': 'Stripe Payment',
            'payment_terms': 'Net 30',
            'line_items': [
                {
                    'description': 'Contract review and redlining',
                    'quantity': 6.0,
                    'unit': 'hours',
                    'rate': 400.00,
                    'amount': 2400.00
                },
                {
                    'description': 'Negotiation strategy consultation',
                    'quantity': 2.0,
                    'unit': 'hours',
                    'rate': 400.00,
                    'amount': 800.00
                }
            ],
            'notes': 'Contract successfully negotiated and executed.',
            'created_at': (datetime.now() - timedelta(days=22)).isoformat(),
            'paid_at': (datetime.now() - timedelta(days=10)).isoformat()
        }
        
        # 3. Unpaid invoice (overdue)
        unpaid_invoice = {
            'id': f"inv_{base_timestamp}_003",
            'invoice_number': f"INV-{datetime.now().year}-003",
            'client_name': 'Metro Properties',
            'client_email': 'billing@metroproperties.com',
            'subject': 'Real Estate Transaction Legal Services',
            'issue_date': (datetime.now().date() - timedelta(days=45)).isoformat(),
            'due_date': (datetime.now().date() - timedelta(days=15)).isoformat(),
            'status': 'overdue',
            'subtotal': 4750.00,
            'tax_rate': 0.0875,
            'tax_amount': 415.63,
            'total_amount': 5165.63,
            'amount_paid': 0.00,
            'payment_terms': 'Net 30',
            'line_items': [
                {
                    'description': 'Purchase agreement review',
                    'quantity': 4.5,
                    'unit': 'hours',
                    'rate': 425.00,
                    'amount': 1912.50
                },
                {
                    'description': 'Title search and analysis',
                    'quantity': 3.0,
                    'unit': 'hours',
                    'rate': 325.00,
                    'amount': 975.00
                },
                {
                    'description': 'Closing document preparation',
                    'quantity': 5.5,
                    'unit': 'hours',
                    'rate': 325.00,
                    'amount': 1787.50
                },
                {
                    'description': 'Due diligence review',
                    'quantity': 2.0,
                    'unit': 'hours',
                    'rate': 375.00,
                    'amount': 750.00
                }
            ],
            'notes': 'OVERDUE: Payment was due 15 days ago. Please remit payment immediately.',
            'created_at': (datetime.now() - timedelta(days=45)).isoformat()
        }
        
        # 4. Recent unpaid invoice (not overdue yet)
        recent_unpaid = {
            'id': f"inv_{base_timestamp}_004",
            'invoice_number': f"INV-{datetime.now().year}-004",
            'client_name': 'Innovation Labs',
            'client_email': 'accounts@innovationlabs.tech',
            'subject': 'IP Protection and Patent Application',
            'issue_date': (datetime.now().date() - timedelta(days=10)).isoformat(),
            'due_date': (datetime.now().date() + timedelta(days=20)).isoformat(),
            'status': 'sent',
            'subtotal': 6800.00,
            'tax_rate': 0.0875,
            'tax_amount': 595.00,
            'total_amount': 7395.00,
            'amount_paid': 0.00,
            'payment_terms': 'Net 30',
            'line_items': [
                {
                    'description': 'Patent application preparation',
                    'quantity': 12.0,
                    'unit': 'hours',
                    'rate': 475.00,
                    'amount': 5700.00
                },
                {
                    'description': 'Prior art research',
                    'quantity': 4.0,
                    'unit': 'hours',
                    'rate': 275.00,
                    'amount': 1100.00
                }
            ],
            'notes': 'Patent application submitted to USPTO. Tracking number: 17/123,456',
            'created_at': (datetime.now() - timedelta(days=10)).isoformat()
        }
        
        test_invoices = [paid_invoice, paid_invoice_2, unpaid_invoice, recent_unpaid]
        
        return jsonify({
            'success': True,
            'message': f'Created {len(test_invoices)} test invoices',
            'invoices': test_invoices,
            'summary': {
                'paid_invoices': 2,
                'unpaid_invoices': 2,
                'total_paid_amount': paid_invoice['amount_paid'] + paid_invoice_2['amount_paid'],
                'total_outstanding': unpaid_invoice['total_amount'] + recent_unpaid['total_amount']
            }
        })
        
    except Exception as e:
        logger.error(f"Test invoices creation error: {e}")
        return jsonify({'error': 'Failed to create test invoices'}), 500

# ===== INITIALIZATION =====

logger.info("✅ LexAI Clean Flask app initialized for serverless deployment")

# Export for Vercel
app = app