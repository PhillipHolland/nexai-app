"""
LexAI Practice Partner - Production-Ready Legal AI Platform
Modern Flask application with enterprise-grade security and configuration management
"""

import os
import json
import requests
from flask import Flask, request, jsonify, render_template, session, redirect, url_for, flash
from werkzeug.utils import secure_filename
import re
from datetime import datetime, timezone
import os
import logging
from database import db, init_db, get_client_data, update_client_info, add_conversation, clear_conversation_history, add_document, Client, User
import uuid
from dotenv import load_dotenv
from auth import login_required, admin_required, get_current_user, create_user_session, destroy_user_session, register_user, authenticate_user
from config import get_config, validate_environment
from flask_migrate import Migrate
from security import SecurityValidator, RateLimiter, security_headers, rate_limit_decorator, validate_json_input, log_security_event
from error_handling import ErrorHandler, handle_api_error, monitor_performance, HealthCheck

# Load environment variables from .env file
load_dotenv()

def create_app(config_name=None):
    """Application factory pattern for better testability and configuration management"""
    app = Flask(__name__)
    
    # Load configuration
    config_class = get_config(config_name)
    app.config.from_object(config_class)
    
    # Validate environment configuration
    validation_result = validate_environment()
    if not validation_result['valid']:
        for error in validation_result['errors']:
            app.logger.error(f"Configuration Error: {error}")
        raise RuntimeError("Invalid configuration. Check environment variables.")
    
    # Log warnings
    for warning in validation_result['warnings']:
        app.logger.warning(f"Configuration Warning: {warning}")
    
    # Initialize configuration
    config_class.init_app(app)
    
    # Initialize database
    init_db(app)
    
    # Initialize migrations
    migrate = Migrate(app, db)
    
    # Initialize error handling
    error_handler = ErrorHandler(app)
    
    return app

# Create application instance
app = create_app()

# Add security headers to all responses
@app.after_request
def add_security_headers(response):
    return security_headers(response)

# Configure logging
logger = logging.getLogger(__name__)

# API configuration  
XAI_API_KEY = (os.environ.get('XAI_API_KEY') or os.environ.get('xai_api_key') or '').strip()
XAI_MODEL = app.config.get('XAI_MODEL', 'grok-3-latest')
API_TIMEOUT = app.config.get('API_TIMEOUT', 30)

if not XAI_API_KEY:
    logger.warning("XAI_API_KEY not set - AI features will not work")
else:
    logger.info(f"XAI_API_KEY loaded: {XAI_API_KEY[:10]}...{XAI_API_KEY[-4:]}")

# File upload configuration
UPLOAD_FOLDER = app.config.get('UPLOAD_FOLDER', '/tmp/uploads')
ALLOWED_EXTENSIONS = app.config.get('ALLOWED_EXTENSIONS', {'txt', 'pdf', 'doc', 'docx', 'rtf', 'odt'})

# Practice area configurations
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

# ============================================================================
# HEALTH CHECK AND MONITORING ROUTES
# ============================================================================

@app.route('/health')
def health_check():
    """Health check endpoint for monitoring and load balancers"""
    try:
        # Check database connection
        from sqlalchemy import text
        db.session.execute(text('SELECT 1'))
        
        # Check configuration
        validation = validate_environment()
        
        status = {
            'status': 'healthy',
            'timestamp': datetime.utcnow().isoformat(),
            'version': '1.0.0',
            'environment': app.config.get('FLASK_ENV', 'unknown'),
            'database': 'connected',
            'api_configured': bool(XAI_API_KEY),
            'config_valid': validation['valid']
        }
        
        return jsonify(status), 200
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return jsonify({
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat()
        }), 503

@app.route('/config/validate')
@login_required
@admin_required
def validate_config_endpoint():
    """Admin endpoint to validate configuration"""
    validation = validate_environment()
    return jsonify(validation)

# ============================================================================
# MAIN APPLICATION ROUTES
# ============================================================================

@app.route('/')
def dashboard():
    """Main dashboard - shows overview of cases, recent activity, quick actions"""
    try:
        # Get user's recent activity
        recent_clients = Client.query.order_by(Client.updated_at.desc()).limit(5).all()
        total_clients = Client.query.count()
        
        return render_template('dashboard.html', 
                             recent_clients=recent_clients,
                             total_clients=total_clients,
                             practice_areas=PRACTICE_AREAS)
    except Exception as e:
        logger.warning(f"Dashboard error: {e}")
        return render_template('dashboard.html', 
                             recent_clients=[],
                             total_clients=0,
                             practice_areas=PRACTICE_AREAS)

