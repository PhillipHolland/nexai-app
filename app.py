from flask import Flask, request, render_template, jsonify, Response
import requests
import os

app = Flask(__name__)

# xAI API configuration
XAI_API_KEY = os.getenv("XAI_API_KEY", "default_key_if_not_set")
XAI_API_URL = "https://api.x.ai/v1/chat/completions"

# Simulated client data
clients = ["jane_smith", "john_doe"]

@app.route('/')
def index():
    # Serve the main UI directly, no login required
    return render_template('index.html', clients=clients)

@app.route('/api/client/<client_id>', methods=['GET'])
def get_client(client_id):
    # Avoid strict JSON parsing for GET requests (no body expected)
    data = {
        'info': {'name': client_id, 'case_number': '123', 'email': '', 'phone': '', 'case_type': '', 'notes': ''},
        'history': [],
        'documents': []
    }
    return jsonify(data), 200

@app.route('/api/new_conversation/<client_id>', methods=['POST'])
def new_conversation(client_id):
    # Handle JSON requests gracefully
    if request.is_json:
        # Process JSON data if present
        data = request.get_json()
    else:
        # Fallback for non-JSON requests
        data = {}
    # Simulate clearing conversation
    return jsonify({'success': True}), 200

@app.route('/api/upload', methods=['POST'])
def upload_file():
    # Handle multipart/form-data for file uploads
    file = request.files.get('file')
    client_id = request.form.get('client_id', 'default_client')  # Default to "default_client" if not provided
    if not file:
        return jsonify({'error': 'Missing file'}), 400
    # Simulate file processing
    return jsonify({'text': 'Sample file content'}), 200

@app.route('/api/chat', methods=['POST'])
def chat():
    # Handle JSON requests gracefully
    if request.is_json:
        data = request.get_json()
        messages = data.get('messages', [])
        client_id = data.get('client_id', 'default_client')  # Default to "default_client" if not provided
    else:
        # Fallback for non-JSON requests
        return jsonify({'error': 'Expected application/json'}), 415

    # Prepare the payload for the xAI API
    payload = {
        "messages": messages,
        "model": "grok-3-latest",
        "stream": False,
        "temperature": 0
    }

    # Set up headers with the API key
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {XAI_API_KEY}"
    }

    try:
        # Send request to xAI API
        response = requests.post(XAI_API_URL, json=payload, headers=headers)
        response.raise_for_status()  # Raise an exception for HTTP errors
        api_response = response.json()
        print(f"xAI API response: {api_response}")  # Log the response for debugging

        # Format the response to match what the frontend expects
        # Frontend expects {"choices": [{"delta": {"content": "..."}}]}
        if "choices" in api_response and len(api_response["choices"]) > 0:
            content = api_response["choices"][0].get("message", {}).get("content", "No response content")
            formatted_response = {
                "choices": [
                    {
                        "delta": {
                            "content": content
                        }
                    }
                ]
            }
            return jsonify(formatted_response), 200
        else:
            return jsonify({'error': 'Invalid response from xAI API'}), 500

    except requests.exceptions.RequestException as e:
        print(f"Error calling xAI API: {e}")
        return jsonify({'error': f'Failed to call xAI API: {str(e)}'}), 500

@app.route('/api/client/<client_id>', methods=['POST'])
def save_client(client_id):
    # Handle JSON requests gracefully
    if request.is_json:
        data = request.get_json()
    else:
        return jsonify({'error': 'Expected application/json'}), 415
    # Simulate saving client info
    return jsonify({'success': True}), 200

if __name__ == '__main__':
    app.run(debug=True)
