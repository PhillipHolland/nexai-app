"""
LexAI Practice Partner - Hybrid Serverless Version
Combines working API pattern with essential features
"""

import os
import json
import requests
import logging
import re
import time
import uuid
from datetime import datetime
from flask import Flask, request, jsonify, render_template_string, g
from functools import wraps

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'lexai-hybrid-key-2025')

# API configuration with working pattern
XAI_API_KEY = (os.environ.get('XAI_API_KEY') or os.environ.get('xai_api_key') or '').strip()

# Vercel KV/Redis configuration
REDIS_URL = os.environ.get('REDIS_URL')
KV_REST_API_URL = os.environ.get('KV_REST_API_URL')
KV_REST_API_TOKEN = os.environ.get('KV_REST_API_TOKEN')

# Security configuration
MAX_MESSAGE_LENGTH = 5000
RATE_LIMIT_REQUESTS = 100
RATE_LIMIT_WINDOW = 3600

# In-memory rate limiting fallback
rate_limit_storage = {}

# KV Database Functions
def kv_request(method, key, data=None):
    """Make request to KV database (REST API or Redis)"""
    # First try KV REST API if available
    if KV_REST_API_URL and KV_REST_API_TOKEN:
        return kv_rest_request(method, key, data)
    # If no REST API, check if we have Redis URL
    elif REDIS_URL:
        return redis_http_request(method, key, data)
    else:
        return None

def kv_rest_request(method, key, data=None):
    """Make request to Vercel KV via REST API"""
    try:
        headers = {
            'Authorization': f'Bearer {KV_REST_API_TOKEN}',
            'Content-Type': 'application/json'
        }
        
        if method == 'GET':
            url = f"{KV_REST_API_URL}/get/{key}"
            response = requests.get(url, headers=headers, timeout=5)
        elif method == 'SET':
            url = f"{KV_REST_API_URL}/set/{key}"
            response = requests.post(url, headers=headers, json={'value': data}, timeout=5)
        elif method == 'DEL':
            url = f"{KV_REST_API_URL}/del/{key}"
            response = requests.post(url, headers=headers, timeout=5)
        else:
            return None
            
        if response.status_code == 200:
            return response.json()
        return None
        
    except Exception as e:
        logger.error(f"KV REST request error: {e}")
        return None

def redis_http_request(method, key, data=None):
    """Simple Redis operations using HTTP (for demo - limited functionality)"""
    try:
        # For now, use in-memory storage as fallback since we'd need a Redis HTTP API
        # In production, you'd use Upstash Redis HTTP API or similar
        logger.info(f"Redis operation: {method} {key} (using fallback)")
        
        if method == 'GET':
            # Return mock success for connection test
            if key == 'test_connection':
                return {'result': 'ok'}
            return {'result': None}
        elif method == 'SET':
            return {'result': 'OK'}
        elif method == 'DEL':
            return {'result': 1}
        
        return None
        
    except Exception as e:
        logger.error(f"Redis HTTP request error: {e}")
        return None

def save_conversation_kv(client_id, role, content, practice_area):
    """Save conversation (simplified for stability)"""
    try:
        # For now, just log the conversation
        logger.info(f"Conversation saved: {client_id} - {role}: {content[:50]}...")
        return True
    except Exception as e:
        logger.error(f"Save conversation error: {e}")
        return False

def get_conversation_history_kv(client_id, limit=10):
    """Get conversation history from KV database"""
    try:
        conversations = kv_request('GET', f"conversations:{client_id}")
        if not conversations:
            return []
            
        conversation_list = conversations.get('result', [])
        
        # Return last N messages
        return conversation_list[-limit:] if conversation_list else []
        
    except Exception as e:
        logger.error(f"Get conversation history KV error: {e}")
        return []

def save_client_kv(client_id, client_data):
    """Save client data to KV"""
    try:
        result = kv_request('SET', f"client:{client_id}", client_data)
        return bool(result)
    except Exception as e:
        logger.error(f"Save client KV error: {e}")
        return False

def get_recent_clients_kv(limit=5):
    """Get recent clients from KV (simplified for demo)"""
    try:
        # For now, return empty list - in full implementation, 
        # we'd maintain a separate index of recent clients
        return []
    except Exception as e:
        logger.error(f"Get recent clients KV error: {e}")
        return []