@app.route('/chat')
@app.route('/chat/<client_id>')
def chat_interface(client_id=None):
    """Modern chat interface for AI conversations"""
    clients = []
    current_client = None
    
    try:
        clients = Client.query.order_by(Client.updated_at.desc()).all()
        if client_id:
            current_client = Client.query.filter_by(id=client_id).first()
    except Exception as e:
        logger.warning(f"Chat interface error: {e}")
    
    return render_template('chat.html', 
                         clients=clients, 
                         current_client=current_client,
                         practice_areas=PRACTICE_AREAS)

@app.route('/clients')
def clients_list():
    """Client management interface"""
    try:
        clients = Client.query.order_by(Client.updated_at.desc()).all()
        return render_template('clients.html', clients=clients)
    except Exception as e:
        logger.warning(f"Clients list error: {e}")
        return render_template('clients.html', clients=[])

@app.route('/documents')
def documents_list():
    """Document management interface"""
    try:
        # Get user's documents (in production, filter by user)
        documents = db.session.execute(
            'SELECT * FROM documents ORDER BY uploaded_at DESC'
        ).fetchall()
        return render_template('documents.html', documents=documents)
    except Exception as e:
        logger.warning(f"Documents list error: {e}")
        return render_template('documents.html', documents=[])

@app.route('/analytics')
def analytics_dashboard():
    """Analytics and reporting dashboard"""
    try:
        # Calculate basic statistics
        stats = {
            'total_clients': Client.query.count(),
            'total_conversations': db.session.execute(
                'SELECT COUNT(*) FROM conversations WHERE role = "user"'
            ).scalar() or 0,
            'avg_response_time': '2.3s',  # Placeholder
            'client_satisfaction': '94%'   # Placeholder
        }
        return render_template('analytics.html', stats=stats)
    except Exception as e:
        logger.warning(f"Analytics error: {e}")
        return render_template('analytics.html', stats={})

@app.route('/deadlines')
@login_required
def deadlines_page():
    """Deadlines and calendar management"""
    try:
        # Placeholder for deadlines functionality
        return render_template('deadlines.html')
    except Exception as e:
        logger.warning(f"Deadlines page error: {e}")
        return jsonify({"error": "Unable to load deadlines page", "success": False})

@app.route('/contracts')
@login_required
def contracts_page():
    """Contract management and generation"""
    try:
        return render_template('contracts.html')
    except Exception as e:
        logger.warning(f"Contracts page error: {e}")
        return render_template('contracts.html')

@app.route('/billing')
@login_required
def billing_page():
    """Billing and invoicing management"""
    try:
        return render_template('billing.html')
    except Exception as e:
        logger.warning(f"Billing page error: {e}")
        return jsonify({"error": "Unable to load billing page", "success": False})

@app.route('/calendar')
@login_required
def calendar_page():
    """Calendar and scheduling"""
    try:
        return render_template('calendar.html')
    except Exception as e:
        logger.warning(f"Calendar page error: {e}")
        return jsonify({"error": "Unable to load calendar page", "success": False})

@app.route('/time-tracking')
@login_required
def time_tracking_page():
    """Time tracking management"""
    try:
        return render_template('time_tracking.html')
    except Exception as e:
        logger.warning(f"Time tracking page error: {e}")
        return jsonify({"error": "Unable to load time tracking page", "success": False})

@app.route('/admin/users')
@login_required
@admin_required
def admin_users():
    """Admin user management"""
    try:
        users = User.query.all()
        return render_template('admin_users.html', users=users)
    except Exception as e:
        logger.warning(f"Admin users page error: {e}")
        return jsonify({"error": "Unable to load admin users page", "success": False})

@app.route('/admin/settings')
@login_required
@admin_required
def admin_settings():
    """Admin settings management"""
    try:
        return render_template('admin_settings.html')
    except Exception as e:
        logger.warning(f"Admin settings page error: {e}")
        return jsonify({"error": "Unable to load admin settings page", "success": False})

@app.route('/admin/subscriptions')
@login_required
@admin_required
def admin_subscriptions():
    """Admin subscription management"""
    try:
        return render_template('admin_subscriptions.html')
    except Exception as e:
        logger.warning(f"Admin subscriptions page error: {e}")
        return jsonify({"error": "Unable to load admin subscriptions page", "success": False})

