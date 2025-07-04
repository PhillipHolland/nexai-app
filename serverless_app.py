"""
LexAI Practice Partner - Serverless Version of Working Local App
Based on localhost:5002 working version, simplified for Vercel
"""

import os
import json
import requests
import logging
from datetime import datetime
from flask import Flask, request, jsonify, render_template
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'lexai-serverless-2025')

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

@app.route('/')
def dashboard():
    """Main dashboard with practice areas and overview"""
    try:
        # Get basic stats for dashboard
        total_clients = 0  # Would come from database
        recent_clients = []  # Would come from database
        
        return render_template('dashboard.html', 
                             practice_areas=PRACTICE_AREAS,
                             total_clients=total_clients,
                             recent_clients=recent_clients)
    except Exception as e:
        logger.error(f"Dashboard error: {e}")
        # Enhanced fallback with modern styling
        return f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>LexAI Practice Partner - Dashboard</title>
            <style>
                body {{
                    font-family: 'Inter', system-ui, -apple-system, sans-serif;
                    background: linear-gradient(135deg, #1e40af 0%, #3b82f6 100%);
                    margin: 0;
                    padding: 20px;
                    min-height: 100vh;
                    color: #1f2937;
                }}
                .container {{
                    max-width: 1200px;
                    margin: 0 auto;
                    background: white;
                    border-radius: 16px;
                    padding: 32px;
                    box-shadow: 0 20px 40px rgba(0,0,0,0.1);
                }}
                .header {{
                    text-align: center;
                    margin-bottom: 40px;
                }}
                .header h1 {{
                    font-size: 3rem;
                    font-weight: 700;
                    margin-bottom: 8px;
                    background: linear-gradient(135deg, #1e40af, #3b82f6);
                    -webkit-background-clip: text;
                    -webkit-text-fill-color: transparent;
                }}
                .practice-grid {{
                    display: grid;
                    grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
                    gap: 24px;
                    margin-top: 32px;
                }}
                .practice-card {{
                    background: linear-gradient(135deg, #f9fafb 0%, #f3f4f6 100%);
                    border-radius: 12px;
                    padding: 24px;
                    border: 1px solid #e5e7eb;
                    transition: all 0.3s ease;
                    cursor: pointer;
                }}
                .practice-card:hover {{
                    transform: translateY(-4px);
                    box-shadow: 0 12px 24px rgba(0,0,0,0.1);
                }}
                .chat-link {{
                    display: inline-block;
                    background: linear-gradient(135deg, #1e40af, #3b82f6);
                    color: white;
                    padding: 16px 32px;
                    border-radius: 12px;
                    text-decoration: none;
                    font-weight: 600;
                    margin-top: 24px;
                    transition: all 0.3s ease;
                }}
                .chat-link:hover {{
                    transform: translateY(-2px);
                    box-shadow: 0 8px 16px rgba(30, 64, 175, 0.3);
                }}
                .status {{
                    display: flex;
                    gap: 16px;
                    margin-top: 24px;
                    flex-wrap: wrap;
                }}
                .status-item {{
                    background: #f0f9ff;
                    padding: 8px 16px;
                    border-radius: 8px;
                    font-size: 0.875rem;
                    border: 1px solid #e0f2fe;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>🏛️ LexAI Practice Partner</h1>
                    <p style="font-size: 1.25rem; color: #6b7280;">Professional AI-Powered Legal Assistant Platform</p>
                    
                    <div class="status">
                        <div class="status-item">✅ XAI API: {'Configured' if XAI_API_KEY else 'Not Set'}</div>
                        <div class="status-item">✅ Redis: {'Available' if REDIS_URL else 'Not Set'}</div>
                        <div class="status-item">✅ Neon DB: {'Available' if DATABASE_URL else 'Not Set'}</div>
                        <div class="status-item">🚀 Version: Serverless Enhanced</div>
                    </div>
                </div>
                
                <div class="practice-grid">
                    {chr(10).join([f'''
                    <div class="practice-card" onclick="window.location.href='/chat?area={area_id}'">
                        <h3 style="margin-bottom: 12px; color: {area['color']};">{area['name']}</h3>
                        <p style="color: #6b7280; margin-bottom: 16px;">Specialized AI assistance for {area['name'].lower()}</p>
                        <div style="font-size: 0.875rem; color: #9ca3af;">
                            Click to start conversation →
                        </div>
                    </div>
                    ''' for area_id, area in PRACTICE_AREAS.items()])}
                </div>
                
                <div style="text-align: center;">
                    <a href="/chat" class="chat-link">Start General Legal Chat</a>
                </div>
                
                <div style="margin-top: 32px; text-align: center;">
                    <a href="/health" style="color: #6b7280; text-decoration: none;">System Health Check</a>
                </div>
            </div>
        </body>
        </html>
        """

@app.route('/chat')
@app.route('/chat/<client_id>')
def chat_interface(client_id=None):
    """Enhanced chat interface matching local version"""
    try:
        # Get practice area from query params
        practice_area = request.args.get('area', 'general')
        
        return render_template('chat.html', 
                             current_client=client_id,
                             practice_areas=PRACTICE_AREAS,
                             selected_area=practice_area)
    except Exception as e:
        logger.error(f"Chat interface error: {e}")
        # Enhanced fallback chat interface with modern styling
        practice_area = request.args.get('area', 'general')
        selected_practice = PRACTICE_AREAS.get(practice_area, {'name': 'General Legal', 'color': '#1e40af'})
        
        return f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>LexAI Chat - {selected_practice['name']}</title>
            <style>
                body {{
                    font-family: 'Inter', system-ui, -apple-system, sans-serif;
                    background: linear-gradient(135deg, #1e40af 0%, #3b82f6 100%);
                    margin: 0;
                    padding: 20px;
                    min-height: 100vh;
                    color: #1f2937;
                }}
                .chat-container {{
                    max-width: 1000px;
                    margin: 0 auto;
                    background: white;
                    border-radius: 16px;
                    overflow: hidden;
                    box-shadow: 0 20px 40px rgba(0,0,0,0.1);
                    display: flex;
                    flex-direction: column;
                    height: 80vh;
                }}
                .chat-header {{
                    background: linear-gradient(135deg, {selected_practice['color']}, #3b82f6);
                    color: white;
                    padding: 20px 24px;
                    border-bottom: 1px solid rgba(255,255,255,0.1);
                }}
                .chat-header h1 {{
                    margin: 0;
                    font-size: 1.5rem;
                    font-weight: 600;
                }}
                .chat-header p {{
                    margin: 4px 0 0 0;
                    opacity: 0.9;
                    font-size: 0.875rem;
                }}
                .chat-messages {{
                    flex: 1;
                    padding: 24px;
                    overflow-y: auto;
                    background: #f9fafb;
                }}
                .message {{
                    margin-bottom: 16px;
                    display: flex;
                    align-items: flex-start;
                    gap: 12px;
                }}
                .message.user {{
                    justify-content: flex-end;
                }}
                .message.user .message-content {{
                    background: linear-gradient(135deg, #1e40af, #3b82f6);
                    color: white;
                }}
                .message-avatar {{
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
                }}
                .message.user .message-avatar {{
                    background: #1e40af;
                    color: white;
                }}
                .message-content {{
                    max-width: 70%;
                    padding: 12px 16px;
                    border-radius: 12px;
                    background: white;
                    box-shadow: 0 2px 8px rgba(0,0,0,0.05);
                    border: 1px solid #e5e7eb;
                }}
                .chat-input {{
                    border-top: 1px solid #e5e7eb;
                    padding: 20px 24px;
                    background: white;
                }}
                .input-group {{
                    display: flex;
                    gap: 12px;
                    align-items: flex-end;
                }}
                .message-input {{
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
                }}
                .message-input:focus {{
                    outline: none;
                    border-color: #1e40af;
                }}
                .send-button {{
                    padding: 12px 24px;
                    background: linear-gradient(135deg, #1e40af, #3b82f6);
                    color: white;
                    border: none;
                    border-radius: 12px;
                    font-weight: 600;
                    cursor: pointer;
                    transition: all 0.2s ease;
                }}
                .send-button:hover {{
                    transform: translateY(-1px);
                    box-shadow: 0 4px 12px rgba(30, 64, 175, 0.3);
                }}
                .send-button:disabled {{
                    opacity: 0.6;
                    cursor: not-allowed;
                    transform: none;
                }}
                .back-link {{
                    position: absolute;
                    top: 20px;
                    left: 20px;
                    background: rgba(255,255,255,0.2);
                    color: white;
                    padding: 8px 16px;
                    border-radius: 8px;
                    text-decoration: none;
                    font-size: 0.875rem;
                    backdrop-filter: blur(10px);
                }}
                .back-link:hover {{
                    background: rgba(255,255,255,0.3);
                }}
                .typing-indicator {{
                    display: none;
                    color: #6b7280;
                    font-style: italic;
                    font-size: 0.875rem;
                }}
            </style>
        </head>
        <body>
            <a href="/" class="back-link">← Dashboard</a>
            
            <div class="chat-container">
                <div class="chat-header">
                    <h1>🏛️ LexAI - {selected_practice['name']}</h1>
                    <p>Professional AI legal assistant specialized in {selected_practice['name'].lower()}</p>
                </div>
                
                <div class="chat-messages" id="chatMessages">
                    <div class="message assistant">
                        <div class="message-avatar">LA</div>
                        <div class="message-content">
                            Welcome to LexAI! I'm your AI legal assistant specializing in {selected_practice['name'].lower()}. 
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
                            placeholder="Ask a legal question about {selected_practice['name'].lower()}..."
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
                messageInput.addEventListener('input', function() {{
                    this.style.height = 'auto';
                    this.style.height = Math.min(this.scrollHeight, 120) + 'px';
                }});
                
                // Send on Enter (not Shift+Enter)
                messageInput.addEventListener('keydown', function(e) {{
                    if (e.key === 'Enter' && !e.shiftKey) {{
                        e.preventDefault();
                        sendMessage();
                    }}
                }});
                
                async function sendMessage() {{
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
                    
                    try {{
                        const response = await fetch('/api/chat', {{
                            method: 'POST',
                            headers: {{ 'Content-Type': 'application/json' }},
                            body: JSON.stringify({{ 
                                message: message,
                                practice_area: '{practice_area}',
                                client_id: currentClientId
                            }})
                        }});
                        
                        const data = await response.json();
                        
                        // Hide typing indicator
                        typingIndicator.style.display = 'none';
                        
                        if (data.choices && data.choices[0] && data.choices[0].delta) {{
                            addMessage('assistant', data.choices[0].delta.content);
                        }} else if (data.error) {{
                            addMessage('assistant', `Error: ${{data.error}}`, true);
                        }} else {{
                            addMessage('assistant', 'Unexpected response format', true);
                        }}
                    }} catch (error) {{
                        typingIndicator.style.display = 'none';
                        addMessage('assistant', 'Connection error. Please try again.', true);
                    }}
                    
                    // Re-enable input
                    isTyping = false;
                    input.disabled = false;
                    sendButton.disabled = false;
                    sendButton.textContent = 'Send';
                    input.focus();
                }}
                
                function addMessage(sender, content, isError = false) {{
                    const chatMessages = document.getElementById('chatMessages');
                    const messageDiv = document.createElement('div');
                    messageDiv.className = `message ${{sender}}`;
                    
                    const avatar = sender === 'user' ? 'YOU' : 'LA';
                    const errorStyle = isError ? 'color: #ef4444; font-style: italic;' : '';
                    
                    messageDiv.innerHTML = `
                        <div class="message-avatar">${{avatar}}</div>
                        <div class="message-content" style="${{errorStyle}}">${{content}}</div>
                    `;
                    
                    chatMessages.appendChild(messageDiv);
                    chatMessages.scrollTop = chatMessages.scrollHeight;
                }}
                
                // Focus input on load
                document.addEventListener('DOMContentLoaded', function() {{
                    messageInput.focus();
                }});
            </script>
        </body>
        </html>
        """

@app.route('/health')
def health_check():
    """Health check endpoint"""
    try:
        return jsonify({
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "version": "serverless-with-resources",
            "resources": {
                "xai_api": bool(XAI_API_KEY),
                "redis": bool(REDIS_URL),
                "neon_database": bool(DATABASE_URL)
            },
            "features": {
                "ai_chat": bool(XAI_API_KEY),
                "conversation_storage": bool(REDIS_URL or DATABASE_URL),
                "practice_areas": True
            }
        })
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return jsonify({
            "status": "error",
            "error": str(e)
        }), 500

@app.route('/api/chat', methods=['POST'])
def api_chat():
    """Enhanced chat API (from working local version with proven XAI pattern)"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400
            
        message = data.get('message', '').strip()
        practice_area = data.get('practice_area', 'general')
        client_id = data.get('client_id', f'client_{datetime.utcnow().strftime("%Y%m%d_%H%M%S")}')
        
        if not message:
            return jsonify({"error": "Message is required"}), 400

        if not XAI_API_KEY:
            return jsonify({"error": "AI service not configured"}), 503

        # Build specialized system prompt
        system_prompt = build_system_prompt(practice_area)
        
        # API call payload
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
                
                # Log conversation using available resources
                try:
                    if REDIS_URL:
                        logger.info(f"💾 [REDIS] Conversation: {client_id} | {practice_area} | User: {message[:30]}... | AI: {assistant_content[:30]}...")
                    elif DATABASE_URL:
                        logger.info(f"🗄️ [NEON] Conversation: {client_id} | {practice_area} | User: {message[:30]}... | AI: {assistant_content[:30]}...")
                    else:
                        logger.info(f"📝 [LOG] Conversation: {client_id} | {practice_area} | User: {message[:30]}... | AI: {assistant_content[:30]}...")
                except Exception as e:
                    logger.error(f"Conversation logging error: {e}")
                
                return jsonify({
                    "choices": [{"delta": {"content": assistant_content}}],
                    "client_id": client_id,
                    "practice_area": practice_area
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