from flask import Flask, render_template, request, jsonify, Response, session
import re
import PyPDF2
import requests
import os
import json
from dotenv import load_dotenv
from functools import wraps
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'xAI-LexAI-2025-Secret'
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_SECURE'] = False
app.config['SESSION_COOKIE_HTTPONLY'] = True
load_dotenv()

# Regex patterns for PII
EMAIL_PATTERN = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
PHONE_PATTERN = r'\b(\+\d{1,3}[-.]?)?\(?\d{3}\)?[-.]?\d{3}[-.]?\d{4}\b'
NAME_PATTERN = r'\b[A-Z][a-z]+ [A-Z][a-z]+\b'
ADDRESS_PATTERN = r'\b\d{1,5} [A-Za-z0-9\s]+, [A-Za-z\s]+, [A-Z]{2} \d{5}\b'

def anonymize_text(text):
    text = re.sub(EMAIL_PATTERN, '<REDACTED>', text)
    text = re.sub(PHONE_PATTERN, '<REDACTED>', text)
    text = re.sub(NAME_PATTERN, '<REDACTED>', text)
    text = re.sub(ADDRESS_PATTERN, '<REDACTED>', text)
    return text

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        print("Session in login_required:", dict(session))
        print("Cookies in request:", request.cookies)
        if 'logged_in' not in session:
            return render_template('login.html'), 403
        return f(*args, **kwargs)
    return decorated_function

@app.route('/login', methods=['POST'])
def login():
    data = request.json
    password = data.get('password', '')
    print("Login attempt with password:", password)
    if password == 'LexAI2025!':
        session['logged_in'] = True
        print("Session after login:", dict(session))
        return jsonify({'success': True})
    return jsonify({'error': 'Invalid password'}), 401

@app.route('/logout', methods=['POST'])
def logout():
    print("Session before logout:", dict(session))
    session.pop('logged_in', None)
    print("Session after logout:", dict(session))
    return jsonify({'success': True})

@app.route('/')
def index():
    print("Session in index:", dict(session))
    print("Cookies in index:", request.cookies)
    if 'logged_in' not in session:
        return render_template('login.html')
    clients = [f.replace('.json', '') for f in os.listdir('data') if f.endswith('.json')]
    return render_template('index.html', clients=clients)

@app.route('/api/chat', methods=['POST'])
@login_required
def chat():
    try:
        print("Session in /api/chat:", dict(session))
        print("Cookies in /api/chat:", request.cookies)
        data = request.json
        messages = data.get('messages', [])
        client_id = data.get('client_id', '')
        print("Chat request data:", data)
        if not messages or not isinstance(messages, list) or not client_id:
            return jsonify({'error': 'Invalid request'}), 400

        last_message = messages[-1]['content']
        anonymized_text = anonymize_text(last_message)

        # Load client data
        client_file = f'data/{client_id}.json'
        client_data = {'documents': [], 'history': [], 'info': {}}
        if os.path.exists(client_file):
            with open(client_file, 'r') as f:
                client_data = json.load(f)
            if 'history' not in client_data:
                client_data['history'] = []

        xai_api_key = os.getenv('XAI_API_KEY')
        if not xai_api_key:
            return jsonify({'error': 'XAI_API_KEY not set'}), 500

        headers = {
            'Authorization': f'Bearer {xai_api_key}',
            'Content-Type': 'application/json',
        }
        payload = {
            'messages': [
                {'role': 'system', 'content': f'You are LexAI, a family law assistant for client {client_id}. Draft professional communications, analyze financial statements, legal documents, and court filings related to family law (e.g., divorce, custody). Identify issues and suggest solutions. Client documents: {json.dumps(client_data["documents"])}'},
                {'role': 'user', 'content': anonymized_text},
            ],
            'model': 'grok-3-latest',
            'stream': True,
            'temperature': 0,
        }

        response = requests.post('https://api.x.ai/v1/chat/completions', headers=headers, json=payload, stream=True)
        if not response.ok:
            print("xAI API response:", response.status_code, response.text)
            return jsonify({'error': 'xAI API error'}), response.status_code

        # Store user message in history
        client_data['history'].append({
            'role': 'user',
            'content': anonymized_text,
            'timestamp': datetime.utcnow().isoformat()
        })

        def generate():
            message_content = ''
            for chunk in response.iter_content(chunk_size=1024):
                if chunk:
                    chunk_str = chunk.decode('utf-8')
                    lines = chunk_str.split('\n')
                    for line in lines:
                        if line.startswith('data: ') and line != 'data: [DONE]':
                            try:
                                data = json.loads(line.replace('data: ', ''))
                                if data.get('choices') and data['choices'][0].get('delta') and 'content' in data['choices'][0]['delta']:
                                    content = data['choices'][0]['delta']['content']
                                    anonymized_content = anonymize_text(content)
                                    message_content += anonymized_content
                                    data['choices'][0]['delta']['content'] = anonymized_content
                                    yield f"data: {json.dumps(data)}\n\n"
                                else:
                                    yield f"{line}\n\n"
                            except json.JSONDecodeError:
                                print("Failed to parse chunk:", line)
                                yield f"{line}\n\n"
                        else:
                            yield f"{line}\n\n"
            # Store assistant response in history
            client_data['history'].append({
                'role': 'assistant',
                'content': message_content,
                'timestamp': datetime.utcnow().isoformat()
            })
            with open(client_file, 'w') as f:
                json.dump(client_data, f)

        return Response(generate(), content_type='text/event-stream')
    except Exception as e:
        print("Chat error:", str(e))
        return jsonify({'error': str(e)}), 500