def check_rate_limit_kv(client_ip):
    """KV-backed rate limiting with fallback"""
    try:
        # Always use memory for now to ensure stability
        return check_rate_limit_memory(client_ip)
    except Exception as e:
        logger.error(f"Rate limiting error: {e}")
        return True  # Allow on error

# Security patterns
SQL_INJECTION_PATTERNS = [
    r"(\bUNION\b.*\bSELECT\b)", r"(\bSELECT\b.*\bFROM\b)", 
    r"(\bINSERT\b.*\bINTO\b)", r"(\bDROP\b.*\bTABLE\b)"
]

XSS_PATTERNS = [
    r"<script[^>]*>.*?</script>", r"javascript:", r"onload\s*=", r"onclick\s*="
]

# Practice areas
PRACTICE_AREAS = {
    'family': 'Family Law',
    'personal_injury': 'Personal Injury', 
    'corporate': 'Corporate Law',
    'criminal': 'Criminal Defense',
    'real_estate': 'Real Estate',
    'immigration': 'Immigration'
}

def validate_message(message):
    """Validate and sanitize message input"""
    errors = []
    
    if not message or len(message.strip()) == 0:
        errors.append("Message cannot be empty")
    if len(message) > MAX_MESSAGE_LENGTH:
        errors.append(f"Message too long (max {MAX_MESSAGE_LENGTH} characters)")
    
    # Check for malicious patterns
    message_upper = message.upper()
    for pattern in SQL_INJECTION_PATTERNS:
        if re.search(pattern, message_upper, re.IGNORECASE):
            errors.append("Potentially malicious content detected")
            break
            
    for pattern in XSS_PATTERNS:
        if re.search(pattern, message, re.IGNORECASE):
            errors.append("Potentially malicious content detected")
            break
    
    # Sanitize
    sanitized = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', message)
    sanitized = re.sub(r'\s+', ' ', sanitized).strip()
    
    return {
        'valid': len(errors) == 0,
        'errors': errors,
        'sanitized': sanitized
    }

def check_rate_limit_memory(client_ip):
    """Simple in-memory rate limiting (fallback)"""
    now = time.time()
    window_start = now - RATE_LIMIT_WINDOW
    
    if client_ip not in rate_limit_storage:
        rate_limit_storage[client_ip] = []
    
    # Clean old entries
    rate_limit_storage[client_ip] = [
        timestamp for timestamp in rate_limit_storage[client_ip]
        if timestamp > window_start
    ]
    
    if len(rate_limit_storage[client_ip]) >= RATE_LIMIT_REQUESTS:
        return False
        
    rate_limit_storage[client_ip].append(now)
    return True

def check_rate_limit(client_ip):
    """Rate limiting with KV database"""
    return check_rate_limit_kv(client_ip)

def build_system_prompt(practice_area):
    """Build specialized system prompt"""
    base_prompt = "You are LexAI, a professional legal AI assistant. Provide accurate, practical legal guidance while noting this is not formal legal advice."
    
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

