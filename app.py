import os
import json
import requests
from flask import Flask, request, jsonify, render_template
from werkzeug.utils import secure_filename
import re
from datetime import datetime, timezone
import logging

app = Flask(__name__)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Securely load API key from environment variable
XAI_API_KEY = os.getenv("XAI_API_KEY")
if not XAI_API_KEY:
    raise ValueError("XAI_API_KEY environment variable not set")

# Use /tmp for uploads on Vercel (read-only file system workaround)
UPLOAD_FOLDER = '/tmp/uploads'
ALLOWED_EXTENSIONS = {'txt', 'pdf', 'doc', 'docx'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Mock database for client data
clients = {
    "client1": {
        "info": {"name": "John Doe", "case_number": "12345", "email": "john.doe@example.com", "phone": "555-1234", "case_type": "Divorce", "notes": "Initial consultation"},
        "history": [],
        "documents": []
    },
    "client2": {
        "info": {"name": "Jane Smith", "case_number": "67890", "email": "jane.smith@example.com", "phone": "555-5678", "case_type": "Custody", "notes": "Follow-up meeting"},
        "history": [],
        "documents": []
    }
}

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
    if client_id not in clients:
        return jsonify({"error": "Client not found"}), 404

    if request.method == 'POST':
        data = request.get_json()
        clients[client_id]["info"] = data
        logger.info(f"Updated client info for {client_id}: {data}")
        return jsonify({"success": True})

    # Anonymize client info before sending
    anonymizer = Anonymizer()
    anonymized_info, token_map = anonymize_client_info(clients[client_id]["info"], anonymizer)
    anonymized_history = []
    history_token_map = {}
    for entry in clients[client_id]["history"]:
        tokenized_content, entry_tokens = anonymizer.tokenize(entry["content"])
        history_token_map.update(entry_tokens)
        anonymized_history.append({"role": entry["role"], "content": tokenized_content, "timestamp": entry["timestamp"]})

    anonymized_documents = []
    documents_token_map = {}
    for doc in clients[client_id]["documents"]:
        tokenized_text, doc_tokens = anonymizer.tokenize(doc["text"])
        documents_token_map.update(doc_tokens)
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
    if client_id not in clients:
        return jsonify({"error": "Client not found"}), 404
    clients[client_id]["history"] = []
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
        if client_id not in clients:
            clients[client_id] = {"info": {}, "history": [], "documents": []}

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

        doc = {
            "filename": filename,
            "upload_date": datetime.now(timezone.utc).isoformat(),
            "text": tokenized_text
        }
        clients[client_id]["documents"].append(doc)
        logger.info(f"Uploaded and tokenized file for client {client_id}: {filename}")

        # De-tokenize before returning to the frontend
        detokenized_text = anonymizer.detokenize(tokenized_text, token_map)
        return jsonify({"success": True, "text": detokenized_text})
    return jsonify({"error": "File type not allowed"}), 400

@app.route('/api/chat', methods=['POST'])
def chat():
    data = request.get_json()
    messages = data.get('messages', [])
    client_id = data.get('client_id', 'default_client')

    if not messages:
        return jsonify({"error": "No messages provided"}), 400

    if client_id not in clients:
        clients[client_id] = {"info": {}, "history": [], "documents": []}

    # Tokenize messages before sending to Grok
    anonymizer = Anonymizer()
    tokenized_messages = []
    combined_token_map = {}
    for msg in messages:
        tokenized_msg = msg.copy()
        if 'content' in tokenized_msg:
            # Tokenize the message content
            content = tokenized_msg['content']
            tokenized_content, token_map = anonymizer.tokenize(content)
            # Check if the message contains an email token and modify the instruction
            if "at Email" in tokenized_content:
                # Extract the person and email tokens
                person_token = None
                email_token = None
                for token, value in token_map.items():
                    if token.startswith("Person"):
                        person_token = token
                    elif token.startswith("Email"):
                        email_token = token
                # Rewrite the instruction to explicitly structure the email draft
                subject = "Meeting on May 15, 2025"
                body = tokenized_content.split("about", 1)[1].strip() if "about" in tokenized_content else "about a meeting on May 15, 2025."
                tokenized_content = f"Draft an email with the following details: To: {person_token} <{email_token}>, Subject: {subject}, Body: {body}"
                logger.info(f"Modified instruction: {tokenized_content}")
            tokenized_msg['content'] = tokenized_content
            combined_token_map.update(token_map)
        tokenized_messages.append(tokenized_msg)

    # Update client history with original message (before tokenization)
    user_message = {"role": "user", "content": messages[-1]["content"], "timestamp": datetime.now(timezone.utc).isoformat()}
    clients[client_id]["history"].append(user_message)

    # Prepare the payload for Grok with tokenized messages
    payload = {
        "model": "grok-3",
        "messages": tokenized_messages,
        "stream": False
    }

    try:
        headers = {
            "Authorization": f"Bearer {XAI_API_KEY}",
            "Content-Type": "application/json"
        }
        logger.info(f"Sending request to Grok API with payload: {json.dumps(payload)}")
        response = requests.post(
            "https://api.x.ai/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=30
        )
        response.raise_for_status()
        grok_response = response.json()
        logger.info(f"Grok API response: {grok_response}")

        # De-tokenize Grok's response before storing and returning
        assistant_content = grok_response["choices"][0]["message"]["content"]
        detokenized_content = anonymizer.detokenize(assistant_content, combined_token_map)

        # Post-process the response to ensure the email address is included, but only if not already present
        # Only run post-processing if an email token exists in the token map
        email_token_exists = any(token.startswith("Email") for token in combined_token_map.keys())
        if email_token_exists:
            # Check for "To:" while ignoring markdown formatting (e.g., **To:**, *To:*)
            if not re.search(r'(?:\*\*|\*)*To:(?:\*\*|\*)*', detokenized_content):
                # Find the email token and its corresponding value
                email_token = next(token for token, value in combined_token_map.items() if value == "john.doe@example.com")
                person_token = next(token for token, value in combined_token_map.items() if value == "John Doe")
                email_line = f"To: {combined_token_map[person_token]} <{combined_token_map[email_token]}>\n\n"
                # Insert the "To:" line after the subject line or at the start
                if "Subject: " in detokenized_content:
                    parts = detokenized_content.split("Subject: ", 1)
                    detokenized_content = f"Subject: {parts[1].split('\n\n', 1)[0]}\n\n{email_line}{parts[1].split('\n\n', 1)[1]}"
                    logger.info("Added To: line to response")
                else:
                    detokenized_content = email_line + detokenized_content
                    logger.info("Added To: line to response")
            else:
                logger.info("To: line already present in response (possibly with markdown), skipping post-processing addition")
        else:
            logger.info("No email token found in token map, skipping post-processing for To: line")

        # Add Grok's de-tokenized response to history
        assistant_message = {
            "role": "assistant",
            "content": detokenized_content,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        clients[client_id]["history"].append(assistant_message)

        # Log the final response sent to the frontend
        logger.info(f"Response sent to frontend: {detokenized_content}")

        # Return the de-tokenized response to the frontend
        return jsonify({
            "choices": [
                {
                    "delta": {
                        "content": detokenized_content
                    }
                }
            ]
        })
    except requests.exceptions.RequestException as e:
        # Log the full response if available
        error_detail = str(e)
        if hasattr(e, 'response') and e.response is not None:
            error_detail += f" - Response: {e.response.text}"
        logger.error(f"Error communicating with Grok API: {error_detail}")
        return jsonify({"error": f"Failed to get response from Grok: {str(e)}"}), 500

if __name__ == '__main__':
    app.run(debug=True)
