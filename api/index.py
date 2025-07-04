"""
Vercel-compatible entry point for LexAI Practice Partner
Simplified for serverless deployment
"""

import os
import sys
import json
import requests
from flask import Flask, request, jsonify, render_template
from datetime import datetime
import logging

# Add the parent directory to the Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# Configure logging for Vercel
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create Flask app
app = Flask(__name__, 
           template_folder=os.path.join(os.path.dirname(os.path.dirname(__file__)), 'templates'),
           static_folder=os.path.join(os.path.dirname(os.path.dirname(__file__)), 'static'))

# Simplified configuration for Vercel
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'vercel-dev-key')

# API configuration
XAI_API_KEY = os.environ.get('XAI_API_KEY')
if not XAI_API_KEY:
    logger.warning("XAI_API_KEY not set - AI features will not work")

# Practice areas configuration
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

@app.route('/')
def dashboard():
    """Main dashboard"""
    return render_template('dashboard.html', 
                         recent_clients=[],
                         total_clients=0,
                         practice_areas=PRACTICE_AREAS)

@app.route('/chat')
@app.route('/chat/<client_id>')
def chat_interface(client_id=None):
    """Chat interface"""
    return render_template('chat.html', 
                         clients=[], 
                         current_client=None,
                         practice_areas=PRACTICE_AREAS)

@app.route('/clients')
def clients_list():
    """Client management interface"""
    return render_template('clients.html', clients=[])

@app.route('/health')
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.utcnow().isoformat(),
        'version': '1.0.0',
        'environment': 'vercel',
        'api_configured': bool(XAI_API_KEY)
    })

@app.route('/api/chat', methods=['POST'])
def api_chat():
    """Simplified chat API for Vercel"""
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

        practice_area = data.get('practice_area', 'general')
        
        if not message:
            return jsonify({"error": "Message is required"}), 400

        if not XAI_API_KEY:
            return jsonify({"error": "AI service not configured"}), 503

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

        response = requests.post(
            "https://api.x.ai/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=30
        )
        
        response.raise_for_status()
        grok_response = response.json()
        assistant_content = grok_response["choices"][0]["message"]["content"]

        return jsonify({
            "choices": [{"delta": {"content": assistant_content}}],
            "practice_area": practice_area
        })

    except requests.exceptions.RequestException as e:
        logger.error(f"Grok API error: {str(e)}")
        return jsonify({"error": f"AI service error: {str(e)}"}), 500
    
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500

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

# Vercel expects an 'app' object
# This is the WSGI application that Vercel will call
if __name__ == '__main__':
    app.run(debug=True)
else:
    # For Vercel deployment
    application = app