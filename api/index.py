#!/usr/bin/env python3
"""
LexAI Practice Partner - Clean Serverless Version
Streamlined version for Vercel deployment without duplicate routes
"""

import os
import json
import logging
from datetime import datetime
from decimal import Decimal
from flask import Flask, request, jsonify, render_template, session
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create Flask app
app = Flask(__name__, template_folder='../templates', static_folder='../static')
app.secret_key = os.environ.get('SECRET_KEY', 'dev-key-change-in-production')

# Basic configuration
app.config.update({
    'SECRET_KEY': os.environ.get('SECRET_KEY', 'dev-key-change-in-production'),
    'DATABASE_URL': os.environ.get('DATABASE_URL'),
    'REDIS_URL': os.environ.get('REDIS_URL'),
    'BAGEL_RL_API_KEY': os.environ.get('BAGEL_RL_API_KEY'),
    'XAI_API_KEY': os.environ.get('XAI_API_KEY'),
    'GOOGLE_ANALYTICS_ID': os.environ.get('GOOGLE_ANALYTICS_ID'),
})

# Service availability flags
BAGEL_AI_AVAILABLE = bool(os.environ.get('BAGEL_RL_API_KEY'))
SPANISH_AVAILABLE = True
PRIVACY_AI_AVAILABLE = False
STRIPE_AVAILABLE = bool(os.environ.get('STRIPE_SECRET_KEY'))

logger.info(f"BAGEL_AI_AVAILABLE: {BAGEL_AI_AVAILABLE}")
logger.info(f"SPANISH_AVAILABLE: {SPANISH_AVAILABLE}")
logger.info(f"STRIPE_AVAILABLE: {STRIPE_AVAILABLE}")

# ===== MAIN ROUTES =====

@app.route('/')
def landing_page():
    """Landing page"""
    try:
        return render_template('landing.html',
                             google_analytics_id=app.config.get('GOOGLE_ANALYTICS_ID'))
    except Exception as e:
        logger.error(f"Landing page error: {e}")
        return f"LexAI Practice Partner - Error loading page: {e}", 500

@app.route('/dashboard')
def dashboard():
    """Main dashboard"""
    try:
        return render_template('dashboard.html',
                             user_role=session.get('user_role', 'guest'),
                             user_name=session.get('user_name', 'User'))
    except Exception as e:
        logger.error(f"Dashboard error: {e}")
        return f"Dashboard error: {e}", 500

@app.route('/documents')
def documents_page():
    """Document analysis page"""
    try:
        return render_template('documents.html',
                             bagel_available=BAGEL_AI_AVAILABLE)
    except Exception as e:
        logger.error(f"Documents page error: {e}")
        return f"Documents error: {e}", 500

@app.route('/contracts')
def contracts_page():
    """Contract analysis page"""
    try:
        return render_template('contracts.html',
                             bagel_available=BAGEL_AI_AVAILABLE)
    except Exception as e:
        logger.error(f"Contracts page error: {e}")
        return f"Contracts error: {e}", 500

@app.route('/legal-research')
def legal_research_page():
    """Legal research page"""
    try:
        return render_template('legal_research.html',
                             bagel_available=BAGEL_AI_AVAILABLE)
    except Exception as e:
        logger.error(f"Legal research page error: {e}")
        return f"Legal research error: {e}", 500

@app.route('/spanish')
def spanish_interface():
    """Spanish language interface"""
    try:
        return render_template('spanish_interface.html',
                             spanish_available=SPANISH_AVAILABLE)
    except Exception as e:
        logger.error(f"Spanish interface error: {e}")
        return f"Spanish interface error: {e}", 500

@app.route('/billing')
def billing_page():
    """Billing and payments page"""
    try:
        return render_template('billing.html',
                             stripe_available=STRIPE_AVAILABLE)
    except Exception as e:
        logger.error(f"Billing page error: {e}")
        return f"Billing error: {e}", 500

@app.route('/clients')
def clients_page():
    """Client management page"""
    try:
        return render_template('clients.html')
    except Exception as e:
        logger.error(f"Clients page error: {e}")
        return f"Clients error: {e}", 500

@app.route('/chat')
def chat_page():
    """Chat interface"""
    try:
        return render_template('chat.html',
                             xai_available=bool(app.config.get('XAI_API_KEY')))
    except Exception as e:
        logger.error(f"Chat page error: {e}")
        return f"Chat error: {e}", 500

@app.route('/onboarding')
def onboarding_page():
    """User onboarding flow"""
    try:
        return render_template('onboarding.html')
    except Exception as e:
        logger.error(f"Onboarding error: {e}")
        return f"Onboarding error: {e}", 500

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
        'timestamp': datetime.now().isoformat()
    })

@app.route('/api/documents/analyze', methods=['POST'])
def api_document_analyze():
    """Analyze document text"""
    try:
        data = request.get_json()
        if not data or 'text' not in data:
            return jsonify({
                'success': False,
                'error': 'Document text required'
            }), 400
        
        # Basic response for now
        return jsonify({
            'success': True,
            'message': 'Document analysis completed',
            'analysis': {
                'text_length': len(data['text']),
                'word_count': len(data['text'].split()),
                'status': 'analyzed'
            },
            'bagel_available': BAGEL_AI_AVAILABLE
        })
        
    except Exception as e:
        logger.error(f"Document analysis error: {e}")
        return jsonify({
            'success': False,
            'error': 'Document analysis failed'
        }), 500

@app.route('/api/spanish/translate', methods=['POST'])
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
def api_chat():
    """Chat with AI assistant"""
    try:
        data = request.get_json()
        if not data or 'message' not in data:
            return jsonify({
                'success': False,
                'error': 'Message required'
            }), 400
        
        # Basic response for now
        return jsonify({
            'success': True,
            'response': 'I am LexAI, your legal practice assistant. How can I help you today?',
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Chat error: {e}")
        return jsonify({
            'success': False,
            'error': 'Chat request failed'
        }), 500

@app.route('/api/onboarding/complete', methods=['POST'])
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

# ===== INITIALIZATION =====

logger.info("✅ LexAI Clean Flask app initialized for serverless deployment")

# Export for Vercel
app = app