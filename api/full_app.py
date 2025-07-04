"""
LexAI Practice Partner - Full Serverless Version
Uses Neon PostgreSQL and all enterprise features, optimized for Vercel
"""

import os
import json
import requests
import logging
import re
import hashlib
import psycopg2
from datetime import datetime, timedelta
from flask import Flask, request, jsonify, render_template_string, session, g
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'lexai-production-2025')

# Database configuration using Neon
DATABASE_URL = os.environ.get('DATABASE_URL') or os.environ.get('POSTGRES_URL')

# API configuration
XAI_API_KEY = (os.environ.get('XAI_API_KEY') or os.environ.get('xai_api_key') or '').strip()

# Security configuration
MAX_MESSAGE_LENGTH = 5000
RATE_LIMIT_REQUESTS = 100
RATE_LIMIT_WINDOW = 3600

# Practice areas configuration
PRACTICE_AREAS = {
    'family': {
        'name': 'Family Law',
        'icon': 'family',
        'color': '#8B5CF6',
        'system_prompt': 'You are LexAI, specializing in family law including divorce, custody, child support, and domestic relations. Provide practical guidance while noting this is not formal legal advice.'
    },
    'personal_injury': {
        'name': 'Personal Injury',
        'icon': 'shield',
        'color': '#EF4444',
        'system_prompt': 'You are LexAI, specializing in personal injury law including accidents, medical malpractice, and insurance claims. Provide practical guidance while noting this is not formal legal advice.'
    },
    'corporate': {
        'name': 'Corporate Law',
        'icon': 'building',
        'color': '#3B82F6',
        'system_prompt': 'You are LexAI, specializing in corporate law including contracts, compliance, business formation, and commercial transactions. Provide practical guidance while noting this is not formal legal advice.'
    },
    'criminal': {
        'name': 'Criminal Defense',
        'icon': 'scale',
        'color': '#F59E0B',
        'system_prompt': 'You are LexAI, specializing in criminal defense including charges, procedures, rights, and court processes. Provide practical guidance while noting this is not formal legal advice.'
    },
    'real_estate': {
        'name': 'Real Estate',
        'icon': 'home',
        'color': '#10B981',
        'system_prompt': 'You are LexAI, specializing in real estate law including transactions, contracts, zoning, and property disputes. Provide practical guidance while noting this is not formal legal advice.'
    },
    'immigration': {
        'name': 'Immigration',
        'icon': 'globe',
        'color': '#6366F1',
        'system_prompt': 'You are LexAI, specializing in immigration law including visas, citizenship, deportation defense, and family reunification. Provide practical guidance while noting this is not formal legal advice.'
    }
}

def get_db_connection():
    """Get database connection using Neon PostgreSQL"""
    try:
        if DATABASE_URL:
            conn = psycopg2.connect(DATABASE_URL, sslmode='require')
            return conn
        else:
            logger.error("No DATABASE_URL configured")
            return None
    except Exception as e:
        logger.error(f"Database connection error: {e}")
        return None

