import os
import json
import requests
from flask import Flask, request, jsonify, render_template
from werkzeug.utils import secure_filename
import re
from datetime import datetime, timezone
import logging
from database import db, init_db, get_client_data, update_client_info, add_conversation, clear_conversation_history, add_document, Client

app = Flask(__name__)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Database configuration
DATABASE_URL = os.getenv('DATABASE_URL')
if DATABASE_URL:
    # Handle Heroku/Vercel postgres:// URLs
    if DATABASE_URL.startswith('postgres://'):
        DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://') 
    app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
else:
    # Fallback to SQLite for local development
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///lexai.db'

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize database
init_db(app)

# Securely load API key from environment variable
XAI_API_KEY = os.getenv("XAI_API_KEY")
if not XAI_API_KEY:
    raise ValueError("XAI_API_KEY environment variable not set")

# Use /tmp for uploads on Vercel (read-only file system workaround)
UPLOAD_FOLDER = '/tmp/uploads'
ALLOWED_EXTENSIONS = {'txt', 'pdf', 'doc', 'docx'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Database is now handled by database.py - no mock data needed

# Class to manage tokenization and de-tokenization
class Anonymizer:
    def __init__(self):
        self.token_map = {}  # Maps tokens back to original PII
        self.name_counter = 0
        self.email_counter = 0
        self.phone_counter = 0
        self.ssn_counter = 0
        self.credit_card_counter = 0
        # Common phrases that should not be tokenized as names
        self.excluded_phrases = {
            "draft an", "email to", "meeting on", "about a", "to the",
            "for a", "on the", "at the", "with a", "in the",
            "at john", "com about",
            "brief summary", "of the", "benefits of", "do list", "for productivity",
            "legal advice", "with email"
        }

    def tokenize(self, text):
        if not text:
            return text, {}

        logger.info(f"Original text: {text}")

        patterns = [
            # Emails first to avoid interference from name tokenization
            (r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', 'EMAIL'),
            # Names: Match capitalized words, exclude email-like patterns and tokens
            # Require both words to start with uppercase letters (proper nouns)
            (r'\b(?:Mr\.|Mrs\.|Ms\.|Dr\.|[A-Z][a-z]+) [A-Z][a-z]+\b(?!\S*@\S*\.\S*\b)(?!(?:Person|Email|Phone|SSN|CreditCard)[A-Z])', 'NAME'),
            (r'\b\d{3}-\d{3}-\d{4}\b', 'PHONE'),  # Phone numbers (e.g., 555-123-4567)
            (r'\b\d{3}-\d{2}-\d{4}\b', 'SSN'),  # Social Security Numbers (e.g., 123-45-6789)
            (r'\b\d{4}-\d{4}-\d{4}-\d{4}\b', 'CREDIT_CARD')  # Credit card numbers
        ]

        tokenized_text = text
        token_map = {}
        for pattern, token_prefix in patterns:
            matches = re.finditer(pattern, tokenized_text)
            for match in matches:
                original = match.group()
                # Skip tokenization if the match is in excluded phrases (for names only)
                if token_prefix == 'NAME' and original.lower() in self.excluded_phrases:
                    continue
                # Additional check: Skip if the match contains an existing token
                if any(token in original for token in token_map.keys()):
                    continue
                if token_prefix == 'NAME':
                    self.name_counter += 1
                    token = f"Person{chr(64 + self.name_counter)}"  # PersonA, PersonB, etc.
                elif token_prefix == 'EMAIL':
                    self.email_counter += 1
                    token = f"Email{chr(64 + self.email_counter)}"  # EmailA, EmailB, etc.
                elif token_prefix == 'PHONE':
                    self.phone_counter += 1
                    token = f"Phone{chr(64 + self.phone_counter)}"  # PhoneA, PhoneB, etc.
                elif token_prefix == 'SSN':
                    self.ssn_counter += 1
                    token = f"SSN{chr(64 + self.ssn_counter)}"  # SSNA, SSNB, etc.
                elif token_prefix == 'CREDIT_CARD':
                    self.credit_card_counter += 1
                    token = f"CreditCard{chr(64 + self.credit_card_counter)}"  # CreditCardA, CreditCardB, etc.
                token_map[token] = original
                tokenized_text = tokenized_text.replace(original, token)

        logger.info(f"Tokenized text: {tokenized_text}")
        logger.info(f"Token map: {token_map}")
        return tokenized_text, token_map

    def detokenize(self, text, token_map):
        if not text or not token_map:
            return text

        detokenized_text = text
        previous_text = None
        # Recursively replace tokens until no changes occur (handles nested tokens)
        while detokenized_text != previous_text:
            previous_text = detokenized_text
            for token, original in token_map.items():
                detokenized_text = detokenized_text.replace(token, original)
            logger.info(f"Intermediate de-tokenized text: {detokenized_text}")
        logger.info(f"Final de-tokenized text: {detokenized_text}")
        return detokenized_text

# Function to anonymize client info
def anonymize_client_info(client_info, anonymizer):
    if not client_info:
        return client_info, {}

    anonymized_info = client_info.copy()
    token_map = {}
    sensitive_fields = ['name', 'email', 'phone', 'case_number']
    for field in sensitive_fields:
        if field in anonymized_info and anonymized_info[field]:
            tokenized_value, field_tokens = anonymizer.tokenize(anonymized_info[field])
            anonymized_info[field] = tokenized_value
            token_map.update(field_tokens)
    if 'notes' in anonymized_info:
        tokenized_notes, notes_tokens = anonymizer.tokenize(anonymized_info['notes'])
        anonymized_info['notes'] = tokenized_notes
        token_map.update(notes_tokens)
    return anonymized_info, token_map

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/client/<client_id>', methods=['GET', 'POST'])
def client_data(client_id):
    if request.method == 'POST':
        data = request.get_json()
        updated_client = update_client_info(client_id, data)
        logger.info(f"Updated client info for {client_id}: {data}")
        return jsonify({"success": True})

    # Get client data from database
    client_data = get_client_data(client_id)
    if not client_data:
        return jsonify({"error": "Client not found"}), 404

    # Anonymize client info before sending
    anonymizer = Anonymizer()
    anonymized_info, token_map = anonymize_client_info(client_data["info"], anonymizer)
    anonymized_history = []
    history_token_map = {}
    for entry in client_data["history"]:
        tokenized_content, entry_tokens = anonymizer.tokenize(entry["content"])
        history_token_map.update(entry_tokens)
        anonymized_history.append({"role": entry["role"], "content": tokenized_content, "timestamp": entry["timestamp"]})

    anonymized_documents = []
    documents_token_map = {}
    for doc in client_data["documents"]:
        if doc["text"]:
            tokenized_text, doc_tokens = anonymizer.tokenize(doc["text"])
            documents_token_map.update(doc_tokens)
        else:
            tokenized_text = ""
        anonymized_documents.append({
            "filename": doc["filename"],
            "upload_date": doc["upload_date"],
            "text": tokenized_text
        })

    # Combine all token maps
    combined_token_map = {**token_map, **history_token_map, **documents_token_map}

    # De-tokenize before returning to the frontend (for display purposes)
    detokenized_info = anonymizer.detokenize(anonymized_info, combined_token_map)
    detokenized_history = [
        {"role": entry["role"], "content": anonymizer.detokenize(entry["content"], combined_token_map), "timestamp": entry["timestamp"]}
        for entry in anonymized_history
    ]
    detokenized_documents = [
        {
            "filename": doc["filename"],
            "upload_date": doc["upload_date"],
            "text": anonymizer.detokenize(doc["text"], combined_token_map)
        }
        for doc in anonymized_documents
    ]

    return jsonify({
        "info": detokenized_info,
        "history": detokenized_history,
        "documents": detokenized_documents
    })

@app.route('/api/new_conversation/<client_id>', methods=['POST'])
def new_conversation(client_id):
    client = Client.query.filter_by(id=client_id).first()
    if not client:
        return jsonify({"error": "Client not found"}), 404
    
    clear_conversation_history(client_id)
    logger.info(f"Started new conversation for client {client_id}")
    return jsonify({"success": True})

@app.route('/api/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400
    if file and '.' in file.filename and file.filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS:
        client_id = request.form.get('client_id', 'default_client')
        
        # Ensure client exists in database
        client = Client.query.filter_by(id=client_id).first()
        if not client:
            # Create client if it doesn't exist
            client = Client(id=client_id, name=f"Client {client_id}")
            db.session.add(client)
            db.session.commit()

        filename = secure_filename(file.filename)
        # Create the uploads directory in /tmp if it doesn't exist
        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)

        # For simplicity, assume text extraction for non-text files
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            text = f.read()

        # Anonymize file content before storing
        anonymizer = Anonymizer()
        tokenized_text, token_map = anonymizer.tokenize(text)

        # Add document to database
        doc = add_document(client_id, filename, tokenized_text)
        logger.info(f"Uploaded and tokenized file for client {client_id}: {filename}")

        # De-tokenize before returning to the frontend
        detokenized_text = anonymizer.detokenize(tokenized_text, token_map)
        return jsonify({"success": True, "text": detokenized_text})
    return jsonify({"error": "File type not allowed"}), 400

@app.route('/api/chat', methods=['POST'])
def chat():
    try:
        data = request.get_json()
        
        # Support both old format (messages array) and new format (single message)
        if 'message' in data:
            # New simplified format like fAIble
            message = data.get('message', '').strip()
            client_id = data.get('client_id', 'default_client')
        else:
            # Old format for backward compatibility
            messages = data.get('messages', [])
            client_id = data.get('client_id', 'default_client')
            if not messages:
                return jsonify({"error": "Message is required"}), 400
            message = messages[-1].get('content', '').strip()

        if not message:
            return jsonify({"error": "Message is required"}), 400

        logger.info(f"Chat request: client_id={client_id}, message='{message[:50]}...'")

        # Ensure client exists in database
        try:
            client = Client.query.filter_by(id=client_id).first()
            if not client:
                client = Client(id=client_id, name=f"Client {client_id}")
                db.session.add(client)
                db.session.commit()
                logger.info(f"Created new client: {client_id}")
        except Exception as e:
            logger.warning(f"Database operation failed: {e}")
            # Continue without database for now

        # Simple direct API call (without complex tokenization for now)
        payload = {
            "model": "grok-3-latest",
            "messages": [
                {"role": "system", "content": "You are a helpful legal assistant specializing in family law. Provide clear, professional guidance while noting that this is not formal legal advice."},
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
        logger.info(f"Received response from Grok API: {len(assistant_content)} characters")

        # Save to database if possible
        try:
            add_conversation(client_id, "user", message)
            add_conversation(client_id, "assistant", assistant_content)
            logger.info(f"Saved conversation to database")
        except Exception as e:
            logger.warning(f"Failed to save to database: {e}")
            # Continue without saving

        # Return response in the format expected by frontend
        return jsonify({
            "choices": [
                {
                    "delta": {
                        "content": assistant_content
                    }
                }
            ]
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

if __name__ == '__main__':
    app.run(debug=True)