@app.route('/api/upload', methods=['POST'])
@login_required
def upload():
    try:
        print("Session in /api/upload:", dict(session))
        print("Cookies in /api/upload:", request.cookies)
        file = request.files.get('file')
        client_id = request.form.get('client_id', '')
        print("Upload request: client_id=", client_id, "file=", file.filename if file else None)
        if not file or not client_id:
            return jsonify({'error': 'No file or client_id provided'}), 400

        if file.mimetype == 'text/plain':
            text = file.read().decode('utf-8')
        elif file.mimetype == 'application/pdf':
            pdf_reader = PyPDF2.PdfReader(file)
            text = ''
            for page in pdf_reader.pages:
                text += page.extract_text() or ''
        else:
            return jsonify({'error': 'Unsupported file type'}), 400

        # Store document in client data
        client_file = f'data/{client_id}.json'
        client_data = {'documents': [], 'history': [], 'info': {}}
        if os.path.exists(client_file):
            with open(client_file, 'r') as f:
                client_data = json.load(f)
            if 'history' not in client_data:
                client_data['history'] = []
        client_data['documents'].append({
            'filename': file.filename,
            'text': text,
            'upload_date': datetime.utcnow().isoformat()
        })
        with open(client_file, 'w') as f:
            json.dump(client_data, f)

        return jsonify({'text': text})
    except Exception as e:
        print("Upload error:", str(e))
        return jsonify({'error': str(e)}), 500

@app.route('/api/client/<client_id>', methods=['GET', 'POST'])
@login_required
def client_info(client_id):
    client_file = f'data/{client_id}.json'
    client_data = {'documents': [], 'history': [], 'info': {}}
    if os.path.exists(client_file):
        with open(client_file, 'r') as f:
            client_data = json.load(f)
        if 'history' not in client_data:
            client_data['history'] = []

    if request.method == 'POST':
        data = request.json
        client_data['info'] = {
            'name': anonymize_text(data.get('name', '')),
            'case_number': data.get('case_number', ''),
            'email': anonymize_text(data.get('email', '')),
            'phone': anonymize_text(data.get('phone', '')),
            'case_type': data.get('case_type', ''),
            'notes': data.get('notes', '')
        }
        with open(client_file, 'w') as f:
            json.dump(client_data, f)
        return jsonify({'success': True})

    return jsonify(client_data)

@app.route('/api/new_client', methods=['POST'])
@login_required
def new_client():
    data = request.json
    client_id = data.get('client_id', '').lower().replace(' ', '_')
    if not client_id or os.path.exists(f'data/{client_id}.json'):
        return jsonify({'error': 'Invalid or existing client ID'}), 400
    client_data = {
        'documents': [],
        'history': [],
        'info': {
            'name': anonymize_text(data.get('name', '')),
            'case_number': data.get('case_number', ''),
            'email': anonymize_text(data.get('email', '')),
            'phone': anonymize_text(data.get('phone', '')),
            'case_type': data.get('case_type', ''),
            'notes': data.get('notes', '')
        }
    }
    with open(f'data/{client_id}.json', 'w') as f:
        json.dump(client_data, f)
    return jsonify({'success': True})

@app.route('/api/new_conversation/<client_id>', methods=['POST'])
@login_required
def new_conversation(client_id):
    client_file = f'data/{client_id}.json'
    if not os.path.exists(client_file):
        return jsonify({'error': 'Client not found'}), 404
    with open(client_file, 'r') as f:
        client_data = json.load(f)
    if 'history' not in client_data:
        client_data['history'] = []
    # Clear history for new conversation
    client_data['history'] = []
    with open(client_file, 'w') as f:
        json.dump(client_data, f)
    return jsonify({'success': True})

@app.route('/api/export/<client_id>', methods=['GET'])
@login_required
def export_history(client_id):
    client_file = f'data/{client_id}.json'
    if not os.path.exists(client_file):
        return jsonify({'error': 'Client not found'}), 404
    with open(client_file, 'r') as f:
        client_data = json.load(f)
    if 'history' not in client_data:
        client_data['history'] = []
    history_text = ''
    for entry in client_data['history']:
        role = 'User' if entry['role'] == 'user' else 'LexAI'
        history_text += f"[{entry['timestamp']}] {role}: {entry['content']}\n\n"
    return Response(history_text, mimetype='text/plain', headers={'Content-Disposition': f'attachment;filename={client_id}_history.txt'})

if __name__ == '__main__':
    app.run(debug=True)