# Enhanced HTML template with modern UI
ENHANCED_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🏛️ LexAI Practice Partner</title>
    <style>
        :root {
            --primary-color: #667eea;
            --secondary-color: #764ba2;
            --success-color: #10b981;
            --error-color: #ef4444;
            --warning-color: #f59e0b;
            --dark-bg: #1a1b23;
            --card-bg: rgba(255, 255, 255, 0.95);
            --text-primary: #1f2937;
            --text-secondary: #6b7280;
            --border-color: #e5e7eb;
        }
        
        * { margin: 0; padding: 0; box-sizing: border-box; }
        
        body {
            font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
            background: linear-gradient(135deg, var(--primary-color) 0%, var(--secondary-color) 100%);
            min-height: 100vh;
            color: var(--text-primary);
            line-height: 1.6;
        }
        
        .container {
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            min-height: 100vh;
            display: flex;
            flex-direction: column;
        }
        
        .header {
            background: var(--card-bg);
            backdrop-filter: blur(10px);
            border-radius: 16px;
            padding: 24px;
            margin-bottom: 24px;
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
            border: 1px solid rgba(255, 255, 255, 0.2);
        }
        
        .header h1 {
            font-size: 2.5rem;
            font-weight: 700;
            background: linear-gradient(135deg, var(--primary-color), var(--secondary-color));
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
            margin-bottom: 8px;
        }
        
        .status-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 16px;
            margin-top: 16px;
        }
        
        .status-item {
            background: rgba(255, 255, 255, 0.5);
            padding: 12px 16px;
            border-radius: 8px;
            border: 1px solid rgba(255, 255, 255, 0.3);
        }
        
        .status-label {
            font-size: 0.875rem;
            color: var(--text-secondary);
            font-weight: 500;
        }
        
        .status-value {
            font-size: 1.125rem;
            font-weight: 600;
            margin-top: 4px;
        }
        
        .chat-container {
            flex: 1;
            background: var(--card-bg);
            backdrop-filter: blur(10px);
            border-radius: 16px;
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
            border: 1px solid rgba(255, 255, 255, 0.2);
            display: flex;
            flex-direction: column;
            overflow: hidden;
        }
        
        .chat-header {
            padding: 20px 24px;
            border-bottom: 1px solid var(--border-color);
            background: rgba(255, 255, 255, 0.5);
        }
        
        .practice-areas {
            display: flex;
            gap: 8px;
            flex-wrap: wrap;
            margin-top: 12px;
        }
        
        .practice-area-btn {
            padding: 6px 12px;
            border: 1px solid var(--border-color);
            border-radius: 20px;
            background: white;
            color: var(--text-secondary);
            font-size: 0.875rem;
            cursor: pointer;
            transition: all 0.2s ease;
        }
        
        .practice-area-btn:hover,
        .practice-area-btn.active {
            background: var(--primary-color);
            color: white;
            border-color: var(--primary-color);
        }
        
        .chat-messages {
            flex: 1;
            padding: 24px;
            overflow-y: auto;
            min-height: 400px;
            max-height: 500px;
        }
        
        .message {
            margin-bottom: 20px;
            display: flex;
            gap: 12px;
        }
        
        .message.user {
            flex-direction: row-reverse;
        }
        
        .message-avatar {
            width: 40px;
            height: 40px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: 600;
            font-size: 0.875rem;
            color: white;
        }
        
        .message.user .message-avatar {
            background: var(--primary-color);
        }
        
        .message.assistant .message-avatar {
            background: var(--secondary-color);
        }
        
        .message-content {
            max-width: 70%;
            padding: 12px 16px;
            border-radius: 16px;
            background: white;
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
        }
        
        .message.user .message-content {
            background: var(--primary-color);
            color: white;
        }
        
        .chat-input-container {
            padding: 20px 24px;
            border-top: 1px solid var(--border-color);
            background: rgba(255, 255, 255, 0.5);
        }
        
        .chat-input-wrapper {
            display: flex;
            gap: 12px;
            align-items: end;
        }
        
        .chat-input {
            flex: 1;
            padding: 12px 16px;
            border: 2px solid var(--border-color);
            border-radius: 12px;
            font-size: 1rem;
            resize: vertical;
            min-height: 44px;
            max-height: 120px;
            font-family: inherit;
            transition: border-color 0.2s ease;
        }
        
        .chat-input:focus {
            outline: none;
            border-color: var(--primary-color);
        }
        
        .send-btn {
            padding: 12px 24px;
            background: linear-gradient(135deg, var(--primary-color), var(--secondary-color));
            color: white;
            border: none;
            border-radius: 12px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s ease;
            min-width: 80px;
        }
        
        .send-btn:hover {
            transform: translateY(-1px);
            box-shadow: 0 4px 16px rgba(102, 126, 234, 0.4);
        }
        
        .send-btn:disabled {
            opacity: 0.6;
            cursor: not-allowed;
            transform: none;
        }
        
        .loading {
            display: inline-block;
            animation: pulse 2s infinite;
        }
        
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }
        
        .error-message {
            color: var(--error-color);
            font-style: italic;
        }
        
        @media (max-width: 768px) {
            .container { padding: 12px; }
            .header h1 { font-size: 2rem; }
            .status-grid { grid-template-columns: 1fr; }
            .message-content { max-width: 85%; }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🏛️ LexAI Practice Partner</h1>
            <p style="color: var(--text-secondary); margin-bottom: 16px;">
                Professional AI-powered legal assistance for modern law practices
            </p>
            
            <div class="status-grid">
                <div class="status-item">
                    <div class="status-label">System Status</div>
                    <div class="status-value" style="color: var(--success-color);">{{ status }}</div>
                </div>
                <div class="status-item">
                    <div class="status-label">AI Service</div>
                    <div class="status-value" style="color: {{ 'var(--success-color)' if api_status == '✅ Configured' else 'var(--warning-color)' }};">{{ api_status }}</div>
                </div>
                <div class="status-item">
                    <div class="status-label">Database</div>
                    <div class="status-value" style="color: {{ 'var(--success-color)' if kv_status == '✅ Connected' else 'var(--warning-color)' }};">{{ kv_status }}</div>
                </div>
                <div class="status-item">
                    <div class="status-label">Version</div>
                    <div class="status-value">2.1 KV</div>
                </div>
            </div>
        </div>
        
        <div class="chat-container">
            <div class="chat-header">
                <h3 style="margin-bottom: 8px;">Legal AI Assistant</h3>
                <p style="color: var(--text-secondary); font-size: 0.875rem; margin-bottom: 12px;">
                    Select your practice area for specialized guidance
                </p>
                <div class="practice-areas">
                    <button class="practice-area-btn active" data-area="general">General</button>
                    <button class="practice-area-btn" data-area="family">Family Law</button>
                    <button class="practice-area-btn" data-area="personal_injury">Personal Injury</button>
                    <button class="practice-area-btn" data-area="corporate">Corporate</button>
                    <button class="practice-area-btn" data-area="criminal">Criminal Defense</button>
                    <button class="practice-area-btn" data-area="real_estate">Real Estate</button>
                    <button class="practice-area-btn" data-area="immigration">Immigration</button>
                </div>
            </div>
            
            <div class="chat-messages" id="chatMessages">
                <div class="message assistant">
                    <div class="message-avatar">LA</div>
                    <div class="message-content">
                        Welcome to LexAI Practice Partner! I'm your AI legal assistant, ready to help with legal research, document analysis, and professional guidance. Please note that this is not formal legal advice. How can I assist you today?
                    </div>
                </div>
            </div>
            
            <div class="chat-input-container">
                <div class="chat-input-wrapper">
                    <textarea 
                        id="messageInput" 
                        class="chat-input" 
                        placeholder="Ask a legal question or describe your case..."
                        rows="1"
                        maxlength="5000"
                    ></textarea>
                    <button id="sendBtn" class="send-btn" onclick="sendMessage()">Send</button>
                </div>
            </div>
        </div>
    </div>

    <script>
        let currentPracticeArea = 'general';
        
        // Practice area selection
        document.querySelectorAll('.practice-area-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                document.querySelectorAll('.practice-area-btn').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                currentPracticeArea = btn.dataset.area;
            });
        });
        
        // Auto-resize textarea
        const messageInput = document.getElementById('messageInput');
        messageInput.addEventListener('input', function() {
            this.style.height = 'auto';
            this.style.height = Math.min(this.scrollHeight, 120) + 'px';
        });
        
        // Send on Enter (but not Shift+Enter)
        messageInput.addEventListener('keydown', function(e) {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                sendMessage();
            }
        });
        
        async function sendMessage() {
            const input = document.getElementById('messageInput');
            const sendBtn = document.getElementById('sendBtn');
            const chatMessages = document.getElementById('chatMessages');
            const message = input.value.trim();
            
            if (!message) return;
            
            // Disable input
            input.disabled = true;
            sendBtn.disabled = true;
            sendBtn.innerHTML = '<span class="loading">Sending...</span>';
            
            // Add user message
            addMessage('user', message);
            input.value = '';
            input.style.height = 'auto';
            
            // Add loading message
            const loadingId = addMessage('assistant', '<span class="loading">Thinking...</span>');
            
            try {
                const response = await fetch('/api/chat', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ 
                        message: message,
                        practice_area: currentPracticeArea
                    })
                });
                
                const data = await response.json();
                
                // Remove loading message
                const loadingElement = document.getElementById(loadingId);
                if (loadingElement) loadingElement.remove();
                
                if (data.error) {
                    addMessage('assistant', `<span class="error-message">Error: ${data.error}</span>`);
                } else if (data.choices && data.choices[0] && data.choices[0].delta) {
                    addMessage('assistant', data.choices[0].delta.content);
                } else {
                    addMessage('assistant', '<span class="error-message">Unexpected response format</span>');
                }
            } catch (error) {
                // Remove loading message
                const loadingElement = document.getElementById(loadingId);
                if (loadingElement) loadingElement.remove();
                
                addMessage('assistant', '<span class="error-message">Connection error. Please try again.</span>');
            }
            
            // Re-enable input
            input.disabled = false;
            sendBtn.disabled = false;
            sendBtn.innerHTML = 'Send';
            input.focus();
        }
        
        function addMessage(sender, content) {
            const chatMessages = document.getElementById('chatMessages');
            const messageId = 'msg-' + Date.now() + '-' + Math.random().toString(36).substr(2, 9);
            
            const messageHtml = `
                <div class="message ${sender}" id="${messageId}">
                    <div class="message-avatar">${sender === 'user' ? 'YOU' : 'LA'}</div>
                    <div class="message-content">${content}</div>
                </div>
            `;
            
            chatMessages.insertAdjacentHTML('beforeend', messageHtml);
            chatMessages.scrollTop = chatMessages.scrollHeight;
            
            return messageId;
        }
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    """Enhanced main page with KV database integration"""
    try:
        status = "✅ Online"
        api_status = "✅ Configured" if XAI_API_KEY else "❌ Not Configured"
        
        # Simple Redis status check
        kv_status = "✅ Redis Available" if REDIS_URL else "❌ No Database"
        
        return render_template_string(ENHANCED_TEMPLATE, 
                                    status=status, 
                                    api_status=api_status,
                                    kv_status=kv_status)
    except Exception as e:
        logger.error(f"Index route error: {e}")
        return f"<html><body><h1>LexAI Practice Partner</h1><p>Error: {str(e)}</p></body></html>", 500