@app.route('/admin/audit-logs')
@login_required
@admin_required
def admin_audit_logs():
    """Admin audit log management"""
    try:
        return render_template('admin_audit_logs.html')
    except Exception as e:
        logger.warning(f"Admin audit logs page error: {e}")
        return jsonify({"error": "Unable to load admin audit logs page", "success": False})

# ============================================================================
# API ENDPOINTS
# ============================================================================

@app.route('/api/chat', methods=['POST'])
@rate_limit_decorator
@validate_json_input(['message'])
@handle_api_error
@monitor_performance
def api_chat():
    """Enhanced chat API with practice area specialization and security"""
    try:
        data = g.validated_data
        
        # Support both message formats
        if 'message' in data:
            message = data.get('message', '').strip()
        else:
            messages = data.get('messages', [])
            if not messages:
                return jsonify({"error": "Message is required"}), 400
            message = messages[-1].get('content', '').strip()

        # Validate and sanitize message
        validation_result = SecurityValidator.validate_message(message)
        if not validation_result['valid']:
            log_security_event('input_validation_failed', f"Message validation failed: {validation_result['errors']}")
            return jsonify({"error": validation_result['errors'][0]}), 400
        
        message = validation_result['sanitized']
        client_id = data.get('client_id', f'client_{uuid.uuid4().hex[:8]}')
        practice_area = data.get('practice_area', 'general')
        
        if not message:
            return jsonify({"error": "Message is required"}), 400

        logger.info(f"Chat request: client_id={client_id}, practice_area={practice_area}")

        # Ensure client exists
        try:
            client = Client.query.filter_by(id=client_id).first()
            if not client:
                client = Client(
                    id=client_id, 
                    name=f"Client {client_id[-8:]}",
                    case_type=practice_area.replace('_', ' ').title()
                )
                db.session.add(client)
                db.session.commit()
                logger.info(f"Created new client: {client_id}")
        except Exception as e:
            logger.warning(f"Database operation failed: {e}")

        # Build specialized system prompt
        system_prompt = build_system_prompt(practice_area)
        
        # API call to Grok
        payload = {
            "model": "grok-3-latest",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": message}
            ],
            "stream": False,
            "temperature": 0.7
        }

        headers = {
            "Authorization": f"Bearer {XAI_API_KEY}",
            "Content-Type": "application/json"
        }

        logger.info(f"Sending request to Grok API...")
        response = requests.post(
            "https://api.x.ai/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=30
        )
        
        if response.status_code == 200:
            grok_response = response.json()
            if 'choices' in grok_response and len(grok_response['choices']) > 0:
                assistant_content = grok_response["choices"][0]["message"]["content"].strip()
                logger.info(f"Received response: {len(assistant_content)} characters")
            else:
                logger.error(f"Unexpected response structure: {grok_response}")
                return jsonify({"error": "Invalid response from AI service"}), 502
        else:
            logger.error(f"XAI API error: {response.status_code} - {response.text}")
            return jsonify({"error": "AI service temporarily unavailable"}), 503

        # Save to database
        try:
            add_conversation(client_id, "user", message)
            add_conversation(client_id, "assistant", assistant_content)
            logger.info(f"Saved conversation to database")
        except Exception as e:
            logger.warning(f"Failed to save to database: {e}")

        return jsonify({
            "choices": [{"delta": {"content": assistant_content}}],
            "client_id": client_id,
            "practice_area": practice_area
        })

    except Exception as e:
        logger.error(f"Chat endpoint error: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500

@app.route('/api/clients', methods=['GET', 'POST'])
def api_clients():
    """Client management API"""
    if request.method == 'POST':
        try:
            data = request.get_json()
            client_id = data.get('id') or f'client_{uuid.uuid4().hex[:8]}'
            
            client_info = {
                'name': data.get('name', ''),
                'email': data.get('email', ''),
                'phone': data.get('phone', ''),
                'case_type': data.get('case_type', ''),
                'notes': data.get('notes', '')
            }
            
            update_client_info(client_id, client_info)
            return jsonify({"success": True, "client_id": client_id})
        except Exception as e:
            logger.error(f"Client creation error: {e}")
            return jsonify({"error": str(e)}), 500
    
    else:  # GET
        try:
            clients = Client.query.order_by(Client.updated_at.desc()).all()
            return jsonify([{
                'id': client.id,
                'name': client.name,
                'email': client.email,
                'phone': client.phone,
                'case_type': client.case_type,
                'updated_at': client.updated_at.isoformat() if client.updated_at else None
            } for client in clients])
        except Exception as e:
            logger.error(f"Clients fetch error: {e}")
            return jsonify([])

@app.route('/api/upload', methods=['POST'])
@rate_limit_decorator
def api_upload_document():
    """Secure document upload API"""
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
            
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
            
        # Validate file
        validation_result = SecurityValidator.validate_file_upload(
            file.filename, 
            len(file.read())
        )
        file.seek(0)  # Reset file pointer
        
        if not validation_result['valid']:
            log_security_event('file_validation_failed', f"File validation failed: {validation_result['errors']}")
            return jsonify({'error': validation_result['errors'][0]}), 400
            
        # Generate secure filename
        import os
        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        safe_filename = validation_result['safe_filename']
        filename = f"{timestamp}_{safe_filename}"
        
        # Ensure upload directory exists
        os.makedirs(UPLOAD_FOLDER, exist_ok=True)
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        
        # Save file
        file.save(filepath)
        
        # Store document metadata in database
        client_id = request.form.get('client_id', 'general')
        add_document(client_id, safe_filename, filepath, file.content_type or 'application/octet-stream')
        
        logger.info(f"Document uploaded: {filename} for client {client_id}")
        
        return jsonify({
            'success': True,
            'filename': safe_filename,
            'message': 'Document uploaded successfully'
        })
        
    except Exception as e:
        logger.error(f"Document upload error: {e}")
        return jsonify({'error': 'Upload failed'}), 500

@app.route('/api/client/<client_id>', methods=['GET', 'POST'])
def api_client_detail(client_id):
    """Individual client API"""
    if request.method == 'POST':
        try:
            data = request.get_json()
            update_client_info(client_id, data)
            return jsonify({"success": True})
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    
    else:  # GET
        try:
            client_data = get_client_data(client_id)
            if not client_data:
                return jsonify({"error": "Client not found"}), 404
            return jsonify(client_data)
        except Exception as e:
            return jsonify({"error": str(e)}), 500

# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def build_system_prompt(practice_area):
    """Build specialized system prompt based on practice area"""
    base_prompt = """You are LexAI, an advanced legal AI assistant designed to help legal professionals. You provide accurate, professional guidance while noting this is not formal legal advice."""
    
    specializations = {
        'family': """
        
**FAMILY LAW SPECIALIZATION:**
- Focus on divorce, custody, child support, adoption, and domestic relations
- Consider state-specific family law variations
        - Provide templates for common family law documents
        - Calculate child support using standard formulas
        - Address emotional aspects with professionalism and empathy
        """,
        
        'personal_injury': """
        
**PERSONAL INJURY SPECIALIZATION:**
        - Focus on tort law, damages calculation, and settlement negotiation
        - Analyze medical records and injury severity
        - Consider comparative negligence and liability factors
        - Provide guidance on settlement timing and strategy
        - Reference relevant case law and precedents
        """,
        
        'corporate': """
        
**CORPORATE LAW SPECIALIZATION:**
        - Focus on business formation, contracts, and compliance
        - Consider federal and state business regulations
        - Provide guidance on entity structure and governance
        - Address intellectual property and employment issues
        - Reference relevant business law principles
        """,
        
        'criminal': """
        
**CRIMINAL DEFENSE SPECIALIZATION:**
        - Focus on criminal procedure, evidence, and constitutional rights
        - Consider federal and state criminal law variations
        - Provide guidance on plea negotiations and trial strategy
        - Reference relevant precedents and constitutional protections
        - Address procedural requirements and deadlines
        """,
        
        'real_estate': """
        
**REAL ESTATE SPECIALIZATION:**
        - Focus on property transactions, title issues, and zoning
        - Consider local real estate law and customs
        - Provide guidance on purchase agreements and closing procedures
        - Address landlord-tenant and commercial real estate issues
        - Reference relevant property law principles
        """,
        
        'immigration': """
        
**IMMIGRATION SPECIALIZATION:**
        - Focus on visa applications, citizenship, and immigration procedures
        - Consider federal immigration law and policy changes
        - Provide guidance on eligibility requirements and documentation
        - Address family-based and employment-based immigration
        - Reference current immigration regulations and precedents
        """
    }
    
    return base_prompt + specializations.get(practice_area, '')

if __name__ == '__main__':
    app.run(debug=True, host='127.0.0.1', port=5004)