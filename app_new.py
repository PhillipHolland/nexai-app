"""
LexAI Practice Partner - Comprehensive Legal AI Platform
Modern Flask application with advanced features for law firms of all sizes.
"""

import os
import json
import requests
from flask import Flask, request, jsonify, render_template, session, redirect, url_for
from werkzeug.utils import secure_filename
import re
from datetime import datetime, timezone
import logging
from database import db, init_db, get_client_data, update_client_info, add_conversation, clear_conversation_history, add_document, Client
import uuid

app = Flask(__name__)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# App configuration
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'lexai-dev-key-change-in-production')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file upload

# Database configuration
DATABASE_URL = os.getenv('DATABASE_URL')
if DATABASE_URL:
    if DATABASE_URL.startswith('postgres://'):
        DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://') 
    app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
else:
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///lexai_platform.db'

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize database
init_db(app)

# API configuration
XAI_API_KEY = os.getenv("XAI_API_KEY")
if not XAI_API_KEY:
    logger.warning("XAI_API_KEY not set - AI features will not work")

# File upload configuration
UPLOAD_FOLDER = '/tmp/uploads'
ALLOWED_EXTENSIONS = {'txt', 'pdf', 'doc', 'docx', 'rtf', 'odt'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

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
# ROUTES
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
    return render_template('documents.html')

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

# ============================================================================
# API ENDPOINTS
# ============================================================================

@app.route('/api/chat', methods=['POST'])
def api_chat():
    """Enhanced chat API with practice area specialization"""
    try:
        data = request.get_json()
        
        # Support both message formats
        if 'message' in data:
            message = data.get('message', '').strip()
        else:
            messages = data.get('messages', [])
            if not messages:
                return jsonify({"error": "Message is required"}), 400
            message = messages[-1].get('content', '').strip()

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
        
        response.raise_for_status()
        grok_response = response.json()
        
        assistant_content = grok_response["choices"][0]["message"]["content"]
        logger.info(f"Received response: {len(assistant_content)} characters")

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

    except requests.exceptions.RequestException as e:
        error_detail = str(e)
        if hasattr(e, 'response') and e.response is not None:
            try:
                error_response = e.response.json()
                error_detail += f" - Response: {error_response}"
            except:
                error_detail += f" - Response: {e.response.text}"
        logger.error(f"Grok API error: {error_detail}")
        return jsonify({"error": f"AI service error: {str(e)}"}), 500
    
    except Exception as e:
        logger.error(f"Unexpected error in chat endpoint: {str(e)}")
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500

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
    app.run(debug=True)