def init_database():
    """Initialize database tables if they don't exist"""
    try:
        conn = get_db_connection()
        if not conn:
            return False
            
        cursor = conn.cursor()
        
        # Users table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                email VARCHAR(255) UNIQUE NOT NULL,
                password_hash VARCHAR(255) NOT NULL,
                name VARCHAR(255) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_active BOOLEAN DEFAULT TRUE
            )
        """)
        
        # Clients table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS clients (
                id VARCHAR(255) PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                case_type VARCHAR(100),
                email VARCHAR(255),
                phone VARCHAR(50),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Conversations table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id SERIAL PRIMARY KEY,
                client_id VARCHAR(255) REFERENCES clients(id),
                role VARCHAR(20) NOT NULL,
                content TEXT NOT NULL,
                practice_area VARCHAR(50),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Rate limiting table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS rate_limits (
                ip_hash VARCHAR(64) PRIMARY KEY,
                request_count INTEGER DEFAULT 0,
                window_start TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        conn.commit()
        cursor.close()
        conn.close()
        return True
        
    except Exception as e:
        logger.error(f"Database initialization error: {e}")
        return False

def validate_message(message):
    """Validate and sanitize message input"""
    errors = []
    
    if not message or len(message.strip()) == 0:
        errors.append("Message cannot be empty")
    if len(message) > MAX_MESSAGE_LENGTH:
        errors.append(f"Message too long (max {MAX_MESSAGE_LENGTH} characters)")
    
    # Security patterns
    sql_patterns = [r"(\bUNION\b.*\bSELECT\b)", r"(\bDROP\b.*\bTABLE\b)", r"(\';.*--)"]
    xss_patterns = [r"<script[^>]*>", r"javascript:", r"onload\s*="]
    
    message_upper = message.upper()
    for pattern in sql_patterns:
        if re.search(pattern, message_upper, re.IGNORECASE):
            errors.append("Potentially malicious content detected")
            break
            
    for pattern in xss_patterns:
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

def check_rate_limit(client_ip):
    """Database-backed rate limiting"""
    try:
        conn = get_db_connection()
        if not conn:
            return True  # Allow if database unavailable
            
        cursor = conn.cursor()
        ip_hash = hashlib.md5(client_ip.encode()).hexdigest()
        now = datetime.utcnow()
        window_start = now - timedelta(seconds=RATE_LIMIT_WINDOW)
        
        # Clean old entries
        cursor.execute("DELETE FROM rate_limits WHERE window_start < %s", (window_start,))
        
        # Check current rate
        cursor.execute("SELECT request_count FROM rate_limits WHERE ip_hash = %s", (ip_hash,))
        result = cursor.fetchone()
        
        if result and result[0] >= RATE_LIMIT_REQUESTS:
            cursor.close()
            conn.close()
            return False
        
        # Update or insert
        cursor.execute("""
            INSERT INTO rate_limits (ip_hash, request_count, window_start)
            VALUES (%s, 1, %s)
            ON CONFLICT (ip_hash) 
            DO UPDATE SET request_count = rate_limits.request_count + 1
        """, (ip_hash, now))
        
        conn.commit()
        cursor.close()
        conn.close()
        return True
        
    except Exception as e:
        logger.error(f"Rate limiting error: {e}")
        return True  # Allow if error

def save_conversation(client_id, role, content, practice_area):
    """Save conversation to database"""
    try:
        conn = get_db_connection()
        if not conn:
            return False
            
        cursor = conn.cursor()
        
        # Ensure client exists
        cursor.execute("""
            INSERT INTO clients (id, name, case_type) 
            VALUES (%s, %s, %s) 
            ON CONFLICT (id) DO NOTHING
        """, (client_id, f"Client {client_id[-8:]}", practice_area.replace('_', ' ').title()))
        
        # Save conversation
        cursor.execute("""
            INSERT INTO conversations (client_id, role, content, practice_area)
            VALUES (%s, %s, %s, %s)
        """, (client_id, role, content, practice_area))
        
        conn.commit()
        cursor.close()
        conn.close()
        return True
        
    except Exception as e:
        logger.error(f"Save conversation error: {e}")
        return False

def get_conversation_history(client_id, limit=10):
    """Get conversation history from database"""
    try:
        conn = get_db_connection()
        if not conn:
            return []
            
        cursor = conn.cursor()
        cursor.execute("""
            SELECT role, content, created_at 
            FROM conversations 
            WHERE client_id = %s 
            ORDER BY created_at DESC 
            LIMIT %s
        """, (client_id, limit))
        
        results = cursor.fetchall()
        cursor.close()
        conn.close()
        
        return [{'role': r[0], 'content': r[1], 'timestamp': r[2]} for r in reversed(results)]
        
    except Exception as e:
        logger.error(f"Get conversation history error: {e}")
        return []

# Initialize database on startup
init_database()

# Enhanced HTML template with full features
FULL_TEMPLATE = """
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
            max-width: 1400px;
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
        
        .main-content {
            flex: 1;
            display: grid;
            grid-template-columns: 300px 1fr;
            gap: 24px;
        }
        
        .sidebar {
            background: var(--card-bg);
            backdrop-filter: blur(10px);
            border-radius: 16px;
            padding: 24px;
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
            border: 1px solid rgba(255, 255, 255, 0.2);
            height: fit-content;
        }
        
        .chat-container {
            background: var(--card-bg);
            backdrop-filter: blur(10px);
            border-radius: 16px;
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
            border: 1px solid rgba(255, 255, 255, 0.2);
            display: flex;
            flex-direction: column;
            overflow: hidden;
            height: 600px;
        }
        
        .practice-areas {
            margin-bottom: 24px;
        }
        
        .practice-area-btn {
            display: block;
            width: 100%;
            padding: 12px 16px;
            margin-bottom: 8px;
            border: 1px solid var(--border-color);
            border-radius: 8px;
            background: white;
            color: var(--text-secondary);
            text-align: left;
            cursor: pointer;
            transition: all 0.2s ease;
            font-size: 0.875rem;
        }
        
        .practice-area-btn:hover,
        .practice-area-btn.active {
            background: var(--primary-color);
            color: white;
            border-color: var(--primary-color);
            transform: translateX(4px);
        }
        
        .chat-messages {
            flex: 1;
            padding: 24px;
            overflow-y: auto;
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
        
        .recent-clients {
            margin-top: 24px;
        }
        
        .client-item {
            padding: 12px;
            background: rgba(255, 255, 255, 0.5);
            border-radius: 8px;
            margin-bottom: 8px;
            cursor: pointer;
            transition: all 0.2s ease;
        }
        
        .client-item:hover {
            background: rgba(255, 255, 255, 0.8);
            transform: translateX(4px);
        }
        
        @media (max-width: 1024px) {
            .main-content {
                grid-template-columns: 1fr;
            }
            .sidebar {
                order: 2;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🏛️ LexAI Practice Partner</h1>
            <p style="color: var(--text-secondary); margin-bottom: 16px;">
                Enterprise legal AI platform with database integration and advanced features
            </p>
            
            <div class="status-grid">
                <div class="status-item">
                    <div style="font-size: 0.875rem; color: var(--text-secondary);">System Status</div>
                    <div style="font-size: 1.125rem; font-weight: 600; color: var(--success-color);">{{ status }}</div>
                </div>
                <div class="status-item">
                    <div style="font-size: 0.875rem; color: var(--text-secondary);">AI Service</div>
                    <div style="font-size: 1.125rem; font-weight: 600; color: {{ 'var(--success-color)' if api_status == '✅ Configured' else 'var(--warning-color)' }};">{{ api_status }}</div>
                </div>
                <div class="status-item">
                    <div style="font-size: 0.875rem; color: var(--text-secondary);">Database</div>
                    <div style="font-size: 1.125rem; font-weight: 600; color: {{ 'var(--success-color)' if db_status == '✅ Connected' else 'var(--error-color)' }};">{{ db_status }}</div>
                </div>
                <div class="status-item">
                    <div style="font-size: 0.875rem; color: var(--text-secondary);">Version</div>
                    <div style="font-size: 1.125rem; font-weight: 600;">Full Enterprise</div>
                </div>
            </div>
        </div>
        
        <div class="main-content">
            <div class="sidebar">
                <div class="practice-areas">
                    <h3 style="margin-bottom: 16px; color: var(--text-primary);">Practice Areas</h3>
                    <button class="practice-area-btn active" data-area="general">General Legal</button>
                    <button class="practice-area-btn" data-area="family">👨‍👩‍👧‍👦 Family Law</button>
                    <button class="practice-area-btn" data-area="personal_injury">🛡️ Personal Injury</button>
                    <button class="practice-area-btn" data-area="corporate">🏢 Corporate Law</button>
                    <button class="practice-area-btn" data-area="criminal">⚖️ Criminal Defense</button>
                    <button class="practice-area-btn" data-area="real_estate">🏠 Real Estate</button>
                    <button class="practice-area-btn" data-area="immigration">🌍 Immigration</button>
                </div>
                
                <div class="recent-clients">
                    <h3 style="margin-bottom: 16px; color: var(--text-primary);">Recent Clients</h3>
                    <div id="clientsList">
                        <div class="client-item">
                            <div style="font-weight: 600;">Welcome</div>
                            <div style="font-size: 0.875rem; color: var(--text-secondary);">Start your first conversation</div>
                        </div>
                    </div>
                </div>
            </div>
            
            <div class="chat-container">
                <div class="chat-messages" id="chatMessages">
                    <div class="message assistant">
                        <div class="message-avatar">LA</div>
                        <div class="message-content">
                            Welcome to LexAI Practice Partner! I'm your enterprise-grade AI legal assistant with database integration and advanced features. Select a practice area and start a conversation. All interactions are saved for your reference.
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
    </div>

    <script>
        let currentPracticeArea = 'general';
        let currentClientId = 'client_' + Math.random().toString(36).substr(2, 9);
        
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
        
        // Send on Enter
        messageInput.addEventListener('keydown', function(e) {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                sendMessage();
            }
        });
        
        async function sendMessage() {
            const input = document.getElementById('messageInput');
            const sendBtn = document.getElementById('sendBtn');
            const message = input.value.trim();
            
            if (!message) return;
            
            // Disable input
            input.disabled = true;
            sendBtn.disabled = true;
            sendBtn.innerHTML = 'Sending...';
            
            // Add user message
            addMessage('user', message);
            input.value = '';
            input.style.height = 'auto';
            
            // Add loading message
            const loadingId = addMessage('assistant', 'Thinking...');
            
            try {
                const response = await fetch('/api/chat', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ 
                        message: message,
                        practice_area: currentPracticeArea,
                        client_id: currentClientId
                    })
                });
                
                const data = await response.json();
                
                // Remove loading message
                document.getElementById(loadingId)?.remove();
                
                if (data.error) {
                    addMessage('assistant', `Error: ${data.error}`, true);
                } else if (data.choices?.[0]?.delta?.content) {
                    addMessage('assistant', data.choices[0].delta.content);
                } else {
                    addMessage('assistant', 'Unexpected response format', true);
                }
            } catch (error) {
                document.getElementById(loadingId)?.remove();
                addMessage('assistant', 'Connection error. Please try again.', true);
            }
            
            // Re-enable input
            input.disabled = false;
            sendBtn.disabled = false;
            sendBtn.innerHTML = 'Send';
            input.focus();
        }
        
        function addMessage(sender, content, isError = false) {
            const chatMessages = document.getElementById('chatMessages');
            const messageId = 'msg-' + Date.now() + '-' + Math.random().toString(36).substr(2, 9);
            
            const errorClass = isError ? ' error-message' : '';
            const messageHtml = `
                <div class="message ${sender}" id="${messageId}">
                    <div class="message-avatar">${sender === 'user' ? 'YOU' : 'LA'}</div>
                    <div class="message-content${errorClass}" style="${isError ? 'color: var(--error-color); font-style: italic;' : ''}">${content}</div>
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
    """Full-featured main page"""
    try:
        status = "✅ Online"
        api_status = "✅ Configured" if XAI_API_KEY else "❌ Not Configured"
        
        # Test database connection
        conn = get_db_connection()
        db_status = "✅ Connected" if conn else "❌ Disconnected"
        if conn:
            conn.close()
        
        return render_template_string(FULL_TEMPLATE, 
                                    status=status, 
                                    api_status=api_status,
                                    db_status=db_status)
    except Exception as e:
        logger.error(f"Index route error: {e}")
        return f"<html><body><h1>LexAI Practice Partner</h1><p>Error: {str(e)}</p></body></html>", 500

@app.route('/health')
def health():
    """Comprehensive health check"""
    try:
        conn = get_db_connection()
        db_healthy = bool(conn)
        if conn:
            conn.close()
            
        return jsonify({
            'status': 'healthy' if db_healthy else 'degraded',
            'timestamp': datetime.utcnow().isoformat(),
            'version': 'full-enterprise',
            'environment': 'vercel-serverless',
            'components': {
                'api_configured': bool(XAI_API_KEY),
                'database': 'connected' if db_healthy else 'disconnected',
                'rate_limiting': True,
                'security': True
            }
        })
    except Exception as e:
        logger.error(f"Health check error: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/chat', methods=['POST'])
def chat():
    """Full-featured chat API with database integration"""
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
        client_id = data.get('client_id', f'client_{datetime.utcnow().strftime("%Y%m%d_%H%M%S")}')
        
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

        # Get system prompt for practice area
        system_prompt = PRACTICE_AREAS.get(practice_area, {}).get(
            'system_prompt', 
            'You are LexAI, a professional legal AI assistant. Provide accurate legal guidance while noting this is not formal legal advice.'
        )
        
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

        # Make API call
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
                
                # Save conversation to database
                save_conversation(client_id, 'user', message, practice_area)
                save_conversation(client_id, 'assistant', ai_content, practice_area)
                
                return jsonify({
                    "choices": [{"delta": {"content": ai_content}}],
                    "practice_area": practice_area,
                    "client_id": client_id
                })
        
        logger.error(f"XAI API error: {response.status_code} - {response.text}")
        return jsonify({"error": "AI service temporarily unavailable"}), 503
    
    except Exception as e:
        logger.error(f"Chat error: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500

@app.route('/api/clients/<client_id>/history')
def get_client_history(client_id):
    """Get conversation history for a client"""
    try:
        history = get_conversation_history(client_id)
        return jsonify({"history": history})
    except Exception as e:
        logger.error(f"Get history error: {e}")
        return jsonify({"error": "Failed to retrieve history"}), 500

# Error handlers
@app.errorhandler(404)
def not_found(e):
    return jsonify({"error": "Not found"}), 404

@app.errorhandler(500)
def server_error(e):
    return jsonify({"error": "Internal server error"}), 500

# Security headers
@app.after_request
def add_security_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    return response

if __name__ == '__main__':
    app.run(debug=True)