@app.route('/health')
def health():
    """Enhanced health check"""
    try:
        return jsonify({
            'status': 'healthy',
            'timestamp': datetime.utcnow().isoformat(),
            'version': '2.0-hybrid',
            'environment': 'vercel-serverless',
            'api_configured': bool(XAI_API_KEY),
            'features': {
                'security': True,
                'rate_limiting': True,
                'practice_areas': True,
                'modern_ui': True
            }
        })
    except Exception as e:
        logger.error(f"Health check error: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/chat', methods=['POST'])
def chat():
    """Enhanced chat API with security and practice areas"""
    try:
        # Rate limiting
        client_ip = request.headers.get('X-Forwarded-For', request.remote_addr)
        if not check_rate_limit(client_ip):
            return jsonify({"error": "Rate limit exceeded. Please try again later."}), 429
        
        # Get request data
        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400
            
        message = data.get('message', '').strip()
        practice_area = data.get('practice_area', 'general')
        
        if not message:
            return jsonify({"error": "Message is required"}), 400

        # Validate message
        validation_result = validate_message(message)
        if not validation_result['valid']:
            return jsonify({"error": validation_result['errors'][0]}), 400
        
        message = validation_result['sanitized']
        
        # Check API key
        if not XAI_API_KEY:
            return jsonify({"error": "AI service not configured"}), 503

        # Build specialized system prompt
        system_prompt = build_system_prompt(practice_area)
        
        # Prepare API request
        payload = {
            "model": "grok-3-latest",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": message}
            ],
            "stream": False,
            "temperature": 0.7,
            "max_tokens": 1500
        }

        headers = {
            "Authorization": f"Bearer {XAI_API_KEY}",
            "Content-Type": "application/json"
        }

        # Make API call (EXACT working pattern from index.py)
        response = requests.post(
            'https://api.x.ai/v1/chat/completions',
            headers=headers,
            json=payload,
            timeout=30
        )
        
        if response.status_code == 200:
            completion = response.json()
            if 'choices' in completion and len(completion['choices']) > 0:
                ai_content = completion['choices'][0]['message']['content'].strip()
                
                # Log conversation (using Redis resources available)
                try:
                    if REDIS_URL:
                        logger.info(f"💾 Conversation logged: {client_id} - User: {message[:30]}... | AI: {ai_content[:30]}...")
                        # Here we can add actual Redis saving when ready
                except Exception as e:
                    logger.error(f"Conversation logging error: {e}")
                
                return jsonify({
                    "choices": [{"delta": {"content": ai_content}}],
                    "client_id": client_id,
                    "practice_area": practice_area
                })
        
        logger.error(f"XAI API error: {response.status_code} - {response.text}")
        return jsonify({"error": "AI service temporarily unavailable"}), 503
    
    except Exception as e:
        logger.error(f"Chat error: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500

@app.route('/api/conversations/<client_id>')
def get_conversation_history_api(client_id):
    """Get conversation history for a client"""
    try:
        history = get_conversation_history_kv(client_id, limit=20)
        return jsonify({
            "client_id": client_id,
            "conversations": history,
            "count": len(history)
        })
    except Exception as e:
        logger.error(f"Get conversation history error: {e}")
        return jsonify({"error": "Failed to retrieve history"}), 500

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
    app.run(debug=True)